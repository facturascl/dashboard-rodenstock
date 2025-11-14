
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os
from datetime import datetime, timedelta
import random

DB_FILE = "facturas.db"

# ============================================================================
# AUTO-INITIALIZE DATABASE IF NOT EXISTS
# ============================================================================

def init_database_if_needed():
    """Crea la BD automáticamente si no existe"""
    if os.path.exists(DB_FILE):
        return
    
    st.info("⏳ Creando base de datos con datos históricos... (esto toma ~1 minuto)")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Crear tablas
    cursor.execute('''
    CREATE TABLE facturas (
        numerofactura TEXT PRIMARY KEY,
        fechaemision TEXT,
        subtotal REAL,
        iva REAL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE lineas_factura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numerofactura TEXT,
        clasificacion_categoria TEXT,
        clasificacion_subcategoria TEXT,
        FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura)
    )
    ''')
    
    # Categorías
    categorias = {
        'Monofocales': ['Policarbonato azul', 'Hi-index Verde', 'Polarizado', 'Fotocromático', 'Policarbonato verde', 'CR39'],
        'Progresivo': ['Verde', 'Azul', 'Fotocromático'],
        'Newton': ['Newton Standard'],
        'Newton Plus': ['Newton Plus Premium'],
    }
    
    yearly_facturas = {
        2020: 4500,
        2021: 6000,
        2022: 6500,
        2023: 6500,
        2024: 6500,
        2025: 4500
    }
    
    def get_categoria():
        cat_choice = random.randint(1, 100)
        if cat_choice <= 57:
            return 'Monofocales'
        elif cat_choice <= 97:
            return 'Progresivo'
        elif cat_choice <= 99:
            return 'Newton'
        else:
            return 'Newton Plus'
    
    factura_num = 1000
    for year in range(2020, 2026):
        if year == 2025:
            meses_activos = 11  # Enero a Noviembre
        else:
            meses_activos = 12
        
        num_facturas = yearly_facturas[year]
        facturas_por_mes = num_facturas // meses_activos
        facturas_restantes = num_facturas % meses_activos
        
        for mes in range(1, meses_activos + 1):
            cant_facturas_este_mes = facturas_por_mes + (1 if mes <= facturas_restantes else 0)
            
            if mes < 12:
                proximus_mes = datetime(year, mes + 1, 1)
            else:
                proximus_mes = datetime(year + 1, 1, 1)
            
            start_date = datetime(year, mes, 1)
            end_date = proximus_mes - timedelta(days=1)
            days_diff = (end_date - start_date).days + 1
            
            for i in range(cant_facturas_este_mes):
                posicion = i / max(cant_facturas_este_mes - 1, 1) if cant_facturas_este_mes > 1 else 0.5
                dia_offset = int(days_diff * posicion)
                fecha = start_date + timedelta(days=dia_offset)
                fecha_str = fecha.strftime('%Y-%m-%d')
                
                numerofactura = f"FAC{factura_num:06d}"
                factura_num += 1
            
            subtotal = round(random.uniform(100, 5000), 2)
            iva = round(subtotal * 0.19, 2)
            
            cursor.execute(
                'INSERT OR IGNORE INTO facturas VALUES (?, ?, ?, ?)',
                (numerofactura, fecha_str, subtotal, iva)
            )
            
            categoria = get_categoria()
            subcategoria = random.choice(categorias.get(categoria, ['Sin subcategoría']))
            
            cursor.execute(
                'INSERT INTO lineas_factura (numerofactura, clasificacion_categoria, clasificacion_subcategoria) VALUES (?, ?, ?)',
                (numerofactura, categoria, subcategoria)
            )
    
    conn.commit()
    conn.close()
    st.success("✓ Base de datos creada exitosamente")

# ============================================================================
# STREAMLIT CONFIG
# ============================================================================

# Ejecutar inicialización
init_database_if_needed()

st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_conn():
    """Retorna conexión a la BD sin cache"""
    return sqlite3.connect(DB_FILE)

