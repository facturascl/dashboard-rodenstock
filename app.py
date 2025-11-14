import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(page_title="Dashboard Rodenstock", layout="wide")
st.title("📊 Dashboard Rodenstock - Análisis de Facturas")

# ============================================================
# CONEXIÓN A BD
# ============================================================
@st.cache_resource
def get_conn():
    return sqlite3.connect('facturas.db')

conn = get_conn()

# ============================================================
# SIDEBAR - FILTROS PRINCIPALES
# ============================================================
st.sidebar.title("🔧 Filtros")

try:
    # Obtener años disponibles
    anos_query = """
        SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano
        FROM facturas 
        WHERE fechaemision IS NOT NULL
        ORDER BY ano DESC
    """
    anos_df = pd.read_sql_query(anos_query, conn)
    anos_disponibles = sorted(anos_df['ano'].tolist(), reverse=True) if not anos_df.empty else [2025]
    
    # Selectores de años para comparar
    ano1 = st.sidebar.selectbox("📅 Año 1", anos_disponibles, index=0, key="ano1")
    ano2 = st.sidebar.selectbox("📅 Año 2 (Comparar)", anos_disponibles, index=min(1, len(anos_disponibles)-1), key="ano2")
    
    # ⭐ DROPDOWN MENSUAL
    st.sidebar.divider()
    meses_nombres = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                     'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    mes_seleccionado = st.sidebar.selectbox(
        "📅 Filtrar por Mes (Tabs 2 y 4)",
        range(1, 13),
        index=0,
        format_func=lambda x: meses_nombres[x-1]
    )
    
except Exception as e:
    st.error(f"❌ Error al cargar filtros: {e}")
    st.stop()

# ============================================================
# FUNCIONES AUXILIARES - QUERIES CORREGIDAS
# ============================================================

def get_annual_data(year):
    """Obtiene datos anuales por mes"""
    query = f"""
    SELECT 
        CAST(strftime('%m', fechaemision) AS INTEGER) as mes,
        COUNT(*) as cantidad,
        ROUND(AVG(monto), 2) as promedio,
        ROUND(SUM(monto), 2) as total
    FROM facturas
    WHERE strftime('%Y', fechaemision) = '{year}'
    AND fechaemision IS NOT NULL
    AND monto IS NOT NULL
    GROUP BY mes
    ORDER BY mes
    """
    try:
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.warning(f"⚠️ get_annual_data({year}): {str(e)[:100]}")
        return pd.DataFrame()

def get_subcategory_data(year, month):
    """Obtiene desglose por subcategoría"""
    query = f"""
    SELECT 
        COALESCE(lf.clasificacion_subcategoria, 'Sin categoría') as subcategoria,
        COUNT(*) as cantidad,
        ROUND(AVG(CAST(lf.monto AS FLOAT)), 2) as promedio,
        ROUND(SUM(CAST(lf.monto AS FLOAT)), 2) as total
    FROM lineas_factura lf
    JOIN facturas f ON lf.id_factura = f.id
    WHERE strftime('%Y', f.fechaemision) = '{year}'
    AND strftime('%m', f.fechaemision) = PRINTF('%02d', {month})
    AND f.fechaemision IS NOT NULL
    GROUP BY subcategoria
    ORDER BY total DESC
    """
    try:
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error en get_subcategory_data: {e}")
        return pd.DataFrame()

def get_daily_newton_data(year, month):
    """Obtiene datos diarios de Newton vs Plus"""
    query = f"""
    SELECT 
        CAST(strftime('%d', f.fechaemision) AS INTEGER) as dia,
        COALESCE(lf.clasificacion_categoria, 'Otros') as clasificacion_categoria,
        COUNT(*) as cantidad,
        ROUND(AVG(CAST(lf.monto AS FLOAT)), 2) as promedio
    FROM lineas_factura lf
    JOIN facturas f ON lf.id_factura = f.id
    WHERE strftime('%Y', f.fechaemision) = '{year}'
    AND strftime('%m', f.fechaemision) = PRINTF('%02d', {month})
    AND f.fechaemision IS NOT NULL
    GROUP BY dia, clasificacion_categoria
    ORDER BY dia
    """
    try:
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error en get_daily_newton_data: {e}")
        return pd.DataFrame()

def get_category_analysis(year, month):
    """Obtiene análisis por categoría (Newton/Progresivo)"""
    query = f"""
    SELECT 
        COALESCE(lf.clasificacion_categoria, 'Sin categoría') as clasificacion_categoria,
        COUNT(*) as cantidad,
        ROUND(AVG(CAST(lf.monto AS FLOAT)), 2) as promedio,
        ROUND(SUM(CAST(lf.monto AS FLOAT)), 2) as total
    FROM lineas_factura lf
    JOIN facturas f ON lf.id_factura = f.id
    WHERE strftime('%Y', f.fechaemision) = '{year}'
    AND strftime('%m', f.fechaemision) = PRINTF('%02d', {month})
    AND f.fechaemision IS NOT NULL
    GROUP BY clasificacion_categoria
    ORDER BY total DESC
    """
    try:
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error en get_category_analysis: {e}")
        return pd.DataFrame()

