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
    
    ano_seleccionado = st.sidebar.selectbox("📅 Año para Comparar", anos_disponibles, key="ano_select")
    
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
def get_subcategorias_completo(ano):
    """Todas las subcategorías: cantidad, costo, promedio, porcentaje"""
    query = f"""
    WITH stats_totales AS (
        SELECT CAST(SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as total_general
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano)}
        AND f.fechaemision IS NOT NULL
    )
    SELECT 
        COALESCE(lf.clasificacion_subcategoria, 'Sin clasificación') as subcategoria,
        COUNT(DISTINCT lf.numerofactura) as cantidad,
        CAST(SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as costo,
        CAST(AVG(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as promedio,
        CAST(100.0 * SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) / NULLIF((SELECT total_general FROM stats_totales), 0) AS DECIMAL(5,2)) as pct
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano)}
    AND f.fechaemision IS NOT NULL
    GROUP BY subcategoria
    ORDER BY costo DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_newton_rango(fecha_inicio, fecha_fin):
    """Newton vs Newton Plus con rango de fechas: cantidad y promedio diario"""
    query = f"""
    SELECT 
        STRFTIME('%Y-%m-%d', f.fechaemision) as fecha,
        CASE WHEN lf.clasificacion_categoria = 'Newton' THEN 'Newton' ELSE 'Newton Plus' END as tipo,
        COUNT(DISTINCT lf.numerofactura) as cantidad,
        CAST(AVG(f.subtotal + f.iva) AS INTEGER) as promedio_diario
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE f.fechaemision BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
    AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
    AND f.fechaemision IS NOT NULL
    GROUP BY fecha, tipo
    ORDER BY fecha DESC, tipo
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def get_fechas_disponibles(ano):
    """Obtener primer y último día con datos del año"""
    query = f"""
    SELECT 
        MIN(STRFTIME('%Y-%m-%d', fechaemision)) as fecha_min,
        MAX(STRFTIME('%Y-%m-%d', fechaemision)) as fecha_max
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {int(ano)}
    AND lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
    """
    result = pd.read_sql_query(query, conn)
    if not result.empty and result['fecha_min'].iloc[0]:
        return result['fecha_min'].iloc[0], result['fecha_max'].iloc[0]
    return None, None

@st.cache_data(ttl=300)
def get_analisis_categorias(ano):
    """Análisis por categoría principal"""
    query = f"""
    WITH stats_totales AS (
        SELECT CAST(SUM(f.subtotal + f.iva) AS INTEGER) as total_general
        FROM facturas f
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano)}
        AND f.fechaemision IS NOT NULL
    )
    SELECT 
        COALESCE(lf.clasificacion_categoria, 'Sin categoría') as categoria,
        COUNT(DISTINCT lf.numerofactura) as cantidad,
        CAST(SUM(f.subtotal + f.iva) AS INTEGER) as total,
        CAST(100.0 * SUM(f.subtotal + f.iva) / NULLIF((SELECT total_general FROM stats_totales), 0) AS DECIMAL(5,2)) as pct
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano)}
    AND f.fechaemision IS NOT NULL
    GROUP BY categoria
    ORDER BY total DESC
    """
    return pd.read_sql_query(query, conn)

# ============================================================
# TABS PRINCIPALES
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Comparativa Anual",
    "🏷️ Desglose Subcategorías",
    "📈 Newton vs Plus",
    "📍 Análisis Categorías"
])

