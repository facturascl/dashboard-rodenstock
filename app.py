
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

DB_FILE = "facturas.db"

# ============================================================================
# CONFIG STREAMLIT
# ============================================================================

st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# FUNCIONES DB
# ============================================================================

def get_conn():
    """Retorna conexión a la BD"""
    return sqlite3.connect(DB_FILE)

@st.cache_data(ttl=600)
def get_anos_disponibles():
    """Años únicos disponibles en BD"""
    conn = get_conn()
    try:
        query = """
        SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) AS ano 
        FROM facturas WHERE fechaemision IS NOT NULL
        ORDER BY ano DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        anos = sorted(set(df['ano'].tolist())) if not df.empty else [datetime.now().year]
        return sorted(anos, reverse=True)
    except Exception as e:
        conn.close()
        return [datetime.now().year]

@st.cache_data(ttl=600)
def get_meses_por_ano(ano):
    """Meses únicos del año seleccionado"""
    conn = get_conn()
    try:
        query = f"""
        SELECT DISTINCT STRFTIME('%m', fechaemision) AS mes
        FROM facturas
        WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano}
        ORDER BY mes
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return sorted(df['mes'].tolist()) if not df.empty else []
    except Exception as e:
        conn.close()
        return []

def format_currency(value):
    """Formatea número como moneda"""
    if value is None or pd.isna(value):
        return "$0"
    try:
        return f"${int(round(float(value))):,}"
    except:
        return "$0"

def mes_nombre(mes_num):
    """Convierte número de mes a nombre"""
    meses = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    return meses.get(str(mes_num).zfill(2), mes_num)

@st.cache_data(ttl=600)
def get_evolucion_mensual(ano):
    """Evolución mensual de trabajos e ingresos desde BD"""
    conn = get_conn()
    try:
        query = f"""
        SELECT
          STRFTIME('%m', f.fechaemision) AS mes,
          COUNT(DISTINCT f.numerofactura) AS cantidad_facturas,
          ROUND(COALESCE(SUM(f.subtotal + f.iva), 0), 2) AS total_mes
        FROM facturas f
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
        GROUP BY mes
        ORDER BY mes
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            df['mes_nombre'] = df['mes'].apply(lambda x: mes_nombre(x))
        return df
    except Exception as e:
        conn.close()
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_totales_periodo(ano, mes=None):
    """Totales generales del período desde BD REAL"""
    conn = get_conn()
    try:
        query = f"""
        SELECT
          COUNT(DISTINCT numerofactura) AS total_facturas,
          ROUND(COALESCE(SUM(subtotal), 0), 2) AS total_subtotal,
          ROUND(COALESCE(SUM(iva), 0), 2) AS total_iva,
          ROUND(COALESCE(SUM(subtotal + iva), 0), 2) AS total_ingresos,
          ROUND(COALESCE(AVG(subtotal + iva), 0), 2) AS promedio_factura
        FROM facturas
        WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano}
          AND ('{mes}' IS NULL OR STRFTIME('%m', fechaemision) = '{mes}')
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df if not df.empty else pd.DataFrame({
            'total_facturas': [0],
            'total_subtotal': [0.0],
            'total_iva': [0.0],
            'total_ingresos': [0.0],
            'promedio_factura': [0.0]
        })
    except Exception as e:
        conn.close()
        return pd.DataFrame({
            'total_facturas': [0],
            'total_subtotal': [0.0],
            'total_iva': [0.0],
            'total_ingresos': [0.0],
            'promedio_factura': [0.0]
        })

