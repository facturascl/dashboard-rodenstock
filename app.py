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
conn = sqlite3.connect('facturas.db')
cursor = conn.cursor()

# ============================================================
# SIDEBAR - FILTROS PRINCIPALES
# ============================================================
st.sidebar.title("🔧 Filtros")

try:
    # Obtener años disponibles
    anos_query = """
        SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano
        FROM facturas WHERE fechaemision IS NOT NULL
        ORDER BY ano DESC
    """
    anos_df = pd.read_sql_query(anos_query, conn)
    anos_disponibles = sorted(anos_df['ano'].tolist(), reverse=True) if not anos_df.empty else [2025]
    
    # Selectores de años para comparar
    ano1 = st.sidebar.selectbox("📅 Año 1", anos_disponibles, index=0, key="ano1")
    ano2 = st.sidebar.selectbox("📅 Año 2 (Comparar)", anos_disponibles, index=min(1, len(anos_disponibles)-1), key="ano2")
    
    # ⭐ DROPDOWN MENSUAL - AQUÍ ESTÁ LA SOLUCIÓN
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
    st.error(f"Error al cargar filtros: {e}")
    st.stop()

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_annual_data(year):
    """Obtiene datos anuales por mes"""
    query = f"""
        SELECT 
            CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
            COUNT(*) as cantidad,
            ROUND(AVG(monto), 2) as promedio,
            ROUND(SUM(monto), 2) as total
        FROM facturas
        WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {year}
        GROUP BY mes
        ORDER BY mes
    """
    return pd.read_sql_query(query, conn)

def get_subcategory_data(year, month, categories=None):
    """Obtiene desglose por subcategoría"""
    where_clause = f"CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {year}"
    where_clause += f" AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {month}"
    
    if categories:
        cat_list = "', '".join(categories)
        where_clause += f" AND lf.clasificacion_categoria IN ('{cat_list}')"
    
    query = f"""
        SELECT 
            lf.clasificacion_subcategoria as subcategoria,
            COUNT(*) as cantidad,
            ROUND(AVG(lf.monto), 2) as promedio,
            ROUND(SUM(lf.monto), 2) as total
        FROM lineas_factura lf
        JOIN facturas f ON lf.id_factura = f.id
        WHERE {where_clause}
        GROUP BY subcategoria
        ORDER BY total DESC
    """
    return pd.read_sql_query(query, conn)

def get_category_analysis(year, month, category):
    """Obtiene análisis por categoría (Newton/Progresivo)"""
    query = f"""
        SELECT 
            lf.clasificacion_categoria,
            COUNT(*) as cantidad,
            ROUND(AVG(lf.monto), 2) as promedio,
            ROUND(SUM(lf.monto), 2) as total
        FROM lineas_factura lf
        JOIN facturas f ON lf.id_factura = f.id
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {year}
            AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {month}
            AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus', 'Progresivo')
        GROUP BY lf.clasificacion_categoria
        ORDER BY total DESC
    """
    return pd.read_sql_query(query, conn)

def get_daily_newton_data(year, month):
    """Obtiene datos diarios de Newton vs Plus"""
    query = f"""
        SELECT 
            CAST(STRFTIME('%d', f.fechaemision) AS INTEGER) as dia,
            lf.clasificacion_categoria,
            COUNT(*) as cantidad,
            ROUND(AVG(lf.monto), 2) as promedio
        FROM lineas_factura lf
        JOIN facturas f ON lf.id_factura = f.id
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {year}
            AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {month}
            AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
        GROUP BY dia, lf.clasificacion_categoria
        ORDER BY dia
    """
    return pd.read_sql_query(query, conn)

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

