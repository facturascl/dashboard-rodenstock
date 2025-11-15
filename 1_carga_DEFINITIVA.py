
import sys
import json
import sqlite3
from pathlib import Path

DB_FILE = "facturas.db"

def crear_tablas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS facturas (
        numerofactura TEXT PRIMARY KEY,
        fechaemision TEXT, subtotal REAL, descuento_pesos REAL,
        valorneto REAL, iva REAL, total REAL, cantidad_lineas INTEGER)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS lineas_factura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numerofactura TEXT NOT NULL,
        linea_numero INTEGER, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, descuento_pesos_porcentaje REAL,
        total_linea REAL, clasificacion_categoria TEXT,
        clasificacion_subcategoria TEXT,
        FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS notascredito (
        numeronota TEXT PRIMARY KEY,
        fechaemision TEXT, subtotal REAL, descuento_pesos REAL,
        valorneto REAL, iva REAL, total REAL, cantidad_lineas INTEGER)''')
    
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

def cargar_facturas(archivo):
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return 0, 0
    
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
                cantidad_lineas = registro.get('cantidad_lineas', 0)
                
                cursor.execute('''INSERT OR REPLACE INTO facturas 
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                facturas += 1
                
                # Buscar líneas en diferentes campos posibles
                items = registro.get('lineas') or registro.get('items') or []
                
                for id_linea, item in enumerate(items, 1):
                    if isinstance(item, dict):
                        desc = item.get('descripcion', '')
                        cant = float(item.get('cantidad') or 0)
                        precio = float(item.get('precio_unitario') or 0)
                        desc_porc = float(item.get('descuento_pesos_porcentaje') or 0)
                        total_lin = float(item.get('total_linea') or 0)
                        cat = item.get('clasificacion_categoria', '')
                        subcat = item.get('clasificacion_subcategoria', '')
                        
                        cursor.execute('''INSERT INTO lineas_factura 
                            (numerofactura,linea_numero,descripcion,cantidad,precio_unitario,
                             descuento_pesos_porcentaje,total_linea,clasificacion_categoria,
                             clasificacion_subcategoria) 
                            VALUES (?,?,?,?,?,?,?,?,?)''',
                            (numero, id_linea, desc, cant, precio, desc_porc, total_lin, cat, subcat))
                        lineas += 1
            except Exception as e:
                pass
    
    conn.commit()
    conn.close()
    return facturas, lineas

def cargar_notas(archivo):
    if not Path(archivo).exists():
        print(f"❌ {archivo} no encontrado")
        return 0, 0
    
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
                cantidad_lineas = registro.get('cantidad_lineas', 0)
                
                cursor.execute('''INSERT OR REPLACE INTO notascredito 
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (numero, fecha, subtotal, descuento, valorneto, iva, total, cantidad_lineas))
                notas += 1
                
                # Buscar líneas
                items = registro.get('lineas') or registro.get('items') or []
                
                for id_linea, item in enumerate(items, 1):
                    if isinstance(item, dict):
                        desc = item.get('descripcion', '')
                        cant = float(item.get('cantidad') or 0)
                        precio = float(item.get('precio_unitario') or 0)
                        desc_porc = float(item.get('descuento_pesos_porcentaje') or 0)
                        total_lin = float(item.get('total_linea') or 0)
                        cat = item.get('clasificacion_categoria', '')
                        subcat = item.get('clasificacion_subcategoria', '')
                        
                        cursor.execute('''INSERT INTO lineas_notas 
                            (numeronota,linea_numero,descripcion,cantidad,precio_unitario,
                             descuento_pesos_porcentaje,total_linea,clasificacion_categoria,
                             clasificacion_subcategoria) 
                            VALUES (?,?,?,?,?,?,?,?,?)''',
                            (numero, id_linea, desc, cant, precio, desc_porc, total_lin, cat, subcat))
                        lineas += 1
            except Exception as e:
                pass
    
    conn.commit()
    conn.close()
    return notas, lineas

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CARGA DEFINITIVA - SQLite (4 TABLAS CON LÍNEAS)")
    print("="*70 + "\n")
    
    crear_tablas()
    
    print("📥 Cargando facturas...")
    fact, lineas_fact = cargar_facturas("outputs/facturas.jsonl")
    print(f"✅ Facturas: {fact} | Líneas: {lineas_fact}")
    
    print("📥 Cargando notas...")
    notas, lineas_notas = cargar_notas("outputs/notas.jsonl")
    print(f"✅ Notas: {notas} | Líneas: {lineas_notas}")
    
    print("\n" + "="*70)
    print("✅ LISTO PARA VER EN DASHBOARD")
    print("="*70 + "\n")