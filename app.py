import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Dashboard Facturación Rodenstock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CONEXIÓN A BD
# ============================================================
DB_PATH = "facturas.db"

@st.cache_resource
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        st.error(f"Error conectando BD: {e}")
        return None

conn = get_db_connection()

if conn is None:
    st.error("No se pudo conectar a la base de datos")
    st.stop()

# ============================================================
# SIDEBAR - FILTROS
# ============================================================
st.sidebar.title("🔧 Filtros")

try:
    # Obtener años disponibles
    anos_query = """
        SELECT DISTINCT CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano
        FROM facturas
        WHERE fechaemision IS NOT NULL
        ORDER BY ano DESC
    """
    anos_df = pd.read_sql_query(anos_query, conn)
    anos_disponibles = sorted(anos_df['ano'].tolist(), reverse=True) if not anos_df.empty else [datetime.now().year]
    
    ano_seleccionado = st.sidebar.selectbox(
        "Año",
        options=anos_disponibles,
        index=0,
        key="ano_select"
    )
    
    # Obtener meses del año seleccionado
    meses_query = f"""
        SELECT DISTINCT CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes
        FROM facturas
        WHERE CAST(STRFTIME('%Y', fechaemision) AS INTEGER) = {int(ano_seleccionado)}
        AND fechaemision IS NOT NULL
        ORDER BY mes DESC
    """
    meses_df = pd.read_sql_query(meses_query, conn)
    meses_disponibles = sorted(meses_df['mes'].tolist(), reverse=True) if not meses_df.empty else [datetime.now().month]
    
    mes_param = st.sidebar.selectbox(
        "Mes",
        options=meses_disponibles,
        index=0,
        format_func=lambda x: f"{x:02d}",
        key="mes_select"
    )
    
except Exception as e:
    st.error(f"Error al cargar filtros: {e}")
    st.stop()

# ============================================================
# FUNCIONES DE CONSULTA
# ============================================================

@st.cache_data(ttl=600)
def get_comparativa_meses_anos(mes_param):
    """Comparativa por mes de todos los años"""
    try:
        query = f"""
        SELECT 
            CAST(STRFTIME('%Y', fechaemision) AS INTEGER) as ano,
            CAST(STRFTIME('%m', fechaemision) AS INTEGER) as mes,
            COUNT(DISTINCT numerofactura) as cantidad_facturas,
            CAST(SUM(subtotal + iva) AS INTEGER) as total_dinero
        FROM facturas
        WHERE CAST(STRFTIME('%m', fechaemision) AS INTEGER) = {int(mes_param)}
        AND fechaemision IS NOT NULL
        GROUP BY ano, mes
        ORDER BY ano DESC
        """
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error en comparativa: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_subcategorias_desglose(ano_sel, mes_param):
    """Desglose por subcategoría: cantidad, costo, promedio, %"""
    try:
        query = f"""
        WITH stats_totales AS (
            SELECT
                CAST(SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as total_general
            FROM lineas_factura lf
            INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
            WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano_sel)}
            AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {int(mes_param)}
            AND f.fechaemision IS NOT NULL
        )
        SELECT 
            COALESCE(lf.clasificacion_subcategoria, 'Sin subcategoría') as subcategoria,
            COUNT(DISTINCT lf.numerofactura) as cantidad_facturas,
            CAST(SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as total_costo,
            CAST(AVG(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) AS INTEGER) as promedio,
            CAST(100.0 * SUM(CASE WHEN lf.linea_numero = 1 THEN f.subtotal + f.iva ELSE 0 END) / NULLIF((SELECT total_general FROM stats_totales), 0) AS DECIMAL(5,2)) as porcentaje
        FROM lineas_factura lf
        INNER JOIN facturas f ON lf.numerofactura = f.numerofactura
        CROSS JOIN stats_totales
        WHERE CAST(STRFTIME('%Y', f.fechaemision) AS INTEGER) = {int(ano_sel)}
        AND CAST(STRFTIME('%m', f.fechaemision) AS INTEGER) = {int(mes_param)}
        AND f.fechaemision IS NOT NULL
        GROUP BY subcategoria
        ORDER BY total_costo DESC
        """
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error en desglose: {e}")
        return pd.DataFrame()

# ============================================================
# TABS PRINCIPALES - SOLO 2 VISTAS
# ============================================================

