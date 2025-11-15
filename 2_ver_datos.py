#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import sqlite3

DB_FILE = "facturas.db"

st.set_page_config(page_title="Rodenstock", layout="wide")
st.title("📊 Rodenstock - Facturas")

conn = sqlite3.connect(DB_FILE)

# MÉTRICAS
c1, c2, c3, c4 = st.columns(4)
with c1:
    t = pd.read_sql("SELECT COUNT(*) FROM facturas", conn).iloc[0,0]
    st.metric("Facturas", t)
with c2:
    t = pd.read_sql("SELECT SUM(total) FROM facturas", conn).iloc[0,0]
    st.metric("Monto", f"${t:,.0f}" if t else "$0")
with c3:
    t = pd.read_sql("SELECT COUNT(*) FROM notascredito", conn).iloc[0,0]
    st.metric("Notas", t)
with c4:
    t = pd.read_sql("SELECT SUM(total) FROM notascredito", conn).iloc[0,0]
    st.metric("Monto", f"${t:,.0f}" if t else "$0")

st.divider()

# FACTURAS
st.header("📋 FACTURAS")
df = pd.read_sql("SELECT * FROM facturas ORDER BY fechaemision DESC", conn)
st.dataframe(df, use_container_width=True)

st.subheader("Líneas de Facturas")
df = pd.read_sql("SELECT * FROM lineas_factura", conn)
st.dataframe(df, use_container_width=True)

st.divider()

# NOTAS
st.header("📝 NOTAS DE CRÉDITO")
df = pd.read_sql("SELECT * FROM notascredito ORDER BY fechaemision DESC", conn)
st.dataframe(df, use_container_width=True)

st.subheader("Líneas de Notas")
df = pd.read_sql("SELECT * FROM lineas_notas", conn)
st.dataframe(df, use_container_width=True)

conn.close()
