
import sqlite3
import json

DB_FILE = "facturas.db"

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

print("="*80)
print("ESTRUCTURA DE TABLAS EN SQLITE")
print("="*80)

# Listar tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for (table_name,) in tables:
    print(f"\n📋 TABLA: {table_name}")
    print("-"*80)
    
    # Estructura
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print("Columnas:")
    for col in columns:
        print(f"  • {col[1]} ({col[2]})")
    
    # Contar registros
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"\n📊 Total registros: {count}")
    
    # Si hay registros, mostrar 1 ejemplo
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        row = cursor.fetchone()
        print(f"\n✅ EJEMPLO (primer registro):")
        for i, col in enumerate(columns):
            col_name = col[1]
            value = row[i]
            # Si es muy largo, truncar
            if isinstance(value, str) and len(str(value)) > 100:
                value = str(value)[:100] + "..."
            print(f"  {col_name}: {value}")

print("\n" + "="*80)

# Consulta específica: ¿Hay datos de clasificación?
print("\n🔍 BÚSQUEDA DE CLASIFICACIÓN:")
print("="*80)

if "lineas_factura" in [t[0] for t in tables]:
    cursor.execute("""
    SELECT 
      COUNT(*) as total,
      COUNT(DISTINCT clasificacion_categoria) as categorias,
      COUNT(DISTINCT clasificacion_subcategoria) as subcategorias
    FROM lineas_factura
    """)
    result = cursor.fetchone()
    print(f"\nlineas_factura:")
    print(f"  • Total líneas: {result[0]}")
    print(f"  • Categorías distintas: {result[1]}")
    print(f"  • Subcategorías distintas: {result[2]}")

if "lineas_notas" in [t[0] for t in tables]:
    cursor.execute("""
    SELECT 
      COUNT(*) as total,
      COUNT(DISTINCT clasificacion_categoria) as categorias,
      COUNT(DISTINCT clasificacion_subcategoria) as subcategorias
    FROM lineas_notas
    """)
    result = cursor.fetchone()
    print(f"\nlineas_notas:")
    print(f"  • Total líneas: {result[0]}")
    print(f"  • Categorías distintas: {result[1]}")
    print(f"  • Subcategorías distintas: {result[2]}")

conn.close()
print("\n" + "="*80)