@st.cache_data(ttl=600)
def get_categorias_por_periodo(ano, mes=None):
    """Categorías desde la BD REAL"""
    conn = get_conn()
    try:
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
              ELSE TRIM(lf.clasificacion_categoria)
            END AS categoria,
            COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
          FROM lineas_factura lf
          INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
          WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
            {filtro_mes}
          GROUP BY f.numerofactura, f.fechaemision, categoria, total_factura
        ),
        resumen_categorias AS (
          SELECT
            categoria,
            COUNT(DISTINCT numerofactura) AS cantidad_trabajos,
            SUM(total_factura) AS total_dinero,
            AVG(total_factura) AS promedio_trabajo
          FROM facturas_clasificadas
          GROUP BY categoria
        ),
        totales_periodo AS (
          SELECT
            SUM(total_dinero) AS total_mes,
            SUM(cantidad_trabajos) AS total_trabajos
          FROM resumen_categorias
        )
        SELECT
          rc.categoria,
          rc.cantidad_trabajos AS total_facturas,
          ROUND(rc.total_dinero, 2) AS total_ingresos,
          ROUND(rc.promedio_trabajo, 2) AS promedio_factura,
          ROUND((rc.total_dinero / NULLIF(tp.total_mes, 0)) * 100, 2) AS porcentaje
        FROM resumen_categorias rc
        CROSS JOIN totales_periodo tp
        ORDER BY total_ingresos DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_subcategorias_por_periodo(ano, mes=None, categoria=None):
    """Subcategorías desde la BD REAL"""
    conn = get_conn()
    try:
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
            TRIM(lf.clasificacion_categoria) AS categoria,
            TRIM(COALESCE(lf.clasificacion_subcategoria, 'General')) AS subcategoria,
            COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
          FROM lineas_factura lf
          INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
          WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
            AND lf.clasificacion_categoria IS NOT NULL
            {filtro_mes}
            {filtro_cat}
          GROUP BY f.numerofactura, f.fechaemision, categoria, subcategoria, total_factura
        ),
        resumen_subcategorias AS (
          SELECT
            categoria,
            subcategoria,
            COUNT(DISTINCT numerofactura) AS cantidad_trabajos,
            SUM(total_factura) AS total_dinero,
            AVG(total_factura) AS promedio_trabajo
          FROM facturas_clasificadas
          GROUP BY categoria, subcategoria
        ),
        totales_periodo AS (
          SELECT
            SUM(total_dinero) AS total_mes,
            SUM(cantidad_trabajos) AS total_trabajos
          FROM resumen_subcategorias
        )
        SELECT
          rs.categoria,
          rs.subcategoria,
          rs.cantidad_trabajos AS total_facturas,
          ROUND(rs.total_dinero, 2) AS total_ingresos,
          ROUND(rs.promedio_trabajo, 2) AS promedio_factura,
          ROUND((rs.total_dinero / NULLIF(tp.total_mes, 0)) * 100, 2) AS porcentaje
        FROM resumen_subcategorias rs
        CROSS JOIN totales_periodo tp
        ORDER BY total_ingresos DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_comparativa_mes_categoria(ano):
    """Comparativa por mes y categoría desde BD REAL"""
    conn = get_conn()
    try:
        query = f"""
        WITH facturas_clasificadas AS (
          SELECT
            STRFTIME('%m', f.fechaemision) AS mes,
            f.numerofactura,
            CASE 
              WHEN lf.clasificacion_categoria IS NULL 
                OR lf.clasificacion_categoria = 'Sin clasificacion'
              THEN 'Otros'
              ELSE TRIM(lf.clasificacion_categoria)
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
          ROUND((rmc.total_ingresos / NULLIF(tm.total_mes, 0)) * 100, 2) AS porcentaje_mes
        FROM resumen_mes_cat rmc
        INNER JOIN totales_mes tm ON rmc.mes = tm.mes
        ORDER BY rmc.mes, rmc.total_ingresos DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            df['mes_nombre'] = df['mes'].apply(lambda x: mes_nombre(x))
        return df
    except Exception as e:
        conn.close()
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_newton_diario(ano, mes=None):
    """Análisis diario de Newton y Newton Plus desde BD REAL"""
    conn = get_conn()
    try:
        filtro_mes = ""
        if mes:
            filtro_mes = f"AND STRFTIME('%m', f.fechaemision) = '{mes}'"

        query = f"""
        WITH trabajos AS (
          SELECT
            DATE(f.fechaemision) AS dia,
            f.numerofactura,
            MAX(CASE WHEN TRIM(lf.clasificacion_categoria) = 'Newton' THEN 1 ELSE 0 END) AS trabajo_newton,
            MAX(CASE WHEN TRIM(lf.clasificacion_categoria) = 'Newton Plus' THEN 1 ELSE 0 END) AS trabajo_newton_plus,
            COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
          FROM lineas_factura lf
          INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
          WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
            {filtro_mes}
            AND TRIM(lf.clasificacion_categoria) IN ('Newton', 'Newton Plus')
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
          ROUND(COALESCE(total_newton, 0), 2) AS total_newton,
          CASE WHEN cantidad_newton > 0 THEN ROUND(total_newton / cantidad_newton, 2) ELSE 0 END AS promedio_diario_newton,
          cantidad_newton_plus,
          ROUND(COALESCE(total_newton_plus, 0), 2) AS total_newton_plus,
          CASE WHEN cantidad_newton_plus > 0 THEN ROUND(total_newton_plus / cantidad_newton_plus, 2) ELSE 0 END AS promedio_diario_newton_plus,
          ROUND(SUM(COALESCE(total_newton, 0)) OVER () / NULLIF(SUM(cantidad_newton) OVER (), 0), 2) AS promedio_global_newton,
          ROUND(SUM(COALESCE(total_newton_plus, 0)) OVER () / NULLIF(SUM(cantidad_newton_plus) OVER (), 0), 2) AS promedio_global_newton_plus
        FROM resumen_diario
        ORDER BY dia DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        return pd.DataFrame()

# ============================================================================
# UI - MAIN
# ============================================================================

st.title("📊 Dashboard de Facturación Rodenstock")
st.markdown("---")

# SIDEBAR
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

# HEADER - RESUMEN GENERAL
st.header("📈 Resumen General")

totales = get_totales_periodo(ano_seleccionado, mes_param)

if not totales.empty and totales['total_facturas'].iloc[0] > 0:
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("📋 Trabajos", f"{int(totales['total_facturas'].iloc[0]):,}")
    with col2:
        st.metric("💵 Subtotal", format_currency(totales['total_subtotal'].iloc[0]))
    with col3:
        st.metric("📊 IVA", format_currency(totales['total_iva'].iloc[0]))
    with col4:
        st.metric("💰 Total", format_currency(totales['total_ingresos'].iloc[0]))
    with col5:
        st.metric("📈 Promedio", format_currency(totales['promedio_factura'].iloc[0]))
else:
    st.warning("⚠️ No hay datos para el período seleccionado")

st.markdown("---")

# TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Evolución Mensual",
    "🏆 Categorías",
    "🎯 Subcategorías",
    "📈 Análisis Pareto",
    "⚡ Newton vs Newton+",
    "🔍 Comparativa"
])

