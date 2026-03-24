#!/usr/bin/env python3
import sys
import os
import json
from collections import defaultdict

# Añadir el directorio raíz al PYTHONPATH para importar Procesar
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.Procesar import cargar_libreria, clasificar_lineas_factura

def recategorizar_archivo(archivo_entrada):
    if not os.path.exists(archivo_entrada):
        print(f"❌ Archivo no encontrado: {archivo_entrada}")
        return

    print(f"\n🔄 Recategorizando {archivo_entrada}...")
    reglas = cargar_libreria()

    # Cargar todas las líneas
    lineas_originales = []
    with open(archivo_entrada, 'r', encoding='utf-8') as f:
        for text in f:
            if text.strip():
                lineas_originales.append(json.loads(text.strip()))

    # Determinar qué clave usar según el archivo
    is_nota = 'nota' in archivo_entrada.lower()
    id_key = 'numeronota' if is_nota else 'numerofactura'
    
    # Agrupar por documento (factura o nota de crédito) preservando el orden relativo
    documentos = defaultdict(list)
    for linea in lineas_originales:
        doc_id = linea.get(id_key)
        if doc_id:
            documentos[doc_id].append(linea)
            
    lineas_recategorizadas = 0
    
    # Evaluar cada factura/nota en su totalidad para asignarle categoría
    for doc_id, doc_lineas in documentos.items():
        categoria, subcategoria = clasificar_lineas_factura(doc_lineas, reglas)
        
        for linea in doc_lineas:
            linea['clasificacion_categoria'] = categoria
            linea['clasificacion_subcategoria'] = subcategoria
            lineas_recategorizadas += 1

    # Sobrescribir conservando el orden original para no alterar lógicas posteriores
    with open(archivo_entrada, 'w', encoding='utf-8') as f:
        # Repasamos las lineas originales y grabamos la copia mutada en el diccionario
        # (al ser diccionarios por referencia, doc_lineas mutó los de lineas_originales)
        for linea in lineas_originales:
            f.write(json.dumps(linea, ensure_ascii=False) + '\n')

    print(f"✅ Finalizada la actualización de {lineas_recategorizadas} líneas en {archivo_entrada}.")

if __name__ == "__main__":
    print("="*60)
    print("🚀 INICIANDO RECATEGORIZACIÓN DE LÍNEAS HISTÓRICAS...")
    print("="*60)
    
    # Usar rutas relativas asumiendo que el script corre desde la raíz
    recategorizar_archivo("outputs/lineas_factura.jsonl")
    recategorizar_archivo("outputs/lineas_notas.jsonl")
    
    print("\n✅ RECATEGORIZACIÓN COMPLETADA EXITOSAMENTE.")
    print("Por favor ejecuta scripts/Cargar.py para sincronizar a la Base de Datos SQLite.")
