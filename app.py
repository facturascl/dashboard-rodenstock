#!/usr/bin/env python3

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

st.title("📊 Dashboard Rodenstock - Reportes Profesionales")

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

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Análisis Mensual",
    "🏷️ Por Categoría/Subcategoría",
    "🔄 Newton vs Newton Plus",
    "📊 Gráficos Avanzados"
])

with tab1:
    st.subheader("📊 Evolución Mensual: Facturas y Gastos")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        ano_sel1 = st.selectbox("📅 Año 1", options=anos_list, key="ano1")
    with col2:
        ano_sel2 = st.selectbox("📅 Año 2 (Comparación)", options=["---"] + anos_list, key="ano2")
    with col3:
        mes_sel = st.selectbox("📅 Mes (Opcional)", options=["Todos"] + [f"{i:02d}" for i in range(1, 13)], key="mes_sel")
    
    try:
        conn = get_db_connection()
        
        if mes_sel == "Todos":
            query1 = f"""
            SELECT 
                SUBSTR(f.fechaemision, 1, 7) as mes,
                COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
                SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total_mes
            FROM facturas f
            WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel1}' 
              AND f.fechaemision IS NOT NULL
            GROUP BY mes
            ORDER BY mes
            """
        else:
            query1 = f"""
            SELECT 
                SUBSTR(f.fechaemision, 1, 7) as mes,
                COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
                SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total_mes
            FROM facturas f
            WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel1}' 
              AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel}'
              AND f.fechaemision IS NOT NULL
            GROUP BY mes
            ORDER BY mes
            """
        
        df_mensual1 = pd.read_sql_query(query1, conn)
        
        df_mensual2 = pd.DataFrame()
        if ano_sel2 != "---":
            if mes_sel == "Todos":
                query2 = f"""
                SELECT 
                    SUBSTR(f.fechaemision, 1, 7) as mes,
                    COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
                    SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total_mes
                FROM facturas f
                WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel2}' 
                  AND f.fechaemision IS NOT NULL
                GROUP BY mes
                ORDER BY mes
                """
            else:
                query2 = f"""
                SELECT 
                    SUBSTR(f.fechaemision, 1, 7) as mes,
                    COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
                    SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total_mes
                FROM facturas f
                WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel2}' 
                  AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel}'
                  AND f.fechaemision IS NOT NULL
                GROUP BY mes
                ORDER BY mes
                """
            df_mensual2 = pd.read_sql_query(query2, conn)
        
        conn.close()
        
        if not df_mensual1.empty:
            df_mensual1['promedio'] = df_mensual1['total_mes'] / df_mensual1['cantidad_facturas']
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=df_mensual1['mes'], 
                y=df_mensual1['cantidad_facturas'],
                name=f'Facturas {ano_sel1}',
                marker_color='#667eea',
                yaxis='y1'
            ))
            
            fig.add_trace(go.Scatter(
                x=df_mensual1['mes'],
                y=df_mensual1['total_mes'],
                name=f'Total {ano_sel1} ($)',
                yaxis='y2',
                mode='lines+markers',
                line=dict(color='#51cf66', width=3)
            ))
            
            if not df_mensual2.empty:
                df_mensual2['promedio'] = df_mensual2['total_mes'] / df_mensual2['cantidad_facturas']
                
                fig.add_trace(go.Bar(
                    x=df_mensual2['mes'], 
                    y=df_mensual2['cantidad_facturas'],
                    name=f'Facturas {ano_sel2}',
                    marker_color='#ff8c00',
                    yaxis='y1',
                    opacity=0.7
                ))
                
                fig.add_trace(go.Scatter(
                    x=df_mensual2['mes'],
                    y=df_mensual2['total_mes'],
                    name=f'Total {ano_sel2} ($)',
                    yaxis='y2',
                    mode='lines+markers',
                    line=dict(color='#ff6b6b', width=3, dash='dash')
                ))
            
            titulo = f"Comparación: {ano_sel1}" + (f" vs {ano_sel2}" if ano_sel2 != "---" else "")
            if mes_sel != "Todos":
                titulo += f" - Mes {mes_sel}"
            
            fig.update_layout(
                title=titulo,
                xaxis_title="Mes",
                yaxis_title="Cantidad de Facturas",
                yaxis2=dict(title="Total ($)", overlaying='y', side='right'),
                hovermode='x unified',
                height=500,
                barmode='group'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.write(f"**Detalle {ano_sel1}:**")
            df_display1 = df_mensual1[['mes', 'cantidad_facturas', 'total_mes', 'promedio']].copy()
            df_display1.columns = ['Mes', 'Facturas', 'Total ($)', 'Promedio ($)']
            df_display1['Total ($)'] = df_display1['Total ($)'].apply(lambda x: f"${x:,.2f}")
            df_display1['Promedio ($)'] = df_display1['Promedio ($)'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_display1, use_container_width=True, hide_index=True)
            
            if not df_mensual2.empty:
                st.write(f"**Detalle {ano_sel2}:**")
                df_display2 = df_mensual2[['mes', 'cantidad_facturas', 'total_mes', 'promedio']].copy()
                df_display2.columns = ['Mes', 'Facturas', 'Total ($)', 'Promedio ($)']
                df_display2['Total ($)'] = df_display2['Total ($)'].apply(lambda x: f"${x:,.2f}")
                df_display2['Promedio ($)'] = df_display2['Promedio ($)'].apply(lambda x: f"${x:,.2f}")
                st.dataframe(df_display2, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos para este período")
        
    except Exception as e:
        st.error(f"Error en Tab 1: {str(e)}")

with tab2:
    st.subheader("🏷️ Análisis por Categoría y Subcategoría")
    
    col1, col2 = st.columns(2)
    with col1:
        ano_sel = st.selectbox("📅 Año", options=anos_list, key="ano_tab2")
    with col2:
        mes_sel_tab2 = st.selectbox("📅 Mes", options=["Todos"] + [f"{i:02d}" for i in range(1, 13)], key="mes_tab2")
    
    try:
        conn = get_db_connection()
        
        if mes_sel_tab2 == "Todos":
            query = f"""
            SELECT 
                COALESCE(lf.clasificacion_categoria, 'Sin categoría') as categoria,
                COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
                COUNT(DISTINCT lf.numerofactura) as cantidad_facturas,
                SUM(DISTINCT CASE 
                    WHEN lf.linea_numero = 1 THEN COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)
                    ELSE 0
                END) as total_subcategoria
            FROM lineas_factura lf
            INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
            WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
              AND f.fechaemision IS NOT NULL
            GROUP BY categoria, subcategoria
            ORDER BY total_subcategoria DESC
            """
        else:
            query = f"""
            SELECT 
                COALESCE(lf.clasificacion_categoria, 'Sin categoría') as categoria,
                COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
                COUNT(DISTINCT lf.numerofactura) as cantidad_facturas,
                SUM(DISTINCT CASE 
                    WHEN lf.linea_numero = 1 THEN COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)
                    ELSE 0
                END) as total_subcategoria
            FROM lineas_factura lf
            INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
            WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
              AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel_tab2}'
              AND f.fechaemision IS NOT NULL
            GROUP BY categoria, subcategoria
            ORDER BY total_subcategoria DESC
            """
        
        df_cat = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_cat.empty:
            total_general = df_cat['total_subcategoria'].sum()
            total_trabajos = df_cat['cantidad_facturas'].sum()
            
            df_cat['promedio'] = df_cat['total_subcategoria'] / df_cat['cantidad_facturas']
            df_cat['porcentaje'] = (df_cat['total_subcategoria'] / total_general * 100).round(2)
            
            df_cat['categoria_subcategoria'] = df_cat['categoria'] + ' - ' + df_cat['subcategoria']
            
            fig = px.bar(
                df_cat.sort_values('total_subcategoria', ascending=True),
                x='total_subcategoria',
                y='categoria_subcategoria',
                color='categoria',
                orientation='h',
                title=f"Total por Categoría/Subcategoría ({ano_sel}){' - Mes ' + mes_sel_tab2 if mes_sel_tab2 != 'Todos' else ''}",
                labels={'total_subcategoria': 'Total ($)', 'categoria_subcategoria': 'Categoría - Subcategoría'},
                height=700
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            df_display = df_cat[['categoria', 'subcategoria', 'cantidad_facturas', 'total_subcategoria', 'promedio', 'porcentaje']].copy()
            df_display.columns = ['Categoría', 'Subcategoría', 'Cantidad', 'Total ($)', 'Promedio ($)', '% del Total']
            df_display['Total ($)'] = df_display['Total ($)'].apply(lambda x: f"${x:,.2f}")
            df_display['Promedio ($)'] = df_display['Promedio ($)'].apply(lambda x: f"${x:,.2f}")
            df_display['% del Total'] = df_display['% del Total'].apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Facturas", f"{total_trabajos:,}")
            with col2:
                st.metric("Total General ($)", f"${total_general:,.2f}")
            with col3:
                st.metric("Promedio General ($)", f"${total_general/total_trabajos:,.2f}")
        else:
            st.info("Sin datos para este período")
        
    except Exception as e:
        st.error(f"Error en Tab 2: {str(e)}")

with tab3:
    st.subheader("🔄 Newton vs Newton Plus: Rango de Fechas")
    
    ano_sel = st.selectbox("📅 Año", options=anos_list, key="ano_tab3")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("📅 Fecha Inicio", key="fecha_inicio")
    with col2:
        fecha_fin = st.date_input("📅 Fecha Fin", key="fecha_fin")
    
    fecha_inicio_str = fecha_inicio.strftime("%Y-%m-%d")
    fecha_fin_str = fecha_fin.strftime("%Y-%m-%d")
    
    try:
        conn = get_db_connection()
        
        query = f"""
        SELECT 
            f.fechaemision as fecha,
            CASE 
                WHEN lf.clasificacion_categoria LIKE '%Newton Plus%' THEN 'Newton Plus'
                WHEN lf.clasificacion_categoria LIKE '%Newton%' THEN 'Newton'
                ELSE 'Otro'
            END as categoria_producto,
            COUNT(DISTINCT lf.numerofactura) as cantidad_facturas,
            SUM(DISTINCT CASE 
                WHEN lf.linea_numero = 1 THEN COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)
                ELSE 0
            END) as total_diario
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision >= '{fecha_inicio_str}'
          AND f.fechaemision <= '{fecha_fin_str}'
          AND f.fechaemision IS NOT NULL
        GROUP BY f.fechaemision, categoria_producto
        ORDER BY f.fechaemision DESC
        """
        
        df_newton = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_newton.empty:
            df_newton_filtered = df_newton[df_newton['categoria_producto'].isin(['Newton', 'Newton Plus'])]
            
            if not df_newton_filtered.empty:
                df_newton_filtered['promedio_diario'] = df_newton_filtered['total_diario'] / df_newton_filtered['cantidad_facturas']
                
                df_pivot = df_newton_filtered.pivot_table(
                    index='fecha',
                    columns='categoria_producto',
                    values=['cantidad_facturas', 'promedio_diario'],
                    fill_value=0
                )
                
                fig = go.Figure()
                
                if ('cantidad_facturas', 'Newton') in df_pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_pivot.index,
                        y=df_pivot[('cantidad_facturas', 'Newton')],
                        mode='lines+markers',
                        name='Newton (Cantidad)',
                        line=dict(color='#667eea', width=2),
                        yaxis='y1'
                    ))
                
                if ('cantidad_facturas', 'Newton Plus') in df_pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_pivot.index,
                        y=df_pivot[('cantidad_facturas', 'Newton Plus')],
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
                    title=f"Newton vs Newton Plus: {fecha_inicio_str} a {fecha_fin_str}",
                    xaxis_title="Fecha",
                    yaxis=dict(title="Cantidad", side='left'),
                    yaxis2=dict(title="Promedio ($)", overlaying='y', side='right'),
                    hovermode='x unified',
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                summary = df_newton_filtered.groupby('categoria_producto').agg({
                    'cantidad_facturas': 'sum',
                    'total_diario': 'sum'
                }).reset_index()
                
                summary['promedio_general'] = summary['total_diario'] / summary['cantidad_facturas']
                summary.columns = ['Categoría', 'Total Trabajos', 'Total ($)', 'Promedio General ($)']
                summary['Total ($)'] = summary['Total ($)'].apply(lambda x: f"${x:,.2f}")
                summary['Promedio General ($)'] = summary['Promedio General ($)'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(summary, use_container_width=True, hide_index=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    newton_data = df_newton_filtered[df_newton_filtered['categoria_producto'] == 'Newton']
                    if not newton_data.empty:
                        total_newton = newton_data['total_diario'].sum()
                        cant_newton = newton_data['cantidad_facturas'].sum()
                        promedio_newton = total_newton / cant_newton
                        st.metric(
                            "Newton - Trabajos",
                            f"{int(cant_newton):,}",
                            f"Total: ${total_newton:,.2f} | Promedio: ${promedio_newton:,.2f}"
                        )
                
                with col2:
                    newton_plus_data = df_newton_filtered[df_newton_filtered['categoria_producto'] == 'Newton Plus']
                    if not newton_plus_data.empty:
                        total_plus = newton_plus_data['total_diario'].sum()
                        cant_plus = newton_plus_data['cantidad_facturas'].sum()
                        promedio_plus = total_plus / cant_plus
                        st.metric(
                            "Newton Plus - Trabajos",
                            f"{int(cant_plus):,}",
                            f"Total: ${total_plus:,.2f} | Promedio: ${promedio_plus:,.2f}"
                        )
            else:
                st.info("Sin datos de Newton o Newton Plus para este rango")
        else:
            st.info("Sin datos para este rango")
        
    except Exception as e:
        st.error(f"Error en Tab 3: {str(e)}")

with tab4:
    st.subheader("📊 Gráficos Avanzados de Análisis")
    
    ano_sel = st.selectbox("📅 Año", options=anos_list, key="ano_tab4")
    
    try:
        conn = get_db_connection()
        
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
        GROUP BY rango
        ORDER BY cantidad DESC
        """
        
        df_rangos = pd.read_sql_query(query_rangos, conn)
        
        if not df_rangos.empty:
            fig_rangos = go.Figure(data=[
                go.Pie(
                    labels=df_rangos['rango'],
                    values=df_rangos['cantidad'],
                    title='Distribución de Facturas por Rango de Monto',
                    hovertemplate='<b>%{label}</b><br>Cantidad: %{value}<extra></extra>'
                )
            ])
            st.plotly_chart(fig_rangos, use_container_width=True)
        
        st.write("### 📈 Tendencia Diaria de Facturación")
        query_diario = f"""
        SELECT 
            f.fechaemision as fecha,
            COUNT(DISTINCT f.numerofactura) as cantidad,
            SUM(COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)) as total
        FROM facturas f
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
        GROUP BY fecha
        ORDER BY fecha
        """
        
        df_diario = pd.read_sql_query(query_diario, conn)
        
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
        
        st.write("### 🏆 Top 10 Subcategorías")
        query_top_sub = f"""
        SELECT 
            COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
            COUNT(DISTINCT lf.numerofactura) as cantidad,
            SUM(DISTINCT CASE 
                WHEN lf.linea_numero = 1 THEN COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0)
                ELSE 0
            END) as total
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' 
          AND f.fechaemision IS NOT NULL
        GROUP BY subcategoria
        ORDER BY total DESC
        LIMIT 10
        """
        
        df_top_sub = pd.read_sql_query(query_top_sub, conn)
        conn.close()
        
        if not df_top_sub.empty:
            fig_top = px.bar(
                df_top_sub,
                x='total',
                y='subcategoria',
                orientation='h',
                title='Top 10 Subcategorías por Monto Total',
                labels={'total': 'Total ($)', 'subcategoria': 'Subcategoría'},
                color='total',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_top, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error en Tab 4: {str(e)}")

st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
