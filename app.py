
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime, timedelta

# Configuración de página
st.set_page_config(
    page_title="Dashboard Facturación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Conectar a BD
DB_PATH = "facturas.db"

@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn

conn = get_db_connection()

# ============================================================
# SIDEBAR - Filtros
# ============================================================
st.sidebar.title("🔧 Filtros")

# Obtener años disponibles
anos_query = """
    SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano
    FROM facturas
    WHERE fechaemision IS NOT NULL
    ORDER BY ano DESC
"""
anos_df = pd.read_sql_query(anos_query, conn)
anos_disponibles = anos_df['ano'].tolist() if not anos_df.empty else [datetime.now().year]

ano_seleccionado = st.sidebar.selectbox(
    "Año",
    options=anos_disponibles,
    index=0
)

# Obtener meses del año seleccionado
meses_query = f"""
    SELECT DISTINCT CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano_seleccionado}
    AND fechaemision IS NOT NULL
    ORDER BY mes DESC
"""
meses_df = pd.read_sql_query(meses_query, conn)
meses_disponibles = meses_df['mes'].tolist() if not meses_df.empty else [datetime.now().month]

mes_param = st.sidebar.selectbox(
    "Mes",
    options=meses_disponibles,
    index=0,
    format_func=lambda x: f"{x:02d}"
)

# ============================================================
# FUNCIONES DE CONSULTA - CON FIXES
# ============================================================

@st.cache_data(ttl=600)
def get_totales_periodo(ano_sel, mes_param):
    """TAB 1: Totales mensuales desde tabla facturas (sin JOIN duplicado)"""
    query = f"""
    SELECT 
        CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano,
        CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
        COUNT(DISTINCT numerofactura) as cantidad_facturas,
        CAST(SUM(COALESCE(subtotal, 0) + COALESCE(iva, 0)) AS INTEGER) as total_general
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', fechaemision) AS INTEGER) = {mes_param}
    AND fechaemision IS NOT NULL
    GROUP BY ano, mes
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_analisis_categorias(ano_sel, mes_param):
    """TAB 2: Análisis por categoría/subcategoría - CORREGIDO sin doble conteo"""
    query = f"""
    SELECT 
        COALESCE(lf.clasificacion_categoria, 'Sin categoría') as categoria,
        COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
        COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
        CAST(SUM(DISTINCT CASE 
            WHEN lf.linea_numero = 1 THEN COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) 
            ELSE 0 
        END) AS INTEGER) as total_subcategoria
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
    AND f.fechaemision IS NOT NULL
    GROUP BY categoria, subcategoria
    ORDER BY total_subcategoria DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_newton_analysis(ano_sel, mes_param):
    """TAB 3: Newton vs Newton Plus - CORREGIDO con CTE"""
    query = f"""
    WITH trabajos AS (
        SELECT
            f.fechaemision AS dia,
            f.numerofactura,
            MAX(CASE WHEN lf.clasificacion_categoria = 'Newton' THEN 1 ELSE 0 END) AS trabajo_newton,
            MAX(CASE WHEN lf.clasificacion_categoria = 'Newton Plus' THEN 1 ELSE 0 END) AS trabajo_newton_plus,
            COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
        FROM lineas_factura lf
        JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
        AND CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
        AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
        AND f.fechaemision IS NOT NULL
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
        CAST(total_newton AS INTEGER) as total_newton,
        CASE WHEN cantidad_newton > 0 THEN CAST(total_newton / cantidad_newton AS INTEGER) ELSE NULL END AS promedio_diario_newton,
        cantidad_newton_plus,
        CAST(total_newton_plus AS INTEGER) as total_newton_plus,
        CASE WHEN cantidad_newton_plus > 0 THEN CAST(total_newton_plus / cantidad_newton_plus AS INTEGER) ELSE NULL END AS promedio_diario_newton_plus,
        CAST(SUM(total_newton) OVER () / NULLIF(SUM(cantidad_newton) OVER (), 0) AS INTEGER) AS promedio_global_newton,
        CAST(SUM(total_newton_plus) OVER () / NULLIF(SUM(cantidad_newton_plus) OVER (), 0) AS INTEGER) AS promedio_global_newton_plus
    FROM resumen_diario
    ORDER BY dia DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_top_subcategorias(ano_sel, mes_param):
    """TAB 4: Top 10 subcategorías - CORREGIDO sin doble conteo"""
    query = f"""
    SELECT 
        COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
        COUNT(DISTINCT lf.numerofactura) as cantidad,
        CAST(SUM(DISTINCT CASE 
            WHEN lf.linea_numero = 1 THEN COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) 
            ELSE 0 
        END) AS INTEGER) as total
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
    AND f.fechaemision IS NOT NULL
    GROUP BY subcategoria
    ORDER BY total DESC
    LIMIT 10
    """
    return pd.read_sql_query(query, conn)

# ============================================================
# TAB 1: RESUMEN GENERAL
# ============================================================
st.header("📊 Resumen General")

totales = get_totales_periodo(ano_seleccionado, mes_param)

if not totales.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    cantidad = totales['cantidad_facturas'].values[0]
    total_dinero = totales['total_general'].values[0]
    promedio = total_dinero / cantidad if cantidad > 0 else 0
    
    with col1:
        st.metric("Total Facturas", f"{cantidad:,}")
    with col2:
        st.metric("Total Ingresos", f"${total_dinero:,.0f}")
    with col3:
        st.metric("Promedio/Factura", f"${promedio:,.0f}")
    with col4:
        st.metric("Período", f"{ano_seleccionado}-{mes_param:02d}")
    with col5:
        st.metric("Estado", "✅ Activo")
else:
    st.warning("⚠️ No hay datos disponibles para este período")

# ============================================================
# TAB 2: ANÁLISIS POR CATEGORÍA
# ============================================================
st.divider()
st.subheader("🏷️ Análisis por Categoría")

df_categorias = get_analisis_categorias(ano_seleccionado, mes_param)

if not df_categorias.empty:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Tabla principal
        st.dataframe(
            df_categorias,
            use_container_width=True,
            hide_index=True
        )
    
    with col2:
        # Métrica de categorías
        st.metric("Total Categorías", len(df_categorias))
        st.metric("Monto Total", f"${df_categorias['total_subcategoria'].sum():,}")
else:
    st.info("📭 Sin datos de categorías para este período")

# ============================================================
# TAB 3: NEWTON vs NEWTON PLUS
# ============================================================
st.divider()
st.subheader("🔍 Análisis Newton vs Newton Plus")

df_newton = get_newton_analysis(ano_seleccionado, mes_param)

if not df_newton.empty:
    # Totales globales
    total_newton = df_newton['total_newton'].sum()
    total_newton_plus = df_newton['total_newton_plus'].sum()
    cantidad_newton = df_newton['cantidad_newton'].sum()
    cantidad_newton_plus = df_newton['cantidad_newton_plus'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Newton - Cantidad", f"{cantidad_newton:.0f}")
    with col2:
        st.metric("Newton - Total", f"${total_newton:,.0f}")
    with col3:
        st.metric("Newton Plus - Cantidad", f"{cantidad_newton_plus:.0f}")
    with col4:
        st.metric("Newton Plus - Total", f"${total_newton_plus:,.0f}")
    
    # Gráfico de línea por día
    if len(df_newton) > 0:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_newton['dia'],
            y=df_newton['total_newton'],
            mode='lines+markers',
            name='Newton Total',
            line=dict(color='#1f77b4')
        ))
        
        fig.add_trace(go.Scatter(
            x=df_newton['dia'],
            y=df_newton['total_newton_plus'],
            mode='lines+markers',
            name='Newton Plus Total',
            line=dict(color='#ff7f0e')
        ))
        
        fig.update_layout(
            title="Evolución Diaria - Newton vs Newton Plus",
            xaxis_title="Fecha",
            yaxis_title="Total ($)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabla detallada
    st.dataframe(
        df_newton,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("📭 Sin datos de Newton para este período")

# ============================================================
# TAB 4: TOP SUBCATEGORÍAS
# ============================================================
st.divider()
st.subheader("🥇 Top 10 Subcategorías")

df_top = get_top_subcategorias(ano_seleccionado, mes_param)

if not df_top.empty:
    # Gráfico de barras
    fig = px.bar(
        df_top,
        x='total',
        y='subcategoria',
        orientation='h',
        title='Top 10 Subcategorías por Total',
        labels={'total': 'Total ($)', 'subcategoria': 'Subcategoría'},
        color='total',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabla
    st.dataframe(
        df_top,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("📭 Sin datos de subcategorías para este período")

# ============================================================
# PIE DE PÁGINA
# ============================================================
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("✅ Base de datos: SQLite")
with col2:
    st.caption(f"📅 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
with col3:
    st.caption("🔧 Rodenstock Dashboard v2.0 - FIXED")
