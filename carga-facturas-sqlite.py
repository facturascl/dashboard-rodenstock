
import os
import json
import base64
import pickle
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.oauthlib.flow import InstalledAppFlow
import google.auth
from googleapiclient.discovery import build

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"
OUTPUT_DIR = "outputs"
DB_FILE = "facturas.db"  # ← Base de datos SQLite local

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================================
# INICIALIZACIÓN DE BASE DE DATOS SQLITE
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
    
    # Tabla: lineas_factura
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lineas_factura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura TEXT,
            id_linea INTEGER,
            descripcion TEXT,
            cantidad REAL,
            precio_unitario REAL,
            FOREIGN KEY (numero_factura) REFERENCES facturas(numero_factura)
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
    
    # Tabla: lineas_notas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lineas_notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_nota TEXT,
            id_linea INTEGER,
            descripcion TEXT,
            cantidad REAL,
            precio_unitario REAL,
            FOREIGN KEY (numero_nota) REFERENCES notas_credito(numero_nota)
        )
    ''')
    
    # Tabla de control: qué mensajes ya fueron procesados (evita duplicados)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes_procesados (
            id INTEGER PRIMARY KEY,
            email_id TEXT UNIQUE,
            fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Base de datos SQLite inicializada: {DB_FILE}")


# ============================================================================
# FUNCIONES DE AUTENTICACIÓN
# ============================================================================

def get_gmail_service():
    """Autentica y retorna el servicio de Gmail."""
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)


# ============================================================================
# EXTRACCIÓN DE FACTURAS DESDE GMAIL
# ============================================================================

def extract_invoice_data_from_pdf(pdf_content: bytes) -> Dict:
    """
    Extrae datos de factura desde contenido PDF.
    Retorna diccionario con estructura normalizada.
    """
    try:
        import PyPDF2
        from io import BytesIO
        
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # Parsing básico (adapta según tu formato de PDF)
        invoice_data = {
            "numero_factura": extract_field(text, "Factura") or "SIN_NUMERO",
            "fecha": extract_field(text, "Fecha") or datetime.now().isoformat(),
            "cliente": extract_field(text, "Cliente") or "DESCONOCIDO",
            "monto_total": float(extract_field(text, "Total") or "0"),
            "pdf_hash": hash(pdf_content) % 10**8,
        }
        
        return invoice_data
    except Exception as e:
        print(f"⚠️  Error extrayendo PDF: {e}")
        return {}


def extract_field(text: str, keyword: str) -> Optional[str]:
    """Extrae campo simple de texto."""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            return line.split(':', 1)[-1].strip() if ':' in line else None
    return None


def download_invoices_from_gmail(service, since_date: str = None):
    """
    Descarga facturas desde Gmail y retorna solo las no procesadas.
    
    Args:
        service: Gmail API service
        since_date: Fecha mínima en formato "2025-01-01"
    
    Returns:
        List[Dict]: Lista de facturas nuevas
    """
    invoices = []
    processed_ids = set()
    
    # Leer IDs ya procesados
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email_id FROM mensajes_procesados")
    processed_ids = set(row[0] for row in cursor.fetchall())
    conn.close()
    
    query = 'filename:pdf'
    if since_date:
        query += f' after:{since_date}'
    
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=500
        ).execute()
        
        messages = results.get('messages', [])
        print(f"📧 Encontrados {len(messages)} mensajes con PDFs")
        print(f"   (Ya procesados: {len(processed_ids)})")
        
        for i, message in enumerate(messages):
            msg_id = message['id']
            
            # Saltar si ya fue procesado
            if msg_id in processed_ids:
                print(f"  ⊘ Mensaje {msg_id[:8]}... ya procesado")
                continue
            
            msg = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            # Procesar attachments
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part['filename'] and 'pdf' in part['filename'].lower():
                        attachment = service.users().messages().attachments().get(
                            userId='me',
                            messageId=msg_id,
                            id=part['body'].get('attachmentId')
                        ).execute()
                        
                        file_data = base64.urlsafe_b64decode(
                            attachment['data'].encode('UTF-8')
                        )
                        
                        invoice = extract_invoice_data_from_pdf(file_data)
                        if invoice and invoice.get('numero_factura') != 'SIN_NUMERO':
                            invoice['_email_id'] = msg_id  # Marcar para later
                            invoices.append(invoice)
            
            if (i + 1) % 50 == 0:
                print(f"  ↳ Procesados {i + 1}/{len(messages)}...")
        
        print(f"✅ Nuevas facturas encontradas: {len(invoices)}")
        return invoices
        
    except Exception as e:
        print(f"❌ Error descargando de Gmail: {e}")
        return []


# ============================================================================
# CARGA A SQLITE
# ============================================================================

def upload_to_sqlite(invoices: List[Dict]) -> int:
    """
    Carga facturas a SQLite.
    
    Args:
        invoices: Lista de diccionarios con datos de facturas
    
    Returns:
        int: Cantidad de registros insertados
    """
    if not invoices:
        print("⚠️  No hay facturas para cargar")
        return 0
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    inserted = 0
    duplicates = 0
    
    try:
        for inv in invoices:
            email_id = inv.pop('_email_id', None)
            
            try:
                cursor.execute('''
                    INSERT INTO facturas 
                    (numero_factura, fecha, cliente, monto_total, pdf_hash)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    inv['numero_factura'],
                    inv['fecha'],
                    inv['cliente'],
                    inv['monto_total'],
                    inv['pdf_hash']
                ))
                
                inserted += 1
                
                # Marcar como procesado
                if email_id:
                    cursor.execute(
                        'INSERT OR IGNORE INTO mensajes_procesados (email_id) VALUES (?)',
                        (email_id,)
                    )
                
            except sqlite3.IntegrityError:
                duplicates += 1
                print(f"  ⊘ Duplicado: {inv['numero_factura']}")
        
        conn.commit()
        print(f"✅ Carga completada:")
        print(f"   • Insertados: {inserted}")
        print(f"   • Duplicados: {duplicates}")
        
        return inserted
        
    except Exception as e:
        print(f"❌ Error cargando a SQLite: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


# ============================================================================
# EXPORTACIÓN A CSV (Para Looker Studio)
# ============================================================================

def export_to_csv():
    """Exporta datos de SQLite a CSV para Looker Studio."""
    import pandas as pd
    
    conn = sqlite3.connect(DB_FILE)
    
    # Leer facturas
    df_facturas = pd.read_sql_query(
        "SELECT * FROM facturas ORDER BY fecha_carga DESC",
        conn
    )
    
    # Guardar CSV
    csv_file = f"{OUTPUT_DIR}/facturas_export.csv"
    df_facturas.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"✅ Exportado a CSV: {csv_file}")
    
    conn.close()
    return csv_file


