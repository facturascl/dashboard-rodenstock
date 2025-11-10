import streamlit as st
import pandas as pd
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account

st.set_page_config(page_title="Dashboard de Facturacion Rodenstock", page_icon="📊", layout="wide")
st.title("📊 Dashboard de Facturacion Rodenstock")

@st.cache_resource
def get_bigquery_client():
    try:
        try:
            credentials = service_account.Credentials.from_service_account_file(
                'bigquery-credentials.json'
            )
        except FileNotFoundError:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
        client = bigquery.Client(
            credentials=credentials,
            project=credentials.project_id
        )
        return client
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return None

client = get_bigquery_client()
if client is None:
    st.stop()

# Sidebar con filtros
st.sidebar.header("Filtros")

# Filtro de año
anio_query = """
SELECT DISTINCT EXTRACT(YEAR FROM fechaemision) AS anio
FROM `rodenstock-471300.facturacion.facturas`
ORDER BY anio DESC
"""
anios_disponibles = client.query(anio_query).to_dataframe()
anio_seleccionado = st.sidebar.selectbox(
    "Año",
    options=anios_disponibles['anio'].tolist(),
    index=0
)

# Filtro de mes
meses = {
    "Todos": None,
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
    "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
    "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
}
mes_seleccionado = st.sidebar.selectbox("Mes", options=list(meses.keys()))

# Query simple: contar facturas por producto
query_datos = f"""
SELECT
  producto AS categoria,
  COUNT(*) AS cantidad
FROM
  `rodenstock-471300.facturacion.lineas_factura`
WHERE
  EXTRACT(YEAR FROM fechaemision) = {anio_seleccionado}
  {f"AND EXTRACT(MONTH FROM fechaemision) = {meses[mes_seleccionado]}" if meses[mes_seleccionado] else ""}
GROUP BY
  producto
ORDER BY
  cantidad DESC
"""

df_datos = client.query(query_datos).to_dataframe()

st.header("Resumen General")

if not df_datos.empty:
    col1, col2, col3 = st.columns(3)

    with col1:
        total_lineas = df_datos['cantidad'].sum()
        st.metric("Total de Lineas", f"{total_lineas:,}")
    with col2:
        total_productos = len(df_datos)
        st.metric("Productos Unicos", total_productos)
    with col3:
        producto_top = df_datos.iloc[0]['categoria'] if len(df_datos) > 0 else "N/A"
        st.metric("Producto Top", producto_top)

    st.subheader("Distribucion por Producto")
    fig_barras = px.bar(
        df_datos.head(15),
        x='categoria',
        y='cantidad',
        title='Top 15 Productos',
        labels={'categoria': 'Producto', 'cantidad': 'Cantidad'},
        color='cantidad',
        color_continuous_scale='Blues'
    )
    fig_barras.update_layout(height=500, xaxis_tickangle=-45)
    st.plotly_chart(fig_barras, use_container_width=True)

    st.subheader("Distribucion Porcentual (Top 10)")
    fig_torta = px.pie(
        df_datos.head(10),
        values='cantidad',
        names='categoria',
        title='Top 10 Productos',
        hole=0.4
    )
    fig_torta.update_traces(textposition='inside', textinfo='percent+label')
    fig_torta.update_layout(height=500)
    st.plotly_chart(fig_torta, use_container_width=True)

    st.subheader("Detalle Completo")
    df_display = df_datos.copy()
    df_display.columns = ['Producto', 'Cantidad']
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("Actualizar Datos"):
        st.cache_resource.clear()
        st.rerun()

else:
    st.warning("No hay datos disponibles para los filtros seleccionados.")

st.markdown("---")
st.markdown("Dashboard desarrollado con Streamlit | Datos desde BigQuery | (c) 2025 Rodenstock")
