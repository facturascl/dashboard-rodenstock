import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime
from streamlit_echarts import st_echarts

st.set_page_config(page_title="Dashboard Rodenstock", page_icon="📊", layout="wide")

import os

DB_PATH = "data/facturas.db"

# Verificar si existe la base de datos
if not os.path.exists(DB_PATH):
    st.error(f"❌ Base de datos no encontrada en: {DB_PATH}")
    st.info("📁 Archivos en directorio actual: " + ", ".join(os.listdir(".")))
    st.stop()
else:
    file_size = os.path.getsize(DB_PATH)
    st.sidebar.success(f"✅ BD encontrada ({file_size:,} bytes)")

@st.cache_resource
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM facturas")
        total_facturas = cursor.fetchone()[0]
        
        if total_facturas == 0:
            st.error("⚠️ La base de datos está vacía")
        else:
            st.sidebar.info(f"📊 Total facturas en BD: {total_facturas:,}")
            
        return conn
    except Exception as e:
        st.error(f"❌ Error BD: {e}")
        return None

# ============================================================
# BOTÓN PARA LIMPIAR CACHÉ Y FORZAR ACTUALIZACIÓN
# ============================================================
col_refresh, col_space = st.columns([1, 10])
with col_refresh:
    if st.button("🔄 Actualizar Datos", key="btn_refresh", help="Fuerza recarga de la BD"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

conn = get_db_connection()
if conn is None:
    st.stop()

# ============================================================
# SIDEBAR - FILTROS PRINCIPALES
# ============================================================
st.sidebar.title("🔧 Filtros")

try:
    anos_query = """
        SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano
        FROM facturas WHERE fechaemision IS NOT NULL
        ORDER BY ano DESC
    """
    anos_df = pd.read_sql_query(anos_query, conn)
    anos_disponibles = sorted(anos_df['ano'].tolist(), reverse=True) if not anos_df.empty else [2025]
    
    st.sidebar.write("📅 Años con datos:", anos_disponibles)
    
    count_query = """
        SELECT 
            CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano,
            COUNT(*) as total
        FROM facturas 
        WHERE fechaemision IS NOT NULL
        GROUP BY ano
        ORDER BY ano DESC
    """
    count_df = pd.read_sql_query(count_query, conn)
    st.sidebar.write("📊 Facturas por año:")
    st.sidebar.dataframe(count_df, hide_index=True)
    
    ano_actual = st.sidebar.selectbox("📅 Año Actual", anos_disponibles, index=0, key="ano_actual")
    
except Exception as e:
    st.error(f"Error al cargar años: {e}")
    st.stop()

# ============================================================
# FUNCIONES DE CONSULTA - FACTURAS
# ============================================================

@st.cache_data(ttl=300)
def get_comparativa_12_meses(ano):
    """Comparativa de 12 meses: cantidad de facturas + línea de dinero."""
    query = f"""
    SELECT 
        CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
        COUNT(DISTINCT numerofactura) as cantidad_facturas,
        CAST(SUM(subtotal + iva) AS INTEGER) as total_dinero
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {int(ano)}
    AND fechaemision IS NOT NULL
    GROUP BY mes
    ORDER BY mes
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_subcategorias_completo_mes(ano, mes):
    """Desglose por subcategoría - una factura = una sola vez."""
    query = f"""
    WITH facturas_clasif AS (
      SELECT
        f.numerofactura,
        CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) AS ano,
        CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) AS mes,
        CASE 
          WHEN lf.clasificacion_categoria IS NULL 
               OR lf.clasificacion_categoria = 'Sin clasificacion' 
               OR TRIM(lf.clasificacion_categoria) = ''
            THEN 'Otros'
          ELSE lf.clasificacion_categoria
        END AS categoria,
        COALESCE(lf.clasificacion_subcategoria, '') AS subcategoria,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE f.fechaemision IS NOT NULL
    ),
    facturas_unicas AS (
      SELECT
        numerofactura,
        ano,
        mes,
        categoria,
        MIN(subcategoria) AS subcategoria,
        MAX(total_factura) AS total_factura
      FROM facturas_clasif
      GROUP BY numerofactura, ano, mes, categoria
    ),
    resumen_categorias AS (
      SELECT
        ano,
        mes,
        categoria,
        subcategoria,
        COUNT(*) AS cantidad_trabajos,
        SUM(total_factura) AS total_dinero,
        AVG(total_factura) AS promedio_trabajo
      FROM facturas_unicas
      WHERE ano = {ano} AND mes = {mes}
      GROUP BY categoria, subcategoria
    ),
    totales_mes AS (
      SELECT
        SUM(total_dinero) AS total_mes,
        SUM(cantidad_trabajos) AS total_trabajos
      FROM resumen_categorias
    )
    SELECT
      rc.categoria,
      rc.subcategoria,
      rc.cantidad_trabajos AS cantidad,
      CAST(rc.total_dinero AS INTEGER) AS costo,
      CAST(rc.promedio_trabajo AS INTEGER) AS promedio,
      ROUND((rc.total_dinero / tm.total_mes) * 100, 2) AS pct
    FROM resumen_categorias rc
    CROSS JOIN totales_mes tm
    ORDER BY rc.total_dinero DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_evolucion_categorias_ano(ano):
    """Evolución mensual de categorías a lo largo del año."""
    query = f"""
    WITH facturas_clasif AS (
      SELECT
        f.numerofactura,
        CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) AS ano,
        CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) AS mes,
        CASE 
          WHEN lf.clasificacion_categoria IS NULL 
               OR lf.clasificacion_categoria = 'Sin clasificacion' 
               OR TRIM(lf.clasificacion_categoria) = ''
            THEN 'Otros'
          ELSE lf.clasificacion_categoria
        END AS categoria,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE f.fechaemision IS NOT NULL
    ),
    facturas_unicas AS (
      SELECT
        numerofactura,
        ano,
        mes,
        categoria,
        MAX(total_factura) AS total_factura
      FROM facturas_clasif
      GROUP BY numerofactura, ano, mes, categoria
    )
    SELECT
      mes,
      categoria,
      COUNT(DISTINCT numerofactura) as cantidad,
      CAST(SUM(total_factura) AS INTEGER) as total_mes,
      CAST(AVG(total_factura) AS INTEGER) as promedio_mes
    FROM facturas_unicas
    WHERE ano = {ano}
    GROUP BY mes, categoria
    ORDER BY mes, categoria
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_evolucion_subcategorias_ano(ano):
    """Evolución mensual de subcategorías a lo largo del año."""
    query = f"""
    WITH facturas_clasif AS (
      SELECT
        f.numerofactura,
        CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) AS ano,
        CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) AS mes,
        CASE 
          WHEN lf.clasificacion_categoria IS NULL 
               OR lf.clasificacion_categoria = 'Sin clasificacion' 
               OR TRIM(lf.clasificacion_categoria) = ''
            THEN 'Otros'
          ELSE lf.clasificacion_categoria
        END AS categoria,
        COALESCE(lf.clasificacion_subcategoria, '') AS subcategoria,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE f.fechaemision IS NOT NULL
    ),
    facturas_unicas AS (
      SELECT
        numerofactura,
        ano,
        mes,
        categoria,
        MIN(subcategoria) AS subcategoria,
        MAX(total_factura) AS total_factura
      FROM facturas_clasif
      GROUP BY numerofactura, ano, mes, categoria
    )
    SELECT
      mes,
      categoria || ' - ' || subcategoria as label,
      COUNT(DISTINCT numerofactura) as cantidad,
      CAST(SUM(total_factura) AS INTEGER) as total_mes,
      CAST(AVG(total_factura) AS INTEGER) as promedio_mes
    FROM facturas_unicas
    WHERE ano = {ano}
    GROUP BY mes, label
    ORDER BY mes, label
    """
    return pd.read_sql_query(query, conn)

# ============================================================
# FUNCIONES DE CONSULTA - NOTAS DE CRÉDITO
# ============================================================

@st.cache_data(ttl=300)
def get_notas_credito_12_meses(ano):
    """Comparativa de 12 meses de notas de crédito: cantidad + dinero."""
    query = f"""
    SELECT 
        CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
        COUNT(DISTINCT numeronota) as cantidad_notas,
        CAST(SUM(total + iva) AS INTEGER) as total_dinero
    FROM notascredito
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {int(ano)}
    AND fechaemision IS NOT NULL
    GROUP BY mes
    ORDER BY mes
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_notas_credito_categorias_mes(ano, mes):
    """Desglose de notas de crédito por categoría para un mes específico."""
    query = f"""
    WITH notas_clasif AS (
      SELECT
        nc.numeronota,
        CAST(STRFTIME('%Y', nc.fechaemision) AS INTEGER) AS ano,
        CAST(STRFTIME('%m', nc.fechaemision) AS INTEGER) AS mes,
        CASE 
          WHEN ln.clasificacion_categoria IS NULL 
               OR ln.clasificacion_categoria = 'Sin clasificacion' 
               OR TRIM(ln.clasificacion_categoria) = ''
            THEN 'Otros'
          ELSE ln.clasificacion_categoria
        END AS categoria,
        COALESCE(ln.clasificacion_subcategoria, '') AS subcategoria,
        COALESCE(nc.total, 0) + COALESCE(nc.iva, 0) AS total_nota
      FROM lineas_notas ln
      INNER JOIN notascredito nc ON ln.numeronota = nc.numeronota
      WHERE nc.fechaemision IS NOT NULL
    ),
    notas_unicas AS (
      SELECT
        numeronota,
        ano,
        mes,
        categoria,
        MIN(subcategoria) AS subcategoria,
        MAX(total_nota) AS total_nota
      FROM notas_clasif
      GROUP BY numeronota, ano, mes, categoria
    ),
    resumen_categorias AS (
      SELECT
        ano,
        mes,
        categoria,
        subcategoria,
        COUNT(*) AS cantidad_notas,
        GROUP_CONCAT(numeronota, ', ') AS numeros_nota,
        SUM(total_nota) AS total_dinero,
        AVG(total_nota) AS promedio_nota
      FROM notas_unicas
      WHERE ano = {ano} AND mes = {mes}
      GROUP BY categoria, subcategoria
    ),
    totales_mes AS (
      SELECT
        SUM(total_dinero) AS total_mes,
        SUM(cantidad_notas) AS total_notas
      FROM resumen_categorias
    )
    SELECT
      rc.categoria,
      rc.subcategoria,
      rc.cantidad_notas AS cantidad,
      rc.numeros_nota,
      CAST(rc.total_dinero AS INTEGER) AS costo,
      CAST(rc.promedio_nota AS INTEGER) AS promedio,
      ROUND((rc.total_dinero / tm.total_mes) * 100, 2) AS pct
    FROM resumen_categorias rc
    CROSS JOIN totales_mes tm
    ORDER BY rc.total_dinero DESC
    """
    return pd.read_sql_query(query, conn)

