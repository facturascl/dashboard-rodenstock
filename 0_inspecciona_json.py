
import json

# Lee primeras 3 líneas de facturas
print("="*60)
print("INSPECCIONANDO: outputs/facturas.jsonl")
print("="*60)

with open("outputs/facturas.jsonl", 'r', encoding='utf-8') as f:
    for i, linea in enumerate(f):
        if i >= 3:  # Solo primeras 3
            break
        try:
            registro = json.loads(linea.strip())
            print(f"\nFACTURA #{i+1}:")
            print(f"Campos disponibles: {list(registro.keys())}")
            for campo, valor in registro.items():
                if isinstance(valor, list):
                    print(f"  {campo}: [lista con {len(valor)} items]")
                else:
                    print(f"  {campo}: {valor}")
        except:
            pass

print("\n" + "="*60)
print("INSPECCIONANDO: outputs/notas.jsonl")
print("="*60)

with open("outputs/notas.jsonl", 'r', encoding='utf-8') as f:
    for i, linea in enumerate(f):
        if i >= 3:  # Solo primeras 3
            break
        try:
            registro = json.loads(linea.strip())
            print(f"\nNOTA #{i+1}:")
            print(f"Campos disponibles: {list(registro.keys())}")
            for campo, valor in registro.items():
                if isinstance(valor, list):
                    print(f"  {campo}: [lista con {len(valor)} items]")
                else:
                    print(f"  {campo}: {valor}")
        except:
            pass

print("\n" + "="*60)
print("⚠️  COPIA ESTA SALIDA EN EL CHAT")
print("="*60)
