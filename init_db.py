
import sqlite3
import random
from datetime import datetime, timedelta

DB_FILE = "facturas.db"

def create_database():
    """Crea las tablas y genera datos demo"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Crear tabla facturas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS facturas (
        numerofactura TEXT PRIMARY KEY,
        fechaemision TEXT,
        subtotal REAL,
        iva REAL
    )
    ''')
    
    # Crear tabla lineas_factura
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lineas_factura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numerofactura TEXT,
        clasificacion_categoria TEXT,
        clasificacion_subcategoria TEXT,
        FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura)
    )
    ''')
    
    # Datos de ejemplo
    categorias = {
        'Monofocales': ['Policarbonato azul', 'Hi-index Verde', 'Polarizado', 'Fotocromático', 'Policarbonato verde', 'CR39'],
        'Progresivo': ['Verde', 'Azul', 'Fotocromático'],
        'Newton': ['Newton Standard'],
        'Newton Plus': ['Newton Plus Premium'],
    }
    
    # Generar facturas para Enero 2025
    start_date = datetime(2025, 1, 1)
    num_facturas = 433  # Exactamente 433 para que coincida con tus datos
    
    factura_num = 1000
    for i in range(num_facturas):
        # Distribución de fechas en el mes
        days_offset = random.randint(0, 30)
        fecha = start_date + timedelta(days=days_offset)
        fecha_str = fecha.strftime('%Y-%m-%d')
        
        numerofactura = f"FAC{factura_num:06d}"
        factura_num += 1
        
        # Subtotal entre $100 y $5000
        subtotal = round(random.uniform(100, 5000), 2)
        iva = round(subtotal * 0.19, 2)  # Chile 19% IVA
        
        cursor.execute(
            'INSERT OR IGNORE INTO facturas VALUES (?, ?, ?, ?)',
            (numerofactura, fecha_str, subtotal, iva)
        )
        
        # Insertar 1-3 líneas por factura (con categorías variadas)
        num_lineas = random.randint(1, 3)
        
        # Distribución por categoría (ajustada para ~57% Monofocales, ~42% Progresivo, ~1% otros)
        cat_choice = random.randint(1, 100)
        if cat_choice <= 57:
            categoria = 'Monofocales'
        elif cat_choice <= 99:
            categoria = 'Progresivo'
        elif cat_choice <= 100:
            categoria = random.choice(['Newton', 'Newton Plus'])
        
        subcategoria = random.choice(categorias.get(categoria, ['Sin subcategoría']))
        
        for _ in range(num_lineas):
            cursor.execute(
                'INSERT INTO lineas_factura (numerofactura, clasificacion_categoria, clasificacion_subcategoria) VALUES (?, ?, ?)',
                (numerofactura, categoria, subcategoria)
            )
    
    conn.commit()
    conn.close()
    print(f"✅ Base de datos '{DB_FILE}' creada con {num_facturas} facturas demo")
    print("   Lista para usar con Streamlit Cloud")

if __name__ == "__main__":
    create_database()