import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
def get_datos_unificados(ano=None, mes=None):
    """
    FUENTE UNICA DE VERDAD para tabla y gráficos
    SIN porcentaje en evolución (solo para vista detallada)
    """
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    
    filtros = ["f.fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"EXTRACT(YEAR FROM f.fechaemision) = {ano}")
    if mes is not None:
        filtros.append(f"EXTRACT(MONTH FROM f.fechaemision) = {mes}")
    where_clause = " AND ".join(filtros)
    
    # QUERY UNIFICADA - Sin porcentaje en evolución
    query = f"""
    SELECT
      EXTRACT(YEAR FROM f.fechaemision) AS ano,
      EXTRACT(MONTH FROM f.fechaemision) AS mes,
      FORMAT_DATE('%Y-%m', f.fechaemision) AS mes_formato,
      CONCAT(
        COALESCE(lf.clasificacion_categoria, 'Sin Clasificar'),
        ' - ',
        COALESCE(lf.clasificacion_subcategoria, '')
      ) AS categoria,
      COUNT(DISTINCT lf.numerofactura) AS cantidad_trabajos,
      ROUND(SUM(CAST(lf.total_linea AS FLOAT64) * 1.19), 0) AS total_dinero
    FROM `rodenstock-471300.facturacion.lineas_factura` lf
    JOIN `rodenstock-471300.facturacion.facturas` f
      ON lf.numerofactura = f.numerofactura
    WHERE {where_clause}
    GROUP BY ano, mes, mes_formato, categoria
    ORDER BY mes_formato ASC, categoria
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_datos_detalle_con_porcentaje(ano=None, mes=None):
    """
    Datos para tabla detallada CON porcentaje
    Solo se calcula cuando hay filtro específico
    """
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    
    filtros = ["f.fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"EXTRACT(YEAR FROM f.fechaemision) = {ano}")
    if mes is not None:
        filtros.append(f"EXTRACT(MONTH FROM f.fechaemision) = {mes}")
    where_clause = " AND ".join(filtros)
    
    # Query CON porcentaje para tabla detallada
    query = f"""
    WITH datos_base AS (
      SELECT
        EXTRACT(YEAR FROM f.fechaemision) AS ano,
        EXTRACT(MONTH FROM f.fechaemision) AS mes,
        FORMAT_DATE('%Y-%m', f.fechaemision) AS mes_formato,
        CONCAT(
          COALESCE(lf.clasificacion_categoria, 'Sin Clasificar'),
          ' - ',
          COALESCE(lf.clasificacion_subcategoria, '')
        ) AS categoria,
        COUNT(DISTINCT lf.numerofactura) AS cantidad_trabajos,
        ROUND(SUM(CAST(lf.total_linea AS FLOAT64) * 1.19), 0) AS total_dinero
      FROM `rodenstock-471300.facturacion.lineas_factura` lf
      JOIN `rodenstock-471300.facturacion.facturas` f
        ON lf.numerofactura = f.numerofactura
      WHERE {where_clause}
      GROUP BY ano, mes, mes_formato, categoria
    ),
    total_general AS (
      SELECT SUM(cantidad_trabajos) AS total_trabajos
      FROM datos_base
    )
    SELECT
      d.ano,
      d.mes,
      d.mes_formato,
      d.categoria,
      d.cantidad_trabajos,
      d.total_dinero,
      ROUND(d.total_dinero / d.cantidad_trabajos, 0) AS promedio_trabajo,
      ROUND((d.cantidad_trabajos * 100.0) / tg.total_trabajos, 2) AS porcentaje
    FROM datos_base d
    CROSS JOIN total_general tg
    ORDER BY d.ano DESC, d.mes DESC, d.total_dinero DESC
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_distribucion_mensual_anual(ano):
    """Obtiene distribucion mensual del año seleccionado para grafico de torta"""
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    query = f"""
    WITH datos_mensuales AS (
      SELECT
        FORMAT_DATE('%Y-%m', f.fechaemision) AS mes,
        ROUND(SUM(CAST(COALESCE(f.valorneto, 0) AS FLOAT64) + CAST(COALESCE(f.iva, 0) AS FLOAT64)), 0) AS total_mes
      FROM `rodenstock-471300.facturacion.facturas` f
      WHERE EXTRACT(YEAR FROM f.fechaemision) = {ano}
        AND f.fechaemision IS NOT NULL
      GROUP BY mes
    ),
    total_anual AS (
      SELECT SUM(total_mes) AS total_ano
      FROM datos_mensuales
    )
    SELECT
      dm.mes,
      dm.total_mes,
      ROUND((dm.total_mes * 100.0) / ta.total_ano, 1) AS porcentaje
    FROM datos_mensuales dm
    CROSS JOIN total_anual ta
    ORDER BY dm.mes ASC
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_facturas_vs_notas():
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    query = """
    SELECT
      FORMAT_DATE('%Y-%m', fechaemision) AS mes,
      COUNTIF(numerofactura LIKE 'F%' OR numerofactura NOT LIKE 'N%') AS cantidad_facturas,
      COUNTIF(numerofactura LIKE 'N%') AS cantidad_notas,
      ROUND(SUM(CAST(COALESCE(valorneto, 0) AS FLOAT64) + CAST(COALESCE(iva, 0) AS FLOAT64)), 0) AS total_mes,
      ROUND(AVG(CAST(COALESCE(valorneto, 0) AS FLOAT64) + CAST(COALESCE(iva, 0) AS FLOAT64)), 0) AS promedio_mes
    FROM `rodenstock-471300.facturacion.facturas`
    WHERE fechaemision IS NOT NULL
    GROUP BY mes
    ORDER BY mes ASC
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
      ROUND(SUM(CAST(COALESCE(valorneto, 0) AS FLOAT64) + CAST(COALESCE(iva, 0) AS FLOAT64)), 0) AS total_ingresos,
      ROUND(AVG(CAST(COALESCE(valorneto, 0) AS FLOAT64) + CAST(COALESCE(iva, 0) AS FLOAT64)), 0) AS promedio_factura
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
        
        # DATOS PARA EVOLUCIÓN (sin porcentaje)
        df_datos = get_datos_unificados(ano_seleccionado, mes_seleccionado)
        
        # DATOS PARA TABLA DETALLADA (con porcentaje)
        df_detalle = get_datos_detalle_con_porcentaje(ano_seleccionado, mes_seleccionado)
        
        if not df_datos.empty:
            tab1, tab2, tab3 = st.tabs(["Distribucion", "Evolucion", "Detalle"])
            
            # TAB 1: DISTRIBUCION
            with tab1:
                st.subheader("Distribucion por Categoria")
                col1, col2 = st.columns([2, 1])
                with col1:
                    fig_barras = px.bar(
                        df_datos.sort_values('total_dinero', ascending=False).head(15),
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
                        df_datos.head(10),
                        values='total_dinero',
                        names='categoria',
                        title='Distribucion de Ingresos (Top 10)',
                        height=500
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                # Grafico: Facturas vs Notas de Credito por mes
                st.subheader("Facturas vs Notas de Credito por Mes")
                df_fac_notas = get_facturas_vs_notas()
                if not df_fac_notas.empty:
                    fig_combo = go.Figure()
                    fig_combo.add_trace(go.Bar(
                        x=df_fac_notas['mes'],
                        y=df_fac_notas['cantidad_facturas'],
                        name='Facturas',
                        marker_color='#3b82f6',
                        hovertemplate='<b>Facturas</b><br>Mes: %{x}<br>Cantidad: %{y}<extra></extra>'
                    ))
                    fig_combo.add_trace(go.Bar(
                        x=df_fac_notas['mes'],
                        y=df_fac_notas['cantidad_notas'],
                        name='Notas de Credito',
                        marker_color='#ef4444',
                        hovertemplate='<b>Notas de Crédito</b><br>Mes: %{x}<br>Cantidad: %{y}<extra></extra>'
                    ))
                    fig_combo.add_trace(go.Scatter(
                        x=df_fac_notas['mes'],
                        y=df_fac_notas['promedio_mes'],
                        name='Promedio Mensual',
                        yaxis='y2',
                        line=dict(color='#059669', width=3),
                        mode='lines+markers',
                        hovertemplate='<b>Promedio Mensual</b><br>Mes: %{x}<br>Promedio: $%{y:,.0f}<extra></extra>'
                    ))
                    fig_combo.update_layout(
                        title='Cantidad de Facturas y Notas vs Promedio Mensual',
                        xaxis_title='Mes',
                        yaxis_title='Cantidad',
                        yaxis2=dict(
                            title='Promedio ($)',
                            overlaying='y',
                            side='right'
                        ),
                        barmode='group',
                        height=500,
                        hovermode='closest'
                    )
                    st.plotly_chart(fig_combo, use_container_width=True)
                
                # Grafico de distribucion mensual (torta)
                st.subheader(f"Distribucion Mensual del Año {ano_seleccionado}")
                df_dist_mensual = get_distribucion_mensual_anual(ano_seleccionado)
                if not df_dist_mensual.empty:
                    fig_pie_mensual = px.pie(
                        df_dist_mensual,
                        values='total_mes',
                        names='mes',
                        title=f'Porcentaje que Representa Cada Mes del Total Anual {ano_seleccionado}',
                        height=600
                    )
                    fig_pie_mensual.update_traces(
                        textposition='inside',
                        textinfo='percent+label',
                        hovertemplate='<b>%{label}</b><br>Total: $%{value:,.0f}<br>Porcentaje: %{percent}<extra></extra>'
                    )
                    st.plotly_chart(fig_pie_mensual, use_container_width=True)
            
            # TAB 2: EVOLUCION (datos absolutos, sin porcentaje relativo)
            with tab2:
                st.subheader("Evolucion Mensual")
                st.info("📊 Los gráficos de evolución muestran valores absolutos por mes y categoría (no porcentajes relativos)")
                
                # Grafico 1: Cantidad de trabajos
                fig_trabajos = px.line(
                    df_datos,
                    x='mes_formato',
                    y='cantidad_trabajos',
                    color='categoria',
                    title='Cantidad de Trabajos por Mes',
                    labels={'cantidad_trabajos': 'Cantidad', 'mes_formato': 'Mes'},
                    height=450,
                    markers=True
                )
                df_datos['promedio_trabajo'] = (df_datos['total_dinero'] / df_datos['cantidad_trabajos']).round(0)
                fig_trabajos.update_traces(
                    customdata=df_datos[['total_dinero', 'promedio_trabajo']],
                    hovertemplate='<b>%{fullData.name}</b><br>Mes: %{x}<br>Cantidad: %{y}<br>Total: $%{customdata[0]:,.0f}<br>Promedio: $%{customdata[1]:,.0f}<extra></extra>'
                )
                st.plotly_chart(fig_trabajos, use_container_width=True)
                
                # Grafico 2: Total por mes
                fig_total = px.line(
                    df_datos,
                    x='mes_formato',
                    y='total_dinero',
                    color='categoria',
                    title='Total de Ingresos por Mes',
                    labels={'total_dinero': 'Ingresos', 'mes_formato': 'Mes'},
                    height=450,
                    markers=True
                )
                fig_total.update_traces(
                    customdata=df_datos[['cantidad_trabajos', 'promedio_trabajo']],
                    hovertemplate='<b>%{fullData.name}</b><br>Mes: %{x}<br>Total: $%{y:,.0f}<br>Cantidad: %{customdata[0]}<br>Promedio: $%{customdata[1]:,.0f}<extra></extra>'
                )
                st.plotly_chart(fig_total, use_container_width=True)
                
                # Grafico 3: Promedio por trabajo
                fig_promedio = px.line(
                    df_datos,
                    x='mes_formato',
                    y='promedio_trabajo',
                    color='categoria',
                    title='Promedio por Trabajo',
                    labels={'promedio_trabajo': 'Promedio ($)', 'mes_formato': 'Mes'},
                    height=450,
                    markers=True
                )
                fig_promedio.update_traces(
                    customdata=df_datos[['cantidad_trabajos', 'total_dinero']],
                    hovertemplate='<b>%{fullData.name}</b><br>Mes: %{x}<br>Promedio: $%{y:,.0f}<br>Cantidad: %{customdata[0]}<br>Total: $%{customdata[1]:,.0f}<extra></extra>'
                )
                st.plotly_chart(fig_promedio, use_container_width=True)
            
            # TAB 3: TABLA DETALLADA (con porcentaje si hay datos)
            with tab3:
                st.subheader("Tabla Detallada")
                if not df_detalle.empty:
                    df_display = df_detalle.copy()
                    df_display['total_dinero'] = df_display['total_dinero'].apply(lambda x: f"${int(x):,}")
                    df_display['promedio_trabajo'] = df_display['promedio_trabajo'].apply(lambda x: f"${int(x):,}")
                    df_display['porcentaje'] = df_display['porcentaje'].apply(lambda x: f"{x:.2f}%")
                    df_display = df_display[['ano', 'mes', 'categoria', 'cantidad_trabajos', 'total_dinero', 'promedio_trabajo', 'porcentaje']]
                    df_display.columns = ['Año', 'Mes', 'Categoria', 'Cantidad Trabajos', 'Total Ingresos (con IVA)', 'Promedio por Trabajo', 'Porcentaje']
                    st.dataframe(df_display, use_container_width=True, height=600)
                    csv = df_detalle.to_csv(index=False).encode('utf-8')
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
