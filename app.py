import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime
import os

# ============ CONFIGURACIÓN DE PÁGINA ============
st.set_page_config(
    page_title="Dashboard Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ FUNCIONES DE DATOS ============

@st.cache_resource
def get_bigquery_client():
    """Inicializa cliente BigQuery con credenciales"""
    try:
        # Intenta cargar desde Streamlit Secrets (para deploy en cloud)
        if 'gcp_service_account' in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return bigquery.Client(credentials=credentials)
    except:
        pass
    
    # Para desarrollo local - usa tu archivo de credenciales
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'bigquery-credentials.json'
    return bigquery.Client()

@st.cache_data(ttl=600)  # Cache por 10 minutos
def get_resumen_mensual(ano=None, mes=None, categorias=None, incluir_sin_clasificar=False):
    """Obtiene resumen mensual por categoría"""
    client = get_bigquery_client()
    
    # Construir filtros
    filtros = ["f.fechaemision IS NOT NULL"]
    
    if not incluir_sin_clasificar:
        filtros.append("lf.clasificacion_categoria IS NOT NULL")
        filtros.append("lf.clasificacion_categoria != 'Sin clasificacion'")
    
    if ano:
        filtros.append(f"EXTRACT(YEAR FROM f.fechaemision) = {ano}")
    if mes:
        filtros.append(f"EXTRACT(MONTH FROM f.fechaemision) = {mes}")
    if categorias:
        cats_str = "', '".join(categorias)
        filtros.append(f"lf.clasificacion_categoria IN ('{cats_str}')")
    
    where_clause = " AND ".join(filtros)
    
    query = f"""
    WITH facturas_clasificadas AS (
      SELECT
        f.fechaemision,
        f.numerofactura,
        COALESCE(
          CONCAT(lf.clasificacion_categoria, ' ', lf.clasificacion_subcategoria),
          'Sin Clasificación'
        ) AS categoria_unificada,
        COALESCE(f.valorneto, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM `rodenstock-471300.facturacion.lineas_factura` lf
      JOIN `rodenstock-471300.facturacion.facturas` f
        ON lf.numerofactura = f.numerofactura
      WHERE {where_clause}
      GROUP BY 
        f.fechaemision,
        f.numerofactura,
        categoria_unificada,
        total_factura
    )
    
    SELECT
      EXTRACT(YEAR FROM fechaemision) AS ano,
      EXTRACT(MONTH FROM fechaemision) AS mes,
      categoria_unificada,
      COUNT(DISTINCT numerofactura) AS cantidad_trabajos,
      SUM(total_factura) AS total_dinero,
      AVG(total_factura) AS promedio_trabajo
    FROM facturas_clasificadas
    GROUP BY ano, mes, categoria_unificada
    ORDER BY ano DESC, mes DESC, total_dinero DESC
    """
    
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_evolucion_mensual(categorias=None, incluir_sin_clasificar=False):
    """Obtiene evolución mes a mes de categorías"""
    client = get_bigquery_client()
    
    filtros = ["f.fechaemision IS NOT NULL"]
    
    if not incluir_sin_clasificar:
        filtros.append("lf.clasificacion_categoria IS NOT NULL")
        filtros.append("lf.clasificacion_categoria != 'Sin clasificacion'")
    
    if categorias:
        cats_str = "', '".join(categorias)
        filtros.append(f"lf.clasificacion_categoria IN ('{cats_str}')")
    
    where_clause = " AND ".join(filtros)
    
    query = f"""
    WITH facturas_clasificadas AS (
      SELECT
        FORMAT_DATE('%Y-%m', f.fechaemision) AS mes,
        COALESCE(
          CONCAT(lf.clasificacion_categoria, ' ', lf.clasificacion_subcategoria),
          'Sin Clasificación'
        ) AS categoria_unificada,
        f.numerofactura,
        COALESCE(f.valorneto, 0) + COALESCE(f.iva, 0) AS total_factura
      FROM `rodenstock-471300.facturacion.lineas_factura` lf
      JOIN `rodenstock-471300.facturacion.facturas` f
        ON lf.numerofactura = f.numerofactura
      WHERE {where_clause}
      GROUP BY mes, categoria_unificada, f.numerofactura, total_factura
    )
    
    SELECT
      mes,
      categoria_unificada,
      COUNT(DISTINCT numerofactura) AS cantidad_trabajos,
      SUM(total_factura) AS total_dinero
    FROM facturas_clasificadas
    GROUP BY mes, categoria_unificada
    ORDER BY mes DESC
    """
    
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def get_totales_generales(ano=None, mes=None):
    """Obtiene totales generales del periodo"""
    client = get_bigquery_client()
    
    filtros = ["fechaemision IS NOT NULL"]
    if ano:
        filtros.append(f"EXTRACT(YEAR FROM fechaemision) = {ano}")
    if mes:
        filtros.append(f"EXTRACT(MONTH FROM fechaemision) = {mes}")
    
    where_clause = " AND ".join(filtros)
    
    query = f"""
    SELECT
      COUNT(DISTINCT numerofactura) AS total_facturas,
      SUM(COALESCE(valorneto, 0) + COALESCE(iva, 0)) AS total_ingresos,
      AVG(COALESCE(valorneto, 0) + COALESCE(iva, 0)) AS promedio_factura
    FROM `rodenstock-471300.facturacion.facturas`
    WHERE {where_clause}
    """
    
    return client.query(query).to_dataframe()

# ============ INTERFAZ DE USUARIO ============

# Título principal
st.title("📊 Dashboard de Facturación Rodenstock")
st.markdown("---")

# ============ SIDEBAR - FILTROS ============
with st.sidebar:
    st.header("🔍 Filtros")
    
    # Filtro de año
    anos_disponibles = list(range(2025, datetime.now().year + 1))
    ano_seleccionado = st.selectbox(
        "Año",
        options=[None] + anos_disponibles,
        format_func=lambda x: "Todos" if x is None else str(x),
        index=1  # Selecciona 2025 por defecto
    )
    
    # Filtro de mes
    meses = {
        None: "Todos",
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    mes_seleccionado = st.selectbox(
        "Mes",
        options=list(meses.keys()),
        format_func=lambda x: meses[x]
    )
    
    # Filtro de categoría
    categorias_disponibles = ["Newton", "Newton Plus", "Monofocales", "Progresivo"]
    categorias_seleccionadas = st.multiselect(
        "Categorías",
        options=categorias_disponibles,
        default=categorias_disponibles
    )
    
    # Opción para incluir facturas sin clasificar
    incluir_sin_clasificar = st.checkbox(
        "Incluir facturas sin clasificar",
        value=False,
        help="Muestra también las facturas que no tienen categoría asignada"
    )
    
    st.markdown("---")
    st.markdown("### ℹ️ Acerca de")
    st.info("Dashboard interactivo para análisis de facturación de productos Rodenstock.")
    
    # Botón para refrescar datos
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

# ============ MÉTRICAS PRINCIPALES ============
st.header("📈 Resumen General")

try:
    # Obtener totales
    totales = get_totales_generales(ano_seleccionado, mes_seleccionado)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total Trabajos",
            value=f"{int(totales['total_facturas'].iloc[0]):,}",
            help="Cantidad total de facturas emitidas"
        )
    
    with col2:
        st.metric(
            label="Ingresos Totales",
            value=f"${int(totales['total_ingresos'].iloc[0]):,}",
            help="Suma de todas las facturas (neto + IVA)"
        )
    
    with col3:
        st.metric(
            label="Promedio por Trabajo",
            value=f"${int(totales['promedio_factura'].iloc[0]):,}",
            help="Promedio de facturación por trabajo"
        )
    
    st.markdown("---")
    
    # ============ GRÁFICOS Y TABLAS ============
    
    # Obtener datos filtrados
    df_resumen = get_resumen_mensual(ano_seleccionado, mes_seleccionado, categorias_seleccionadas, incluir_sin_clasificar)
    
    if not df_resumen.empty:
        
        # Crear pestañas
        tab1, tab2, tab3 = st.tabs(["📊 Distribución", "📈 Evolución", "📋 Detalle"])
        
        # ============ TAB 1: DISTRIBUCIÓN POR CATEGORÍA ============
        with tab1:
            st.subheader("Distribución por Categoría")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Gráfico de barras
                fig_barras = px.bar(
                    df_resumen.sort_values('total_dinero', ascending=False).head(15),
                    x='categoria_unificada',
                    y='cantidad_trabajos',
                    color='categoria_unificada',
                    title='Top 15 Categorías por Cantidad de Trabajos',
                    labels={'cantidad_trabajos': 'Cantidad', 'categoria_unificada': 'Categoría'},
                    height=500
                )
                fig_barras.update_layout(showlegend=False, xaxis_tickangle=-45)
                st.plotly_chart(fig_barras, use_container_width=True)
            
            with col2:
                # Gráfico de pastel
                fig_pie = px.pie(
                    df_resumen.head(10),
                    values='total_dinero',
                    names='categoria_unificada',
                    title='Distribución de Ingresos (Top 10)',
                    height=500
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        # ============ TAB 2: EVOLUCIÓN MENSUAL ============
        with tab2:
            st.subheader("Evolución Mensual")
            
            df_evolucion = get_evolucion_mensual(categorias_seleccionadas, incluir_sin_clasificar)
            
            if not df_evolucion.empty:
                # Calcular promedio
                df_evolucion['promedio_trabajo'] = df_evolucion['total_dinero'] / df_evolucion['cantidad_trabajos']
                
                # Gráfico 1: Evolución de Trabajos
                fig_lineas = px.line(
                    df_evolucion,
                    x='mes',
                    y='cantidad_trabajos',
                    color='categoria_unificada',
                    title='Evolución de Trabajos por Mes',
                    labels={'cantidad_trabajos': 'Cantidad', 'mes': 'Mes'},
                    height=450,
                    markers=True
                )
                st.plotly_chart(fig_lineas, use_container_width=True)
                
                # Gráfico 2: Evolución de Ingresos
                fig_area = px.area(
                    df_evolucion,
                    x='mes',
                    y='total_dinero',
                    color='categoria_unificada',
                    title='Evolución de Ingresos por Mes',
                    labels={'total_dinero': 'Ingresos', 'mes': 'Mes'},
                    height=450
                )
                st.plotly_chart(fig_area, use_container_width=True)
                
                # Gráfico 3: Evolución del Promedio (NUEVO)
                fig_promedio = px.line(
                    df_evolucion,
                    x='mes',
                    y='promedio_trabajo',
                    color='categoria_unificada',
                    title='Evolución del Promedio por Trabajo',
                    labels={'promedio_trabajo': 'Promedio ($)', 'mes': 'Mes'},
                    height=450,
                    markers=True
                )
                st.plotly_chart(fig_promedio, use_container_width=True)
            else:
                st.warning("No hay datos de evolución para mostrar con los filtros seleccionados.")
        
        # ============ TAB 3: TABLA DETALLADA ============
        with tab3:
            st.subheader("Tabla Detallada")
            
            # Formatear columnas
            df_display = df_resumen.copy()
            df_display['total_dinero'] = df_display['total_dinero'].apply(lambda x: f"${x:,.0f}")
            df_display['promedio_trabajo'] = df_display['promedio_trabajo'].apply(lambda x: f"${x:,.0f}")
            
            # Renombrar columnas
            df_display.columns = ['Año', 'Mes', 'Categoría', 'Cantidad Trabajos', 'Total Ingresos', 'Promedio por Trabajo']
            
            # Mostrar tabla
            st.dataframe(
                df_display,
                use_container_width=True,
                height=600
            )
            
            # Botón de descarga
            csv = df_resumen.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f'rodenstock_facturacion_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
            )
    
    else:
        st.warning("⚠️ No hay datos disponibles para los filtros seleccionados. Intenta cambiar los criterios de búsqueda.")

except Exception as e:
    st.error(f"❌ Error al cargar los datos: {str(e)}")
    st.info("💡 Asegúrate de que:")
    st.markdown("""
    - El archivo `bigquery-credentials.json` esté en la misma carpeta que `app.py`
    - Las credenciales tengan permisos de lectura en BigQuery
    - La conexión a internet esté activa
    """)

# ============ FOOTER ============
st.markdown("---")
st.caption("Dashboard desarrollado con Streamlit | Datos desde BigQuery | © 2025 Rodenstock")