# ============================================================
# TABS PRINCIPALES
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Comparativa Anual",
    "🏷️ Desglose Subcategorías",
    "📈 Evolución Mensual",
    "📋 Notas de Crédito"
])

meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

# ============================================================
# TAB 1: COMPARATIVA ANUAL (12 MESES)
# ============================================================
with tab1:
    st.header("📊 Comparativa de Años")
    
    # PARTE 1: AÑO ACTUAL
    st.subheader(f"📅 Año {ano_actual} - Vista Actual")
    
    df_comp_actual = get_comparativa_12_meses(ano_actual)
    df_comp_actual_full = pd.DataFrame({'mes': range(1, 13)})
    df_comp_actual_full = df_comp_actual_full.merge(df_comp_actual, on='mes', how='left').fillna(0)
    df_comp_actual_full['cantidad_facturas'] = df_comp_actual_full['cantidad_facturas'].astype(int)
    df_comp_actual_full['total_dinero'] = df_comp_actual_full['total_dinero'].astype(int)
    df_comp_actual_full['promedio'] = (
        df_comp_actual_full['total_dinero'] /
        df_comp_actual_full['cantidad_facturas'].replace(0, 1)
    ).fillna(0).astype(int)
    
    fig_actual = go.Figure()
    fig_actual.add_trace(go.Bar(
        x=[meses_nombres[i-1] for i in df_comp_actual_full['mes']],
        y=df_comp_actual_full['cantidad_facturas'],
        name='Cantidad de Facturas',
        yaxis='y1',
        marker=dict(color='rgba(0, 118, 168, 0.7)'),
        hovertemplate='<b>%{x}</b><br>Facturas: %{y:,.0f}<extra></extra>'
    ))
    fig_actual.add_trace(go.Scatter(
        x=[meses_nombres[i-1] for i in df_comp_actual_full['mes']],
        y=df_comp_actual_full['total_dinero'],
        name='Total en Dinero ($)',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#FF6B6B', width=3),
        marker=dict(size=10),
        hovertemplate='<b>%{x}</b><br>Total: $%{y:,.0f}<extra></extra>'
    ))
    fig_actual.add_trace(go.Scatter(
        x=[meses_nombres[i-1] for i in df_comp_actual_full['mes']],
        y=df_comp_actual_full['promedio'],
        name='Promedio Mensual por Factura ($)',
        yaxis='y2',
        mode='lines',
        line=dict(color='rgba(0,0,0,0.6)', width=2, dash='dash'),
        hovertemplate='<b>%{x}</b><br>Promedio: $%{y:,.0f}<extra></extra>'
    ))
    fig_actual.update_layout(
        xaxis_title="Mes",
        yaxis=dict(title="Cantidad de Facturas", side='left'),
        yaxis2=dict(title="Total / Promedio ($)", overlaying='y', side='right'),
        hovermode='x unified',
        height=400,
        showlegend=True
    )
    st.plotly_chart(fig_actual, use_container_width=True)
    
    tabla_actual = df_comp_actual_full.copy()
    tabla_actual['mes_nombre'] = [meses_nombres[i-1] for i in tabla_actual['mes']]
    tabla_actual['cantidad_facturas_fmt'] = tabla_actual['cantidad_facturas'].apply(lambda x: f"{int(x):,}")
    tabla_actual['total_dinero_fmt'] = tabla_actual['total_dinero'].apply(lambda x: f"${int(x):,}")
    tabla_actual['promedio_fmt'] = tabla_actual['promedio'].apply(lambda x: f"${int(x):,}")
    st.dataframe(
        tabla_actual[['mes_nombre', 'cantidad_facturas_fmt', 'total_dinero_fmt', 'promedio_fmt']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "mes_nombre": st.column_config.TextColumn("Mes", width=80),
            "cantidad_facturas_fmt": st.column_config.TextColumn("Facturas", width=100),
            "total_dinero_fmt": st.column_config.TextColumn("Total ($)", width=130),
            "promedio_fmt": st.column_config.TextColumn("Promedio/Factura ($)", width=150),
        }
    )
    
    # PARTE 2: COMPARATIVA ENTRE AÑOS
    st.divider()
    st.subheader("🔄 Comparativa entre Años (Lado a Lado)")
    
    col_ano1, col_ano2 = st.columns(2)
    with col_ano1:
        ano_comp1 = st.selectbox("📅 Año 1", anos_disponibles, index=0, key="ano_comp1")
    with col_ano2:
        ano_comp2 = st.selectbox("📅 Año 2", anos_disponibles,
                                 index=min(1, len(anos_disponibles)-1), key="ano_comp2")
    
    # Año 1
    df_comp1 = get_comparativa_12_meses(ano_comp1)
    df_comp1_full = pd.DataFrame({'mes': range(1, 13)})
    df_comp1_full = df_comp1_full.merge(df_comp1, on='mes', how='left').fillna(0)
    df_comp1_full['cantidad_facturas'] = df_comp1_full['cantidad_facturas'].astype(int)
    df_comp1_full['total_dinero'] = df_comp1_full['total_dinero'].astype(int)
    df_comp1_full['promedio'] = (
        df_comp1_full['total_dinero'] /
        df_comp1_full['cantidad_facturas'].replace(0, 1)
    ).fillna(0).astype(int)
    
    # Año 2
    df_comp2 = get_comparativa_12_meses(ano_comp2) if ano_comp1 != ano_comp2 else pd.DataFrame()
    if not df_comp2.empty:
        df_comp2_full = pd.DataFrame({'mes': range(1, 13)})
        df_comp2_full = df_comp2_full.merge(df_comp2, on='mes', how='left').fillna(0)
        df_comp2_full['cantidad_facturas'] = df_comp2_full['cantidad_facturas'].astype(int)
        df_comp2_full['total_dinero'] = df_comp2_full['total_dinero'].astype(int)
        df_comp2_full['promedio'] = (
            df_comp2_full['total_dinero'] /
            df_comp2_full['cantidad_facturas'].replace(0, 1)
        ).fillna(0).astype(int)
    
    # Gráficos lado a lado
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.subheader(f"Año {ano_comp1}")
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=[meses_nombres[i-1] for i in df_comp1_full['mes']],
            y=df_comp1_full['cantidad_facturas'],
            name='Cantidad',
            yaxis='y1',
            marker=dict(color='rgba(0, 118, 168, 0.7)'),
            hovertemplate='<b>%{x}</b><br>Facturas: %{y:,.0f}<extra></extra>'
        ))
        fig1.add_trace(go.Scatter(
            x=[meses_nombres[i-1] for i in df_comp1_full['mes']],
            y=df_comp1_full['total_dinero'],
            name='Total ($)',
            yaxis='y2',
            mode='lines+markers',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Total: $%{y:,.0f}<extra></extra>'
        ))
        fig1.add_trace(go.Scatter(
            x=[meses_nombres[i-1] for i in df_comp1_full['mes']],
            y=df_comp1_full['promedio'],
            name='Promedio',
            yaxis='y2',
            mode='lines',
            line=dict(color='rgba(0,0,0,0.6)', width=2, dash='dash'),
            hovertemplate='<b>%{x}</b><br>Promedio: $%{y:,.0f}<extra></extra>'
        ))
        fig1.update_layout(
            xaxis_title="Mes",
            yaxis=dict(title="Facturas", side='left'),
            yaxis2=dict(title="Total / Promedio ($)", overlaying='y', side='right'),
            hovermode='x unified',
            height=400,
            showlegend=True
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    if ano_comp1 != ano_comp2 and not df_comp2.empty:
        with col_graf2:
            st.subheader(f"Año {ano_comp2}")
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=[meses_nombres[i-1] for i in df_comp2_full['mes']],
                y=df_comp2_full['cantidad_facturas'],
                name='Cantidad',
                yaxis='y1',
                marker=dict(color='rgba(76, 175, 80, 0.7)'),
                hovertemplate='<b>%{x}</b><br>Facturas: %{y:,.0f}<extra></extra>'
            ))
            fig2.add_trace(go.Scatter(
                x=[meses_nombres[i-1] for i in df_comp2_full['mes']],
                y=df_comp2_full['total_dinero'],
                name='Total ($)',
                yaxis='y2',
                mode='lines+markers',
                line=dict(color='#FFC107', width=3),
                marker=dict(size=10),
                hovertemplate='<b>%{x}</b><br>Total: $%{y:,.0f}<extra></extra>'
            ))
            fig2.add_trace(go.Scatter(
                x=[meses_nombres[i-1] for i in df_comp2_full['mes']],
                y=df_comp2_full['promedio'],
                name='Promedio',
                yaxis='y2',
                mode='lines',
                line=dict(color='rgba(0,0,0,0.6)', width=2, dash='dash'),
                hovertemplate='<b>%{x}</b><br>Promedio: $%{y:,.0f}<extra></extra>'
            ))
            fig2.update_layout(
                xaxis_title="Mes",
                yaxis=dict(title="Facturas", side='left'),
                yaxis2=dict(title="Total / Promedio ($)", overlaying='y', side='right'),
                hovermode='x unified',
                height=400,
                showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    # Tablas lado a lado
    st.subheader("Tablas Comparativas")
    col_tab1, col_tab2 = st.columns(2)
    
    with col_tab1:
        st.caption(f"Año {ano_comp1}")
        tabla1 = df_comp1_full.copy()
        tabla1['mes_nombre'] = [meses_nombres[i-1] for i in tabla1['mes']]
        tabla1['cantidad_facturas_fmt'] = tabla1['cantidad_facturas'].apply(lambda x: f"{int(x):,}")
        tabla1['total_dinero_fmt'] = tabla1['total_dinero'].apply(lambda x: f"${int(x):,}")
        tabla1['promedio_fmt'] = tabla1['promedio'].apply(lambda x: f"${int(x):,}")
        st.dataframe(
            tabla1[['mes_nombre', 'cantidad_facturas_fmt', 'total_dinero_fmt', 'promedio_fmt']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "mes_nombre": st.column_config.TextColumn("Mes", width=60),
                "cantidad_facturas_fmt": st.column_config.TextColumn("Facturas", width=80),
                "total_dinero_fmt": st.column_config.TextColumn("Total", width=100),
                "promedio_fmt": st.column_config.TextColumn("Promedio", width=100),
            }
        )
    
    if ano_comp1 != ano_comp2 and not df_comp2.empty:
        with col_tab2:
            st.caption(f"Año {ano_comp2}")
            tabla2 = df_comp2_full.copy()
            tabla2['mes_nombre'] = [meses_nombres[i-1] for i in tabla2['mes']]
            tabla2['cantidad_facturas_fmt'] = tabla2['cantidad_facturas'].apply(lambda x: f"{int(x):,}")
            tabla2['total_dinero_fmt'] = tabla2['total_dinero'].apply(lambda x: f"${int(x):,}")
            tabla2['promedio_fmt'] = tabla2['promedio'].apply(lambda x: f"${int(x):,}")
            st.dataframe(
                tabla2[['mes_nombre', 'cantidad_facturas_fmt', 'total_dinero_fmt', 'promedio_fmt']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mes_nombre": st.column_config.TextColumn("Mes", width=60),
                    "cantidad_facturas_fmt": st.column_config.TextColumn("Facturas", width=80),
                    "total_dinero_fmt": st.column_config.TextColumn("Total", width=100),
                    "promedio_fmt": st.column_config.TextColumn("Promedio", width=100),
                }
            )

# ============================================================
# TAB 2: DESGLOSE SUBCATEGORÍAS
# ============================================================
with tab2:
    st.header(f"🏷️ Desglose Subcategorías - Año {ano_actual}")
    
    col_mes, col_space = st.columns([2, 10])
    with col_mes:
        mes_tab2 = st.selectbox(
            "📅 Mes",
            range(1, 13),
            index=0,
            format_func=lambda x: meses_nombres[x-1],
            key="tab2_mes"
        )
    
    df_subcat = get_subcategorias_completo_mes(ano_actual, mes_tab2)
    
    if not df_subcat.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Subcategorías", f"{len(df_subcat):,}")
        with col2:
            st.metric("Ingresos Totales", f"${df_subcat['costo'].sum():,.0f}")
        with col3:
            st.metric("Cantidad Total", f"{df_subcat['cantidad'].sum():,}")
        with col4:
            promedio_gral = int(df_subcat['costo'].sum() / df_subcat['cantidad'].sum())
            st.metric("Promedio General", f"${promedio_gral:,}")
        
        st.divider()
        
        st.subheader("Detalle Completo")
        df_subcat_fmt = df_subcat.copy()
        df_subcat_fmt['cantidad_fmt'] = df_subcat_fmt['cantidad'].apply(lambda x: f"{int(x):,}")
        df_subcat_fmt['costo_fmt'] = df_subcat_fmt['costo'].apply(lambda x: f"${int(x):,}")
        df_subcat_fmt['promedio_fmt'] = df_subcat_fmt['promedio'].apply(lambda x: f"${int(x):,}")
        df_subcat_fmt['pct_fmt'] = df_subcat_fmt['pct'].apply(lambda x: f"{x:.2f}%")
        st.dataframe(
            df_subcat_fmt[['categoria', 'subcategoria', 'cantidad_fmt', 'costo_fmt', 'promedio_fmt', 'pct_fmt']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria": st.column_config.TextColumn("Categoría", width=150),
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=200),
                "cantidad_fmt": st.column_config.TextColumn("Cantidad", width=100),
                "costo_fmt": st.column_config.TextColumn("Total ($)", width=130),
                "promedio_fmt": st.column_config.TextColumn("Promedio ($)", width=130),
                "pct_fmt": st.column_config.TextColumn("% Total", width=100),
            }
        )
        
        st.subheader("Distribución por Categoría y Subcategoría")
        
        df_subcat_vis = df_subcat.copy()
        df_subcat_vis['label_completo'] = df_subcat_vis['categoria'] + ' - ' + df_subcat_vis['subcategoria']
        total_mes = df_subcat_vis['costo'].sum()
        
        col_donut, col_sunburst = st.columns(2)
        
        with col_donut:
            st.markdown("#### Gráfico Donut - Mes Actual")
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=df_subcat_vis['label_completo'],
                values=df_subcat_vis['costo'],
                hole=0.45,
                textposition='auto',
                hovertemplate='<b>%{label}</b><br>Total: $%{value:,.0f}<br>%{percent}<extra></extra>',
                marker=dict(line=dict(color='white', width=3))
            )])
            
            fig_donut.update_layout(
                title=dict(text=f"{meses_nombres[mes_tab2-1]} {ano_actual}", x=0.5, xanchor='center'),
                annotations=[dict(
                    text=f'<b>Total</b><br>${total_mes:,.0f}',
                    x=0.5, y=0.5,
                    font_size=14,
                    showarrow=False
                )],
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=9)),
                height=550
            )
            
            st.plotly_chart(fig_donut, use_container_width=True)
        
        with col_sunburst:
            st.markdown("#### Vista Sunburst - Jerarquía")
            
            fig_sunburst = px.sunburst(
                df_subcat_vis,
                path=['categoria', 'subcategoria'],
                values='costo',
                color='costo',
                color_continuous_scale='Viridis'
            )
            
            fig_sunburst.update_traces(
                textinfo='label+percent parent',
                hovertemplate='<b>%{label}</b><br>Total: $%{value:,.0f}<br>%{percentParent}<extra></extra>',
                marker=dict(line=dict(color='white', width=2))
            )
            
            fig_sunburst.update_layout(
                title=dict(text='Categorías → Subcategorías', x=0.5, xanchor='center'),
                height=550
            )
            
            st.plotly_chart(fig_sunburst, use_container_width=True)
        
    else:
        st.info("ℹ️ Sin datos de subcategorías")