@st.cache_data(ttl=600)
def get_anos_disponibles():
    conn = get_conn()
    query = """
    SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) AS ano 
    FROM facturas WHERE fechaemision IS NOT NULL
    ORDER BY ano DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        anos = sorted(set(df['ano'].tolist())) if not df.empty else [datetime.now().year]
        return sorted(anos, reverse=True)
    except Exception as e:
        conn.close()
        return [datetime.now().year]

@st.cache_data(ttl=600)
def get_meses_por_ano(ano):
    conn = get_conn()
    query = f"""
    SELECT DISTINCT STRFTIME('%m', fechaemision) AS mes
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano}
    ORDER BY mes
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return sorted(df['mes'].tolist()) if not df.empty else []
    except Exception as e:
        conn.close()
        return []

def format_currency(value):
    if value is None or pd.isna(value):
        return "$0"
    try:
        return f"${int(round(float(value))):,}"
    except:
        return "$0"

def mes_nombre(mes_num):
    meses = {'01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril', 
             '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
             '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'}
    return meses.get(str(mes_num).zfill(2), mes_num)

@st.cache_data(ttl=600)
def get_evolucion_mensual(ano):
    """Evolución mensual de trabajos e ingresos"""
    conn = get_conn()
    query = f"""
    SELECT
      STRFTIME('%m', f.fechaemision) AS mes,
      COUNT(DISTINCT f.numerofactura) AS cantidad_facturas,
      ROUND(SUM(f.subtotal + f.iva), 2) AS total_mes
    FROM facturas f
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
    GROUP BY mes
    ORDER BY mes
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['mes_nombre'] = df['mes'].apply(lambda x: mes_nombre(x))
    return df

@st.cache_data(ttl=600)
def get_categorias_por_periodo(ano, mes=None):
    """Replicación exacta del CTE facturas_clasificadas de BigQuery"""
    conn = get_conn()
    
    filtro_mes = ""
    if mes:
        filtro_mes = f"AND STRFTIME('%m', f.fechaemision) = '{mes}'"
    
    query = f"""
    WITH facturas_clasificadas AS (
      SELECT
        f.numerofactura,
        f.fechaemision,
        CASE 
          WHEN lf.clasificacion_categoria IS NULL 
            OR lf.clasificacion_categoria = 'Sin clasificacion' 
            OR TRIM(lf.clasificacion_categoria) = ''
          THEN 'Otros'
          ELSE lf.clasificacion_categoria || ' ' || COALESCE(lf.clasificacion_subcategoria, '')
        END AS categoria_unificada,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
        {filtro_mes}
      GROUP BY f.numerofactura, f.fechaemision, categoria_unificada, total_factura
    ),
    resumen_categorias AS (
      SELECT
        categoria_unificada,
        COUNT(DISTINCT numerofactura) AS cantidad_trabajos,
        SUM(total_factura) AS total_dinero,
        AVG(total_factura) AS promedio_trabajo
      FROM facturas_clasificadas
      GROUP BY categoria_unificada
    ),
    totales_periodo AS (
      SELECT
        SUM(total_dinero) AS total_mes,
        SUM(cantidad_trabajos) AS total_trabajos
      FROM resumen_categorias
    )
    SELECT
      rc.categoria_unificada AS categoria,
      rc.cantidad_trabajos AS total_facturas,
      ROUND(rc.total_dinero, 2) AS total_ingresos,
      ROUND(rc.promedio_trabajo, 2) AS promedio_factura,
      ROUND((rc.total_dinero / tp.total_mes) * 100, 2) AS porcentaje
    FROM resumen_categorias rc
    CROSS JOIN totales_periodo tp
    ORDER BY total_ingresos DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def get_subcategorias_por_periodo(ano, mes=None, categoria=None):
    """Subcategorías con lógica correcta de conteo de facturas únicas"""
    conn = get_conn()
    
    filtro_mes = ""
    if mes:
        filtro_mes = f"AND STRFTIME('%m', f.fechaemision) = '{mes}'"
    
    filtro_cat = ""
    if categoria:
        categoria_clean = categoria.replace("'", "''")
        filtro_cat = f"AND lf.clasificacion_categoria = '{categoria_clean}'"
    
    query = f"""
    WITH facturas_clasificadas AS (
      SELECT
        f.numerofactura,
        f.fechaemision,
        lf.clasificacion_categoria,
        lf.clasificacion_subcategoria,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
        AND lf.clasificacion_categoria IS NOT NULL
        {filtro_mes}
        {filtro_cat}
      GROUP BY f.numerofactura, f.fechaemision, lf.clasificacion_categoria, lf.clasificacion_subcategoria, total_factura
    ),
    resumen_subcategorias AS (
      SELECT
        clasificacion_categoria,
        clasificacion_subcategoria,
        COUNT(DISTINCT numerofactura) AS cantidad_trabajos,
        SUM(total_factura) AS total_dinero,
        AVG(total_factura) AS promedio_trabajo
      FROM facturas_clasificadas
      GROUP BY clasificacion_categoria, clasificacion_subcategoria
    ),
    totales_periodo AS (
      SELECT
        SUM(total_dinero) AS total_mes,
        SUM(cantidad_trabajos) AS total_trabajos
      FROM resumen_subcategorias
    )
    SELECT
      rs.clasificacion_categoria AS categoria,
      rs.clasificacion_subcategoria AS subcategoria,
      rs.cantidad_trabajos AS total_facturas,
      ROUND(rs.total_dinero, 2) AS total_ingresos,
      ROUND(rs.promedio_trabajo, 2) AS promedio_factura,
      ROUND((rs.total_dinero / tp.total_mes) * 100, 2) AS porcentaje
    FROM resumen_subcategorias rs
    CROSS JOIN totales_periodo tp
    ORDER BY total_ingresos DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def get_comparativa_mes_categoria(ano):
    """Comparativa por mes y categoría"""
    conn = get_conn()
    query = f"""
    WITH facturas_clasificadas AS (
      SELECT
        STRFTIME('%m', f.fechaemision) AS mes,
        f.numerofactura,
        CASE 
          WHEN lf.clasificacion_categoria IS NULL 
            OR lf.clasificacion_categoria = 'Sin clasificacion'
          THEN 'Otros'
          ELSE lf.clasificacion_categoria
        END AS categoria,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
      GROUP BY mes, f.numerofactura, categoria, total_factura
    ),
    resumen_mes_cat AS (
      SELECT
        mes,
        categoria,
        COUNT(DISTINCT numerofactura) AS total_facturas,
        SUM(total_factura) AS total_ingresos,
        AVG(total_factura) AS promedio_factura
      FROM facturas_clasificadas
      GROUP BY mes, categoria
    ),
    totales_mes AS (
      SELECT
        mes,
        SUM(total_ingresos) AS total_mes,
        SUM(total_facturas) AS total_trabajos
      FROM resumen_mes_cat
      GROUP BY mes
    )
    SELECT
      rmc.mes,
      rmc.categoria,
      rmc.total_facturas,
      ROUND(rmc.total_ingresos, 2) AS total_ingresos,
      ROUND(rmc.promedio_factura, 2) AS promedio_factura,
      ROUND((rmc.total_ingresos / tm.total_mes) * 100, 2) AS porcentaje_mes
    FROM resumen_mes_cat rmc
    INNER JOIN totales_mes tm ON rmc.mes = tm.mes
    ORDER BY rmc.mes, rmc.total_ingresos DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['mes_nombre'] = df['mes'].apply(lambda x: mes_nombre(x))
    return df

