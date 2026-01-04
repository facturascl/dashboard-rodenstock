import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Dashboard Rodenstock", page_icon="📊", layout="wide")

DB_PATH = "facturas.db"

@st.cache_resource
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
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
    
    # Selector de año actual
    ano_actual = st.sidebar.selectbox("📅 Año Actual", anos_disponibles, index=0, key="ano_actual")
    
except Exception as e:
    st.error(f"Error al cargar años: {e}")
    st.stop()

# ============================================================
# FUNCIONES DE CONSULTA
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
def get_newton_rango(fecha_inicio, fecha_fin):
    """Newton vs Newton Plus con rango de fechas."""
    query = f"""
    WITH newton_data AS (
      SELECT
        STRFTIME('%Y-%m-%d', f.fechaemision) as fecha,
        CASE 
          WHEN lf.clasificacion_categoria = 'Newton' THEN 'Newton' 
          WHEN lf.clasificacion_categoria = 'Newton Plus' THEN 'Newton Plus'
          ELSE 'Otro'
        END as tipo,
        f.numerofactura,
        COALESCE(f.subtotal, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM lineas_factura lf
      INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
      WHERE f.fechaemision BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
      AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
      AND f.fechaemision IS NOT NULL
    )
    SELECT
      fecha,
      tipo,
      COUNT(DISTINCT numerofactura) as cantidad,
      CAST(SUM(total_factura) AS INTEGER) as total_diario,
      CAST(AVG(total_factura) AS INTEGER) as promedio_diario
    FROM newton_data
    GROUP BY fecha, tipo
    ORDER BY fecha DESC, tipo
    """
    return pd.read_sql_query(query, conn)

# ============================================================
# TABS PRINCIPALES
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "📊 Comparativa Anual",
    "🏷️ Desglose Subcategorías",
    "📈 Newton vs Plus"
])

