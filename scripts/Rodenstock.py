#!/usr/bin/env python3
"""
Rodenstock.py - Script unificado de procesamiento de facturas
Versión 3.0 - Automatización completa (Local + GitHub Actions)

Combina:
- Procesamiento de correos Gmail (Procesar.py)
- Carga a base de datos SQLite (Cargar.py)
- Limpieza de archivos temporales

Autor: Sistema automatizado Rodenstock
Fecha: 2025-02-10
"""

import os
import sys
import json
import base64
import shutil
from pathlib import Path
from datetime import datetime

# ============ DETECCIÓN DE ENTORNO ============
IS_GITHUB_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'
IS_CI = os.getenv('CI') == 'true' or IS_GITHUB_ACTIONS

# ============ CONFIGURACIÓN DE RUTAS ============
# Detectar si estamos en scripts/ o en raíz del proyecto
SCRIPT_DIR = Path(__file__).parent.resolve()
SCRIPT_NAME = Path(__file__).name

# Si estamos en scripts/, subir un nivel para llegar a la raíz
if SCRIPT_DIR.name == "scripts":
    BASE_DIR = SCRIPT_DIR.parent
    print(f"📂 Detectado: Ejecutando desde scripts/ - Base: {BASE_DIR}")
else:
    BASE_DIR = SCRIPT_DIR
    print(f"📂 Detectado: Ejecutando desde raíz - Base: {BASE_DIR}")

# Directorios del proyecto
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
PDF_SAVE_DIR = BASE_DIR / "pdf_attachments"

# Archivos de estado (en raíz del proyecto)
LAST_PROCESSED_FILE = BASE_DIR / "last_processed.txt"
PROCESSED_MSGS_FILE = BASE_DIR / "processed_messages.json"

# Archivos de configuración (en raíz del proyecto)
TOKEN_FILE = BASE_DIR / "token.json"
CONFIG_DIR = BASE_DIR / ".streamlit"
CONFIG_FILE = CONFIG_DIR / "config.toml"
CREDENTIALS_FILE = BASE_DIR / "config" / "credentials.json"

# Archivos de datos
LIBRERIA_FILE = SCRIPTS_DIR / "libreria.xlsx"
DATABASE_FILE = DATA_DIR / "facturas.db"


# ============ SETUP DE CREDENCIALES (GitHub Actions) ============
def setup_credentials():
    """
    Configura credenciales desde GitHub Secrets si estamos en CI.
    En local, usa los archivos existentes.
    """
    if not IS_CI:
        print("🔧 Modo LOCAL - usando archivos de credenciales existentes")
        
        # Validar que existan los archivos necesarios
        required_files = {
            'token.json': TOKEN_FILE,
            'config.toml': CONFIG_FILE,
            'credentials.json': CREDENTIALS_FILE,
        }
        
        missing = [name for name, path in required_files.items() if not path.exists()]
        if missing:
            print(f"⚠️  ADVERTENCIA: Archivos faltantes: {', '.join(missing)}")
            print("   El script puede fallar si estos archivos son necesarios.")
        
        return
    
    print("🔧 Modo GITHUB ACTIONS - configurando credenciales desde secrets...")
    
    # Crear directorios necesarios
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Decodificar y crear token.json
    token_b64 = os.getenv('GMAIL_TOKEN')
    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode('utf-8')
            TOKEN_FILE.write_text(token_json)
            print("  ✅ token.json creado desde secret")
        except Exception as e:
            print(f"  ❌ Error creando token.json: {e}")
            sys.exit(1)
    else:
        print("  ⚠️  Secret GMAIL_TOKEN no encontrado")
    
    # 2. Decodificar y crear config.toml
    config_b64 = os.getenv('GMAIL_CONFIG')
    if config_b64:
        try:
            config_toml = base64.b64decode(config_b64).decode('utf-8')
            CONFIG_FILE.write_text(config_toml)
            print("  ✅ config.toml creado desde secret")
        except Exception as e:
            print(f"  ⚠️  Error creando config.toml: {e}")
    
    # 3. Decodificar y crear credentials.json (si existe)
    creds_b64 = os.getenv('GOOGLE_CREDENTIALS')
    if creds_b64:
        try:
            creds_json = base64.b64decode(creds_b64).decode('utf-8')
            CREDENTIALS_FILE.write_text(creds_json)
            print("  ✅ credentials.json creado desde secret")
        except Exception as e:
            print(f"  ⚠️  Error creando credentials.json: {e}")


# ============ IMPORTACIÓN DE MÓDULOS ORIGINALES ============
def import_procesar_logic():
    """
    Importa la lógica de Procesar.py sin ejecutar su main()
    """
    try:
        # Agregar el directorio scripts al path si no está
        scripts_path = str(SCRIPTS_DIR)
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        
        # Intentar importar Procesar
        import Procesar
        return Procesar
    except ImportError as e:
        print(f"❌ Error importando Procesar.py: {e}")
        print("   Asegúrate de que Procesar.py esté en la carpeta 'scripts/'")
        return None