@st.cache_data(ttl=600)
def get_totales_periodo(ano, mes=None):
    """Totales generales del período"""
    conn = get_conn()
    filtro_mes = ""
    if mes:
        filtro_mes = f"AND STRFTIME('%m', fechaemision) = '{mes}'"
    
    query = f"""
    SELECT
      COUNT(DISTINCT numerofactura) AS total_facturas,
      ROUND(SUM(subtotal), 2) AS total_subtotal,
      ROUND(SUM(iva), 2) AS total_iva,
      ROUND(SUM(subtotal + iva), 2) AS total_ingresos,
      ROUND(AVG(subtotal + iva), 2) AS promedio_factura
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano}
      {filtro_mes}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def get_newton_diario(ano, mes=None):
    """Análisis diario de Newton y Newton Plus"""
    conn = get_conn()
    
    filtro_mes = ""
    if mes:
        filtro_mes = f"AND STRFTIME('%m', f.fechaemision) = '{mes}'"
    
    query = f"""
    WITH trabajos AS (
      SELECT
        DATE(f.fechaemision) AS dia,
        f.numerofactura,
        MAX(CASE WHEN lf.clasificacion_categoria = 'Newton' THEN 1 ELSE 0 END) AS trabajo_newton,
        MAX(CASE WHEN lf.clasificacion_categoria = 'Newton Plus' THEN 1 ELSE 0 END) AS trabajo_newton_plus,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
        {filtro_mes}
        AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
      GROUP BY dia, f.numerofactura, total_factura
    ),
    resumen_diario AS (
      SELECT
        dia,
        SUM(trabajo_newton) AS cantidad_newton,
        SUM(CASE WHEN trabajo_newton = 1 THEN total_factura ELSE 0 END) AS total_newton,
        SUM(trabajo_newton_plus) AS cantidad_newton_plus,
        SUM(CASE WHEN trabajo_newton_plus = 1 THEN total_factura ELSE 0 END) AS total_newton_plus
      FROM trabajos
      GROUP BY dia
    )
    SELECT
      dia,
      cantidad_newton,
      ROUND(total_newton, 2) AS total_newton,
      CASE WHEN cantidad_newton > 0 THEN ROUND(total_newton / cantidad_newton, 2) ELSE NULL END AS promedio_diario_newton,
      cantidad_newton_plus,
      ROUND(total_newton_plus, 2) AS total_newton_plus,
      CASE WHEN cantidad_newton_plus > 0 THEN ROUND(total_newton_plus / cantidad_newton_plus, 2) ELSE NULL END AS promedio_diario_newton_plus,
      ROUND(SUM(total_newton) OVER () / NULLIF(SUM(cantidad_newton) OVER (), 0), 2) AS promedio_global_newton,
      ROUND(SUM(total_newton_plus) OVER () / NULLIF(SUM(cantidad_newton_plus) OVER (), 0), 2) AS promedio_global_newton_plus
    FROM resumen_diario
    ORDER BY dia DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ============================================================================
