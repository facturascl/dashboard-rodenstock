import subprocess
import json

jsonl_file = "outputs/notas.jsonl"
table_id = "rodenstock-471300:facturacion.notascredito"

# Comando bq load (NO es streaming, es bulk - SÍ funciona en free tier)
cmd = [
    'bq', 'load',
    '--source_format=NEWLINE_DELIMITED_JSON',
    table_id,
    jsonl_file
]

print(f"📤 Cargando: {table_id}")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    print(f"✅ Carga completada exitosamente")
else:
    print(f"❌ Error:")
    print(result.stderr)
