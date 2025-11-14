
import streamlit as st
import pandas as pd
import sqlite3

DB_FILE = './facturas.db'

st.set_page_config(page_title="Dashboard Debug", page_icon="🔍", layout="wide")

st.title("🔍 DEBUG Dashboard")
st.markdown("---")

def get_conn():
    return sqlite3.connect(DB_FILE)

# 1. AÑOS DISPONIBLES
st.header("1️⃣ Años Disponibles")
try:
    conn = get_conn()
    query = "SELECT DISTINCT SUBSTR(fechaemision, 1, 4) AS ano FROM facturas WHERE fechaemision IS NOT NULL ORDER BY ano DESC"
    df_anos = pd.read_sql_query(query, conn)
    conn.close()
    st.write(f"**Años encontrados:** {df_anos['ano'].tolist()}")
    anos_list = df_anos['ano'].tolist()
except Exception as e:
    st.error(f"Error: {e}")
    anos_list = ['2025', '2024']

# 2. MESES POR AÑO
st.header("2️⃣ Meses por Año")
ano_sel = st.selectbox("Selecciona año", options=anos_list)

try:
    conn = get_conn()
    query_meses = f"SELECT DISTINCT SUBSTR(fechaemision, 6, 2) AS mes, COUNT(*) as cantidad FROM facturas WHERE SUBSTR(fechaemision, 1, 4) = '{ano_sel}' AND fechaemision IS NOT NULL GROUP BY mes ORDER BY mes"
    df_meses = pd.read_sql_query(query_meses, conn)
    conn.close()
    st.write(f"**Meses en {ano_sel}:**")
    st.dataframe(df_meses, use_container_width=True, hide_index=True)
    meses_list = df_meses['mes'].tolist()
except Exception as e:
    st.error(f"Error: {e}")
    meses_list = []

# 3. CATEGORÍAS
st.header("3️⃣ Categorías Disponibles")
mes_options = ["Todos"] + meses_list
mes_sel = st.selectbox("Selecciona mes (opcional)", options=mes_options)

try:
    conn = get_conn()

    if mes_sel == "Todos":
        query_cat = f"""
        SELECT DISTINCT lf.clasificacion_categoria,
               COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
               ROUND(SUM(f.subtotal + f.iva), 2) as total
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}'
          AND f.fechaemision IS NOT NULL
          AND lf.clasificacion_categoria IS NOT NULL
        GROUP BY lf.clasificacion_categoria
        ORDER BY total DESC
        """
    else:
        query_cat = f"""
        SELECT DISTINCT lf.clasificacion_categoria,
               COUNT(DISTINCT f.numerofactura) as cantidad_facturas,
               ROUND(SUM(f.subtotal + f.iva), 2) as total
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        WHERE SUBSTR(f.fechaemision, 1, 4) = '{ano_sel}'
          AND SUBSTR(f.fechaemision, 6, 2) = '{mes_sel}'
          AND f.fechaemision IS NOT NULL
          AND lf.clasificacion_categoria IS NOT NULL
        GROUP BY lf.clasificacion_categoria
        ORDER BY total DESC
        """

    df_cat = pd.read_sql_query(query_cat, conn)
    conn.close()

    st.write(f"**Categorías en {ano_sel}/{mes_sel}:**")
    if not df_cat.empty:
        st.dataframe(df_cat, use_container_width=True, hide_index=True)
        st.success(f"✅ Encontradas {len(df_cat)} categorías")
    else:
        st.info("No hay categorías para este período")

except Exception as e:
    st.error(f"Error en categorías: {e}")

# 4. RESUMEN GENERAL
st.header("4️⃣ Resumen General")
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("Total Facturas", "13,663")
with col2: st.metric("Total Años", "4")
with col3: st.metric("Rango Fechas", "2022-2025")
with col4: st.metric("Líneas Factura", "69,904")

st.markdown("---")
st.success("✅ Si ves este dashboard sin errores, todo funciona correctamente")