def import_cargar_logic():
    """
    Importa la lógica de Cargar.py sin ejecutar su main()
    """
    try:
        scripts_path = str(SCRIPTS_DIR)
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        
        import Cargar
        return Cargar
    except ImportError as e:
        print(f"❌ Error importando Cargar.py: {e}")
        print("   Asegúrate de que Cargar.py esté en la carpeta 'scripts/'")
        return None


# ============ FUNCIONES PRINCIPALES ============
def procesar_correos():
    """
    Ejecuta la lógica de Procesar.py:
    - Autentica con Gmail
    - Descarga correos nuevos
    - Extrae datos de PDFs
    - Clasifica con libreria.xlsx
    - Genera JSONLs en outputs/
    - Actualiza archivos de estado
    """
    print("\n" + "=" * 80)
    print("📧 FASE 1: PROCESAMIENTO DE CORREOS GMAIL")
    print("=" * 80)
    
    Procesar = import_procesar_logic()
    if not Procesar:
        raise ImportError("No se pudo importar Procesar.py")
    
    # Ejecutar la función main() de Procesar
    try:
        Procesar.main()
        print("✅ Procesamiento de correos completado")
    except Exception as e:
        print(f"❌ Error en procesamiento de correos: {e}")
        raise


def cargar_a_base():
    """
    Ejecuta la lógica de Cargar.py:
    - Lee JSONLs de outputs/
    - Carga datos a facturas.db (modo incremental)
    - Actualiza tablas: facturas, lineas_factura, notascredito, lineas_notas
    """
    print("\n" + "=" * 80)
    print("💾 FASE 2: CARGA A BASE DE DATOS")
    print("=" * 80)
    
    Cargar = import_cargar_logic()
    if not Cargar:
        raise ImportError("No se pudo importar Cargar.py")
    
    # Ejecutar las funciones de Cargar.py
    try:
        # Crear tablas si no existen
        Cargar.crear_tablas()
        
        # Cargar facturas
        facturas_jsonl = OUTPUT_DIR / "facturas.jsonl"
        lineas_facturas_jsonl = OUTPUT_DIR / "lineas_factura.jsonl"
        
        if facturas_jsonl.exists() and lineas_facturas_jsonl.exists():
            Cargar.cargar_facturas(str(facturas_jsonl), str(lineas_facturas_jsonl))
        else:
            print("⚠️  No se encontraron archivos de facturas para cargar")
        
        # Cargar notas de crédito
        notas_jsonl = OUTPUT_DIR / "notas.jsonl"
        lineas_notas_jsonl = OUTPUT_DIR / "lineas_notas.jsonl"
        
        if notas_jsonl.exists() and lineas_notas_jsonl.exists():
            Cargar.cargar_notas(str(notas_jsonl), str(lineas_notas_jsonl))
        else:
            print("⚠️  No se encontraron archivos de notas para cargar")
        
        # Mostrar estadísticas
        Cargar.mostrar_estadisticas()
        
        print("✅ Carga a base de datos completada")
    except Exception as e:
        print(f"❌ Error en carga a base de datos: {e}")
        raise


def limpiar_temporales():
    """
    Limpia archivos temporales:
    - PDFs en pdf_attachments/
    - (Opcional) JSONLs en outputs/ - Por ahora NO los borramos por seguridad
    """
    print("\n" + "=" * 80)
    print("🧹 FASE 3: LIMPIEZA DE ARCHIVOS TEMPORALES")
    print("=" * 80)
    
    archivos_borrados = 0
    
    # Limpiar PDFs
    if PDF_SAVE_DIR.exists():
        try:
            pdf_count = len(list(PDF_SAVE_DIR.glob("*.pdf")))
            shutil.rmtree(PDF_SAVE_DIR)
            archivos_borrados += pdf_count
            print(f"  ✅ {pdf_count} PDFs eliminados de {PDF_SAVE_DIR}")
        except Exception as e:
            print(f"  ⚠️  Error eliminando PDFs: {e}")
    else:
        print(f"  ℹ️  No hay PDFs para eliminar")
    
    # NO borrar JSONLs por seguridad (pueden ser útiles para debugging)
    # Si quieres borrarlos en el futuro, descomenta estas líneas:
    # if OUTPUT_DIR.exists():
    #     for jsonl in OUTPUT_DIR.glob("*.jsonl"):
    #         jsonl.unlink()
    #         archivos_borrados += 1
    
    if archivos_borrados > 0:
        print(f"✅ {archivos_borrados} archivo(s) temporal(es) eliminado(s)")
    else:
        print("ℹ️  No hay archivos temporales para eliminar")


