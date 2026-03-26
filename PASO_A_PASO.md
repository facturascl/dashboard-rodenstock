# 🔄 Actualización de Categorías - Paso a Paso

Si en el futuro añades una **nueva categoría** o subcategoría en tu archivo `libreria.xlsx` y necesitas que la historia pasada (lo que ya descargaste y muestra el Dashboard) refleje ese cambio, debes seguir estos 3 sencillos pasos:

### Paso 1: Modificar tu Librería
1. Abre tu archivo `scripts/libreria.xlsx`.
2. Añade tu nueva regla asegurándote de escribir exactamente el texto que se debe buscar en la factura (ya sea por *Producto*, *Tratamiento*, etc).
3. **Guarda** el archivo Excel y ciérralo.

### Paso 2: Ejecutar la Recategorización Histórica
1. Abre tu terminal (PowerShell) y asegúrate de estar en la carpeta de tu proyecto (`C:\Users\Superusuario\Documents\dashboard-rodenstock`).
2. Ejecuta el archivo de recategorización (usando el python de tu entorno virtual) con este comando:
   ```powershell
   .\venv\Scripts\python.exe scripts\Recategorizar_DB.py
   ```
   *(Aparecerá un mensaje diciendo cuántas líneas de facturas y notas de crédito se actualizaron directamente en la Base de Datos Histórica).*

### Paso 3: Subir los Cambios a la Nube (GitHub)
Para que el Dashboard de Streamlit en línea asimile estos cambios, debes enviarle la base de datos y la librería recién actualizada.

**Opción A: Desde GitHub Desktop (Recomendada)**
1. Abre tu aplicación **GitHub Desktop**.
2. Escribe de título "Añadiendo nueva categoría".
3. Haz clic en **Commit to main** abajo a la izquierda.
4. Arriba, presiona **Push origin**.

**Opción B: Desde la Terminal (Comandos)**
Si prefieres hacerlo por código, pega y ejecuta línea por línea:
```powershell
& "C:\Program Files\Git\cmd\git.exe" add data\facturas.db scripts\libreria.xlsx PASO_A_PASO.md
& "C:\Program Files\Git\cmd\git.exe" commit -m "Añadiendo nuevas categorias a la historia"
& "C:\Program Files\Git\cmd\git.exe" push origin main
```

¡Eso es todo! Después de hacer el *Push*, entra a tu Dashboard en internet, espera alrededor de un minuto para que recargue y verás que tus datos históricos han adquirido la nueva categoría.
