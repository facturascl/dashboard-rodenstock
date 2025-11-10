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
        st.error("Asegurate de que:")
        st.markdown("""
        - El archivo `bigquery-credentials.json` este en la misma carpeta que `app.py`
        - Las credenciales tengan permisos de lectura en BigQuery
        - La conexion a internet este activa
        """)
        return None

client = get_bigquery_client()
if client is None:
    st.stop()

# Sidebar con filtros
st.sidebar.header("Filtros")

# Filtro de año usando fechaemision
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

meses = {
    "Todos": None,
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
    "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
    "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
}
mes_seleccionado = st.sidebar.selectbox("Mes", options=list(meses.keys()))

# Filtro de categorias - usando la tabla correcta
categorias_query = """
SELECT DISTINCT categoria
FROM `rodenstock-471300.facturacion.analisis_categorias`
ORDER BY categoria
"""
categorias_disponibles = client.query(categorias_query).to_dataframe()
categorias_seleccionadas = st.sidebar.multiselect(
    "Categorias",
    options=categorias_disponibles['categoria'].tolist(),
    default=categorias_disponibles['categoria'].tolist()
)

incluir_sin_clasificar = st.sidebar.checkbox("Incluir facturas sin clasificar", value=False)

# Construir filtros
filtro_fecha = f"EXTRACT(YEAR FROM ventas.fechaemision) = {anio_seleccionado}"
if meses[mes_seleccionado] is not None:
    filtro_fecha += f" AND EXTRACT(MONTH FROM ventas.fechaemision) = {meses[mes_seleccionado]}"

# Filtro de categorias
if categorias_seleccionadas:
    categorias_str = "', '".join(categorias_seleccionadas)
    filtro_categorias = f"AND categorias.categoria IN ('{categorias_str}')"
else:
    filtro_categorias = ""

if incluir_sin_clasificar:
    filtro_categorias += " OR categorias.categoria IS NULL"

# Query principal usando vista_analisis_categorias y fechaemision
query_principal = f"""
SELECT
  categorias.categoria,
  SUM(CAST(ventas.cantidad AS INT64)) AS cantidad_total,
  ROUND(SAFE_DIVIDE(
    SUM(CAST(ventas.cantidad AS INT64)),
    (SELECT SUM(CAST(cantidad AS INT64))
     FROM `rodenstock-471300.facturacion.vista_analisis_categorias`
     WHERE EXTRACT(YEAR FROM fechaemision) = {anio_seleccionado}
     {f"AND EXTRACT(MONTH FROM fechaemision) = {meses[mes_seleccionado]}" if meses[mes_seleccionado] else ""})
  ) * 100, 2) AS porcentaje
FROM
  `rodenstock-471300.facturacion.vista_analisis_categorias` AS ventas
LEFT JOIN
  `rodenstock-471300.facturacion.analisis_categorias` AS categorias
ON
  ventas.categoria = categorias.categoria_original
WHERE
  {filtro_fecha}
  {filtro_categorias}
GROUP BY
  categorias.categoria
ORDER BY
  cantidad_total DESC
"""

df_datos = client.query(query_principal).to_dataframe()

st.header("Resumen General")

if not df_datos.empty:
    col1, col2, col3 = st.columns(3)

    with col1:
        total_unidades = df_datos['cantidad_total'].sum()
        st.metric("Total de Unidades", f"{total_unidades:,}")
    with col2:
        total_categorias = len(df_datos)
        st.metric("Categorias", total_categorias)
    with col3:
        categoria_top = df_datos.iloc[0]['categoria'] if len(df_datos) > 0 else "N/A"
        st.metric("Categoria Top", categoria_top)

    st.subheader("Distribucion por Categoria")
    fig_barras = px.bar(
        df_datos,
        x='categoria',
        y='cantidad_total',
        text='porcentaje',
        title='Cantidad de Unidades por Categoria',
        labels={'categoria': 'Categoria', 'cantidad_total': 'Cantidad'},
        color='cantidad_total',
        color_continuous_scale='Blues'
    )
    fig_barras.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_barras.update_layout(height=500)
    st.plotly_chart(fig_barras, use_container_width=True)

    st.subheader("Distribucion Porcentual")
    fig_torta = px.pie(
        df_datos,
        values='cantidad_total',
        names='categoria',
        title='Distribucion Porcentual por Categoria',
        hole=0.4
    )
    fig_torta.update_traces(textposition='inside', textinfo='percent+label')
    fig_torta.update_layout(height=500)
    st.plotly_chart(fig_torta, use_container_width=True)

    st.subheader("Detalle por Categoria")
    df_display = df_datos.copy()
    df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.2f}%")
    df_display.columns = ['Categoria', 'Cantidad Total', 'Porcentaje']
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
    st.info("""
    Asegurate de que:
    - El archivo `bigquery-credentials.json` este en la misma carpeta que `app.py`
    - Las credenciales tengan permisos de lectura en BigQuery
    - La conexion a internet este activa
    """)

st.markdown("---")
st.markdown("Dashboard desarrollado con Streamlit | Datos desde BigQuery | (c) 2025 Rodenstock")
