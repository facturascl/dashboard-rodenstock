
import sqlite3
import json
import os

DB_FILE = "facturas.db"
OUTPUT_DIR = "outputs"

# Archivos JSONL a cargar
FILES_CONFIG = {
    "facturas.jsonl": {
        "table": "facturas",
        "columns": ["numerofactura", "fechaemision", "subtotal", "descuento_pesos", 
                   "valorneto", "iva", "total", "cantidad_lineas"]
    },
    "lineas_factura.jsonl": {
        "table": "lineas_factura",
        "columns": ["numerofactura", "linea_numero", "descripcion", "cantidad", 
                   "precio_unitario", "descuento_pesos_porcentaje", "total_linea",
                   "clasificacion_categoria", "clasificacion_subcategoria"]
    },
    "notas.jsonl": {
        "table": "notascredito",
        "columns": ["numeronota", "fechaemision", "subtotal", "descuento_pesos",
                   "valorneto", "iva", "total", "cantidad_lineas"]
    },
    "lineas_notas.jsonl": {
        "table": "lineas_notas",
        "columns": ["numeronota", "linea_numero", "descripcion", "cantidad",
                   "precio_unitario", "descuento_pesos_porcentaje", "total_linea",
                   "clasificacion_categoria", "clasificacion_subcategoria"]
    }
}

def crear_tablas(conn):
    """Crea las 4 tablas (si no existen)"""
    cursor = conn.cursor()
    
    # Tabla facturas
    cursor.execute("""
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
    """)
    
    # Tabla lineas_factura
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lineas_factura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numerofactura TEXT,
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
    """)
    
    # Tabla notascredito
    cursor.execute("""
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
    """)
    
    # Tabla lineas_notas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lineas_notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numeronota TEXT,
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
    """)
    
    conn.commit()
    print("✅ Tablas creadas/verificadas")

def limpiar_tablas(conn):
    """Limpia los datos existentes para recargar"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lineas_notas")
    cursor.execute("DELETE FROM lineas_factura")
    cursor.execute("DELETE FROM notascredito")
    cursor.execute("DELETE FROM facturas")
    conn.commit()
    print("🗑️  Tablas limpias (datos anteriores eliminados)")

def cargar_jsonl(conn, archivo_jsonl, config):
    """Carga un archivo JSONL a una tabla"""
    ruta = os.path.join(OUTPUT_DIR, archivo_jsonl)
    
    if not os.path.exists(ruta):
        print(f"❌ Archivo NO encontrado: {ruta}")
        return 0
    
    cursor = conn.cursor()
    tabla = config["table"]
    contador = 0
    
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                
                try:
                    registro = json.loads(linea)
                    
                    # Construir INSERT dinámico
                    columnas = ", ".join(registro.keys())
                    placeholders = ", ".join(["?" for _ in registro.keys()])
                    valores = list(registro.values())
                    
                    query = f"INSERT INTO {tabla} ({columnas}) VALUES ({placeholders})"
                    cursor.execute(query, valores)
                    contador += 1
                    
                except json.JSONDecodeError as e:
                    print(f"  ⚠️  Error JSON en línea: {linea[:50]}... - {str(e)}")
                except Exception as e:
                    print(f"  ⚠️  Error inserción: {str(e)}")
        
        conn.commit()
        print(f"📥 {archivo_jsonl:25} → {tabla:20} ✅ {contador:6} registros")
        return contador
    
    except Exception as e:
        print(f"❌ Error cargando {archivo_jsonl}: {str(e)}")
        return 0

def verificar_carga(conn):
    """Verifica cuántos registros se cargaron"""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("📊 VERIFICACIÓN DE CARGA")
    print("="*80)
    
    for tabla in ["facturas", "lineas_factura", "notascredito", "lineas_notas"]:
        cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Mostrar 1 ejemplo
            cursor.execute(f"SELECT * FROM {tabla} LIMIT 1")
            cols = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            
            print(f"\n✅ {tabla.upper()}: {count} registros")
            print(f"   Primer registro:")
            for col, val in zip(cols, row):
                if isinstance(val, str) and len(str(val)) > 50:
                    val = str(val)[:50] + "..."
                print(f"     • {col}: {val}")
        else:
            print(f"\n⚠️  {tabla.upper()}: 0 registros")
    
    print("\n" + "="*80)

def main():
    print("="*80)
    print("🚀 CARGAR 4 JSON A SQLITE")
    print("="*80)
    
    # Conectar a DB
    conn = sqlite3.connect(DB_FILE)
    
    # 1. Crear tablas
    print("\n1️⃣  Creando estructura de tablas...")
    crear_tablas(conn)
    
    # 2. Limpiar datos previos
    print("\n2️⃣  Limpiando datos anteriores...")
    limpiar_tablas(conn)
    
    # 3. Cargar cada archivo
    print("\n3️⃣  Cargando archivos JSONL...")
    print("-"*80)
    
    total_general = 0
    for archivo, config in FILES_CONFIG.items():
        cantidad = cargar_jsonl(conn, archivo, config)
        total_general += cantidad
    
    # 4. Verificar
    print("\n4️⃣  Verificando carga...")
    verificar_carga(conn)
    
    conn.close()
    
    print(f"\n✅ CARGA COMPLETADA: {total_general} registros total\n")

if __name__ == "__main__":
    main()