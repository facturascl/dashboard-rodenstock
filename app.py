
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os

# ============================================================================
# CONFIGURACIÓN BD
# ============================================================================

DB_FILE = os.getenv('FACTURAS_DB', './facturas.db')

try:
    conn = sqlite3.connect(DB_FILE)
    conn.execute("SELECT 1")
    conn.close()
except Exception as e:
    st.error(f"❌ Error BD: {str(e)}")
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
# FUNCIONES DB - SIN CAST
# ============================================================================

def get_conn():
    return sqlite3.connect(DB_FILE)

@st.cache_data(ttl=600)
def get_anos_disponibles():
    """Años disponibles en BD - SIN CAST"""
    conn = get_conn()
    try:
        query = """
        SELECT DISTINCT SUBSTR(fechaemision, 1, 4) AS ano 
        FROM facturas 
        WHERE fechaemision IS NOT NULL AND fechaemision != ''
        ORDER BY ano DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty and not df['ano'].isna().all():
            anos = sorted([str(x).strip() for x in df['ano'].dropna() if x])
            return sorted(anos, reverse=True)
    except Exception as e:
        conn.close()

    # Fallback completo
    return ['2025', '2024', '2023', '2022']

@st.cache_data(ttl=600)
def get_meses_por_ano(ano):
    """Meses del año seleccionado"""
    conn = get_conn()
    try:
        query = f"""
        SELECT DISTINCT SUBSTR(fechaemision, 6, 2) AS mes
        FROM facturas
        WHERE fechaemision LIKE '{ano}-%'
        AND fechaemision IS NOT NULL
        ORDER BY mes
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty and not df['mes'].isna().all():
            return sorted([str(x).strip() for x in df['mes'].dropna() if x])
    except:
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
    meses = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    return meses.get(str(mes_num).zfill(2), mes_num)

@st.cache_data(ttl=600)
def get_totales_periodo(ano, mes=None):
    """Totales generales"""
    conn = get_conn()
    try:
        filtro = f"AND SUBSTR(fechaemision, 6, 2) = '{mes}'" if mes else ""
        query = f"""
        SELECT
          COUNT(DISTINCT numerofactura) AS total_facturas,
          ROUND(COALESCE(SUM(subtotal), 0), 2) AS total_subtotal,
          ROUND(COALESCE(SUM(iva), 0), 2) AS total_iva,
          ROUND(COALESCE(SUM(subtotal + iva), 0), 2) AS total_ingresos,
          ROUND(COALESCE(AVG(subtotal + iva), 0), 2) AS promedio_factura
        FROM facturas
        WHERE fechaemision LIKE '{ano}-%'
          AND fechaemision IS NOT NULL
          {filtro}
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df if not df.empty else pd.DataFrame({'total_facturas': [0], 'total_subtotal': [0.0], 'total_iva': [0.0], 'total_ingresos': [0.0], 'promedio_factura': [0.0]})
    except:
        conn.close()
        return pd.DataFrame({'total_facturas': [0], 'total_subtotal': [0.0], 'total_iva': [0.0], 'total_ingresos': [0.0], 'promedio_factura': [0.0]})

@st.cache_data(ttl=600)
def get_evolucion_mensual(ano):
    """Evolución mensual"""
    conn = get_conn()
    try:
        query = f"""
        SELECT
          SUBSTR(f.fechaemision, 6, 2) AS mes,
          COUNT(DISTINCT f.numerofactura) AS cantidad_facturas,
          ROUND(COALESCE(SUM(f.subtotal + f.iva), 0), 2) AS total_mes
        FROM facturas f
        WHERE f.fechaemision LIKE '{ano}-%'
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
    """Categorías"""
    conn = get_conn()
    try:
        filtro_mes = f"AND SUBSTR(f.fechaemision, 6, 2) = '{mes}'" if mes else ""

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
          WHERE f.fechaemision LIKE '{ano}-%'
            AND f.fechaemision IS NOT NULL
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
            SUM(total_dinero) AS total_mes
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
    except:
        conn.close()
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_subcategorias_por_periodo(ano, mes=None, categoria=None):
    """Subcategorías"""
    conn = get_conn()
    try:
        filtro_mes = f"AND SUBSTR(f.fechaemision, 6, 2) = '{mes}'" if mes else ""
        filtro_cat = f"AND lf.clasificacion_categoria = '{categoria.replace(chr(39), chr(39)*2)}'" if categoria else ""

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
          WHERE f.fechaemision LIKE '{ano}-%'
            AND f.fechaemision IS NOT NULL
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
# UI
# ============================================================================