tab1, tab2 = st.tabs([
    "📊 Comparativa de Años",
    "🏷️ Desglose por Subcategoría"
])

# ============================================================
# TAB 1: COMPARATIVA DE AÑOS
# ============================================================
with tab1:
    st.header("📊 Comparativa de Años por Mes")
    
    df_comparativa = get_comparativa_meses_anos(mes_param)
    
    if not df_comparativa.empty:
        # Crear gráfico
        fig = go.Figure()
        
        # Agrupar por año
        for ano in sorted(df_comparativa['ano'].unique(), reverse=True):
            df_ano = df_comparativa[df_comparativa['ano'] == ano]
            
            # Barra: cantidad de facturas (eje Y principal)
            fig.add_trace(go.Bar(
                x=[f"Año {ano}"],
                y=df_ano['cantidad_facturas'].values,
                name=f"Facturas {ano}",
                yaxis='y1',
                marker=dict(opacity=0.7)
            ))
            
            # Línea: total dinero (eje Y secundario)
            fig.add_trace(go.Scatter(
                x=[f"Año {ano}"],
                y=df_ano['total_dinero'].values,
                name=f"Total $ {ano}",
                mode='lines+markers',
                yaxis='y2',
                line=dict(width=3),
                marker=dict(size=10)
            ))
        
        # Layout con 2 ejes Y
        fig.update_layout(
            title=f"Comparativa Años - Mes {mes_param:02d}",
            xaxis_title="Año",
            yaxis=dict(
                title="Cantidad de Facturas",
                side='left'
            ),
            yaxis2=dict(
                title="Total en Dinero ($)",
                overlaying='y',
                side='right'
            ),
            hovermode='x unified',
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabla con datos
        st.subheader("Datos Detallados")
        st.dataframe(
            df_comparativa,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ano": st.column_config.NumberColumn("Año", width=100),
                "mes": st.column_config.NumberColumn("Mes", width=100),
                "cantidad_facturas": st.column_config.NumberColumn("Facturas", width=120),
                "total_dinero": st.column_config.NumberColumn("Total ($)", width=150, format="$%d"),
            }
        )
    else:
        st.info("ℹ️ Sin datos disponibles para este mes")

# ============================================================
# TAB 2: DESGLOSE POR SUBCATEGORÍA
# ============================================================
with tab2:
    st.header("🏷️ Desglose por Subcategoría")
    
    df_subcategorias = get_subcategorias_desglose(ano_seleccionado, mes_param)
    
    if not df_subcategorias.empty:
        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Subcategorías", len(df_subcategorias))
        with col2:
            st.metric("Total Ingresos", f"${df_subcategorias['total_costo'].sum():,.0f}")
        with col3:
            st.metric("Promedio Categoría", f"${df_subcategorias['promedio'].mean():,.0f}")
        
        st.divider()
        
        # Tabla detallada
        st.subheader("Detalle Completo")
        st.dataframe(
            df_subcategorias,
            use_container_width=True,
            hide_index=True,
            column_config={
                "subcategoria": st.column_config.TextColumn("Subcategoría", width=250),
                "cantidad_facturas": st.column_config.NumberColumn("Cantidad", width=120),
                "total_costo": st.column_config.NumberColumn("Costo Total", width=150, format="$%d"),
                "promedio": st.column_config.NumberColumn("Promedio", width=150, format="$%d"),
                "porcentaje": st.column_config.NumberColumn("% del Total", width=120, format="%%.2f%%"),
            }
        )
        
        # Gráfico: distribución por subcategoría
        st.subheader("Distribución por Subcategoría")
        fig_pie = go.Figure(data=[go.Pie(
            labels=df_subcategorias['subcategoria'],
            values=df_subcategorias['total_costo'],
            text=df_subcategorias['porcentaje'].apply(lambda x: f"{x:.1f}%"),
            textposition='inside',
            hovertemplate='<b>%{label}</b><br>Total: $%{value:,.0f}<br>%{text}<extra></extra>'
        )])
        fig_pie.update_layout(height=500)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    else:
        st.info("📭 Sin datos de subcategorías para este período")

# ============================================================
# PIE DE PÁGINA
# ============================================================
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("✅ BD: SQLite")
with col2:
    st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
with col3:
    st.caption("🔧 Dashboard v1.0 - LIMPIO")