# ============================================================
# TAB 2: DESGLOSE SUBCATEGORÍAS
# ============================================================
with tab2:
    st.header(f"🏷️ Desglose Subcategorías - Año {ano1}, Mes {meses_nombres[mes_seleccionado-1]}")
    
    data_sub = get_subcategory_data(ano1, mes_seleccionado)
    
    if not data_sub.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                data_sub,
                values='total',
                names='subcategoria',
                title=f"Distribución por Subcategoría ({meses_nombres[mes_seleccionado-1]} {ano1})"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            fig_bar = px.bar(
                data_sub,
                x='subcategoria',
                y=['cantidad', 'promedio'],
                title="Cantidad y Promedio por Subcategoría",
                barmode='group'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.subheader("Detalle de Subcategorías")
        st.dataframe(data_sub, use_container_width=True)
    else:
        st.warning(f"No hay datos para {meses_nombres[mes_seleccionado-1]} de {ano1}")

# ============================================================
# TAB 3: NEWTON VS PLUS (GRÁFICO ÚNICO)
# ============================================================
with tab3:
    st.header(f"📈 Newton vs Newton Plus - {meses_nombres[mes_seleccionado-1]} {ano1}")
    
    newton_data = get_daily_newton_data(ano1, mes_seleccionado)
    
    if not newton_data.empty:
        # Preparar datos para gráfico combinado
        newton_df = newton_data[newton_data['clasificacion_categoria'] == 'Newton'].sort_values('dia')
        plus_df = newton_data[newton_data['clasificacion_categoria'] == 'Newton Plus'].sort_values('dia')
        
        fig = go.Figure()
        
        # Barras para cantidad - Newton
        fig.add_trace(go.Bar(
            x=newton_df['dia'],
            y=newton_df['cantidad'],
            name='Newton - Cantidad',
            marker_color='rgb(55, 83, 109)',
            xaxis='x',
            yaxis='y'
        ))
        
        # Barras para cantidad - Newton Plus
        fig.add_trace(go.Bar(
            x=plus_df['dia'],
            y=plus_df['cantidad'],
            name='Newton Plus - Cantidad',
            marker_color='rgb(26, 118, 255)',
            xaxis='x',
            yaxis='y'
        ))
        
        # Línea para promedio - Newton
        fig.add_trace(go.Scatter(
            x=newton_df['dia'],
            y=newton_df['promedio'],
            name='Newton - Promedio',
            mode='lines+markers',
            line=dict(color='rgb(255, 0, 0)', width=2),
            xaxis='x',
            yaxis='y2'
        ))
        
        # Línea para promedio - Newton Plus
        fig.add_trace(go.Scatter(
            x=plus_df['dia'],
            y=plus_df['promedio'],
            name='Newton Plus - Promedio',
            mode='lines+markers',
            line=dict(color='rgb(50, 171, 96)', width=2),
            xaxis='x',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title=f"Newton vs Newton Plus - {meses_nombres[mes_seleccionado-1]} {ano1}",
            xaxis=dict(title="Día del mes"),
            yaxis=dict(title="Cantidad de facturas", side='left'),
            yaxis2=dict(title="Promedio ($)", overlaying='y', side='right'),
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabla de resumen
        st.subheader("Resumen diario")
        st.dataframe(newton_data.sort_values('dia'), use_container_width=True)
    else:
        st.warning(f"No hay datos de Newton para {meses_nombres[mes_seleccionado-1]} de {ano1}")

# ============================================================
# TAB 4: ANÁLISIS SUBCATEGORÍAS (NEWTON + PROGRESIVO)
# ============================================================
with tab4:
    st.header(f"📍 Análisis Newton + Progresivo - Año {ano1}, Mes {meses_nombres[mes_seleccionado-1]}")
    
    category_data = get_category_analysis(ano1, mes_seleccionado, ['Newton', 'Newton Plus', 'Progresivo'])
    
    if not category_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                category_data,
                values='total',
                names='clasificacion_categoria',
                title=f"Distribución: Newton, Plus y Progresivo"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            fig_bar = px.bar(
                category_data,
                x='clasificacion_categoria',
                y=['cantidad', 'promedio'],
                title="Cantidad y Promedio por Categoría",
                barmode='group',
                color_discrete_sequence=['lightblue', 'salmon']
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.subheader("Detalle por Categoría")
        
        # Mostrar métricas
        for idx, row in category_data.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(f"{row['clasificacion_categoria']} - Cantidad", int(row['cantidad']))
                with col2:
                    st.metric(f"{row['clasificacion_categoria']} - Promedio", f"${row['promedio']:,.2f}")
                with col3:
                    st.metric(f"{row['clasificacion_categoria']} - Total", f"${row['total']:,.2f}")
                with col4:
                    pct = (row['total'] / category_data['total'].sum()) * 100
                    st.metric(f"{row['clasificacion_categoria']} - %", f"{pct:.1f}%")
        
        st.dataframe(category_data, use_container_width=True)
    else:
        st.warning(f"No hay datos de Newton/Progresivo para {meses_nombres[mes_seleccionado-1]} de {ano1}")

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.markdown("---")
st.markdown(f"📅 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
st.markdown("Desarrollado con ❤️ para Rodenstock")