# ============================================================
# TAB 1: COMPARATIVA ANUAL (12 MESES)
# ============================================================
with tab1:
    st.header(f"📊 Comparativa Año {ano_seleccionado} - 12 Meses")
    
    df_comp = get_comparativa_12_meses(ano_seleccionado)
    
    if not df_comp.empty:
        # Rellenar meses faltantes
        df_comp_full = pd.DataFrame({'mes': range(1, 13)})
        df_comp_full = df_comp_full.merge(df_comp, on='mes', how='left').fillna(0)
        df_comp_full['cantidad_facturas'] = df_comp_full['cantidad_facturas'].astype(int)
        df_comp_full['total_dinero'] = df_comp_full['total_dinero'].astype(int)
        
        meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        
        # Gráfico
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=[meses_nombres[i-1] for i in df_comp_full['mes']],
            y=df_comp_full['cantidad_facturas'],
            name='Cantidad de Facturas',
            yaxis='y1',
            marker=dict(color='rgba(0, 118, 168, 0.7)')
        ))
        
        fig.add_trace(go.Scatter(
            x=[meses_nombres[i-1] for i in df_comp_full['mes']],
            y=df_comp_full['total_dinero'],
            name='Total en Dinero ($)',
            yaxis='y2',
            mode='lines+markers',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=10)
        ))
        
        fig.update_layout(
            title=f"Comparativa {ano_seleccionado}: Facturas por Mes y Total en Dinero",
            xaxis_title="Mes",
            yaxis=dict(title="Cantidad de Facturas", side='left'),
            yaxis2=dict(title="Total ($)", overlaying='y', side='right'),
            hovermode='x unified',
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabla
        st.subheader("Datos Mensuales")
        tabla_display = df_comp_full.copy()
        tabla_display['mes_nombre'] = [meses_nombres[i-1] for i in tabla_display['mes']]
        st.dataframe(
            tabla_display[['mes_nombre', 'cantidad_facturas', 'total_dinero']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "mes_nombre": st.column_config.TextColumn("Mes", width=100),
                "cantidad_facturas": st.column_config.NumberColumn("Facturas", width=120),
                "total_dinero": st.column_config.NumberColumn("Total ($)", width=150, format="$%d"),
            }
        )
    else:
        st.info("ℹ️ Sin datos para este año")

# ============================================================
# TAB 2: DESGLOSE SUBCATEGORÍAS
# ============================================================
with tab2:
    st.header(f"🏷️ Desglose Subcategorías - {ano_seleccionado}")
    
    df_subcat = get_subcategorias_completo(ano_seleccionado)
    
    if not df_subcat.empty:
        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Subcategorías", len(df_subcat))
        with col2:
            st.metric("Ingresos Totales", f"${df_subcat['costo'].sum():,.0f}")
        with col3:
            st.metric("Promedio", f"${df_subcat['promedio'].mean():,.0f}")
        
        st.divider()
        
        # Tabla
        st.subheader("Detalle Completo")
        st.dataframe(
            df_subcat,
            use_container_width=True,
            hide_index=True,
            column_config={
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=250),
                "cantidad": st.column_config.NumberColumn("Cantidad", width=100),
                "costo": st.column_config.NumberColumn("Costo", width=130, format="$%d"),
                "promedio": st.column_config.NumberColumn("Promedio", width=130, format="$%d"),
                "pct": st.column_config.NumberColumn("% Total", width=100, format="%.2f%%"),
            }
        )
        
        # Gráfico
        st.subheader("Distribución")
        fig_pie = go.Figure(data=[go.Pie(
            labels=df_subcat['subcategoria'],
            values=df_subcat['costo'],
            textposition='inside',
            hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<extra></extra>'
        )])
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("ℹ️ Sin datos de subcategorías")

