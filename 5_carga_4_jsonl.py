
import json
import sqlite3
from pathlib import Path

DB_FILE = "facturas.db"

def crear_tablas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla facturas
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
    
    # Tabla líneas de factura
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
    
    # Tabla notas de crédito
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
    
    # Tabla líneas de notas
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
    print("✅ 4 tablas creadas")

def cargar_archivo(archivo, tabla, clave_pk=None):
    """Carga un JSONL a una tabla SQLite"""
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    contador = 0
    
    with open(archivo, 'r', encoding='utf-8') as f:
        for linea_texto in f:
            try:
                registro = json.loads(linea_texto.strip())
                
                # Obtener claves y valores
                columnas = list(registro.keys())
                valores = [registro.get(col) for col in columnas]
                
                # Crear query INSERT
                placeholders = ','.join(['?' for _ in columnas])
                columnas_str = ','.join(columnas)
                query = f'INSERT OR REPLACE INTO {tabla} ({columnas_str}) VALUES ({placeholders})'
                
                cursor.execute(query, valores)
                contador += 1
                
                if contador % 1000 == 0 and contador > 0:
                    print(f"  {contador} registros cargados...")
                    
            except Exception as e:
                print(f"  ⚠️  Error en línea: {str(e)[:100]}")
                pass
    
    conn.commit()
    conn.close()
    return contador

print("\n" + "="*70)
print("CARGA DEFINITIVA - 4 JSONL A SQLITE")
print("="*70 + "\n")

# Crear tablas
crear_tablas()

# Cargar facturas
print("📥 Cargando facturas.jsonl...")
facturas = cargar_archivo("outputs/facturas.jsonl", "facturas")
print(f"✅ Facturas: {facturas}")

# Cargar líneas de facturas
print("📥 Cargando lineas_factura.jsonl...")
lineas_fact = cargar_archivo("outputs/lineas_factura.jsonl", "lineas_factura")
print(f"✅ Líneas de Factura: {lineas_fact}")

# Cargar notas
print("📥 Cargando notas.jsonl...")
notas = cargar_archivo("outputs/notas.jsonl", "notascredito")
print(f"✅ Notas de Crédito: {notas}")

# Cargar líneas de notas
print("📥 Cargando lineas_notas.jsonl...")
lineas_notas = cargar_archivo("outputs/lineas_notas.jsonl", "lineas_notas")
print(f"✅ Líneas de Notas: {lineas_notas}")

print("\n" + "="*70)
print("✅ LISTO PARA USAR EN DASHBOARD")
print("="*70)
print(f"\n📊 Resumen:")
print(f"  • Facturas: {facturas}")
print(f"  • Líneas de Factura: {lineas_fact}")
print(f"  • Notas de Crédito: {notas}")
print(f"  • Líneas de Notas: {lineas_notas}")
print(f"\n➡️  Ejecuta: streamlit run 2_dashboard_COMPLETO.py\n")
print("="*70 + "\n")