# ============================================================
# TAB 1: COMPARATIVA ANUAL (12 MESES)
# ============================================================
with tab1:
    st.header("📊 Comparativa de Años")
    
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
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
    # Línea de promedio mensual por factura
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
            name='Promedio Mensual por Factura ($)',
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
                name='Promedio Mensual por Factura ($)',
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
        
        # Crear DataFrame para visualización
        df_subcat_vis = df_subcat.copy()
        df_subcat_vis['label_completo'] = df_subcat_vis['categoria'] + ' - ' + df_subcat_vis['subcategoria']
        
        # Dos columnas para los gráficos lado a lado
        col_donut, col_sunburst = st.columns(2)
        
        with col_donut:
            st.markdown("#### Gráfico Circular (Donut)")
            
            # Colores personalizados por categoría
            colors = px.colors.qualitative.Set3
            
            # Calcular porcentajes manualmente para consistencia
            total_mes = df_subcat_vis['costo'].sum()
            df_subcat_vis['pct_calculado'] = (df_subcat_vis['costo'] / total_mes * 100).round(2)
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=df_subcat_vis['label_completo'],
                values=df_subcat_vis['costo'],
                hole=0.45,
                textposition='outside',
                texttemplate='<b>%{label}</b><br>%{customdata:.1f}%',
                customdata=df_subcat_vis['pct_calculado'],
                hovertemplate='<b>%{label}</b><br>' +
                              'Total: $%{value:,.0f}<br>' +
                              'Porcentaje: %{customdata:.2f}%<br>' +
                              '<extra></extra>',
                marker=dict(
                    colors=colors,
                    line=dict(color='white', width=3)
                ),
                pull=[0.03] * len(df_subcat_vis),
                rotation=45
            )])
            
            fig_donut.update_layout(
                showlegend=False,
                height=550,
                annotations=[dict(
                    text=f'<b>Total</b><br>${total_mes:,.0f}',
                    x=0.5, y=0.5,
                    font=dict(size=16, color='#333'),
                    showarrow=False
                )],
                title=dict(
                    text=f'{meses_nombres[mes_tab2-1]} {ano_actual}',
                    x=0.5,
                    xanchor='center',
                    font=dict(size=14, color='#333')
                ),
                margin=dict(l=10, r=10, t=60, b=10)
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        
        with col_sunburst:
            st.markdown("#### Vista Jerárquica (Sunburst)")
            
            fig_sunburst = px.sunburst(
                df_subcat_vis,
                path=['categoria', 'subcategoria'],
                values='costo',
                color='costo',
                color_continuous_scale='Viridis'
            )
            
            # Preparar customdata con toda la info
            customdata_list = []
            for _, row in df_subcat_vis.iterrows():
                customdata_list.append([row['cantidad'], row['promedio'], row['pct_calculado']])
            
            fig_sunburst.update_traces(
                textinfo='label+percent parent',
                customdata=customdata_list,
                hovertemplate='<b>%{label}</b><br>' +
                             'Total: $%{value:,.0f}<br>' +
                             'Cantidad: %{customdata[0]}<br>' +
                             'Promedio: $%{customdata[1]:,.0f}<br>' +
                             'Del total mes: %{customdata[2]:.2f}%<br>' +
                             'De su categoría: %{percentParent}<br>' +
                             '<extra></extra>',
                marker=dict(line=dict(color='white', width=2))
            )
            
            fig_sunburst.update_layout(
                height=550,
                title=dict(
                    text='Categorías → Subcategorías',
                    x=0.5,
                    xanchor='center',
                    font=dict(size=14, color='#333')
                ),
                margin=dict(l=10, r=10, t=60, b=10)
            )
            
            st.plotly_chart(fig_sunburst, use_container_width=True)
        
        # Explicación clara de los porcentajes
        st.info("""
        📊 **Explicación de porcentajes:**
        
        **Gráfico Donut (izquierda):** Muestra el porcentaje que representa cada subcategoría del total del mes completo.
        
        **Gráfico Sunburst (derecha):** 
        - **Círculo interno (categorías):** % respecto al total del mes
        - **Círculo externo (subcategorías):** % respecto a su categoría padre
        - En el tooltip se muestran ambos: "Del total mes" y "De su categoría"
        
        Por ejemplo: "Monofocales - Hi-index Verde" puede ser 20% del total del mes, pero 35% dentro de la categoría Monofocales.
        """)
    else:
        st.info("ℹ️ Sin datos de subcategorías")

# ============================================================
# TAB 3: NEWTON VS NEWTON PLUS
# ============================================================
with tab3:
    st.header("📈 Newton vs Newton Plus")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input(
            "📅 Fecha Inicio",
            value=pd.to_datetime(f"{ano_actual}-01-01"),
            key="newton_inicio"
        )
    with col2:
        fecha_fin = st.date_input(
            "📅 Fecha Fin",
            value=pd.to_datetime(f"{ano_actual}-12-31"),
            key="newton_fin"
        )
    
    df_newton = get_newton_rango(
        fecha_inicio.strftime('%Y-%m-%d'),
        fecha_fin.strftime('%Y-%m-%d')
    )
    
    if not df_newton.empty:
        df_newton_pivot_cant = df_newton.pivot_table(
            index='fecha', columns='tipo', values='cantidad',
            aggfunc='sum', fill_value=0
        )
        df_newton_pivot_prom = df_newton.pivot_table(
            index='fecha', columns='tipo', values='promedio_diario',
            aggfunc='first', fill_value=0
        )
        
        fig = go.Figure()
        
        # Barras para cantidad
        for col in df_newton_pivot_cant.columns:
            fig.add_trace(go.Bar(
                x=df_newton_pivot_cant.index,
                y=df_newton_pivot_cant[col],
                name=f"{col} (Cantidad)",
                yaxis='y1',
                opacity=0.7,
                hovertemplate='<b>%{x}</b><br>' + col +
                              ' Cantidad: %{y:,.0f}<extra></extra>'
            ))
        
        # Líneas para promedio diario
        for col in df_newton_pivot_prom.columns:
            fig.add_trace(go.Scatter(
                x=df_newton_pivot_prom.index,
                y=df_newton_pivot_prom[col],
                name=f"{col} (Promedio Diario)",
                yaxis='y2',
                mode='lines+markers',
                line=dict(width=2),
                hovertemplate='<b>%{x}</b><br>' + col +
                              ' Promedio Diario: $%{y:,.0f}<extra></extra>'
            ))
        
        fig.update_layout(
            xaxis_title="Fecha",
            yaxis=dict(title="Cantidad", side='left'),
            yaxis2=dict(title="Promedio Diario ($)", overlaying='y', side='right'),
            hovermode='x unified',
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Sin datos Newton/Newton Plus en este rango")

# ============================================================
# PIE DE PÁGINA
# ============================================================
st.divider()
st.caption(
    f"✅ Dashboard Ben&Frank | Rodenstock | Cristián Ibañez | "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M')} | Año {ano_actual}"
)
