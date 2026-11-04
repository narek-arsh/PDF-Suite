import pdfplumber
import os
import re
import shlex
from pathlib import Path
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter

DOWNLOADS = Path.home() / "Downloads"
DOWNLOADS.mkdir(exist_ok=True)

def procesar_pdf(ruta):
    if not os.path.exists(ruta):
        print(f"\n[!] Error: No se encuentra el archivo en: {ruta}")
        return

    if not ruta.lower().endswith('.pdf'):
        print(f"\n[!] Ignorando archivo porque no es PDF: {ruta}")
        return

    datos_paginas = []
    print(f"\n--- Analizando: {os.path.basename(ruta)} ---")
    
    try:
        with pdfplumber.open(ruta) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text()
                
                if not texto:
                    continue

                # Extraer DNI / DOC.ID
                match_dni = re.search(r'DNI ó DOC\.ID:\s*(\S+)', texto)
                dni = match_dni.group(1) if match_dni else "Z_DESCONOCIDO"
                
                # Extraer Fecha de Origen
                match_fecha = re.search(r'Origen:.*?(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', texto)
                if match_fecha:
                    fecha_str = match_fecha.group(1)
                    fecha = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
                else:
                    fecha = datetime.max

                datos_paginas.append({
                    'num_original': i,
                    'dni': dni,
                    'fecha': fecha
                })
                
    except Exception as e:
        print(f"Error al leer {os.path.basename(ruta)}: {e}")
        return

    # Ordenar por fecha y luego por DNI
    datos_paginas.sort(key=lambda x: (x['fecha'], x['dni']))

    # Crear el nuevo PDF
    try:
        reader = PdfReader(ruta)
        writer = PdfWriter()

        for p in datos_paginas:
            writer.add_page(reader.pages[p['num_original']])

        stem = Path(ruta).stem
        ruta_salida = str(DOWNLOADS / f"{stem}_ordenado.pdf")
        with open(ruta_salida, "wb") as f:
            writer.write(f)
        
        print(f"[+] Ordenado y guardado con éxito: {os.path.basename(ruta_salida)}")

    except Exception as e:
        print(f"Error al crear el nuevo PDF para {os.path.basename(ruta)}: {e}")

def main():
    entrada = input("Arrastra los archivos PDF aquí y pulsa ENTER, o teclea 'I' para importar desde ventana:\n").strip()
    
    rutas_procesar = []

    if entrada.lower() == 'i':
        # Inicializar y ocultar la ventana principal de Tkinter
        root = tk.Tk()
        root.withdraw()
        # Forzar que la ventana aparezca en primer plano
        root.attributes('-topmost', True)
        
        # Abrir el selector de archivos (permite seleccionar varios)
        archivos_seleccionados = filedialog.askopenfilenames(
            title="Selecciona los billetes PDF",
            filetypes=[("Archivos PDF", "*.pdf")]
        )
        rutas_procesar = list(archivos_seleccionados)
    else:
        # Reparar el problema de Windows al arrastrar varios archivos juntos
        rutas_separadas = re.sub(r'(?i)(\.pdf\"?)\s*(\"?)([a-zA-Z]:[\\/])', r'\1 \2\3', entrada)
        rutas_extraidas = shlex.split(rutas_separadas, posix=False)
        
        for ruta in rutas_extraidas:
            rutas_procesar.append(ruta.replace('"', '').replace("'", ""))

    if not rutas_procesar:
        print("No has seleccionado ningún archivo.")
        return

    for ruta_limpia in rutas_procesar:
        procesar_pdf(ruta_limpia)

if __name__ == "__main__":
    main()
    input("\nProceso terminado. Presiona ENTER para salir...")