# ============================================================
# TAB 3: NEWTON VS NEWTON PLUS (DÍA A DÍA + RANGO)
# ============================================================
with tab3:
    st.header(f"📈 Newton vs Newton Plus - Análisis por Día {ano_seleccionado}")
    
    # Selector de rango de fechas
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("📅 Fecha Inicio", value=pd.to_datetime(f"{ano_seleccionado}-01-01"))
    with col2:
        fecha_fin = st.date_input("📅 Fecha Fin", value=pd.to_datetime(f"{ano_seleccionado}-12-31"))
    
    df_newton = get_newton_rango(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))
    
    if not df_newton.empty:
        # Tabla: Cantidad + Promedio Diario
        st.subheader("Detalle Diario: Cantidad y Promedio")
        st.dataframe(
            df_newton,
            use_container_width=True,
            hide_index=True,
            column_config={
                "fecha": st.column_config.TextColumn("Fecha", width=120),
                "tipo": st.column_config.TextColumn("Tipo", width=100),
                "cantidad": st.column_config.NumberColumn("Cantidad", width=100),
                "promedio_diario": st.column_config.NumberColumn("Promedio/Día ($)", width=150, format="$%d"),
            }
        )
        
        # Gráfico 1: Cantidad Diaria
        st.subheader("Cantidad Diaria: Newton vs Newton Plus")
        
        df_newton_cantidad = df_newton.pivot_table(
            index='fecha', columns='tipo', values='cantidad', aggfunc='sum', fill_value=0
        )
        
        fig_cantidad = go.Figure()
        for col in df_newton_cantidad.columns:
            fig_cantidad.add_trace(go.Bar(
                x=df_newton_cantidad.index,
                y=df_newton_cantidad[col],
                name=col,
                opacity=0.7
            ))
        
        fig_cantidad.update_layout(
            title="Cantidad de Facturas Diarias",
            xaxis_title="Fecha",
            yaxis_title="Cantidad",
            hovermode='x unified',
            height=400,
            barmode='group'
        )
        st.plotly_chart(fig_cantidad, use_container_width=True)
        
        # Gráfico 2: Promedio Diario
        st.subheader("Promedio Diario: Newton vs Newton Plus")
        
        df_newton_promedio = df_newton.pivot_table(
            index='fecha', columns='tipo', values='promedio_diario', aggfunc='first', fill_value=0
        )
        
        fig_promedio = go.Figure()
        for col in df_newton_promedio.columns:
            fig_promedio.add_trace(go.Scatter(
                x=df_newton_promedio.index,
                y=df_newton_promedio[col],
                name=col,
                mode='lines+markers',
                line=dict(width=2)
            ))
        
        fig_promedio.update_layout(
            title="Promedio de Factura Diario ($)",
            xaxis_title="Fecha",
            yaxis_title="Promedio ($)",
            hovermode='x unified',
            height=400
        )
        st.plotly_chart(fig_promedio, use_container_width=True)
    else:
        st.info("ℹ️ Sin datos Newton/Newton Plus en este rango")

# ============================================================
# TAB 4: ANÁLISIS DE CATEGORÍAS
# ============================================================
with tab4:
    st.header(f"📍 Análisis por Categoría - {ano_seleccionado}")
    
    df_cat = get_analisis_categorias(ano_seleccionado)
    
    if not df_cat.empty:
        # Tabla
        st.dataframe(
            df_cat,
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria": st.column_config.TextColumn("Categoría", width=250),
                "cantidad": st.column_config.NumberColumn("Cantidad", width=100),
                "total": st.column_config.NumberColumn("Total ($)", width=130, format="$%d"),
                "pct": st.column_config.NumberColumn("% Total", width=100, format="%.2f%%"),
            }
        )
        
        # Gráfico
        fig = go.Figure(data=[go.Bar(
            x=df_cat['categoria'],
            y=df_cat['total'],
            text=df_cat['pct'].apply(lambda x: f"{x:.1f}%"),
            textposition='outside',
            marker=dict(color=df_cat['total'], colorscale='Viridis')
        )])
        fig.update_layout(
            title="Total por Categoría",
            xaxis_title="Categoría",
            yaxis_title="Total ($)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Sin datos de categorías")

# ============================================================
# PIE
# ============================================================
st.divider()
st.caption(f"✅ Dashboard v2.1 | {datetime.now().strftime('%d/%m/%Y %H:%M')} | Año: {ano_seleccionado}")
