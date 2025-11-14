
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os
from datetime import datetime
from pathlib import Path

# ============================================================================
# BÚSQUEDA INTELIGENTE DE LA BD
# ============================================================================

DB_FILE = None

if os.environ.get('FACTURAS_DB'):
    DB_FILE = os.environ.get('FACTURAS_DB')

if not DB_FILE or not Path(DB_FILE).exists():
    streamlit_path = Path(__file__).parent / "facturas.db"
    if streamlit_path.exists():
        DB_FILE = str(streamlit_path)

if not DB_FILE or not Path(DB_FILE).exists():
    possible_paths = [
        Path.cwd() / "facturas.db",
        Path.cwd().parent / "facturas.db",
        Path("/root/facturas.db"),
        Path(os.path.expanduser("~/facturas.db")),
    ]
    for path in possible_paths:
        if path.exists():
            DB_FILE = str(path)
            break

if not DB_FILE or not Path(DB_FILE).exists():
    st.error("❌ No se encontró facturas.db")
    st.stop()

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
    return sqlite3.connect(DB_FILE)

@st.cache_data(ttl=600)
def inspect_data():
    """Inspecciona la estructura de datos disponibles"""
    conn = get_conn()
    try:
        cursor = conn.cursor()

        # Checar qué años hay en fechaemision
        cursor.execute("""
        SELECT DISTINCT STRFTIME('%Y', fechaemision) AS ano 
        FROM facturas 
        WHERE fechaemision IS NOT NULL 
        LIMIT 10
        """)
        anos = [row[0] for row in cursor.fetchall() if row[0]]

        # Contar NULL en fechaemision
        cursor.execute("SELECT COUNT(*) FROM facturas WHERE fechaemision IS NULL")
        null_count = cursor.fetchone()[0]

        # Contar totales
        cursor.execute("SELECT COUNT(*) FROM facturas")
        total_facturas = cursor.fetchone()[0]

        conn.close()

        return {
            'anos': sorted(set(anos), reverse=True) if anos else [],
            'null_fechas': null_count,
            'total_facturas': total_facturas
        }
    except Exception as e:
        conn.close()
        return {'anos': [], 'null_fechas': 0, 'total_facturas': 0}

@st.cache_data(ttl=600)
def get_anos_disponibles():
    """Años únicos disponibles en BD"""
    info = inspect_data()
    if info['anos']:
        return info['anos']
    # Si no hay años en fechaemision, usar años por defecto
    return [2024, 2025]

@st.cache_data(ttl=600)
def get_meses_por_ano(ano):
    """Meses únicos del año seleccionado"""
    conn = get_conn()
    try:
        query = f"""
        SELECT DISTINCT STRFTIME('%m', fechaemision) AS mes
        FROM facturas
        WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano}
        AND fechaemision IS NOT NULL
        ORDER BY mes
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return sorted(df['mes'].dropna().tolist()) if not df.empty else []
    except:
        conn.close()
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']

def format_currency(value):
    if value is None or pd.isna(value):
        return "$0"
    try:
        return f"${int(round(float(value))):,}"
    except:
        return "$0"

def mes_nombre(mes_num):
    meses = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    return meses.get(str(mes_num).zfill(2), mes_num)

@st.cache_data(ttl=600)
def get_totales_periodo(ano, mes=None):
    """Totales generales del período"""
    conn = get_conn()
    try:
        filtro = f"AND STRFTIME('%m', fechaemision) = '{mes}'" if mes else ""
        query = f"""
        SELECT
          COUNT(DISTINCT numerofactura) AS total_facturas,
          ROUND(COALESCE(SUM(subtotal), 0), 2) AS total_subtotal,
          ROUND(COALESCE(SUM(iva), 0), 2) AS total_iva,
          ROUND(COALESCE(SUM(subtotal + iva), 0), 2) AS total_ingresos,
          ROUND(COALESCE(AVG(subtotal + iva), 0), 2) AS promedio_factura
        FROM facturas
        WHERE fechaemision IS NOT NULL
          {filtro}
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df if not df.empty else pd.DataFrame({
            'total_facturas': [0], 'total_subtotal': [0.0],
            'total_iva': [0.0], 'total_ingresos': [0.0],
            'promedio_factura': [0.0]
        })
    except Exception as e:
        conn.close()
        return pd.DataFrame({
            'total_facturas': [0], 'total_subtotal': [0.0],
            'total_iva': [0.0], 'total_ingresos': [0.0],
            'promedio_factura': [0.0]
        })

