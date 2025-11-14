#!/usr/bin/env python3
"""
Dashboard de Facturación Rodenstock - PROFESIONAL CORREGIDO
Totales consistentes: 1 factura = 1 trabajo
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
import os
from datetime import datetime

st.set_page_config(
    page_title="Dashboard Rodenstock Pro",
    page_icon="📊",
    layout="wide"
)

# ========== BD ==========
def find_database():
    possible_paths = ['facturas.db', '/app/facturas.db', '/mount/src/dashboard-rodenstock/facturas.db']
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

DB_FILE = find_database()

def get_db_connection():
    if DB_FILE is None:
        st.error("❌ Base de datos no encontrada")
        st.stop()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

# ========== ENCABEZADO ==========
st.title("📊 Dashboard Rodenstock - Reportes Profesionales")

# ========== SIDEBAR - FILTROS ==========
st.sidebar.header("⚙️ Filtros")

try:
    conn = get_db_connection()
    query_anos = """
    SELECT DISTINCT SUBSTR(fechaemision, 1, 4) AS ano 
    FROM facturas 
    WHERE fechaemision IS NOT NULL 
    ORDER BY ano DESC
    """
    df_anos = pd.read_sql_query(query_anos, conn)
    conn.close()
    
    anos_list = sorted(df_anos['ano'].tolist(), reverse=True) if not df_anos.empty else ["2025"]
except Exception as e:
    st.sidebar.error(f"Error cargando años: {str(e)}")
    anos_list = ["2025"]

ano_sel = st.sidebar.selectbox("📅 Año", options=anos_list)

# Cargar meses disponibles según el año
try:
    conn = get_db_connection()
    query_meses = f"""
    SELECT DISTINCT SUBSTR(fechaemision, 1, 7) AS mes 
    FROM facturas 
    WHERE SUBSTR(fechaemision, 1, 4) = '{ano_sel}' 
      AND fechaemision IS NOT NULL 
    ORDER BY mes DESC
    """
    df_meses = pd.read_sql_query(query_meses, conn)
    conn.close()
    
    meses_list = df_meses['mes'].tolist() if not df_meses.empty else []
    mes_sel = st.sidebar.selectbox("📆 Mes (Opcional)", options=["Todos"] + meses_list)
except Exception as e:
    st.sidebar.error(f"Error cargando meses: {str(e)}")
    mes_sel = "Todos"

# ========== TABS PRINCIPALES ==========
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Análisis Mensual",
    "🏷️ Por Categoría/Subcategoría",
    "🔄 Newton vs Newton Plus",
    "📊 Gráficos Avanzados"
])

# ==================== TAB 1: ANÁLISIS MENSUAL ====================
with tab1:
    st.subheader("📊 Evolución Mensual: Documentos y Gastos")
    
    try:
        conn = get_db_connection()
        
        query = f"""
        SELECT 
            SUBSTR(f.fechaemision, 1, 7) as mes,
            COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total_mes
        FROM facturas f
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
        GROUP BY mes
        ORDER BY mes
        """
        
        df_mensual = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_mensual.empty:
            df_mensual['promedio'] = df_mensual['total_mes'] / df_mensual['cantidad_facturas']
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=df_mensual['mes'], 
                y=df_mensual['cantidad_facturas'],
                name='Facturas',
                marker_color='#667eea'
            ))
            
            fig.add_trace(go.Scatter(
                x=df_mensual['mes'],
                y=df_mensual['total_mes'],
                name='Total ($)',
                yaxis='y2',
                mode='lines+markers',
                line=dict(color='#51cf66', width=3)
            ))
            
            fig.update_layout(
                title="Evolución de Facturas y Gastos Mensuales",
                xaxis_title="Mes",
                yaxis_title="Cantidad de Facturas",
                yaxis2=dict(title="Total ($)", overlaying='y', side='right'),
                hovermode='x unified',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            df_display = df_mensual[['mes', 'cantidad_facturas', 'total_mes', 'promedio']].copy()
            df_display.columns = ['Mes', 'Facturas', 'Total ($)', 'Promedio ($)']
            df_display['Total ($)'] = df_display['Total ($)'].apply(lambda x: f"${x:,.2f}")
            df_display['Promedio ($)'] = df_display['Promedio ($)'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos para este año")
        
    except Exception as e:
        st.error(f"Error en Tab 1: {str(e)}")

# ==================== TAB 2: POR CATEGORÍA/SUBCATEGORÍA ====================
with tab2:
    st.subheader("🏷️ Análisis por Categoría y Subcategoría")
    
    try:
        conn = get_db_connection()
        
        where_mes = f"AND SUBSTR(f.fechaemision, 1, 7) = '{mes_sel}'" if mes_sel != "Todos" else ""
        
        # CORRECCIÓN: Solo traer FACTURAS ÚNICAS con sus categorías (SIN contar líneas múltiples)
        query = f"""
        SELECT 
            COALESCE(lf.clasificacion_categoria, 'Sin categoría') as categoria,
            COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
            COUNT(DISTINCT f.numerofactura) as cantidad_trabajos,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total_subcategoria
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
          {where_mes}
        GROUP BY categoria, subcategoria
        ORDER BY total_subcategoria DESC
        """
        
        df_cat = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_cat.empty:
            total_general = df_cat['total_subcategoria'].sum()
            total_trabajos = df_cat['cantidad_trabajos'].sum()
            
            df_cat['promedio'] = df_cat['total_subcategoria'] / df_cat['cantidad_trabajos']
            df_cat['porcentaje'] = (df_cat['total_subcategoria'] / total_general * 100).round(2)
            
            fig = px.bar(
                df_cat.sort_values('total_subcategoria', ascending=True),
                x='total_subcategoria',
                y='subcategoria',
                color='categoria',
                orientation='h',
                title=f"Total por Subcategoría ({mes_sel})",
                labels={'total_subcategoria': 'Total ($)', 'subcategoria': 'Subcategoría'},
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            df_display = df_cat[['categoria', 'subcategoria', 'cantidad_trabajos', 'total_subcategoria', 'promedio', 'porcentaje']].copy()
            df_display.columns = ['Categoría', 'Subcategoría', 'Cantidad', 'Total ($)', 'Promedio ($)', '% del Total']
            df_display['Total ($)'] = df_display['Total ($)'].apply(lambda x: f"${x:,.2f}")
            df_display['Promedio ($)'] = df_display['Promedio ($)'].apply(lambda x: f"${x:,.2f}")
            df_display['% del Total'] = df_display['% del Total'].apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Trabajos", f"{total_trabajos:,}")
            with col2:
                st.metric("Total General ($)", f"${total_general:,.2f}")
            with col3:
                st.metric("Promedio General ($)", f"${total_general/total_trabajos:,.2f}")
        else:
            st.info("Sin datos para este período")
        
    except Exception as e:
        st.error(f"Error en Tab 2: {str(e)}")

# ==================== TAB 3: NEWTON vs NEWTON PLUS ====================
with tab3:
    st.subheader("🔄 Resumen Diario: Newton vs Newton Plus")
    
    try:
        conn = get_db_connection()
        
        # CORRECCIÓN: Usar FACTURAS ÚNICAS (no líneas)
        query = f"""
        SELECT 
            f.fechaemision as fecha,
            CASE 
                WHEN lf.clasificacion_categoria LIKE '%Newton Plus%' THEN 'Newton Plus'
                WHEN lf.clasificacion_categoria LIKE '%Newton%' THEN 'Newton'
                ELSE 'Otro'
            END as categoria_producto,
            COUNT(DISTINCT f.numerofactura) as cantidad_trabajos,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
        GROUP BY fecha, categoria_producto
        ORDER BY fecha DESC
        """
        
        df_newton = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_newton.empty:
            df_newton_filtered = df_newton[df_newton['categoria_producto'].isin(['Newton', 'Newton Plus'])]
            
            if not df_newton_filtered.empty:
                # Calcular promedio por día
                df_newton_filtered['promedio_diario'] = df_newton_filtered['total'] / df_newton_filtered['cantidad_trabajos']
                
                df_pivot = df_newton_filtered.pivot_table(
                    index='fecha',
                    columns='categoria_producto',
                    values=['cantidad_trabajos', 'promedio_diario'],
                    fill_value=0
                )
                
                fig = go.Figure()
                
                if ('cantidad_trabajos', 'Newton') in df_pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_pivot.index,
                        y=df_pivot[('cantidad_trabajos', 'Newton')],
                        mode='lines+markers',
                        name='Newton (Cantidad)',
                        line=dict(color='#667eea', width=2),
                        yaxis='y1'
                    ))
                
                if ('cantidad_trabajos', 'Newton Plus') in df_pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_pivot.index,
                        y=df_pivot[('cantidad_trabajos', 'Newton Plus')],
                        mode='lines+markers',
                        name='Newton Plus (Cantidad)',
                        line=dict(color='#51cf66', width=2),
                        yaxis='y1'
                    ))
                
                if ('promedio_diario', 'Newton') in df_pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_pivot.index,
                        y=df_pivot[('promedio_diario', 'Newton')],
                        mode='lines+markers',
                        name='Newton (Promedio $)',
                        line=dict(color='#667eea', width=2, dash='dash'),
                        yaxis='y2'
                    ))
                
                if ('promedio_diario', 'Newton Plus') in df_pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_pivot.index,
                        y=df_pivot[('promedio_diario', 'Newton Plus')],
                        mode='lines+markers',
                        name='Newton Plus (Promedio $)',
                        line=dict(color='#51cf66', width=2, dash='dash'),
                        yaxis='y2'
                    ))
                
                fig.update_layout(
                    title="Newton vs Newton Plus: Cantidad y Promedio Diario",
                    xaxis_title="Fecha",
                    yaxis=dict(title="Cantidad", side='left'),
                    yaxis2=dict(title="Promedio ($)", overlaying='y', side='right'),
                    hovermode='x unified',
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Resumen general
                summary = df_newton_filtered.groupby('categoria_producto').agg({
                    'cantidad_trabajos': 'sum',
                    'total': 'sum'
                }).reset_index()
                
                summary['promedio_general'] = summary['total'] / summary['cantidad_trabajos']
                summary.columns = ['Categoría', 'Total Trabajos', 'Total ($)', 'Promedio General ($)']
                summary['Total ($)'] = summary['Total ($)'].apply(lambda x: f"${x:,.2f}")
                summary['Promedio General ($)'] = summary['Promedio General ($)'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(summary, use_container_width=True, hide_index=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    newton_data = df_newton_filtered[df_newton_filtered['categoria_producto'] == 'Newton']
                    if not newton_data.empty:
                        promedio_newton = newton_data['total'].sum() / newton_data['cantidad_trabajos'].sum()
                        st.metric(
                            "Newton - Trabajos",
                            f"{int(newton_data['cantidad_trabajos'].sum()):,}",
                            f"Promedio: ${promedio_newton:,.2f}"
                        )
                
                with col2:
                    newton_plus_data = df_newton_filtered[df_newton_filtered['categoria_producto'] == 'Newton Plus']
                    if not newton_plus_data.empty:
                        promedio_plus = newton_plus_data['total'].sum() / newton_plus_data['cantidad_trabajos'].sum()
                        st.metric(
                            "Newton Plus - Trabajos",
                            f"{int(newton_plus_data['cantidad_trabajos'].sum()):,}",
                            f"Promedio: ${promedio_plus:,.2f}"
                        )
            else:
                st.info("Sin datos de Newton o Newton Plus para este año")
        else:
            st.info("Sin datos para este año")
        
    except Exception as e:
        st.error(f"Error en Tab 3: {str(e)}")

# ==================== TAB 4: GRÁFICOS AVANZADOS ====================
with tab4:
    st.subheader("📊 Gráficos Avanzados de Análisis")
    
    try:
        conn = get_db_connection()
        
        where_mes = f"AND SUBSTR(f.fechaemision, 1, 7) = '{mes_sel}'" if mes_sel != "Todos" else ""
        
        # Gráfico 1: Top 10 Clientes (por total)
        st.write("### 🏆 Top 10 Clientes por Monto Total")
        query_top_clientes = f"""
        SELECT 
            COALESCE(f.empresa_cliente, 'Sin empresa') as cliente,
            COUNT(DISTINCT f.numerofactura) as cantidad,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total
        FROM facturas f
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
          {where_mes}
        GROUP BY cliente
        ORDER BY total DESC
        LIMIT 10
        """
        
        df_top_clientes = pd.read_sql_query(query_top_clientes, conn)
        
        if not df_top_clientes.empty:
            fig_clientes = px.bar(
                df_top_clientes,
                x='total',
                y='cliente',
                orientation='h',
                title='Top 10 Clientes',
                labels={'total': 'Total ($)', 'cliente': 'Cliente'},
                color='total',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig_clientes, use_container_width=True)
        
        # Gráfico 2: Distribución por rango de montos
        st.write("### 📊 Distribución por Rango de Montos")
        query_rangos = f"""
        SELECT 
            CASE 
                WHEN (COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) < 100000 THEN 'Menor a 100K'
                WHEN (COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) < 500000 THEN '100K - 500K'
                WHEN (COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) < 1000000 THEN '500K - 1M'
                ELSE 'Mayor a 1M'
            END as rango,
            COUNT(DISTINCT f.numerofactura) as cantidad,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total
        FROM facturas f
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
          {where_mes}
        GROUP BY rango
        ORDER BY cantidad DESC
        """
        
        df_rangos = pd.read_sql_query(query_rangos, conn)
        
        if not df_rangos.empty:
            fig_rangos = go.Figure(data=[
                go.Pie(
                    labels=df_rangos['rango'],
                    values=df_rangos['cantidad'],
                    title='Distribución de Facturas por Rango de Monto'
                )
            ])
            st.plotly_chart(fig_rangos, use_container_width=True)
        
        # Gráfico 3: Tendencia de facturación por día
        st.write("### 📈 Tendencia Diaria de Facturación")
        query_diario = f"""
        SELECT 
            f.fechaemision as fecha,
            COUNT(DISTINCT f.numerofactura) as cantidad,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total
        FROM facturas f
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
          {where_mes}
        GROUP BY fecha
        ORDER BY fecha
        """
        
        df_diario = pd.read_sql_query(query_diario, conn)
        conn.close()
        
        if not df_diario.empty:
            fig_diario = go.Figure()
            
            fig_diario.add_trace(go.Bar(
                x=df_diario['fecha'],
                y=df_diario['cantidad'],
                name='Cantidad',
                marker_color='#667eea',
                yaxis='y1'
            ))
            
            fig_diario.add_trace(go.Scatter(
                x=df_diario['fecha'],
                y=df_diario['total'],
                name='Total ($)',
                line=dict(color='#51cf66', width=2),
                yaxis='y2'
            ))
            
            fig_diario.update_layout(
                title='Tendencia Diaria de Facturación',
                xaxis_title='Fecha',
                yaxis=dict(title='Cantidad'),
                yaxis2=dict(title='Total ($)', overlaying='y', side='right'),
                hovermode='x unified',
                height=500
            )
            
            st.plotly_chart(fig_diario, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error en Tab 4: {str(e)}")

# ========== FOOTER ==========
st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
```

