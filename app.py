
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import os
from datetime import datetime

st.set_page_config(
    page_title="Dashboard Rodenstock",
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
st.title("📊 Dashboard de Facturación Rodenstock")

# ========== SIDEBAR - FILTROS ==========
st.sidebar.header("⚙️ Filtros")

conn = get_db_connection()
query_anos = "SELECT DISTINCT SUBSTR(fechaemision, 1, 4) AS ano FROM facturas WHERE fechaemision IS NOT NULL ORDER BY ano DESC"
df_anos = pd.read_sql_query(query_anos, conn)
anos_list = sorted(df_anos['ano'].tolist(), reverse=True) if not df_anos.empty else []
conn.close()

ano_sel = st.sidebar.selectbox("📅 Año", options=anos_list if anos_list else ["2025"])

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

# ========== WHERE CLAUSE ==========
if mes_sel == "Todos":
    where_clause = f"WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' AND f.fechaemision IS NOT NULL"
else:
    where_clause = f"WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}' AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel}' AND f.fechaemision IS NOT NULL"

# ========== TABS: Solo Evolución + Tabla ==========
tab1, tab2 = st.tabs(["📊 Evolución Temporal", "📋 Tabla Detallada"])

with tab1:
    st.subheader("Evolución Temporal de Ingresos")
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

        if not df.empty:
            if mes_sel == "Todos":
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['periodo'], y=df['monto'], 
                                        mode='lines+markers', name='Monto',
                                        line=dict(color='#667eea', width=3)))
                fig.update_layout(title="Evolución Mensual de Ingresos",
                                xaxis_title="Mes", yaxis_title="Monto ($)",
                                hovermode='x unified')
            else:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df['fecha'], y=df['monto'], 
                                    marker_color='#667eea'))
                fig.update_layout(title=f"Evolución Diaria - {ano_sel}/{mes_sel}",
                                xaxis_title="Fecha", yaxis_title="Monto ($)")

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos para este período")

        conn.close()
    except Exception as e:
        st.error(f"Error en evolución: {str(e)}")

with tab2:
    st.subheader("Tabla Detallada de Facturas")
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
        """
        df = pd.read_sql_query(query, conn)

        if not df.empty:
            for col in ['Subtotal', 'IVA', 'Total']:
                df[col] = df[col].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(f"Total: {len(df):,} facturas")
        else:
            st.info("Sin facturas para este período")

        conn.close()
    except Exception as e:
        st.error(f"Error en tabla: {str(e)}")

# ========== FOOTER ==========
st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