def verificar_prerequisitos():
    """
    Verifica que existan los archivos/directorios necesarios antes de empezar.
    """
    print("\n🔍 Verificando prerequisitos...")
    
    errores = []
    warnings = []
    
    # Archivos críticos
    if not LIBRERIA_FILE.exists():
        errores.append(f"❌ Faltante: {LIBRERIA_FILE}")
    else:
        print(f"  ✅ libreria.xlsx encontrado")
    
    # Archivos de estado (pueden no existir la primera vez)
    if not LAST_PROCESSED_FILE.exists():
        warnings.append(f"⚠️  {LAST_PROCESSED_FILE} no existe (se creará automáticamente)")
    else:
        print(f"  ✅ last_processed.txt encontrado")
    
    if not PROCESSED_MSGS_FILE.exists():
        warnings.append(f"⚠️  {PROCESSED_MSGS_FILE} no existe (se creará automáticamente)")
    else:
        print(f"  ✅ processed_messages.json encontrado")
    
    # Credenciales (solo advertencias en modo local)
    if not IS_CI:
        if not TOKEN_FILE.exists():
            errores.append(f"❌ Faltante: {TOKEN_FILE}")
        else:
            print(f"  ✅ token.json encontrado")
    
    # Base de datos (puede no existir la primera vez)
    if not DATABASE_FILE.exists():
        warnings.append(f"⚠️  {DATABASE_FILE} no existe (se creará automáticamente)")
    else:
        db_size = DATABASE_FILE.stat().st_size / (1024 * 1024)  # MB
        print(f"  ✅ facturas.db encontrado ({db_size:.2f} MB)")
    
    # Mostrar warnings
    for w in warnings:
        print(f"  {w}")
    
    # Si hay errores críticos, abortar
    if errores:
        print("\n❌ ERRORES CRÍTICOS:")
        for e in errores:
            print(f"  {e}")
        print("\nNo se puede continuar. Por favor, corrige los errores.")
        sys.exit(1)
    
    print("✅ Todos los prerequisitos verificados")


def mostrar_resumen():
    """
    Muestra un resumen del estado final del sistema.
    """
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    
    # Estado de la base de datos
    if DATABASE_FILE.exists():
        db_size = DATABASE_FILE.stat().st_size / (1024 * 1024)
        print(f"📁 Base de datos: {db_size:.2f} MB")
    
    # Estado de los archivos de estado
    if LAST_PROCESSED_FILE.exists():
        last_date = LAST_PROCESSED_FILE.read_text().strip()
        print(f"📅 Última fecha procesada: {last_date}")
    
    if PROCESSED_MSGS_FILE.exists():
        try:
            msgs = json.loads(PROCESSED_MSGS_FILE.read_text())
            print(f"📧 Mensajes procesados totales: {len(msgs)}")
        except:
            pass
    
    # Archivos de salida
    jsonl_files = list(OUTPUT_DIR.glob("*.jsonl"))
    if jsonl_files:
        print(f"📄 Archivos JSONL generados: {len(jsonl_files)}")
    
    print("=" * 80)


# ============ FUNCIÓN PRINCIPAL ============
def main():
    """
    Función principal que orquesta todo el proceso.
    """
    inicio = datetime.now()
    
    print("=" * 80)
    print("🚀 RODENSTOCK - SISTEMA AUTOMÁTICO DE PROCESAMIENTO DE FACTURAS")
    print("   Versión 3.0 - Unificado (Procesar + Cargar + Limpieza)")
    print("=" * 80)
    print(f"📅 Fecha/Hora: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🖥️  Entorno: {'GitHub Actions' if IS_GITHUB_ACTIONS else 'Local'}")
    print(f"📂 Script ubicado en: {SCRIPT_DIR}")
    print(f"📂 Directorio base del proyecto: {BASE_DIR}")
    print("=" * 80)
    
    try:
        # 0. Setup de credenciales (si es necesario)
        setup_credentials()
        
        # 1. Verificar prerequisitos
        verificar_prerequisitos()
        
        # 2. Procesar correos de Gmail
        procesar_correos()
        
        # 3. Cargar a base de datos
        cargar_a_base()
        
        # 4. Limpiar archivos temporales
        limpiar_temporales()
        
        # 5. Mostrar resumen
        mostrar_resumen()
        
        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()
        
        print("\n" + "=" * 80)
        print("✅ PROCESO COMPLETADO EXITOSAMENTE")
        print(f"⏱️  Tiempo total: {duracion:.2f} segundos")
        print("=" * 80)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        return 130
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ ERROR FATAL")
        print("=" * 80)
        print(f"Error: {e}")
        
        # Mostrar traceback completo solo en modo debug
        if os.getenv('DEBUG') == 'true':
            import traceback
            print("\n📋 Traceback completo:")
            traceback.print_exc()
        
        return 1


# ============ PUNTO DE ENTRADA ============
if __name__ == '__main__':
    sys.exit(main())