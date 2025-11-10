import streamlit as st
import pandas as pd
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime

st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def get_bigquery_client():
    try:
        if 'gcp_service_account' in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return bigquery.Client(credentials=credentials)
    except:
        pass
    try:
        credentials = service_account.Credentials.from_service_account_file(
            'bigquery-credentials.json'
        )
        return bigquery.Client(credentials=credentials)
    except:
        st.error("No se pudo cargar las credenciales de BigQuery")
        return None

@st.cache_data(ttl=600)
def get_resumen_mensual(ano=None, mes=None):
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    filtros = ["f.fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"EXTRACT(YEAR FROM f.fechaemision) = {ano}")
    if mes is not None:
        filtros.append(f"EXTRACT(MONTH FROM f.fechaemision) = {mes}")
    where_clause = " AND ".join(filtros)
    
    query = f"""
    WITH datos AS (
      SELECT
        EXTRACT(YEAR FROM f.fechaemision) AS ano,
        EXTRACT(MONTH FROM f.fechaemision) AS mes,
        CONCAT(
          COALESCE(lf.clasificacion_categoria, 'Sin Clasificar'),
          ' - ',
          COALESCE(lf.clasificacion_subcategoria, '')
        ) AS categoria,
        COUNT(DISTINCT lf.numerofactura) AS cantidad_trabajos,
        SUM(CAST(lf.total_linea AS FLOAT64)) AS total_dinero
      FROM `rodenstock-471300.facturacion.lineas_factura` lf
      JOIN `rodenstock-471300.facturacion.facturas` f
        ON lf.numerofactura = f.numerofactura
      WHERE {where_clause}
      GROUP BY ano, mes, categoria
    ),
    total_general AS (
      SELECT SUM(cantidad_trabajos) AS total_trabajos
      FROM datos
    )
    SELECT
      d.ano,
      d.mes,
      d.categoria,
      d.cantidad_trabajos,
      d.total_dinero,
      ROUND(d.total_dinero / d.cantidad_trabajos, 0) AS promedio_trabajo,
      ROUND((d.cantidad_trabajos * 100.0) / tg.total_trabajos, 2) AS porcentaje
    FROM datos d
    CROSS JOIN total_general tg
    ORDER BY d.ano DESC, d.mes DESC, d.total_dinero DESC
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_evolucion_mensual():
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    query = """
    SELECT
      FORMAT_DATE('%Y-%m', f.fechaemision) AS mes,
      CONCAT(
        COALESCE(lf.clasificacion_categoria, 'Sin Clasificar'),
        ' - ',
        COALESCE(lf.clasificacion_subcategoria, '')
      ) AS categoria,
      COUNT(DISTINCT lf.numerofactura) AS cantidad_trabajos,
      SUM(CAST(lf.total_linea AS FLOAT64)) AS total_dinero
    FROM `rodenstock-471300.facturacion.lineas_factura` lf
    JOIN `rodenstock-471300.facturacion.facturas` f
      ON lf.numerofactura = f.numerofactura
    WHERE f.fechaemision IS NOT NULL
    GROUP BY mes, categoria
    ORDER BY mes DESC
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_totales_generales(ano=None, mes=None):
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    filtros = ["fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"EXTRACT(YEAR FROM fechaemision) = {ano}")
    if mes is not None:
        filtros.append(f"EXTRACT(MONTH FROM fechaemision) = {mes}")
    where_clause = " AND ".join(filtros)
    query = f"""
    SELECT
      COUNT(DISTINCT numerofactura) AS total_facturas,
      SUM(CAST(COALESCE(valorneto, 0) AS FLOAT64) + CAST(COALESCE(iva, 0) AS FLOAT64)) AS total_ingresos,
      AVG(CAST(COALESCE(valorneto, 0) AS FLOAT64) + CAST(COALESCE(iva, 0) AS FLOAT64)) AS promedio_factura
    FROM `rodenstock-471300.facturacion.facturas`
    WHERE {where_clause}
    """
    return client.query(query).to_dataframe()

st.title("📊 Dashboard de Facturacion Rodenstock")
st.markdown("---")

with st.sidebar:
    st.header("Filtros")
    anos_disponibles = list(range(2023, datetime.now().year + 1))
    ano_seleccionado = st.selectbox(
        "Año",
        options=anos_disponibles,
        index=len(anos_disponibles) - 1
    )
    meses = {
        None: "Todos",
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    mes_seleccionado = st.selectbox(
        "Mes",
        options=list(meses.keys()),
        format_func=lambda x: meses[x],
        index=0
    )
    st.markdown("---")
    if st.button("Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

st.header("Resumen General")

try:
    totales = get_totales_generales(ano_seleccionado, mes_seleccionado)
    if not totales.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="Total Trabajos",
                value=f"{int(totales['total_facturas'].iloc[0]):,}"
            )
        with col2:
            st.metric(
                label="Ingresos Totales",
                value=f"${int(totales['total_ingresos'].iloc[0]):,}"
            )
        with col3:
            st.metric(
                label="Promedio por Trabajo",
                value=f"${int(totales['promedio_factura'].iloc[0]):,}"
            )
        st.markdown("---")
        df_resumen = get_resumen_mensual(ano_seleccionado, mes_seleccionado)
        if not df_resumen.empty:
            tab1, tab2, tab3 = st.tabs(["Distribucion", "Evolucion", "Detalle"])
            with tab1:
                st.subheader("Distribucion por Categoria")
                col1, col2 = st.columns([2, 1])
                with col1:
                    fig_barras = px.bar(
                        df_resumen.sort_values('total_dinero', ascending=False).head(15),
                        x='categoria',
                        y='cantidad_trabajos',
                        color='categoria',
                        title='Top 15 Categorias por Cantidad de Trabajos',
                        labels={'cantidad_trabajos': 'Cantidad', 'categoria': 'Categoria'},
                        height=500
                    )
                    fig_barras.update_layout(showlegend=False, xaxis_tickangle=-45)
                    st.plotly_chart(fig_barras, use_container_width=True)
                with col2:
                    fig_pie = px.pie(
                        df_resumen.head(10),
                        values='total_dinero',
                        names='categoria',
                        title='Distribucion de Ingresos (Top 10)',
                        height=500
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
            with tab2:
                st.subheader("Evolucion Mensual")
                df_evolucion = get_evolucion_mensual()
                if not df_evolucion.empty:
                    df_evolucion['promedio_trabajo'] = df_evolucion['total_dinero'] / df_evolucion['cantidad_trabajos']
                    fig_lineas = px.line(
                        df_evolucion,
                        x='mes',
                        y='cantidad_trabajos',
                        color='categoria',
                        title='Evolucion de Trabajos por Mes',
                        labels={'cantidad_trabajos': 'Cantidad', 'mes': 'Mes'},
                        height=450,
                        markers=True
                    )
                    st.plotly_chart(fig_lineas, use_container_width=True)
                    fig_area = px.area(
                        df_evolucion,
                        x='mes',
                        y='total_dinero',
                        color='categoria',
                        title='Evolucion de Ingresos por Mes',
                        labels={'total_dinero': 'Ingresos', 'mes': 'Mes'},
                        height=450
                    )
                    st.plotly_chart(fig_area, use_container_width=True)
                else:
                    st.warning("No hay datos de evolucion disponibles.")
            with tab3:
                st.subheader("Tabla Detallada")
                df_display = df_resumen.copy()
                df_display['total_dinero'] = df_display['total_dinero'].apply(lambda x: f"${x:,.0f}")
                df_display['promedio_trabajo'] = df_display['promedio_trabajo'].apply(lambda x: f"${x:,.0f}")
                df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.2f}%")
                df_display.columns = ['Año', 'Mes', 'Categoria', 'Cantidad Trabajos', 'Total Ingresos', 'Promedio por Trabajo', 'Porcentaje']
                st.dataframe(df_display, use_container_width=True, height=600)
                csv = df_resumen.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Descargar CSV",
                    data=csv,
                    file_name=f'rodenstock_{datetime.now().strftime("%Y%m%d")}.csv',
                    mime='text/csv',
                )
        else:
            st.warning("No hay datos disponibles para los filtros seleccionados.")
    else:
        st.warning("No hay datos disponibles.")
except Exception as e:
    st.error(f"Error al cargar los datos: {str(e)}")
    st.info("Asegurate de que las credenciales de BigQuery esten configuradas correctamente.")

st.markdown("---")
st.caption("Dashboard desarrollado con Streamlit | Datos desde BigQuery | (c) 2025 Rodenstock")
