#!/usr/bin/env python3
import sys
import json
import sqlite3
from pathlib import Path

DB_FILE = "facturas.db"

# ============ CREAR 4 TABLAS ============
def crear_tablas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # TABLA 1
    cursor.execute('''CREATE TABLE IF NOT EXISTS facturas (
        numerofactura TEXT PRIMARY KEY,
        fechaemision TEXT, subtotal REAL, descuento_pesos REAL,
        valorneto REAL, iva REAL, total REAL, cantidad_lineas INTEGER)''')
    
    # TABLA 2
    cursor.execute('''CREATE TABLE IF NOT EXISTS lineas_factura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numerofactura TEXT NOT NULL,
        linea_numero INTEGER, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, descuento_pesos_porcentaje REAL,
        total_linea REAL, clasificacion_categoria TEXT,
        clasificacion_subcategoria TEXT,
        FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura))''')
    
    # TABLA 3
    cursor.execute('''CREATE TABLE IF NOT EXISTS notascredito (
        numeronota TEXT PRIMARY KEY,
        fechaemision TEXT, subtotal REAL, descuento_pesos REAL,
        valorneto REAL, iva REAL, total REAL, cantidad_lineas INTEGER)''')
    
    # TABLA 4
    cursor.execute('''CREATE TABLE IF NOT EXISTS lineas_notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numeronota TEXT NOT NULL,
        linea_numero INTEGER, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, descuento_pesos_porcentaje REAL,
        total_linea REAL, clasificacion_categoria TEXT,
        clasificacion_subcategoria TEXT,
        FOREIGN KEY (numeronota) REFERENCES notascredito(numeronota))''')
    
    conn.commit()
    conn.close()
    print("✅ 4 tablas creadas")

# ============ CARGAR FACTURAS ============
def cargar_facturas(archivo):
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    facturas = 0
    lineas = 0
    
    with open(archivo, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            try:
                registro = json.loads(texto_linea.strip())
                
                numero = registro.get('numerofactura')
                fecha = registro.get('fechaemision')
                subtotal = float(registro.get('subtotal') or 0)
                descuento = float(registro.get('descuento_pesos') or 0)
                valorneto = float(registro.get('valorneto') or 0)
                iva = float(registro.get('iva') or 0)
                total = float(registro.get('total') or 0)
                cantidad_lineas = len(registro.get('lineas', []))
                
                cursor.execute('''INSERT OR REPLACE INTO facturas 
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                facturas += 1
                
                for id_linea, linea in enumerate(registro.get('lineas', []), 1):
                    cursor.execute('''INSERT INTO lineas_factura 
                        (numerofactura,linea_numero,descripcion,cantidad,precio_unitario,
                         descuento_pesos_porcentaje,total_linea,clasificacion_categoria,
                         clasificacion_subcategoria) 
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                        (numero, id_linea, linea.get('descripcion'),
                         float(linea.get('cantidad') or 0),
                         float(linea.get('precio_unitario') or 0),
                         float(linea.get('descuento_pesos_porcentaje') or 0),
                         float(linea.get('total_linea') or 0),
                         linea.get('clasificacion_categoria'),
                         linea.get('clasificacion_subcategoria')))
                    lineas += 1
            except:
                pass
    
    conn.commit()
    conn.close()
    print(f"✅ Facturas: {facturas} | Líneas: {lineas}")

# ============ CARGAR NOTAS ============
def cargar_notas(archivo):
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    notas = 0
    lineas = 0
    
    with open(archivo, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            try:
                registro = json.loads(texto_linea.strip())
                
                numero = registro.get('numeronota')
                fecha = registro.get('fechaemision')
                subtotal = float(registro.get('subtotal') or 0)
                descuento = float(registro.get('descuento_pesos') or 0)
                valorneto = float(registro.get('valorneto') or 0)
                iva = float(registro.get('iva') or 0)
                total = float(registro.get('total') or 0)
                cantidad_lineas = len(registro.get('lineas', []))
                
                cursor.execute('''INSERT OR REPLACE INTO notascredito 
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                notas += 1
                
                for id_linea, linea in enumerate(registro.get('lineas', []), 1):
                    cursor.execute('''INSERT INTO lineas_notas 
                        (numeronota,linea_numero,descripcion,cantidad,precio_unitario,
                         descuento_pesos_porcentaje,total_linea,clasificacion_categoria,
                         clasificacion_subcategoria) 
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                        (numero, id_linea, linea.get('descripcion'),
                         float(linea.get('cantidad') or 0),
                         float(linea.get('precio_unitario') or 0),
                         float(linea.get('descuento_pesos_porcentaje') or 0),
                         float(linea.get('total_linea') or 0),
                         linea.get('clasificacion_categoria'),
                         linea.get('clasificacion_subcategoria')))
                    lineas += 1
            except:
                pass
    
    conn.commit()
    conn.close()
    print(f"✅ Notas: {notas} | Líneas: {lineas}")

# ============ MAIN ============
if __name__ == "__main__":
    print("\n" + "="*60)
    crear_tablas()
    
    print("📥 Cargando facturas...")
    cargar_facturas("outputs/facturas.jsonl")
    
    print("📥 Cargando notas...")
    cargar_notas("outputs/notas.jsonl")
    
    print("="*60)
    print("✅ LISTO para usar\n")
