
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

DB_FILE = "facturas.db"

st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CONEXION
@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_FILE)

# AÑOS DISPONIBLES - DINÁMICO
@st.cache_data(ttl=600)
def get_anos_disponibles():
    conn = get_conn()
    query = """
    SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) AS ano 
    FROM facturas 
    WHERE fechaemision IS NOT NULL 
    ORDER BY ano DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
        return sorted(df['ano'].tolist()) if not df.empty else [datetime.now().year]
    except:
        return [datetime.now().year]

# DATOS UNIFICADOS
@st.cache_data(ttl=600)
def get_datos_unificados(ano=None, mes=None):
    conn = get_conn()
    filtros = ["f.fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}")
    if mes is not None:
        filtros.append(f"CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes}")
    
    where_clause = " AND ".join(filtros)
    
    query = f"""
    SELECT
      CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) AS ano,
      CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) AS mes,
      STRFTIME('%Y-%m', f.fechaemision) AS mes_formato,
      COALESCE(lf.clasificacion_categoria, 'Sin Clasificar') || ' - ' || 
      COALESCE(lf.clasificacion_subcategoria, '') AS categoria,
      COUNT(DISTINCT lf.numerofactura) AS cantidad_trabajos,
      ROUND(SUM(CAST(lf.total_linea AS FLOAT)), 0) AS total_dinero
    FROM lineas_factura lf
    JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE {where_clause}
    GROUP BY ano, mes, mes_formato, categoria
    ORDER BY mes_formato ASC, categoria
    """
    return pd.read_sql_query(query, conn)

# TOTALES GENERALES
@st.cache_data(ttl=600)
def get_totales_generales(ano=None, mes=None):
    conn = get_conn()
    filtros = ["f.fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}")
    if mes is not None:
        filtros.append(f"CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes}")
    
    where_clause = " AND ".join(filtros)
    
    query = f"""
    SELECT
      COUNT(DISTINCT f.numerofactura) AS total_facturas,
      ROUND(SUM(CAST(lf.total_linea AS FLOAT)), 0) AS total_ingresos,
      ROUND(AVG(CAST(lf.total_linea AS FLOAT)), 0) AS promedio_factura
    FROM lineas_factura lf
    JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE {where_clause}
    """
    return pd.read_sql_query(query, conn)

# DISTRIBUICIÓN MENSUAL
@st.cache_data(ttl=600)
def get_distribucion_mensual_anual(ano):
    conn = get_conn()
    query = f"""
    WITH datos_mensuales AS (
      SELECT
        STRFTIME('%Y-%m', fechaemision) AS mes,
        ROUND(SUM(CAST(COALESCE(valorneto, 0) AS FLOAT) + CAST(COALESCE(iva, 0) AS FLOAT)), 0) AS total_mes
      FROM facturas
      WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano}
        AND fechaemision IS NOT NULL
      GROUP BY mes
    ),
    total_anual AS (
      SELECT SUM(total_mes) AS total_ano FROM datos_mensuales
    )
    SELECT
      dm.mes,
      dm.total_mes,
      ROUND((dm.total_mes * 100.0) / ta.total_ano, 1) AS porcentaje
    FROM datos_mensuales dm
    CROSS JOIN total_anual ta
    ORDER BY dm.mes ASC
    """
    return pd.read_sql_query(query, conn)

# FACTURAS VS NOTAS
@st.cache_data(ttl=600)
def get_facturas_vs_notas():
    conn = get_conn()
    query = """
    SELECT
      STRFTIME('%Y-%m', f.fechaemision) AS mes,
      COUNT(f.numerofactura) AS cantidad_facturas,
      COUNT(n.numeronota) AS cantidad_notas,
      ROUND(SUM(CAST(COALESCE(f.valorneto, 0) AS FLOAT) + CAST(COALESCE(f.iva, 0) AS FLOAT)), 0) AS total_mes,
      ROUND(AVG(CAST(COALESCE(f.valorneto, 0) AS FLOAT) + CAST(COALESCE(f.iva, 0) AS FLOAT)), 0) AS promedio_mes
    FROM facturas f
    LEFT JOIN notascredito n ON STRFTIME('%Y-%m', f.fechaemision) = STRFTIME('%Y-%m', n.fechaemision)
    WHERE f.fechaemision IS NOT NULL
    GROUP BY mes
    ORDER BY mes ASC
    """
    return pd.read_sql_query(query, conn)

# DETALLE CON PORCENTAJE
@st.cache_data(ttl=600)
def get_datos_detalle_con_porcentaje(ano=None, mes=None):
    conn = get_conn()
    filtros = ["f.fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano}")
    if mes is not None:
        filtros.append(f"CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes}")
    
    where_clause = " AND ".join(filtros)
    
    query = f"""
    WITH datos_base AS (
      SELECT
        CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) AS ano,
        CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) AS mes,
        STRFTIME('%Y-%m', f.fechaemision) AS mes_formato,
        COALESCE(lf.clasificacion_categoria, 'Sin Clasificar') || ' - ' || 
        COALESCE(lf.clasificacion_subcategoria, '') AS categoria,
        COUNT(DISTINCT lf.numerofactura) AS cantidad_trabajos,
        ROUND(SUM(CAST(lf.total_linea AS FLOAT)), 0) AS total_dinero
      FROM lineas_factura lf
      JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE {where_clause}
      GROUP BY ano, mes, mes_formato, categoria
    ),
    total_general AS (
      SELECT SUM(cantidad_trabajos) AS total_trabajos FROM datos_base
    )
    SELECT
      d.ano,
      d.mes,
      d.mes_formato,
      d.categoria,
      d.cantidad_trabajos,
      d.total_dinero,
      ROUND(d.total_dinero / d.cantidad_trabajos, 0) AS promedio_trabajo,
      ROUND((d.cantidad_trabajos * 100.0) / tg.total_trabajos, 2) AS porcentaje
    FROM datos_base d
    CROSS JOIN total_general tg
    ORDER BY d.ano DESC, d.mes DESC, d.total_dinero DESC
    """
    return pd.read_sql_query(query, conn)

# TÍTULO
st.title("📊 Dashboard de Facturación Rodenstock")
st.markdown("---")

# SIDEBAR CON FILTROS DINÁMICOS
with st.sidebar:
    st.header("🔧 Filtros")
    
    # Años dinámicos
    anos_disponibles = get_anos_disponibles()
    ano_seleccionado = st.selectbox(
        "Año",
        options=anos_disponibles,
        index=len(anos_disponibles) - 1 if anos_disponibles else 0
    )
    
    meses = {
        None: "Todos",
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    mes_seleccionado = st.selectbox(
        "Mes",
        options=list(meses.keys()),
        format_func=lambda x: meses[x],
        index=0
    )
    
    st.markdown("---")
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

# RESUMEN GENERAL
st.header("📈 Resumen General")

try:
    totales = get_totales_generales(ano_seleccionado, mes_seleccionado)
    
    if not totales.empty and totales['total_facturas'].iloc[0] > 0:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="📋 Total Trabajos",
                value=f"{int(totales['total_facturas'].iloc[0]):,}"
            )
        with col2:
            st.metric(
                label="💰 Ingresos Totales",
                value=f"${int(totales['total_ingresos'].iloc[0]):,}"
            )
        with col3:
            st.metric(
                label="📊 Promedio por Trabajo",
                value=f"${int(totales['promedio_factura'].iloc[0]):,}"
            )
        
        st.markdown("---")
        
        # DATOS PARA GRÁFICOS
        df_datos = get_datos_unificados(ano_seleccionado, mes_seleccionado)
        
        if not df_datos.empty:
            tab1, tab2, tab3 = st.tabs(["📊 Distribución", "📈 Evolución", "🔍 Detalle"])
            
            # TAB 1: DISTRIBUCIÓN
            with tab1:
                st.subheader("Distribución por Categoría")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    fig_barras = px.bar(
                        df_datos.sort_values('total_dinero', ascending=False).head(15),
                        x='categoria',
                        y='cantidad_trabajos',
                        color='categoria',
                        title='Top 15 Categorías por Cantidad de Trabajos',
                        labels={'cantidad_trabajos': 'Cantidad', 'categoria': 'Categoría'},
                        height=500
                    )
                    fig_barras.update_layout(showlegend=False, xaxis_tickangle=-45)
                    st.plotly_chart(fig_barras, use_container_width=True)
                
                with col2:
                    fig_pie = px.pie(
                        df_datos.head(10),
                        values='total_dinero',
                        names='categoria',
                        title='Distribución de Ingresos (Top 10)',
                        height=500
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                # FACTURAS VS NOTAS
                st.subheader("Facturas vs Notas de Crédito por Mes")
                df_fac_notas = get_facturas_vs_notas()
                
                if not df_fac_notas.empty:
                    fig_combo = go.Figure()
                    fig_combo.add_trace(go.Bar(
                        x=df_fac_notas['mes'],
                        y=df_fac_notas['cantidad_facturas'],
                        name='Facturas',
                        marker_color='#3b82f6'
                    ))
                    fig_combo.add_trace(go.Bar(
                        x=df_fac_notas['mes'],
                        y=df_fac_notas['cantidad_notas'],
                        name='Notas de Crédito',
                        marker_color='#ef4444'
                    ))
                    fig_combo.add_trace(go.Scatter(
                        x=df_fac_notas['mes'],
                        y=df_fac_notas['promedio_mes'],
                        name='Promedio Mensual',
                        yaxis='y2',
                        line=dict(color='#059669', width=3),
                        mode='lines+markers'
                    ))
                    fig_combo.update_layout(
                        title='Cantidad de Facturas y Notas vs Promedio Mensual',
                        yaxis_title='Cantidad',
                        yaxis2=dict(title='Promedio ($)', overlaying='y', side='right'),
                        barmode='group',
                        height=500
                    )
                    st.plotly_chart(fig_combo, use_container_width=True)
                
                # DISTRIBUCIÓN MENSUAL
                st.subheader(f"Distribución Mensual del Año {ano_seleccionado}")
                df_dist_mensual = get_distribucion_mensual_anual(ano_seleccionado)
                
                if not df_dist_mensual.empty:
                    fig_pie_mensual = px.pie(
                        df_dist_mensual,
                        values='total_mes',
                        names='mes',
                        title=f'Porcentaje que Representa Cada Mes {ano_seleccionado}',
                        height=600
                    )
                    fig_pie_mensual.update_traces(
                        textposition='inside',
                        textinfo='percent+label'
                    )
                    st.plotly_chart(fig_pie_mensual, use_container_width=True)
            
            # TAB 2: EVOLUCIÓN
            with tab2:
                st.subheader("Evolución Mensual")
                st.info("📊 Valores absolutos por mes y categoría")
                
                fig_trabajos = px.line(
                    df_datos,
                    x='mes_formato',
                    y='cantidad_trabajos',
                    color='categoria',
                    title='Cantidad de Trabajos por Mes',
                    height=450,
                    markers=True
                )
                st.plotly_chart(fig_trabajos, use_container_width=True)
                
                fig_total = px.line(
                    df_datos,
                    x='mes_formato',
                    y='total_dinero',
                    color='categoria',
                    title='Total de Ingresos por Mes',
                    height=450,
                    markers=True
                )
                st.plotly_chart(fig_total, use_container_width=True)
                
                # Calcular promedio
                df_datos['promedio'] = df_datos['total_dinero'] / df_datos['cantidad_trabajos']
                fig_promedio = px.line(
                    df_datos,
                    x='mes_formato',
                    y='promedio',
                    color='categoria',
                    title='Promedio por Trabajo',
                    height=450,
                    markers=True
                )
                st.plotly_chart(fig_promedio, use_container_width=True)
            
            # TAB 3: TABLA DETALLADA
            with tab3:
                st.subheader("Tabla Detallada")
                
                df_detalle = get_datos_detalle_con_porcentaje(ano_seleccionado, mes_seleccionado)
                
                if not df_detalle.empty:
                    df_display = df_detalle.copy()
                    df_display['total_dinero'] = df_display['total_dinero'].apply(lambda x: f"${int(x):,}")
                    df_display['promedio_trabajo'] = df_display['promedio_trabajo'].apply(lambda x: f"${int(x):,}")
                    df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.2f}%")
                    
                    df_display = df_display[['mes_formato', 'categoria', 'cantidad_trabajos', 'total_dinero', 'promedio_trabajo', 'porcentaje']]
                    df_display.columns = ['Mes', 'Categoría', 'Cantidad', 'Total Ingresos', 'Promedio', 'Porcentaje']
                    
                    st.dataframe(df_display, use_container_width=True, height=600)
                    
                    csv = df_detalle.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f'rodenstock_{datetime.now().strftime("%Y%m%d")}.csv',
                        mime='text/csv'
                    )
        else:
            st.warning("⚠️ No hay datos de líneas para los filtros seleccionados")
    else:
        st.warning("⚠️ No hay datos disponibles. Verifica la BD.")
        
except Exception as e:
    st.error(f"❌ Error: {str(e)}")
    st.info("Verifica que la BD 'facturas.db' existe y tiene datos en lineas_factura")

st.markdown("---")
st.caption("Dashboard Rodenstock | SQLite Local | © 2025")