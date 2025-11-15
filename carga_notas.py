from google.cloud import bigquery
import json

client = bigquery.Client(project="rodenstock-471300")
table_id = "rodenstock-471300.facturacion.notascredito"

# Cargar JSONL
with open("outputs/notas.jsonl", "r") as f:
    rows = [json.loads(line) for line in f]

# Insertar
errors = client.insert_rows_json(table_id, rows)
if errors:
    print(f"Errores: {errors}")
else:
    print(f"✅ {len(rows)} filas cargadas exitosamente")