# ============================================================
# TABS PRINCIPALES
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Comparativa Anual",
    "🏷️ Desglose Subcategorías",
    "📈 Newton vs Plus",
    "📍 Análisis Subcategorías"
])

# ============================================================
# TAB 1: COMPARATIVA ANUAL
# ============================================================
with tab1:
    st.header(f"📊 Comparativa Anual - {ano1} vs {ano2}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"Año {ano1}")
        data1 = get_annual_data(ano1)
        if not data1.empty:
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(
                x=data1['mes'],
                y=data1['cantidad'],
                name='Cantidad',
                marker_color='lightblue'
            ))
            fig1.update_layout(
                title=f"Facturas por mes - {ano1}",
                xaxis_title="Mes",
                yaxis_title="Cantidad de facturas",
                height=400
            )
            st.plotly_chart(fig1, use_container_width=True)
            st.dataframe(data1, use_container_width=True)
        else:
            st.info(f"Sin datos para {ano1}")
    
    with col2:
        st.subheader(f"Año {ano2}")
        data2 = get_annual_data(ano2)
        if not data2.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=data2['mes'],
                y=data2['cantidad'],
                name='Cantidad',
                marker_color='lightcoral'
            ))
            fig2.update_layout(
                title=f"Facturas por mes - {ano2}",
                xaxis_title="Mes",
                yaxis_title="Cantidad de facturas",
                height=400
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(data2, use_container_width=True)
        else:
            st.info(f"Sin datos para {ano2}")

# ============================================================
# TAB 2: DESGLOSE SUBCATEGORÍAS
# ============================================================
with tab2:
    st.header(f"🏷️ Desglose Subcategorías - {meses_nombres[mes_seleccionado-1]} {ano1}")
    
    data_sub = get_subcategory_data(ano1, mes_seleccionado)
    
    if not data_sub.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                data_sub,
                values='total',
                names='subcategoria',
                title=f"Distribución por Subcategoría"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            fig_bar = px.bar(
                data_sub,
                x='subcategoria',
                y='cantidad',
                title="Cantidad por Subcategoría"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.subheader("Detalle")
        st.dataframe(data_sub, use_container_width=True)
    else:
        st.warning(f"No hay datos para {meses_nombres[mes_seleccionado-1]} de {ano1}")

# ============================================================
# TAB 3: NEWTON VS PLUS
# ============================================================
with tab3:
    st.header(f"📈 Newton vs Newton Plus - {meses_nombres[mes_seleccionado-1]} {ano1}")
    
    newton_data = get_daily_newton_data(ano1, mes_seleccionado)
    
    if not newton_data.empty:
        fig = go.Figure()
        
        # Datos Newton
        newton_df = newton_data[newton_data['clasificacion_categoria'] == 'Newton']
        plus_df = newton_data[newton_data['clasificacion_categoria'] == 'Newton Plus']
        
        # Barras cantidad
        fig.add_trace(go.Bar(
            x=newton_df['dia'],
            y=newton_df['cantidad'],
            name='Newton',
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            x=plus_df['dia'],
            y=plus_df['cantidad'],
            name='Newton Plus',
            marker_color='salmon'
        ))
        
        fig.update_layout(
            title=f"Newton vs Newton Plus",
            xaxis_title="Día",
            yaxis_title="Cantidad",
            barmode='group',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(newton_data.sort_values('dia'), use_container_width=True)
    else:
        st.warning(f"No hay datos de Newton para {meses_nombres[mes_seleccionado-1]} de {ano1}")

# ============================================================
# TAB 4: ANÁLISIS CATEGORÍAS
# ============================================================
with tab4:
    st.header(f"📍 Análisis Newton + Progresivo - {meses_nombres[mes_seleccionado-1]} {ano1}")
    
    cat_data = get_category_analysis(ano1, mes_seleccionado)
    
    if not cat_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                cat_data,
                values='total',
                names='clasificacion_categoria',
                title="Distribución: Newton, Plus y Progresivo"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            fig_bar = px.bar(
                cat_data,
                x='clasificacion_categoria',
                y='cantidad',
                title="Cantidad por Categoría"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.subheader("Detalle por Categoría")
        st.dataframe(cat_data, use_container_width=True)
    else:
        st.warning(f"No hay datos para {meses_nombres[mes_seleccionado-1]} de {ano1}")

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.markdown(f"📅 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
st.markdown("Desarrollado para Rodenstock ✓")