# ============================================================
# TAB 3: EVOLUCIÓN MENSUAL
# ============================================================
with tab3:
    st.header(f"📈 Evolución Mensual - Año {ano_actual}")
    
    st.subheader("📊 Evolución de Categorías")
    
    df_evo_cat = get_evolucion_categorias_ano(ano_actual)
    
    if not df_evo_cat.empty:
        df_cat_pivot_cant = df_evo_cat.pivot_table(
            index='mes', columns='categoria', values='cantidad',
            aggfunc='sum', fill_value=0
        )
        df_cat_pivot_total = df_evo_cat.pivot_table(
            index='mes', columns='categoria', values='total_mes',
            aggfunc='sum', fill_value=0
        )
        
        for mes in range(1, 13):
            if mes not in df_cat_pivot_cant.index:
                df_cat_pivot_cant.loc[mes] = 0
            if mes not in df_cat_pivot_total.index:
                df_cat_pivot_total.loc[mes] = 0
        
        df_cat_pivot_cant = df_cat_pivot_cant.sort_index()
        df_cat_pivot_total = df_cat_pivot_total.sort_index()
        
        fig_cat = go.Figure()
        
        for col in df_cat_pivot_cant.columns:
            fig_cat.add_trace(go.Scatter(
                x=[meses_nombres[m-1] for m in df_cat_pivot_cant.index],
                y=df_cat_pivot_cant[col],
                name=col,
                mode='lines+markers',
                line=dict(width=3),
                marker=dict(size=8),
                customdata=df_cat_pivot_total[col],
                hovertemplate='<b>%{x}</b><br><b>' + col + '</b><br>Cantidad: %{y:,.0f} | Total: $%{customdata:,.0f}<extra></extra>'
            ))
        
        fig_cat.update_layout(
            xaxis_title="Mes",
            yaxis=dict(title="Cantidad de Trabajos"),
            hovermode='x unified',
            height=500,
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        
        st.plotly_chart(fig_cat, use_container_width=True)
        
        st.markdown("#### Resumen por Categoría")
        resumen_cat = df_evo_cat.groupby('categoria').agg({
            'cantidad': 'sum',
            'total_mes': 'sum',
            'promedio_mes': 'mean'
        }).reset_index()
        resumen_cat['cantidad_fmt'] = resumen_cat['cantidad'].apply(lambda x: f"{int(x):,}")
        resumen_cat['total_fmt'] = resumen_cat['total_mes'].apply(lambda x: f"${int(x):,}")
        resumen_cat['promedio_fmt'] = resumen_cat['promedio_mes'].apply(lambda x: f"${int(x):,}")
        
        st.dataframe(
            resumen_cat[['categoria', 'cantidad_fmt', 'total_fmt', 'promedio_fmt']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria": st.column_config.TextColumn("Categoría", width=200),
                "cantidad_fmt": st.column_config.TextColumn("Total Cantidad", width=150),
                "total_fmt": st.column_config.TextColumn("Total Ingresos", width=150),
                "promedio_fmt": st.column_config.TextColumn("Promedio", width=150),
            }
        )
    else:
        st.info("ℹ️ Sin datos de categorías para este año")
    
    st.divider()
    
    st.subheader("🏷️ Evolución de Todas las Subcategorías")
    
    df_evo_subcat = get_evolucion_subcategorias_ano(ano_actual)
    
    if not df_evo_subcat.empty:
        total_subcats = df_evo_subcat['label'].nunique()
        st.info(f"📊 Mostrando evolución de **{total_subcats}** subcategorías diferentes")
        
        col_filtro1, col_filtro2 = st.columns([3, 9])
        with col_filtro1:
            mostrar_top = st.checkbox("Filtrar Top N", value=False, key="filtrar_top_subcat")
        
        if mostrar_top:
            with col_filtro2:
                top_n = st.slider("Cantidad a mostrar", min_value=5, max_value=50, value=20, step=5)
            top_subcats_anual = df_evo_subcat.groupby('label')['total_mes'].sum().nlargest(top_n).index.tolist()
            df_evo_subcat_filtrado = df_evo_subcat[df_evo_subcat['label'].isin(top_subcats_anual)]
            st.caption(f"Mostrando top {top_n} subcategorías por ingresos totales del año")
        else:
            df_evo_subcat_filtrado = df_evo_subcat
            st.caption("Mostrando todas las subcategorías")
        
        df_subcat_pivot_cant = df_evo_subcat_filtrado.pivot_table(
            index='mes', columns='label', values='cantidad',
            aggfunc='sum', fill_value=0
        )
        df_subcat_pivot_total = df_evo_subcat_filtrado.pivot_table(
            index='mes', columns='label', values='total_mes',
            aggfunc='sum', fill_value=0
        )
        
        for mes in range(1, 13):
            if mes not in df_subcat_pivot_cant.index:
                df_subcat_pivot_cant.loc[mes] = 0
            if mes not in df_subcat_pivot_total.index:
                df_subcat_pivot_total.loc[mes] = 0
        
        df_subcat_pivot_cant = df_subcat_pivot_cant.sort_index()
        df_subcat_pivot_total = df_subcat_pivot_total.sort_index()
        
        fig_subcat = go.Figure()
        
        for col in df_subcat_pivot_cant.columns:
            fig_subcat.add_trace(go.Scatter(
                x=[meses_nombres[m-1] for m in df_subcat_pivot_cant.index],
                y=df_subcat_pivot_cant[col],
                name=col,
                mode='lines+markers',
                line=dict(width=3),
                marker=dict(size=8),
                customdata=df_subcat_pivot_total[col],
                hovertemplate='<b>%{x}</b><br><b>' + col + '</b><br>Cantidad: %{y:,.0f} | Total: $%{customdata:,.0f}<extra></extra>'
            ))
        
        fig_subcat.update_layout(
            xaxis_title="Mes",
            yaxis=dict(title="Cantidad de Trabajos"),
            hovermode='x unified',
            height=600,
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        
        st.plotly_chart(fig_subcat, use_container_width=True)
        
        st.markdown("#### Resumen Completo de Subcategorías del Año")
        resumen_subcat = df_evo_subcat.groupby('label').agg({
            'cantidad': 'sum',
            'total_mes': 'sum',
            'promedio_mes': 'mean'
        }).reset_index().sort_values('total_mes', ascending=False)
        
        resumen_subcat['cantidad_fmt'] = resumen_subcat['cantidad'].apply(lambda x: f"{int(x):,}")
        resumen_subcat['total_fmt'] = resumen_subcat['total_mes'].apply(lambda x: f"${int(x):,}")
        resumen_subcat['promedio_fmt'] = resumen_subcat['promedio_mes'].apply(lambda x: f"${int(x):,}")
        
        st.dataframe(
            resumen_subcat[['label', 'cantidad_fmt', 'total_fmt', 'promedio_fmt']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "label": st.column_config.TextColumn("Categoría - Subcategoría", width=250),
                "cantidad_fmt": st.column_config.TextColumn("Total Cantidad", width=150),
                "total_fmt": st.column_config.TextColumn("Total Ingresos", width=150),
                "promedio_fmt": st.column_config.TextColumn("Promedio", width=150),
            }
        )
    else:
        st.info("ℹ️ Sin datos de subcategorías para este año")

# ============================================================
# TAB 4: NOTAS DE CRÉDITO
# ============================================================
with tab4:
    st.header("📋 Notas de Crédito")
    
    st.subheader(f"📅 Año {ano_actual} - Evolución Mensual")
    
    df_notas = get_notas_credito_12_meses(ano_actual)
    
    if not df_notas.empty:
        df_notas_full = pd.DataFrame({'mes': range(1, 13)})
        df_notas_full = df_notas_full.merge(df_notas, on='mes', how='left').fillna(0)
        df_notas_full['cantidad_notas'] = df_notas_full['cantidad_notas'].astype(int)
        df_notas_full['total_dinero'] = df_notas_full['total_dinero'].astype(int)
        df_notas_full['promedio'] = (
            df_notas_full['total_dinero'] /
            df_notas_full['cantidad_notas'].replace(0, 1)
        ).fillna(0).astype(int)
        
        # Gráfico
        fig_notas = go.Figure()
        fig_notas.add_trace(go.Bar(
            x=[meses_nombres[i-1] for i in df_notas_full['mes']],
            y=df_notas_full['cantidad_notas'],
            name='Cantidad de Notas',
            yaxis='y1',
            marker=dict(color='rgba(255, 107, 107, 0.7)'),
            hovertemplate='<b>%{x}</b><br>Notas: %{y:,.0f}<extra></extra>'
        ))
        fig_notas.add_trace(go.Scatter(
            x=[meses_nombres[i-1] for i in df_notas_full['mes']],
            y=df_notas_full['total_dinero'],
            name='Total en Dinero ($)',
            yaxis='y2',
            mode='lines+markers',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Total: $%{y:,.0f}<extra></extra>'
        ))
        fig_notas.add_trace(go.Scatter(
            x=[meses_nombres[i-1] for i in df_notas_full['mes']],
            y=df_notas_full['promedio'],
            name='Promedio por Nota ($)',
            yaxis='y2',
            mode='lines',
            line=dict(color='rgba(0,0,0,0.6)', width=2, dash='dash'),
            hovertemplate='<b>%{x}</b><br>Promedio: $%{y:,.0f}<extra></extra>'
        ))
        fig_notas.update_layout(
            xaxis_title="Mes",
            yaxis=dict(title="Cantidad de Notas", side='left'),
            yaxis2=dict(title="Total / Promedio ($)", overlaying='y', side='right'),
            hovermode='x unified',
            height=400,
            showlegend=True
        )
        st.plotly_chart(fig_notas, use_container_width=True)
        
        # Tabla
        st.subheader("📋 Detalle Mensual")
        tabla_notas = df_notas_full.copy()
        tabla_notas['mes_nombre'] = [meses_nombres[i-1] for i in tabla_notas['mes']]
        tabla_notas['cantidad_notas_fmt'] = tabla_notas['cantidad_notas'].apply(lambda x: f"{int(x):,}")
        tabla_notas['total_dinero_fmt'] = tabla_notas['total_dinero'].apply(lambda x: f"${int(x):,}")
        tabla_notas['promedio_fmt'] = tabla_notas['promedio'].apply(lambda x: f"${int(x):,}")
        st.dataframe(
            tabla_notas[['mes_nombre', 'cantidad_notas_fmt', 'total_dinero_fmt', 'promedio_fmt']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "mes_nombre": st.column_config.TextColumn("Mes", width=80),
                "cantidad_notas_fmt": st.column_config.TextColumn("Notas", width=100),
                "total_dinero_fmt": st.column_config.TextColumn("Total ($)", width=130),
                "promedio_fmt": st.column_config.TextColumn("Promedio/Nota ($)", width=150),
            }
        )
        
        # Métricas del año
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Notas del Año", f"{df_notas_full['cantidad_notas'].sum():,}")
        with col2:
            st.metric("Monto Total Anual", f"${df_notas_full['total_dinero'].sum():,}")
        with col3:
            promedio_anual = int(df_notas_full['total_dinero'].sum() / df_notas_full['cantidad_notas'].sum()) if df_notas_full['cantidad_notas'].sum() > 0 else 0
            st.metric("Promedio Anual", f"${promedio_anual:,}")
        
        # Desglose por mes (opcional)
        st.divider()
        st.subheader("🔍 Desglose por Mes y Categoría")
        
        mes_detalle = st.selectbox(
            "Selecciona un mes para ver el desglose",
            range(1, 13),
            format_func=lambda x: meses_nombres[x-1],
            key="mes_detalle_notas"
        )
        
        df_notas_cat = get_notas_credito_categorias_mes(ano_actual, mes_detalle)
        
        if not df_notas_cat.empty:
            st.dataframe(
                df_notas_cat[['categoria', 'subcategoria', 'cantidad', 'numeros_nota', 'costo', 'promedio', 'pct']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "categoria": st.column_config.TextColumn("Categoría", width=150),
                    "subcategoria": st.column_config.TextColumn("Subcategoría", width=150),
                    "cantidad": st.column_config.NumberColumn("Cantidad", width=80),
                    "numeros_nota": st.column_config.TextColumn("Nº Notas", width=200),
                    "costo": st.column_config.NumberColumn("Total ($)", width=120, format="$%d"),
                    "promedio": st.column_config.NumberColumn("Promedio ($)", width=120, format="$%d"),
                    "pct": st.column_config.NumberColumn("% Total", width=80, format="%.2f%%"),
                }
            )
        else:
            st.info(f"ℹ️ Sin notas de crédito para {meses_nombres[mes_detalle-1]} {ano_actual}")
        
    else:
        st.info(f"ℹ️ Sin notas de crédito para el año {ano_actual}")

# ============================================================
# PIE DE PÁGINA
# ============================================================
st.divider()
st.caption(
    f"✅ Dashboard Ben&Frank | Rodenstock | Cristián Ibañez | "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M')} | Año {ano_actual}"
)