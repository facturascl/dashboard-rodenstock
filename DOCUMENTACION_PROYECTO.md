# 📊 Dashboard Rodenstock - Documentación Completa

## 📋 Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Instalación desde Cero](#instalación-desde-cero)
4. [Configuración de Automatización](#configuración-de-automatización)
5. [Estructura del Proyecto](#estructura-del-proyecto)
6. [Flujo de Datos](#flujo-de-datos)
7. [Mantenimiento](#mantenimiento)
8. [Solución de Problemas](#solución-de-problemas)

---

## 📄 Resumen Ejecutivo

### ¿Qué es este proyecto?

Sistema automatizado de procesamiento de facturas y notas de crédito de Rodenstock con dashboard interactivo para análisis y visualización.

### Componentes principales:

1. **Procesamiento automatizado** de facturas desde Gmail
2. **Base de datos SQLite** con información histórica
3. **Dashboard interactivo** en Streamlit con múltiples vistas analíticas
4. **Automatización diaria** vía GitHub Actions (20:00 hrs Chile)
5. **Notificaciones por email** del estado de procesamiento

### Stack tecnológico:

- **Backend**: Python 3.11
- **Base de datos**: SQLite
- **Frontend**: Streamlit
- **Gráficos**: Plotly / ECharts
- **Automatización**: GitHub Actions
- **Deploy**: Streamlit Cloud
- **Email**: Gmail API + SMTP

### Métricas del sistema:

- **~15,000 facturas** procesadas históricamente
- **~2,000 notas de crédito** procesadas
- **Procesamiento automático**: Diario a las 20:00 hrs
- **Tiempo de ejecución**: ~1-2 minutos por procesamiento
- **Costo**: $0 (todo en planes gratuitos)

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    GMAIL (Rodenstock)                        │
│  Facturas y Notas de Crédito en PDF (adjuntos en emails)    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Gmail API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              GITHUB REPOSITORY (Código fuente)               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GitHub Actions (Automatización)                     │   │
│  │  - Se ejecuta diariamente a las 20:00 hrs Chile      │   │
│  │  - Trigger: Cron schedule                            │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  scripts/Rodenstock.py                               │   │
│  │  1. Descarga emails nuevos de Gmail                  │   │
│  │  2. Extrae PDFs adjuntos                             │   │
│  │  3. Procesa facturas y notas de crédito              │   │
│  │  4. Clasifica productos por categoría/subcategoría   │   │
│  │  5. Actualiza data/facturas.db                       │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  data/facturas.db (SQLite)                           │   │
│  │  Tablas:                                              │   │
│  │  - facturas                                           │   │
│  │  - lineas_factura                                     │   │
│  │  - notascredito                                       │   │
│  │  - lineas_notas                                       │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Git Commit + Push automático                        │   │
│  │  Actualiza: facturas.db, outputs/, metadata          │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Notificación por Email (Gmail SMTP)                 │   │
│  │  Destinatario: cristian.ibanez@benandfrank.com       │   │
│  │  Contenido: Estado de ejecución (éxito/error)        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                     │
                     │ Auto-deploy on push
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              STREAMLIT CLOUD (Dashboard)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  app.py                                               │   │
│  │  Tabs:                                                │   │
│  │  - 📊 Comparativa Anual                              │   │
│  │  - 🏷️ Desglose Subcategorías                        │   │
│  │  - 📈 Evolución Mensual                              │   │
│  │  - 📋 Notas de Crédito                               │   │
│  └──────────────────────────────────────────────────────┘   │
│  Acceso: https://dashboard-rodenstock.streamlit.app         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Instalación desde Cero

### Prerequisitos

- Python 3.11+
- Cuenta de GitHub
- Cuenta de Gmail con API habilitada
- Cuenta de Streamlit Cloud (gratuita)

### Paso 1: Clonar el Repositorio

```bash
# Clonar repositorio
git clone https://github.com/facturascl/dashboard-rodenstock.git
cd dashboard-rodenstock

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # En Mac/Linux
# o
venv\Scripts\activate  # En Windows

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 2: Configurar Gmail API

#### 2.1 Crear proyecto en Google Cloud Console

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Crear nuevo proyecto: "Rodenstock Dashboard"
3. Habilitar Gmail API:
   - APIs & Services → Library
   - Buscar "Gmail API"
   - Click "Enable"

#### 2.2 Crear credenciales OAuth 2.0

1. APIs & Services → Credentials
2. Create Credentials → OAuth client ID
3. Application type: Desktop app
4. Download JSON → Guardar como `credentials.json`

#### 2.3 Obtener token de acceso

```bash
# Ejecutar script para autenticar
python scripts/get_gmail_token.py

# Esto abrirá el navegador
# Autoriza el acceso
# Se creará token.json automáticamente
```

#### 2.4 Convertir a base64 para GitHub Secrets

```bash
# En Mac/Linux
cat token.json | base64 > token_base64.txt
cat credentials.json | base64 > credentials_base64.txt

# Guardar estos valores para después
```

### Paso 3: Configurar GitHub Secrets

1. Ir al repositorio en GitHub
2. Settings → Secrets and variables → Actions
3. New repository secret para cada uno:

| Secret Name | Valor | Descripción |
|-------------|-------|-------------|
| `GMAIL_TOKEN` | Contenido de `token_base64.txt` | Token de acceso OAuth2 |
| `GMAIL_CONFIG` | Contenido de `credentials_base64.txt` | Credenciales OAuth2 |
| `SMTP_EMAIL` | Tu Gmail (ej: `tu@gmail.com`) | Email para enviar notificaciones |
| `SMTP_PASSWORD` | App Password de Gmail | Contraseña de aplicación |
| `NOTIFICATION_EMAIL` | `cristian.ibanez@benandfrank.com` | Email donde recibir notificaciones |

#### 3.1 Cómo obtener SMTP_PASSWORD (App Password)

1. Ir a [Google Account Security](https://myaccount.google.com/security)
2. Activar verificación en 2 pasos (si no está activa)
3. Ir a [App Passwords](https://myaccount.google.com/apppasswords)
4. Seleccionar "Mail" y "Other (Custom name)" → "GitHub Actions"
5. Click "Generate"
6. Copiar la contraseña de 16 caracteres
7. Guardar en `SMTP_PASSWORD`

### Paso 4: Configurar GitHub Actions Workflow

El workflow ya está creado en `.github/workflows/procesar_facturas.yml`

**Configuración del horario:**

```yaml
schedule:
  - cron: '0 23 * * *'  # 20:00 Chile (UTC-3 verano) = 23:00 UTC
```

**Ajustar para horario de invierno (UTC-4):**

```yaml
schedule:
  - cron: '0 0 * * *'  # 20:00 Chile (UTC-4 invierno) = 00:00 UTC
```

### Paso 5: Deploy en Streamlit Cloud

1. Ir a [Streamlit Cloud](https://share.streamlit.io/)
2. Sign in con GitHub
3. New app → Seleccionar repositorio `dashboard-rodenstock`
4. Settings:
   - Main file path: `app.py`
   - Python version: `3.11`
5. Deploy

**URL del dashboard:**
```
https://dashboard-rodenstock.streamlit.app
```

---

## ⚙️ Configuración de Automatización

### Workflow de GitHub Actions

Archivo: `.github/workflows/procesar_facturas.yml`

#### Estructura del Workflow

```yaml
name: Procesar Facturas Automático

on:
  workflow_dispatch:  # Ejecución manual
  schedule:
    - cron: '0 23 * * *'  # Ejecución automática

permissions:
  contents: write  # Necesario para commit/push

jobs:
  procesar-facturas:
    runs-on: ubuntu-latest
    
    steps:
      - Checkout código
      - Setup Python 3.11
      - Instalar dependencias
      - Configurar credenciales Gmail
      - Ejecutar Rodenstock.py
      - Commit y push de cambios
      - Enviar email de éxito
      - Enviar email de error (si falla)
```

#### Emails de Notificación

**Email de éxito incluye:**
- Fecha de ejecución
- Tipo de ejecución (automática/manual)
- Si hubo cambios en la BD
- Link al workflow

**Email de error incluye:**
- Fecha del error
- Link directo a los logs
- Alerta para revisar

### Ejecución Manual

Para ejecutar manualmente el procesamiento:

1. Ir a GitHub → Actions
2. Seleccionar "Procesar Facturas Automático"
3. Click "Run workflow"
4. Ejecutar

---

## 📁 Estructura del Proyecto

```
dashboard-rodenstock/
├── .github/
│   └── workflows/
│       └── procesar_facturas.yml    # Automatización GitHub Actions
│
├── data/
│   └── facturas.db                  # Base de datos SQLite (7.5MB+)
│
├── scripts/
│   ├── Rodenstock.py               # Script principal de procesamiento
│   ├── clasificador.py             # Lógica de clasificación de productos
│   └── reclasificar.py             # Re-clasificación de datos históricos
│
├── outputs/
│   ├── facturas.jsonl              # Export de facturas
│   ├── lineas_factura.jsonl        # Export de líneas
│   └── ...
│
├── app.py                          # Dashboard Streamlit (versión producción)
├── requirements.txt                # Dependencias Python
├── processed_messages.json         # Control de mensajes procesados
├── last_processed.txt              # Timestamp del último procesamiento
└── README.md                       # Documentación básica
```

### Archivos Clave

#### `scripts/Rodenstock.py`

**Funciones principales:**

```python
def obtener_emails_gmail()
    """Conecta con Gmail API y descarga emails nuevos"""

def extraer_pdfs_de_email(msg)
    """Extrae archivos PDF adjuntos de un email"""

def procesar_factura_pdf(pdf_path)
    """Extrae datos de una factura en PDF usando regex"""

def procesar_nota_credito_pdf(pdf_path)
    """Extrae datos de una nota de crédito en PDF"""

def clasificar_producto(descripcion)
    """Clasifica un producto en categoría y subcategoría"""

def guardar_en_bd(datos)
    """Guarda datos procesados en SQLite"""
```

**Flujo de ejecución:**

1. Conectar con Gmail API
2. Obtener emails nuevos desde `last_processed.txt`
3. Para cada email:
   - Extraer PDFs adjuntos
   - Determinar si es factura o nota de crédito
   - Procesar PDF (extraer campos)
   - Clasificar productos
   - Guardar en BD
4. Actualizar `last_processed.txt`
5. Actualizar `processed_messages.json`
6. Exportar a JSON (outputs/)

#### `data/facturas.db`

**Esquema de base de datos:**

```sql
-- Tabla de facturas
CREATE TABLE facturas (
    numerofactura TEXT PRIMARY KEY,
    fechaemision TEXT,
    rut_cliente TEXT,
    nombre_cliente TEXT,
    subtotal REAL,
    descuento_pesos REAL,
    iva REAL,
    total REAL,
    cantidad_lineas INTEGER
);

-- Tabla de líneas de factura
CREATE TABLE lineas_factura (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numerofactura TEXT NOT NULL,
    linea_numero INTEGER,
    codigo TEXT,
    descripcion TEXT,
    cantidad REAL,
    precio_unitario REAL,
    descuento_porcentaje REAL,
    total_linea REAL,
    clasificacion_categoria TEXT,
    clasificacion_subcategoria TEXT,
    FOREIGN KEY (numerofactura) REFERENCES facturas(numerofactura)
);

-- Tabla de notas de crédito
CREATE TABLE notascredito (
    numeronota TEXT PRIMARY KEY,
    fechaemision TEXT,
    subtotal REAL,
    descuento_pesos REAL,
    valorneto REAL,
    iva REAL,
    total REAL,
    cantidad_lineas INTEGER
);

-- Tabla de líneas de notas
CREATE TABLE lineas_notas (
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
);
```

**⚠️ IMPORTANTE - Cálculo de Totales:**

```sql
-- FACTURAS: subtotal + iva = total con IVA incluido ✅
SELECT SUM(subtotal + iva) FROM facturas;

-- NOTAS DE CRÉDITO: total NO incluye IVA
-- Hay que sumar: total + iva = total con IVA incluido ✅
SELECT SUM(total + iva) FROM notascredito;
```

#### `app.py`

**Estructura del dashboard:**

```python
# Configuración
st.set_page_config(...)

# Conexión a BD
@st.cache_resource
def get_db_connection()

# Funciones de consulta SQL
@st.cache_data(ttl=300)
def get_comparativa_12_meses(ano)
def get_subcategorias_completo_mes(ano, mes)
def get_evolucion_categorias_ano(ano)
def get_evolucion_subcategorias_ano(ano)
def get_notas_credito_12_meses(ano)
def get_notas_credito_categorias_mes(ano, mes)

# Tabs del dashboard
tab1: Comparativa Anual
tab2: Desglose Subcategorías
tab3: Evolución Mensual
tab4: Notas de Crédito
```

---

## 🔄 Flujo de Datos

### Procesamiento Diario (20:00 hrs)

```
1. GitHub Actions Trigger (cron: 0 23 * * *)
   ↓
2. Checkout del código
   ↓
3. Setup Python 3.11 + dependencias
   ↓
4. Configurar credenciales Gmail (desde secrets)
   ↓
5. Ejecutar Rodenstock.py
   │
   ├─→ Conectar Gmail API
   ├─→ Buscar emails nuevos desde last_processed.txt
   ├─→ Para cada email:
   │   ├─→ Descargar PDF
   │   ├─→ Procesar (extraer datos)
   │   ├─→ Clasificar productos
   │   └─→ Guardar en facturas.db
   │
   ├─→ Actualizar last_processed.txt
   ├─→ Actualizar processed_messages.json
   └─→ Exportar JSONs (outputs/)
   ↓
6. Git add + commit + push
   │
   ├─→ data/facturas.db
   ├─→ outputs/*.jsonl
   ├─→ last_processed.txt
   └─→ processed_messages.json
   ↓
7. Enviar email notificación (éxito/error)
   ↓
8. Streamlit Cloud detecta push
   ↓
9. Auto-redeploy dashboard (1-2 minutos)
   ↓
10. Dashboard actualizado disponible
```

### Clasificación de Productos

Ubicación: `scripts/clasificador.py` o dentro de `Rodenstock.py`

**Categorías principales:**
- Monofocales
- Progresivos
- Bifocales
- Ocupacionales
- Tratamientos
- Accesorios
- Montajes
- Otros

**Subcategorías (ejemplos):**
- Hi-index Azul
- Fotocromatico
- Progressiv Pro L
- HSAR++ Blue
- etc.

**Lógica de clasificación:**

```python
def clasificar_producto(descripcion):
    """
    Clasifica un producto basado en palabras clave
    
    Args:
        descripcion (str): Descripción del producto
        
    Returns:
        tuple: (categoria, subcategoria)
    """
    desc_lower = descripcion.lower()
    
    # Diccionario de palabras clave
    if 'progressiv' in desc_lower:
        return ('Progresivos', extraer_subcategoria(descripcion))
    elif 'monofocal' in desc_lower or 'sf' in desc_lower:
        return ('Monofocales', extraer_subcategoria(descripcion))
    # ... más reglas
    else:
        return ('Sin clasificacion', '')
```

---

## 🔧 Mantenimiento

### Tareas Regulares

#### Verificar Ejecución Diaria

**Cada mañana (20:15 hrs aprox):**

1. Revisar email de notificación en `cristian.ibanez@benandfrank.com`
2. Verificar que llegó correctamente
3. Si hay error, revisar logs en GitHub Actions

#### Monitorear Base de Datos

```bash
# Ver tamaño de BD
ls -lh data/facturas.db

# Contar registros
sqlite3 data/facturas.db "SELECT COUNT(*) FROM facturas"
sqlite3 data/facturas.db "SELECT COUNT(*) FROM notascredito"

# Ver últimas facturas procesadas
sqlite3 data/facturas.db "SELECT numerofactura, fechaemision FROM facturas ORDER BY fechaemision DESC LIMIT 10"
```

#### Backup de Base de Datos

**Recomendación:** Backup semanal manual

```bash
# Crear backup local
cp data/facturas.db backups/facturas_backup_$(date +%Y%m%d).db

# Subir a GitHub (opcional)
git add backups/
git commit -m "Backup BD semanal"
git push
```

### Actualización de Categorías

**Cuando se agrega una nueva categoría/subcategoría:**

```bash
# 1. Actualizar clasificador.py con nueva lógica
# 2. Re-clasificar datos históricos

python scripts/reclasificar.py

# 3. Verificar resultados
sqlite3 data/facturas.db "SELECT clasificacion_categoria, COUNT(*) FROM lineas_factura GROUP BY clasificacion_categoria"

# 4. Subir cambios
git add data/facturas.db scripts/clasificador.py
git commit -m "Agregar nueva categoría: [NOMBRE]"
git push
```

### Limpieza de Archivos Temporales

```bash
# Eliminar PDFs temporales (si quedan)
rm -rf temp_pdfs/

# Limpiar cache de Python
find . -type d -name "__pycache__" -exec rm -rf {} +
```

---

## 🐛 Solución de Problemas

### Problema 1: Workflow no se ejecuta automáticamente

**Síntomas:**
- No llega email a las 20:00 hrs
- No hay nuevas ejecuciones en GitHub Actions

**Soluciones:**

1. **Verificar que el workflow está activo:**
   - GitHub → Actions → Verificar que no esté deshabilitado

2. **Verificar horario del cron:**
   ```yaml
   # Verano Chile (UTC-3): 20:00 = 23:00 UTC
   - cron: '0 23 * * *'
   
   # Invierno Chile (UTC-4): 20:00 = 00:00 UTC
   - cron: '0 0 * * *'
   ```

3. **Ejecutar manualmente para probar:**
   - Actions → Run workflow

### Problema 2: Error "Gmail API authentication failed"

**Síntomas:**
- Workflow falla con error de autenticación
- Email dice "ERROR al procesar facturas"

**Soluciones:**

1. **Verificar secrets de GitHub:**
   - Settings → Secrets → Verificar `GMAIL_TOKEN` y `GMAIL_CONFIG`

2. **Regenerar token:**
   ```bash
   python scripts/get_gmail_token.py
   cat token.json | base64
   # Actualizar GMAIL_TOKEN en GitHub Secrets
   ```

3. **Verificar permisos de Gmail API:**
   - Google Cloud Console → Gmail API → Verificar habilitada

### Problema 3: Push rechazado (fetch first)

**Síntomas:**
```
! [rejected] main -> main (fetch first)
```

**Causa:** La automatización hizo commits que no tienes localmente

**Solución:**

```bash
# Hacer pull con merge
git config pull.rebase false
git pull

# Ahora sí push
git push
```

### Problema 4: Datos incorrectos en dashboard

**Síntomas:**
- Totales no coinciden con facturas reales
- Categorías vacías

**Soluciones:**

1. **Verificar cálculo de totales:**
   ```sql
   -- Facturas (correcto)
   SELECT SUM(subtotal + iva) FROM facturas;
   
   -- Notas de crédito (correcto)
   SELECT SUM(total + iva) FROM notascredito;
   ```

2. **Re-clasificar productos:**
   ```bash
   python scripts/reclasificar.py
   ```

3. **Limpiar cache de Streamlit:**
   - En el dashboard: Click "🔄 Actualizar Datos"

### Problema 5: Streamlit no se actualiza

**Síntomas:**
- Dashboard muestra datos viejos después de push
- Cambios en código no se reflejan

**Soluciones:**

1. **Forzar redeploy:**
   - Streamlit Cloud → Reboot app

2. **Verificar que el push llegó:**
   - GitHub → Commits → Verificar último commit

3. **Limpiar cache:**
   ```python
   # En app.py, botón "Actualizar Datos" ejecuta:
   st.cache_resource.clear()
   st.cache_data.clear()
   st.rerun()
   ```

### Problema 6: Email de notificación no llega

**Síntomas:**
- Workflow ejecuta correctamente
- No llega email de notificación

**Soluciones:**

1. **Verificar SMTP secrets:**
   - `SMTP_EMAIL`: Email correcto
   - `SMTP_PASSWORD`: App Password válido
   - `NOTIFICATION_EMAIL`: Email destino correcto

2. **Revisar spam:**
   - Buscar en carpeta de spam

3. **Probar manualmente:**
   ```bash
   # Ejecutar workflow manual
   # Revisar logs del paso "Enviar email"
   ```

### Problema 7: Base de datos corrupta

**Síntomas:**
```
Error: database disk image is malformed
```

**Soluciones:**

1. **Restaurar desde backup:**
   ```bash
   cp backups/facturas_backup_FECHA.db data/facturas.db
   ```

2. **Si no hay backup, exportar e importar:**
   ```bash
   # Exportar lo que se pueda
   sqlite3 data/facturas.db ".dump" > dump.sql
   
   # Crear nueva BD
   rm data/facturas.db
   sqlite3 data/facturas.db < dump.sql
   ```

---

## 📊 Métricas y Monitoreo

### KPIs del Sistema

| Métrica | Valor Esperado | Dónde Verificar |
|---------|---------------|-----------------|
| Tiempo de ejecución | 1-2 minutos | GitHub Actions logs |
| Facturas procesadas/día | 5-50 | Email de notificación |
| Tamaño BD | Crece ~1MB/mes | `ls -lh data/facturas.db` |
| Tasa de error | <5% | Emails de error |
| Uptime dashboard | >99% | Streamlit Cloud status |

### Logs Importantes

**GitHub Actions:**
```
GitHub → Actions → Workflow run → View logs
```

**Streamlit Cloud:**
```
Streamlit Cloud → App → Logs
```

**Base de datos:**
```bash
# Ver últimas 10 facturas
sqlite3 data/facturas.db "SELECT * FROM facturas ORDER BY fechaemision DESC LIMIT 10"

# Ver estadísticas por categoría
sqlite3 data/facturas.db "SELECT clasificacion_categoria, COUNT(*) FROM lineas_factura GROUP BY clasificacion_categoria"
```

---

## 🔐 Seguridad

### Secrets de GitHub

**NUNCA commits en código:**
- ❌ Credenciales Gmail
- ❌ Tokens de API
- ❌ Contraseñas SMTP
- ❌ Emails personales

**Usar siempre GitHub Secrets:**
- ✅ `${{ secrets.GMAIL_TOKEN }}`
- ✅ `${{ secrets.SMTP_PASSWORD }}`

### Permisos Mínimos

**Gmail API:**
- Solo permisos de lectura necesarios
- Scope: `gmail.readonly` o `gmail.modify`

**GitHub Actions:**
- `permissions: contents: write` (solo lo necesario)

### Backup y Recuperación

**Estrategia 3-2-1:**
1. **3 copias:** Local + GitHub + Backup manual
2. **2 medios:** Git repo + Archive
3. **1 offsite:** GitHub (cloud)

---

## 📚 Recursos Adicionales

### Documentación Externa

- [Streamlit Docs](https://docs.streamlit.io/)
- [Gmail API Guide](https://developers.google.com/gmail/api)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

### Contacto

**Desarrollador:** Cristián Ibañez  
**Email:** cristian.ibanez@benandfrank.com  
**Empresa:** Ben & Frank  
**Cliente:** Rodenstock Chile

---

## 📝 Changelog

### v2.0 - Febrero 2026
- ✅ Migrado de 2 scripts separados a 1 script unificado (Rodenstock.py)
- ✅ Agregado procesamiento de notas de crédito
- ✅ Implementada automatización con GitHub Actions
- ✅ Agregadas notificaciones por email
- ✅ Corregido cálculo de totales (total + iva)
- ✅ Agregada columna de números de nota en desglose
- ✅ Eliminado tab Newton vs Newton Plus
- ✅ Agregado tab de Notas de Crédito

### v1.0 - Enero 2026
- ✅ Versión inicial con procesamiento manual
- ✅ Dashboard básico en Streamlit
- ✅ Clasificación de productos por categoría

---

## ✅ Checklist de Implementación

### Setup Inicial

- [ ] Repositorio clonado
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas
- [ ] Gmail API configurada
- [ ] `credentials.json` obtenido
- [ ] `token.json` generado
- [ ] GitHub Secrets configurados (5 secrets)
- [ ] Workflow de GitHub Actions probado
- [ ] Streamlit Cloud conectado
- [ ] Primera ejecución manual exitosa

### Verificación Post-Deploy

- [ ] Dashboard accesible en Streamlit Cloud
- [ ] Workflow se ejecuta a las 20:00 hrs
- [ ] Email de notificación llega correctamente
- [ ] Base de datos se actualiza diariamente
- [ ] Gráficos muestran datos correctos
- [ ] No hay errores en logs

### Mantenimiento Configurado

- [ ] Backup semanal programado
- [ ] Monitoreo de emails activado
- [ ] Documentación revisada
- [ ] Equipo capacitado en uso

---

**Última actualización:** Febrero 2026  
**Versión:** 2.0  
**Estado:** ✅ En Producción
