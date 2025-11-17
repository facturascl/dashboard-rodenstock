#!/usr/bin/env python3
import sys
import json
import sqlite3
from pathlib import Path


DB_FILE = "facturas.db"


# ============ CREAR 4 TABLAS ============
def crear_tablas():
    """Crea las tablas SQLite si no existen (sin eliminar datos previos)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # TABLA 1: FACTURAS
    cursor.execute('''CREATE TABLE IF NOT EXISTS facturas (
        numerofactura TEXT PRIMARY KEY,
        fechaemision TEXT, subtotal REAL, descuento_pesos REAL,
        valorneto REAL, iva REAL, total REAL, cantidad_lineas INTEGER)''')
    
    # TABLA 2: LINEAS DE FACTURA
    cursor.execute('''CREATE TABLE IF NOT EXISTS lineas_factura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numerofactura TEXT NOT NULL,
        linea_numero INTEGER, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, descuento_pesos_porcentaje REAL,
        total_linea REAL, clasificacion_categoria TEXT,
        clasificacion_subcategoria TEXT,
        FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura))''')
    
    # TABLA 3: NOTAS DE CRÉDITO
    cursor.execute('''CREATE TABLE IF NOT EXISTS notascredito (
        numeronota TEXT PRIMARY KEY,
        fechaemision TEXT, subtotal REAL, descuento_pesos REAL,
        valorneto REAL, iva REAL, total REAL, cantidad_lineas INTEGER)''')
    
    # TABLA 4: LINEAS DE NOTAS
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
    print("✅ 4 tablas creadas (datos previos conservados)")


# ============ CARGAR FACTURAS (INCREMENTAL) ============
def cargar_facturas(archivo):
    """
    Lee JSONL y carga en DB de forma incremental.
    ⭐ INSERT OR IGNORE = si ya existe, la ignora (NO sobrescribe)
    ⭐ Así solo SUMA nuevas facturas sin tocar las existentes
    """
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return 0, 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    facturas_nuevas = 0
    lineas_nuevas = 0
    duplicadas = 0
    
    with open(archivo, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            if not texto_linea.strip():
                continue
            
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
                
                # ⭐ INSERT OR IGNORE: si ya existe, la ignora
                cursor.execute('''INSERT OR IGNORE INTO facturas 
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                
                # Contar si fue nueva o duplicada
                if cursor.rowcount == 1:
                    facturas_nuevas += 1
                    
                    # Insertar líneas (solo si factura es nueva)
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
                        lineas_nuevas += 1
                else:
                    duplicadas += 1
            
            except (json.JSONDecodeError, Exception):
                pass
    
    conn.commit()
    conn.close()
    
    print(f"   ✅ Facturas nuevas: {facturas_nuevas}")
    print(f"   ⏭️  Facturas duplicadas (ignoradas): {duplicadas}")
    print(f"   ✅ Líneas nuevas: {lineas_nuevas}")
    
    return facturas_nuevas, lineas_nuevas


# ============ CARGAR NOTAS (INCREMENTAL) ============
def cargar_notas(archivo):
    """
    Lee JSONL y carga en DB de forma incremental.
    ⭐ INSERT OR IGNORE = si ya existe, la ignora (NO sobrescribe)
    """
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return 0, 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    notas_nuevas = 0
    lineas_nuevas = 0
    duplicadas = 0
    
    with open(archivo, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            if not texto_linea.strip():
                continue
            
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
                
                # ⭐ INSERT OR IGNORE: si ya existe, la ignora
                cursor.execute('''INSERT OR IGNORE INTO notascredito 
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                
                # Contar si fue nueva o duplicada
                if cursor.rowcount == 1:
                    notas_nuevas += 1
                    
                    # Insertar líneas (solo si nota es nueva)
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
                        lineas_nuevas += 1
                else:
                    duplicadas += 1
            
            except (json.JSONDecodeError, Exception):
                pass
    
    conn.commit()
    conn.close()
    
    print(f"   ✅ Notas nuevas: {notas_nuevas}")
    print(f"   ⏭️  Notas duplicadas (ignoradas): {duplicadas}")
    print(f"   ✅ Líneas nuevas: {lineas_nuevas}")
    
    return notas_nuevas, lineas_nuevas


# ============ ESTADÍSTICAS ============
def mostrar_estadisticas():
    """Muestra el total de registros en la DB"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM facturas")
        total_facturas = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM notascredito")
        total_notas = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n📊 ESTADO ACTUAL DE LA BASE DE DATOS:")
        print(f"   📄 Total facturas en DB: {total_facturas}")
        print(f"   📋 Total notas en DB: {total_notas}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============ MAIN ============
if __name__ == "__main__":
    print("\n" + "="*70)
    print("📥 CARGADOR INCREMENTAL DE FACTURAS Y NOTAS (SIN PERDER DATOS)")
    print("="*70)
    
    crear_tablas()
    
    print("\n📁 Leyendo facturas desde JSON...")
    cargar_facturas("outputs/facturas.jsonl")
    
    print("\n📁 Leyendo notas de crédito desde JSON...")
    cargar_notas("outputs/notas.jsonl")
    
    mostrar_estadisticas()
    
    print("\n" + "="*70)
    print("✅ LISTO - Se sumaron solo datos nuevos, sin eliminar los anteriores")
    print("="*70 + "\n")
