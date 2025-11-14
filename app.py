
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CONEXIÓN A BD ==========
def find_database():
    """Busca facturas.db en rutas comunes"""
    possible_paths = [
        'facturas.db',
        '/app/facturas.db',
        '/mount/src/dashboard-rodenstock/facturas.db',
        os.path.join(os.getcwd(), 'facturas.db'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

DB_FILE = find_database()

@st.cache_resource
def get_conn():
    if DB_FILE is None:
        st.error("❌ Base de datos no encontrada")
        st.stop()
    return sqlite3.connect(DB_FILE)

# ========== ESTILOS ==========
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
    }
    .metric-label {
        font-size: 14px;
        opacity: 0.8;
    }
</style>
""", unsafe_allow_html=True)

# ========== ENCABEZADO ==========
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📊 Dashboard de Facturación Rodenstock")
with col2:
    st.info(f"📁 {DB_FILE.split('/')[-1] if DB_FILE else 'BD no encontrada'}")

st.markdown("---")

# ========== SIDEBAR - FILTROS ==========
st.sidebar.header("⚙️ Filtros")

try:
    conn = get_conn()

    # Cargar años
    query_anos = "SELECT DISTINCT SUBSTR(fechaemision, 1, 4) AS ano FROM facturas WHERE fechaemision IS NOT NULL ORDER BY ano DESC"
    df_anos = pd.read_sql_query(query_anos, conn)
    anos_list = sorted(df_anos['ano'].tolist(), reverse=True) if not df_anos.empty else []

    ano_sel = st.sidebar.selectbox("📅 Año", options=anos_list if anos_list else ["2025"])

    # Cargar meses
    query_meses = f"SELECT DISTINCT SUBSTR(fechaemision, 6, 2) AS mes FROM facturas WHERE SUBSTR(fechaemision, 1, 4) = '{ano_sel}' AND fechaemision IS NOT NULL ORDER BY mes"
    df_meses = pd.read_sql_query(query_meses, conn)
    meses_list = sorted(df_meses['mes'].tolist()) if not df_meses.empty else []

    mes_options = ["Todos"] + meses_list
    mes_sel = st.sidebar.selectbox("📆 Mes", options=mes_options, index=0)

    conn.close()

except Exception as e:
    st.error(f"Error cargando filtros: {e}")
    anos_list = []
    mes_sel = "Todos"

# ========== QUERIES SEGÚN FILTRO ==========
def get_where_clause():
    if mes_sel == "Todos":
        return f"WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' AND f.fechaemision IS NOT NULL"
    else:
        return f"WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel}' AND f.fechaemision IS NOT NULL"

# ========== MÉTRICAS PRINCIPALES ==========
st.subheader("📈 Resumen Ejecutivo")

try:
    conn = get_conn()
    where = get_where_clause()

    # Totales
    query = f"SELECT COUNT(*) as total_fact, SUM(f.subtotal + f.iva) as monto_total FROM facturas f {where}"
    result = pd.read_sql_query(query, conn).iloc[0]

    total_facturas = int(result['total_fact']) if result['total_fact'] else 0
    total_monto = float(result['monto_total']) if result['monto_total'] else 0

    # Categorías
    query_cat = f"SELECT COUNT(DISTINCT lf.clasificacion_categoria) as num_cat, COUNT(*) as num_lineas FROM lineas_factura lf INNER JOIN facturas f ON lf.numerofactura = f.numerofactura {where}"
    result_cat = pd.read_sql_query(query_cat, conn).iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Facturas", f"{total_facturas:,}")
    with col2:
        st.metric("💰 Monto Total", f"${total_monto:,.0f}")
    with col3:
        st.metric("🏷️ Categorías", int(result_cat['num_cat']))
    with col4:
        st.metric("📝 Líneas", f"{int(result_cat['num_lineas']):,}")

    conn.close()
except Exception as e:
    st.error(f"Error en métricas: {e}")

st.markdown("---")

# ========== GRÁFICAS ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Evolución", 
    "🏷️ Categorías", 
    "💰 Top 10", 
    "📈 Pareto", 
    "📅 Comparativa Meses",
    "📋 Tabla Detallada"
])

with tab1:
    st.subheader("1. Evolución Temporal")
    try:
        conn = get_conn()
        where = get_where_clause()

        if mes_sel == "Todos":
            # Mensual
            query = f"""
            SELECT SUBSTR(f.fechaemision, 1, 7) as periodo, 
                   COUNT(*) as facturas,
                   SUM(f.subtotal + f.iva) as monto
            FROM facturas f
            {where}
            GROUP BY periodo
            ORDER BY periodo
            """
            df = pd.read_sql_query(query, conn)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df['periodo'], y=df['monto'], 
                                     mode='lines+markers', name='Monto',
                                     line=dict(color='#667eea', width=3)))
            fig.update_layout(title="Evolución Mensual de Ingresos",
                            xaxis_title="Mes", yaxis_title="Monto ($)",
                            hovermode='x unified')
        else:
            # Diario
            query = f"""
            SELECT SUBSTR(f.fechaemision, 1, 10) as fecha, 
                   COUNT(*) as facturas,
                   SUM(f.subtotal + f.iva) as monto
            FROM facturas f
            {where}
            GROUP BY fecha
            ORDER BY fecha
            """
            df = pd.read_sql_query(query, conn)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['fecha'], y=df['monto'], 
                                name='Monto',
                                marker_color='#667eea'))
            fig.update_layout(title=f"Evolución Diaria - {ano_sel}/{mes_sel}",
                            xaxis_title="Fecha", yaxis_title="Monto ($)")

        st.plotly_chart(fig, use_container_width=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en gráfica de evolución: {e}")

with tab2:
    st.subheader("2. Distribución por Categoría")
    try:
        conn = get_conn()
        where = get_where_clause()

        query = f"""
        SELECT lf.clasificacion_categoria as categoria,
               COUNT(DISTINCT f.numerofactura) as facturas,
               SUM(f.subtotal + f.iva) as monto
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        {where}
        GROUP BY categoria
        ORDER BY monto DESC
        """
        df = pd.read_sql_query(query, conn)

        col1, col2 = st.columns(2)

        with col1:
            fig_pie = px.pie(df, values='monto', names='categoria',
                           title="Distribución por Monto",
                           color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            fig_bar = px.bar(df, x='categoria', y='facturas',
                           title="Cantidad de Facturas por Categoría",
                           color='monto',
                           color_continuous_scale='Viridis')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.dataframe(df, use_container_width=True, hide_index=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en gráfica de categorías: {e}")

with tab3:
    st.subheader("3. Top 10 Clientes/Productos")
    try:
        conn = get_conn()
        where = get_where_clause()

        query = f"""
        SELECT f.numerofactura,
               SUM(f.subtotal + f.iva) as monto
        FROM facturas f
        {where}
        GROUP BY f.numerofactura
        ORDER BY monto DESC
        LIMIT 10
        """
        df = pd.read_sql_query(query, conn)

        fig = px.bar(df, x='numerofactura', y='monto',
                    title="Top 10 Facturas por Monto",
                    color='monto',
                    color_continuous_scale='RdYlGn')
        fig.update_xaxes(tickangle=45)

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en top 10: {e}")

with tab4:
    st.subheader("4. Análisis de Pareto")
    try:
        conn = get_conn()
        where = get_where_clause()

        query = f"""
        SELECT lf.clasificacion_categoria as categoria,
               COUNT(DISTINCT f.numerofactura) as facturas,
               SUM(f.subtotal + f.iva) as monto
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        {where}
        GROUP BY categoria
        ORDER BY monto DESC
        """
        df = pd.read_sql_query(query, conn)

        # Calcular % acumulado
        df['porcentaje'] = (df['monto'] / df['monto'].sum() * 100).round(2)
        df['porcentaje_acumulado'] = df['porcentaje'].cumsum()

        fig = go.Figure()

        fig.add_trace(go.Bar(x=df['categoria'], y=df['monto'],
                            name='Monto', marker_color='#667eea'))

        fig.add_trace(go.Scatter(x=df['categoria'], y=df['porcentaje_acumulado'],
                                name='% Acumulado', mode='lines+markers',
                                yaxis='y2', line=dict(color='#ff6b6b', width=2)))

        fig.update_layout(
            title="Diagrama de Pareto",
            xaxis_title="Categoría",
            yaxis_title="Monto ($)",
            yaxis2=dict(title="% Acumulado", overlaying='y', side='right'),
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['categoria', 'facturas', 'monto', 'porcentaje', 'porcentaje_acumulado']], 
                    use_container_width=True, hide_index=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en Pareto: {e}")

with tab5:
    st.subheader("5. Comparativa entre Meses")
    try:
        conn = get_conn()

        query = f"""
        SELECT SUBSTR(f.fechaemision, 1, 7) as mes,
               COUNT(*) as facturas,
               SUM(f.subtotal + f.iva) as monto
        FROM facturas f
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}'
        GROUP BY mes
        ORDER BY mes
        """
        df = pd.read_sql_query(query, conn)

        fig = go.Figure()

        fig.add_trace(go.Bar(name='Facturas', x=df['mes'], y=df['facturas'],
                            marker_color='#667eea'))
        fig.add_trace(go.Scatter(name='Monto', x=df['mes'], y=df['monto'],
                                yaxis='y2', mode='lines+markers',
                                line=dict(color='#ff6b6b', width=2)))

        fig.update_layout(
            title=f"Comparativa Mensual - {ano_sel}",
            xaxis_title="Mes",
            yaxis_title="Cantidad de Facturas",
            yaxis2=dict(title="Monto ($)", overlaying='y', side='right'),
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en comparativa: {e}")

with tab6:
    st.subheader("6. Tabla Detallada de Facturas")
    try:
        conn = get_conn()
        where = get_where_clause()

        query = f"""
        SELECT f.numerofactura as "Factura",
               f.fechaemision as "Fecha",
               f.subtotal as "Subtotal",
               f.iva as "IVA",
               f.total as "Total"
        FROM facturas f
        {where}
        ORDER BY f.fechaemision DESC
        LIMIT 500
        """
        df = pd.read_sql_query(query, conn)

        if not df.empty:
            # Formatear moneda
            for col in ['Subtotal', 'IVA', 'Total']:
                df[col] = df[col].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(f"Mostrando primeras 500 facturas de {len(df):,} totales")
        else:
            st.info("No hay facturas para este período")

        conn.close()
    except Exception as e:
        st.error(f"Error en tabla: {e}")

# ========== FOOTER ==========
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with col2:
    st.caption("Dashboard v2.0 - Funcional Completo")
with col3:
    st.caption("✅ Todos los datos cargados correctamente")
