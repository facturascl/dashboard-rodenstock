#!/usr/bin/env python3
"""
Script de extracción de facturas Rodenstock desde Gmail
Versión 2.0 - Con clasificación automática desde librería y corrección de precios
"""

import os
import base64
import re
import json
import pdfplumber
import pandas as pd
from datetime import datetime
from email.utils import parsedate_to_datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ============ CONFIGURACIÓN ============
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
PROJECT_ID = 'rodenstock-471300'
DATASET = "facturacion"
OUTPUT_DIR = "outputs"
PDF_SAVE_DIR = "pdf_attachments"
LAST_PROCESSED_DATE_FILE = 'last_processed.txt'
PROCESSED_MSGS_FILE = 'processed_messages.json'
LIBRERIA_PATH = 'libreria.xlsx'
BASE_QUERY = 'from:facturacion@rodenstock.cl in:inbox'


# ============ FUNCIONES DE UTILIDAD ============

def ensure_dirs():
    """Crea directorios necesarios si no existen"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PDF_SAVE_DIR, exist_ok=True)


def normalize_text(s):
    """Normaliza texto: elimina espacios extra y convierte a string"""
    if s is None:
        return ''
    return re.sub(r'\s+', ' ', str(s)).strip()


def limpiar_prefijo_numerico(texto):
    """
    Elimina prefijos numéricos al inicio del texto.
    Ejemplos: "65 Progressiv Pro L" -> "Progressiv Pro L"
    """
    if not texto:
        return texto
    texto = str(texto).strip()
    texto_limpio = re.sub(r'^\d+\s+', '', texto)
    return texto_limpio.strip()


def parse_number(s):
    """
    Convierte string a número manejando formatos chilenos y decimales.
    
    Casos:
    - "8.306" con punto → Si tiene 3 dígitos después del punto = miles → 8306
    - "6.98" con punto → Si tiene 1-2 dígitos después del punto = decimal → 6.98
    - "6,98" → coma es decimal → 6.98
    - "1.234,56" → punto miles, coma decimal → 1234.56
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return s
    
    s = str(s).strip()
    if s == '' or s == '-':
        return None
    
    # Eliminar espacios
    s = s.replace(' ', '')
    
    # Detectar si tiene tanto punto como coma
    tiene_punto = '.' in s
    tiene_coma = ',' in s
    
    if tiene_punto and tiene_coma:
        # Formato: 1.234,56 → punto es miles, coma es decimal
        s = s.replace('.', '').replace(',', '.')
    elif tiene_coma and not tiene_punto:
        # Formato: 1234,56 → coma es decimal
        s = s.replace(',', '.')
    elif tiene_punto and not tiene_coma:
        # Ambiguo: puede ser miles o decimal
        # Detectar basándose en la posición del punto
        partes = s.split('.')
        if len(partes) == 2:
            parte_entera = partes[0]
            parte_decimal = partes[1]
            
            # Si la parte decimal tiene exactamente 3 dígitos, probablemente es separador de miles
            # Ejemplo: "8.306" → 8306
            if len(parte_decimal) == 3 and parte_entera.isdigit() and parte_decimal.isdigit():
                s = parte_entera + parte_decimal
            # Si la parte decimal tiene 1 o 2 dígitos, es decimal
            # Ejemplo: "6.98" → 6.98
            elif len(parte_decimal) <= 2:
                # Dejar el punto como está (ya es formato decimal correcto)
                pass
            else:
                # Caso extraño, eliminar puntos
                s = s.replace('.', '')
    
    # Limpiar caracteres no numéricos excepto punto y signo negativo
    s = re.sub(r'[^\d\.\-]', '', s)
    
    try:
        if s == '' or s == '-':
            return None
        val = float(s) if '.' in s else int(s)
        return val
    except:
        return None


# ============ LIBRERÍA DE PRODUCTOS ============