# UI
# ============================================================================

st.title("📊 Dashboard de Facturación Rodenstock")
st.markdown("---")

with st.sidebar:
    st.header("🔧 Filtros")
    
    anos_disponibles = get_anos_disponibles()
    ano_seleccionado = st.selectbox("📅 Año", options=anos_disponibles, index=0)
    
    meses_disponibles = get_meses_por_ano(ano_seleccionado)
    mes_options = ["Todos"] + meses_disponibles
    mes_seleccionado = st.selectbox(
        "📆 Mes",
        options=mes_options,
        index=0,
        help="Selecciona 'Todos' para ver todo el año"
    )
    
    mes_param = None if mes_seleccionado == "Todos" else mes_seleccionado
    
    st.markdown("---")
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.header("📈 Resumen General")

totales = get_totales_periodo(ano_seleccionado, mes_param)

if not totales.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📋 Trabajos (Facturas)", f"{int(totales['total_facturas'].iloc[0]):,}")
    with col2:
        st.metric("💵 Subtotal", format_currency(totales['total_subtotal'].iloc[0]))
    with col3:
        st.metric("📊 IVA", format_currency(totales['total_iva'].iloc[0]))
    with col4:
        st.metric("💰 Total", format_currency(totales['total_ingresos'].iloc[0]))
    with col5:
        st.metric("📈 Promedio", format_currency(totales['promedio_factura'].iloc[0]))

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Evolución Mensual",
    "🏆 Categorías",
    "🎯 Subcategorías",
    "📈 Análisis",
    "⚡ Newton vs Newton+",
    "🔍 Comparativa"
])

