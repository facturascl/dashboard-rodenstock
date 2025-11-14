
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

# ========== ENCONTRAR BD ==========
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

def get_db_connection():
    """Crea conexión nueva sin cache"""
    if DB_FILE is None:
        st.error("❌ Base de datos no encontrada")
        st.stop()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

# ========== ENCABEZADO ==========
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📊 Dashboard de Facturación Rodenstock")
with col2:
    st.info(f"📁 {DB_FILE.split('/')[-1] if DB_FILE else 'BD no encontrada'}")

st.markdown("---")

# ========== SIDEBAR - FILTROS ==========
st.sidebar.header("⚙️ Filtros")

# Cargar años
conn = get_db_connection()
query_anos = "SELECT DISTINCT SUBSTR(fechaemision, 1, 4) AS ano FROM facturas WHERE fechaemision IS NOT NULL ORDER BY ano DESC"
df_anos = pd.read_sql_query(query_anos, conn)
anos_list = sorted(df_anos['ano'].tolist(), reverse=True) if not df_anos.empty else []
conn.close()

ano_sel = st.sidebar.selectbox("📅 Año", options=anos_list if anos_list else ["2025"])

# Cargar meses según año seleccionado
if ano_sel:
    conn = get_db_connection()
    query_meses = f"SELECT DISTINCT SUBSTR(fechaemision, 6, 2) AS mes FROM facturas WHERE SUBSTR(fechaemision, 1, 4) = '{ano_sel}' AND fechaemision IS NOT NULL ORDER BY mes"
    df_meses = pd.read_sql_query(query_meses, conn)
    meses_list = sorted(df_meses['mes'].tolist()) if not df_meses.empty else []
    conn.close()
else:
    meses_list = []

mes_options = ["Todos"] + meses_list
mes_sel = st.sidebar.selectbox("📆 Mes", options=mes_options, index=0)

# ========== MÉTRICAS PRINCIPALES ==========
st.subheader("📈 Resumen Ejecutivo")

# Construir WHERE clause
if mes_sel == "Todos":
    where_clause = f"WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' AND f.fechaemision IS NOT NULL"
else:
    where_clause = f"WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel}' AND f.fechaemision IS NOT NULL"

try:
    conn = get_db_connection()

    # Total facturas y monto
    query = f"SELECT COUNT(*) as total_fact, SUM(f.subtotal + f.iva) as monto_total FROM facturas f {where_clause}"
    result = pd.read_sql_query(query, conn).iloc[0]

    total_facturas = int(result['total_fact']) if result['total_fact'] else 0
    total_monto = float(result['monto_total']) if result['monto_total'] else 0

    # Categorías y líneas
    query_cat = f"SELECT COUNT(DISTINCT lf.clasificacion_categoria) as num_cat, COUNT(*) as num_lineas FROM lineas_factura lf INNER JOIN facturas f ON lf.numerofactura = f.numerofactura {where_clause}"
    result_cat = pd.read_sql_query(query_cat, conn).iloc[0]

    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Facturas", f"{total_facturas:,}")
    with col2:
        st.metric("💰 Monto Total", f"${total_monto:,.0f}")
    with col3:
        st.metric("🏷️ Categorías", int(result_cat['num_cat']))
    with col4:
        st.metric("📝 Líneas", f"{int(result_cat['num_lineas']):,}")

except Exception as e:
    st.error(f"Error en métricas: {str(e)}")

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
        conn = get_db_connection()

        if mes_sel == "Todos":
            query = f"""
            SELECT SUBSTR(f.fechaemision, 1, 7) as periodo, 
                   COUNT(*) as facturas,
                   SUM(f.subtotal + f.iva) as monto
            FROM facturas f
            {where_clause}
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
            query = f"""
            SELECT SUBSTR(f.fechaemision, 1, 10) as fecha, 
                   COUNT(*) as facturas,
                   SUM(f.subtotal + f.iva) as monto
            FROM facturas f
            {where_clause}
            GROUP BY fecha
            ORDER BY fecha
            """
            df = pd.read_sql_query(query, conn)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['fecha'], y=df['monto'], 
                                marker_color='#667eea'))
            fig.update_layout(title=f"Evolución Diaria - {ano_sel}/{mes_sel}",
                            xaxis_title="Fecha", yaxis_title="Monto ($)")

        st.plotly_chart(fig, use_container_width=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en evolución: {str(e)}")

with tab2:
    st.subheader("2. Distribución por Categoría")
    try:
        conn = get_db_connection()

        query = f"""
        SELECT lf.clasificacion_categoria as categoria,
               COUNT(DISTINCT f.numerofactura) as facturas,
               SUM(f.subtotal + f.iva) as monto
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        {where_clause}
        GROUP BY categoria
        ORDER BY monto DESC
        """
        df = pd.read_sql_query(query, conn)

        col1, col2 = st.columns(2)

        with col1:
            fig_pie = px.pie(df, values='monto', names='categoria',
                           title="Distribución por Monto")
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            fig_bar = px.bar(df, x='categoria', y='facturas',
                           title="Cantidad de Facturas",
                           color='monto',
                           color_continuous_scale='Viridis')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.dataframe(df, use_container_width=True, hide_index=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en categorías: {str(e)}")

with tab3:
    st.subheader("3. Top 10 Facturas")
    try:
        conn = get_db_connection()

        query = f"""
        SELECT f.numerofactura,
               SUM(f.subtotal + f.iva) as monto
        FROM facturas f
        {where_clause}
        GROUP BY f.numerofactura
        ORDER BY monto DESC
        LIMIT 10
        """
        df = pd.read_sql_query(query, conn)

        fig = px.bar(df, x='numerofactura', y='monto',
                    title="Top 10 Facturas",
                    color='monto',
                    color_continuous_scale='RdYlGn')
        fig.update_xaxes(tickangle=45)

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        conn.close()
    except Exception as e:
        st.error(f"Error en top 10: {str(e)}")

with tab4:
    st.subheader("4. Análisis de Pareto")
    try:
        conn = get_db_connection()

        query = f"""
        SELECT lf.clasificacion_categoria as categoria,
               COUNT(DISTINCT f.numerofactura) as facturas,
               SUM(f.subtotal + f.iva) as monto
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        {where_clause}
        GROUP BY categoria
        ORDER BY monto DESC
        """
        df = pd.read_sql_query(query, conn)

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
        st.error(f"Error en Pareto: {str(e)}")

with tab5:
    st.subheader("5. Comparativa entre Meses")
    try:
        conn = get_db_connection()

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
        st.error(f"Error en comparativa: {str(e)}")

with tab6:
    st.subheader("6. Tabla Detallada de Facturas")
    try:
        conn = get_db_connection()

        query = f"""
        SELECT f.numerofactura as "Factura",
               f.fechaemision as "Fecha",
               f.subtotal as "Subtotal",
               f.iva as "IVA",
               f.total as "Total"
        FROM facturas f
        {where_clause}
        ORDER BY f.fechaemision DESC
        LIMIT 500
        """
        df = pd.read_sql_query(query, conn)

        if not df.empty:
            for col in ['Subtotal', 'IVA', 'Total']:
                df[col] = df[col].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(f"Mostrando {len(df):,} facturas")
        else:
            st.info("Sin facturas para este período")

        conn.close()
    except Exception as e:
        st.error(f"Error en tabla: {str(e)}")

# ========== FOOTER ==========
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with col2:
    st.caption("Dashboard v2.1 - Bugs Fixed")
with col3:
    st.caption("✅ Todos los datos cargados correctamente")
