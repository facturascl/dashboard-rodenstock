import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime, timedelta

# Configuración de página
st.set_page_config(
    page_title="Dashboard Facturación Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CONEXIÓN A BD
# ============================================================
DB_PATH = "facturas.db"

@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

conn = get_db_connection()

# ============================================================
# SIDEBAR - FILTROS
# ============================================================
st.sidebar.title("🔧 Filtros")

# Obtener años disponibles
anos_query = """
    SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano
    FROM facturas
    WHERE fechaemision IS NOT NULL
    ORDER BY ano DESC
"""
anos_df = pd.read_sql_query(anos_query, conn)
anos_disponibles = anos_df['ano'].tolist() if not anos_df.empty else [datetime.now().year]

ano_seleccionado = st.sidebar.selectbox(
    "Año",
    options=anos_disponibles,
    index=0
)

# Obtener meses del año seleccionado
meses_query = f"""
    SELECT DISTINCT CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano_seleccionado}
    AND fechaemision IS NOT NULL
    ORDER BY mes DESC
"""
meses_df = pd.read_sql_query(meses_query, conn)
meses_disponibles = meses_df['mes'].tolist() if not meses_df.empty else [datetime.now().month]

mes_param = st.sidebar.selectbox(
    "Mes",
    options=meses_disponibles,
    index=0,
    format_func=lambda x: f"{x:02d}"
)

# ============================================================
# FUNCIONES DE CONSULTA - CORREGIDAS
# ============================================================

@st.cache_data(ttl=600)
def get_totales_periodo(ano_sel, mes_param):
    """Totales mensuales"""
    query = f"""
    SELECT 
        CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano,
        CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
        COUNT(DISTINCT numerofactura) as cantidad_facturas,
        CAST(SUM(subtotal + iva) AS INTEGER) as total_general
    FROM facturas
    WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', fechaemision) AS INTEGER) = {mes_param}
    AND fechaemision IS NOT NULL
    GROUP BY ano, mes
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_resumen_facturas(ano_sel, mes_param):
    """Resumen detallado de facturas - SIN columna descripcion (no existe)"""
    query = f"""
    SELECT
        f.numerofactura,
        DATE(f.fechaemision) as fecha,
        (SELECT COUNT(DISTINCT linea_numero) 
         FROM lineas_factura 
         WHERE numerofactura = f.numerofactura) as items,
        CAST(f.subtotal AS INTEGER) as subtotal,
        CAST(f.iva AS INTEGER) as iva,
        CAST(f.subtotal + f.iva AS INTEGER) as total
    FROM facturas f
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
    AND f.fechaemision IS NOT NULL
    ORDER BY f.fechaemision DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_categorias_detalle(ano_sel, mes_param):
    """Categorías y subcategorías"""
    query = f"""
    SELECT 
        COALESCE(lf.clasificacion_categoria, 'Sin categoría') as categoria,
        COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
        COUNT(DISTINCT lf.numerofactura) as cantidad_facturas,
        CAST(SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as total
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
    AND f.fechaemision IS NOT NULL
    GROUP BY categoria, subcategoria
    ORDER BY total DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_newton_diario(ano_sel, mes_param):
    """Newton vs Newton Plus por día"""
    query = f"""
    WITH trabajos AS (
        SELECT
            DATE(f.fechaemision) AS dia,
            f.numerofactura,
            MAX(CASE WHEN lf.clasificacion_categoria = 'Newton' THEN 1 ELSE 0 END) AS es_newton,
            MAX(CASE WHEN lf.clasificacion_categoria = 'Newton Plus' THEN 1 ELSE 0 END) AS es_newton_plus,
            f.subtotal + f.iva as total_factura
        FROM lineas_factura lf
        JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE lf.clasificacion_categoria IN ('Newton', 'Newton Plus')
        AND CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
        AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
        AND f.fechaemision IS NOT NULL
        GROUP BY dia, f.numerofactura, total_factura
    ),
    resumen_diario AS (
        SELECT
            dia,
            SUM(es_newton) AS cantidad_newton,
            SUM(CASE WHEN es_newton = 1 THEN total_factura ELSE 0 END) AS total_newton,
            SUM(es_newton_plus) AS cantidad_newton_plus,
            SUM(CASE WHEN es_newton_plus = 1 THEN total_factura ELSE 0 END) AS total_newton_plus
        FROM trabajos
        GROUP BY dia
    )
    SELECT
        dia,
        cantidad_newton,
        CAST(total_newton AS INTEGER) as total_newton,
        CASE WHEN cantidad_newton > 0 THEN CAST(total_newton / cantidad_newton AS INTEGER) ELSE NULL END AS promedio_newton,
        cantidad_newton_plus,
        CAST(total_newton_plus AS INTEGER) as total_newton_plus,
        CASE WHEN cantidad_newton_plus > 0 THEN CAST(total_newton_plus / cantidad_newton_plus AS INTEGER) ELSE NULL END AS promedio_newton_plus
    FROM resumen_diario
    ORDER BY dia DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_top_subcategorias(ano_sel, mes_param):
    """Top 10 subcategorías"""
    query = f"""
    SELECT 
        COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
        COUNT(DISTINCT lf.numerofactura) as cantidad,
        CAST(SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as total
    FROM lineas_factura lf
    INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
    WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {ano_sel}
    AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {mes_param}
    AND f.fechaemision IS NOT NULL
    GROUP BY subcategoria
    ORDER BY total DESC
    LIMIT 10
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=600)
def get_comparativa_anos(mes_param):
    """Comparativa de 2 años por mes - AGREGADO PERDIDO"""
    query = f"""
    SELECT 
        CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano,
        CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
        COUNT(DISTINCT numerofactura) as cantidad_facturas,
        CAST(SUM(subtotal + iva) AS INTEGER) as total_mes
    FROM facturas
    WHERE CAST(STRFTIME('%m', fechaemision) AS INTEGER) = {mes_param}
    AND fechaemision IS NOT NULL
    GROUP BY ano, mes
    ORDER BY ano DESC
    """
    return pd.read_sql_query(query, conn)

# ============================================================
# TABS PRINCIPALES
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Resumen",
    "📋 Facturas",
    "🏷️ Análisis de Categorías",
    "🔍 Newton vs Plus",
    "🥇 Top 10"
])

# ============================================================
# TAB 1: RESUMEN
# ============================================================
with tab1:
    st.header("📊 Resumen General")
    
    totales = get_totales_periodo(ano_seleccionado, mes_param)
    
    if not totales.empty:
        cantidad = totales['cantidad_facturas'].values[0]
        total_dinero = totales['total_general'].values[0]
        promedio = total_dinero / cantidad if cantidad > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📌 Total Facturas", f"{cantidad:,}")
        with col2:
            st.metric("💰 Total Ingresos", f"${total_dinero:,.0f}")
        with col3:
            st.metric("📈 Promedio/Factura", f"${promedio:,.0f}")
        with col4:
            st.metric("📅 Período", f"{ano_seleccionado}-{mes_param:02d}")
        
        # Gráfico de línea de totales diarios
        st.subheader("Distribución diaria de ingresos")
        
        query_diario = f"""
        SELECT
            DATE(fechaemision) as fecha,
            CAST(SUM(subtotal + iva) AS INTEGER) as total_diario,
            COUNT(DISTINCT numerofactura) as facturas_diarias
        FROM facturas
        WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {ano_seleccionado}
        AND CAST(STRFTIME('%m', fechaemision) AS INTEGER) = {mes_param}
        AND fechaemision IS NOT NULL
        GROUP BY fecha
        ORDER BY fecha
        """
        df_diario = pd.read_sql_query(query_diario, conn)
        
        if not df_diario.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_diario['fecha'],
                y=df_diario['total_diario'],
                mode='lines+markers',
                name='Total Diario',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=6)
            ))
            fig.update_layout(
                title="Ingresos por Día",
                xaxis_title="Fecha",
                yaxis_title="Total ($)",
                hovermode='x unified',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # GRÁFICO DE COMPARATIVA POR AÑO - RESTAURADO
        st.divider()
        st.subheader("📊 Comparativa de años - Mes seleccionado")
        
        df_comparativa = get_comparativa_anos(mes_param)
        
        if not df_comparativa.empty and len(df_comparativa) > 1:
            fig_comparativa = go.Figure()
            
            for idx, row in df_comparativa.iterrows():
                fig_comparativa.add_trace(go.Bar(
                    x=['Facturas', 'Total ($)'],
                    y=[row['cantidad_facturas'], row['total_mes'] / 1000],  # Dividir por 1000 para escala
                    name=f"Año {int(row['ano'])}",
                    text=[f"{int(row['cantidad_facturas'])}", f"${row['total_mes']:,.0f}"],
                    textposition='auto'
                ))
            
            fig_comparativa.update_layout(
                title=f"Comparativa Años - Mes {mes_param:02d}",
                xaxis_title="Métrica",
                yaxis_title="Valor (Facturas o $k)",
                barmode='group',
                height=400,
                hovermode='x unified'
            )
            st.plotly_chart(fig_comparativa, use_container_width=True)
        elif not df_comparativa.empty:
            st.info("ℹ️ Solo hay datos de un año. Necesitas 2 años para comparar.")
    else:
        st.warning("⚠️ No hay datos disponibles para este período")

# ============================================================
# TAB 2: FACTURAS
# ============================================================
with tab2:
    st.header("📋 Detalle de Facturas")
    
    df_facturas = get_resumen_facturas(ano_seleccionado, mes_param)
    
    if not df_facturas.empty:
        # Buscador y filtro
        col1, col2 = st.columns(2)
        with col1:
            buscar = st.text_input("🔍 Buscar por número de factura:")
        
        # Aplicar filtro
        if buscar:
            df_facturas = df_facturas[
                df_facturas['numerofactura'].astype(str).str.contains(buscar, case=False)
            ]
        
        # Tabla
        st.dataframe(
            df_facturas,
            use_container_width=True,
            hide_index=True,
            column_config={
                "numerofactura": st.column_config.TextColumn("N° Factura", width=120),
                "fecha": st.column_config.DateColumn("Fecha", width=100),
                "items": st.column_config.NumberColumn("Items", width=80),
                "subtotal": st.column_config.NumberColumn("Subtotal", width=100, format="$%d"),
                "iva": st.column_config.NumberColumn("IVA", width=100, format="$%d"),
                "total": st.column_config.NumberColumn("Total", width=100, format="$%d"),
            }
        )
        
        st.caption(f"Total registros: {len(df_facturas)}")
    else:
        st.info("📭 Sin facturas para este período")

# ============================================================
# TAB 3: ANÁLISIS DE CATEGORÍAS
# ============================================================
with tab3:
    st.header("🏷️ Análisis por Categoría")
    
    df_categorias = get_categorias_detalle(ano_seleccionado, mes_param)
    
    if not df_categorias.empty:
        # Resumen
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Categorías únicas", len(df_categorias['categoria'].unique()))
        with col2:
            st.metric("Subcategorías", len(df_categorias))
        with col3:
            st.metric("Total ingresos", f"${df_categorias['total'].sum():,.0f}")
        
        st.divider()
        
        # Tabla
        st.subheader("Detalle por subcategoría")
        st.dataframe(
            df_categorias,
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria": st.column_config.TextColumn("Categoría", width=150),
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=200),
                "cantidad_facturas": st.column_config.NumberColumn("Facturas", width=100),
                "total": st.column_config.NumberColumn("Total", width=120, format="$%d"),
            }
        )
        
        # Gráfico de pie por categoría
        st.subheader("Distribución por categoría")
        df_cat_pie = df_categorias.groupby('categoria')['total'].sum().reset_index()
        fig_pie = px.pie(
            df_cat_pie,
            names='categoria',
            values='total',
            title="% Ingresos por Categoría"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("📭 Sin datos de categorías para este período")

# ============================================================
# TAB 4: NEWTON VS NEWTON PLUS
# ============================================================
with tab4:
    st.header("🔍 Newton vs Newton Plus")
    
    df_newton = get_newton_diario(ano_seleccionado, mes_param)
    
    if not df_newton.empty:
        # Totales globales
        total_newton = df_newton['total_newton'].sum()
        total_newton_plus = df_newton['total_newton_plus'].sum()
        cantidad_newton = df_newton['cantidad_newton'].sum()
        cantidad_newton_plus = df_newton['cantidad_newton_plus'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🔵 Newton - Cantidad", f"{int(cantidad_newton)}")
        with col2:
            st.metric("🔵 Newton - Total", f"${total_newton:,.0f}")
        with col3:
            st.metric("🟠 Newton Plus - Cantidad", f"{int(cantidad_newton_plus)}")
        with col4:
            st.metric("🟠 Newton Plus - Total", f"${total_newton_plus:,.0f}")
        
        st.divider()
        
        # Gráfico comparativo
        st.subheader("Evolución diaria")
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_newton['dia'],
            y=df_newton['total_newton'],
            mode='lines+markers',
            name='Newton Total',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6)
        ))
        
        fig.add_trace(go.Scatter(
            x=df_newton['dia'],
            y=df_newton['total_newton_plus'],
            mode='lines+markers',
            name='Newton Plus Total',
            line=dict(color='#ff7f0e', width=2),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            title="Ingresos diarios: Newton vs Newton Plus",
            xaxis_title="Fecha",
            yaxis_title="Total ($)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabla detallada
        st.subheader("Detalle por día")
        st.dataframe(
            df_newton,
            use_container_width=True,
            hide_index=True,
            column_config={
                "dia": st.column_config.DateColumn("Fecha", width=100),
                "cantidad_newton": st.column_config.NumberColumn("Newton Qty", width=100),
                "total_newton": st.column_config.NumberColumn("Newton Total", width=120, format="$%d"),
                "promedio_newton": st.column_config.NumberColumn("Newton Avg", width=120, format="$%d"),
                "cantidad_newton_plus": st.column_config.NumberColumn("Plus Qty", width=100),
                "total_newton_plus": st.column_config.NumberColumn("Plus Total", width=120, format="$%d"),
                "promedio_newton_plus": st.column_config.NumberColumn("Plus Avg", width=120, format="$%d"),
            }
        )
    else:
        st.info("📭 Sin datos de Newton para este período")

# ============================================================
# TAB 5: TOP 10 SUBCATEGORÍAS
# ============================================================
with tab5:
    st.header("🥇 Top 10 Subcategorías")
    
    df_top = get_top_subcategorias(ano_seleccionado, mes_param)
    
    if not df_top.empty:
        # Métrica
        st.metric("Total ingresos top 10", f"${df_top['total'].sum():,.0f}")
        
        st.divider()
        
        # Gráfico de barras
        fig_bar = px.bar(
            df_top,
            x='total',
            y='subcategoria',
            orientation='h',
            title='Top 10 Subcategorías por Ingresos',
            labels={'total': 'Total ($)', 'subcategoria': 'Subcategoría'},
            color='total',
            color_continuous_scale='Viridis'
        )
        fig_bar.update_layout(height=500, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)
        
        # Tabla
        st.subheader("Detalle")
        st.dataframe(
            df_top,
            use_container_width=True,
            hide_index=True,
            column_config={
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=250),
                "cantidad": st.column_config.NumberColumn("Facturas", width=100),
                "total": st.column_config.NumberColumn("Total", width=120, format="$%d"),
            }
        )
    else:
        st.info("📭 Sin datos de subcategorías para este período")

# ============================================================
# PIE DE PÁGINA
# ============================================================
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("✅ Base de datos: SQLite")
with col2:
    st.caption(f"📅 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
with col3:
    st.caption("🔧 Rodenstock Dashboard v3.1")