# ============================================================================
# UTILITIES PARA STREAMLIT
# ============================================================================

def get_facturas_from_db():
    """Retorna DataFrame con todas las facturas (para Streamlit)."""
    import pandas as pd
    
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM facturas ORDER BY fecha_carga DESC",
        conn
    )
    conn.close()
    return df


def get_estadisticas():
    """Retorna estadísticas de facturas."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM facturas")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(monto_total) FROM facturas")
    monto_total = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(DISTINCT cliente) FROM facturas")
    clientes = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_facturas": total,
        "monto_total": monto_total,
        "total_clientes": clientes
    }


# ============================================================================
# ORQUESTACIÓN PRINCIPAL
# ============================================================================

def main():
    """Flujo principal del script."""
    print("\n" + "="*70)
    print("🚀 SCRIPT RODENSTOCK - EXTRACCIÓN Y CARGA A SQLITE")
    print("="*70 + "\n")
    
    # 1. Inicializar BD
    print("🔧 Inicializando base de datos SQLite...")
    init_sqlite_db()
    print()
    
    # 2. Autenticar con Gmail
    print("🔐 Autenticando con Google...")
    try:
        gmail_service = get_gmail_service()
        print("✅ Autenticación exitosa\n")
    except Exception as e:
        print(f"❌ Error de autenticación: {e}")
        return
    
    # 3. Descargar facturas nuevas desde Gmail
    print("📥 Descargando facturas desde Gmail...")
    invoices = download_invoices_from_gmail(
        gmail_service,
        since_date="2025-01-01"
    )
    
    if not invoices:
        print("⚠️  No hay nuevas facturas para procesar.")
        stats = get_estadisticas()
        print(f"\n📊 Estado actual de la BD:")
        print(f"   • Total facturas: {stats['total_facturas']}")
        print(f"   • Monto acumulado: ${stats['monto_total']:,.2f}")
        print(f"   • Clientes únicos: {stats['total_clientes']}")
        return
    
    print()
    
    # 4. Cargar a SQLite
    print("💾 Cargando a SQLite...")
    inserted = upload_to_sqlite(invoices)
    print()
    
    # 5. Exportar a CSV
    print("📤 Exportando a CSV para Looker Studio...")
    csv_file = export_to_csv()
    print()
    
    # 6. Mostrar estadísticas
    stats = get_estadisticas()
    print("📊 ESTADÍSTICAS FINALES:")
    print(f"   • Total facturas: {stats['total_facturas']}")
    print(f"   • Monto acumulado: ${stats['monto_total']:,.2f}")
    print(f"   • Clientes únicos: {stats['total_clientes']}")
    print()
    
    print("📌 PRÓXIMOS PASOS:")
    print(f"   1. Archivo CSV: {csv_file}")
    print(f"   2. Importar en Looker Studio: Datos → Nueva fuente de datos → CSV")
    print(f"   3. O crear dashboard Streamlit (ver app_dashboard.py)")
    print()


if __name__ == "__main__":
    main()
