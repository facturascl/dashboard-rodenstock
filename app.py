import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
    """Comparativa de 12 meses: cantidad de facturas + línea de dinero"""
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
    """Todas las subcategorías por mes: cantidad, costo, promedio, porcentaje - CORREGIDO"""
    query = f"""
    WITH fact_consolidadas AS (
        SELECT 
            lf.clasificacion_categoria,
            lf.clasificacion_subcategoria,
            f.numerofactura,
            (f.subtotal + f.iva) as monto_total
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano)}
        AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {int(mes)}
        AND f.fechaemision IS NOT NULL
        GROUP BY f.numerofactura, lf.clasificacion_categoria, lf.clasificacion_subcategoria
    ),
    stats_totales AS (
        SELECT CAST(SUM(monto_total) AS INTEGER) as total_general
        FROM fact_consolidadas
    )
    SELECT 
        COALESCE(clasificacion_categoria, 'Sin categoría') as categoria,
        COALESCE(clasificacion_subcategoria, 'Sin clasificación') as subcategoria,
        COUNT(*) as cantidad,
        CAST(SUM(monto_total) AS INTEGER) as costo,
        CAST(SUM(monto_total) / NULLIF(COUNT(*), 0) AS INTEGER) as promedio,
        CAST(100.0 * SUM(monto_total) / NULLIF((SELECT total_general FROM stats_totales), 0) AS DECIMAL(5,2)) as pct
    FROM fact_consolidadas
    GROUP BY categoria, subcategoria
    ORDER BY costo DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_analisis_subcategorias_mes(ano, mes):
    """Análisis COMPLETO por subcategoría - por mes - CORREGIDO"""
    query = f"""
    WITH fact_consolidadas AS (
        SELECT 
            lf.clasificacion_categoria,
            lf.clasificacion_subcategoria,
            f.numerofactura,
            (f.subtotal + f.iva) as monto_total
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano)}
        AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {int(mes)}
        AND f.fechaemision IS NOT NULL
        GROUP BY f.numerofactura, lf.clasificacion_categoria, lf.clasificacion_subcategoria
    ),
    stats_totales AS (
        SELECT CAST(SUM(monto_total) AS INTEGER) as total_general
        FROM fact_consolidadas
    )
    SELECT 
        COALESCE(clasificacion_categoria, 'Sin categoría') as categoria,
        COALESCE(clasificacion_subcategoria, 'Sin clasificación') as subcategoria,
        COUNT(*) as cantidad,
        CAST(SUM(monto_total) AS INTEGER) as total,
        CAST(SUM(monto_total) / NULLIF(COUNT(*), 0) AS INTEGER) as promedio,
        CAST(100.0 * SUM(monto_total) / NULLIF((SELECT total_general FROM stats_totales), 0) AS DECIMAL(5,2)) as pct
    FROM fact_consolidadas
    GROUP BY categoria, subcategoria
    ORDER BY total DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_newton_rango(fecha_inicio, fecha_fin):
    """Newton vs Newton Plus con rango de fechas: cantidad diaria y promedio diario"""
    query = f"""
    SELECT 
        STRFTIME('%Y-%m-%d', f.fechaemision) as fecha,
        CASE WHEN lf.clasificacion_categoria = 'Newton' THEN 'Newton' ELSE 'Newton Plus' END as tipo,
        COUNT(DISTINCT f.numerofactura) as cantidad,
        CAST(SUM(f.subtotal + f.iva) / NULLIF(COUNT(DISTINCT f.numerofactura), 0) AS INTEGER) as promedio_diario
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE f.fechaemision BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
    AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
    AND f.fechaemision IS NOT NULL
    GROUP BY fecha, tipo
    ORDER BY fecha DESC, tipo
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
# TAB 1: COMPARATIVA ANUAL (12 MESES) - REORGANIZADO
# ============================================================
with tab1:
    st.header(f"📊 Comparativa de Años")
    
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    # PARTE 1: AÑO ACTUAL (ARRIBA, COMPLETO)
    st.subheader(f"📅 Año {ano_actual} - Vista Actual")
    
    df_comp_actual = get_comparativa_12_meses(ano_actual)
    df_comp_actual_full = pd.DataFrame({'mes': range(1, 13)})
    df_comp_actual_full = df_comp_actual_full.merge(df_comp_actual, on='mes', how='left').fillna(0)
    df_comp_actual_full['cantidad_facturas'] = df_comp_actual_full['cantidad_facturas'].astype(int)
    df_comp_actual_full['total_dinero'] = df_comp_actual_full['total_dinero'].astype(int)
    df_comp_actual_full['promedio'] = (df_comp_actual_full['total_dinero'] / df_comp_actual_full['cantidad_facturas'].replace(0, 1)).fillna(0).astype(int)
    
    fig_actual = go.Figure()
    fig_actual.add_trace(go.Bar(
        x=[meses_nombres[i-1] for i in df_comp_actual_full['mes']],
        y=df_comp_actual_full['cantidad_facturas'],
        name='Cantidad de Facturas',
        yaxis='y1',
        marker=dict(color='rgba(0, 118, 168, 0.7)')
    ))
    fig_actual.add_trace(go.Scatter(
        x=[meses_nombres[i-1] for i in df_comp_actual_full['mes']],
        y=df_comp_actual_full['total_dinero'],
        name='Total en Dinero ($)',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#FF6B6B', width=3),
        marker=dict(size=10)
    ))
    fig_actual.update_layout(
        xaxis_title="Mes",
        yaxis=dict(title="Cantidad de Facturas", side='left'),
        yaxis2=dict(title="Total ($)", overlaying='y', side='right'),
        hovermode='x unified',
        height=400,
        showlegend=True
    )
    st.plotly_chart(fig_actual, use_container_width=True)
    
    tabla_actual = df_comp_actual_full.copy()
    tabla_actual['mes_nombre'] = [meses_nombres[i-1] for i in tabla_actual['mes']]
    st.dataframe(
        tabla_actual[['mes_nombre', 'cantidad_facturas', 'total_dinero', 'promedio']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "mes_nombre": st.column_config.TextColumn("Mes", width=80),
            "cantidad_facturas": st.column_config.NumberColumn("Facturas", width=100),
            "total_dinero": st.column_config.NumberColumn("Total ($)", width=130, format="$%d"),
            "promedio": st.column_config.NumberColumn("Promedio/Factura ($)", width=150, format="$%d"),
        }
    )
    
    # PARTE 2: COMPARATIVA (ABAJO, LADO A LADO)
    st.divider()
    st.subheader("🔄 Comparativa entre Años (Lado a Lado)")
    
    col_ano1, col_ano2 = st.columns(2)
    with col_ano1:
        ano_comp1 = st.selectbox("📅 Año 1", anos_disponibles, index=0, key="ano_comp1")
    with col_ano2:
        ano_comp2 = st.selectbox("📅 Año 2", anos_disponibles, index=min(1, len(anos_disponibles)-1), key="ano_comp2")
    
    # Obtener datos de ambos años
    df_comp1 = get_comparativa_12_meses(ano_comp1)
    df_comp1_full = pd.DataFrame({'mes': range(1, 13)})
    df_comp1_full = df_comp1_full.merge(df_comp1, on='mes', how='left').fillna(0)
    df_comp1_full['cantidad_facturas'] = df_comp1_full['cantidad_facturas'].astype(int)
    df_comp1_full['total_dinero'] = df_comp1_full['total_dinero'].astype(int)
    df_comp1_full['promedio'] = (df_comp1_full['total_dinero'] / df_comp1_full['cantidad_facturas'].replace(0, 1)).fillna(0).astype(int)
    
    df_comp2 = get_comparativa_12_meses(ano_comp2) if ano_comp1 != ano_comp2 else pd.DataFrame()
    if not df_comp2.empty:
        df_comp2_full = pd.DataFrame({'mes': range(1, 13)})
        df_comp2_full = df_comp2_full.merge(df_comp2, on='mes', how='left').fillna(0)
        df_comp2_full['cantidad_facturas'] = df_comp2_full['cantidad_facturas'].astype(int)
        df_comp2_full['total_dinero'] = df_comp2_full['total_dinero'].astype(int)
        df_comp2_full['promedio'] = (df_comp2_full['total_dinero'] / df_comp2_full['cantidad_facturas'].replace(0, 1)).fillna(0).astype(int)
    
    # Gráficos LADO A LADO
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.subheader(f"Año {ano_comp1}")
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=[meses_nombres[i-1] for i in df_comp1_full['mes']],
            y=df_comp1_full['cantidad_facturas'],
            name='Cantidad',
            yaxis='y1',
            marker=dict(color='rgba(0, 118, 168, 0.7)')
        ))
        fig1.add_trace(go.Scatter(
            x=[meses_nombres[i-1] for i in df_comp1_full['mes']],
            y=df_comp1_full['total_dinero'],
            name='Total ($)',
            yaxis='y2',
            mode='lines+markers',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=10)
        ))
        fig1.update_layout(
            xaxis_title="Mes",
            yaxis=dict(title="Facturas", side='left'),
            yaxis2=dict(title="Total ($)", overlaying='y', side='right'),
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
                marker=dict(color='rgba(76, 175, 80, 0.7)')
            ))
            fig2.add_trace(go.Scatter(
                x=[meses_nombres[i-1] for i in df_comp2_full['mes']],
                y=df_comp2_full['total_dinero'],
                name='Total ($)',
                yaxis='y2',
                mode='lines+markers',
                line=dict(color='#FFC107', width=3),
                marker=dict(size=10)
            ))
            fig2.update_layout(
                xaxis_title="Mes",
                yaxis=dict(title="Facturas", side='left'),
                yaxis2=dict(title="Total ($)", overlaying='y', side='right'),
                hovermode='x unified',
                height=400,
                showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    # Tablas LADO A LADO
    st.subheader("Tablas Comparativas")
    col_tab1, col_tab2 = st.columns(2)
    
    with col_tab1:
        st.caption(f"Año {ano_comp1}")
        tabla1 = df_comp1_full.copy()
        tabla1['mes_nombre'] = [meses_nombres[i-1] for i in tabla1['mes']]
        st.dataframe(
            tabla1[['mes_nombre', 'cantidad_facturas', 'total_dinero', 'promedio']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "mes_nombre": st.column_config.TextColumn("Mes", width=60),
                "cantidad_facturas": st.column_config.NumberColumn("Facturas", width=80),
                "total_dinero": st.column_config.NumberColumn("Total", width=100, format="$%d"),
                "promedio": st.column_config.NumberColumn("Promedio", width=100, format="$%d"),
            }
        )
    
    if ano_comp1 != ano_comp2 and not df_comp2.empty:
        with col_tab2:
            st.caption(f"Año {ano_comp2}")
            tabla2 = df_comp2_full.copy()
            tabla2['mes_nombre'] = [meses_nombres[i-1] for i in tabla2['mes']]
            st.dataframe(
                tabla2[['mes_nombre', 'cantidad_facturas', 'total_dinero', 'promedio']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mes_nombre": st.column_config.TextColumn("Mes", width=60),
                    "cantidad_facturas": st.column_config.NumberColumn("Facturas", width=80),
                    "total_dinero": st.column_config.NumberColumn("Total", width=100, format="$%d"),
                    "promedio": st.column_config.NumberColumn("Promedio", width=100, format="$%d"),
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
            st.metric("Total Subcategorías", len(df_subcat))
        with col2:
            st.metric("Ingresos Totales", f"${df_subcat['costo'].sum():,.0f}")
        with col3:
            st.metric("Cantidad Total", f"{df_subcat['cantidad'].sum()}")
        with col4:
            st.metric("Promedio General", f"${int(df_subcat['costo'].sum() / df_subcat['cantidad'].sum()):,.0f}")
        
        st.divider()
        
        st.subheader("Detalle Completo")
        st.dataframe(
            df_subcat,
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria": st.column_config.TextColumn("Categoría", width=150),
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=200),
                "cantidad": st.column_config.NumberColumn("Cantidad", width=100),
                "costo": st.column_config.NumberColumn("Total ($)", width=130, format="$%d"),
                "promedio": st.column_config.NumberColumn("Promedio ($)", width=130, format="$%d"),
                "pct": st.column_config.NumberColumn("% Total", width=100, format="%.2f%%"),
            }
        )
        
        st.subheader("Distribución por Subcategoría")
        fig_pie = go.Figure(data=[go.Pie(
            labels=df_subcat['subcategoria'],
            values=df_subcat['costo'],
            textposition='inside',
            hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>'
        )])
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.subheader("Gráfico de Barras")
        fig_bar = go.Figure(data=[go.Bar(
            x=df_subcat['subcategoria'],
            y=df_subcat['costo'],
            text=[f"{p:.1f}%" for p in df_subcat['pct']],
            textposition='outside',
            marker=dict(color=df_subcat['costo'], colorscale='Viridis'),
            hovertemplate='<b>%{x}</b><br>Categoría: ' + df_subcat['categoria'].astype(str) + '<br>Cantidad: ' + df_subcat['cantidad'].astype(str) + '<br>Total: $%{y:,.0f}<br>Promedio: $' + df_subcat['promedio'].astype(str) + '<extra></extra>'
        )])
        fig_bar.update_layout(xaxis_title="Subcategoría", yaxis_title="Total ($)", height=400)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("ℹ️ Sin datos de subcategorías")

# ============================================================
# TAB 3: NEWTON VS NEWTON PLUS
# ============================================================
with tab3:
    st.header(f"📈 Newton vs Newton Plus")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("📅 Fecha Inicio", value=pd.to_datetime(f"{ano_actual}-01-01"), key="newton_inicio")
    with col2:
        fecha_fin = st.date_input("📅 Fecha Fin", value=pd.to_datetime(f"{ano_actual}-12-31"), key="newton_fin")
    
    df_newton = get_newton_rango(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))
    
    if not df_newton.empty:
        df_newton_pivot_cant = df_newton.pivot_table(
            index='fecha', columns='tipo', values='cantidad', aggfunc='sum', fill_value=0
        )
        df_newton_pivot_prom = df_newton.pivot_table(
            index='fecha', columns='tipo', values='promedio_diario', aggfunc='first', fill_value=0
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
                hovertemplate='<b>%{x}</b><br>' + col + ' Cantidad: %{y}<extra></extra>'
            ))
        
        # Líneas para promedio DIARIO
        for col in df_newton_pivot_prom.columns:
            fig.add_trace(go.Scatter(
                x=df_newton_pivot_prom.index,
                y=df_newton_pivot_prom[col],
                name=f"{col} (Promedio Diario)",
                yaxis='y2',
                mode='lines+markers',
                line=dict(width=2),
                hovertemplate='<b>%{x}</b><br>' + col + ' Promedio Diario: $%{y:,.0f}<extra></extra>'
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
# TAB 4: ANÁLISIS POR SUBCATEGORÍA
# ============================================================
with tab4:
    st.header(f"📍 Análisis Completo por Subcategoría - Año {ano_actual}")
    
    col_mes, col_space = st.columns([2, 10])
    with col_mes:
        mes_tab4 = st.selectbox(
            "📅 Mes",
            range(1, 13),
            index=0,
            format_func=lambda x: meses_nombres[x-1],
            key="tab4_mes"
        )
    
    df_subcat_full = get_analisis_subcategorias_mes(ano_actual, mes_tab4)
    
    if not df_subcat_full.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Subcategorías", len(df_subcat_full))
        with col2:
            st.metric("Ingresos Totales", f"${df_subcat_full['total'].sum():,.0f}")
        with col3:
            st.metric("Total Trabajos", f"{df_subcat_full['cantidad'].sum()}")
        
        st.divider()
        
        st.subheader("Cantidad | Total | Promedio | Porcentaje")
        st.dataframe(
            df_subcat_full,
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria": st.column_config.TextColumn("Categoría", width=150),
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=220),
                "cantidad": st.column_config.NumberColumn("Cantidad de Trabajos", width=130),
                "total": st.column_config.NumberColumn("Total ($)", width=140, format="$%d"),
                "promedio": st.column_config.NumberColumn("Promedio ($)", width=140, format="$%d"),
                "pct": st.column_config.NumberColumn("% Total", width=110, format="%.2f%%"),
            }
        )
        
        st.subheader("Distribución")
        fig = go.Figure(data=[go.Bar(
            x=df_subcat_full['subcategoria'],
            y=df_subcat_full['total'],
            text=[f"{p:.1f}%" for p in df_subcat_full['pct']],
            textposition='outside',
            marker=dict(color=df_subcat_full['total'], colorscale='Viridis'),
            hovertemplate='<b>%{x}</b><br>Categoría: ' + df_subcat_full['categoria'].astype(str) + '<br>Cantidad: ' + df_subcat_full['cantidad'].astype(str) + '<br>Total: $%{y:,.0f}<extra></extra>'
        )])
        fig.update_layout(xaxis_title="Subcategoría", yaxis_title="Total ($)", height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Sin datos")

# ============================================================
# PIE
# ============================================================
st.divider()
st.caption(f"✅ Dashboard v4.0 MEJORADO | {datetime.now().strftime('%d/%m/%Y %H:%M')} | Año {ano_actual}")
