import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from google.oauth2 import service_account
import json

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Facturación Rodenstock",
    page_icon="📊",
    layout="wide"
)

# Título del dashboard
st.title("📊 Dashboard de Facturación Rodenstock")

# Función para cargar credenciales y conectar a BigQuery
@st.cache_resource
def get_bigquery_client():
    """Crea y retorna el cliente de BigQuery usando las credenciales de secrets"""
    try:
        # Verificar si el archivo existe localmente (para desarrollo)
        try:
            credentials = service_account.Credentials.from_service_account_file(
                'bigquery-credentials.json'
            )
        except FileNotFoundError:
            # Si no existe el archivo, usar secrets de Streamlit Cloud
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
        
        client = bigquery.Client(
            credentials=credentials,
            project=credentials.project_id
        )
        return client
    except Exception as e:
        st.error(f"❌ Error al cargar los datos: {e}")
        st.error("Asegúrate de que:")
        st.markdown("""
        - El archivo `bigquery-credentials.json` esté en la misma carpeta que `app.py`
        - Las credenciales tengan permisos de lectura en BigQuery
        - La conexión a internet esté activa
        """)
        return None

# Conectar a BigQuery
client = get_bigquery_client()

if client is None:
    st.stop()

# Sidebar con filtros
st.sidebar.header("🔍 Filtros")

# Filtro de año
año_query = """
SELECT DISTINCT EXTRACT(YEAR FROM fecha) as año
FROM `rodenstock-471300.facturacion.facturas`
ORDER BY año DESC
"""
años_disponibles = client.query(año_query).to_dataframe()
año_seleccionado = st.sidebar.selectbox(
    "Año",
    options=años_disponibles['año'].tolist(),
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

# Filtro de categorías
categorias_query = """
SELECT DISTINCT categoria
FROM `rodenstock-471300.facturacion.categorias`
ORDER BY categoria
"""
categorias_disponibles = client.query(categorias_query).to_dataframe()
categorias_seleccionadas = st.sidebar.multiselect(
    "Categorías",
    options=categorias_disponibles['categoria'].tolist(),
    default=categorias_disponibles['categoria'].tolist()
)

# Checkbox para incluir facturas sin clasificar
incluir_sin_clasificar = st.sidebar.checkbox("Incluir facturas sin clasificar", value=False)

# Construir filtro SQL
filtro_fecha = f"EXTRACT(YEAR FROM f.fecha) = {año_seleccionado}"
if meses[mes_seleccionado] is not None:
    filtro_fecha += f" AND EXTRACT(MONTH FROM f.fecha) = {meses[mes_seleccionado]}"

# Query principal con porcentajes corregidos
query_principal = f"""
SELECT
  categorias.categoria,
  SUM(CAST(ventas.cantidad AS INT64)) AS cantidad_total,
  ROUND(SAFE_DIVIDE(
    SUM(CAST(ventas.cantidad AS INT64)), 
    (SELECT SUM(CAST(cantidad AS INT64)) 
     FROM `rodenstock-471300.facturacion.vista_ventas_por_categoria`
     WHERE EXTRACT(YEAR FROM fecha) = {año_seleccionado}
     {f"AND EXTRACT(MONTH FROM fecha) = {meses[mes_seleccionado]}" if meses[mes_seleccionado] else ""})
  ) * 100, 2) AS porcentaje
FROM
  `rodenstock-471300.facturacion.vista_ventas_por_categoria` AS ventas
LEFT JOIN
  `rodenstock-471300.facturacion.categorias` AS categorias
ON
  ventas.categoria = categorias.categoria_original
WHERE
  {filtro_fecha}
  {f"AND categorias.categoria IN ({','.join([f'\\'{c}\\'' for c in categorias_seleccionadas])})" if categorias_seleccionadas else ""}
  {f"OR categorias.categoria IS NULL" if incluir_sin_clasificar else ""}
GROUP BY
  categorias.categoria
ORDER BY
  cantidad_total DESC
"""

# Ejecutar query
df_datos = client.query(query_principal).to_dataframe()

# Mostrar resumen general
st.header("📈 Resumen General")

if not df_datos.empty:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_unidades = df_datos['cantidad_total'].sum()
        st.metric("Total de Unidades", f"{total_unidades:,}")
    
    with col2:
        total_categorias = len(df_datos)
        st.metric("Categorías", total_categorias)
    
    with col3:
        categoria_top = df_datos.iloc[0]['categoria'] if len(df_datos) > 0 else "N/A"
        st.metric("Categoría Top", categoria_top)
    
    # Gráfico de barras - Distribución por categoría
    st.subheader("📊 Distribución por Categoría")
    
    fig_barras = px.bar(
        df_datos,
        x='categoria',
        y='cantidad_total',
        text='porcentaje',
        title='Cantidad de Unidades por Categoría',
        labels={'categoria': 'Categoría', 'cantidad_total': 'Cantidad'},
        color='cantidad_total',
        color_continuous_scale='Blues'
    )
    
    fig_barras.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_barras.update_layout(height=500)
    st.plotly_chart(fig_barras, use_container_width=True)
    
    # Gráfico de torta - Porcentajes
    st.subheader("🥧 Distribución Porcentual")
    
    fig_torta = px.pie(
        df_datos,
        values='cantidad_total',
        names='categoria',
        title='Distribución Porcentual por Categoría',
        hole=0.4
    )
    
    fig_torta.update_traces(textposition='inside', textinfo='percent+label')
    fig_torta.update_layout(height=500)
    st.plotly_chart(fig_torta, use_container_width=True)
    
    # Tabla de datos
    st.subheader("📋 Detalle por Categoría")
    
    df_display = df_datos.copy()
    df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.2f}%")
    df_display.columns = ['Categoría', 'Cantidad Total', 'Porcentaje']
    
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )
    
    # Botón para actualizar datos
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.cache_resource.clear()
        st.rerun()

else:
    st.warning("⚠️ No hay datos disponibles para los filtros seleccionados.")
    st.info("""
    💡 Asegúrate de que:
    - El archivo `bigquery-credentials.json` esté en la misma carpeta que `app.py`
    - Las credenciales tengan permisos de lectura en BigQuery
    - La conexión a internet esté activa
    """)

# Footer
st.markdown("---")
st.markdown("Dashboard desarrollado con Streamlit | Datos desde BigQuery | © 2025 Rodenstock")
