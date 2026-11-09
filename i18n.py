# -*- coding: utf-8 -*-
"""Traducción de los textos que ve el usuario (no del código). El español es el idioma
base: las claves de TR son el texto español tal cual aparece en la interfaz."""
import json

import theme   # reutiliza la misma ruta de configuración que la paleta de colores

LANGS = ["es", "en", "pt"]
LANG_NAMES = {"es": "Español", "en": "English", "pt": "Português"}


def load_lang() -> str:
    try:
        data = json.loads(theme.CONFIG_PATH.read_text(encoding="utf-8"))
        lang = data.get("lang")
        if lang in LANGS:
            return lang
    except Exception:
        pass
    return "es"


def save_lang(lang: str) -> None:
    if lang not in LANGS:
        return
    try:
        theme.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if theme.CONFIG_PATH.is_file():
            try:
                data = json.loads(theme.CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["lang"] = lang
        theme.CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def next_lang(current: str) -> str:
    return LANGS[(LANGS.index(current) + 1) % len(LANGS)]


TR = {
    "en": {
        # Buscador y barra lateral
        "Buscar una función… (p. ej. «firmar», «formulario», «numerar»)":
            "Search for a function… (e.g. “sign”, “form”, “numbering”)",
        "Sin resultados.": "No results.",
        "Cambiar a modo claro": "Switch to light mode",
        "Cambiar a modo oscuro": "Switch to dark mode",
        "Abrir provecto.app": "Open provecto.app",

        # Grupos del menú
        "Combinar y dividir": "Merge & split",
        "Comparar": "Compare",
        "Editar": "Edit",
        "Formato": "Format",
        "Optimizar": "Optimize",
        "Texto y conversión": "Text & conversion",
        "Más": "More",

        # Elementos del menú
        "Unir": "Merge",
        "Dividir": "Split",
        "Organizar páginas": "Organize pages",
        "Comparar PDFs": "Compare PDFs",
        "Numerar páginas": "Page numbering",
        "Analizar PDF": "Analyze PDF",
        "Verificar firmas": "Verify signatures",
        "Editor": "Editor",
        "Metadatos": "Metadata",
        "Ajuste de imagen": "Image adjustment",
        "Tamaño y márgenes": "Size & margins",
        "Varias por hoja": "Multiple per page",
        "Comprimir": "Compress",
        "Proteger": "Protect",
        "Marca de agua": "Watermark",
        "Invertir colores": "Invert colors",
        "Aplanar y reparar": "Flatten & repair",
        "OCR": "OCR",
        "Convertir a PDF": "Convert to PDF",
        "Convertir desde PDF": "Convert from PDF",
        "Workflows": "Workflows",

        # Funciones dentro del Editor (solo se encuentran buscando)
        "Firmar": "Sign",
        "Formulario": "Form",
        "Sello": "Stamp",
        "Resaltar texto": "Highlight text",
        "Dibujar": "Draw",
        "Enlace": "Link",
        "Añadir texto": "Add text",
        "Censurar": "Redact",
        "Reemplazar texto": "Replace text",
        "Copiar texto o tabla": "Copy text or table",

        # Campo de URL y subida
        "Pega un enlace a un PDF y pulsa Enter (o arrastra archivos aquí)":
            "Paste a link to a PDF and press Enter (or drag files here)",
        "Añadir archivos": "Add files",
        "Subir PDFs o fotos desde el ordenador": "Upload PDFs or photos from this computer",
        "Descargando PDF…": "Downloading PDF…",
        "No se pudo descargar el PDF": "Couldn't download the PDF",
        "Elegir PDFs o fotos": "Choose PDFs or photos",
        "PDF y fotos ({exts})": "PDF and photos ({exts})",
        "Fotos ({photos})": "Photos ({photos})",
        "Todos los archivos (*.*)": "All files (*.*)",

        # Barra de pasos / workflow
        "Guardar como workflow": "Save as workflow",
        "Guardar como nuevo": "Save as new",
        "Añadir al workflow": "Add to workflow",
        "Descartar pasos": "Discard steps",
        "Borra la lista de pasos anotados para empezar otro workflow desde cero. No deshace nada en tus archivos.":
            "Clears the recorded steps to start another workflow from scratch. It doesn't undo anything in your files.",
        "Pasos aplicados:  ": "Steps applied:  ",
        "guardado  ·  pasos nuevos:  ": "saved  ·  new steps:  ",
        "✓ Guardado como «{name}»  ·  ": "✓ Saved as “{name}”  ·  ",
        "  Añadir a «{name}»": "  Add to “{name}”",

        # Barra de acciones y pie
        "Limpiar todo": "Clear all",
        "Guardar como…": "Save as…",
        "  Unir los {n} archivos": "  Merge {n} files",
        "archivo": "file",
        "archivos": "files",
        "página": "page",
        "páginas": "pages",
        "arrastra las tarjetas para ordenarlas": "drag the cards to reorder them",
        "Arrastra archivos o pega un enlace para empezar": "Drag files or paste a link to get started",

        # Selector de idioma
        "Idioma": "Language",

        # --- ui/pick.py, ui/metadata.py, ui/compare.py ---
        "Elegir archivos…": "Choose files…",
        "Esta herramienta trabaja sobre un PDF. Súbelo aquí y se abrirá en cuanto esté cargado.":
            "This tool works on one PDF. Upload it here and it will open as soon as it's loaded.",
        "Hacen falta al menos {minimum} PDFs. Tienes {have}: añade {falta} más y se abrirá en cuanto estén cargados.":
            "You need at least {minimum} PDFs. You have {have}: add {falta} more and it will open as soon as they're loaded.",
        "PDF y fotos": "PDF and photos",
        "Todos los archivos": "All files",
        "Metadata – Ver / editar / borrar": "Metadata – View / edit / delete",
        "Archivo:": "File:",
        "Título": "Title",
        "Autor": "Author",
        "Asunto": "Subject",
        "Palabras clave": "Keywords",
        "Creador (programa de origen)": "Creator (source program)",
        "Productor (motor que generó el PDF)": "Producer (engine that generated the PDF)",
        "Creado: —": "Created: —",
        "Modificado: —": "Modified: —",
        "Guardar cambios": "Save changes",
        "Borrar todos los metadatos": "Delete all metadata",
        "Creado: {d}": "Created: {d}",
        "Modificado: {d}": "Modified: {d}",
        "✓ {ok_label} en {n} archivo{s}.": "✓ {ok_label} in {n} file{s}.",
        "No se pudo en ningún archivo.": "Couldn't do it on any file.",
        " ({n} con error)": " ({n} with an error)",
        "Selecciona un archivo": "Select a file",
        "Guardando metadatos…": "Saving metadata…",
        "Metadatos guardados": "Metadata saved",
        "Eliminando metadatos…": "Deleting metadata…",
        "Metadatos eliminados": "Metadata deleted",
        "Comparar PDFs": "Compare PDFs",
        "Elige dos PDFs ya subidos (o añade uno nuevo desde el disco) y pulsa «Comparar». Se compara el texto y el aspecto de cada página; no se modifica ninguno de los dos archivos.":
            "Choose two already-uploaded PDFs (or add a new one from disk) and click “Compare”. The text and the look of each page are compared; neither file is modified.",
        "Archivo A": "File A",
        "Archivo B": "File B",
        "Contraseña:": "Password:",
        "solo si la tiene": "only if it has one",
        "Comparar": "Compare",
        "Diferencias": "Differences",
        "El texto de la página aparece aquí cuando hay diferencias.": "The page text appears here when there are differences.",
        "Elegir desde el disco…": "Choose from disk…",
        "Elige un PDF": "Choose a PDF",
        "Elige los dos archivos a comparar.": "Choose the two files to compare.",
        "Elige dos archivos distintos.": "Choose two different files.",
        "Comparando…": "Comparing…",
        "✓ Son idénticos: {n} páginas, sin ninguna diferencia.": "✓ They are identical: {n} pages, no differences.",
        "{n} distinta(s)": "{n} different",
        "{n} añadida(s)": "{n} added",
        "{n} quitada(s)": "{n} removed",
        "A tiene {n_a} páginas, B tiene {n_b}": "A has {n_a} pages, B has {n_b}",
        "Página {n} — {label}": "Page {n} — {label}",
        "Comparación hecha.": "Comparison done.",
        "Sin diferencias": "No differences",
        "No aplica": "Not applicable",
        "(sin texto)": "(no text)",
        "No existe en este archivo": "Doesn't exist in this file",
        "No se puede mostrar": "Can't be displayed",
        "Igual": "Same",
        "Diferente": "Different",
        "Solo en B (añadida)": "Only in B (added)",
        "Solo en A (quitada)": "Only in A (removed)",

        # --- ui/ajuste.py, ui/workflows_ui.py ---
        "Página {n} / {total}": "Page {n} / {total}",
        "Brillo": "Brightness",
        "Contraste": "Contrast",
        "Saturación": "Saturation",
        "Blanco y negro": "Black and white",
        "Aplicar a esta página": "Apply to this page",
        "Aplicar a todas las páginas de este PDF": "Apply to all pages of this PDF",
        "Cancelar": "Cancel",
        "No se pudo generar la vista previa": "Could not generate the preview",
        "Error": "Error",
        "No se pudo aplicar el ajuste.": "Could not apply the adjustment.",
        "Ajuste de imagen — varios archivos": "Image adjustment — multiple files",
        "Navega por las páginas de todos los archivos como en un merge. El ajuste se aplicará a todas las páginas de todos los archivos cargados.":
            "Browse through the pages of all the files as in a merge. The adjustment will be applied to all pages of all the loaded files.",
        "Aplicar a todos los archivos": "Apply to all files",
        "{name} — página {pi}/{total}   ·   ({cur}/{total_all} en total)": "{name} — page {pi}/{total}   ·   ({cur}/{total_all} total)",
        "Nombre del workflow:": "Workflow name:",
        "p.ej. Enviar a cliente": "e.g. Send to client",
        "Estos pasos se aplicarán, en orden, a cada archivo que subas («Unir archivos» junta todos en uno). Quita los que no quieras.":
            "These steps will be applied, in order, to each file you upload (\"Merge files\" joins them all into one). Remove the ones you don't want.",
        "Subir": "Move up",
        "Bajar": "Move down",
        "Quitar paso": "Remove step",
        "Preguntar al ejecutar": "Ask when running",
        "Marca lo que cambia en cada archivo: se te pedirá al lanzar el workflow.": "Check what changes in each file: you'll be asked for it when you run the workflow.",
        "Este paso no tiene valores de texto que preguntar.": "This step has no text values to ask for.",
        "{label}  (valor guardado: «{value}»)": "{label}  (saved value: \"{value}\")",
        "Guardar": "Save",
        "Falta el nombre": "Missing name",
        "Ponle un nombre al workflow.": "Give the workflow a name.",
        "Sin pasos": "No steps",
        "El workflow no tiene ningún paso.": "The workflow has no steps.",
        "Editar workflow": "Edit workflow",
        "Ejecutar: {name}": "Run: {name}",
        "Rellena los valores de esta vez:": "Fill in the values for this run:",
        "{label}  ·  paso {n}: {step_label}": "{label}  ·  step {n}: {step_label}",
        "Ejecutar": "Run",
        "Falta un valor": "Missing value",
        "«{label}» no puede estar vacío.": "\"{label}\" cannot be empty.",
        "Secuencias de pasos guardadas. Elige una, sube los archivos y se ejecuta sola. Para crear una: aplica tus herramientas como siempre y pulsa «Guardar como workflow» en la pantalla principal.":
            "Saved sequences of steps. Pick one, upload the files and it runs itself. To create one: apply your tools as usual and press \"Save as workflow\" on the main screen.",
        "Todavía no hay ningún workflow guardado.": "There are no saved workflows yet.",
        "Editar": "Edit",
        "Borrar": "Delete",
        "Elige un workflow": "Choose a workflow",
        "✓ Workflow «{name}» actualizado": "✓ Workflow \"{name}\" updated",
        "Borrar workflow": "Delete workflow",
        "¿Borrar «{name}»?": "Delete \"{name}\"?",

        # --- ui/organize.py, ui/split.py ---
        "Organize – Gestionar páginas": "Organize – Manage pages",
        "Arrastra las páginas para reordenarlas · clic derecho o R/Supr para rotar/eliminar": "Drag pages to reorder them · right-click or R/Del to rotate/delete",
        "Rotar 90°": "Rotate 90°",
        "Eliminar página": "Delete page",
        "Organize y guardar en Descargas": "Organize and save to Downloads",
        "No quedan páginas": "No pages left",
        "¿Dónde guardar?": "Where to save?",
        "¿Cómo quieres guardar los archivos generados?": "How do you want to save the generated files?",
        "En una carpeta": "In a folder",
        "Como archivo .zip": "As a .zip file",
        "Split – Dividir PDF": "Split – Split PDF",
        "Cada página en un archivo": "Each page in a file",
        "Elegir páginas con el ratón": "Pick pages with the mouse",
        "Dividir por página de referencia": "Split by reference page",
        "Prefijo + número de página": "Prefix + page number",
        "Lista de nombres (una por línea)": "List of names (one per line)",
        "Prefijo, p.ej. Pagina_": "Prefix, e.g. Page_",
        "Casa\nSilla\nMesa\n…\n(una línea = el nombre de cada página, en orden)": "House\nChair\nTable\n…\n(one line = the name of each page, in order)",
        "Dividir en páginas sueltas": "Split into separate pages",
        "Clic para seleccionar · Ctrl/Shift+clic para varias páginas": "Click to select · Ctrl/Shift+click for multiple pages",
        "Guardar selección": "Save selection",
        "Dividir en 2 (seleccionadas / resto)": "Split into 2 (selected / rest)",
        "Página de referencia:": "Reference page:",
        "El primer archivo tendrá las páginas anteriores a la de referencia; el segundo, desde la página de referencia hasta el final.":
            "The first file will have the pages before the reference page; the second, from the reference page to the end.",
        "Pág. {n}": "Page {n}",
        "No hay páginas que guardar": "No pages to save",
        "Guardado: {name}": "Saved: {name}",
        "Elegir carpeta destino": "Choose destination folder",
        "{n} archivo(s) guardados en {folder}/": "{n} file(s) saved to {folder}/",
        "Guardar como ZIP": "Save as ZIP",
        "ZIP guardado: {name}": "ZIP saved: {name}",
        "El PDF no tiene páginas": "The PDF has no pages",
        "Faltan nombres": "Missing names",
        "El PDF tiene {total} páginas pero diste menos nombres. A las páginas sin nombre se les asignará 'Pagina_N'.":
            "The PDF has {total} pages but you gave fewer names. Unnamed pages will be assigned 'Page_N'.",
        "Selecciona al menos una página": "Select at least one page",
        "No quedan páginas fuera de la selección": "No pages left outside the selection",
        "Página de referencia fuera de rango": "Reference page out of range",

        # --- ui/ocr.py ---
        "Arrastra cada punto a su esquina del papel: mientras arrastras aparece una lupa con una cruz «+». Para afinar, elige un punto y mueve con las flechas del teclado (1 píxel; con Mayús, 5).": "Drag each point to its corner of the paper: a magnifier with a «+» cross appears while you drag. To fine-tune, pick a point and move it with the arrow keys (1 pixel; with Shift, 5).",
        "Detectar de nuevo": "Detect again",
        "Toda la página": "Whole page",
        "Aplicar": "Apply",
        "Esquinas detectadas: comprueba que cada punto está en su sitio.": "Corners detected: check that each point is in place.",
        "No distingo el papel del fondo: colócalas a mano.": "I can't tell the paper from the background: place them by hand.",
        "Enderezar foto": "Straighten photo",
        "Toda la imagen": "Whole image",
        "Arrastra cada punto a su esquina del papel.": "Drag each point to its corner of the paper.",
        "Formato": "Format",
        "Automático": "Automatic",
        "Carta": "Letter",
        "Como se ve": "As shown",
        "Aclarar fondo y luz": "Lighten background and light",
        "Ver resultado": "View result",
        "Una hoja arrugada o curvada no se puede aplanar así: usa una foto con el papel plano y bien iluminado.": "A wrinkled or curved sheet can't be flattened this way: use a photo with the paper flat and well lit.",
        "Corregir página": "Fix page",
        "He encontrado las esquinas del papel. Comprueba que los cuatro puntos están en su sitio y arrástralos si hace falta.": "I found the corners of the paper. Check that the four points are in place and drag them if needed.",
        "No distingo bien el papel del fondo: arrastra los cuatro puntos a las esquinas de la hoja.": "I can't clearly tell the paper from the background: drag the four points to the corners of the sheet.",
        "Línea nueva": "New line",
        "Borrar esta línea": "Delete this line",
        "Añadir una línea nueva debajo": "Add a new line below",
        "Corregido por su posición: el OCR había leído «{val}»": "Fixed by its position: the OCR had read «{val}»",
        "(línea añadida: no hay original)": "(added line: no original)",
        "Revisar el texto reconocido": "Review the recognized text",
        "Cada línea tiene el texto reconocido arriba (cada palabra sobre la suya) y la línea original debajo. Corrige las palabras en su sitio: Tab pasa a la siguiente y la palabra original se marca en amarillo. Las palabras que cambias se tiñen de amarillo; las cantidades con el separador corregido por su posición, de azul; las dudosas llevan borde naranja. Con ✕ borras una línea y con ＋ añades otra debajo.": "Each line shows the recognized text on top (each word above its own) and the original line below. Fix the words in place: Tab moves to the next one and the original word is highlighted in yellow. Words you change turn yellow; amounts with the separator fixed by position turn blue; uncertain ones get an orange border. Use ✕ to delete a line and ＋ to add another below.",
        "Anterior": "Previous",
        "Siguiente": "Next",
        "Restaurar el texto leído": "Restore the recognized text",
        "PDF con la imagen y el texto detrás (se puede buscar y copiar) — recomendado": "PDF with the image and searchable text behind it (can be searched and copied) — recommended",
        "PDF nuevo redibujado solo con el texto (sin la imagen)": "New PDF redrawn with just the text (without the image)",
        "Crea un segundo PDF donde el texto se dibuja a la vista en su posición, con las rayas de las tablas. Sirve para tener el documento limpio y editable. No conserva dibujos, sellos ni fotos.": "Creates a second PDF where the text is drawn visibly in place, with table lines. Useful for a clean, editable document. It doesn't keep drawings, stamps, or photos.",
        "Página {n} de {total} (hoja {sheet} del PDF)": "Page {n} of {total} (sheet {sheet} of the PDF)",
        "línea": "line",
        "líneas": "lines",
        "cambiada": "changed",
        "cambiadas": "changed",
        "Sin cambios": "No changes",
        "Marca al menos una de las dos opciones de guardado.": "Check at least one of the two save options.",
        "Detectadas": "Detected",
        "Manual": "Manual",
        "Sin detectar": "Not detected",
        "Ya tiene texto · se omite": "Already has text · skipped",
        "Página {n}": "Page {n}",
        "Pulsa para ajustar las esquinas en grande": "Click to adjust the corners in large view",
        "Ajustar en grande…": "Adjust in large view…",
        "Detectar esta página": "Detect this page",
        "Detectar todas": "Detect all",
        "Ver resultado enderezado": "View straightened result",
        "Este archivo no se puede previsualizar (tiene contraseña o no hay archivo).": "This file can't be previewed (it's password-protected or there's no file).",
        "Cargando páginas…": "Loading pages…",
        "Página {n} de {total}": "Page {n} of {total}",
        "{n} detectadas": "{n} detected",
        "{n} manual": "{n} manual",
        "{n} sin detectar (solo se endereza el texto)": "{n} not detected (only the text is straightened)",
        "{n} ya tienen texto (se omiten)": "{n} already have text (skipped)",
        "Esquinas detectadas automáticamente. Si algo no encaja, pulsa «Ajustar en grande…».": "Corners detected automatically. If something doesn't fit, click «Adjust in large view…».",
        "Esquinas marcadas por ti. «Detectar esta página» vuelve a la detección automática.": "Corners marked by you. «Detect this page» goes back to automatic detection.",
        "No distingo el papel del fondo. Pulsa «Ajustar en grande…» para marcar las esquinas, o déjala así (solo se endereza el texto).": "I can't tell the paper from the background. Click «Adjust in large view…» to mark the corners, or leave it as is (only the text gets straightened).",
        "Esta página ya tiene texto y se deja como está (desmarca «Solo las páginas sin texto» para tratarla).": "This page already has text and is left as is (uncheck «Only pages without text» to process it).",
        "Esquinas · página {n}": "Corners · page {n}",

        # --- ui/common.py ---
        "¿A qué archivos?": "Which files?",
        "Tienes {n} archivos subidos. ¿Aplicar esto a todos o solo al elegido ahora{current}?":
            "You have {n} files uploaded. Apply this to all of them, or only to the one selected now{current}?",
        "A todos": "To all",
        "Solo a este": "Only this one",
        "Ha ocurrido un error inesperado: {e}": "An unexpected error occurred: {e}",

        # --- ui/size_nup.py ---
        "Vista previa · tamaño": "Preview · size",
        "Cambiar tamaño de página": "Change page size",
        "Ancho:": "Width:",
        "Alto:": "Height:",
        "Escalar contenido para llenar la hoja": "Scale content to fill the sheet",
        "Mantener tamaño original y centrar": "Keep original size and center",
        "Aplicar tamaño": "Apply size",
        "Cambiar márgenes": "Change margins",
        "Valores positivos añaden margen en blanco en ese borde; valores negativos recortan ese borde de la página.":
            "Positive values add blank margin on that edge; negative values crop that edge of the page.",
        "Arriba": "Top",
        "Abajo": "Bottom",
        "Izquierda": "Left",
        "Derecha": "Right",
        "Aplicar márgenes": "Apply margins",
        "Vista previa · márgenes": "Preview · margins",
        "No se pudo: {label}.": "Couldn't {label}.",
        "Cambiando tamaño…": "Changing size…",
        "Tamaño aplicado": "Size applied",
        "Aplicando márgenes…": "Applying margins…",
        "Márgenes aplicados": "Margins applied",
        "N-Up – Varias páginas por hoja": "N-Up – Multiple pages per sheet",
        "Hoja": "Sheet",
        "Vista previa · hoja de salida": "Preview · output sheet",
        "Columnas:": "Columns:",
        "Filas:": "Rows:",
        "Tamaño de la hoja de salida:": "Output sheet size:",
        "Orientación de la hoja:": "Sheet orientation:",
        "Vertical": "Portrait",
        "Horizontal": "Landscape",
        "Automática: elige la orientación en la que las páginas salen más grandes":
            "Automatic: picks whichever orientation makes the pages come out largest",
        "Girar páginas para aprovechar mejor la hoja": "Rotate pages to make better use of the sheet",
        "Si una página llena mejor su celda girada 90°, se gira (útil con documentos de páginas mezcladas)":
            "If a page fits its cell better rotated 90°, it gets rotated (useful for documents with mixed-orientation pages)",
        "Espacio entre páginas:": "Spacing between pages:",
        "Aplicar N-Up": "Apply N-Up",
        "= {n} página(s) por hoja": "= {n} page(s) per sheet",
        "Auto: ahora {v:.1f} mm (3 mm, reducido hasta 0 si la cuadrícula necesita el sitio)":
            "Auto: currently {v:.1f} mm (3 mm, reduced down to 0 if the grid needs the room)",
        "Se unirán {n_files} archivos en el orden de la lista ({pages} páginas) y después se aplicará N-Up":
            "{n_files} files will be merged in list order ({pages} pages), then N-Up will be applied",
        "Vista previa · hoja {orient}": "Preview · {orient} sheet",
        "horizontal": "landscape",
        "vertical": "portrait",
        "✓ N-Up aplicado: {name}": "✓ N-Up applied: {name}",
        "No se pudo aplicar N-Up": "Couldn't apply N-Up",

        # --- ui/widgets.py ---
        "{pages} pág.": "{pages} pg.",
        "Arrastra PDFs o fotos aquí (también texto, HTML, Word…)": "Drag PDFs or photos here (also text, HTML, Word…)",
        "Abrir": "Open",
        "Quitar archivo": "Remove file",
        "Volver": "Back",

        # --- ui/editor_view.py ---
        "Insertar una página aquí": "Insert a page here",
        "Borrar esta página": "Delete this page",
        "Acercar": "Zoom in",
        "Alejar": "Zoom out",
        "Girar a la izquierda": "Rotate left",
        "Girar a la derecha": "Rotate right",
        "Insertar página aquí": "Insert page here",
        "Archivo adjuntado (el clip). Clic en el clip para guardar una copia o quitarlo.": "File attached (the clip). Click the clip to save a copy or remove it.",
        "Elige antes el archivo: Notas → Adjuntar archivo…": "First choose the file: Notes → Attach file…",
        "Campo": "Field",
        "Este campo es de solo lectura.": "This field is read-only.",
        "Para firmar, usa el botón Firma.": "To sign, use the Signature button.",
        "Este botón no se puede rellenar.": "This button can't be filled in.",
        "Arrastra un recuadro más grande para crear el campo.": "Drag a larger box to create the field.",
        "Haz clic en un campo para rellenarlo, o arrastra un recuadro para crear uno nuevo.": "Click a field to fill it in, or drag a box to create a new one.",
        "Arrastra sobre el texto o el área, o haz clic sobre una imagen o dibujo, para convertirlo en enlace.": "Drag over the text or area, or click an image or drawing, to turn it into a link.",
        "Imagen del PDF seleccionada: pulsa Supr para quitarla de esta página.": "PDF image selected: press Delete to remove it from this page.",
        "Guardar como firma…": "Save as signature…",
        "Eliminar este dibujo": "Delete this drawing",
        "Editar este texto": "Edit this text",
        "Reemplazar «{w}»…": "Replace «{w}»…",
        "Rellenar / cambiar": "Fill in / change",
        "Eliminar campo «{n}»": "Delete field «{n}»",
        "Cambiar de icono…": "Change icon…",
        "Girar 15° a la izquierda": "Rotate 15° left",
        "Girar 15° a la derecha": "Rotate 15° right",
        "Duplicar": "Duplicate",
        "Eliminar": "Delete",
        "No hay ninguna marca ahí.": "There's no markup there.",
        "Arrastra sobre el texto que quieras marcar.": "Drag over the text you want to mark.",
        "Vista general: has acercado la página {n} para poder editarla.": "Overview: you zoomed into page {n} so you can edit it.",
        "Cuentagotas: haz clic en cualquier punto de la página para tomar su color.": "Eyedropper: click anywhere on the page to pick its color.",
        "Esta página está girada: para editarla, vuelve a girarla a su posición original (botones de giro sobre la página).": "This page is rotated: to edit it, rotate it back to its original position (rotate buttons above the page).",
        "Fuente": "Font",
        "Tamaño del texto": "Text size",
        "Negrita": "Bold",
        "Cursiva": "Italic",
        "Color del texto": "Text color",
        "Borrar este texto": "Delete this text",
        "Añadir un elemento debajo (con su etiqueta o viñeta, y renumera los siguientes)": "Add an item below (with its label or bullet, renumbering the following ones)",
        "Buscar fuente…": "Search fonts…",
        "Color original": "Original color",
        "Otro color…": "Other color…",
        "Novo elemento": "New item",
        "No se pudo añadir el elemento.": "Couldn't add the item.",
        "Este texto no cabe en la página y se creará una nueva. Marca la cabecera y el pie para no tocarlos y decide cómo se repiten. Si cancelas, el cambio se descarta.": "This text doesn't fit on the page and a new one will be created. Mark the header and footer so they're left untouched and decide how they repeat. If you cancel, the change is discarded.",
        "El texto que no cabía pasó a la página {pages}.": "The text that didn't fit moved to page {pages}.",

        # --- ui/editor_parts.py ---
        "Insertar página": "Insert page",
        "¿Qué quieres insertar aquí?": "What do you want to insert here?",
        "Una página en blanco": "A blank page",
        "Páginas de otro documento (PDF)…": "Pages from another document (PDF)…",
        "Se ha detectado cabecera, pie o fondo de página en este documento.": "A header, footer or page background was detected in this document.",
        "Este documento tiene la cabecera y el pie que configuraste.": "This document has the header and footer you set up.",
        "Mantener cabecera, pie y fondo": "Keep header, footer and background",
        "Hoja totalmente en blanco": "A completely blank sheet",
        "Configurar cabecera y pie…": "Set up header and footer…",
        "Insertar": "Insert",
        "Al pulsar «Insertar» elegirás el PDF cuyas páginas se añaden aquí.": "When you click \"Insert\" you'll choose the PDF whose pages are added here.",
        "Sin vista previa": "No preview",
        "Elige el PDF a insertar": "Choose the PDF to insert",
        "PDF (*.pdf);;Todos los archivos (*.*)": "PDF (*.pdf);;All files (*.*)",
        "Cambiar icono": "Change icon",
        "Icono de «clic aquí»": "\"Click here\" icon",
        "Pulsa un icono para cambiarlo al momento; puedes probar varios.": "Click an icon to change it instantly; you can try several.",
        "El enlace está sobre una imagen. ¿Quieres insertar alguno de estos iconos para indicar a quien lea el PDF que puede hacer clic? Después podrás moverlo y girarlo un poco para que no tape nada.": "The link is on top of an image. Do you want to insert one of these icons to show readers of the PDF that they can click? Afterwards you can move it and rotate it slightly so it doesn't cover anything.",
        "Tu imagen": "Your image",
        "Usar mi propia imagen…": "Use my own image…",
        "Importa un PNG, JPG o SVG para usarlo como icono (queda guardado para otros documentos)": "Import a PNG, JPG or SVG to use as an icon (it stays saved for other documents)",
        "Cerrar": "Close",
        "No, gracias": "No, thanks",
        "Elige las imágenes de tus iconos": "Choose the images for your icons",
        "Imágenes e ilustraciones (*.png *.jpg *.jpeg *.svg *.ai *.eps *.pdf *.webp *.gif *.bmp);;Todos (*.*)": "Images and illustrations (*.png *.jpg *.jpeg *.svg *.ai *.eps *.pdf *.webp *.gif *.bmp);;All files (*.*)",
        "Icono": "Icon",
        "Cabecera y pie de página": "Header and footer",
        "Marca con un clic los textos que son cabecera o pie: no se moverán al repartir el texto entre páginas y se podrán repetir en las páginas nuevas.": "Click to mark the texts that are header or footer: they won't move when text is spread across pages and can be repeated on new pages.",
        "Cada clic marca el texto como:": "Each click marks the text as:",
        "Cabecera (azul)": "Header (blue)",
        "Pie de página (verde)": "Footer (green)",
        "Repetir la cabecera en las páginas nuevas": "Repeat the header on new pages",
        "Repetir el pie en las páginas nuevas": "Repeat the footer on new pages",
        "¿Son iguales en todas las páginas?": "Are they the same on every page?",
        "Iguales en todas": "Same on all pages",
        "Distintos en pares e impares": "Different on even and odd pages",
        "La página nueva copia la de dos antes, o la anterior si no hay.": "The new page copies the one two pages back, or the previous one if there isn't one.",
        "Seguir la numeración de página": "Follow the page numbering",
        "Continuar": "Continue",
        "Número de página detectado: {nums}. En la página nueva subirá solo.": "Page number detected: {nums}. It will go up by itself on the new page.",
        "No se ha detectado ningún número de página en lo marcado.": "No page number was detected in what's marked.",
        "Copiar texto": "Copy text",
        "Texto de la zona": "Text in the area",
        "Unir las líneas de cada párrafo (quita los saltos de línea del escaneo o de la maquetación)": "Join the lines of each paragraph (removes line breaks from scanning or layout)",
        "Tablas a Excel…": "Tables to Excel…",
        "Copiar": "Copy",
        "párrafo": "paragraph",
        "tabla": "table",
        "fila": "row",
        "suelta": "loose",
        "Se ha reconocido: ": "Recognized: ",
        "nada de texto": "no text",
        "Las celdas de tablas y filas van separadas por tabuladores: al pegarlo en Excel o en una tabla de Word cada una cae en su columna.": "Table and row cells are separated by tabs: when pasted into Excel or a Word table, each one falls into its own column.",
        "Guardar tablas": "Save tables",
        "Excel (*.xlsx)": "Excel (*.xlsx)",
        "✓ Guardado: {name} ({n} hoja{s}).": "✓ Saved: {name} ({n} sheet{s}).",
        "No se pudo guardar: {e}": "Could not save: {e}",
        "✓ Copiado al portapapeles.": "✓ Copied to clipboard.",
        "Editar nota": "Edit note",
        "Nueva nota": "New note",
        "Autor: {author}": "Author: {author}",
        "Eliminar nota": "Delete note",
        "Texto (una línea)": "Text (one line)",
        "Texto (varias líneas)": "Text (multiple lines)",
        "Casilla": "Checkbox",
        "Lista desplegable": "Dropdown list",
        "Lista de selección": "Selection list",
        "Botones de opción (elegir uno)": "Radio buttons (choose one)",
        "Nuevo campo": "New field",
        "Nuevo campo de formulario": "New form field",
        "Tipo de campo": "Field type",
        "Nombre del campo (así se identifica al exportar los datos)": "Field name (this identifies it when exporting the data)",
        "Opciones (una por línea)": "Options (one per line)",
        "Opción 1\nOpción 2\nOpción 3": "Option 1\nOption 2\nOption 3",
        "Valor inicial (opcional)": "Initial value (optional)",
        "Crear campo": "Create field",
        "Opciones (una por línea, mínimo 2)": "Options (one per line, minimum 2)",
        "Azul de hipervínculo": "Hyperlink blue",
        "Azul oscuro": "Dark blue",
        "Morado (visitado)": "Purple (visited)",
        "Rojo": "Red",
        "Verde": "Green",
        "Naranja": "Orange",
        "Negro": "Black",
        "Editar enlace": "Edit link",
        "Nuevo enlace": "New link",
        "Dirección web (o correo electrónico)": "Web address (or email)",
        "https://ejemplo.com  ·  nombre@correo.com": "https://example.com  ·  name@email.com",
        "Una página de este documento": "A page in this document",
        "Página ": "Page ",
        " de {n}": " of {n}",
        "Poner el texto en azul y subrayarlo, como un hipervínculo": "Make the text blue and underlined, like a hyperlink",
        "Color del texto y del subrayado": "Color of the text and underline",
        "Este enlace ocupa {n} zonas (líneas): se editan y se quitan juntas.": "This link covers {n} zones (lines): they are edited and removed together.",
        "Quitar enlace": "Remove link",
        "Guardar enlace": "Save link",
        "Color": "Color",
        "Color del enlace": "Link color",
        "Esa dirección no es válida. Usa una web (https://…), un correo o un teléfono; por seguridad no se admiten otros tipos de enlace.": "That address isn't valid. Use a website (https://…), an email or a phone number; for security, other kinds of links aren't allowed.",
        "Sin relleno": "No fill",
        "Elige un color": "Choose a color",
        "Cuentagotas (tomar de la página)": "Eyedropper (pick from the page)",
        "Opacidad total": "Total opacity",
        "Solo el trazo (opcional)": "Stroke only (optional)",
        "Solo el relleno (opcional)": "Fill only (optional)",
        "Color del borde": "Border color",
        "Color de relleno": "Fill color",
        "Grosor": "Thickness",
        "Opacidad del relleno": "Fill opacity",
        "Forma de la punta de la flecha": "Arrowhead shape",
        "Duplicar (Ctrl+D)": "Duplicate (Ctrl+D)",
        "Borrar (Supr)": "Delete (Del)",
        "Fino": "Thin",
        "Normal": "Normal",
        "Grueso": "Thick",
        "Muy grueso": "Very thick",
        "Borde": "Border",
        "Relleno": "Fill",
        "Opacidad {p} %": "Opacity {p}%",
        "Opacidad {p1}/{p2} %": "Opacity {p1}/{p2}%",
        "Opacidad total; dentro puedes dar otra solo al trazo o solo al relleno": "Total opacity; inside you can set a different one for just the stroke or just the fill",
        "Punta": "Tip",

        # --- ui/edit_page.py ---
        "Fuentes que faltan": "Missing fonts",
        "Este PDF usa fuentes que no están en tu ordenador. Sin ellas, al editar se usa una "
        "parecida y el texto puede verse algo distinto. Las que publica Google Fonts "
        "(licencia libre) se pueden descargar aquí. Las de Microsoft, Adobe o de pago no.":
            "This PDF uses fonts that aren't on your computer. Without them, editing uses a "
            "similar one and the text may look slightly different. Fonts published by Google Fonts "
            "(free license) can be downloaded here. Microsoft, Adobe or paid fonts can't.",
        "«{family}» — comprobando en Google Fonts…": "“{family}” — checking Google Fonts…",
        "Buscar la seleccionada en Google Fonts": "Search the selected one on Google Fonts",
        "Instalar solo en este programa (recomendado: no cambia nada en Windows)":
            "Install only in this program (recommended: doesn't change anything in Windows)",
        "Instalar también en Windows (para todos tus programas; solo para tu "
        "usuario, sin permisos de administrador)":
            "Also install in Windows (for all your programs; only for your "
            "user, no administrator rights needed)",
        "Descargar e instalar": "Download and install",
        "«{family}» — disponible en Google Fonts ({n} estilos)": "“{family}” — available on Google Fonts ({n} styles)",
        "«{family}» — de Microsoft; «{sub}» (Google Fonts) tiene las mismas medidas":
            "“{family}” — from Microsoft; “{sub}” (Google Fonts) has the same metrics",
        "«{family}» no se puede descargar (es de Microsoft). «{sub}» es una "
        "fuente libre con medidas idénticas: el texto ocupa lo mismo y no se descoloca.":
            "“{family}” can't be downloaded (it's from Microsoft). “{sub}” is a "
            "free font with identical metrics: text takes up the same space and doesn't shift.",
        "«{family}» — no está en Google Fonts: se usa «Arial» en su lugar. Si quieres usar «{family}», "
        "instálala en Windows (doble clic en el archivo de la fuente → Instalar) y reabre la aplicación.":
            "“{family}” — not on Google Fonts: “Arial” is used instead. If you want to use “{family}”, "
            "install it in Windows (double-click the font file → Install) and reopen the app.",
        "Suele ser una fuente de pago o del sistema, y no se puede descargar de aquí.":
            "It's usually a paid or system font, and can't be downloaded from here.",
        "No se pudo conectar con Google Fonts. Comprueba tu conexión a internet.":
            "Couldn't connect to Google Fonts. Check your internet connection.",
        "«{family}» — sin conexión": "“{family}” — no connection",
        "Marca al menos una fuente.": "Check at least one font.",
        "Listo: {names} instalada(s). Ya se usarán al editar este PDF.":
            "Done: {names} installed. They'll now be used when editing this PDF.",
        "  Cerrar": "  Close",
        "No se pudo descargar: {msg}": "Couldn't download: {msg}",
        "Descargando «{fam}»: {name} ({i}/{n})": "Downloading “{fam}”: {name} ({i}/{n})",
        "«{fam}» descargada": "“{fam}” downloaded",
        "Instalando «{family}» en Windows…": "Installing “{family}” in Windows…",
        "Edit – Editor visual": "Edit – Visual editor",
        "Clic sobre cualquier texto de la página para editarlo directamente, "
        "sobre la propia página. Enter hace una línea nueva, Ctrl+Enter confirma y Esc cancela. Usa la fuente original del "
        "PDF si la tienes instalada en Windows; si no, avisa y usa una de respaldo.":
            "Click any text on the page to edit it directly, "
            "right on the page itself. Enter makes a new line, Ctrl+Enter confirms and Esc cancels. It uses the PDF's "
            "original font if you have it installed in Windows; otherwise it warns you and uses a fallback.",
        "Descargar fuentes…": "Download fonts…",
        "Ignorar": "Ignore",
        "Reiniciar con este documento": "Restart with this document",
        "Cierra y vuelve a abrir la aplicación con este mismo documento y sus cambios, para "
        "que reconozca una fuente recién instalada":
            "Closes and reopens the app with this same document and its changes, so "
            "it recognizes a font you just installed",
        "Deshacer (Ctrl+Z)": "Undo (Ctrl+Z)",
        "Rehacer (Ctrl+Y)": "Redo (Ctrl+Y)",
        "Tapar texto con una barra negra": "Cover text with a black bar",
        "Reemplazar": "Replace",
        "Buscar y reemplazar texto": "Find and replace text",
        "Editar el texto existente: haz clic sobre un texto y cámbialo": "Edit existing text: click on a text and change it",
        "Configurar página": "Configure page",
        "Marca qué es cabecera y pie de página y cómo se repiten en páginas nuevas":
            "Mark what's the header and footer and how they repeat on new pages",
        "Añadir texto nuevo: haz clic en cualquier punto de la página y escribe":
            "Add new text: click anywhere on the page and type",
        "Automático: deduce párrafos, listas, cabecera, pie y numeración, y reparte el texto "
        "entre páginas.\nManual: cada línea se edita por separado y no se mueve nada más.":
            "Automatic: infers paragraphs, lists, header, footer and numbering, and spreads the text "
            "across pages.\nManual: each line is edited separately and nothing else moves.",
        "Marcar": "Markup",
        "Resaltar, subrayar o tachar texto arrastrando sobre él": "Highlight, underline or strike through text by dragging over it",
        "Dibujo libre (lápiz, rotulador), rectángulos, elipses, líneas y flechas":
            "Freehand drawing (pencil, marker), rectangles, ellipses, lines and arrows",
        "Insertar una imagen, o seleccionar, mover y borrar las que ya hay en el PDF":
            "Insert an image, or select, move and delete the ones already in the PDF",
        "Firma": "Signature",
        "Firmar: dibuja, escribe o usa una imagen; se guarda para volver a usarla":
            "Sign: draw, type or use an image; it's saved to reuse later",
        "Convertir un texto, un área, una imagen o un dibujo en un enlace; clic en uno existente para editarlo":
            "Turn a text, an area, an image or a drawing into a link; click an existing one to edit it",
        "Rellenar los campos del PDF, crear campos nuevos o aplanar el formulario":
            "Fill in the PDF's fields, create new fields, or flatten the form",
        "Notas": "Notes",
        "Notas y comentarios, archivos adjuntos y ocultar las anotaciones": "Notes and comments, attached files and hiding annotations",
        "Copiar texto con sentido: arrastra una zona o haz clic en un párrafo o tabla. "
        "Entiende párrafos, columnas y tablas (también en escaneos)":
            "Copy text with meaning: drag over an area or click a paragraph or table. "
            "Understands paragraphs, columns and tables (even in scans)",
        "Sello de texto (APROBADO, RECIBIDO…) con fecha y autor": "Text stamp (APPROVED, RECEIVED…) with date and author",
        "Alejar (Ctrl y −, o Ctrl + rueda)": "Zoom out (Ctrl and −, or Ctrl + wheel)",
        "Acercar (Ctrl y +, o Ctrl + rueda)": "Zoom in (Ctrl and +, or Ctrl + wheel)",
        "Ajustar al ancho de la ventana (Ctrl+0)": "Fit to window width (Ctrl+0)",
        "Con este panel abierto, clica sobre cualquier fragmento de texto "
        "de la página para taparlo al instante, o clica y arrastra sobre "
        "cualquier área (también fotos o firmas) para censurar justo esa "
        "zona. También puedes buscar un texto exacto aquí abajo. "
        "Esta acción no se puede deshacer.":
            "With this panel open, click any piece of text "
            "on the page to cover it instantly, or click and drag over "
            "any area (including photos or signatures) to redact exactly that "
            "zone. You can also search for an exact text below. "
            "This action cannot be undone.",
        "O escribe aquí un texto exacto a censurar": "Or type an exact text to redact here",
        "Censurar texto": "Redact text",
        "Buscar y reemplazar": "Find and replace",
        "Reemplazar por (vacío = eliminar)": "Replace with (empty = delete)",
        "Distinguir mayúsculas y minúsculas": "Match case",
        "Reemplaza en todo el documento conservando la fuente, el tamaño y el color. Ctrl+Z lo deshace.":
            "Replaces throughout the document keeping the font, size and color. Ctrl+Z undoes it.",
        "Este PDF tiene campos de formulario: usa el botón Formulario para rellenarlos.":
            "This PDF has form fields: use the Form button to fill them in.",
        "Pág. {n} / {total}": "Pg. {n} / {total}",
        "La fuente «{fam}» no está instalada, pero está en Google Fonts: pulsa «Descargar "
        "fuentes…» para instalarla. Mientras tanto se usa «{fb}».":
            "The font “{fam}” isn't installed, but it's on Google Fonts: press “Download "
            "fonts…” to install it. Meanwhile “{fb}” is used.",
        "La fuente «{fam}» no está en Google Fonts (suele ser de pago o de otro programa): se está "
        "usando «{fb}» en su lugar. Si quieres usar «{fam}», descárgala e instálala en Windows "
        "(doble clic en el archivo de la fuente → Instalar) y pulsa «Reiniciar con este documento».":
            "The font “{fam}” isn't on Google Fonts (it's usually paid or from another program): "
            "“{fb}” is being used instead. If you want to use “{fam}”, download and install it in Windows "
            "(double-click the font file → Install) and press “Restart with this document”.",
        "La fuente «{fam}» no está instalada: se está usando «{fb}» en su lugar. Si quieres usar "
        "«{fam}», instálala en Windows y reabre la aplicación (o mira si está en Google Fonts "
        "con «Descargar fuentes…»).":
            "The font “{fam}” isn't installed: “{fb}” is being used instead. If you want to use "
            "“{fam}”, install it in Windows and reopen the app (or check if it's on Google Fonts "
            "with “Download fonts…”).",
        "Fuentes instaladas: {names}": "Fonts installed: {names}",
        "Añadir página al final": "Add page at the end",
        "Añadir página después de la {n}": "Add page after {n}",
        "Añadir página antes de la {n}": "Add page before {n}",
        "Girar la página {n} a la derecha": "Rotate page {n} right",
        "Girar la página {n} a la izquierda": "Rotate page {n} left",
        "Girar todas las páginas a la derecha": "Rotate all pages right",
        "Borrar la página {n}": "Delete page {n}",
        "{n} página{s} insertada{s}.": "{n} page{s} inserted.",
        "No se pudo insertar ese PDF (¿tiene contraseña?).": "Couldn't insert that PDF (does it have a password?).",
        "Marca la cabecera y el pie de página para copiarlos a la página nueva y decide cómo se numera.":
            "Mark the header and footer to copy them to the new page and decide how it's numbered.",
        "Página añadida (ahora es la {n}).": "Page added (now it's page {n}).",
        "No se pudo añadir la página.": "Couldn't add the page.",
        "Página girada. Mientras esté girada no se puede editar su contenido; vuelve a girarla "
        "a su posición para hacerlo.":
            "Page rotated. While it's rotated its content can't be edited; rotate it back "
            "to its position to do so.",
        "Páginas giradas.": "Pages rotated.",
        "No se pudo girar.": "Couldn't rotate.",
        "No se puede borrar la única página del documento.": "Can't delete the document's only page.",
        "Borrar página": "Delete page",
        "¿Borrar la página {n} con todo su contenido?\n"
        "Las siguientes se renumeran. Puedes deshacerlo con Ctrl+Z.":
            "Delete page {n} with all its content?\n"
            "The following ones will be renumbered. You can undo it with Ctrl+Z.",
        "Página {n} borrada.": "Page {n} deleted.",
        "No se pudo borrar la página.": "Couldn't delete the page.",
        "Haz clic en la página donde quieras escribir.": "Click on the page where you want to write.",
        "  Marcar": "  Markup",
        "  Dibujar": "  Draw",
        "No se pudo crear el sello.": "Couldn't create the stamp.",
        "el sello": "the stamp",
        "Arrastra para copiar una zona, o haz clic en un párrafo o una tabla. Esc para salir.":
            "Drag to copy an area, or click a paragraph or a table. Esc to exit.",
        "No se pudo analizar la página: {e}": "Couldn't analyze the page: {e}",
        "No he encontrado texto en esa página.": "I didn't find text on that page.",
        "Ahí no hay texto. Arrastra para elegir una zona.": "There's no text there. Drag to choose an area.",
        "Esa zona no contiene texto.": "That area contains no text.",
        "Esta página es una imagen: el texto se ha reconocido ahora mismo (OCR, idioma: {langs}). "
        "Para tenerlo siempre buscable y copiable en cualquier lector, usa Herramientas → OCR.":
            "This page is an image: the text has just been recognized (OCR, language: {langs}). "
            "To always have it searchable and copyable in any reader, use Tools → OCR.",
        "Añadir nota": "Add note",
        "Adjuntar archivo…": "Attach file…",
        "Ocultar anotaciones (solo en pantalla)": "Hide annotations (on screen only)",
        "Terminar": "Finish",
        "Haz clic donde quieras la nota. Clic en una nota para editarla; arrástrala para moverla.":
            "Click where you want the note. Click a note to edit it; drag it to move it.",
        "No se pudo guardar la nota.": "Couldn't save the note.",
        "Elige el archivo que quieres adjuntar": "Choose the file you want to attach",
        "Ese archivo pesa más de 25 MB; no se adjunta.": "That file is over 25 MB; it won't be attached.",
        "Mueve el clip hasta donde quieras ponerlo y haz clic. Esc cancela.":
            "Move the clip to where you want to place it and click. Esc cancels.",
        "Guardar una copia de «{name}»…": "Save a copy of “{name}”…",
        "Quitar adjunto": "Remove attachment",
        "No se pudo leer el adjunto.": "Couldn't read the attachment.",
        "Guardar adjunto": "Save attachment",
        "Adjunto guardado: {name}. No se abre solo: ábrelo tú si te fías de su origen.":
            "Attachment saved: {name}. It doesn't open by itself: open it yourself if you trust its source.",
        "Haz clic en un campo (recuadro azul) para rellenarlo. Arrastra en un hueco para crear uno nuevo.":
            "Click a field (blue box) to fill it in. Drag over a gap to create a new one.",
        "Detectar campos automáticamente…": "Auto-detect fields…",
        "Busca rayas, recuadros vacíos y casillas para convertirlos en campos":
            "Looks for lines, empty boxes and checkboxes to turn into fields",
        "Orden de tabulación": "Tab order",
        "Aplanar formulario…": "Flatten form…",
        "Convierte los campos rellenados en contenido fijo de la página": "Turns filled-in fields into fixed page content",
        "Rellenar y crear campos": "Fill in and create fields",
        "Hay {n} campos (recuadros azules): haz clic en uno para rellenarlo. ":
            "There are {n} fields (blue boxes): click one to fill it in. ",
        "Este PDF no tiene campos. ": "This PDF has no fields. ",
        "Arrastra un recuadro vacío para crear uno nuevo; clic derecho "
        "sobre un campo para eliminarlo.":
            "Drag over an empty box to create a new one; right-click "
            "a field to delete it.",
        "No encontré rayas, recuadros vacíos ni casillas que convertir en campos.":
            "I didn't find lines, empty boxes or checkboxes to turn into fields.",
        "Detectar campos": "Detect fields",
        "He encontrado {total} posibles campos (marcados en verde): {n_text} de texto y {n_chk} casillas.\n\n"
        "Salen de rayas, recuadros vacíos y cuadritos de la página; revisa que no sobre ninguno (puedes borrar "
        "los que no quieras con clic derecho). ¿Crearlos?":
            "I found {total} possible fields (marked in green): {n_text} text and {n_chk} checkboxes.\n\n"
            "They come from lines, empty boxes and small squares on the page; check that none is extra (you can delete "
            "the ones you don't want with right-click). Create them?",
        "{n} campos creados. Haz clic en uno para rellenarlo.": "{n} fields created. Click one to fill it in.",
        "No se pudo crear ningún campo.": "Couldn't create any field.",
        "Este PDF no tiene campos de formulario.": "This PDF has no form fields.",
        "Orden de tabulación: {order} (en {n} página{s}).": "Tab order: {order} (on {n} page{s}).",
        "Campo creado.": "Field created.",
        "No se pudo crear el campo.": "Couldn't create the field.",
        "Aplanar formulario": "Flatten form",
        "Los campos pasarán a ser contenido fijo de la página, con lo que hayas rellenado: "
        "ya no se podrán editar. Puedes deshacerlo con Ctrl+Z hasta que guardes.\n\n"
        "¿Aplanar el formulario?":
            "The fields will become fixed page content, with whatever you've filled in: "
            "they can no longer be edited. You can undo it with Ctrl+Z until you save.\n\n"
            "Flatten the form?",
        "Formulario aplanado.": "Form flattened.",
        "No se pudo aplanar el formulario.": "Couldn't flatten the form.",
        "Arrastra sobre un texto o un área para crear un enlace. Haz clic en un recuadro azul "
        "para editarlo o quitarlo.":
            "Drag over a text or an area to create a link. Click a blue box "
            "to edit or remove it.",
        "Enlace quitado.": "Link removed.",
        "Enlace guardado.": "Link saved.",
        "Enlace creado ({n} zona{s}).": "Link created ({n} zone{s}).",
        "No se pudo guardar el enlace.": "Couldn't save the link.",
        "No se pudo añadir el icono.": "Couldn't add the icon.",
        "Icono añadido. Arrástralo para moverlo; el punto de arriba lo gira (o las teclas [ y ]).":
            "Icon added. Drag it to move it; the top dot rotates it (or the [ and ] keys).",
        "Insertar una imagen…": "Insert an image…",
        "Seleccionar, mover o borrar imágenes": "Select, move or delete images",
        "Haz clic en una imagen para seleccionarla: arrástrala para moverla, usa los puntos para cambiar "
        "el tamaño y pulsa Supr para borrarla (en las imágenes del PDF, solo borrar). Esc para salir.":
            "Click an image to select it: drag it to move it, use the dots to resize "
            "it and press Delete to remove it (for images already in the PDF, only removing works). Esc to exit.",
        "Elige una imagen": "Choose an image",
        "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;Todos los archivos (*.*)":
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;All files (*.*)",
        "No se pudo leer esa imagen.": "Couldn't read that image.",
        "la imagen": "the image",
        "Haz clic donde quieras {what} (o arrastra para dibujarle el tamaño). Después puedes "
        "moverla, cambiarle el tamaño por las esquinas (Mayús = deformar) y borrarla con Supr.":
            "Click where you want {what} (or drag to draw its size). Afterwards you can "
            "move it, resize it from the corners (Shift = distort) and delete it with Delete.",
        "la firma": "the signature",
        "Crear firma nueva…": "Create new signature…",
        "Gestionar mis firmas": "Manage my signatures",
        "Cambiar el nombre…": "Rename…",
        "Editar…": "Edit…",
        "Nombre de la firma": "Signature name",
        "Nombre:": "Name:",
        "Firma renombrada.": "Signature renamed.",
        "Firma actualizada. Se usará la nueva versión en los documentos siguientes.":
            "Signature updated. The new version will be used in the following documents.",
        "Ese dibujo no se puede guardar como firma.": "That drawing can't be saved as a signature.",
        "Guardar como firma": "Save as signature",
        "Nombre de la firma:": "Signature name:",
        "Firma guardada: la tienes en el menú Firma.": "Signature saved: you'll find it in the Signature menu.",
        "No se pudo abrir esa firma.": "Couldn't open that signature.",
        "Borrar firma": "Delete signature",
        "¿Borrar esta firma guardada?": "Delete this saved signature?",
        "Firma borrada.": "Signature deleted.",
        "Seleccionar / mover": "Select / move",
        "Lápiz libre": "Freehand pencil",
        "Rotulador libre": "Freehand marker",
        "Rectángulo": "Rectangle",
        "Elipse": "Ellipse",
        "Línea": "Line",
        "Flecha": "Arrow",
        "Color del borde / trazo": "Border / stroke color",
        "Color de relleno (rectángulo y elipse)": "Fill color (rectangle and ellipse)",
        "Grosor: {label}": "Thickness: {label}",
        "Grosor de la línea": "Line thickness",
        "Opacidad: total por defecto 100 %; opcionalmente otra para el trazo o el relleno":
            "Opacity: overall 100% by default; optionally a different one for stroke or fill",
        "Forma de la punta de las flechas": "Arrowhead shape",
        "Duplicar selección": "Duplicate selection",
        "Eliminar selección": "Delete selection",
        "Relleno (formas)": "Fill (shapes)",
        "Terminar de dibujar": "Finish drawing",
        "Clic en una forma o trazo para seleccionarlo: arrastra para mover, puntos blancos para "
        "cambiar el tamaño, Ctrl+D duplica, Supr borra.":
            "Click a shape or stroke to select it: drag to move, white dots to "
            "resize, Ctrl+D duplicates, Delete removes.",
        "Dibuja con el ratón. Para mover, escalar o duplicar un trazo: «Seleccionar / mover».":
            "Draw with the mouse. To move, scale or duplicate a stroke: “Select / move”.",
        "Arrastra para dibujar (Mayús para proporción exacta). Para mover, escalar o duplicar "
        "una forma ya dibujada, elige «Seleccionar / mover» o haz clic en su borde.":
            "Drag to draw (Shift for exact proportion). To move, scale or duplicate "
            "an already-drawn shape, choose “Select / move” or click its border.",
        "Resaltar": "Highlight",
        "Subrayar": "Underline",
        "Tachar": "Strike through",
        "Quitar marca": "Remove markup",
        "Terminar de marcar": "Finish marking up",
        "Haz clic sobre una marca para quitarla.": "Click a markup to remove it.",
        "Arrastra sobre el texto (o haz clic en una palabra) para marcarlo.": "Drag over the text (or click a word) to mark it up.",
        "Modo manual: cada línea se edita por separado y no se mueve nada más.":
            "Manual mode: each line is edited separately and nothing else moves.",
        "Modo automático: párrafos, listas, cabecera, pie y numeración.":
            "Automatic mode: paragraphs, lists, header, footer and numbering.",
        "No se pudo guardar el borrador para reiniciar.": "Couldn't save the draft to restart.",
        "No se pudo reiniciar la aplicación; ábrela tú y te preguntará si continúas.":
            "Couldn't restart the app; open it yourself and it'll ask if you want to continue.",
        "La fuente «{family}» no está instalada: se ha usado «{fb}» en su lugar. Si quieres usar «{family}», "
        "instálala en Windows (doble clic en su archivo → Instalar) y reabre la aplicación.":
            "The font “{family}” isn't installed: “{fb}” has been used instead. If you want to use “{family}”, "
            "install it in Windows (double-click its file → Install) and reopen the app.",
        "Cambios sin guardar": "Unsaved changes",
        "Tienes cambios sin guardar en este PDF. ¿Guardarlos antes de cambiar de archivo?":
            "You have unsaved changes in this PDF. Save them before switching files?",
        "No se pudo guardar": "Couldn't save",
        "✓ Guardado: {name} — listo para guardar una copia o seguir con otra herramienta":
            "✓ Saved: {name} — ready to save a copy or continue with another tool",
        "Escribe el texto a censurar": "Type the text to redact",
        "Censurando…": "Redacting…",
        "✓ Censurado (sin vuelta atrás): {name} — listo para guardar o seguir con otra herramienta":
            "✓ Redacted (no going back): {name} — ready to save or continue with another tool",
        "No se encontró ese texto en el PDF": "That text wasn't found in the PDF",
        "Escribe el texto nuevo y pulsa Reemplazar.": "Type the new text and press Replace.",
        "Escribe el texto a buscar": "Type the text to search for",
        "El texto nuevo no cabe y se creará una página. Marca la cabecera y el pie para no "
        "tocarlos y decide cómo se repiten. Si cancelas, no se reemplaza nada más.":
            "The new text doesn't fit and a page will be created. Mark the header and footer so they're not "
            "touched and decide how they repeat. If you cancel, nothing else is replaced.",
        "No se pudo reemplazar: {e}": "Couldn't replace: {e}",
        "Cancelado: no se ha reemplazado nada.": "Cancelled: nothing was replaced.",
        "No se encontró ese texto en el PDF.": "That text wasn't found in the PDF.",
        "✓ {n} cambio{s1} en {np} página{s2}. Ctrl+Z lo deshace.": "✓ {n} change{s1} in {np} page{s2}. Ctrl+Z undoes it.",
        "Texto": "Text",
        "Imagen": "Image",
        "Buscar": "Search",

        # --- ui/tools.py ---
        "Herramientas": "Tools",
        "Sin vista previa": "No preview",
        "🔒 Protegido con contraseña": "🔒 Password protected",
        "No se puede mostrar este archivo": "Can't display this file",
        "No se puede mostrar la página": "Can't display the page",
        "Página {i} de {n}": "Page {i} of {n}",
        "Arrastra aquí los archivos a convertir\no pulsa «Añadir archivos…»":
            "Drag the files to convert here\nor click “Add files…”",
        "Contraseña del PDF:": "PDF password:",
        "solo si lo necesita": "only if needed",
        "Añade un PDF en la pantalla principal para usar esta herramienta.":
            "Add a PDF on the main screen to use this tool.",
        " · tiene contraseña de apertura": " · has an opening password",
        " · {pages} pág.": " · {pages} pages",
        "Peso actual: {size}": "Current size: {size}",
        "Añade primero un PDF en la pantalla principal.": "Add a PDF on the main screen first.",
        "Procesando {unit} {i} de {n}…": "Processing {unit} {i} of {n}…",
        "{n} con error: ": "{n} with an error: ",
        "Sin cambios.": "No changes.",
        "Reduce el peso del PDF reescalando las imágenes grandes y limpiando lo que sobra. El texto no cambia.":
            "Reduces the PDF's size by rescaling large images and cleaning up what's left over. The text doesn't change.",
        "Calidad alta (ahorra poco)": "High quality (saves little)",
        "Equilibrada (recomendada)": "Balanced (recommended)",
        "Máxima compresión (calidad menor)": "Maximum compression (lower quality)",
        "Comprimiendo…": "Compressing…",
        "comprimido": "compressed",
        "Bloquea el PDF con contraseña (cifrado AES-256) o quita la protección de uno que ya tengas. Si olvidas la contraseña, nadie podrá recuperarla: guárdala.":
            "Locks the PDF with a password (AES-256 encryption) or removes the protection from one you already have. If you forget the password, no one can recover it: save it somewhere safe.",
        "Bloquear": "Lock",
        "Contraseña para abrirlo (déjala vacía para solo limitar permisos)":
            "Password to open it (leave empty to only restrict permissions)",
        "Repite la contraseña": "Repeat the password",
        "Contraseña de propietario para cambiar permisos (opcional)":
            "Owner password to change permissions (optional)",
        "Permitir a quien lo abra:": "Allow whoever opens it to:",
        "Imprimir": "Print",
        "Modificar": "Modify",
        "Anotar y rellenar": "Annotate and fill in",
        "Desbloquear": "Unlock",
        "Escribe arriba la «Contraseña del PDF» si hace falta para abrirlo. Úsalo solo con documentos que sean tuyos o que tengas permiso para modificar.":
            "Enter the “PDF password” above if one is needed to open it. Only use this with documents that are yours or that you have permission to modify.",
        "Quitar protección": "Remove protection",
        "Las dos contraseñas no coinciden.": "The two passwords don't match.",
        "Usa una contraseña de al menos 4 caracteres.": "Use a password of at least 4 characters.",
        "Ya tenía(n) contraseña: desbloquéalo(s) primero.": "Already had a password: unlock it/them first.",
        "Protegiendo…": "Protecting…",
        "protegido": "protected",
        "{n} ya tenía(n) contraseña: no se han tocado.": "{n} already had a password: they weren't touched.",
        "Quitando protección…": "Removing protection…",
        "desprotegido": "unprotected",
        "Añade un texto o una imagen detrás del contenido de las páginas, con transparencia. No tapa nada. Los cambios solo se ven en la vista previa: no se guarda nada hasta pulsar «Añadir marca de agua».":
            "Adds a text or image behind the page content, with transparency. It doesn't cover anything. Changes are only shown in the preview: nothing is saved until you click “Add watermark”.",
        "CONFIDENCIAL": "CONFIDENTIAL",
        "Elige una imagen (PNG con fondo transparente queda mejor)": "Choose an image (PNG with a transparent background looks best)",
        "Elegir…": "Choose…",
        "Gris": "Gray",
        "Azul": "Blue",
        "Amarillo": "Yellow",
        "Rosa": "Pink",
        "Morado": "Purple",
        "Opacidad": "Opacity",
        "Repetir (mosaico)": "Repeat (tile)",
        "Giro del texto": "Text rotation",
        "en mosaico": "when tiled",
        "Giro de la imagen": "Image rotation",
        "Páginas": "Pages",
        "todas  ·  ejemplos: 1-3, 5, 8-   ·   pares   ·   impares": "all  ·  examples: 1-3, 5, 8-   ·   even   ·   odd",
        "Añadir marca de agua": "Add watermark",
        "Color de la marca de agua": "Watermark color",
        "Otro color…": "Other color…",
        "Imagen de la marca de agua": "Watermark image",
        "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)": "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        "Añadiendo marca de agua…": "Adding watermark…",
        "con marca de agua": "with watermark",
        "Añade el número de página. Los cambios solo se ven en la vista previa: no se guarda nada hasta pulsar «Añadir numeración».":
            "Adds the page number. Changes are only shown in the preview: nothing is saved until you click “Add numbering”.",
        "Posición": "Position",
        "Página {n} de {total}": "Page {n} of {total}",
        "{n} = número de página, {total} = último número. Puedes escribir tu propio formato.":
            "{n} = page number, {total} = last number. You can type your own format.",
        "Empezar en": "Start at",
        "Tamaño": "Size",
        "Margen": "Margin",
        "Color de la numeración": "Numbering color",
        "Añadir numeración": "Add numbering",
        "todas  ·  ejemplos: 2-   (deja la portada sin número)   ·   pares   ·   impares":
            "all  ·  examples: 2-   (leaves the cover page unnumbered)   ·   even   ·   odd",
        "Numerando páginas…": "Numbering pages…",
        "numerado": "numbered",
        "Pasa el PDF a modo oscuro: fondo oscuro y colores más claros. El texto sigue siendo texto de verdad: se puede seguir buscando y copiando. Los cambios solo se ven en la vista previa: no se guarda nada hasta pulsar «Invertir colores».":
            "Switches the PDF to dark mode: dark background and lighter colors. The text stays real text: it can still be searched and copied. Changes are only shown in the preview: nothing is saved until you click “Invert colors”.",
        "Modo": "Mode",
        "Oscuro, conservar colores de las fotos": "Dark, keep photo colors",
        "Invertir todos los colores (como un negativo)": "Invert all colors (like a negative)",
        "Fondo": "Background",
        "No tocar las páginas que ya son oscuras (diapositivas, fotos a página completa…)":
            "Don't touch pages that are already dark (slides, full-page photos…)",
        "Invirtiendo colores…": "Inverting colors…",
        "con modo oscuro": "with dark mode",
        "Aplanar convierte comentarios, dibujos y campos de formulario en contenido fijo (ya no se pueden editar). Reparar reconstruye un PDF dañado o que no se abre bien.":
            "Flattening turns comments, drawings and form fields into fixed content (they can no longer be edited). Repairing rebuilds a damaged PDF or one that doesn't open properly.",
        "Aplanar": "Flatten",
        "Anotaciones (resaltados, dibujos, notas, sellos…)": "Annotations (highlights, drawings, notes, stamps…)",
        "Campos de formulario (con lo rellenado)": "Form fields (with what was filled in)",
        "Reparar": "Repair",
        "Reparar PDF": "Repair PDF",
        "Aplanando…": "Flattening…",
        "aplanado": "flattened",
        "Reparando…": "Repairing…",
        "revisado": "checked",
        "Convierte imágenes, texto, Markdown, HTML y otros formatos a PDF. Word, Excel y PowerPoint necesitan Office o LibreOffice instalados. Formatos: {exts}":
            "Converts images, text, Markdown, HTML and other formats to PDF. Word, Excel and PowerPoint need Office or LibreOffice installed. Formats: {exts}",
        "No encuentro Office ni LibreOffice: los archivos de Word, Excel o PowerPoint no se podrán convertir hasta que instales uno de los dos. Las imágenes, el texto y el HTML sí funcionan igual.":
            "I can't find Office or LibreOffice: Word, Excel or PowerPoint files won't be able to convert until you install one of the two. Images, text and HTML still work the same.",
        "Instalar LibreOffice…": "Install LibreOffice…",
        "Ya lo instalé: comprobar": "I already installed it: check",
        "Añadir archivos…": "Add files…",
        "Quitar": "Remove",
        "Imágenes en página:": "Images on page:",
        "Convertir": "Convert",
        "Todos los compatibles ({exts})": "All supported ({exts})",
        "Archivos a convertir": "Files to convert",
        "Añade al menos un archivo.": "Add at least one file.",
        "{n} PDF creado(s) (están en la lista y en Descargas).": "{n} PDF(s) created (they're in the list and in Downloads).",
        "No se pudo: ": "Couldn't: ",
        "Convirtiendo…": "Converting…",
        "Ya puedes convertir Word, Excel y PowerPoint.": "You can now convert Word, Excel and PowerPoint.",
        "Sigo sin encontrar Office ni LibreOffice.": "I still can't find Office or LibreOffice.",
        "Se descargará el instalador oficial de LibreOffice {version} para Windows\n«{filename}», unos {size_mb:.0f} MB\ndesde download.documentfoundation.org.\n\nDespués se abrirá su propio instalador: tú decides si seguir, aceptas sus condiciones y lo instalas (con el permiso de Windows si lo pide). El programa no instala nada por su cuenta.":
            "The official LibreOffice {version} installer for Windows will be downloaded\n“{filename}”, about {size_mb:.0f} MB\nfrom download.documentfoundation.org.\n\nIts own installer will then open: you decide whether to continue, accept its terms and install it (with Windows' permission if it asks). The program doesn't install anything on its own.",
        "Instalar LibreOffice": "Install LibreOffice",
        "Descargando LibreOffice…": "Downloading LibreOffice…",
        "Descargando LibreOffice… {done:.0f} / {total:.0f} MB": "Downloading LibreOffice… {done:.0f} / {total:.0f} MB",
        "Se descargó, pero no se pudo abrir el instalador. Ábrelo a mano.":
            "It downloaded, but the installer couldn't be opened. Open it manually.",
        "Se ha abierto el instalador de LibreOffice. Cuando termines, vuelve aquí y pulsa «Ya lo instalé: comprobar».":
            "The LibreOffice installer has opened. When you're done, come back here and click “I already installed it: check”.",
        "Exporta el PDF elegido a otro formato. El PDF original no se modifica; el resultado se guarda en Descargas.":
            "Exports the chosen PDF to another format. The original PDF isn't modified; the result is saved in Downloads.",
        "Formato de salida": "Output format",
        "Calidad": "Quality",
        "Normal (100 ppp)": "Normal (100 dpi)",
        "Alta (150 ppp)": "High (150 dpi)",
        "Muy alta (300 ppp)": "Very high (300 dpi)",
        "Una imagen por página, con transparencia donde la hubiera.": "One image per page, with transparency where there was any.",
        "Una imagen por página, más ligeras pero sin transparencia.": "One image per page, lighter but without transparency.",
        "El texto que ya tiene el PDF. Si es un escaneo sin OCR previo, no saldrá nada: pásalo antes por OCR.":
            "The text the PDF already has. If it's a scan without prior OCR, nothing will come out: run it through OCR first.",
        "El texto de cada página, colocado tal como está en el PDF.": "The text of each page, placed just as it is in the PDF.",
        "Sale editable, pero no es una copia exacta: tablas, columnas y fuentes pueden no coincidir del todo con el original.":
            "Comes out editable, but it's not an exact copy: tables, columns and fonts may not fully match the original.",
        "convertido (en Descargas)": "converted (in Downloads)",
        "Examina el PDF elegido: versión, páginas, metadatos, cifrado y permisos, fuentes, imágenes, formulario, marcadores y si tiene firma digital. No lo modifica ni lo guarda.":
            "Examines the chosen PDF: version, pages, metadata, encryption and permissions, fonts, images, form, bookmarks and whether it has a digital signature. It doesn't modify or save it.",
        "Analizar": "Analyze",
        "Pulsa «Analizar» para ver la información del PDF elegido.": "Click “Analyze” to see information about the chosen PDF.",
        "No se ha podido analizar: {err}": "Couldn't analyze it: {err}",
        "Analizado(s) {n} archivo(s).": "Analyzed {n} file(s).",
        "Analizando…": "Analyzing…",
        "Archivo: {name}  ({size})": "File: {name}  ({size})",
        "Versión: {v}": "Version: {v}",
        "Páginas: {n}": "Pages: {n}",
        "  • {n} página(s) de {w} × {h} pt ({orientation})": "  • {n} page(s) of {w} × {h} pt ({orientation})",
        "Metadatos:": "Metadata:",
        "Programa de creación": "Creator program",
        "Productor": "Producer",
        "Creado": "Created",
        "Modificado": "Modified",
        "(sin metadatos)": "(no metadata)",
        "Seguridad:": "Security:",
        "Necesita contraseña para abrirse: {v}": "Needs a password to open: {v}",
        "sí": "yes",
        "no": "no",
        "Cifrado: {v}": "Encrypted: {v}",
        "Permite: {v}": "Allows: {v}",
        "nada": "nothing",
        "Firma digital: {v}": "Digital signature: {v}",
        "sí tiene (usa «Verificar firmas» para comprobarla)": "yes, it has one (use “Verify signatures” to check it)",
        "no tiene": "no, it doesn't",
        "Fuentes ({n}):": "Fonts ({n}):",
        "incrustada": "embedded",
        "no incrustada": "not embedded",
        "Imágenes: {n}": "Images: {n}",
        "Formulario: {v}": "Form: {v}",
        "sí, con {n} campo(s)": "yes, with {n} field(s)",
        "Marcadores: {n}": "Bookmarks: {n}",
        "Comprueba las firmas digitales del PDF elegido: quién firmó, cuándo y si el documento se modificó después de firmarlo. No comprueba si el certificado es de una entidad de confianza (no dice si la firma es «cualificada» en el sentido legal), solo si el documento está intacto.":
            "Checks the chosen PDF's digital signatures: who signed, when, and whether the document was modified after signing. It doesn't check whether the certificate belongs to a trusted entity (it doesn't say whether the signature is “qualified” in the legal sense), only whether the document is intact.",
        "Comprobar firmas": "Verify signatures",
        "Pulsa «Comprobar firmas» para ver las firmas del PDF elegido.": "Click “Verify signatures” to see the chosen PDF's signatures.",
        "No se ha podido comprobar: {err}": "Couldn't be checked: {err}",
        "Firmas comprobadas.": "Signatures verified.",
        "Alguna firma indica que un documento se modificó después.": "A signature indicates the document was modified afterward.",
        "Comprobando firmas…": "Verifying signatures…",
        "Este PDF no tiene ninguna firma digital.": "This PDF has no digital signature.",
        "{n} firma(s) encontrada(s):\n": "{n} signature(s) found:\n",
        "— Firma {i}: campo «{field}»": "— Signature {i}: field “{field}”",
        "Firmante (según el certificado): {v}": "Signer (according to the certificate): {v}",
        "Emitido por: {v}": "Issued by: {v}",
        "Fecha de firma: {v}": "Signing date: {v}",
        "(no indicada)": "(not given)",
        "Firma íntegra (no se ha tocado desde que se firmó): {v}": "Signature intact (untouched since it was signed): {v}",
        "NO — el documento se modificó después de esta firma": "NO — the document was modified after this signature",
        "Aviso: esta firma no cubre todo el archivo (hay contenido añadido después, p. ej. otra firma posterior).":
            "Notice: this signature doesn't cover the whole file (there's content added afterward, e.g. another later signature).",
        "Qué cambió después: {v}": "What changed afterward: {v}",
        "ninguna (igual que cuando se firmó)": "none (same as when it was signed)",
        "se rellenaron campos de formulario": "form fields were filled in",
        "se añadieron anotaciones": "annotations were added",
        "sí, se modificó el contenido": "yes, the content was modified",
        "Nota: esto comprueba que el documento no se ha tocado desde que se firmó, pero no comprueba si el certificado pertenece de verdad a quien dice ser (para eso haría falta la lista de entidades de confianza de la UE, que no está incluida). No es una comprobación de validez legal ni dice si la firma es «cualificada».":
            "Note: this checks that the document hasn't been touched since it was signed, but it doesn't check whether the certificate truly belongs to who it claims to be (that would require the EU's trusted list, which isn't included). This isn't a legal validity check and doesn't say whether the signature is “qualified”.",
        "Reconoce el texto de un PDF escaneado (o hecho de imágenes) y lo añade de forma invisible: ya se puede buscar y copiar. Si la página es una foto torcida, puede enderezarla antes en el mismo paso. Funciona sin internet; los idiomas son archivos pequeños que se instalan una vez.":
            "Recognizes the text of a scanned PDF (or one made of images) and adds it invisibly: it can now be searched and copied. If the page is a crooked photo, it can be straightened first in the same step. Works without internet; the languages are small files installed once.",
        "Motor": "Engine",
        "RapidOCR · recomendado": "RapidOCR · recommended",
        "Tesseract · rápido": "Tesseract · fast",
        "RapidOCR no está instalado: pip install rapidocr": "RapidOCR isn't installed: pip install rapidocr",
        "RapidOCR usa redes neuronales (sin internet, gratis) y lee mucho mejor las fotos borrosas o pequeñas. Tesseract es más rápido y va bien con escaneos limpios.":
            "RapidOCR uses neural networks (no internet, free) and reads blurry or small photos much better. Tesseract is faster and works well with clean scans.",
        "Idiomas del documento:": "Document languages:",
        "Solo las páginas sin texto": "Only pages without text",
        "Máxima precisión": "Maximum accuracy",
        "Usa datos de idioma de alta precisión (tessdata_best, unos 15 MB por idioma, se descargan una vez). Más lento, pero lee mucho mejor el texto borroso o de baja resolución.":
            "Uses high-accuracy language data (tessdata_best, about 15 MB per language, downloaded once). Slower, but reads blurry or low-resolution text much better.",
        "Revisar el texto antes de guardar": "Review the text before saving",
        "Tras leer, se abre una vista para comparar el texto con la página y corregirlo. Desde ahí también puedes crear un PDF nuevo redibujado con el texto.":
            "After reading, a view opens to compare the text with the page and correct it. From there you can also create a new PDF redrawn with the text.",
        "Enderezar las páginas torcidas": "Straighten crooked pages",
        "Busca solo el papel, corrige la perspectiva y gira la página hasta que las líneas de texto queden horizontales (se guía por la base de las letras). Las páginas que ya están rectas no se tocan. Sirve para papel plano: una hoja arrugada no se aplana.":
            "Looks for just the paper, corrects the perspective and rotates the page until the lines of text are horizontal (guided by the base of the letters). Pages that are already straight aren't touched. Works for flat paper: a crumpled sheet won't be flattened.",
        "Reconocer texto": "Recognize text",
        "¿Otro idioma?": "Another language?",
        "Descargar otro idioma…": "Download another language…",
        "Instalar idioma": "Install language",
        "Se descargará el idioma «{name}» ({code}.traineddata, unos 1–10 MB) del repositorio oficial de Tesseract (github.com/tesseract-ocr/tessdata_fast) y se guardará en tu carpeta de datos del programa.\n\n¿Descargarlo?":
            "The “{name}” language ({code}.traineddata, about 1–10 MB) will be downloaded from Tesseract's official repository (github.com/tesseract-ocr/tessdata_fast) and saved in your program's data folder.\n\nDownload it?",
        "Idioma «{name}» instalado.": "Language “{name}” installed.",
        "Descargando «{name}»…": "Downloading “{name}”…",
        "Español": "Spanish", "Portugués": "Portuguese", "Inglés": "English", "Francés": "French",
        "Alemán": "German", "Italiano": "Italian", "Catalán": "Catalan", "Gallego": "Galician",
        "Euskera": "Basque", "Neerlandés": "Dutch", "Danés": "Danish", "Noruego": "Norwegian",
        "Sueco": "Swedish", "Finés": "Finnish", "Polaco": "Polish", "Checo": "Czech",
        "Eslovaco": "Slovak", "Esloveno": "Slovenian", "Húngaro": "Hungarian", "Rumano": "Romanian",
        "Búlgaro": "Bulgarian", "Croata": "Croatian", "Serbio": "Serbian", "Griego": "Greek",
        "Turco": "Turkish", "Ruso": "Russian", "Ucraniano": "Ukrainian", "Hebreo": "Hebrew",
        "Árabe": "Arabic", "Hindi": "Hindi", "Chino simplificado": "Simplified Chinese",
        "Chino tradicional": "Traditional Chinese", "Japonés": "Japanese", "Coreano": "Korean",
        "Tailandés": "Thai", "Vietnamita": "Vietnamese", "Indonesio": "Indonesian", "Latín": "Latin",
        "Lee bien fotos, escaneos borrosos y papel torcido. Detecta solo el idioma (alfabeto latino): no hace falta elegirlo. Es algo más lento.":
            "Reads photos, blurry scans and crooked paper well. Detects only the language (Latin alphabet): no need to choose it. It's a bit slower.",
        "Muy rápido y va bien con escaneos limpios y rectos. Elige abajo el idioma del documento; para fotos o texto borroso usa RapidOCR.":
            "Very fast and works well with clean, straight scans. Choose the document's language below; for photos or blurry text use RapidOCR.",
        "Marca al menos un idioma (o instala uno de la lista).": "Check at least one language (or install one from the list).",
        "Descargar datos de alta precisión": "Download high-accuracy data",
        "Para la máxima precisión se descargará, una sola vez: {names}.\n\nOrigen: github.com/tesseract-ocr/tessdata_best (repositorio oficial de Tesseract). Unos 15 MB por idioma (el de inglés pesa 15 MB). Se guardan en tu carpeta de datos del programa.\n\n¿Descargarlos?":
            "For maximum accuracy, this will be downloaded once: {names}.\n\nSource: github.com/tesseract-ocr/tessdata_best (Tesseract's official repository). About 15 MB per language (English weighs 15 MB). They're saved in your program's data folder.\n\nDownload them?",
        " También: {name}.": " Also: {name}.",
        "Texto guardado en {pages} página(s) ({words} palabras).": "Text saved on {pages} page(s) ({words} words).",
        "Guardando…": "Saving…",
        "Revisión cancelada: no se ha guardado nada.": "Review canceled: nothing was saved.",
        "Guardando el texto…": "Saving the text…",
        ", {n} tabla(s)": ", {n} table(s)",
        " {n} página(s) enderezada(s).": " {n} page(s) straightened.",
        " La página original no se ha tocado.": " The original page wasn't touched.",
        "Texto reconocido en {pages} página(s) ({words} palabras{extra}).": "Text recognized on {pages} page(s) ({words} words{extra}).",
        "Guardado en Descargas: {name}": "Saved in Downloads: {name}",
    },
    "pt": {
        "Buscar una función… (p. ej. «firmar», «formulario», «numerar»)":
            "Buscar uma função… (ex.: «assinar», «formulário», «numerar»)",
        "Sin resultados.": "Sem resultados.",
        "Cambiar a modo claro": "Mudar para o modo claro",
        "Cambiar a modo oscuro": "Mudar para o modo escuro",
        "Abrir provecto.app": "Abrir provecto.app",

        "Combinar y dividir": "Unir e dividir",
        "Comparar": "Comparar",
        "Editar": "Editar",
        "Formato": "Formato",
        "Optimizar": "Otimizar",
        "Texto y conversión": "Texto e conversão",
        "Más": "Mais",

        "Unir": "Unir",
        "Dividir": "Dividir",
        "Organizar páginas": "Organizar páginas",
        "Comparar PDFs": "Comparar PDFs",
        "Numerar páginas": "Numerar páginas",
        "Analizar PDF": "Analisar PDF",
        "Verificar firmas": "Verificar assinaturas",
        "Editor": "Editor",
        "Metadatos": "Metadados",
        "Ajuste de imagen": "Ajuste de imagem",
        "Tamaño y márgenes": "Tamanho e margens",
        "Varias por hoja": "Várias por folha",
        "Comprimir": "Comprimir",
        "Proteger": "Proteger",
        "Marca de agua": "Marca d'água",
        "Invertir colores": "Inverter cores",
        "Aplanar y reparar": "Achatar e reparar",
        "OCR": "OCR",
        "Convertir a PDF": "Converter para PDF",
        "Convertir desde PDF": "Converter a partir de PDF",
        "Workflows": "Workflows",

        "Firmar": "Assinar",
        "Formulario": "Formulário",
        "Sello": "Carimbo",
        "Resaltar texto": "Destacar texto",
        "Dibujar": "Desenhar",
        "Enlace": "Link",
        "Añadir texto": "Adicionar texto",
        "Censurar": "Censurar",
        "Reemplazar texto": "Substituir texto",
        "Copiar texto o tabla": "Copiar texto ou tabela",

        "Pega un enlace a un PDF y pulsa Enter (o arrastra archivos aquí)":
            "Cole um link para um PDF e pressione Enter (ou arraste arquivos aqui)",
        "Añadir archivos": "Adicionar arquivos",
        "Subir PDFs o fotos desde el ordenador": "Enviar PDFs ou fotos do computador",
        "Descargando PDF…": "Baixando PDF…",
        "No se pudo descargar el PDF": "Não foi possível baixar o PDF",
        "Elegir PDFs o fotos": "Escolher PDFs ou fotos",
        "PDF y fotos ({exts})": "PDF e fotos ({exts})",
        "Fotos ({photos})": "Fotos ({photos})",
        "Todos los archivos (*.*)": "Todos os arquivos (*.*)",

        "Guardar como workflow": "Salvar como workflow",
        "Guardar como nuevo": "Salvar como novo",
        "Añadir al workflow": "Adicionar ao workflow",
        "Descartar pasos": "Descartar etapas",
        "Borra la lista de pasos anotados para empezar otro workflow desde cero. No deshace nada en tus archivos.":
            "Apaga a lista de etapas registradas para começar outro workflow do zero. Não desfaz nada nos seus arquivos.",
        "Pasos aplicados:  ": "Etapas aplicadas:  ",
        "guardado  ·  pasos nuevos:  ": "salvo  ·  novas etapas:  ",
        "✓ Guardado como «{name}»  ·  ": "✓ Salvo como «{name}»  ·  ",
        "  Añadir a «{name}»": "  Adicionar a «{name}»",

        "Limpiar todo": "Limpar tudo",
        "Guardar como…": "Salvar como…",
        "  Unir los {n} archivos": "  Unir {n} arquivos",
        "archivo": "arquivo",
        "archivos": "arquivos",
        "página": "página",
        "páginas": "páginas",
        "arrastra las tarjetas para ordenarlas": "arraste os cartões para reordená-los",
        "Arrastra archivos o pega un enlace para empezar": "Arraste arquivos ou cole um link para começar",

        "Idioma": "Idioma",

        # --- ui/pick.py, ui/metadata.py, ui/compare.py ---
        "Elegir archivos…": "Escolher arquivos…",
        "Esta herramienta trabaja sobre un PDF. Súbelo aquí y se abrirá en cuanto esté cargado.":
            "Esta ferramenta trabalha sobre um PDF. Envie-o aqui e ele abrirá assim que for carregado.",
        "Hacen falta al menos {minimum} PDFs. Tienes {have}: añade {falta} más y se abrirá en cuanto estén cargados.":
            "São necessários pelo menos {minimum} PDFs. Você tem {have}: adicione mais {falta} e ele abrirá assim que estiverem carregados.",
        "PDF y fotos": "PDF e fotos",
        "Todos los archivos": "Todos os arquivos",
        "Metadata – Ver / editar / borrar": "Metadados – Ver / editar / excluir",
        "Archivo:": "Arquivo:",
        "Título": "Título",
        "Autor": "Autor",
        "Asunto": "Assunto",
        "Palabras clave": "Palavras-chave",
        "Creador (programa de origen)": "Criador (programa de origem)",
        "Productor (motor que generó el PDF)": "Produtor (mecanismo que gerou o PDF)",
        "Creado: —": "Criado: —",
        "Modificado: —": "Modificado: —",
        "Guardar cambios": "Salvar alterações",
        "Borrar todos los metadatos": "Excluir todos os metadados",
        "Creado: {d}": "Criado: {d}",
        "Modificado: {d}": "Modificado: {d}",
        "✓ {ok_label} en {n} archivo{s}.": "✓ {ok_label} em {n} arquivo{s}.",
        "No se pudo en ningún archivo.": "Não foi possível em nenhum arquivo.",
        " ({n} con error)": " ({n} com erro)",
        "Selecciona un archivo": "Selecione um arquivo",
        "Guardando metadatos…": "Salvando metadados…",
        "Metadatos guardados": "Metadados salvos",
        "Eliminando metadatos…": "Excluindo metadados…",
        "Metadatos eliminados": "Metadados excluídos",
        "Comparar PDFs": "Comparar PDFs",
        "Elige dos PDFs ya subidos (o añade uno nuevo desde el disco) y pulsa «Comparar». Se compara el texto y el aspecto de cada página; no se modifica ninguno de los dos archivos.":
            "Escolha dois PDFs já enviados (ou adicione um novo do disco) e clique em «Comparar». O texto e a aparência de cada página são comparados; nenhum dos dois arquivos é modificado.",
        "Archivo A": "Arquivo A",
        "Archivo B": "Arquivo B",
        "Contraseña:": "Senha:",
        "solo si la tiene": "somente se tiver uma",
        "Comparar": "Comparar",
        "Diferencias": "Diferenças",
        "El texto de la página aparece aquí cuando hay diferencias.": "O texto da página aparece aqui quando há diferenças.",
        "Elegir desde el disco…": "Escolher do disco…",
        "Elige un PDF": "Escolha um PDF",
        "Elige los dos archivos a comparar.": "Escolha os dois arquivos a comparar.",
        "Elige dos archivos distintos.": "Escolha dois arquivos diferentes.",
        "Comparando…": "Comparando…",
        "✓ Son idénticos: {n} páginas, sin ninguna diferencia.": "✓ São idênticos: {n} páginas, sem nenhuma diferença.",
        "{n} distinta(s)": "{n} diferente(s)",
        "{n} añadida(s)": "{n} adicionada(s)",
        "{n} quitada(s)": "{n} removida(s)",
        "A tiene {n_a} páginas, B tiene {n_b}": "A tem {n_a} páginas, B tem {n_b}",
        "Página {n} — {label}": "Página {n} — {label}",
        "Comparación hecha.": "Comparação concluída.",
        "Sin diferencias": "Sem diferenças",
        "No aplica": "Não aplicável",
        "(sin texto)": "(sem texto)",
        "No existe en este archivo": "Não existe neste arquivo",
        "No se puede mostrar": "Não é possível exibir",
        "Igual": "Igual",
        "Diferente": "Diferente",
        "Solo en B (añadida)": "Somente em B (adicionada)",
        "Solo en A (quitada)": "Somente em A (removida)",

        # --- ui/ajuste.py, ui/workflows_ui.py ---
        "Página {n} / {total}": "Página {n} / {total}",
        "Brillo": "Brilho",
        "Contraste": "Contraste",
        "Saturación": "Saturação",
        "Blanco y negro": "Preto e branco",
        "Aplicar a esta página": "Aplicar a esta página",
        "Aplicar a todas las páginas de este PDF": "Aplicar a todas as páginas deste PDF",
        "Cancelar": "Cancelar",
        "No se pudo generar la vista previa": "Não foi possível gerar a pré-visualização",
        "Error": "Erro",
        "No se pudo aplicar el ajuste.": "Não foi possível aplicar o ajuste.",
        "Ajuste de imagen — varios archivos": "Ajuste de imagem — vários arquivos",
        "Navega por las páginas de todos los archivos como en un merge. El ajuste se aplicará a todas las páginas de todos los archivos cargados.":
            "Navegue pelas páginas de todos os arquivos como em uma fusão. O ajuste será aplicado a todas as páginas de todos os arquivos carregados.",
        "Aplicar a todos los archivos": "Aplicar a todos os arquivos",
        "{name} — página {pi}/{total}   ·   ({cur}/{total_all} en total)": "{name} — página {pi}/{total}   ·   ({cur}/{total_all} no total)",
        "Nombre del workflow:": "Nome do workflow:",
        "p.ej. Enviar a cliente": "ex.: Enviar ao cliente",
        "Estos pasos se aplicarán, en orden, a cada archivo que subas («Unir archivos» junta todos en uno). Quita los que no quieras.":
            "Estas etapas serão aplicadas, em ordem, a cada arquivo que você enviar (\"Unir arquivos\" junta todos em um só). Remova as que não quiser.",
        "Subir": "Mover para cima",
        "Bajar": "Mover para baixo",
        "Quitar paso": "Remover etapa",
        "Preguntar al ejecutar": "Perguntar ao executar",
        "Marca lo que cambia en cada archivo: se te pedirá al lanzar el workflow.": "Marque o que muda em cada arquivo: será solicitado ao executar o workflow.",
        "Este paso no tiene valores de texto que preguntar.": "Esta etapa não tem valores de texto para perguntar.",
        "{label}  (valor guardado: «{value}»)": "{label}  (valor salvo: \"{value}\")",
        "Guardar": "Salvar",
        "Falta el nombre": "Falta o nome",
        "Ponle un nombre al workflow.": "Dê um nome ao workflow.",
        "Sin pasos": "Sem etapas",
        "El workflow no tiene ningún paso.": "O workflow não tem nenhuma etapa.",
        "Editar workflow": "Editar workflow",
        "Ejecutar: {name}": "Executar: {name}",
        "Rellena los valores de esta vez:": "Preencha os valores desta vez:",
        "{label}  ·  paso {n}: {step_label}": "{label}  ·  etapa {n}: {step_label}",
        "Ejecutar": "Executar",
        "Falta un valor": "Falta um valor",
        "«{label}» no puede estar vacío.": "\"{label}\" não pode estar vazio.",
        "Secuencias de pasos guardadas. Elige una, sube los archivos y se ejecuta sola. Para crear una: aplica tus herramientas como siempre y pulsa «Guardar como workflow» en la pantalla principal.":
            "Sequências de etapas salvas. Escolha uma, envie os arquivos e ela é executada automaticamente. Para criar uma: aplique suas ferramentas como sempre e toque em \"Salvar como workflow\" na tela principal.",
        "Todavía no hay ningún workflow guardado.": "Ainda não há nenhum workflow salvo.",
        "Editar": "Editar",
        "Borrar": "Excluir",
        "Elige un workflow": "Escolha um workflow",
        "✓ Workflow «{name}» actualizado": "✓ Workflow \"{name}\" atualizado",
        "Borrar workflow": "Excluir workflow",
        "¿Borrar «{name}»?": "Excluir \"{name}\"?",

        # --- ui/organize.py, ui/split.py ---
        "Organize – Gestionar páginas": "Organize – Gerenciar páginas",
        "Arrastra las páginas para reordenarlas · clic derecho o R/Supr para rotar/eliminar": "Arraste as páginas para reordená-las · clique direito ou R/Del para girar/excluir",
        "Rotar 90°": "Girar 90°",
        "Eliminar página": "Excluir página",
        "Organize y guardar en Descargas": "Organizar e salvar em Downloads",
        "No quedan páginas": "Não há páginas restantes",
        "¿Dónde guardar?": "Onde salvar?",
        "¿Cómo quieres guardar los archivos generados?": "Como você quer salvar os arquivos gerados?",
        "En una carpeta": "Em uma pasta",
        "Como archivo .zip": "Como arquivo .zip",
        "Split – Dividir PDF": "Split – Dividir PDF",
        "Cada página en un archivo": "Cada página em um arquivo",
        "Elegir páginas con el ratón": "Escolher páginas com o mouse",
        "Dividir por página de referencia": "Dividir por página de referência",
        "Prefijo + número de página": "Prefixo + número da página",
        "Lista de nombres (una por línea)": "Lista de nomes (um por linha)",
        "Prefijo, p.ej. Pagina_": "Prefixo, ex. Pagina_",
        "Casa\nSilla\nMesa\n…\n(una línea = el nombre de cada página, en orden)": "Casa\nCadeira\nMesa\n…\n(uma linha = o nome de cada página, em ordem)",
        "Dividir en páginas sueltas": "Dividir em páginas separadas",
        "Clic para seleccionar · Ctrl/Shift+clic para varias páginas": "Clique para selecionar · Ctrl/Shift+clique para várias páginas",
        "Guardar selección": "Salvar seleção",
        "Dividir en 2 (seleccionadas / resto)": "Dividir em 2 (selecionadas / resto)",
        "Página de referencia:": "Página de referência:",
        "El primer archivo tendrá las páginas anteriores a la de referencia; el segundo, desde la página de referencia hasta el final.":
            "O primeiro arquivo terá as páginas anteriores à de referência; o segundo, da página de referência até o final.",
        "Pág. {n}": "Pág. {n}",
        "No hay páginas que guardar": "Não há páginas para salvar",
        "Guardado: {name}": "Salvo: {name}",
        "Elegir carpeta destino": "Escolher pasta de destino",
        "{n} archivo(s) guardados en {folder}/": "{n} arquivo(s) salvos em {folder}/",
        "Guardar como ZIP": "Salvar como ZIP",
        "ZIP guardado: {name}": "ZIP salvo: {name}",
        "El PDF no tiene páginas": "O PDF não tem páginas",
        "Faltan nombres": "Faltam nomes",
        "El PDF tiene {total} páginas pero diste menos nombres. A las páginas sin nombre se les asignará 'Pagina_N'.":
            "O PDF tem {total} páginas, mas você deu menos nomes. Às páginas sem nome será atribuído 'Pagina_N'.",
        "Selecciona al menos una página": "Selecione pelo menos uma página",
        "No quedan páginas fuera de la selección": "Não há páginas restantes fora da seleção",
        "Página de referencia fuera de rango": "Página de referência fora do intervalo",

        # --- ui/ocr.py ---
        "Arrastra cada punto a su esquina del papel: mientras arrastras aparece una lupa con una cruz «+». Para afinar, elige un punto y mueve con las flechas del teclado (1 píxel; con Mayús, 5).": "Arraste cada ponto até ao seu canto do papel: enquanto arrasta aparece uma lupa com uma cruz «+». Para ajustar, escolha um ponto e mova com as setas do teclado (1 pixel; com Shift, 5).",
        "Detectar de nuevo": "Detetar de novo",
        "Toda la página": "Página inteira",
        "Aplicar": "Aplicar",
        "Esquinas detectadas: comprueba que cada punto está en su sitio.": "Cantos detetados: verifique se cada ponto está no sítio certo.",
        "No distingo el papel del fondo: colócalas a mano.": "Não consigo distinguir o papel do fundo: coloque-os manualmente.",
        "Enderezar foto": "Endireitar foto",
        "Toda la imagen": "Imagem inteira",
        "Arrastra cada punto a su esquina del papel.": "Arraste cada ponto até ao seu canto do papel.",
        "Formato": "Formato",
        "Automático": "Automático",
        "Carta": "Carta",
        "Como se ve": "Como está",
        "Aclarar fondo y luz": "Clarear fundo e luz",
        "Ver resultado": "Ver resultado",
        "Una hoja arrugada o curvada no se puede aplanar así: usa una foto con el papel plano y bien iluminado.": "Uma folha amarrotada ou curvada não pode ser achatada assim: use uma foto com o papel plano e bem iluminado.",
        "Corregir página": "Corrigir página",
        "He encontrado las esquinas del papel. Comprueba que los cuatro puntos están en su sitio y arrástralos si hace falta.": "Encontrei os cantos do papel. Verifique se os quatro pontos estão no sítio certo e arraste-os se for preciso.",
        "No distingo bien el papel del fondo: arrastra los cuatro puntos a las esquinas de la hoja.": "Não consigo distinguir bem o papel do fundo: arraste os quatro pontos para os cantos da folha.",
        "Línea nueva": "Linha nova",
        "Borrar esta línea": "Apagar esta linha",
        "Añadir una línea nueva debajo": "Adicionar uma linha nova abaixo",
        "Corregido por su posición: el OCR había leído «{val}»": "Corrigido pela sua posição: o OCR tinha lido «{val}»",
        "(línea añadida: no hay original)": "(linha adicionada: não há original)",
        "Revisar el texto reconocido": "Revisar o texto reconhecido",
        "Cada línea tiene el texto reconocido arriba (cada palabra sobre la suya) y la línea original debajo. Corrige las palabras en su sitio: Tab pasa a la siguiente y la palabra original se marca en amarillo. Las palabras que cambias se tiñen de amarillo; las cantidades con el separador corregido por su posición, de azul; las dudosas llevan borde naranja. Con ✕ borras una línea y con ＋ añades otra debajo.": "Cada linha tem o texto reconhecido em cima (cada palavra sobre a sua) e a linha original abaixo. Corrija as palavras no seu lugar: Tab passa à seguinte e a palavra original fica marcada a amarelo. As palavras que mudar ficam amarelas; os valores com o separador corrigido pela posição, azuis; as duvidosas têm borda laranja. Com ✕ apaga uma linha e com ＋ adiciona outra abaixo.",
        "Anterior": "Anterior",
        "Siguiente": "Seguinte",
        "Restaurar el texto leído": "Restaurar o texto lido",
        "PDF con la imagen y el texto detrás (se puede buscar y copiar) — recomendado": "PDF com a imagem e o texto por detrás (pode ser pesquisado e copiado) — recomendado",
        "PDF nuevo redibujado solo con el texto (sin la imagen)": "PDF novo redesenhado apenas com o texto (sem a imagem)",
        "Crea un segundo PDF donde el texto se dibuja a la vista en su posición, con las rayas de las tablas. Sirve para tener el documento limpio y editable. No conserva dibujos, sellos ni fotos.": "Cria um segundo PDF onde o texto é desenhado à vista na sua posição, com as linhas das tabelas. Serve para ter o documento limpo e editável. Não conserva desenhos, selos nem fotos.",
        "Página {n} de {total} (hoja {sheet} del PDF)": "Página {n} de {total} (folha {sheet} do PDF)",
        "línea": "linha",
        "líneas": "linhas",
        "cambiada": "alterada",
        "cambiadas": "alteradas",
        "Sin cambios": "Sem alterações",
        "Marca al menos una de las dos opciones de guardado.": "Marque pelo menos uma das duas opções de gravação.",
        "Detectadas": "Detetados",
        "Manual": "Manual",
        "Sin detectar": "Não detetados",
        "Ya tiene texto · se omite": "Já tem texto · é ignorada",
        "Página {n}": "Página {n}",
        "Pulsa para ajustar las esquinas en grande": "Toque para ajustar os cantos em grande",
        "Ajustar en grande…": "Ajustar em grande…",
        "Detectar esta página": "Detetar esta página",
        "Detectar todas": "Detetar todas",
        "Ver resultado enderezado": "Ver resultado endireitado",
        "Este archivo no se puede previsualizar (tiene contraseña o no hay archivo).": "Este ficheiro não pode ser pré-visualizado (tem palavra-passe ou não há ficheiro).",
        "Cargando páginas…": "A carregar páginas…",
        "Página {n} de {total}": "Página {n} de {total}",
        "{n} detectadas": "{n} detetadas",
        "{n} manual": "{n} manual",
        "{n} sin detectar (solo se endereza el texto)": "{n} não detetadas (só o texto é endireitado)",
        "{n} ya tienen texto (se omiten)": "{n} já têm texto (são ignoradas)",
        "Esquinas detectadas automáticamente. Si algo no encaja, pulsa «Ajustar en grande…».": "Cantos detetados automaticamente. Se algo não encaixar, toque em «Ajustar em grande…».",
        "Esquinas marcadas por ti. «Detectar esta página» vuelve a la detección automática.": "Cantos marcados por si. «Detetar esta página» volta à deteção automática.",
        "No distingo el papel del fondo. Pulsa «Ajustar en grande…» para marcar las esquinas, o déjala así (solo se endereza el texto).": "Não consigo distinguir o papel do fundo. Toque em «Ajustar em grande…» para marcar os cantos, ou deixe assim (só o texto é endireitado).",
        "Esta página ya tiene texto y se deja como está (desmarca «Solo las páginas sin texto» para tratarla).": "Esta página já tem texto e é deixada como está (desmarque «Só as páginas sem texto» para a tratar).",
        "Esquinas · página {n}": "Cantos · página {n}",

        # --- ui/common.py ---
        "¿A qué archivos?": "A quais arquivos?",
        "Tienes {n} archivos subidos. ¿Aplicar esto a todos o solo al elegido ahora{current}?":
            "Você tem {n} arquivos enviados. Aplicar isso a todos ou só ao escolhido agora{current}?",
        "A todos": "A todos",
        "Solo a este": "Só a este",
        "Ha ocurrido un error inesperado: {e}": "Ocorreu um erro inesperado: {e}",

        # --- ui/size_nup.py ---
        "Vista previa · tamaño": "Pré-visualização · tamanho",
        "Cambiar tamaño de página": "Alterar tamanho da página",
        "Ancho:": "Largura:",
        "Alto:": "Altura:",
        "Escalar contenido para llenar la hoja": "Escalar o conteúdo para preencher a folha",
        "Mantener tamaño original y centrar": "Manter o tamanho original e centralizar",
        "Aplicar tamaño": "Aplicar tamanho",
        "Cambiar márgenes": "Alterar margens",
        "Valores positivos añaden margen en blanco en ese borde; valores negativos recortan ese borde de la página.":
            "Valores positivos adicionam margem em branco nessa borda; valores negativos recortam essa borda da página.",
        "Arriba": "Acima",
        "Abajo": "Abaixo",
        "Izquierda": "Esquerda",
        "Derecha": "Direita",
        "Aplicar márgenes": "Aplicar margens",
        "Vista previa · márgenes": "Pré-visualização · margens",
        "No se pudo: {label}.": "Não foi possível: {label}.",
        "Cambiando tamaño…": "Alterando tamanho…",
        "Tamaño aplicado": "Tamanho aplicado",
        "Aplicando márgenes…": "Aplicando margens…",
        "Márgenes aplicados": "Margens aplicadas",
        "N-Up – Varias páginas por hoja": "N-Up – Várias páginas por folha",
        "Hoja": "Folha",
        "Vista previa · hoja de salida": "Pré-visualização · folha de saída",
        "Columnas:": "Colunas:",
        "Filas:": "Linhas:",
        "Tamaño de la hoja de salida:": "Tamanho da folha de saída:",
        "Orientación de la hoja:": "Orientação da folha:",
        "Vertical": "Retrato",
        "Horizontal": "Paisagem",
        "Automática: elige la orientación en la que las páginas salen más grandes":
            "Automática: escolhe a orientação em que as páginas saem maiores",
        "Girar páginas para aprovechar mejor la hoja": "Girar páginas para aproveitar melhor a folha",
        "Si una página llena mejor su celda girada 90°, se gira (útil con documentos de páginas mezcladas)":
            "Se uma página couber melhor em sua célula girada 90°, ela é girada (útil em documentos com páginas de orientações misturadas)",
        "Espacio entre páginas:": "Espaço entre páginas:",
        "Aplicar N-Up": "Aplicar N-Up",
        "= {n} página(s) por hoja": "= {n} página(s) por folha",
        "Auto: ahora {v:.1f} mm (3 mm, reducido hasta 0 si la cuadrícula necesita el sitio)":
            "Automático: agora {v:.1f} mm (3 mm, reduzido até 0 se a grade precisar do espaço)",
        "Se unirán {n_files} archivos en el orden de la lista ({pages} páginas) y después se aplicará N-Up":
            "{n_files} arquivos serão unidos na ordem da lista ({pages} páginas) e depois o N-Up será aplicado",
        "Vista previa · hoja {orient}": "Pré-visualização · folha {orient}",
        "horizontal": "paisagem",
        "vertical": "retrato",
        "✓ N-Up aplicado: {name}": "✓ N-Up aplicado: {name}",
        "No se pudo aplicar N-Up": "Não foi possível aplicar o N-Up",

        # --- ui/widgets.py ---
        "{pages} pág.": "{pages} pág.",
        "Arrastra PDFs o fotos aquí (también texto, HTML, Word…)": "Arraste PDFs ou fotos aqui (também texto, HTML, Word…)",
        "Abrir": "Abrir",
        "Quitar archivo": "Remover arquivo",
        "Volver": "Voltar",

        # --- ui/editor_view.py ---
        "Insertar una página aquí": "Inserir uma página aqui",
        "Borrar esta página": "Excluir esta página",
        "Acercar": "Aproximar",
        "Alejar": "Afastar",
        "Girar a la izquierda": "Girar para a esquerda",
        "Girar a la derecha": "Girar para a direita",
        "Insertar página aquí": "Inserir página aqui",
        "Archivo adjuntado (el clip). Clic en el clip para guardar una copia o quitarlo.": "Arquivo anexado (o clipe). Clique no clipe para salvar uma cópia ou removê-lo.",
        "Elige antes el archivo: Notas → Adjuntar archivo…": "Escolha primeiro o arquivo: Notas → Anexar arquivo…",
        "Campo": "Campo",
        "Este campo es de solo lectura.": "Este campo é somente leitura.",
        "Para firmar, usa el botón Firma.": "Para assinar, use o botão Assinatura.",
        "Este botón no se puede rellenar.": "Este botão não pode ser preenchido.",
        "Arrastra un recuadro más grande para crear el campo.": "Arraste um quadro maior para criar o campo.",
        "Haz clic en un campo para rellenarlo, o arrastra un recuadro para crear uno nuevo.": "Clique em um campo para preenchê-lo, ou arraste um quadro para criar um novo.",
        "Arrastra sobre el texto o el área, o haz clic sobre una imagen o dibujo, para convertirlo en enlace.": "Arraste sobre o texto ou a área, ou clique em uma imagem ou desenho, para transformá-lo em link.",
        "Imagen del PDF seleccionada: pulsa Supr para quitarla de esta página.": "Imagem do PDF selecionada: pressione Delete para removê-la desta página.",
        "Guardar como firma…": "Salvar como assinatura…",
        "Eliminar este dibujo": "Excluir este desenho",
        "Editar este texto": "Editar este texto",
        "Reemplazar «{w}»…": "Substituir «{w}»…",
        "Rellenar / cambiar": "Preencher / alterar",
        "Eliminar campo «{n}»": "Excluir campo «{n}»",
        "Cambiar de icono…": "Trocar ícone…",
        "Girar 15° a la izquierda": "Girar 15° para a esquerda",
        "Girar 15° a la derecha": "Girar 15° para a direita",
        "Duplicar": "Duplicar",
        "Eliminar": "Excluir",
        "No hay ninguna marca ahí.": "Não há nenhuma marcação ali.",
        "Arrastra sobre el texto que quieras marcar.": "Arraste sobre o texto que deseja marcar.",
        "Vista general: has acercado la página {n} para poder editarla.": "Visão geral: você aproximou a página {n} para poder editá-la.",
        "Cuentagotas: haz clic en cualquier punto de la página para tomar su color.": "Conta-gotas: clique em qualquer ponto da página para capturar sua cor.",
        "Esta página está girada: para editarla, vuelve a girarla a su posición original (botones de giro sobre la página).": "Esta página está girada: para editá-la, gire-a de volta à posição original (botões de giro acima da página).",
        "Fuente": "Fonte",
        "Tamaño del texto": "Tamanho do texto",
        "Negrita": "Negrito",
        "Cursiva": "Itálico",
        "Color del texto": "Cor do texto",
        "Borrar este texto": "Excluir este texto",
        "Añadir un elemento debajo (con su etiqueta o viñeta, y renumera los siguientes)": "Adicionar um item abaixo (com seu rótulo ou marcador, renumerando os seguintes)",
        "Buscar fuente…": "Buscar fonte…",
        "Color original": "Cor original",
        "Otro color…": "Outra cor…",
        "Novo elemento": "Novo item",
        "No se pudo añadir el elemento.": "Não foi possível adicionar o item.",
        "Este texto no cabe en la página y se creará una nueva. Marca la cabecera y el pie para no tocarlos y decide cómo se repiten. Si cancelas, el cambio se descarta.": "Este texto não cabe na página e uma nova será criada. Marque o cabeçalho e o rodapé para não alterá-los e decida como se repetem. Se cancelar, a alteração será descartada.",
        "El texto que no cabía pasó a la página {pages}.": "O texto que não cabia foi movido para a página {pages}.",

        # --- ui/editor_parts.py ---
        "Insertar página": "Inserir página",
        "¿Qué quieres insertar aquí?": "O que você quer inserir aqui?",
        "Una página en blanco": "Uma página em branco",
        "Páginas de otro documento (PDF)…": "Páginas de outro documento (PDF)…",
        "Se ha detectado cabecera, pie o fondo de página en este documento.": "Foi detectado cabeçalho, rodapé ou fundo de página neste documento.",
        "Este documento tiene la cabecera y el pie que configuraste.": "Este documento tem o cabeçalho e o rodapé que você configurou.",
        "Mantener cabecera, pie y fondo": "Manter cabeçalho, rodapé e fundo",
        "Hoja totalmente en blanco": "Folha totalmente em branco",
        "Configurar cabecera y pie…": "Configurar cabeçalho e rodapé…",
        "Insertar": "Inserir",
        "Al pulsar «Insertar» elegirás el PDF cuyas páginas se añaden aquí.": "Ao clicar em \"Inserir\" você escolherá o PDF cujas páginas serão adicionadas aqui.",
        "Sin vista previa": "Sem pré-visualização",
        "Elige el PDF a insertar": "Escolha o PDF a inserir",
        "PDF (*.pdf);;Todos los archivos (*.*)": "PDF (*.pdf);;Todos os arquivos (*.*)",
        "Cambiar icono": "Alterar ícone",
        "Icono de «clic aquí»": "Ícone de \"clique aqui\"",
        "Pulsa un icono para cambiarlo al momento; puedes probar varios.": "Clique em um ícone para alterá-lo na hora; você pode testar vários.",
        "El enlace está sobre una imagen. ¿Quieres insertar alguno de estos iconos para indicar a quien lea el PDF que puede hacer clic? Después podrás moverlo y girarlo un poco para que no tape nada.": "O link está sobre uma imagem. Quer inserir um destes ícones para indicar a quem ler o PDF que pode clicar? Depois você poderá movê-lo e girá-lo um pouco para não cobrir nada.",
        "Tu imagen": "Sua imagem",
        "Usar mi propia imagen…": "Usar minha própria imagem…",
        "Importa un PNG, JPG o SVG para usarlo como icono (queda guardado para otros documentos)": "Importe um PNG, JPG ou SVG para usar como ícone (fica salvo para outros documentos)",
        "Cerrar": "Fechar",
        "No, gracias": "Não, obrigado",
        "Elige las imágenes de tus iconos": "Escolha as imagens dos seus ícones",
        "Imágenes e ilustraciones (*.png *.jpg *.jpeg *.svg *.ai *.eps *.pdf *.webp *.gif *.bmp);;Todos (*.*)": "Imagens e ilustrações (*.png *.jpg *.jpeg *.svg *.ai *.eps *.pdf *.webp *.gif *.bmp);;Todos (*.*)",
        "Icono": "Ícone",
        "Cabecera y pie de página": "Cabeçalho e rodapé",
        "Marca con un clic los textos que son cabecera o pie: no se moverán al repartir el texto entre páginas y se podrán repetir en las páginas nuevas.": "Marque com um clique os textos que são cabeçalho ou rodapé: eles não se moverão ao distribuir o texto entre páginas e poderão se repetir nas páginas novas.",
        "Cada clic marca el texto como:": "Cada clique marca o texto como:",
        "Cabecera (azul)": "Cabeçalho (azul)",
        "Pie de página (verde)": "Rodapé (verde)",
        "Repetir la cabecera en las páginas nuevas": "Repetir o cabeçalho nas páginas novas",
        "Repetir el pie en las páginas nuevas": "Repetir o rodapé nas páginas novas",
        "¿Son iguales en todas las páginas?": "São iguais em todas as páginas?",
        "Iguales en todas": "Iguais em todas",
        "Distintos en pares e impares": "Diferentes em pares e ímpares",
        "La página nueva copia la de dos antes, o la anterior si no hay.": "A página nova copia a de duas antes, ou a anterior se não houver.",
        "Seguir la numeración de página": "Seguir a numeração de página",
        "Continuar": "Continuar",
        "Número de página detectado: {nums}. En la página nueva subirá solo.": "Número de página detectado: {nums}. Na página nova ele subirá sozinho.",
        "No se ha detectado ningún número de página en lo marcado.": "Não foi detectado nenhum número de página no que foi marcado.",
        "Copiar texto": "Copiar texto",
        "Texto de la zona": "Texto da área",
        "Unir las líneas de cada párrafo (quita los saltos de línea del escaneo o de la maquetación)": "Unir as linhas de cada parágrafo (remove as quebras de linha da digitalização ou da diagramação)",
        "Tablas a Excel…": "Tabelas para Excel…",
        "Copiar": "Copiar",
        "párrafo": "parágrafo",
        "tabla": "tabela",
        "fila": "linha",
        "suelta": "solta",
        "Se ha reconocido: ": "Foi reconhecido: ",
        "nada de texto": "nenhum texto",
        "Las celdas de tablas y filas van separadas por tabuladores: al pegarlo en Excel o en una tabla de Word cada una cae en su columna.": "As células de tabelas e linhas são separadas por tabulações: ao colar no Excel ou numa tabela do Word, cada uma cai na sua coluna.",
        "Guardar tablas": "Salvar tabelas",
        "Excel (*.xlsx)": "Excel (*.xlsx)",
        "✓ Guardado: {name} ({n} hoja{s}).": "✓ Salvo: {name} ({n} planilha{s}).",
        "No se pudo guardar: {e}": "Não foi possível salvar: {e}",
        "✓ Copiado al portapapeles.": "✓ Copiado para a área de transferência.",
        "Editar nota": "Editar nota",
        "Nueva nota": "Nova nota",
        "Autor: {author}": "Autor: {author}",
        "Eliminar nota": "Excluir nota",
        "Texto (una línea)": "Texto (uma linha)",
        "Texto (varias líneas)": "Texto (várias linhas)",
        "Casilla": "Caixa de seleção",
        "Lista desplegable": "Lista suspensa",
        "Lista de selección": "Lista de seleção",
        "Botones de opción (elegir uno)": "Botões de opção (escolher um)",
        "Nuevo campo": "Novo campo",
        "Nuevo campo de formulario": "Novo campo de formulário",
        "Tipo de campo": "Tipo de campo",
        "Nombre del campo (así se identifica al exportar los datos)": "Nome do campo (assim é identificado ao exportar os dados)",
        "Opciones (una por línea)": "Opções (uma por linha)",
        "Opción 1\nOpción 2\nOpción 3": "Opção 1\nOpção 2\nOpção 3",
        "Valor inicial (opcional)": "Valor inicial (opcional)",
        "Crear campo": "Criar campo",
        "Opciones (una por línea, mínimo 2)": "Opções (uma por linha, mínimo 2)",
        "Azul de hipervínculo": "Azul de hiperlink",
        "Azul oscuro": "Azul escuro",
        "Morado (visitado)": "Roxo (visitado)",
        "Rojo": "Vermelho",
        "Verde": "Verde",
        "Naranja": "Laranja",
        "Negro": "Preto",
        "Editar enlace": "Editar link",
        "Nuevo enlace": "Novo link",
        "Dirección web (o correo electrónico)": "Endereço web (ou e-mail)",
        "https://ejemplo.com  ·  nombre@correo.com": "https://exemplo.com  ·  nome@email.com",
        "Una página de este documento": "Uma página deste documento",
        "Página ": "Página ",
        " de {n}": " de {n}",
        "Poner el texto en azul y subrayarlo, como un hipervínculo": "Deixar o texto azul e sublinhado, como um hiperlink",
        "Color del texto y del subrayado": "Cor do texto e do sublinhado",
        "Este enlace ocupa {n} zonas (líneas): se editan y se quitan juntas.": "Este link ocupa {n} zonas (linhas): são editadas e removidas juntas.",
        "Quitar enlace": "Remover link",
        "Guardar enlace": "Salvar link",
        "Color": "Cor",
        "Color del enlace": "Cor do link",
        "Esa dirección no es válida. Usa una web (https://…), un correo o un teléfono; por seguridad no se admiten otros tipos de enlace.": "Esse endereço não é válido. Use um site (https://…), um e-mail ou um telefone; por segurança, outros tipos de link não são permitidos.",
        "Sin relleno": "Sem preenchimento",
        "Elige un color": "Escolha uma cor",
        "Cuentagotas (tomar de la página)": "Conta-gotas (pegar da página)",
        "Opacidad total": "Opacidade total",
        "Solo el trazo (opcional)": "Só o traço (opcional)",
        "Solo el relleno (opcional)": "Só o preenchimento (opcional)",
        "Color del borde": "Cor da borda",
        "Color de relleno": "Cor de preenchimento",
        "Grosor": "Espessura",
        "Opacidad del relleno": "Opacidade do preenchimento",
        "Forma de la punta de la flecha": "Forma da ponta da flecha",
        "Duplicar (Ctrl+D)": "Duplicar (Ctrl+D)",
        "Borrar (Supr)": "Excluir (Del)",
        "Fino": "Fino",
        "Normal": "Normal",
        "Grueso": "Grosso",
        "Muy grueso": "Muito grosso",
        "Borde": "Borda",
        "Relleno": "Preenchimento",
        "Opacidad {p} %": "Opacidade {p}%",
        "Opacidad {p1}/{p2} %": "Opacidade {p1}/{p2}%",
        "Opacidad total; dentro puedes dar otra solo al trazo o solo al relleno": "Opacidade total; dentro você pode dar uma diferente só para o traço ou só para o preenchimento",
        "Punta": "Ponta",

        # --- ui/edit_page.py ---
        "Fuentes que faltan": "Fontes em falta",
        "Este PDF usa fuentes que no están en tu ordenador. Sin ellas, al editar se usa una "
        "parecida y el texto puede verse algo distinto. Las que publica Google Fonts "
        "(licencia libre) se pueden descargar aquí. Las de Microsoft, Adobe o de pago no.":
            "Este PDF usa fontes que não estão no seu computador. Sem elas, ao editar se usa uma "
            "parecida e o texto pode parecer um pouco diferente. As publicadas pelo Google Fonts "
            "(licença livre) podem ser baixadas aqui. As da Microsoft, Adobe ou pagas não.",
        "«{family}» — comprobando en Google Fonts…": "«{family}» — verificando no Google Fonts…",
        "Buscar la seleccionada en Google Fonts": "Buscar a selecionada no Google Fonts",
        "Instalar solo en este programa (recomendado: no cambia nada en Windows)":
            "Instalar somente neste programa (recomendado: não altera nada no Windows)",
        "Instalar también en Windows (para todos tus programas; solo para tu "
        "usuario, sin permisos de administrador)":
            "Instalar também no Windows (para todos os seus programas; apenas para o seu "
            "usuário, sem permissões de administrador)",
        "Descargar e instalar": "Baixar e instalar",
        "«{family}» — disponible en Google Fonts ({n} estilos)": "«{family}» — disponível no Google Fonts ({n} estilos)",
        "«{family}» — de Microsoft; «{sub}» (Google Fonts) tiene las mismas medidas":
            "«{family}» — da Microsoft; «{sub}» (Google Fonts) tem as mesmas medidas",
        "«{family}» no se puede descargar (es de Microsoft). «{sub}» es una "
        "fuente libre con medidas idénticas: el texto ocupa lo mismo y no se descoloca.":
            "«{family}» não pode ser baixada (é da Microsoft). «{sub}» é uma "
            "fonte livre com medidas idênticas: o texto ocupa o mesmo espaço e não se desloca.",
        "«{family}» — no está en Google Fonts: se usa «Arial» en su lugar. Si quieres usar «{family}», "
        "instálala en Windows (doble clic en el archivo de la fuente → Instalar) y reabre la aplicación.":
            "«{family}» — não está no Google Fonts: usa-se «Arial» em seu lugar. Se quiser usar «{family}», "
            "instale-a no Windows (duplo clique no arquivo da fonte → Instalar) e reabra o aplicativo.",
        "Suele ser una fuente de pago o del sistema, y no se puede descargar de aquí.":
            "Costuma ser uma fonte paga ou do sistema, e não pode ser baixada aqui.",
        "No se pudo conectar con Google Fonts. Comprueba tu conexión a internet.":
            "Não foi possível conectar ao Google Fonts. Verifique sua conexão à internet.",
        "«{family}» — sin conexión": "«{family}» — sem conexão",
        "Marca al menos una fuente.": "Marque pelo menos uma fonte.",
        "Listo: {names} instalada(s). Ya se usarán al editar este PDF.":
            "Pronto: {names} instalada(s). Já serão usadas ao editar este PDF.",
        "  Cerrar": "  Fechar",
        "No se pudo descargar: {msg}": "Não foi possível baixar: {msg}",
        "Descargando «{fam}»: {name} ({i}/{n})": "Baixando «{fam}»: {name} ({i}/{n})",
        "«{fam}» descargada": "«{fam}» baixada",
        "Instalando «{family}» en Windows…": "Instalando «{family}» no Windows…",
        "Edit – Editor visual": "Edit – Editor visual",
        "Clic sobre cualquier texto de la página para editarlo directamente, "
        "sobre la propia página. Enter hace una línea nueva, Ctrl+Enter confirma y Esc cancela. Usa la fuente original del "
        "PDF si la tienes instalada en Windows; si no, avisa y usa una de respaldo.":
            "Clique em qualquer texto da página para editá-lo diretamente, "
            "na própria página. Enter faz uma linha nova, Ctrl+Enter confirma e Esc cancela. Usa a fonte original do "
            "PDF se você a tiver instalada no Windows; caso contrário, avisa e usa uma substituta.",
        "Descargar fuentes…": "Baixar fontes…",
        "Ignorar": "Ignorar",
        "Reiniciar con este documento": "Reiniciar com este documento",
        "Cierra y vuelve a abrir la aplicación con este mismo documento y sus cambios, para "
        "que reconozca una fuente recién instalada":
            "Fecha e reabre o aplicativo com este mesmo documento e suas alterações, para "
            "que reconheça uma fonte recém-instalada",
        "Deshacer (Ctrl+Z)": "Desfazer (Ctrl+Z)",
        "Rehacer (Ctrl+Y)": "Refazer (Ctrl+Y)",
        "Tapar texto con una barra negra": "Cobrir texto com uma barra preta",
        "Reemplazar": "Substituir",
        "Buscar y reemplazar texto": "Buscar e substituir texto",
        "Editar el texto existente: haz clic sobre un texto y cámbialo": "Editar o texto existente: clique em um texto e altere-o",
        "Configurar página": "Configurar página",
        "Marca qué es cabecera y pie de página y cómo se repiten en páginas nuevas":
            "Marque o que é cabeçalho e rodapé e como se repetem em páginas novas",
        "Añadir texto nuevo: haz clic en cualquier punto de la página y escribe":
            "Adicionar texto novo: clique em qualquer ponto da página e escreva",
        "Automático: deduce párrafos, listas, cabecera, pie y numeración, y reparte el texto "
        "entre páginas.\nManual: cada línea se edita por separado y no se mueve nada más.":
            "Automático: deduz parágrafos, listas, cabeçalho, rodapé e numeração, e distribui o texto "
            "entre páginas.\nManual: cada linha é editada separadamente e nada mais se move.",
        "Marcar": "Marcar",
        "Resaltar, subrayar o tachar texto arrastrando sobre él": "Destacar, sublinhar ou riscar texto arrastando sobre ele",
        "Dibujo libre (lápiz, rotulador), rectángulos, elipses, líneas y flechas":
            "Desenho livre (lápis, marcador), retângulos, elipses, linhas e setas",
        "Insertar una imagen, o seleccionar, mover y borrar las que ya hay en el PDF":
            "Inserir uma imagem, ou selecionar, mover e apagar as que já existem no PDF",
        "Firma": "Assinatura",
        "Firmar: dibuja, escribe o usa una imagen; se guarda para volver a usarla":
            "Assinar: desenhe, escreva ou use uma imagem; é salva para reutilizar depois",
        "Convertir un texto, un área, una imagen o un dibujo en un enlace; clic en uno existente para editarlo":
            "Transformar um texto, uma área, uma imagem ou um desenho em link; clique em um existente para editá-lo",
        "Rellenar los campos del PDF, crear campos nuevos o aplanar el formulario":
            "Preencher os campos do PDF, criar campos novos ou achatar o formulário",
        "Notas": "Notas",
        "Notas y comentarios, archivos adjuntos y ocultar las anotaciones": "Notas e comentários, arquivos anexos e ocultar anotações",
        "Copiar texto con sentido: arrastra una zona o haz clic en un párrafo o tabla. "
        "Entiende párrafos, columnas y tablas (también en escaneos)":
            "Copiar texto com sentido: arraste uma zona ou clique em um parágrafo ou tabela. "
            "Entende parágrafos, colunas e tabelas (também em digitalizações)",
        "Sello de texto (APROBADO, RECIBIDO…) con fecha y autor": "Carimbo de texto (APROVADO, RECEBIDO…) com data e autor",
        "Alejar (Ctrl y −, o Ctrl + rueda)": "Diminuir zoom (Ctrl e −, ou Ctrl + roda)",
        "Acercar (Ctrl y +, o Ctrl + rueda)": "Aumentar zoom (Ctrl e +, ou Ctrl + roda)",
        "Ajustar al ancho de la ventana (Ctrl+0)": "Ajustar à largura da janela (Ctrl+0)",
        "Con este panel abierto, clica sobre cualquier fragmento de texto "
        "de la página para taparlo al instante, o clica y arrastra sobre "
        "cualquier área (también fotos o firmas) para censurar justo esa "
        "zona. También puedes buscar un texto exacto aquí abajo. "
        "Esta acción no se puede deshacer.":
            "Com este painel aberto, clique em qualquer trecho de texto "
            "da página para cobri-lo instantaneamente, ou clique e arraste sobre "
            "qualquer área (também fotos ou assinaturas) para censurar exatamente essa "
            "zona. Também é possível buscar um texto exato aqui abaixo. "
            "Esta ação não pode ser desfeita.",
        "O escribe aquí un texto exacto a censurar": "Ou escreva aqui um texto exato a censurar",
        "Censurar texto": "Censurar texto",
        "Buscar y reemplazar": "Buscar e substituir",
        "Reemplazar por (vacío = eliminar)": "Substituir por (vazio = excluir)",
        "Distinguir mayúsculas y minúsculas": "Diferenciar maiúsculas e minúsculas",
        "Reemplaza en todo el documento conservando la fuente, el tamaño y el color. Ctrl+Z lo deshace.":
            "Substitui em todo o documento mantendo a fonte, o tamanho e a cor. Ctrl+Z desfaz.",
        "Este PDF tiene campos de formulario: usa el botón Formulario para rellenarlos.":
            "Este PDF tem campos de formulário: use o botão Formulário para preenchê-los.",
        "Pág. {n} / {total}": "Pág. {n} / {total}",
        "La fuente «{fam}» no está instalada, pero está en Google Fonts: pulsa «Descargar "
        "fuentes…» para instalarla. Mientras tanto se usa «{fb}».":
            "A fonte «{fam}» não está instalada, mas está no Google Fonts: pressione «Baixar "
            "fontes…» para instalá-la. Enquanto isso, usa-se «{fb}».",
        "La fuente «{fam}» no está en Google Fonts (suele ser de pago o de otro programa): se está "
        "usando «{fb}» en su lugar. Si quieres usar «{fam}», descárgala e instálala en Windows "
        "(doble clic en el archivo de la fuente → Instalar) y pulsa «Reiniciar con este documento».":
            "A fonte «{fam}» não está no Google Fonts (costuma ser paga ou de outro programa): está "
            "sendo usada «{fb}» em seu lugar. Se quiser usar «{fam}», baixe-a e instale-a no Windows "
            "(duplo clique no arquivo da fonte → Instalar) e pressione «Reiniciar com este documento».",
        "La fuente «{fam}» no está instalada: se está usando «{fb}» en su lugar. Si quieres usar "
        "«{fam}», instálala en Windows y reabre la aplicación (o mira si está en Google Fonts "
        "con «Descargar fuentes…»).":
            "A fonte «{fam}» não está instalada: está sendo usada «{fb}» em seu lugar. Se quiser usar "
            "«{fam}», instale-a no Windows e reabra o aplicativo (ou veja se está no Google Fonts "
            "com «Baixar fontes…»).",
        "Fuentes instaladas: {names}": "Fontes instaladas: {names}",
        "Añadir página al final": "Adicionar página ao final",
        "Añadir página después de la {n}": "Adicionar página depois da {n}",
        "Añadir página antes de la {n}": "Adicionar página antes da {n}",
        "Girar la página {n} a la derecha": "Girar a página {n} para a direita",
        "Girar la página {n} a la izquierda": "Girar a página {n} para a esquerda",
        "Girar todas las páginas a la derecha": "Girar todas as páginas para a direita",
        "Borrar la página {n}": "Excluir a página {n}",
        "{n} página{s} insertada{s}.": "{n} página{s} inserida{s}.",
        "No se pudo insertar ese PDF (¿tiene contraseña?).": "Não foi possível inserir esse PDF (tem senha?).",
        "Marca la cabecera y el pie de página para copiarlos a la página nueva y decide cómo se numera.":
            "Marque o cabeçalho e o rodapé para copiá-los para a página nova e decida como numerar.",
        "Página añadida (ahora es la {n}).": "Página adicionada (agora é a {n}).",
        "No se pudo añadir la página.": "Não foi possível adicionar a página.",
        "Página girada. Mientras esté girada no se puede editar su contenido; vuelve a girarla "
        "a su posición para hacerlo.":
            "Página girada. Enquanto estiver girada não é possível editar seu conteúdo; gire-a "
            "de volta à posição para fazê-lo.",
        "Páginas giradas.": "Páginas giradas.",
        "No se pudo girar.": "Não foi possível girar.",
        "No se puede borrar la única página del documento.": "Não é possível excluir a única página do documento.",
        "Borrar página": "Excluir página",
        "¿Borrar la página {n} con todo su contenido?\n"
        "Las siguientes se renumeran. Puedes deshacerlo con Ctrl+Z.":
            "Excluir a página {n} com todo o seu conteúdo?\n"
            "As seguintes serão renumeradas. Pode desfazer com Ctrl+Z.",
        "Página {n} borrada.": "Página {n} excluída.",
        "No se pudo borrar la página.": "Não foi possível excluir a página.",
        "Haz clic en la página donde quieras escribir.": "Clique na página onde quiser escrever.",
        "  Marcar": "  Marcar",
        "  Dibujar": "  Desenhar",
        "No se pudo crear el sello.": "Não foi possível criar o carimbo.",
        "el sello": "o carimbo",
        "Arrastra para copiar una zona, o haz clic en un párrafo o una tabla. Esc para salir.":
            "Arraste para copiar uma zona, ou clique em um parágrafo ou uma tabela. Esc para saír.",
        "No se pudo analizar la página: {e}": "Não foi possível analisar a página: {e}",
        "No he encontrado texto en esa página.": "Não encontrei texto nessa página.",
        "Ahí no hay texto. Arrastra para elegir una zona.": "Ali não há texto. Arraste para escolher uma zona.",
        "Esa zona no contiene texto.": "Essa zona não contém texto.",
        "Esta página es una imagen: el texto se ha reconocido ahora mismo (OCR, idioma: {langs}). "
        "Para tenerlo siempre buscable y copiable en cualquier lector, usa Herramientas → OCR.":
            "Esta página é uma imagem: o texto foi reconhecido agora mesmo (OCR, idioma: {langs}). "
            "Para tê-lo sempre pesquisável e copiável em qualquer leitor, use Ferramentas → OCR.",
        "Añadir nota": "Adicionar nota",
        "Adjuntar archivo…": "Anexar arquivo…",
        "Ocultar anotaciones (solo en pantalla)": "Ocultar anotações (somente na tela)",
        "Terminar": "Terminar",
        "Haz clic donde quieras la nota. Clic en una nota para editarla; arrástrala para moverla.":
            "Clique onde quiser a nota. Clique em uma nota para editá-la; arraste-a para movê-la.",
        "No se pudo guardar la nota.": "Não foi possível salvar a nota.",
        "Elige el archivo que quieres adjuntar": "Escolha o arquivo que deseja anexar",
        "Ese archivo pesa más de 25 MB; no se adjunta.": "Esse arquivo tem mais de 25 MB; não será anexado.",
        "Mueve el clip hasta donde quieras ponerlo y haz clic. Esc cancela.":
            "Mova o clipe até onde quiser colocá-lo e clique. Esc cancela.",
        "Guardar una copia de «{name}»…": "Salvar uma cópia de «{name}»…",
        "Quitar adjunto": "Remover anexo",
        "No se pudo leer el adjunto.": "Não foi possível ler o anexo.",
        "Guardar adjunto": "Salvar anexo",
        "Adjunto guardado: {name}. No se abre solo: ábrelo tú si te fías de su origen.":
            "Anexo salvo: {name}. Não abre por conta própria: abra-o você mesmo se confiar na origem.",
        "Haz clic en un campo (recuadro azul) para rellenarlo. Arrastra en un hueco para crear uno nuevo.":
            "Clique em um campo (quadro azul) para preenchê-lo. Arraste em um espaço vazio para criar um novo.",
        "Detectar campos automáticamente…": "Detectar campos automaticamente…",
        "Busca rayas, recuadros vacíos y casillas para convertirlos en campos":
            "Busca linhas, quadros vazios e caixas de seleção para transformá-los em campos",
        "Orden de tabulación": "Ordem de tabulação",
        "Aplanar formulario…": "Achatar formulário…",
        "Convierte los campos rellenados en contenido fijo de la página": "Converte os campos preenchidos em conteúdo fixo da página",
        "Rellenar y crear campos": "Preencher e criar campos",
        "Hay {n} campos (recuadros azules): haz clic en uno para rellenarlo. ":
            "Há {n} campos (quadros azuis): clique em um para preenchê-lo. ",
        "Este PDF no tiene campos. ": "Este PDF não tem campos. ",
        "Arrastra un recuadro vacío para crear uno nuevo; clic derecho "
        "sobre un campo para eliminarlo.":
            "Arraste um quadro vazio para criar um novo; clique com o botão direito "
            "em um campo para excluí-lo.",
        "No encontré rayas, recuadros vacíos ni casillas que convertir en campos.":
            "Não encontrei linhas, quadros vazios nem caixas de seleção para transformar em campos.",
        "Detectar campos": "Detectar campos",
        "He encontrado {total} posibles campos (marcados en verde): {n_text} de texto y {n_chk} casillas.\n\n"
        "Salen de rayas, recuadros vacíos y cuadritos de la página; revisa que no sobre ninguno (puedes borrar "
        "los que no quieras con clic derecho). ¿Crearlos?":
            "Encontrei {total} possíveis campos (marcados em verde): {n_text} de texto e {n_chk} caixas de seleção.\n\n"
            "Vêm de linhas, quadros vazios e pequenos quadrados da página; verifique se não sobra nenhum (pode excluir "
            "os que não quiser com clique direito). Criá-los?",
        "{n} campos creados. Haz clic en uno para rellenarlo.": "{n} campos criados. Clique em um para preenchê-lo.",
        "No se pudo crear ningún campo.": "Não foi possível criar nenhum campo.",
        "Este PDF no tiene campos de formulario.": "Este PDF não tem campos de formulário.",
        "Orden de tabulación: {order} (en {n} página{s}).": "Ordem de tabulação: {order} (em {n} página{s}).",
        "Campo creado.": "Campo criado.",
        "No se pudo crear el campo.": "Não foi possível criar o campo.",
        "Aplanar formulario": "Achatar formulário",
        "Los campos pasarán a ser contenido fijo de la página, con lo que hayas rellenado: "
        "ya no se podrán editar. Puedes deshacerlo con Ctrl+Z hasta que guardes.\n\n"
        "¿Aplanar el formulario?":
            "Os campos passarão a ser conteúdo fixo da página, com o que você tiver preenchido: "
            "não poderão mais ser editados. Pode desfazer com Ctrl+Z até salvar.\n\n"
            "Achatar o formulário?",
        "Formulario aplanado.": "Formulário achatado.",
        "No se pudo aplanar el formulario.": "Não foi possível achatar o formulário.",
        "Arrastra sobre un texto o un área para crear un enlace. Haz clic en un recuadro azul "
        "para editarlo o quitarlo.":
            "Arraste sobre um texto ou uma área para criar um link. Clique em um quadro azul "
            "para editá-lo ou removê-lo.",
        "Enlace quitado.": "Link removido.",
        "Enlace guardado.": "Link salvo.",
        "Enlace creado ({n} zona{s}).": "Link criado ({n} zona{s}).",
        "No se pudo guardar el enlace.": "Não foi possível salvar o link.",
        "No se pudo añadir el icono.": "Não foi possível adicionar o ícone.",
        "Icono añadido. Arrástralo para moverlo; el punto de arriba lo gira (o las teclas [ y ]).":
            "Ícone adicionado. Arraste-o para movê-lo; o ponto de cima o gira (ou as teclas [ e ]).",
        "Insertar una imagen…": "Inserir uma imagem…",
        "Seleccionar, mover o borrar imágenes": "Selecionar, mover ou excluir imagens",
        "Haz clic en una imagen para seleccionarla: arrástrala para moverla, usa los puntos para cambiar "
        "el tamaño y pulsa Supr para borrarla (en las imágenes del PDF, solo borrar). Esc para salir.":
            "Clique em uma imagem para selecioná-la: arraste-a para movê-la, use os pontos para alterar "
            "o tamanho e pressione Delete para excluí-la (nas imagens do PDF, apenas excluir). Esc para saír.",
        "Elige una imagen": "Escolha uma imagem",
        "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;Todos los archivos (*.*)":
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;Todos os arquivos (*.*)",
        "No se pudo leer esa imagen.": "Não foi possível ler essa imagem.",
        "la imagen": "a imagem",
        "Haz clic donde quieras {what} (o arrastra para dibujarle el tamaño). Después puedes "
        "moverla, cambiarle el tamaño por las esquinas (Mayús = deformar) y borrarla con Supr.":
            "Clique onde quiser {what} (ou arraste para desenhar seu tamanho). Depois é possível "
            "movê-la, redimensioná-la pelos cantos (Shift = distorcer) e excluí-la com Delete.",
        "la firma": "a assinatura",
        "Crear firma nueva…": "Criar nova assinatura…",
        "Gestionar mis firmas": "Gerenciar minhas assinaturas",
        "Cambiar el nombre…": "Renomear…",
        "Editar…": "Editar…",
        "Nombre de la firma": "Nome da assinatura",
        "Nombre:": "Nome:",
        "Firma renombrada.": "Assinatura renomeada.",
        "Firma actualizada. Se usará la nueva versión en los documentos siguientes.":
            "Assinatura atualizada. A nova versão será usada nos próximos documentos.",
        "Ese dibujo no se puede guardar como firma.": "Esse desenho não pode ser salvo como assinatura.",
        "Guardar como firma": "Salvar como assinatura",
        "Nombre de la firma:": "Nome da assinatura:",
        "Firma guardada: la tienes en el menú Firma.": "Assinatura salva: você a encontra no menu Assinatura.",
        "No se pudo abrir esa firma.": "Não foi possível abrir essa assinatura.",
        "Borrar firma": "Excluir assinatura",
        "¿Borrar esta firma guardada?": "Excluir esta assinatura salva?",
        "Firma borrada.": "Assinatura excluída.",
        "Seleccionar / mover": "Selecionar / mover",
        "Lápiz libre": "Lápis livre",
        "Rotulador libre": "Marcador livre",
        "Rectángulo": "Retângulo",
        "Elipse": "Elipse",
        "Línea": "Linha",
        "Flecha": "Seta",
        "Color del borde / trazo": "Cor da borda / traço",
        "Color de relleno (rectángulo y elipse)": "Cor de preenchimento (retângulo e elipse)",
        "Grosor: {label}": "Espessura: {label}",
        "Grosor de la línea": "Espessura da linha",
        "Opacidad: total por defecto 100 %; opcionalmente otra para el trazo o el relleno":
            "Opacidade: total por padrão 100%; opcionalmente outra para o traço ou o preenchimento",
        "Forma de la punta de las flechas": "Forma da ponta das setas",
        "Duplicar selección": "Duplicar seleção",
        "Eliminar selección": "Excluir seleção",
        "Relleno (formas)": "Preenchimento (formas)",
        "Terminar de dibujar": "Terminar de desenhar",
        "Clic en una forma o trazo para seleccionarlo: arrastra para mover, puntos blancos para "
        "cambiar el tamaño, Ctrl+D duplica, Supr borra.":
            "Clique em uma forma ou traço para selecioná-lo: arraste para mover, pontos brancos para "
            "alterar o tamanho, Ctrl+D duplica, Delete exclui.",
        "Dibuja con el ratón. Para mover, escalar o duplicar un trazo: «Seleccionar / mover».":
            "Desenhe com o mouse. Para mover, redimensionar ou duplicar um traço: «Selecionar / mover».",
        "Arrastra para dibujar (Mayús para proporción exacta). Para mover, escalar o duplicar "
        "una forma ya dibujada, elige «Seleccionar / mover» o haz clic en su borde.":
            "Arraste para desenhar (Shift para proporção exata). Para mover, redimensionar ou duplicar "
            "uma forma já desenhada, escolha «Selecionar / mover» ou clique na sua borda.",
        "Resaltar": "Destacar",
        "Subrayar": "Sublinhar",
        "Tachar": "Riscar",
        "Quitar marca": "Remover marca",
        "Terminar de marcar": "Terminar de marcar",
        "Haz clic sobre una marca para quitarla.": "Clique em uma marca para removê-la.",
        "Arrastra sobre el texto (o haz clic en una palabra) para marcarlo.": "Arraste sobre o texto (ou clique em uma palavra) para marcá-lo.",
        "Modo manual: cada línea se edita por separado y no se mueve nada más.":
            "Modo manual: cada linha é editada separadamente e nada mais se move.",
        "Modo automático: párrafos, listas, cabecera, pie y numeración.":
            "Modo automático: parágrafos, listas, cabeçalho, rodapé e numeração.",
        "No se pudo guardar el borrador para reiniciar.": "Não foi possível salvar o rascunho para reiniciar.",
        "No se pudo reiniciar la aplicación; ábrela tú y te preguntará si continúas.":
            "Não foi possível reiniciar o aplicativo; abra-o você mesmo e ele perguntará se deseja continuar.",
        "La fuente «{family}» no está instalada: se ha usado «{fb}» en su lugar. Si quieres usar «{family}», "
        "instálala en Windows (doble clic en su archivo → Instalar) y reabre la aplicación.":
            "A fonte «{family}» não está instalada: foi usada «{fb}» em seu lugar. Se quiser usar «{family}», "
            "instale-a no Windows (duplo clique no arquivo → Instalar) e reabra o aplicativo.",
        "Cambios sin guardar": "Alterações não salvas",
        "Tienes cambios sin guardar en este PDF. ¿Guardarlos antes de cambiar de archivo?":
            "Você tem alterações não salvas neste PDF. Salvá-las antes de mudar de arquivo?",
        "No se pudo guardar": "Não foi possível salvar",
        "✓ Guardado: {name} — listo para guardar una copia o seguir con otra herramienta":
            "✓ Salvo: {name} — pronto para salvar uma cópia ou continuar com outra ferramenta",
        "Escribe el texto a censurar": "Escreva o texto a censurar",
        "Censurando…": "Censurando…",
        "✓ Censurado (sin vuelta atrás): {name} — listo para guardar o seguir con otra herramienta":
            "✓ Censurado (sem volta): {name} — pronto para salvar ou continuar com outra ferramenta",
        "No se encontró ese texto en el PDF": "Esse texto não foi encontrado no PDF",
        "Escribe el texto nuevo y pulsa Reemplazar.": "Escreva o texto novo e pressione Substituir.",
        "Escribe el texto a buscar": "Escreva o texto a buscar",
        "El texto nuevo no cabe y se creará una página. Marca la cabecera y el pie para no "
        "tocarlos y decide cómo se repiten. Si cancelas, no se reemplaza nada más.":
            "O texto novo não cabe e uma página será criada. Marque o cabeçalho e o rodapé para não "
            "tocá-los e decida como se repetem. Se cancelar, nada mais será substituído.",
        "No se pudo reemplazar: {e}": "Não foi possível substituir: {e}",
        "Cancelado: no se ha reemplazado nada.": "Cancelado: nada foi substituído.",
        "No se encontró ese texto en el PDF.": "Esse texto não foi encontrado no PDF.",
        "✓ {n} cambio{s1} en {np} página{s2}. Ctrl+Z lo deshace.": "✓ {n} alteração{s1} em {np} página{s2}. Ctrl+Z desfaz.",
        "Texto": "Texto",
        "Imagen": "Imagem",
        "Buscar": "Buscar",

        # --- ui/tools.py ---
        "Herramientas": "Ferramentas",
        "Sin vista previa": "Sem pré-visualização",
        "🔒 Protegido con contraseña": "🔒 Protegido com senha",
        "No se puede mostrar este archivo": "Não é possível exibir este arquivo",
        "No se puede mostrar la página": "Não é possível exibir a página",
        "Página {i} de {n}": "Página {i} de {n}",
        "Arrastra aquí los archivos a convertir\no pulsa «Añadir archivos…»":
            "Arraste aqui os arquivos a converter\nou clique em «Adicionar arquivos…»",
        "Contraseña del PDF:": "Senha do PDF:",
        "solo si lo necesita": "somente se for necessário",
        "Añade un PDF en la pantalla principal para usar esta herramienta.":
            "Adicione um PDF na tela principal para usar esta ferramenta.",
        " · tiene contraseña de apertura": " · tem senha de abertura",
        " · {pages} pág.": " · {pages} pág.",
        "Peso actual: {size}": "Tamanho atual: {size}",
        "Añade primero un PDF en la pantalla principal.": "Adicione primeiro um PDF na tela principal.",
        "Procesando {unit} {i} de {n}…": "Processando {unit} {i} de {n}…",
        "{n} con error: ": "{n} com erro: ",
        "Sin cambios.": "Sem alterações.",
        "Reduce el peso del PDF reescalando las imágenes grandes y limpiando lo que sobra. El texto no cambia.":
            "Reduz o tamanho do PDF redimensionando as imagens grandes e limpando o que sobra. O texto não muda.",
        "Calidad alta (ahorra poco)": "Qualidade alta (economiza pouco)",
        "Equilibrada (recomendada)": "Equilibrada (recomendada)",
        "Máxima compresión (calidad menor)": "Compressão máxima (qualidade menor)",
        "Comprimiendo…": "Comprimindo…",
        "comprimido": "comprimido",
        "Bloquea el PDF con contraseña (cifrado AES-256) o quita la protección de uno que ya tengas. Si olvidas la contraseña, nadie podrá recuperarla: guárdala.":
            "Bloqueia o PDF com senha (criptografia AES-256) ou remove a proteção de um que você já tenha. Se esquecer a senha, ninguém poderá recuperá-la: guarde-a.",
        "Bloquear": "Bloquear",
        "Contraseña para abrirlo (déjala vacía para solo limitar permisos)":
            "Senha para abri-lo (deixe em branco para apenas limitar permissões)",
        "Repite la contraseña": "Repita a senha",
        "Contraseña de propietario para cambiar permisos (opcional)":
            "Senha de proprietário para alterar permissões (opcional)",
        "Permitir a quien lo abra:": "Permitir a quem o abrir:",
        "Imprimir": "Imprimir",
        "Modificar": "Modificar",
        "Anotar y rellenar": "Anotar e preencher",
        "Desbloquear": "Desbloquear",
        "Escribe arriba la «Contraseña del PDF» si hace falta para abrirlo. Úsalo solo con documentos que sean tuyos o que tengas permiso para modificar.":
            "Digite acima a «Senha do PDF» se for necessária para abri-lo. Use isto apenas com documentos que sejam seus ou que você tenha permissão para modificar.",
        "Quitar protección": "Remover proteção",
        "Las dos contraseñas no coinciden.": "As duas senhas não coincidem.",
        "Usa una contraseña de al menos 4 caracteres.": "Use uma senha de pelo menos 4 caracteres.",
        "Ya tenía(n) contraseña: desbloquéalo(s) primero.": "Já tinha(m) senha: desbloqueie-o(s) primeiro.",
        "Protegiendo…": "Protegendo…",
        "protegido": "protegido",
        "{n} ya tenía(n) contraseña: no se han tocado.": "{n} já tinha(m) senha: não foram alterados.",
        "Quitando protección…": "Removendo proteção…",
        "desprotegido": "desprotegido",
        "Añade un texto o una imagen detrás del contenido de las páginas, con transparencia. No tapa nada. Los cambios solo se ven en la vista previa: no se guarda nada hasta pulsar «Añadir marca de agua».":
            "Adiciona um texto ou uma imagem atrás do conteúdo das páginas, com transparência. Não cobre nada. As alterações só aparecem na pré-visualização: nada é salvo até clicar em «Adicionar marca d'água».",
        "CONFIDENCIAL": "CONFIDENCIAL",
        "Elige una imagen (PNG con fondo transparente queda mejor)": "Escolha uma imagem (PNG com fundo transparente fica melhor)",
        "Elegir…": "Escolher…",
        "Gris": "Cinza",
        "Azul": "Azul",
        "Amarillo": "Amarelo",
        "Rosa": "Rosa",
        "Morado": "Roxo",
        "Opacidad": "Opacidade",
        "Repetir (mosaico)": "Repetir (mosaico)",
        "Giro del texto": "Rotação do texto",
        "en mosaico": "em mosaico",
        "Giro de la imagen": "Rotação da imagem",
        "Páginas": "Páginas",
        "todas  ·  ejemplos: 1-3, 5, 8-   ·   pares   ·   impares": "todas  ·  exemplos: 1-3, 5, 8-   ·   pares   ·   ímpares",
        "Añadir marca de agua": "Adicionar marca d'água",
        "Color de la marca de agua": "Cor da marca d'água",
        "Otro color…": "Outra cor…",
        "Imagen de la marca de agua": "Imagem da marca d'água",
        "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)": "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        "Añadiendo marca de agua…": "Adicionando marca d'água…",
        "con marca de agua": "com marca d'água",
        "Añade el número de página. Los cambios solo se ven en la vista previa: no se guarda nada hasta pulsar «Añadir numeración».":
            "Adiciona o número da página. As alterações só aparecem na pré-visualização: nada é salvo até clicar em «Adicionar numeração».",
        "Posición": "Posição",
        "Página {n} de {total}": "Página {n} de {total}",
        "{n} = número de página, {total} = último número. Puedes escribir tu propio formato.":
            "{n} = número da página, {total} = último número. Você pode digitar seu próprio formato.",
        "Empezar en": "Começar em",
        "Tamaño": "Tamanho",
        "Margen": "Margem",
        "Color de la numeración": "Cor da numeração",
        "Añadir numeración": "Adicionar numeração",
        "todas  ·  ejemplos: 2-   (deja la portada sin número)   ·   pares   ·   impares":
            "todas  ·  exemplos: 2-   (deixa a capa sem número)   ·   pares   ·   ímpares",
        "Numerando páginas…": "Numerando páginas…",
        "numerado": "numerado",
        "Pasa el PDF a modo oscuro: fondo oscuro y colores más claros. El texto sigue siendo texto de verdad: se puede seguir buscando y copiando. Los cambios solo se ven en la vista previa: no se guarda nada hasta pulsar «Invertir colores».":
            "Transforma o PDF em modo escuro: fundo escuro e cores mais claras. O texto continua sendo texto de verdade: ainda pode ser buscado e copiado. As alterações só aparecem na pré-visualização: nada é salvo até clicar em «Inverter cores».",
        "Modo": "Modo",
        "Oscuro, conservar colores de las fotos": "Escuro, manter cores das fotos",
        "Invertir todos los colores (como un negativo)": "Inverter todas as cores (como um negativo)",
        "Fondo": "Fundo",
        "No tocar las páginas que ya son oscuras (diapositivas, fotos a página completa…)":
            "Não tocar nas páginas que já são escuras (slides, fotos em página inteira…)",
        "Invirtiendo colores…": "Invertendo cores…",
        "con modo oscuro": "com modo escuro",
        "Aplanar convierte comentarios, dibujos y campos de formulario en contenido fijo (ya no se pueden editar). Reparar reconstruye un PDF dañado o que no se abre bien.":
            "Achatar transforma comentários, desenhos e campos de formulário em conteúdo fixo (não podem mais ser editados). Reparar reconstrói um PDF danificado ou que não abre bem.",
        "Aplanar": "Achatar",
        "Anotaciones (resaltados, dibujos, notas, sellos…)": "Anotações (realces, desenhos, notas, carimbos…)",
        "Campos de formulario (con lo rellenado)": "Campos de formulário (com o que foi preenchido)",
        "Reparar": "Reparar",
        "Reparar PDF": "Reparar PDF",
        "Aplanando…": "Achatando…",
        "aplanado": "achatado",
        "Reparando…": "Reparando…",
        "revisado": "verificado",
        "Convierte imágenes, texto, Markdown, HTML y otros formatos a PDF. Word, Excel y PowerPoint necesitan Office o LibreOffice instalados. Formatos: {exts}":
            "Converte imagens, texto, Markdown, HTML e outros formatos para PDF. Word, Excel e PowerPoint precisam do Office ou do LibreOffice instalado. Formatos: {exts}",
        "No encuentro Office ni LibreOffice: los archivos de Word, Excel o PowerPoint no se podrán convertir hasta que instales uno de los dos. Las imágenes, el texto y el HTML sí funcionan igual.":
            "Não encontro o Office nem o LibreOffice: os arquivos do Word, Excel ou PowerPoint não poderão ser convertidos até você instalar um dos dois. Imagens, texto e HTML funcionam normalmente.",
        "Instalar LibreOffice…": "Instalar LibreOffice…",
        "Ya lo instalé: comprobar": "Já instalei: verificar",
        "Añadir archivos…": "Adicionar arquivos…",
        "Quitar": "Remover",
        "Imágenes en página:": "Imagens na página:",
        "Convertir": "Converter",
        "Todos los compatibles ({exts})": "Todos os compatíveis ({exts})",
        "Archivos a convertir": "Arquivos para converter",
        "Añade al menos un archivo.": "Adicione pelo menos um arquivo.",
        "{n} PDF creado(s) (están en la lista y en Descargas).": "{n} PDF(s) criado(s) (estão na lista e em Downloads).",
        "No se pudo: ": "Não foi possível: ",
        "Convirtiendo…": "Convertendo…",
        "Ya puedes convertir Word, Excel y PowerPoint.": "Agora você já pode converter Word, Excel e PowerPoint.",
        "Sigo sin encontrar Office ni LibreOffice.": "Continuo sem encontrar o Office ou o LibreOffice.",
        "Se descargará el instalador oficial de LibreOffice {version} para Windows\n«{filename}», unos {size_mb:.0f} MB\ndesde download.documentfoundation.org.\n\nDespués se abrirá su propio instalador: tú decides si seguir, aceptas sus condiciones y lo instalas (con el permiso de Windows si lo pide). El programa no instala nada por su cuenta.":
            "O instalador oficial do LibreOffice {version} para Windows será baixado\n«{filename}», cerca de {size_mb:.0f} MB\nde download.documentfoundation.org.\n\nDepois será aberto o seu próprio instalador: você decide se continua, aceita os termos e o instala (com a permissão do Windows, se solicitado). O programa não instala nada por conta própria.",
        "Instalar LibreOffice": "Instalar LibreOffice",
        "Descargando LibreOffice…": "Baixando LibreOffice…",
        "Descargando LibreOffice… {done:.0f} / {total:.0f} MB": "Baixando LibreOffice… {done:.0f} / {total:.0f} MB",
        "Se descargó, pero no se pudo abrir el instalador. Ábrelo a mano.":
            "Foi baixado, mas não foi possível abrir o instalador. Abra-o manualmente.",
        "Se ha abierto el instalador de LibreOffice. Cuando termines, vuelve aquí y pulsa «Ya lo instalé: comprobar».":
            "O instalador do LibreOffice foi aberto. Quando terminar, volte aqui e clique em «Já instalei: verificar».",
        "Exporta el PDF elegido a otro formato. El PDF original no se modifica; el resultado se guarda en Descargas.":
            "Exporta o PDF escolhido para outro formato. O PDF original não é modificado; o resultado é salvo em Downloads.",
        "Formato de salida": "Formato de saída",
        "Calidad": "Qualidade",
        "Normal (100 ppp)": "Normal (100 ppp)",
        "Alta (150 ppp)": "Alta (150 ppp)",
        "Muy alta (300 ppp)": "Muito alta (300 ppp)",
        "Una imagen por página, con transparencia donde la hubiera.": "Uma imagem por página, com transparência onde houver.",
        "Una imagen por página, más ligeras pero sin transparencia.": "Uma imagem por página, mais leve, mas sem transparência.",
        "El texto que ya tiene el PDF. Si es un escaneo sin OCR previo, no saldrá nada: pásalo antes por OCR.":
            "O texto que o PDF já tem. Se for um escaneamento sem OCR prévio, não sairá nada: passe-o antes pelo OCR.",
        "El texto de cada página, colocado tal como está en el PDF.": "O texto de cada página, colocado tal como está no PDF.",
        "Sale editable, pero no es una copia exacta: tablas, columnas y fuentes pueden no coincidir del todo con el original.":
            "Sai editável, mas não é uma cópia exata: tabelas, colunas e fontes podem não corresponder totalmente ao original.",
        "convertido (en Descargas)": "convertido (em Downloads)",
        "Examina el PDF elegido: versión, páginas, metadatos, cifrado y permisos, fuentes, imágenes, formulario, marcadores y si tiene firma digital. No lo modifica ni lo guarda.":
            "Examina o PDF escolhido: versão, páginas, metadados, criptografia e permissões, fontes, imagens, formulário, marcadores e se tem assinatura digital. Não o modifica nem o salva.",
        "Analizar": "Analisar",
        "Pulsa «Analizar» para ver la información del PDF elegido.": "Clique em «Analisar» para ver as informações do PDF escolhido.",
        "No se ha podido analizar: {err}": "Não foi possível analisar: {err}",
        "Analizado(s) {n} archivo(s).": "Analisado(s) {n} arquivo(s).",
        "Analizando…": "Analisando…",
        "Archivo: {name}  ({size})": "Arquivo: {name}  ({size})",
        "Versión: {v}": "Versão: {v}",
        "Páginas: {n}": "Páginas: {n}",
        "  • {n} página(s) de {w} × {h} pt ({orientation})": "  • {n} página(s) de {w} × {h} pt ({orientation})",
        "Metadatos:": "Metadados:",
        "Programa de creación": "Programa de criação",
        "Productor": "Produtor",
        "Creado": "Criado",
        "Modificado": "Modificado",
        "(sin metadatos)": "(sem metadados)",
        "Seguridad:": "Segurança:",
        "Necesita contraseña para abrirse: {v}": "Precisa de senha para abrir: {v}",
        "sí": "sim",
        "no": "não",
        "Cifrado: {v}": "Criptografado: {v}",
        "Permite: {v}": "Permite: {v}",
        "nada": "nada",
        "Firma digital: {v}": "Assinatura digital: {v}",
        "sí tiene (usa «Verificar firmas» para comprobarla)": "sim, tem (use «Verificar assinaturas» para verificá-la)",
        "no tiene": "não tem",
        "Fuentes ({n}):": "Fontes ({n}):",
        "incrustada": "incorporada",
        "no incrustada": "não incorporada",
        "Imágenes: {n}": "Imagens: {n}",
        "Formulario: {v}": "Formulário: {v}",
        "sí, con {n} campo(s)": "sim, com {n} campo(s)",
        "Marcadores: {n}": "Marcadores: {n}",
        "Comprueba las firmas digitales del PDF elegido: quién firmó, cuándo y si el documento se modificó después de firmarlo. No comprueba si el certificado es de una entidad de confianza (no dice si la firma es «cualificada» en el sentido legal), solo si el documento está intacto.":
            "Verifica as assinaturas digitais do PDF escolhido: quem assinou, quando e se o documento foi modificado depois de assinado. Não verifica se o certificado pertence a uma entidade confiável (não diz se a assinatura é «qualificada» no sentido legal), apenas se o documento está intacto.",
        "Comprobar firmas": "Verificar assinaturas",
        "Pulsa «Comprobar firmas» para ver las firmas del PDF elegido.": "Clique em «Verificar assinaturas» para ver as assinaturas do PDF escolhido.",
        "No se ha podido comprobar: {err}": "Não foi possível verificar: {err}",
        "Firmas comprobadas.": "Assinaturas verificadas.",
        "Alguna firma indica que un documento se modificó después.": "Uma assinatura indica que o documento foi modificado depois.",
        "Comprobando firmas…": "Verificando assinaturas…",
        "Este PDF no tiene ninguna firma digital.": "Este PDF não tem nenhuma assinatura digital.",
        "{n} firma(s) encontrada(s):\n": "{n} assinatura(s) encontrada(s):\n",
        "— Firma {i}: campo «{field}»": "— Assinatura {i}: campo «{field}»",
        "Firmante (según el certificado): {v}": "Signatário (segundo o certificado): {v}",
        "Emitido por: {v}": "Emitido por: {v}",
        "Fecha de firma: {v}": "Data da assinatura: {v}",
        "(no indicada)": "(não indicada)",
        "Firma íntegra (no se ha tocado desde que se firmó): {v}": "Assinatura íntegra (não foi alterada desde que foi assinada): {v}",
        "NO — el documento se modificó después de esta firma": "NÃO — o documento foi modificado depois desta assinatura",
        "Aviso: esta firma no cubre todo el archivo (hay contenido añadido después, p. ej. otra firma posterior).":
            "Aviso: esta assinatura não cobre todo o arquivo (há conteúdo adicionado depois, por exemplo, outra assinatura posterior).",
        "Qué cambió después: {v}": "O que mudou depois: {v}",
        "ninguna (igual que cuando se firmó)": "nenhuma (igual a quando foi assinado)",
        "se rellenaron campos de formulario": "campos de formulário foram preenchidos",
        "se añadieron anotaciones": "anotações foram adicionadas",
        "sí, se modificó el contenido": "sim, o conteúdo foi modificado",
        "Nota: esto comprueba que el documento no se ha tocado desde que se firmó, pero no comprueba si el certificado pertenece de verdad a quien dice ser (para eso haría falta la lista de entidades de confianza de la UE, que no está incluida). No es una comprobación de validez legal ni dice si la firma es «cualificada».":
            "Nota: isto verifica que o documento não foi alterado desde que foi assinado, mas não verifica se o certificado realmente pertence a quem diz ser (para isso seria necessária a lista de entidades confiáveis da UE, que não está incluída). Não é uma verificação de validade legal nem diz se a assinatura é «qualificada».",
        "Reconoce el texto de un PDF escaneado (o hecho de imágenes) y lo añade de forma invisible: ya se puede buscar y copiar. Si la página es una foto torcida, puede enderezarla antes en el mismo paso. Funciona sin internet; los idiomas son archivos pequeños que se instalan una vez.":
            "Reconhece o texto de um PDF escaneado (ou feito de imagens) e o adiciona de forma invisível: já pode ser buscado e copiado. Se a página for uma foto torta, pode endireitá-la antes, na mesma etapa. Funciona sem internet; os idiomas são arquivos pequenos instalados uma vez.",
        "Motor": "Motor",
        "RapidOCR · recomendado": "RapidOCR · recomendado",
        "Tesseract · rápido": "Tesseract · rápido",
        "RapidOCR no está instalado: pip install rapidocr": "O RapidOCR não está instalado: pip install rapidocr",
        "RapidOCR usa redes neuronales (sin internet, gratis) y lee mucho mejor las fotos borrosas o pequeñas. Tesseract es más rápido y va bien con escaneos limpios.":
            "O RapidOCR usa redes neurais (sem internet, gratuito) e lê muito melhor fotos borradas ou pequenas. O Tesseract é mais rápido e funciona bem com escaneamentos limpos.",
        "Idiomas del documento:": "Idiomas do documento:",
        "Solo las páginas sin texto": "Somente as páginas sem texto",
        "Máxima precisión": "Precisão máxima",
        "Usa datos de idioma de alta precisión (tessdata_best, unos 15 MB por idioma, se descargan una vez). Más lento, pero lee mucho mejor el texto borroso o de baja resolución.":
            "Usa dados de idioma de alta precisão (tessdata_best, cerca de 15 MB por idioma, baixados uma vez). Mais lento, mas lê muito melhor o texto borrado ou de baixa resolução.",
        "Revisar el texto antes de guardar": "Revisar o texto antes de salvar",
        "Tras leer, se abre una vista para comparar el texto con la página y corregirlo. Desde ahí también puedes crear un PDF nuevo redibujado con el texto.":
            "Após a leitura, abre-se uma visualização para comparar o texto com a página e corrigi-lo. A partir daí também é possível criar um novo PDF redesenhado com o texto.",
        "Enderezar las páginas torcidas": "Endireitar páginas tortas",
        "Busca solo el papel, corrige la perspectiva y gira la página hasta que las líneas de texto queden horizontales (se guía por la base de las letras). Las páginas que ya están rectas no se tocan. Sirve para papel plano: una hoja arrugada no se aplana.":
            "Procura apenas o papel, corrige a perspectiva e gira a página até que as linhas de texto fiquem horizontais (guiando-se pela base das letras). As páginas que já estão retas não são alteradas. Serve para papel plano: uma folha amassada não é achatada.",
        "Reconocer texto": "Reconhecer texto",
        "¿Otro idioma?": "Outro idioma?",
        "Descargar otro idioma…": "Baixar outro idioma…",
        "Instalar idioma": "Instalar idioma",
        "Se descargará el idioma «{name}» ({code}.traineddata, unos 1–10 MB) del repositorio oficial de Tesseract (github.com/tesseract-ocr/tessdata_fast) y se guardará en tu carpeta de datos del programa.\n\n¿Descargarlo?":
            "O idioma «{name}» ({code}.traineddata, cerca de 1–10 MB) será baixado do repositório oficial do Tesseract (github.com/tesseract-ocr/tessdata_fast) e salvo na pasta de dados do programa.\n\nBaixar?",
        "Idioma «{name}» instalado.": "Idioma «{name}» instalado.",
        "Descargando «{name}»…": "Baixando «{name}»…",
        "Español": "Espanhol", "Portugués": "Português", "Inglés": "Inglês", "Francés": "Francês",
        "Alemán": "Alemão", "Italiano": "Italiano", "Catalán": "Catalão", "Gallego": "Galego",
        "Euskera": "Basco", "Neerlandés": "Holandês", "Danés": "Dinamarquês", "Noruego": "Norueguês",
        "Sueco": "Sueco", "Finés": "Finlandês", "Polaco": "Polonês", "Checo": "Tcheco",
        "Eslovaco": "Eslovaco", "Esloveno": "Esloveno", "Húngaro": "Húngaro", "Rumano": "Romeno",
        "Búlgaro": "Búlgaro", "Croata": "Croata", "Serbio": "Sérvio", "Griego": "Grego",
        "Turco": "Turco", "Ruso": "Russo", "Ucraniano": "Ucraniano", "Hebreo": "Hebraico",
        "Árabe": "Árabe", "Hindi": "Hindi", "Chino simplificado": "Chinês simplificado",
        "Chino tradicional": "Chinês tradicional", "Japonés": "Japonês", "Coreano": "Coreano",
        "Tailandés": "Tailandês", "Vietnamita": "Vietnamita", "Indonesio": "Indonésio", "Latín": "Latim",
        "Lee bien fotos, escaneos borrosos y papel torcido. Detecta solo el idioma (alfabeto latino): no hace falta elegirlo. Es algo más lento.":
            "Lê bem fotos, escaneamentos borrados e papel torto. Detecta apenas o idioma (alfabeto latino): não é preciso escolhê-lo. É um pouco mais lento.",
        "Muy rápido y va bien con escaneos limpios y rectos. Elige abajo el idioma del documento; para fotos o texto borroso usa RapidOCR.":
            "Muito rápido e funciona bem com escaneamentos limpos e retos. Escolha abaixo o idioma do documento; para fotos ou texto borrado use o RapidOCR.",
        "Marca al menos un idioma (o instala uno de la lista).": "Marque pelo menos um idioma (ou instale um da lista).",
        "Descargar datos de alta precisión": "Baixar dados de alta precisão",
        "Para la máxima precisión se descargará, una sola vez: {names}.\n\nOrigen: github.com/tesseract-ocr/tessdata_best (repositorio oficial de Tesseract). Unos 15 MB por idioma (el de inglés pesa 15 MB). Se guardan en tu carpeta de datos del programa.\n\n¿Descargarlos?":
            "Para a máxima precisão, será baixado uma única vez: {names}.\n\nOrigem: github.com/tesseract-ocr/tessdata_best (repositório oficial do Tesseract). Cerca de 15 MB por idioma (o de inglês pesa 15 MB). São salvos na pasta de dados do programa.\n\nBaixar?",
        " También: {name}.": " Também: {name}.",
        "Texto guardado en {pages} página(s) ({words} palabras).": "Texto salvo em {pages} página(s) ({words} palavras).",
        "Guardando…": "Salvando…",
        "Revisión cancelada: no se ha guardado nada.": "Revisão cancelada: nada foi salvo.",
        "Guardando el texto…": "Salvando o texto…",
        ", {n} tabla(s)": ", {n} tabela(s)",
        " {n} página(s) enderezada(s).": " {n} página(s) endireitada(s).",
        " La página original no se ha tocado.": " A página original não foi alterada.",
        "Texto reconocido en {pages} página(s) ({words} palabras{extra}).": "Texto reconhecido em {pages} página(s) ({words} palavras{extra}).",
        "Guardado en Descargas: {name}": "Salvo em Downloads: {name}",
    },
}


LANG = load_lang()


def tr(key: str, **kwargs) -> str:
    template = TR.get(LANG, {}).get(key, key)
    return template.format(**kwargs) if kwargs else template
