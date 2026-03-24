#!/usr/bin/env python3
import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.Procesar import cargar_libreria, clasificar_lineas_factura

DB_FILE = "data/facturas.db"

def recategorizar_db():
    if not os.path.exists(DB_FILE):
        print(f"❌ Base de datos no encontrada: {DB_FILE}")
        return

    print("🔄 Recategorizando base de datos completa...")
    reglas = cargar_libreria()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # == 1. FACTURAS ==
    cursor.execute("SELECT id, numerofactura, descripcion FROM lineas_factura")
    todas_lineas = cursor.fetchall()
    
    # Agrupar por factura
    docs_facturas = {}
    for id_linea, numero, desc in todas_lineas:
        if numero not in docs_facturas:
            docs_facturas[numero] = []
        docs_facturas[numero].append({"id": id_linea, "descripcion": desc})

    actualizaciones_f = 0
    for numero, lineas in docs_facturas.items():
        cat, subcat = clasificar_lineas_factura(lineas, reglas)
        for linea in lineas:
            cursor.execute("UPDATE lineas_factura SET clasificacion_categoria=?, clasificacion_subcategoria=? WHERE id=?", 
                           (cat, subcat, linea["id"]))
            actualizaciones_f += 1

    # == 2. NOTAS DE CRÉDITO ==
    cursor.execute("SELECT id, numeronota, descripcion FROM lineas_notas")
    todas_notas = cursor.fetchall()
    
    docs_notas = {}
    for id_linea, numero, desc in todas_notas:
        if numero not in docs_notas:
            docs_notas[numero] = []
        docs_notas[numero].append({"id": id_linea, "descripcion": desc})

    actualizaciones_n = 0
    for numero, lineas in docs_notas.items():
        cat, subcat = clasificar_lineas_factura(lineas, reglas)
        for linea in lineas:
            cursor.execute("UPDATE lineas_notas SET clasificacion_categoria=?, clasificacion_subcategoria=? WHERE id=?", 
                           (cat, subcat, linea["id"]))
            actualizaciones_n += 1

    conn.commit()
    conn.close()
    print(f"✅ Se han recategorizado {actualizaciones_f} líneas de faturas y {actualizaciones_n} líneas de notas de crédito directamente en la BD.")

if __name__ == "__main__":
    print("="*60)
    print("🚀 INICIANDO RECATEGORIZACIÓN EN BD HISTÓRICA")
    print("="*60)
    recategorizar_db()
    print("✅ LISTO. No es necesario ejecutar Cargar.py.")