def cargar_libreria():
    """
    Carga la librería de productos y la estructura en 3 tipos de reglas.
    Normaliza todo a minúsculas para comparación.
    """
    df = pd.read_excel(LIBRERIA_PATH)
    
    reglas = {
        'producto_y_tratamiento': [],
        'solo_producto': [],
        'solo_tratamiento': []
    }
    
    for _, row in df.iterrows():
        producto = row['Prodcuto'] if pd.notna(row['Prodcuto']) else None
        tratamiento = row['Tratamiento'] if pd.notna(row['Tratamiento']) else None
        categoria = row['Categoria']
        subcategoria = row['Sub categoria']
        
        # Normalizar texto para búsqueda (minúsculas, sin espacios extra)
        producto_norm = normalize_text(producto).lower() if producto else None
        tratamiento_norm = normalize_text(tratamiento).lower() if tratamiento else None
        
        if producto and tratamiento:
            reglas['producto_y_tratamiento'].append({
                'producto': producto_norm,
                'tratamiento': tratamiento_norm,
                'categoria': categoria,
                'subcategoria': subcategoria,
                'especificidad': len(producto_norm) + len(tratamiento_norm)
            })
        elif producto:
            reglas['solo_producto'].append({
                'producto': producto_norm,
                'categoria': categoria,
                'subcategoria': subcategoria,
                'especificidad': len(producto_norm)
            })
        elif tratamiento:
            reglas['solo_tratamiento'].append({
                'tratamiento': tratamiento_norm,
                'categoria': categoria,
                'subcategoria': subcategoria,
                'especificidad': len(tratamiento_norm)
            })
    
    # Ordenar por especificidad (más específico primero)
    reglas['producto_y_tratamiento'].sort(key=lambda x: x['especificidad'], reverse=True)
    reglas['solo_producto'].sort(key=lambda x: x['especificidad'], reverse=True)
    reglas['solo_tratamiento'].sort(key=lambda x: x['especificidad'], reverse=True)
    
    print(f"✅ Librería cargada: {len(reglas['producto_y_tratamiento'])} producto+tratamiento, "
          f"{len(reglas['solo_producto'])} solo producto, {len(reglas['solo_tratamiento'])} solo tratamiento")
    
    return reglas


def clasificar_lineas_factura(lineas, reglas):
    """
    Clasifica todas las líneas de una factura buscando coincidencias con la librería.
    Retorna la categoría más específica encontrada.
    Búsqueda en texto completo de la factura y prioridad por especificidad.
    """
    if not lineas:
        return 'Sin clasificacion', 'Sin clasificacion'
    
    # Extraer TODAS las descripciones de la factura en un solo texto normalizado
    texto_completo = ' '.join([
        normalize_text(linea.get('descripcion', '')).lower() 
        for linea in lineas
    ])
    
    mejor_match = None
    mayor_especificidad = 0
    
    # PRIORIDAD 1: Buscar coincidencia de producto Y tratamiento
    for regla in reglas['producto_y_tratamiento']:
        if regla['producto'] in texto_completo and regla['tratamiento'] in texto_completo:
            if regla['especificidad'] > mayor_especificidad:
                mejor_match = regla
                mayor_especificidad = regla['especificidad']
    
    if mejor_match:
        return mejor_match['categoria'], mejor_match['subcategoria']
    
    # PRIORIDAD 2: Buscar coincidencia solo por tratamiento
    for regla in reglas['solo_tratamiento']:
        if regla['tratamiento'] in texto_completo:
            if regla['especificidad'] > mayor_especificidad:
                mejor_match = regla
                mayor_especificidad = regla['especificidad']
    
    if mejor_match:
        return mejor_match['categoria'], mejor_match['subcategoria']
    
    # PRIORIDAD 3: Buscar coincidencia solo por producto
    for regla in reglas['solo_producto']:
        if regla['producto'] in texto_completo:
            if regla['especificidad'] > mayor_especificidad:
                mejor_match = regla
                mayor_especificidad = regla['especificidad']
    
    if mejor_match:
        return mejor_match['categoria'], mejor_match['subcategoria']
    
    # No se encontró clasificación
    return 'Sin clasificacion', 'Sin clasificacion'


# ============ GMAIL ============