with tab1:
    st.subheader(f"📊 Evolución Mensual {ano_seleccionado}")
    
    df_mes = get_evolucion_mensual(ano_seleccionado)
    
    if not df_mes.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df_mes['mes_nombre'],
            y=df_mes['cantidad_facturas'],
            name='Trabajos (Facturas)',
            marker_color='rgba(33, 128, 141, 0.7)',
            yaxis='y1'
        ))
        
        fig.add_trace(go.Scatter(
            x=df_mes['mes_nombre'],
            y=df_mes['total_mes'],
            name='Total Ingresos (Subtotal + IVA)',
            mode='lines+markers',
            line=dict(color='#FF6B6B', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title=f'Facturas e Ingresos por Mes - {ano_seleccionado}',
            xaxis=dict(title='Mes'),
            yaxis=dict(
                title=dict(text='Cantidad de Trabajos', font=dict(color='#208085')),
                tickfont=dict(color='#208085')
            ),
            yaxis2=dict(
                title=dict(text='Total Ingresos ($)', font=dict(color='#FF6B6B')),
                tickfont=dict(color='#FF6B6B'),
                overlaying='y',
                side='right'
            ),
            height=400,
            hovermode='x unified',
            legend=dict(x=0.01, y=0.99)
        )
        
        st.plotly_chart(fig, use_container_width=True, key="evolución_mensual")
        
        st.markdown("#### 📋 Detalles por Mes")
        df_display = df_mes.copy()
        df_display['cantidad_facturas'] = df_display['cantidad_facturas'].apply(lambda x: f"{int(x):,}")
        df_display['total_mes'] = df_display['total_mes'].apply(format_currency)
        df_display = df_display[['mes_nombre', 'cantidad_facturas', 'total_mes']]
        df_display.columns = ['Mes', 'Trabajos', 'Total']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos disponibles")

with tab2:
    st.subheader(f"🏆 Análisis por Categoría - {ano_seleccionado}" + (f" / {mes_nombre(mes_seleccionado)}" if mes_param else ""))
    
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    
    if not df_cat.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                df_cat,
                values='total_ingresos',
                names='categoria',
                title='Distribución de Ingresos por Categoría'
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="pie_categoria")
        
        with col2:
            df_sorted = df_cat.sort_values('total_ingresos')
            fig_bar = px.bar(
                df_sorted,
                y='categoria',
                x='total_ingresos',
                orientation='h',
                title='Total Ingresos por Categoría',
                color='total_ingresos',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_bar, use_container_width=True, key="bar_categoria_ingresos")
        
        st.markdown("#### 📊 Resumen por Categoría")
        df_display = df_cat.copy()
        df_display['total_facturas'] = df_display['total_facturas'].apply(lambda x: f"{int(x):,}")
        df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
        df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
        df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.1f}%")
        df_display = df_display.rename(columns={
            'categoria': 'Categoría',
            'total_facturas': 'Trabajos',
            'total_ingresos': 'Total',
            'promedio_factura': 'Promedio/Trabajo',
            'porcentaje': '% Total'
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay datos")

with tab3:
    st.subheader(f"🎯 Análisis por Subcategoría - {ano_seleccionado}" + (f" / {mes_nombre(mes_seleccionado)}" if mes_param else ""))
    
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    
    if not df_cat.empty:
        categorias = sorted([c for c in df_cat['categoria'].unique() if c and c != 'Otros'])
        categorias.insert(0, 'Todas')
        cat_seleccionada = st.selectbox("Filtrar por Categoría", categorias, key="tab3_cat")
        
        if cat_seleccionada == 'Todas':
            df_subcat = get_subcategorias_por_periodo(ano_seleccionado, mes_param)
        else:
            df_subcat = get_subcategorias_por_periodo(ano_seleccionado, mes_param, cat_seleccionada.split()[0])
        
        if not df_subcat.empty:
            total_trabajos_periodo = df_subcat['total_facturas'].sum()
            
            col1, col2 = st.columns(2)
            
            with col1:
                df_subcat_chart = df_subcat.copy()
                df_subcat_chart['label'] = df_subcat_chart['subcategoria'] + ' (' + df_subcat_chart['categoria'] + ')'
                df_sorted = df_subcat_chart.sort_values('total_ingresos', ascending=True)
                fig = px.bar(
                    df_sorted,
                    y='label',
                    x='total_ingresos',
                    orientation='h',
                    title='Total Ingresos por Subcategoría',
                    color='total_ingresos',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig, use_container_width=True, key="bar_subcategoria")
            
            with col2:
                st.metric("Total de Trabajos", f"{total_trabajos_periodo:,}")
                st.metric("Total Ingresos", format_currency(df_subcat['total_ingresos'].sum()))
                st.metric("Promedio Gral.", format_currency(df_subcat['promedio_factura'].mean()))
            
            st.markdown("#### 📋 Detalle Subcategorías")
            df_display = df_subcat.copy()
            df_display['total_facturas'] = df_display['total_facturas'].apply(lambda x: f"{int(x):,}")
            df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
            df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
            df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.1f}%")
            df_display = df_display.rename(columns={
                'categoria': 'Categoría',
                'subcategoria': 'Subcategoría',
                'total_facturas': 'Trabajos',
                'total_ingresos': 'Total',
                'promedio_factura': 'Promedio/Trabajo',
                'porcentaje': '% Total'
            })
            df_display = df_display[['Categoría', 'Subcategoría', 'Trabajos', 'Total', 'Promedio/Trabajo', '% Total']]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.warning("No hay datos para esta categoría")
    else:
        st.warning("No hay datos")

with tab4:
    st.subheader(f"📈 Análisis de Pareto - {ano_seleccionado}" + (f" / {mes_nombre(mes_seleccionado)}" if mes_param else ""))
    
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    
    if not df_cat.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Categorías", len(df_cat))
        with col2:
            st.metric("Total Trabajos", f"{int(df_cat['total_facturas'].sum()):,}")
        with col3:
            st.metric("Total Ingresos", format_currency(df_cat['total_ingresos'].sum()))
        with col4:
            st.metric("Promedio Gral.", format_currency(df_cat['promedio_factura'].mean()))
        
        st.markdown("---")
        
        st.markdown("#### 📊 Análisis de Pareto - Categorías")
        
        df_pareto = df_cat.sort_values('total_ingresos', ascending=False).copy()
        df_pareto['acumulado'] = df_pareto['total_ingresos'].cumsum()
        df_pareto['porcentaje_acum'] = (df_pareto['acumulado'] / df_pareto['total_ingresos'].sum() * 100)
        
        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(
            x=df_pareto['categoria'],
            y=df_pareto['total_ingresos'],
            name='Ingresos',
            marker_color='#208085'
        ))
        fig_pareto.add_trace(go.Scatter(
            x=df_pareto['categoria'],
            y=df_pareto['porcentaje_acum'],
            name='% Acumulado',
            yaxis='y2',
            line=dict(color='#FF6B6B', width=3),
            mode='lines+markers'
        ))
        
        fig_pareto.update_layout(
            yaxis=dict(title='Ingresos ($)'),
            yaxis2=dict(title='% Acumulado', overlaying='y', side='right'),
            title='Análisis de Pareto - Categorías',
            height=400
        )
        st.plotly_chart(fig_pareto, use_container_width=True, key="pareto_categoria")
    else:
        st.warning("No hay datos")

