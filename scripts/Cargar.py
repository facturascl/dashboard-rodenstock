#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path

DB_FILE = "data/facturas.db"

# ============ CREAR 4 TABLAS ============
def crear_tablas():
    """Crea las tablas SQLite si no existen (sin eliminar datos previos)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # TABLA 1: FACTURAS
    cursor.execute('''CREATE TABLE IF NOT EXISTS facturas (
        numerofactura TEXT PRIMARY KEY,
        fechaemision TEXT,
        subtotal REAL,
        descuento_pesos REAL,
        valorneto REAL,
        iva REAL,
        total REAL,
        cantidad_lineas INTEGER
    )''')
    
    # TABLA 2: LINEAS DE FACTURA
    cursor.execute('''CREATE TABLE IF NOT EXISTS lineas_factura (
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
    )''')
    
    # TABLA 3: NOTAS DE CRÉDITO
    cursor.execute('''CREATE TABLE IF NOT EXISTS notascredito (
        numeronota TEXT PRIMARY KEY,
        fechaemision TEXT,
        subtotal REAL,
        descuento_pesos REAL,
        valorneto REAL,
        iva REAL,
        total REAL,
        cantidad_lineas INTEGER
    )''')
    
    # TABLA 4: LINEAS DE NOTAS
    cursor.execute('''CREATE TABLE IF NOT EXISTS lineas_notas (
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
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Tablas creadas (o ya existentes).")

# ============ CARGAR FACTURAS (facturas.jsonl + lineas_factura.jsonl) ============
def cargar_facturas(archivo_facturas, archivo_lineas):
    """
    Carga facturas y líneas desde dos JSONL:
    - archivo_facturas: outputs/facturas.jsonl (cabeceras)
    - archivo_lineas: outputs/lineas_factura.jsonl (detalle)
    
    INCREMENTAL: solo actualiza las facturas/líneas presentes en los JSONL
    """
    if not Path(archivo_facturas).exists():
        print(f"❌ {archivo_facturas} no encontrado")
        return 0, 0
    if not Path(archivo_lineas).exists():
        print(f"❌ {archivo_lineas} no encontrado")
        return 0, 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    facturas_procesadas = 0
    lineas_nuevas = 0
    
    # 1) Cargar cabeceras de facturas (INSERT OR REPLACE)
    print("📋 Cargando cabeceras de facturas...")
    with open(archivo_facturas, 'r', encoding='utf-8') as f:
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
                cantidad_lineas = int(registro.get('cantidad_lineas') or 0)
                
                cursor.execute(
                    '''INSERT OR REPLACE INTO facturas
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas)
                )
                facturas_procesadas += 1
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Error procesando factura JSONL: {e}")
                continue
    
    # 2) Carga INCREMENTAL de líneas: borrar solo las de facturas presentes en JSONL
    print("🔄 Actualizando líneas de facturas (solo las nuevas/reprocesadas)...")
    nuevas_facturas_set = set()
    with open(archivo_lineas, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            if not texto_linea.strip():
                continue
            try:
                linea = json.loads(texto_linea.strip())
                if linea.get('numerofactura'):
                    nuevas_facturas_set.add(linea['numerofactura'])
            except:
                pass  # Ignorar errores solo para recolectar facturas
    
    if nuevas_facturas_set:
        placeholders = ','.join(['?' for _ in nuevas_facturas_set])
        cursor.execute(
            f"DELETE FROM lineas_factura WHERE numerofactura IN ({placeholders})",
            tuple(nuevas_facturas_set)
        )
        print(f"🗑️ Borradas líneas antiguas de {len(nuevas_facturas_set)} facturas")
    
    # Insertar las nuevas líneas
    with open(archivo_lineas, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            if not texto_linea.strip():
                continue
            try:
                linea = json.loads(texto_linea.strip())
                numero = linea.get('numerofactura')
                linea_numero = linea.get('linea_numero')
                descripcion = linea.get('descripcion')
                cantidad = float(linea.get('cantidad') or 0)
                precio_unitario = float(linea.get('precio_unitario') or 0)
                descuento_pct = float(linea.get('descuento_pesos_porcentaje') or 0)
                total_linea = float(linea.get('total_linea') or 0)
                cat = linea.get('clasificacion_categoria')
                subcat = linea.get('clasificacion_subcategoria')
                
                cursor.execute(
                    '''INSERT INTO lineas_factura
                    (numerofactura, linea_numero, descripcion, cantidad,
                     precio_unitario, descuento_pesos_porcentaje, total_linea,
                     clasificacion_categoria, clasificacion_subcategoria)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (numero, linea_numero, descripcion, cantidad,
                     precio_unitario, descuento_pct, total_linea, cat, subcat)
                )
                lineas_nuevas += 1
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Error procesando línea JSONL: {e}")
                continue
    
    conn.commit()
    conn.close()
    
    print(f"✅ Facturas procesadas: {facturas_procesadas}")
    print(f"✅ Líneas de factura insertadas: {lineas_nuevas}")
    return facturas_procesadas, lineas_nuevas

# ============ CARGAR NOTAS (notas.jsonl + lineas_notas.jsonl) ============
def cargar_notas(archivo_notas, archivo_lineas):
    """
    Carga notas de crédito y líneas desde dos JSONL:
    - archivo_notas: outputs/notas.jsonl
    - archivo_lineas: outputs/lineas_notas.jsonl
    
    INCREMENTAL: solo actualiza las notas/líneas presentes en los JSONL
    """
    if not Path(archivo_notas).exists():
        print(f"❌ {archivo_notas} no encontrado")
        return 0, 0
    if not Path(archivo_lineas).exists():
        print(f"❌ {archivo_lineas} no encontrado")
        return 0, 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    notas_procesadas = 0
    lineas_nuevas = 0
    
    # 1) Cargar cabeceras de notas (INSERT OR REPLACE)
    print("📋 Cargando cabeceras de notas...")
    with open(archivo_notas, 'r', encoding='utf-8') as f:
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
                cantidad_lineas = int(registro.get('cantidad_lineas') or 0)
                
                cursor.execute(
                    '''INSERT OR REPLACE INTO notascredito
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas)
                )
                notas_procesadas += 1
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Error procesando nota JSONL: {e}")
                continue
    
    # 2) Carga INCREMENTAL de líneas de notas
    print("🔄 Actualizando líneas de notas (solo las nuevas/reprocesadas)...")
    nuevas_notas_set = set()
    with open(archivo_lineas, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            if not texto_linea.strip():
                continue
            try:
                linea = json.loads(texto_linea.strip())
                if linea.get('numeronota'):
                    nuevas_notas_set.add(linea['numeronota'])
            except:
                pass  # Ignorar errores solo para recolectar notas
    
    if nuevas_notas_set:
        placeholders = ','.join(['?' for _ in nuevas_notas_set])
        cursor.execute(
            f"DELETE FROM lineas_notas WHERE numeronota IN ({placeholders})",
            tuple(nuevas_notas_set)
        )
        print(f"🗑️ Borradas líneas antiguas de {len(nuevas_notas_set)} notas")
    
    # Insertar las nuevas líneas
    with open(archivo_lineas, 'r', encoding='utf-8') as f:
        for texto_linea in f:
            if not texto_linea.strip():
                continue
            try:
                linea = json.loads(texto_linea.strip())
                numero = linea.get('numeronota')
                linea_numero = linea.get('linea_numero')
                descripcion = linea.get('descripcion')
                cantidad = float(linea.get('cantidad') or 0)
                precio_unitario = float(linea.get('precio_unitario') or 0)
                descuento_pct = float(linea.get('descuento_pesos_porcentaje') or 0)
                total_linea = float(linea.get('total_linea') or 0)
                cat = linea.get('clasificacion_categoria')
                subcat = linea.get('clasificacion_subcategoria')
                
                cursor.execute(
                    '''INSERT INTO lineas_notas
                    (numeronota, linea_numero, descripcion, cantidad,
                     precio_unitario, descuento_pesos_porcentaje, total_linea,
                     clasificacion_categoria, clasificacion_subcategoria)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (numero, linea_numero, descripcion, cantidad,
                     precio_unitario, descuento_pct, total_linea, cat, subcat)
                )
                lineas_nuevas += 1
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Error procesando línea nota JSONL: {e}")
                continue
    
    conn.commit()
    conn.close()
    
    print(f"✅ Notas procesadas: {notas_procesadas}")
    print(f"✅ Líneas de notas insertadas: {lineas_nuevas}")
    return notas_procesadas, lineas_nuevas

# ============ ESTADÍSTICAS ============
def mostrar_estadisticas():
    """Muestra el total de registros en la DB."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM facturas")
        total_facturas = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM lineas_factura")
        total_lineas_fact = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM notascredito")
        total_notas = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM lineas_notas")
        total_lineas_notas = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(DISTINCT f.numerofactura)
            FROM facturas f
            JOIN lineas_factura lf ON lf.numerofactura = f.numerofactura
        """)
        facturas_con_lineas = cursor.fetchone()[0]
        
        conn.close()
        
        print("\n" + "="*80)
        print("📊 ESTADO FINAL DE LA BASE DE DATOS")
        print("="*80)
        print(f"Total facturas: {total_facturas}")
        print(f"Total líneas de factura: {total_lineas_fact}")
        print(f"Facturas con líneas: {facturas_con_lineas}/{total_facturas}")
        print(f"Total notas de crédito: {total_notas}")
        print(f"Total líneas de notas: {total_lineas_notas}")
    except Exception as e:
        print(f"⚠️ Error estadísticas: {e}")

# ============ MAIN ============
if __name__ == '__main__':
    print("=" * 80)
    print("🚀 CARGADOR DE FACTURAS Y NOTAS - SQLite (INCREMENTAL)")
    print("=" * 80)
    
    crear_tablas()
    
    print("\n📋 Cargando facturas desde JSONL...")
    cargar_facturas("outputs/facturas.jsonl", "outputs/lineas_factura.jsonl")
    
    print("\n📋 Cargando notas de crédito desde JSONL...")
    cargar_notas("outputs/notas.jsonl", "outputs/lineas_notas.jsonl")
    
    mostrar_estadisticas()
    
    print("=" * 80)
    print("✅ LISTO - Base de datos cargada para el dashboard")
    print("=" * 80)
