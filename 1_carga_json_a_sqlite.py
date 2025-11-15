"""
Carga JSON existente a SQLite con TUS TABLAS EXACTAS
Sin esperar Gmail, sin Gmail API, solo carga local
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_FILE = "facturas.db"

# ============================================
# PASO 1: CREAR TODAS LAS 4 TABLAS
# ============================================

def crear_tablas():
    """Crea las 4 tablas EXACTAS a tus especificaciones"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # TABLA 1: facturas (encabezado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            numerofactura TEXT PRIMARY KEY,
            fechaemision TEXT,
            subtotal REAL,
            descuento_pesos REAL,
            valorneto REAL,
            iva REAL,
            total REAL,
            cantidad_lineas INTEGER
        )
    ''')
    
    # TABLA 2: lineas_factura (detalle)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lineas_factura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numerofactura TEXT NOT NULL,
            linea_numero INTEGER,
            descripcion TEXT,
            cantidad REAL,
            precio_unitario REAL,
            descuento_pesos_porcentaje REAL,
            total_linea REAL,
            clasificacion_categoria TEXT,
            clasificacion_subcategoria TEXT,
            FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura)
        )
    ''')
    
    # TABLA 3: notascredito (encabezado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notascredito (
            numeronota TEXT PRIMARY KEY,
            fechaemision TEXT,
            subtotal REAL,
            descuento_pesos REAL,
            valorneto REAL,
            iva REAL,
            total REAL,
            cantidad_lineas INTEGER
        )
    ''')
    
    # TABLA 4: lineas_notas (detalle)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lineas_notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numeronota TEXT NOT NULL,
            linea_numero INTEGER,
            descripcion TEXT,
            cantidad REAL,
            precio_unitario REAL,
            descuento_pesos_porcentaje REAL,
            total_linea REAL,
            clasificacion_categoria TEXT,
            clasificacion_subcategoria TEXT,
            FOREIGN KEY (numeronota) REFERENCES notascredito(numeronota)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ Tablas creadas:\n")
    print("   1. facturas")
    print("   2. lineas_factura")
    print("   3. notascredito")
    print("   4. lineas_notas")
    print()


# ============================================
# PASO 2: CARGAR JSON A SQLITE
# ============================================

def cargar_json_facturas(archivo_json):
    """Carga JSON de facturas a las tablas"""
    if not Path(archivo_json).exists():
        print(f"❌ Archivo no encontrado: {archivo_json}")
        return 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    facturas_cargadas = 0
    lineas_cargadas = 0
    
    try:
        with open(archivo_json, 'r', encoding='utf-8') as f:
            for linea in f:
                try:
                    registro = json.loads(linea.strip())
                    
                    # Extraer datos del encabezado (facturas)
                    numero = registro.get('numerofactura') or registro.get('numero_factura')
                    fecha = registro.get('fechaemision') or registro.get('fecha')
                    subtotal = float(registro.get('subtotal') or 0)
                    descuento = float(registro.get('descuento_pesos') or 0)
                    valorneto = float(registro.get('valorneto') or 0)
                    iva = float(registro.get('iva') or 0)
                    total = float(registro.get('total') or 0)
                    cantidad_lineas = len(registro.get('lineas', []))
                    
                    # Insertar en tabla facturas
                    cursor.execute('''
                        INSERT OR REPLACE INTO facturas 
                        (numerofactura, fechaemision, subtotal, descuento_pesos, 
                         valorneto, iva, total, cantidad_lineas)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                    
                    facturas_cargadas += 1
                    
                    # Insertar líneas en tabla lineas_factura
                    lineas = registro.get('lineas', [])
                    for id_linea, linea in enumerate(lineas, 1):
                        cursor.execute('''
                            INSERT INTO lineas_factura 
                            (numerofactura, linea_numero, descripcion, cantidad, precio_unitario,
                             descuento_pesos_porcentaje, total_linea, clasificacion_categoria,
                             clasificacion_subcategoria)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            numero,
                            id_linea,
                            linea.get('descripcion'),
                            float(linea.get('cantidad') or 0),
                            float(linea.get('precio_unitario') or 0),
                            float(linea.get('descuento_pesos_porcentaje') or 0),
                            float(linea.get('total_linea') or 0),
                            linea.get('clasificacion_categoria'),
                            linea.get('clasificacion_subcategoria')
                        ))
                        lineas_cargadas += 1
                
                except json.JSONDecodeError:
                    continue
        
        conn.commit()
        print(f"✅ Facturas cargadas: {facturas_cargadas}")
        print(f"✅ Líneas cargadas: {lineas_cargadas}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


def cargar_json_notas(archivo_json):
    """Carga JSON de notas de crédito a las tablas"""
    if not Path(archivo_json).exists():
        print(f"❌ Archivo no encontrado: {archivo_json}")
        return 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    notas_cargadas = 0
    lineas_cargadas = 0
    
    try:
        with open(archivo_json, 'r', encoding='utf-8') as f:
            for linea in f:
                try:
                    registro = json.loads(linea.strip())
                    
                    # Extraer datos del encabezado (notas)
                    numero = registro.get('numeronota') or registro.get('numero_nota')
                    fecha = registro.get('fechaemision') or registro.get('fecha')
                    subtotal = float(registro.get('subtotal') or 0)
                    descuento = float(registro.get('descuento_pesos') or 0)
                    valorneto = float(registro.get('valorneto') or 0)
                    iva = float(registro.get('iva') or 0)
                    total = float(registro.get('total') or 0)
                    cantidad_lineas = len(registro.get('lineas', []))
                    
                    # Insertar en tabla notascredito
                    cursor.execute('''
                        INSERT OR REPLACE INTO notascredito 
                        (numeronota, fechaemision, subtotal, descuento_pesos, 
                         valorneto, iva, total, cantidad_lineas)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                    
                    notas_cargadas += 1
                    
                    # Insertar líneas en tabla lineas_notas
                    lineas = registro.get('lineas', [])
                    for id_linea, linea in enumerate(lineas, 1):
                        cursor.execute('''
                            INSERT INTO lineas_notas 
                            (numeronota, linea_numero, descripcion, cantidad, precio_unitario,
                             descuento_pesos_porcentaje, total_linea, clasificacion_categoria,
                             clasificacion_subcategoria)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            numero,
                            id_linea,
                            linea.get('descripcion'),
                            float(linea.get('cantidad') or 0),
                            float(linea.get('precio_unitario') or 0),
                            float(linea.get('descuento_pesos_porcentaje') or 0),
                            float(linea.get('total_linea') or 0),
                            linea.get('clasificacion_categoria'),
                            linea.get('clasificacion_subcategoria')
                        ))
                        lineas_cargadas += 1
                
                except json.JSONDecodeError:
                    continue
        
        conn.commit()
        print(f"✅ Notas cargadas: {notas_cargadas}")
        print(f"✅ Líneas cargadas: {lineas_cargadas}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


# ============================================
# PASO 3: VER ESTADÍSTICAS
# ============================================

def ver_estadisticas():
    """Muestra lo que se cargó"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("📊 ESTADÍSTICAS DE LA BASE DE DATOS")
    print("="*60)
    
    # Facturas
    cursor.execute("SELECT COUNT(*) FROM facturas")
    total_facturas = cursor.fetchone()
    cursor.execute("SELECT SUM(total) FROM facturas")
    monto_facturas = cursor.fetchone() or 0
    
    print(f"\n📋 FACTURAS:")
    print(f"   • Total: {total_facturas}")
    print(f"   • Monto: ${monto_facturas:,.2f}")
    
    # Líneas facturas
    cursor.execute("SELECT COUNT(*) FROM lineas_factura")
    total_lineas_fact = cursor.fetchone()
    print(f"   • Líneas: {total_lineas_fact}")
    
    # Notas
    cursor.execute("SELECT COUNT(*) FROM notascredito")
    total_notas = cursor.fetchone()
    cursor.execute("SELECT SUM(total) FROM notascredito")
    monto_notas = cursor.fetchone() or 0
    
    print(f"\n📝 NOTAS DE CRÉDITO:")
    print(f"   • Total: {total_notas}")
    print(f"   • Monto: ${monto_notas:,.2f}")
    
    # Líneas notas
    cursor.execute("SELECT COUNT(*) FROM lineas_notas")
    total_lineas_notas = cursor.fetchone()
    print(f"   • Líneas: {total_lineas_notas}")
    
    print("\n" + "="*60)
    conn.close()


# ============================================
# MAIN
# ============================================

def main():
    if len(sys.argv) < 2:
        print("\n🔴 MODO DE USO:\n")
        print("   Para cargar FACTURAS:")
        print("   python 1_carga_json_a_sqlite.py facturas outputs/facturas.jsonl\n")
        print("   Para cargar NOTAS DE CRÉDITO:")
        print("   python 1_carga_json_a_sqlite.py notas outputs/notas.jsonl\n")
        return
    
    tipo = sys.argv.lower()
    archivo = sys.argv if len(sys.argv) > 2 else None
    
    print("\n" + "="*60)
    print("CARGA DE DATOS A SQLITE")
    print("="*60 + "\n")
    
    # Crear tablas
    print("🔧 Creando tablas...")
    crear_tablas()
    
    # Cargar según tipo
    if tipo == 'facturas':
        if not archivo:
            print("❌ Debes especificar el archivo JSON")
            return
        print(f"📥 Cargando facturas desde: {archivo}\n")
        cargar_json_facturas(archivo)
    
    elif tipo == 'notas':
        if not archivo:
            print("❌ Debes especificar el archivo JSON")
            return
        print(f"📥 Cargando notas desde: {archivo}\n")
        cargar_json_notas(archivo)
    
    else:
        print(f"❌ Tipo desconocido: {tipo}")
        print("   Usa 'facturas' o 'notas'")
        return
    
    # Ver resultado
    ver_estadisticas()


if __name__ == "__main__":
    main()