# TAB 1: EVOLUCIÓN MENSUAL
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
            name='Total Ingresos',
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
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True, key="tab1_chart")

        st.markdown("#### 📋 Detalles por Mes")
        df_display = df_mes[['mes_nombre', 'cantidad_facturas', 'total_mes']].copy()
        df_display['cantidad_facturas'] = df_display['cantidad_facturas'].apply(lambda x: f"{int(x):,}")
        df_display['total_mes'] = df_display['total_mes'].apply(format_currency)
        df_display.columns = ['Mes', 'Trabajos', 'Total']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos disponibles")

# TAB 2: CATEGORÍAS
with tab2:
    st.subheader(f"🏆 Análisis por Categoría - {ano_seleccionado}")

    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig_pie = px.pie(
                df_cat,
                values='total_ingresos',
                names='categoria',
                title='Distribución de Ingresos'
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="tab2_pie")

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
            st.plotly_chart(fig_bar, use_container_width=True, key="tab2_bar")

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
            'promedio_factura': 'Promedio',
            'porcentaje': '%'
        })
        st.dataframe(df_display[['Categoría', 'Trabajos', 'Total', 'Promedio', '%']], 
                     use_container_width=True, hide_index=True)
    else:
        st.warning("No hay datos")

# TAB 3: SUBCATEGORÍAS
with tab3:
    st.subheader(f"🎯 Análisis por Subcategoría - {ano_seleccionado}")

    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        categorias = sorted([c for c in df_cat['categoria'].unique() if c and c != 'Otros'])
        categorias.insert(0, 'Todas')
        cat_seleccionada = st.selectbox("Filtrar por Categoría", categorias, key="tab3_cat")

        if cat_seleccionada == 'Todas':
            df_subcat = get_subcategorias_por_periodo(ano_seleccionado, mes_param)
        else:
            df_subcat = get_subcategorias_por_periodo(ano_seleccionado, mes_param, cat_seleccionada)

        if not df_subcat.empty:
            df_sorted = df_subcat.sort_values('total_ingresos', ascending=True)
            fig = px.bar(
                df_sorted,
                y='subcategoria',
                x='total_ingresos',
                orientation='h',
                title='Total Ingresos por Subcategoría',
                color='total_ingresos',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True, key="tab3_bar")

            st.markdown("#### 📋 Detalle Subcategorías")
            df_display = df_subcat.copy()
            df_display['total_facturas'] = df_display['total_facturas'].apply(lambda x: f"{int(x):,}")
            df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
            df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
            df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.1f}%")
            df_display = df_display.rename(columns={
                'categoria': 'Cat.',
                'subcategoria': 'Subcategoría',
                'total_facturas': 'Trabajos',
                'total_ingresos': 'Total',
                'promedio_factura': 'Promedio',
                'porcentaje': '%'
            })
            st.dataframe(df_display[['Cat.', 'Subcategoría', 'Trabajos', 'Total', 'Promedio', '%']], 
                        use_container_width=True, hide_index=True)
        else:
            st.warning("No hay datos para esta categoría")
    else:
        st.warning("No hay datos")