with tab5:
    st.subheader(f"⚡ Análisis Diario: Newton vs Newton Plus - {ano_seleccionado}" + (f" / {mes_nombre(mes_seleccionado)}" if mes_param else ""))
    
    df_newton = get_newton_diario(ano_seleccionado, mes_param)
    
    if not df_newton.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_newton = df_newton['cantidad_newton'].sum()
            st.metric("📦 Total Trabajos Newton", f"{int(total_newton):,}")
        with col2:
            total_newton_plus = df_newton['cantidad_newton_plus'].sum()
            st.metric("🚀 Total Trabajos Newton Plus", f"{int(total_newton_plus):,}")
        with col3:
            prom_newton = df_newton['promedio_global_newton'].iloc[0]
            st.metric("💰 Promedio Newton", format_currency(prom_newton))
        with col4:
            prom_newton_plus = df_newton['promedio_global_newton_plus'].iloc[0]
            st.metric("💎 Promedio Newton Plus", format_currency(prom_newton_plus))
        
        st.markdown("---")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df_newton['dia'],
            y=df_newton['cantidad_newton'],
            name='Trabajos Newton',
            marker_color='rgba(33, 128, 141, 0.7)'
        ))
        
        fig.add_trace(go.Bar(
            x=df_newton['dia'],
            y=df_newton['cantidad_newton_plus'],
            name='Trabajos Newton Plus',
            marker_color='rgba(255, 107, 107, 0.7)'
        ))
        
        fig.update_layout(
            barmode='group',
            title='Cantidad de Trabajos Diarios: Newton vs Newton Plus',
            xaxis_title='Día',
            yaxis_title='Cantidad de Trabajos',
            height=400,
            hovermode='x unified',
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig, use_container_width=True, key="newton_barras")
        
        fig2 = go.Figure()
        
        fig2.add_trace(go.Scatter(
            x=df_newton['dia'],
            y=df_newton['promedio_diario_newton'],
            name='Promedio Diario Newton',
            mode='lines+markers',
            line=dict(color='#208085', width=2)
        ))
        
        fig2.add_trace(go.Scatter(
            x=df_newton['dia'],
            y=df_newton['promedio_diario_newton_plus'],
            name='Promedio Diario Newton Plus',
            mode='lines+markers',
            line=dict(color='#FF6B6B', width=2)
        ))
        
        fig2.update_layout(
            title='Promedio de Costo Diario: Newton vs Newton Plus',
            xaxis_title='Día',
            yaxis_title='Promedio ($)',
            height=400,
            hovermode='x unified',
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig2, use_container_width=True, key="newton_promedios")
        
        st.markdown("#### 📋 Detalles Diarios")
        df_display = df_newton.copy()
        df_display['dia'] = df_display['dia'].astype(str)
        df_display['total_newton'] = df_display['total_newton'].apply(format_currency)
        df_display['promedio_diario_newton'] = df_display['promedio_diario_newton'].apply(format_currency)
        df_display['total_newton_plus'] = df_display['total_newton_plus'].apply(format_currency)
        df_display['promedio_diario_newton_plus'] = df_display['promedio_diario_newton_plus'].apply(format_currency)
        df_display['promedio_global_newton'] = df_display['promedio_global_newton'].apply(format_currency)
        df_display['promedio_global_newton_plus'] = df_display['promedio_global_newton_plus'].apply(format_currency)
        
        df_display = df_display[[
            'dia', 'cantidad_newton', 'total_newton', 'promedio_diario_newton',
            'cantidad_newton_plus', 'total_newton_plus', 'promedio_diario_newton_plus',
            'promedio_global_newton', 'promedio_global_newton_plus'
        ]]
        df_display.columns = [
            'Día', 'Cant. Newton', 'Total Newton', 'Prom. Diario Newton',
            'Cant. Newton+', 'Total Newton+', 'Prom. Diario Newton+',
            'Prom. Global Newton', 'Prom. Global Newton+'
        ]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos de Newton o Newton Plus para este período")

with tab6:
    st.subheader(f"🔍 Comparativa por Mes - {ano_seleccionado}")
    
    df_comp_cat = get_comparativa_mes_categoria(ano_seleccionado)
    
    if not df_comp_cat.empty:
        st.markdown("### 📊 Comparativa por Categoría (Mensual)")
        
        df_display = df_comp_cat.copy()
        df_display['total_facturas'] = df_display['total_facturas'].apply(lambda x: f"{int(x):,}")
        df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
        df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
        df_display['porcentaje_mes'] = df_display['porcentaje_mes'].apply(lambda x: f"{x:.1f}%")
        df_display = df_display[['mes_nombre', 'categoria', 'total_facturas', 'total_ingresos', 'promedio_factura', 'porcentaje_mes']]
        df_display.columns = ['Mes', 'Categoría', 'Trabajos', 'Total ($)', 'Promedio/Trabajo', '% Mes']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay datos")

st.markdown("---")
st.caption("📊 Dashboard Rodenstock | © 2025 | ✓ Auto-Init con Datos Históricos 2020-2025")