def authenticate_gmail():
    """Autentica con Gmail API"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def get_all_messages(service, query):
    """Obtiene todos los mensajes que coinciden con el query"""
    messages = []
    page_token = None
    while True:
        resp = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        msgs = resp.get('messages', [])
        if not msgs:
            break
        messages.extend(msgs)
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return messages


def save_pdf_attachments(service, msg_id):
    """Guarda adjuntos PDF de un mensaje"""
    saved_files = []
    try:
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    except Exception as e:
        print(f"⚠️ No se pudo obtener mensaje {msg_id}: {e}")
        return saved_files

    parts = message.get('payload', {}).get('parts', []) or [message.get('payload', {})]
    for part in parts:
        filename = part.get('filename', '')
        if not filename.lower().endswith('.pdf'):
            continue
        attach_id = part.get('body', {}).get('attachmentId')
        if not attach_id:
            continue
        try:
            attachment = service.users().messages().attachments().get(userId='me', messageId=msg_id, id=attach_id).execute()
        except Exception as e:
            print(f"⚠️ No se pudo obtener adjunto {attach_id} del mensaje {msg_id}: {e}")
            continue
        data = attachment.get('data')
        if not data:
            continue
        file_data = base64.urlsafe_b64decode(data)
        filepath = os.path.join(PDF_SAVE_DIR, filename)
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filename)
            i = 1
            while os.path.exists(os.path.join(PDF_SAVE_DIR, f"{base}_{i}{ext}")):
                i += 1
            filepath = os.path.join(PDF_SAVE_DIR, f"{base}_{i}{ext}")
        with open(filepath, 'wb') as f:
            f.write(file_data)
        saved_files.append(filepath)
        print(f"📥 Guardado adjunto: {filepath}")
    return saved_files


# ============ EXTRACCIÓN DE PDF ============

def extract_header_regex(text):
    """Extrae valores de encabezado de factura usando regex con múltiples patrones"""
    header = {}
    
    # Extraer número de factura
    nro = re.search(r'(?:Factura|N[oº]|Nro|FACTURA)\s*[:#]?\s*([0-9\-]+)', text, re.IGNORECASE)
    if nro:
        header['numero'] = nro.group(1).strip()
    
    patterns = {
        'SUBTOTAL': [
            r'SUB[\s-]?TOTAL\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)',
            r'SUBTOTAL\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)',
            r'Sub\s*Total\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)'
        ],
        'descuento_pesos $': [
            r'descuento[\s_]*pesos?\s*\$?\s*[:\s]*([0-9.,\s]+?)(?=\n|$)',
            r'DESCUENTO\s*\$?\s*[:\s]*([0-9.,\s]+?)(?=\n|$)'
        ],
        'VALOR NETO': [
            r'VALOR\s+NETO\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)',
            r'Valor\s+Neto\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)',
            r'NETO\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)'
        ],
        'IVA': [
            r'I\.?V\.?A\.?\s*(?:\([^)]*\))?\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)',
            r'IVA\s*19%?\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)'
        ],
        'TOTAL': [
            r'\bTOTAL\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)',
            r'Total\s*[:\s]*\$?\s*([0-9.,\s]+?)(?=\n|$)'
        ]
    }
    
    # Intentar cada patrón hasta encontrar match
    for k, pattern_list in patterns.items():
        valor_encontrado = None
        for pattern in pattern_list:
            m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if m:
                valor_str = m.group(1).strip()
                valor_encontrado = parse_number(valor_str)
                if valor_encontrado is not None:
                    break
        header[k] = valor_encontrado
    
    # Calcular TOTAL si no se encontró pero tenemos SUBTOTAL e IVA
    if (header.get('SUBTOTAL') is not None and 
        header.get('IVA') is not None and 
        header.get('TOTAL') is None):
        header['TOTAL'] = header['SUBTOTAL'] + header['IVA']
        print(f"✓ TOTAL calculado: {header['TOTAL']}")
    
    # Si no hay VALOR NETO pero hay SUBTOTAL y descuento, calcularlo
    if (header.get('SUBTOTAL') is not None and 
        header.get('descuento_pesos $') is not None and
        header.get('VALOR NETO') is None):
        header['VALOR NETO'] = header['SUBTOTAL'] - header['descuento_pesos $']
    
    # Si VALOR NETO está pero SUBTOTAL no, usar VALOR NETO como base
    if header.get('VALOR NETO') is not None and header.get('SUBTOTAL') is None:
        header['SUBTOTAL'] = header['VALOR NETO']
    
    return header


def extract_items_from_pdf(pdf_path, numero_factura, is_nota=False):
    """Extrae líneas de items de un PDF"""
    lineas = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pattern = re.compile(
                    r'^\s*(\d{1,3})\s+'  
                    r'([A-Za-z0-9\-\.\/_]+?)\s+'  
                    r'(.+?)\s+'  
                    r'(\d+(?:[.,]\d+)?)\s+'  
                    r'([\d.,]+)\s+'  
                    r'([\d.,]+%?)?'  
                    r'\s+([\d.,]+)\s*$',  
                    re.MULTILINE
                )
                for match in pattern.finditer(text):
                    desc = limpiar_prefijo_numerico(match.group(3).strip())
                    cantidad_raw = parse_number(match.group(4))
                    cantidad = int(cantidad_raw) if cantidad_raw and float(cantidad_raw).is_integer() else cantidad_raw

                    entrada = {
                        ('numerofactura' if not is_nota else 'numeronota'): str(numero_factura),
                        'linea_numero': int(match.group(1)),
                        'descripcion': desc,
                        'cantidad': cantidad,
                        'precio_unitario': parse_number(match.group(5)),
                        'descuento_pesos_porcentaje': parse_number(match.group(6)),
                        'total_linea': parse_number(match.group(7)),
                    }
                    lineas.append(entrada)
    except Exception as e:
        print(f"❌ Error leyendo PDF {pdf_path}: {e}")
    return lineas


# ============ PERSISTENCIA ============

def write_jsonl(path, rows):
    """Escribe filas en formato JSONL"""
    if not rows:
        print(f"⚠️ No hay filas para {os.path.basename(path)}")
        return
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"✅ Generado: {path} ({len(rows)} filas)")


def read_last_date():
    """Lee última fecha procesada"""
    if os.path.exists(LAST_PROCESSED_DATE_FILE):
        with open(LAST_PROCESSED_DATE_FILE, 'r') as f:
            return f.read().strip()
    return '2025-01-01'


def save_last_date(d):
    """Guarda última fecha procesada"""
    with open(LAST_PROCESSED_DATE_FILE, 'w') as f:
        f.write(d)
    print(f"📅 Última fecha guardada: {d}")


def read_processed_msgs():
    """Lee IDs de mensajes procesados"""
    if os.path.exists(PROCESSED_MSGS_FILE):
        with open(PROCESSED_MSGS_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_processed_msgs(s):
    """Guarda IDs de mensajes procesados"""
    with open(PROCESSED_MSGS_FILE, 'w') as f:
        json.dump(list(s), f)
    print(f"📧 Mensajes procesados guardados: {len(s)}")


# ============ MAIN ============

def main():
    print("=" * 60)
    print("🚀 Extracción de Facturas Rodenstock - Versión 2.0")
    print("=" * 60)
    
    ensure_dirs()
    
    # Cargar librería de productos
    print("\n📚 Cargando librería de productos...")
    reglas = cargar_libreria()
    
    # Autenticar Gmail
    print("\n📧 Autenticando con Gmail...")
    service = authenticate_gmail()
    
    # Leer estado previo
    last_date = read_last_date()
    processed_msgs = read_processed_msgs()
    print(f"📅 Última fecha procesada: {last_date}")
    print(f"📧 Mensajes ya procesados: {len(processed_msgs)}")

    # Construir query
    query = f'{BASE_QUERY} after:{last_date.replace("-", "/")}'
    print(f"\n🔍 Query usado: {query}")

    # Obtener mensajes
    msgs = get_all_messages(service, query)
    print(f"📧 Mensajes encontrados: {len(msgs)}")

    facturas, lineas_factura, notas, lineas_notas = [], [], [], []
    new_last_date = last_date

    for i, m in enumerate(msgs, 1):
        msg_id = m['id']
        if msg_id in processed_msgs:
            continue

        print(f"\n[{i}/{len(msgs)}] Procesando mensaje {msg_id}...")
        
        pdfs = save_pdf_attachments(service, msg_id)
        if not pdfs:
            print(f"⚠️ No se procesaron PDFs para el mensaje {msg_id}")
            continue

        msg = None
        try:
            msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        except Exception as e:
            print(f"⚠️ No se pudo obtener mensaje {msg_id}: {e}")
            processed_msgs.add(msg_id)
            continue

        date_header = next((h['value'] for h in msg.get('payload', {}).get('headers', []) if h.get('name') == 'Date'), None)
        if not date_header:
            continue
        dt = parsedate_to_datetime(date_header)
        fecha_iso = dt.strftime('%Y-%m-%d')

        for pdf_path in pdfs:
            filename = os.path.basename(pdf_path)
            print(f"  📄 Procesando: {filename}")
            
            with pdfplumber.open(pdf_path) as pdf:
                text = ''.join([(p.extract_text() or "") + "\n" for p in pdf.pages])
            
            header = extract_header_regex(text)
            numero = header.get('numero') or filename.split('.')[0]
            is_nota = "nota" in filename.lower()

            lineas = extract_items_from_pdf(pdf_path, numero, is_nota=is_nota)
            
            # CLASIFICAR LAS LÍNEAS USANDO LA LIBRERÍA
            categoria, subcategoria = clasificar_lineas_factura(lineas, reglas)
            print(f"  ✅ Clasificado como: {categoria} - {subcategoria}")
            
            # Asignar clasificación a cada línea
            for linea in lineas:
                linea['clasificacion_categoria'] = categoria
                linea['clasificacion_subcategoria'] = subcategoria

            if is_nota:
                notas.append({
                    "numeronota": str(numero),
                    "fechaemision": fecha_iso,
                    "subtotal": header.get('SUBTOTAL'),
                    "descuento_pesos": header.get('descuento_pesos $'),
                    "valorneto": header.get('VALOR NETO'),
                    "iva": header.get('IVA'),
                    "total": header.get('TOTAL'),
                    "cantidad_lineas": len(lineas)
                })
                lineas_notas.extend(lineas)
            else:
                facturas.append({
                    "numerofactura": str(numero),
                    "fechaemision": fecha_iso,
                    "subtotal": header.get('SUBTOTAL'),
                    "descuento_pesos": header.get('descuento_pesos $'),
                    "valorneto": header.get('VALOR NETO'),
                    "iva": header.get('IVA'),
                    "total": header.get('TOTAL'),
                    "cantidad_lineas": len(lineas)
                })
                lineas_factura.extend(lineas)

        processed_msgs.add(msg_id)
        if fecha_iso > new_last_date:
            new_last_date = fecha_iso

    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PROCESAMIENTO")
    print("=" * 60)
    print(f"Facturas: {len(facturas)}")
    print(f"Líneas de factura: {len(lineas_factura)}")
    print(f"Notas de crédito: {len(notas)}")
    print(f"Líneas de notas: {len(lineas_notas)}")

    # Escribir archivos JSONL
    print("\n💾 Generando archivos JSONL...")
    write_jsonl(os.path.join(OUTPUT_DIR, "facturas.jsonl"), facturas)
    write_jsonl(os.path.join(OUTPUT_DIR, "lineas_factura.jsonl"), lineas_factura)
    write_jsonl(os.path.join(OUTPUT_DIR, "notas.jsonl"), notas)
    write_jsonl(os.path.join(OUTPUT_DIR, "lineas_notas.jsonl"), lineas_notas)

    # Guardar estado
    save_last_date(new_last_date)
    save_processed_msgs(processed_msgs)

    print("\n" + "=" * 60)
    print("🚀 COMANDOS DE CARGA EN BIGQUERY")
    print("=" * 60)
    print(f"bq load --source_format=NEWLINE_DELIMITED_JSON --replace {PROJECT_ID}:{DATASET}.facturas {OUTPUT_DIR}/facturas.jsonl")
    print(f"bq load --source_format=NEWLINE_DELIMITED_JSON --replace {PROJECT_ID}:{DATASET}.lineas_factura {OUTPUT_DIR}/lineas_factura.jsonl")
    print(f"bq load --source_format=NEWLINE_DELIMITED_JSON --replace {PROJECT_ID}:{DATASET}.notascredito {OUTPUT_DIR}/notas.jsonl")
    print(f"bq load --source_format=NEWLINE_DELIMITED_JSON --replace {PROJECT_ID}:{DATASET}.lineas_notas {OUTPUT_DIR}/lineas_notas.jsonl")
    print("=" * 60)


if __name__ == '__main__':
    main()