# TAB 4: ANÁLISIS PARETO
with tab4:
    st.subheader(f"📈 Análisis de Pareto - {ano_seleccionado}")

    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Categorías", len(df_cat))
        with col2:
            st.metric("Trabajos", f"{int(df_cat['total_facturas'].sum()):,}")
        with col3:
            st.metric("Total", format_currency(df_cat['total_ingresos'].sum()))
        with col4:
            st.metric("Promedio", format_currency(df_cat['promedio_factura'].mean()))

        st.markdown("---")

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
            title='Análisis de Pareto',
            height=400
        )
        st.plotly_chart(fig_pareto, use_container_width=True, key="tab4_pareto")
    else:
        st.warning("No hay datos")

# TAB 5: NEWTON vs NEWTON+
with tab5:
    st.subheader(f"⚡ Análisis Newton vs Newton Plus - {ano_seleccionado}")

    df_newton = get_newton_diario(ano_seleccionado, mes_param)

    if not df_newton.empty and len(df_newton) > 0:
        col1, col2, col3, col4 = st.columns(4)

        total_newton = df_newton['cantidad_newton'].sum()
        total_newton_plus = df_newton['cantidad_newton_plus'].sum()
        prom_newton = df_newton['promedio_global_newton'].iloc[0] if df_newton['promedio_global_newton'].iloc[0] > 0 else 0
        prom_newton_plus = df_newton['promedio_global_newton_plus'].iloc[0] if df_newton['promedio_global_newton_plus'].iloc[0] > 0 else 0

        with col1:
            st.metric("📦 Total Newton", f"{int(total_newton):,}")
        with col2:
            st.metric("🚀 Total Newton+", f"{int(total_newton_plus):,}")
        with col3:
            st.metric("💰 Prom. Newton", format_currency(prom_newton))
        with col4:
            st.metric("💎 Prom. Newton+", format_currency(prom_newton_plus))

        st.markdown("---")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_newton['dia'],
            y=df_newton['cantidad_newton'],
            name='Newton',
            marker_color='rgba(33, 128, 141, 0.7)'
        ))
        fig.add_trace(go.Bar(
            x=df_newton['dia'],
            y=df_newton['cantidad_newton_plus'],
            name='Newton Plus',
            marker_color='rgba(255, 107, 107, 0.7)'
        ))

        fig.update_layout(
            barmode='group',
            title='Cantidad Diaria',
            xaxis_title='Día',
            yaxis_title='Trabajos',
            height=400,
            xaxis_tickangle=-45
        )

        st.plotly_chart(fig, use_container_width=True, key="tab5_barras")
    else:
        st.info("No hay datos de Newton para este período")

# TAB 6: COMPARATIVA
with tab6:
    st.subheader(f"🔍 Comparativa por Mes - {ano_seleccionado}")

    df_comp = get_comparativa_mes_categoria(ano_seleccionado)

    if not df_comp.empty:
        st.markdown("### 📊 Ingresos por Mes y Categoría")

        df_display = df_comp.copy()
        df_display['total_facturas'] = df_display['total_facturas'].apply(lambda x: f"{int(x):,}")
        df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
        df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
        df_display['porcentaje_mes'] = df_display['porcentaje_mes'].apply(lambda x: f"{x:.1f}%")
        df_display = df_display[['mes_nombre', 'categoria', 'total_facturas', 'total_ingresos', 'promedio_factura', 'porcentaje_mes']]
        df_display.columns = ['Mes', 'Categoría', 'Trabajos', 'Total', 'Promedio', '%']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay datos")

# FOOTER
st.markdown("---")
st.caption("📊 Dashboard Rodenstock | © 2025 | ✓ 100% Datos desde SQLite | REAL")
