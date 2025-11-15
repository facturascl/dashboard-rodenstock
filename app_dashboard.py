"""
Dashboard Streamlit para visualizar facturas desde SQLite.
Ejecutar: streamlit run app_dashboard.py
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

st.set_page_config(
    page_title="📊 Rodenstock - Facturas",
    page_icon="📄",
    layout="wide"
)

DB_FILE = "facturas.db"

# ============================================================================
# FUNCIONES
# ============================================================================

@st.cache_resource
def get_db_connection():
    """Conexión cacheable a SQLite."""
    return sqlite3.connect(DB_FILE)

def get_facturas(filters=None):
    """Obtiene facturas con filtros opcionales."""
    conn = get_db_connection()
    
    query = "SELECT * FROM facturas WHERE 1=1"
    params = []
    
    if filters:
        if 'cliente' in filters and filters['cliente']:
            query += " AND cliente = ?"
            params.append(filters['cliente'])
        
        if 'fecha_desde' in filters and filters['fecha_desde']:
            query += " AND DATE(fecha) >= ?"
            params.append(filters['fecha_desde'])
        
        if 'fecha_hasta' in filters and filters['fecha_hasta']:
            query += " AND DATE(fecha) <= ?"
            params.append(filters['fecha_hasta'])
    
    query += " ORDER BY fecha_carga DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    return df

def get_clientes_unicos():
    """Retorna lista de clientes únicos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT cliente FROM facturas ORDER BY cliente")
    return [row[0] for row in cursor.fetchall()]

def get_estadisticas():
    """Calcula estadísticas."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM facturas")
    total_facturas = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(monto_total) FROM facturas")
    monto_total = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT AVG(monto_total) FROM facturas")
    monto_promedio = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(DISTINCT cliente) FROM facturas")
    total_clientes = cursor.fetchone()[0]
    
    return {
        'total_facturas': total_facturas,
        'monto_total': monto_total,
        'monto_promedio': monto_promedio,
        'total_clientes': total_clientes
    }

# ============================================================================
# INTERFAZ STREAMLIT
# ============================================================================

st.title("📊 Dashboard Rodenstock - Facturas")
st.markdown("---")

# Sidebar: Filtros
with st.sidebar:
    st.header("🔍 Filtros")
    
    cliente_sel = st.selectbox(
        "Cliente",
        options=["Todos"] + get_clientes_unicos()
    )
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Desde", value=None)
    with col2:
        fecha_hasta = st.date_input("Hasta", value=None)
    
    # Construir diccionario de filtros
    filters = {
        'cliente': cliente_sel if cliente_sel != "Todos" else None,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta
    }

# Obtener datos
df = get_facturas(filters)
stats = get_estadisticas()

# Fila 1: Métricas principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📋 Total Facturas",
        value=stats['total_facturas'],
        delta=None
    )

with col2:
    st.metric(
        label="💰 Monto Total",
        value=f"${stats['monto_total']:,.2f}",
        delta=None
    )

with col3:
    st.metric(
        label="📊 Promedio por Factura",
        value=f"${stats['monto_promedio']:,.2f}",
        delta=None
    )

with col4:
    st.metric(
        label="👥 Clientes Únicos",
        value=stats['total_clientes'],
        delta=None
    )

st.markdown("---")

# Fila 2: Gráficos
col1, col2 = st.columns(2)

with col1:
    # Monto por cliente
    if not df.empty:
        df_by_cliente = df.groupby('cliente')['monto_total'].sum().reset_index()
        df_by_cliente = df_by_cliente.sort_values('monto_total', ascending=True).tail(10)
        
        fig1 = px.barh(
            df_by_cliente,
            x='monto_total',
            y='cliente',
            title="💵 Top 10 Clientes por Monto",
            labels={'monto_total': 'Monto ($)', 'cliente': 'Cliente'}
        )
        fig1.update_layout(height=400)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Sin datos para mostrar")

with col2:
    # Timeline de facturas
    if not df.empty:
        df_timeline = df.groupby(pd.to_datetime(df['fecha']).dt.date)['monto_total'].sum().reset_index()
        df_timeline.columns = ['Fecha', 'Monto']
        
        fig2 = px.line(
            df_timeline,
            x='Fecha',
            y='Monto',
            title="📈 Monto por Fecha",
            markers=True
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sin datos para mostrar")

st.markdown("---")

# Tabla de detalle
st.header("📋 Detalle de Facturas")

if not df.empty:
    # Mostrar tabla
    display_df = df.copy()
    display_df['fecha_carga'] = pd.to_datetime(display_df['fecha_carga']).dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df['fecha'] = pd.to_datetime(display_df['fecha']).dt.strftime('%Y-%m-%d')
    display_df['monto_total'] = display_df['monto_total'].apply(lambda x: f"${x:,.2f}")
    
    st.dataframe(
        display_df[['numero_factura', 'fecha', 'cliente', 'monto_total', 'fecha_carga']],
        use_container_width=True,
        height=400
    )
    
    # Exportar CSV
    csv = display_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name=f"facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
else:
    st.warning("⚠️  No hay facturas para mostrar con los filtros seleccionados")

st.markdown("---")
st.caption(f"📊 Último dato cargado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"