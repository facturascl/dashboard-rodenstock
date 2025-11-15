
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict

DB_FILE = "facturas.db"


# ============================================================================
# INICIALIZAR BD (igual que antes)
# ============================================================================

def init_sqlite_db():
    """Crea o valida tablas en SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla: facturas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura TEXT UNIQUE,
            fecha TEXT,
            cliente TEXT,
            monto_total REAL,
            pdf_hash INTEGER,
            fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla: notas_credito
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas_credito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_nota TEXT UNIQUE,
            fecha TEXT,
            cliente TEXT,
            monto_total REAL,
            pdf_hash INTEGER,
            fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Base de datos SQLite inicializada: {DB_FILE}\n")


# ============================================================================
# CARGA DESDE JSON
# ============================================================================

def load_json_file(filepath: str) -> List[Dict]:
    """Lee un archivo JSONL (newline-delimited JSON)."""
    records = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                    if record:
                        records.append(record)
                except json.JSONDecodeError as e:
                    print(f"  ⚠️  Línea {i} inválida: {e}")
                    continue
        
        print(f"📖 Leído {len(records)} registros de: {filepath}\n")
        return records
        
    except FileNotFoundError:
        print(f"❌ Archivo no encontrado: {filepath}")
        return []
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return []


# ============================================================================
# DETECTAR TIPO DE DATO
# ============================================================================

def detect_record_type(record: Dict) -> str:
    """Detecta si es factura o nota de crédito."""
    keys = set(record.keys())
    
    # Buscar claves indicativas
    if any(k in keys for k in ['numero_nota', 'nota_num', 'credit_note']):
        return 'nota_credito'
    elif any(k in keys for k in ['numero_factura', 'factura_num', 'invoice_num']):
        return 'factura'
    
    # Por defecto: si tiene "monto" y "fecha", es probablemente factura
    if 'monto_total' in keys or 'total' in keys:
        return 'factura'
    
    return None


# ============================================================================
# CARGA A SQLITE
# ============================================================================

def upload_facturas(records: List[Dict]) -> Dict:
    """Carga facturas a SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    stats = {
        'insertadas': 0,
        'duplicadas': 0,
        'errores': 0
    }
    
    for i, record in enumerate(records, 1):
        try:
            numero_factura = (
                record.get('numero_factura') or 
                record.get('factura_num') or 
                record.get('numero') or
                f"FACTURA_{i}"
            )
            
            fecha = (
                record.get('fecha') or 
                record.get('date') or
                datetime.now().isoformat()
            )
            
            cliente = (
                record.get('cliente') or 
                record.get('customer') or
                'DESCONOCIDO'
            )
            
            monto = float(record.get('monto_total') or record.get('total') or 0)
            
            pdf_hash = (
                record.get('pdf_hash') or 
                hash(str(record)) % 10**8
            )
            
            cursor.execute('''
                INSERT INTO facturas 
                (numero_factura, fecha, cliente, monto_total, pdf_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (numero_factura, fecha, cliente, monto, pdf_hash))
            
            stats['insertadas'] += 1
            
        except sqlite3.IntegrityError:
            stats['duplicadas'] += 1
        except Exception as e:
            print(f"  ⚠️  Error en registro {i}: {e}")
            stats['errores'] += 1
    
    conn.commit()
    conn.close()
    return stats


def upload_notas_credito(records: List[Dict]) -> Dict:
    """Carga notas de crédito a SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    stats = {
        'insertadas': 0,
        'duplicadas': 0,
        'errores': 0
    }
    
    for i, record in enumerate(records, 1):
        try:
            numero_nota = (
                record.get('numero_nota') or 
                record.get('nota_num') or 
                record.get('numero') or
                f"NOTA_{i}"
            )
            
            fecha = (
                record.get('fecha') or 
                record.get('date') or
                datetime.now().isoformat()
            )
            
            cliente = (
                record.get('cliente') or 
                record.get('customer') or
                'DESCONOCIDO'
            )
            
            monto = float(record.get('monto_total') or record.get('total') or 0)
            
            pdf_hash = (
                record.get('pdf_hash') or 
                hash(str(record)) % 10**8
            )
            
            cursor.execute('''
                INSERT INTO notas_credito 
                (numero_nota, fecha, cliente, monto_total, pdf_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (numero_nota, fecha, cliente, monto, pdf_hash))
            
            stats['insertadas'] += 1
            
        except sqlite3.IntegrityError:
            stats['duplicadas'] += 1
        except Exception as e:
            print(f"  ⚠️  Error en registro {i}: {e}")
            stats['errores'] += 1
    
    conn.commit()
    conn.close()
    return stats


# ============================================================================
# ESTADÍSTICAS
# ============================================================================

def show_stats():
    """Muestra estadísticas finales."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM facturas")
    total_facturas = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(monto_total) FROM facturas")
    monto_facturas = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM notas_credito")
    total_notas = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(monto_total) FROM notas_credito")
    monto_notas = cursor.fetchone()[0] or 0
    
    conn.close()
    
    print("📊 ESTADÍSTICAS DE LA BASE DE DATOS:")
    print(f"   📋 Facturas: {total_facturas} | Monto: ${monto_facturas:,.2f}")
    print(f"   📝 Notas de Crédito: {total_notas} | Monto: ${monto_notas:,.2f}")
    print()


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("⚡ CARGA RÁPIDA - JSON → SQLite")
    print("="*70 + "\n")
    
    # 1. Argumentos
    if len(sys.argv) < 2:
        print("USO:")
        print("  python carga_rapida_sqlite.py <archivo.jsonl>")
        print("\nEJEMPLOS:")
        print("  python carga_rapida_sqlite.py outputs/notas.jsonl")
        print("  python carga_rapida_sqlite.py outputs/facturas.jsonl")
        print()
        return
    
    json_file = sys.argv[1]
    
    # Verificar archivo
    if not Path(json_file).exists():
        print(f"❌ Archivo no encontrado: {json_file}\n")
        return
    
    # 2. Inicializar BD
    print("🔧 Inicializando base de datos...")
    init_sqlite_db()
    
    # 3. Cargar JSON
    print(f"📥 Leyendo: {json_file}")
    records = load_json_file(json_file)
    
    if not records:
        print("❌ No hay datos para cargar\n")
        return
    
    # 4. Detectar tipo y cargar
    print("📤 Detectando tipo de datos...\n")
    
    record_type = detect_record_type(records[0])
    
    if record_type == 'nota_credito':
        print("✓ Tipo detectado: NOTAS DE CRÉDITO\n")
        stats = upload_notas_credito(records)
    elif record_type == 'factura':
        print("✓ Tipo detectado: FACTURAS\n")
        stats = upload_facturas(records)
    else:
        print("⚠️  Tipo desconocido, cargando como FACTURAS...\n")
        stats = upload_facturas(records)
    
    # 5. Mostrar resultados
    print("✅ CARGA COMPLETADA:")
    print(f"   • Insertadas: {stats['insertadas']}")
    print(f"   • Duplicadas: {stats['duplicadas']}")
    print(f"   • Errores: {stats['errores']}")
    print()
    
    # 6. Estadísticas generales
    show_stats()
    
    print("💡 PRÓXIMO PASO:")
    print("   streamlit run app_dashboard.py")
    print()


if __name__ == "__main__":
    main()