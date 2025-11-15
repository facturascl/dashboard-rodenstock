
import json
from pathlib import Path

# PASO 1: Leer facturas y extraer líneas
print("="*70)
print("EXTRAYENDO LÍNEAS DE FACTURAS...")
print("="*70)

lineas_factura_list = []
contador = 0

with open("outputs/facturas.jsonl", 'r', encoding='utf-8') as f:
    with open("outputs/facturas_temp.jsonl", 'w', encoding='utf-8') as f_out:
        for linea in f:
            try:
                factura = json.loads(linea.strip())
                lineas = factura.get('lineas', [])
                
                # Guardar líneas en lista separada
                for idx, linea_item in enumerate(lineas, 1):
                    linea_item['numerofactura'] = factura['numerofactura']
                    linea_item['linea_numero'] = idx
                    lineas_factura_list.append(linea_item)
                
                # Guardar factura sin líneas
                factura_sin_lineas = {k: v for k, v in factura.items() if k != 'lineas'}
                f_out.write(json.dumps(factura_sin_lineas, ensure_ascii=False) + "\n")
                
                contador += 1
                if contador % 1000 == 0:
                    print(f"  Procesadas {contador} facturas, {len(lineas_factura_list)} líneas")
            except Exception as e:
                print(f"  ❌ Error en factura: {str(e)}")

print(f"✅ Total: {contador} facturas, {len(lineas_factura_list)} líneas de factura")

# PASO 2: Guardar líneas de factura
print("\nGuardando líneas de factura...")
with open("outputs/lineas_factura.jsonl", 'w', encoding='utf-8') as f:
    for linea in lineas_factura_list:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
print(f"✅ Guardadas {len(lineas_factura_list)} líneas en outputs/lineas_factura.jsonl")

# PASO 3: Reemplazar facturas.jsonl con facturas sin líneas
Path("outputs/facturas.jsonl").unlink()
Path("outputs/facturas_temp.jsonl").rename("outputs/facturas.jsonl")
print("✅ Actualizado outputs/facturas.jsonl (sin líneas)")

# PASO 4: Hacer lo mismo con notas
print("\n" + "="*70)
print("EXTRAYENDO LÍNEAS DE NOTAS...")
print("="*70)

lineas_notas_list = []
contador = 0

with open("outputs/notas.jsonl", 'r', encoding='utf-8') as f:
    with open("outputs/notas_temp.jsonl", 'w', encoding='utf-8') as f_out:
        for linea in f:
            try:
                nota = json.loads(linea.strip())
                lineas = nota.get('lineas', [])
                
                # Guardar líneas en lista separada
                for idx, linea_item in enumerate(lineas, 1):
                    linea_item['numeronota'] = nota['numeronota']
                    linea_item['linea_numero'] = idx
                    lineas_notas_list.append(linea_item)
                
                # Guardar nota sin líneas
                nota_sin_lineas = {k: v for k, v in nota.items() if k != 'lineas'}
                f_out.write(json.dumps(nota_sin_lineas, ensure_ascii=False) + "\n")
                
                contador += 1
                if contador % 100 == 0:
                    print(f"  Procesadas {contador} notas, {len(lineas_notas_list)} líneas")
            except Exception as e:
                print(f"  ❌ Error en nota: {str(e)}")

print(f"✅ Total: {contador} notas, {len(lineas_notas_list)} líneas de nota")

# PASO 5: Guardar líneas de notas
print("\nGuardando líneas de notas...")
with open("outputs/lineas_notas.jsonl", 'w', encoding='utf-8') as f:
    for linea in lineas_notas_list:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
print(f"✅ Guardadas {len(lineas_notas_list)} líneas en outputs/lineas_notas.jsonl")

# PASO 6: Reemplazar notas.jsonl con notas sin líneas
Path("outputs/notas.jsonl").unlink()
Path("outputs/notas_temp.jsonl").rename("outputs/notas.jsonl")
print("✅ Actualizado outputs/notas.jsonl (sin líneas)")

# RESUMEN
print("\n" + "="*70)
print("✅ EXTRACCIÓN COMPLETADA")
print("="*70)
print(f"\n📁 Archivos generados en outputs/:")
print(f"  1. facturas.jsonl ({contador} encabezados)")
print(f"  2. lineas_factura.jsonl ({len(lineas_factura_list)} líneas)")
print(f"  3. notas.jsonl ({contador} encabezados)")
print(f"  4. lineas_notas.jsonl ({len(lineas_notas_list)} líneas)")
print(f"\n➡️  Ahora ejecuta: python 1_carga_DEFINITIVA.py")
print("="*70 + "\n")