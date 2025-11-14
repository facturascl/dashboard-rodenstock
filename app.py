
```python
#!/usr/bin/env python3

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

DB_FILE = "facturas.db"

# ============================================================================
# STREAMLIT CONFIG
# ============================================================================

st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_conn():
    """Retorna conexión a la BD"""
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
    """Categorías desde la BD REAL"""
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
    """Subcategorías desde la BD REAL"""
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
    """Comparativa por mes y categoría desde BD REAL"""
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
    """Totales generales del período desde BD REAL"""
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
    """Análisis diario de Newton y Newton Plus desde BD REAL"""
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
        st.metric("📋 Trabajos (Facturas)", f"{int(totales['total_facturas'].iloc):,}")
    with col2:
        st.metric("💵 Subtotal", format_currency(totales['total_subtotal'].iloc))
    with col3:
        st.metric("📊 IVA", format_currency(totales['total_iva'].iloc))
    with col4:
        st.metric("💰 Total", format_currency(totales['total_ingresos'].iloc))
    with col5:
        st.metric("📈 Promedio", format_currency(totales['promedio_factura'].iloc))

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Evolución Mensual",
    "🏆 Categorías",
    "🎯 Subcategorías",
    "📈 Análisis",
    "⚡ Newton vs Newton+",
    "🔍 Comparativa"
])

# [Resto del código es IDÉNTICO al documento anterior - tabs completos]

st.markdown("---")
st.caption("📊 Dashboard Rodenstock | © 2025 | ✓ Datos 100% desde BD SQLite | Valores REALES")
```