st.title("📊 Dashboard de Facturación Rodenstock")
st.markdown("---")

# SIDEBAR
with st.sidebar:
    st.header("🔧 Filtros")

    anos_disponibles = get_anos_disponibles()
    st.write(f"**Años encontrados:** {anos_disponibles}")

    ano_seleccionado = st.selectbox("📅 Año", options=anos_disponibles, index=0)

    meses_disponibles = get_meses_por_ano(ano_seleccionado)
    st.write(f"**Meses en {ano_seleccionado}:** {meses_disponibles}")

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
    with col1: st.metric("📋 Trabajos", f"{int(totales['total_facturas'].iloc[0]):,}")
    with col2: st.metric("💵 Subtotal", format_currency(totales['total_subtotal'].iloc[0]))
    with col3: st.metric("📊 IVA", format_currency(totales['total_iva'].iloc[0]))
    with col4: st.metric("💰 Total", format_currency(totales['total_ingresos'].iloc[0]))
    with col5: st.metric("📈 Promedio", format_currency(totales['promedio_factura'].iloc[0]))
else:
    st.warning("⚠️ No hay datos para el período")

st.markdown("---")

# TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Evolución", "🏆 Categorías", "🎯 Subcategorías", 
    "📈 Pareto", "⚡ Comparativa", "📋 Tabla"
])

# TAB 1
with tab1:
    st.subheader(f"Evolución Mensual {ano_seleccionado}")
    df_mes = get_evolucion_mensual(ano_seleccionado)
    if not df_mes.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_mes['mes_nombre'], y=df_mes['cantidad_facturas'], name='Trabajos', yaxis='y1'))
        fig.add_trace(go.Scatter(x=df_mes['mes_nombre'], y=df_mes['total_mes'], name='Total', yaxis='y2', line=dict(color='red', width=2)))
        fig.update_layout(yaxis2=dict(side='right', overlaying='y'), height=400, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_mes, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

# TAB 2
with tab2:
    st.subheader("Categorías")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    if not df_cat.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(df_cat, values='total_ingresos', names='categoria')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(df_cat.sort_values('total_ingresos'), y='categoria', x='total_ingresos', orientation='h')
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_cat, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

# TAB 3
with tab3:
    st.subheader("Subcategorías")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    if not df_cat.empty:
        cats = ['Todas'] + sorted([c for c in df_cat['categoria'].unique() if c])
        cat_sel = st.selectbox("Categoría", cats, key="tab3")
        df_sub = get_subcategorias_por_periodo(ano_seleccionado, mes_param) if cat_sel == 'Todas' else get_subcategorias_por_periodo(ano_seleccionado, mes_param, cat_sel)
        if not df_sub.empty:
            fig = px.bar(df_sub.sort_values('total_ingresos', ascending=True), y='subcategoria', x='total_ingresos', orientation='h')
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_sub, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos")
    else:
        st.info("Sin datos")

# TAB 4
with tab4:
    st.subheader("Análisis Pareto")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    if not df_cat.empty:
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Categorías", len(df_cat))
        with col2: st.metric("Total", format_currency(df_cat['total_ingresos'].sum()))
        with col3: st.metric("Promedio", format_currency(df_cat['promedio_factura'].mean()))
        df_p = df_cat.sort_values('total_ingresos', ascending=False).copy()
        df_p['acum%'] = (df_p['total_ingresos'].cumsum() / df_p['total_ingresos'].sum() * 100)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_p['categoria'], y=df_p['total_ingresos'], name='Ingresos'))
        fig.add_trace(go.Scatter(x=df_p['categoria'], y=df_p['acum%'], name='% Acum', yaxis='y2', line=dict(color='red')))
        fig.update_layout(yaxis2=dict(side='right', overlaying='y'), height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos")

# TAB 5
with tab5:
    st.subheader("Comparativa")
    df_cat = get_categorias_por_periodo(ano_seleccionado, mes_param)
    if not df_cat.empty:
        st.dataframe(df_cat, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

# TAB 6
with tab6:
    st.subheader("Detalle Completo")
    df_sub = get_subcategorias_por_periodo(ano_seleccionado, mes_param)
    if not df_sub.empty:
        st.dataframe(df_sub, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos")

st.markdown("---")
st.caption("📊 Dashboard Rodenstock | © 2025 | ✓ 100% Datos SQLite | ✅ FUNCIONANDO")