@st.cache_data(ttl=600)
def get_evolucion_mensual(ano):
    """Evolución mensual de trabajos e ingresos"""
    conn = get_conn()
    try:
        query = f"""
        SELECT
          STRFTIME('%m', f.fechaemision) AS mes,
          COUNT(DISTINCT f.numerofactura) AS cantidad_facturas,
          ROUND(COALESCE(SUM(f.subtotal + f.iva), 0), 2) AS total_mes
        FROM facturas f
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}
        AND f.fechaemision IS NOT NULL
        GROUP BY mes
        ORDER BY mes
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            df['mes_nombre'] = df['mes'].apply(lambda x: mes_nombre(x))
        return df
    except:
        conn.close()
        return pd.DataFrame()

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
          WHERE f.fechaemision IS NOT NULL
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
          WHERE f.fechaemision IS NOT NULL
            AND lf.clasificacion_categoria IS NOT NULL
            {filtro_mes}
            {filtro_cat}
          GROUP BY f.numerofactura, f.fechaemision, categoria, subcategoria, total_factura
        )
        SELECT
          categoria,
          subcategoria,
          COUNT(DISTINCT numerofactura) AS total_facturas,
          ROUND(SUM(total_factura), 2) AS total_ingresos,
          ROUND(AVG(total_factura), 2) AS promedio_factura
        FROM facturas_clasificadas
        GROUP BY categoria, subcategoria
        ORDER BY total_ingresos DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except:
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

    if not anos_disponibles:
        st.error("⚠️ No hay años disponibles")
        st.stop()

    ano_seleccionado = st.selectbox("📅 Año", options=anos_disponibles, index=0)

    meses_disponibles = get_meses_por_ano(ano_seleccionado)
    mes_options = ["Todos"] + meses_disponibles
    mes_seleccionado = st.selectbox("📆 Mes", options=mes_options, index=0)

    mes_param = None if mes_seleccionado == "Todos" else mes_seleccionado

    st.markdown("---")
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# HEADER
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
    "⚡ Comparativa",
    "📋 Tabla Completa"
])

# TAB 1: EVOLUCIÓN MENSUAL
with tab1:
    st.subheader(f"📊 Evolución Mensual {ano_seleccionado}")
    df_mes = get_evolucion_mensual(ano_seleccionado)

    if not df_mes.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_mes['mes_nombre'], y=df_mes['cantidad_facturas'], 
                            name='Trabajos', marker_color='rgba(33, 128, 141, 0.7)', yaxis='y1'))
        fig.add_trace(go.Scatter(x=df_mes['mes_nombre'], y=df_mes['total_mes'], 
                                name='Total', mode='lines+markers', line=dict(color='#FF6B6B', width=3), yaxis='y2'))
        fig.update_layout(
            title='Facturas e Ingresos por Mes',
            xaxis_title='Mes',
            yaxis=dict(title='Cantidad'),
            yaxis2=dict(title='Total ($)', side='right', overlaying='y'),
            height=400,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_mes[['mes_nombre', 'cantidad_facturas', 'total_mes']], use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

# TAB 2: CATEGORÍAS
with tab2:
    st.subheader(f"🏆 Categorías")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig_pie = px.pie(df_cat, values='total_ingresos', names='categoria', title='Distribución')
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            fig_bar = px.bar(df_cat.sort_values('total_ingresos'), y='categoria', x='total_ingresos',
                           orientation='h', title='Total por Categoría')
            st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(df_cat, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

# TAB 3: SUBCATEGORÍAS
with tab3:
    st.subheader(f"🎯 Subcategorías")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        cats = ['Todas'] + sorted([c for c in df_cat['categoria'].unique() if c != 'Otros'])
        cat_sel = st.selectbox("Categoría", cats, key="tab3_cat")

        if cat_sel == 'Todas':
            df_sub = get_subcategorias_por_periodo(ano_seleccionado, mes_param)
        else:
            df_sub = get_subcategorias_por_periodo(ano_seleccionado, mes_param, cat_sel)

        if not df_sub.empty:
            fig = px.bar(df_sub.sort_values('total_ingresos', ascending=True), y='subcategoria', 
                        x='total_ingresos', orientation='h', title='Ingresos por Subcategoría')
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_sub, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos")
    else:
        st.info("Sin datos")

# TAB 4: PARETO
with tab4:
    st.subheader(f"📈 Análisis Pareto")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Categorías", len(df_cat))
        with col2: st.metric("Trabajos", f"{int(df_cat['total_facturas'].sum()):,}")
        with col3: st.metric("Total", format_currency(df_cat['total_ingresos'].sum()))
        with col4: st.metric("Promedio", format_currency(df_cat['promedio_factura'].mean()))

        df_pareto = df_cat.sort_values('total_ingresos', ascending=False).copy()
        df_pareto['acumulado'] = df_pareto['total_ingresos'].cumsum()
        df_pareto['pct_acum'] = (df_pareto['acumulado'] / df_pareto['total_ingresos'].sum() * 100)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_pareto['categoria'], y=df_pareto['total_ingresos'], name='Ingresos'))
        fig.add_trace(go.Scatter(x=df_pareto['categoria'], y=df_pareto['pct_acum'], 
                                name='% Acum', yaxis='y2', line=dict(color='red', width=2)))
        fig.update_layout(yaxis2=dict(title='% Acum', side='right', overlaying='y'), height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos")

# TAB 5: COMPARATIVA
with tab5:
    st.subheader(f"⚡ Resumen Comparativo")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)

    if not df_cat.empty:
        # Matriz de comparativa
        df_display = df_cat.copy()
        df_display['total_facturas'] = df_display['total_facturas'].astype(int)
        df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
        df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
        df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

# TAB 6: TABLA COMPLETA
with tab6:
    st.subheader(f"📋 Todas las Categorías y Subcategorías")

    df_sub = get_subcategorias_por_periodo(ano_seleccionado, mes_param)
    if not df_sub.empty:
        df_display = df_sub.copy()
        df_display['total_facturas'] = df_display['total_facturas'].astype(int)
        df_display['total_ingresos'] = df_display['total_ingresos'].apply(format_currency)
        df_display['promedio_factura'] = df_display['promedio_factura'].apply(format_currency)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

st.markdown("---")
st.caption("📊 Dashboard Rodenstock | © 2025 | ✓ 100% Datos SQLite | ✅ 6 VISTAS")
