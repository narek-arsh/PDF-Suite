import flet as ft
import os
import tempfile
import threading
import requests
import base64
import math
import pdfplumber
import re
from pathlib import Path
from datetime import datetime
from pypdf import PdfReader, PdfWriter

try:
    import fitz  # pip install pymupdf
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

DOWNLOADS = Path.home() / "Downloads"
DOWNLOADS.mkdir(exist_ok=True)

FILE_COLORS = [
    "#E53935", "#8E24AA", "#1E88E5", "#00897B",
    "#F4511E", "#6D4C41", "#039BE5", "#43A047",
]

_thumb_cache: dict = {}


def label_for(fi: int, pi: int) -> str:
    return f"{chr(65 + fi)}{pi + 1}"


def safe_page_count(path: str) -> int:
    try:
        return len(PdfReader(path).pages)
    except Exception:
        return 0


def get_page_thumbnail(file_path: str, page_idx: int, rotation: int = 0, width: int = 105) -> str | None:
    if not HAS_FITZ:
        return None
    key = (file_path, page_idx, rotation)
    if key in _thumb_cache:
        return _thumb_cache[key]
    try:
        doc = fitz.open(file_path)
        pg = doc[page_idx]
        rect = pg.rect
        scale = width / (rect.height if rotation in (90, 270) else rect.width) if rect.width > 0 else 1
        mat = fitz.Matrix(scale, scale).prerotate(rotation)
        pix = pg.get_pixmap(matrix=mat)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        _thumb_cache[key] = img_b64
        doc.close()
        return img_b64
    except Exception:
        return None


def download_pdf_from_url(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 200 and ("pdf" in ct.lower() or url.lower().endswith(".pdf")):
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.write(r.content)
            tmp.flush()
            return tmp.name
    except Exception:
        pass
    return None


# ── Ordenar Renfe logic (from Ordenar_Renfe.py) ──────────────────────────────
def _renfe_sort_pdf(ruta: str, out_stem: str | None = None) -> str | None:
    """
    Ordena las páginas de un PDF de billetes Renfe por fecha y DNI.
    out_stem: nombre base para el archivo de salida (sin extension).
              Si es None usa el stem de ruta.
    Devuelve la ruta del PDF ordenado, o None si falla.
    Nunca lanza excepcion.
    """
    datos_paginas = []
    try:
        with pdfplumber.open(ruta) as pdf:
            for i, pagina in enumerate(pdf.pages):
                try:
                    texto = pagina.extract_text() or ""
                except Exception:
                    texto = ""

                match_dni   = re.search(r'DNI ó DOC\.ID:\s*(\S+)', texto)
                dni         = match_dni.group(1) if match_dni else "Z_DESCONOCIDO"

                match_fecha = re.search(r'Origen:.*?(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', texto)
                if match_fecha:
                    try:
                        fecha = datetime.strptime(match_fecha.group(1), "%d/%m/%Y %H:%M")
                    except ValueError:
                        fecha = datetime.max
                else:
                    fecha = datetime.max

                datos_paginas.append({"num_original": i, "dni": dni, "fecha": fecha})
    except Exception:
        return None

    if not datos_paginas:
        return None

    datos_paginas.sort(key=lambda x: (x["fecha"], x["dni"]))

    try:
        reader   = PdfReader(ruta)
        writer   = PdfWriter()
        for p in datos_paginas:
            writer.add_page(reader.pages[p["num_original"]])

        base     = out_stem if out_stem else Path(ruta).stem
        out_path = DOWNLOADS / f"{base}_ordenado.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)
    except Exception:
        return None


# ── CENSURA / BUSCAR Y REEMPLAZAR ───────────────────────────────────────────
def censor_text_in_pdf(path: str, texto: str) -> str | None:
    """
    Busca 'texto' en todas las páginas y lo cubre con una caja negra sólida
    del tamaño exacto de la zona de texto (no un carácter por █, sino el
    área completa en píxeles). Elimina el texto subyacente: censura
    permanente, sin posibilidad de deshacer una vez guardado el PDF.
    Devuelve la ruta del PDF censurado o None si no se encontró nada / error.
    """
    if not HAS_FITZ or not texto.strip():
        return None
    try:
        doc = fitz.open(path)
        encontrado = False
        for page in doc:
            rects = page.search_for(texto)
            for r in rects:
                pad = fitz.Rect(r.x0 - 1.5, r.y0 - 1.5, r.x1 + 1.5, r.y1 + 1.5)
                page.add_redact_annot(pad, fill=(0, 0, 0))
                encontrado = True
            if rects:
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        if not encontrado:
            doc.close()
            return None
        stem = Path(path).stem
        out_path = DOWNLOADS / f"{stem}_censurado.pdf"
        doc.save(str(out_path), deflate=True, garbage=4)
        doc.close()
        return str(out_path)
    except Exception:
        return None


def find_replace_in_pdf(path: str, buscar: str, reemplazar: str) -> str | None:
    """
    Busca 'buscar' en todas las páginas y lo sustituye por 'reemplazar' en la
    misma posición. Si 'reemplazar' está vacío, simplemente elimina el texto
    encontrado. Devuelve la ruta del PDF resultante o None si no hubo coincidencias.
    """
    if not HAS_FITZ or not buscar.strip():
        return None
    try:
        doc = fitz.open(path)
        encontrado = False
        for page in doc:
            rects = page.search_for(buscar)
            if not rects:
                continue
            encontrado = True
            info = [(r, r.y1 - r.y0) for r in rects]
            for r in rects:
                page.add_redact_annot(r, fill=False)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            if reemplazar:
                for r, alto in info:
                    size = max(6.0, min(alto * 0.8, 14.0))
                    pos = fitz.Point(r.x0, r.y1 - 1)
                    try:
                        page.insert_text(pos, reemplazar, fontsize=size,
                                          color=(0, 0, 0), fontname="helv")
                    except Exception:
                        pass
        if not encontrado:
            doc.close()
            return None
        stem = Path(path).stem
        out_path = DOWNLOADS / f"{stem}_reemplazado.pdf"
        doc.save(str(out_path), deflate=True, garbage=4)
        doc.close()
        return str(out_path)
    except Exception:
        return None


# ── METADATOS ────────────────────────────────────────────────────────────
def read_metadata(path: str) -> dict:
    """Devuelve los metadatos legibles del PDF (claves básicas)."""
    if not HAS_FITZ:
        return {}
    try:
        doc = fitz.open(path)
        meta = dict(doc.metadata or {})
        doc.close()
        return meta
    except Exception:
        return {}


def write_metadata(path: str, meta: dict) -> str | None:
    """Escribe los metadatos indicados (título, autor, asunto, palabras clave)
    sobre el PDF y guarda una copia nueva. Las claves no indicadas se
    conservan tal cual estaban."""
    if not HAS_FITZ:
        return None
    try:
        doc = fitz.open(path)
        actual = dict(doc.metadata or {})
        actual.update(meta)
        doc.set_metadata(actual)
        stem = Path(path).stem
        out_path = DOWNLOADS / f"{stem}_metadatos.pdf"
        doc.save(str(out_path), deflate=True, garbage=4)
        doc.close()
        return str(out_path)
    except Exception:
        return None


def clear_metadata(path: str) -> str | None:
    """Borra por completo todos los metadatos del PDF y guarda una copia nueva."""
    if not HAS_FITZ:
        return None
    try:
        doc = fitz.open(path)
        doc.set_metadata({})
        try:
            doc.del_xml_metadata()
        except Exception:
            pass
        stem = Path(path).stem
        out_path = DOWNLOADS / f"{stem}_sin_metadatos.pdf"
        doc.save(str(out_path), deflate=True, garbage=4)
        doc.close()
        return str(out_path)
    except Exception:
        return None


# ── DIVIDIR PDF ──────────────────────────────────────────────────────────
def split_pdf(path: str, n: int, label: str = "parte") -> list[str]:
    """
    Divide el PDF en bloques de n páginas (n=1 => cada página en un archivo
    individual). Guarda los archivos en Descargas/<nombre>_dividido/ y
    devuelve la lista de rutas generadas.
    """
    try:
        reader = PdfReader(path)
        total  = len(reader.pages)
        if total == 0 or n <= 0:
            return []
        stem    = Path(path).stem
        out_dir = DOWNLOADS / f"{stem}_dividido"
        out_dir.mkdir(exist_ok=True)
        outputs = []
        parte   = 1
        for start in range(0, total, n):
            writer = PdfWriter()
            for p in reader.pages[start:start + n]:
                writer.add_page(p)
            out_path = out_dir / f"{stem}_{label}{parte}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            outputs.append(str(out_path))
            parte += 1
        return outputs
    except Exception:
        return []


def _resource(relative: str) -> str:
    """Devuelve la ruta correcta tanto en .py como en .exe (PyInstaller)."""
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base / relative)


def main(page: ft.Page):
    page.title = "PDF Manager – Travel Agent"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#1a1a2e"
    page.window.width = 1000
    page.window.height = 780
    page.window.icon = _resource("icono.ico")
    page.padding = 0

    uploaded_files: list[dict] = []
    org_pages:      list[dict] = []
    merge_order:    list[int]  = []
    fasten_flag:   list[bool] = [False]   # [0] = checkbox Print
    dpi_value:     list[int]  = [300]     # [0] = DPI seleccionado para Print
    ajuste_flag:   list[bool] = [False]   # [0] = checkbox Ajuste B&N

    def snack(msg: str, color="#43A047"):
        page.snack_bar = ft.SnackBar(ft.Text(msg, color="white"), bgcolor=color, duration=3000)
        page.snack_bar.open = True
        page.update()

    # ── FILE PICKERS ──────────────────────────────────────────────────────────
    def pick_files_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        for f in e.files:
            _add_file(f.path, f.name)

    def on_save_merge_result(e: ft.FilePickerResultEvent):
        if e.path and hasattr(page, "_merge_writer"):
            with open(e.path, "wb") as f:
                page._merge_writer.write(f)
            if fasten_flag[0] or ajuste_flag[0]:
                def _sma_pipeline(p=e.path):
                    _apply_pipeline_sync(p, delete_input=True)
                threading.Thread(target=_sma_pipeline, daemon=True).start()
            else:
                snack(f"✓ Guardado: {Path(e.path).name}")
            reset_and_go_home()

    def on_save_org_result(e: ft.FilePickerResultEvent):
        if e.path and hasattr(page, "_org_writer"):
            with open(e.path, "wb") as f:
                page._org_writer.write(f)
            if fasten_flag[0] or ajuste_flag[0]:
                def _soa_pipeline(p=e.path):
                    _apply_pipeline_sync(p, delete_input=True)
                threading.Thread(target=_soa_pipeline, daemon=True).start()
            else:
                snack(f"✓ Guardado: {Path(e.path).name}")
            reset_and_go_home()

    file_picker     = ft.FilePicker(on_result=pick_files_result)
    save_pick_merge = ft.FilePicker(on_result=on_save_merge_result)
    save_pick_org   = ft.FilePicker(on_result=on_save_org_result)
    page.overlay.extend([file_picker, save_pick_merge, save_pick_org])

    # ── EDIT HELPERS ──────────────────────────────────────────────────────────
    import shutil as _shutil

    # ── FASTEN PRINT HELPERS ──────────────────────────────────────────────────
    def _apply_fasten_sync(path: str, delete_input: bool = False) -> str:
        """
        Rasteriza cada pagina del PDF a la resolucion seleccionada (DPI)
        y las reinserta como imagenes. La impresora recibe pixeles listos,
        sin interpretar vectores ni fuentes. Nunca lanza excepcion.
        """
        out = path
        try:
            import io
            dpi  = dpi_value[0]
            zoom = dpi / 72.0
            mat  = fitz.Matrix(zoom, zoom)
            doc  = fitz.open(path)
            snack(f"Rasterizando {len(doc)} paginas a {dpi} DPI...", "#039BE5")

            out_doc = fitz.open()
            for page_num in range(len(doc)):
                pg   = doc[page_num]
                pix  = pg.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csGRAY)
                # JPEG comprime mucho mejor que PNG para texto e imágenes simples
                img_bytes = pix.tobytes("jpg", jpg_quality=85)
                new_page  = out_doc.new_page(width=pg.rect.width, height=pg.rect.height)
                new_page.insert_image(new_page.rect, stream=img_bytes)

            stem     = Path(path).stem
            out_path = DOWNLOADS / f"{stem}_print{dpi}dpi.pdf"
            out_doc.save(str(out_path), deflate=True, garbage=4, clean=True)
            out_doc.close()
            doc.close()
            out = str(out_path)
            snack(f"Fasten Print {dpi} DPI: {Path(out).name}")
        except Exception as ex:
            snack(f"Fasten Print error: {ex}", "#E53935")
        if delete_input and out != path:
            try:
                os.remove(path)
            except Exception:
                pass
        return out

    def _run_fasten(path: str):
        """Fasten Print standalone: rasteriza en hilo sin borrar el original."""
        threading.Thread(
            target=_apply_fasten_sync, args=(path, False), daemon=True
        ).start()

    def _apply_pipeline_sync(path: str, delete_input: bool = False) -> str:
        """Print/DPI -> Ajuste segun checkboxes. delete_input borra el intermedio."""
        current = path
        if fasten_flag[0]:
            current = _apply_fasten_sync(current, delete_input=delete_input)
        if ajuste_flag[0]:
            current = _apply_ajuste_sync(current, delete_input=(current != path))
        return current

    # ── AJUSTE B&N HELPERS ───────────────────────────────────────────────────
    def _open_ajuste_window(path: str, on_done: callable):
        """
        Abre ventana tkinter con sliders de brillo/contraste/saturación y toggle B&N.
        Llama on_done(out_path) cuando el usuario confirma, on_done(None) si cancela.
        Navega entre páginas para previsualizar.
        """
        import tkinter as tk
        from tkinter import ttk

        result_holder: list = [None]

        def _run_tk():
            root = tk.Tk()
            root.title("Ajuste de imagen")
            root.geometry("700x600")
            root.configure(bg="#1a1a2e")
            root.attributes("-topmost", True)

            # ── State ──────────────────────────────────────────────────────
            doc         = fitz.open(path)
            total_pages = len(doc)
            cur_page    = [0]
            bw_mode     = [False]

            brillo_var    = tk.DoubleVar(value=0.0)   # -1.0 a +1.0
            contraste_var = tk.DoubleVar(value=1.0)   # 0.5 a 2.0
            sat_var       = tk.DoubleVar(value=1.0)   # 0.0 a 2.0 (0=gris)

            # ── Preview ────────────────────────────────────────────────────
            try:
                from PIL import Image, ImageTk, ImageEnhance
                HAS_PIL = True
            except ImportError:
                HAS_PIL = False

            preview_label = tk.Label(root, bg="#1e1e3a")
            preview_label.pack(fill="both", expand=True, padx=12, pady=(12, 4))

            def render_preview():
                if not HAS_PIL:
                    preview_label.config(text="pip install pillow para previsualizar",
                                         fg="#9e9eb0", font=("Segoe UI", 11))
                    return
                pg  = doc[cur_page[0]]
                mat = fitz.Matrix(1.2, 1.2)
                pix = pg.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Aplicar ajustes
                img = ImageEnhance.Brightness(img).enhance(1.0 + brillo_var.get())
                img = ImageEnhance.Contrast(img).enhance(contraste_var.get())
                if bw_mode[0]:
                    img = img.convert("L").convert("RGB")
                else:
                    img = ImageEnhance.Color(img).enhance(sat_var.get())

                # Escalar para caber en el label
                max_w, max_h = 650, 380
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                preview_label.config(image=photo, text="")
                preview_label.image = photo

            # ── Navigation ─────────────────────────────────────────────────
            nav_frame = tk.Frame(root, bg="#1a1a2e")
            nav_frame.pack(fill="x", padx=12)

            page_label = tk.Label(nav_frame, text=f"Página 1 / {total_pages}",
                                  bg="#1a1a2e", fg="#9e9eb0", font=("Segoe UI", 10))

            def prev_page():
                if cur_page[0] > 0:
                    cur_page[0] -= 1
                    page_label.config(text=f"Página {cur_page[0]+1} / {total_pages}")
                    render_preview()

            def next_page():
                if cur_page[0] < total_pages - 1:
                    cur_page[0] += 1
                    page_label.config(text=f"Página {cur_page[0]+1} / {total_pages}")
                    render_preview()

            tk.Button(nav_frame, text="◀", command=prev_page,
                      bg="#1e1e3a", fg="white", relief="flat", padx=8).pack(side="left")
            page_label.pack(side="left", padx=8)
            tk.Button(nav_frame, text="▶", command=next_page,
                      bg="#1e1e3a", fg="white", relief="flat", padx=8).pack(side="left")

            # ── Sliders ────────────────────────────────────────────────────
            sliders_frame = tk.Frame(root, bg="#1a1a2e")
            sliders_frame.pack(fill="x", padx=16, pady=6)

            def make_slider(parent, label, var, from_, to, resolution):
                row = tk.Frame(parent, bg="#1a1a2e")
                row.pack(fill="x", pady=2)
                tk.Label(row, text=label, width=14, anchor="w",
                         bg="#1a1a2e", fg="#9e9eb0",
                         font=("Segoe UI", 10)).pack(side="left")
                sl = tk.Scale(row, variable=var, from_=from_, to=to,
                              resolution=resolution, orient="horizontal",
                              bg="#1e1e3a", fg="white", troughcolor="#3a3a5a",
                              highlightthickness=0, length=380,
                              command=lambda _: render_preview())
                sl.pack(side="left", expand=True, fill="x")
                return sl

            make_slider(sliders_frame, "Brillo",    brillo_var,    -1.0, 1.0, 0.05)
            make_slider(sliders_frame, "Contraste", contraste_var,  0.5, 2.0, 0.05)

            sat_row = tk.Frame(sliders_frame, bg="#1a1a2e")
            sat_row.pack(fill="x", pady=2)
            tk.Label(sat_row, text="Saturación", width=14, anchor="w",
                     bg="#1a1a2e", fg="#9e9eb0",
                     font=("Segoe UI", 10)).pack(side="left")
            sat_slider = tk.Scale(sat_row, variable=sat_var, from_=0.0, to=2.0,
                                  resolution=0.05, orient="horizontal",
                                  bg="#1e1e3a", fg="white", troughcolor="#3a3a5a",
                                  highlightthickness=0, length=380,
                                  command=lambda _: render_preview())
            sat_slider.pack(side="left", expand=True, fill="x")

            # ── B&N toggle ─────────────────────────────────────────────────
            bw_var = tk.BooleanVar(value=False)
            def on_bw_toggle():
                bw_mode[0] = bw_var.get()
                sat_slider.config(state="disabled" if bw_mode[0] else "normal")
                render_preview()

            bw_cb = tk.Checkbutton(sliders_frame, text="⚫ Blanco y Negro",
                                   variable=bw_var, command=on_bw_toggle,
                                   bg="#1a1a2e", fg="white", selectcolor="#1e1e3a",
                                   activebackground="#1a1a2e", activeforeground="white",
                                   font=("Segoe UI", 10))
            bw_cb.pack(anchor="w", pady=4)

            # ── Buttons ────────────────────────────────────────────────────
            btn_frame = tk.Frame(root, bg="#1a1a2e")
            btn_frame.pack(fill="x", padx=16, pady=(4, 12))

            def apply_and_save(apply_all: bool):
                """Aplica ajustes y guarda el PDF resultante."""
                try:
                    from PIL import Image, ImageEnhance
                    out_doc  = fitz.open()
                    pages_to = range(total_pages) if apply_all else [cur_page[0]]

                    for pn in range(total_pages):
                        pg  = doc[pn]
                        mat = fitz.Matrix(dpi_value[0] / 72.0, dpi_value[0] / 72.0) if fasten_flag[0] else fitz.Matrix(2, 2)
                        pix = pg.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                        if pn in pages_to or apply_all:
                            img = ImageEnhance.Brightness(img).enhance(1.0 + brillo_var.get())
                            img = ImageEnhance.Contrast(img).enhance(contraste_var.get())
                            if bw_mode[0]:
                                img = img.convert("L").convert("RGB")
                            else:
                                img = ImageEnhance.Color(img).enhance(sat_var.get())

                        import io
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=85)
                        buf.seek(0)

                        new_page = out_doc.new_page(width=pg.rect.width, height=pg.rect.height)
                        new_page.insert_image(new_page.rect, stream=buf.read())

                    stem     = Path(path).stem
                    suffix   = "_bw" if bw_mode[0] else "_ajuste"
                    out_path = DOWNLOADS / f"{stem}{suffix}.pdf"
                    out_doc.save(str(out_path), deflate=True, garbage=4)
                    out_doc.close()
                    result_holder[0] = str(out_path)
                    root.destroy()
                except Exception as ex:
                    tk.messagebox.showerror("Error", str(ex))

            tk.Button(btn_frame, text="Aplicar a esta página", padx=12, pady=6,
                      bg="#8E24AA", fg="white", relief="flat",
                      font=("Segoe UI", 10), cursor="hand2",
                      command=lambda: apply_and_save(False)).pack(side="left", padx=(0, 8))
            tk.Button(btn_frame, text="Aplicar a todo", padx=12, pady=6,
                      bg="#039BE5", fg="white", relief="flat",
                      font=("Segoe UI", 10), cursor="hand2",
                      command=lambda: apply_and_save(True)).pack(side="left", padx=(0, 8))
            tk.Button(btn_frame, text="Cancelar", padx=12, pady=6,
                      bg="#E53935", fg="white", relief="flat",
                      font=("Segoe UI", 10), cursor="hand2",
                      command=root.destroy).pack(side="right")

            # Centrar ventana
            root.update_idletasks()
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"700x600+{(sw-700)//2}+{(sh-600)//2}")

            render_preview()
            root.mainloop()
            doc.close()
            on_done(result_holder[0])

        threading.Thread(target=_run_tk, daemon=True).start()

    def _apply_ajuste_sync(path: str, delete_input: bool = False) -> str:
        """Abre la ventana de ajuste y espera resultado. Bloqueante en su hilo."""
        done_event  = threading.Event()
        result_path: list = [path]

        def on_done(out):
            result_path[0] = out if out else path
            done_event.set()

        _open_ajuste_window(path, on_done)
        done_event.wait()

        out = result_path[0]
        if delete_input and out != path:
            try:
                os.remove(path)
            except Exception:
                pass
        return out

    # ── ADD FILE HELPERS ──────────────────────────────────────────────────────
    def _add_file(path: str, name: str):
        if not path or not os.path.exists(path):
            snack(f"No se pudo cargar: {name}", "#E53935"); return
        pages = safe_page_count(path)
        if pages == 0:
            snack(f"PDF inválido: {name}", "#E53935"); return
        uploaded_files.append({"name": name, "path": path, "pages": pages})
        refresh_file_list()
        snack(f"✓ {name}  ({pages} pág.)")

    def load_from_url(url: str):
        url = url.strip()
        if not url:
            return
        snack("Descargando PDF…", "#1E88E5")
        def _dl():
            p = download_pdf_from_url(url)
            fn = url.split("/")[-1].split("?")[0] or "descargado.pdf"
            if not fn.lower().endswith(".pdf"):
                fn += ".pdf"
            if p:
                _add_file(p, fn)
            else:
                snack("No se pudo descargar el PDF", "#E53935")
        threading.Thread(target=_dl, daemon=True).start()
        url_field.value = ""
        url_field.update()

    # ── DRAG & DROP WINDOW ───────────────────────────────────────────────────
    def _open_drop_window():
        """Abre una ventana tkinterdnd2 flotante para recibir archivos arrastrados."""
        if not HAS_DND:
            snack("tkinterdnd2 no instalado: pip install tkinterdnd2", "#E53935")
            return

        def _run_tk():
            root = TkinterDnD.Tk()
            root.title("Soltar PDFs aquí")
            root.geometry("320x160")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            root.configure(bg="#1a1a2e")

            import tkinter as tk

            lbl = tk.Label(
                root,
                text="📂  Arrastra los PDFs aquí",
                bg="#1e1e3a", fg="#9e9eb0",
                font=("Segoe UI", 13),
                relief="flat", bd=0,
            )
            lbl.pack(expand=True, fill="both", padx=16, pady=16)

            status = tk.Label(
                root, text="", bg="#1a1a2e", fg="#43A047",
                font=("Segoe UI", 10),
            )
            status.pack(pady=(0, 10))

            def on_drop(event):
                # tkinterdnd2 entrega rutas separadas por espacios o entre llaves
                raw = event.data
                import re as _re
                # Extraer rutas entre llaves {ruta con espacios} o sin ellas
                paths = _re.findall(r'\{([^}]+)\}|(\S+)', raw)
                paths = [a or b for a, b in paths]
                added = 0
                for p in paths:
                    if p.lower().endswith(".pdf") and os.path.exists(p):
                        name = Path(p).name
                        _add_file(p, name)
                        added += 1
                if added:
                    status.config(text=f"✓ {added} archivo(s) añadido(s)", fg="#43A047")
                else:
                    status.config(text="⚠ No se detectaron PDFs válidos", fg="#E53935")

            close_btn = tk.Button(
                root, text="Cerrar",
                bg="#E53935", fg="white",
                font=("Segoe UI", 10),
                relief="flat", bd=0,
                padx=16, pady=4,
                cursor="hand2",
                command=root.destroy,
            )
            close_btn.pack(pady=(0, 12))

            lbl.drop_target_register(DND_FILES)
            lbl.dnd_bind("<<Drop>>", on_drop)

            # Centrar ventana
            root.update_idletasks()
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            x  = (sw - 320) // 2
            y  = (sh - 160) // 2
            root.geometry(f"320x160+{x}+{y}")

            root.mainloop()

        threading.Thread(target=_run_tk, daemon=True).start()

    # ── HEADER ────────────────────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.PICTURE_AS_PDF, color="#E53935", size=26),
            ft.Text("PDF Manager", size=20, weight=ft.FontWeight.BOLD, color="white"),
            ft.Text("Travel Agent Edition", size=12, color="#9e9eb0"),
        ], spacing=10),
        padding=ft.padding.symmetric(horizontal=24, vertical=14),
        bgcolor="#12122a",
    )

    # ── URL + BROWSE ROW ──────────────────────────────────────────────────────
    url_field = ft.TextField(
        hint_text="Pega un enlace a un PDF y pulsa Enter",
        hint_style=ft.TextStyle(color="#6e6e80"),
        bgcolor="#1e1e3a", color="white",
        border_color="#3a3a5a", focused_border_color="#1E88E5",
        border_radius=10, height=44, text_size=13,
        prefix_icon=ft.icons.LINK,
        expand=True,
        on_submit=lambda e: load_from_url(e.control.value),
    )
    url_btn = ft.IconButton(
        ft.icons.DOWNLOAD, icon_color="#1E88E5", tooltip="Descargar PDF desde URL",
        on_click=lambda _: load_from_url(url_field.value),
    )
    browse_btn = ft.ElevatedButton(
        "Browse",
        icon=ft.icons.FOLDER_OPEN,
        bgcolor="#1e1e3a", color="white",
        height=44,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            side=ft.BorderSide(1, "#3a3a5a"),
        ),
        on_click=lambda _: file_picker.pick_files(allowed_extensions=["pdf"], allow_multiple=True),
    )
    drop_btn = ft.ElevatedButton(
        "Drop Zone",
        icon=ft.icons.OPEN_WITH,
        bgcolor="#1e1e3a", color="white",
        height=44,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            side=ft.BorderSide(1, "#3a3a5a"),
        ),
        on_click=lambda _: _open_drop_window(),
    )

    # ── FILE LIST ─────────────────────────────────────────────────────────────
    file_list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
    action_row    = ft.Row(visible=False, spacing=10, wrap=False, scroll=ft.ScrollMode.AUTO)

    dpi_dropdown = ft.Dropdown(
        value="300",
        width=120,
        height=42,
        bgcolor="#1e1e3a",
        color="white",
        border_color="#3a3a5a",
        focused_border_color="#039BE5",
        text_size=12,
        disabled=True,   # desactivado hasta que se marque Fasten Print
        options=[
            ft.dropdown.Option("150", "150 DPI – Ligero"),
            ft.dropdown.Option("200", "200 DPI – Equilibrado"),
            ft.dropdown.Option("300", "300 DPI – Estándar"),
            ft.dropdown.Option("400", "400 DPI – Alta calidad"),
            ft.dropdown.Option("600", "600 DPI – Máxima calidad"),
        ],
        on_change=lambda e: dpi_value.__setitem__(0, int(e.control.value)),
    )

    def _on_fasten_change(e):
        fasten_flag[0]        = e.control.value
        dpi_dropdown.disabled = not e.control.value
        dpi_dropdown.update()

    fasten_checkbox = ft.Checkbox(
        label="Print",
        value=False,
        label_style=ft.TextStyle(size=12, color="#9e9eb0"),
        fill_color="#039BE5",
        check_color="white",
        tooltip="Rasteriza el PDF al DPI elegido para impresión fluida sin pausas",
        on_change=_on_fasten_change,
    )
    ajuste_checkbox = ft.Checkbox(
        label="◑ Ajuste",
        value=False,
        label_style=ft.TextStyle(size=12, color="#9e9eb0"),
        fill_color="#8E24AA",
        check_color="white",
        tooltip="Abre ventana de ajuste de brillo, contraste, saturación y B&N antes de guardar",
        on_change=lambda e: ajuste_flag.__setitem__(0, e.control.value),
    )

    def refresh_file_list():
        file_list_col.controls.clear()
        for i, f in enumerate(uploaded_files):
            color = FILE_COLORS[i % len(FILE_COLORS)]
            tile  = ft.Container(
                content=ft.Row([
                    ft.Container(width=4, height=38, bgcolor=color, border_radius=2),
                    ft.Icon(ft.icons.PICTURE_AS_PDF, color=color, size=18),
                    ft.Column([
                        ft.Text(f["name"], size=12, weight=ft.FontWeight.W_500, color="white",
                                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                        ft.Text(f"{f['pages']} pág.", size=11, color="#9e9eb0"),
                    ], spacing=0, expand=True),
                    ft.IconButton(ft.icons.DELETE_OUTLINE, icon_color="#E53935",
                                  icon_size=17, tooltip="Quitar", data=i,
                                  on_click=lambda e: _remove_file(e.control.data)),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor="#1e1e3a", border_radius=10,
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
            )
            file_list_col.controls.append(tile)
        action_row.visible = len(uploaded_files) >= 1
        page.update()

    def _remove_file(idx: int):
        uploaded_files.pop(idx)
        refresh_file_list()

    # ── ACTION BUTTONS ────────────────────────────────────────────────────────
    def do_fasten_standalone(_=None):
        """Print: rasteriza cada PDF por separado al DPI del dropdown."""
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return
        for f in uploaded_files:
            _run_fasten(f["path"])

    def do_ajuste_standalone(_=None):
        """Ajuste: abre ventana de ajuste para cada PDF por separado."""
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return
        def _process():
            for f in uploaded_files:
                _apply_ajuste_sync(f["path"], delete_input=False)
        threading.Thread(target=_process, daemon=True).start()

    def do_organize_renfe(_=None):
        """Organize Renfe: ordena por fecha/DNI; si Edit marcado edita y borra el intermedio."""
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return

        def _process():
            for f in uploaded_files:
                snack(f"Ordenando {f['name']}…", "#039BE5")
                # Usar nombre original limpio, no el del path temporal
                original_stem = Path(f["name"]).stem
                ordered = _renfe_sort_pdf(f["path"], original_stem)
                if ordered:
                    if fasten_flag[0] or ajuste_flag[0]:
                        # pipeline borra el _ordenado.pdf intermedio
                        _apply_pipeline_sync(ordered, delete_input=True)
                    else:
                        snack(f"✓ Renfe ordenado: {Path(ordered).name}")
                else:
                    snack(f"⚠️ No se pudo ordenar: {f['name']}", "#F4511E")

        threading.Thread(target=_process, daemon=True).start()

    action_row.controls = [
        ft.ElevatedButton("Merge", icon=ft.icons.MERGE_TYPE,
                          bgcolor="#1E88E5", color="white", height=42,
                          on_click=lambda _: open_merge_view()),
        ft.ElevatedButton("Organize", icon=ft.icons.DASHBOARD_CUSTOMIZE,
                          bgcolor="#8E24AA", color="white", height=42,
                          on_click=lambda _: open_organize_view()),
        ft.ElevatedButton("Organize Renfe", icon=ft.icons.TRAIN,
                          bgcolor="#00897B", color="white", height=42,
                          on_click=do_organize_renfe),
        ft.ElevatedButton("Print", icon=ft.icons.PRINT,
                          bgcolor="#039BE5", color="white", height=42,
                          on_click=do_fasten_standalone),
        ft.ElevatedButton("◑ Ajuste", icon=ft.icons.TUNE,
                          bgcolor="#8E24AA", color="white", height=42,
                          on_click=do_ajuste_standalone),
        ft.ElevatedButton("Edit", icon=ft.icons.EDIT_NOTE,
                          bgcolor="#F4511E", color="white", height=42,
                          on_click=lambda _: open_edit_view()),
        ft.ElevatedButton("Metadata", icon=ft.icons.INFO_OUTLINE,
                          bgcolor="#6D4C41", color="white", height=42,
                          on_click=lambda _: open_metadata_view()),
        ft.ElevatedButton("Split", icon=ft.icons.CONTENT_CUT,
                          bgcolor="#43A047", color="white", height=42,
                          on_click=lambda _: open_split_view()),
        fasten_checkbox,
        dpi_dropdown,
        ajuste_checkbox,
        ft.OutlinedButton("Limpiar todo", icon=ft.icons.CLEAR_ALL,
                          style=ft.ButtonStyle(color="#E53935"),
                          on_click=lambda _: [uploaded_files.clear(), refresh_file_list()]),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    #  MERGE VIEW
    # ══════════════════════════════════════════════════════════════════════════
    merge_list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

    def build_merge_list():
        merge_list_col.controls.clear()

        def make_item(pos: int, fi: int):
            f     = uploaded_files[fi]
            color = FILE_COLORS[fi % len(FILE_COLORS)]

            def on_accept(e: ft.DragTargetAcceptEvent, target_pos=pos):
                src_pos = int(e.data)
                if src_pos == target_pos:
                    return
                item = merge_order.pop(src_pos)
                merge_order.insert(target_pos, item)
                build_merge_list()

            row_content = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.DRAG_INDICATOR, color="#5a5a8a"),
                    ft.Container(width=4, height=34, bgcolor=color, border_radius=2),
                    ft.Text(f["name"], size=13, color="white", expand=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{f['pages']} pág.", size=11, color="#9e9eb0"),
                    ft.IconButton(ft.icons.ARROW_UPWARD, icon_size=16,
                                  icon_color="#9e9eb0", data=pos, on_click=merge_up),
                    ft.IconButton(ft.icons.ARROW_DOWNWARD, icon_size=16,
                                  icon_color="#9e9eb0", data=pos, on_click=merge_down),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor="#1e1e3a", border_radius=10,
                padding=ft.padding.symmetric(horizontal=10, vertical=5),
            )

            return ft.DragTarget(
                group="merge_items",
                content=ft.Draggable(
                    group="merge_items",
                    data=str(pos),
                    content=row_content,
                    content_when_dragging=ft.Container(
                        height=44,
                        bgcolor="#2a2a4a",
                        border=ft.border.all(2, "#3a3a5a"),
                        border_radius=10,
                    ),
                ),
                on_accept=on_accept,
            )

        for pos, fi in enumerate(merge_order):
            merge_list_col.controls.append(make_item(pos, fi))

        if merge_list_col.page:
            merge_list_col.update()

    def merge_up(e):
        pos = e.control.data
        if pos > 0:
            merge_order[pos], merge_order[pos - 1] = merge_order[pos - 1], merge_order[pos]
            build_merge_list()

    def merge_down(e):
        pos = e.control.data
        if pos < len(merge_order) - 1:
            merge_order[pos], merge_order[pos + 1] = merge_order[pos + 1], merge_order[pos]
            build_merge_list()

    def do_merge(save_as: bool = False):
        if not merge_order:
            return
        writer = PdfWriter()
        for fi in merge_order:
            for p in PdfReader(uploaded_files[fi]["path"]).pages:
                writer.add_page(p)
        first    = Path(uploaded_files[merge_order[0]]["name"]).stem
        out_name = f"{first}_Merged.pdf"
        if save_as:
            page._merge_writer = writer
            save_pick_merge.save_file(file_name=out_name, allowed_extensions=["pdf"])
        else:
            out = DOWNLOADS / out_name
            with open(out, "wb") as f:
                writer.write(f)
            if fasten_flag[0] or ajuste_flag[0]:
                def _merge_pipeline(p=str(out)):
                    _apply_pipeline_sync(p, delete_input=True)
                threading.Thread(target=_merge_pipeline, daemon=True).start()
            else:
                snack(f"✓ Guardado en Descargas: {out_name}")
            reset_and_go_home()

    def open_merge_view():
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return
        merge_order.clear()
        merge_order.extend(range(len(uploaded_files)))
        build_merge_list()

        view = ft.View(
            "/merge",
            bgcolor="#1a1a2e",
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: go_back()),
                title=ft.Text("Merge – Ordenar documentos"),
                bgcolor="#12122a",
            ),
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Text("Arrastra ↕ o usa las flechas para reordenar antes de unir:",
                                size=13, color="#9e9eb0"),
                        merge_list_col,
                        ft.Row([
                            ft.ElevatedButton("⬇  Merge & Guardar en Descargas",
                                              icon=ft.icons.MERGE_TYPE,
                                              bgcolor="#1E88E5", color="white",
                                              on_click=lambda _: do_merge(False)),
                            ft.OutlinedButton("Save As…", icon=ft.icons.FOLDER_OPEN,
                                              style=ft.ButtonStyle(color="white"),
                                              on_click=lambda _: do_merge(True)),
                        ], spacing=12),
                    ], spacing=14, expand=True),
                    padding=24, expand=True,
                ),
            ],
        )
        page.views.append(view)
        page.update()

    # ══════════════════════════════════════════════════════════════════════════
    #  ORGANIZE VIEW
    # ══════════════════════════════════════════════════════════════════════════
    org_grid = ft.GridView(
        expand=True, runs_count=5, max_extent=155,
        child_aspect_ratio=0.72, spacing=10, run_spacing=10,
    )

    def build_org_grid():
        org_grid.controls.clear()
        visible = [p for p in org_pages if not p["deleted"]]
        for pg in visible:
            color     = pg["color"]
            lbl       = pg["label"]
            rot       = pg["rotation"]
            file_path = uploaded_files[pg["file_idx"]]["path"]
            page_idx  = pg["page_idx"]

            thumb = get_page_thumbnail(file_path, page_idx, rotation=rot)
            if thumb:
                preview = ft.Container(
                    content=ft.Image(src_base64=thumb, fit=ft.ImageFit.CONTAIN),
                    alignment=ft.alignment.center,
                    expand=True,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                )
            else:
                preview = ft.Container(
                    content=ft.Icon(ft.icons.ARTICLE, color="#aaaacc", size=36,
                                    rotate=ft.Rotate(rot * math.pi / 180)),
                    alignment=ft.alignment.center,
                    expand=True,
                )

            card = ft.Container(
                content=ft.Stack([
                    ft.Container(
                        content=ft.Column([
                            preview,
                            ft.Container(
                                ft.Text(lbl, size=12, weight=ft.FontWeight.BOLD,
                                        color="white", text_align=ft.TextAlign.CENTER),
                                bgcolor="#00000080", padding=4,
                                border_radius=ft.border_radius.only(
                                    bottom_left=8, bottom_right=8),
                            ),
                        ], spacing=0),
                        bgcolor="#1e1e3a",
                        border=ft.border.all(2, color),
                        border_radius=10,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.IconButton(
                            ft.icons.CLOSE, icon_size=13, icon_color="white",
                            bgcolor="#E53935",
                            style=ft.ButtonStyle(padding=ft.padding.all(0)),
                            data=pg, on_click=org_delete,
                        ),
                        right=2, top=2, width=26, height=26,
                    ),
                    ft.Container(
                        content=ft.IconButton(
                            ft.icons.ROTATE_RIGHT, icon_size=13, icon_color="white",
                            bgcolor="#1E88E5",
                            style=ft.ButtonStyle(padding=ft.padding.all(0)),
                            data=pg, on_click=org_rotate,
                        ),
                        left=2, top=2, width=26, height=26,
                    ),
                    ft.Container(
                        content=ft.IconButton(
                            ft.icons.CHEVRON_LEFT, icon_size=13, icon_color="white",
                            bgcolor="#00000080",
                            style=ft.ButtonStyle(padding=ft.padding.all(0)),
                            data=(pg, "left"), on_click=org_move,
                        ),
                        left=2, bottom=30, width=26, height=26,
                    ),
                    ft.Container(
                        content=ft.IconButton(
                            ft.icons.CHEVRON_RIGHT, icon_size=13, icon_color="white",
                            bgcolor="#00000080",
                            style=ft.ButtonStyle(padding=ft.padding.all(0)),
                            data=(pg, "right"), on_click=org_move,
                        ),
                        right=2, bottom=30, width=26, height=26,
                    ),
                ]),
                height=155,
            )
            org_grid.controls.append(card)
        if org_grid.page:
            org_grid.update()

    def org_delete(e):
        e.control.data["deleted"] = True
        build_org_grid()

    def org_rotate(e):
        pg = e.control.data
        pg["rotation"] = (pg["rotation"] + 90) % 360
        build_org_grid()

    def org_move(e):
        pg, direction = e.control.data
        visible = [p for p in org_pages if not p["deleted"]]
        idx = visible.index(pg)
        ri  = org_pages.index(pg)
        if direction == "left" and idx > 0:
            prev = visible[idx - 1]
            pi   = org_pages.index(prev)
            org_pages[ri], org_pages[pi] = org_pages[pi], org_pages[ri]
        elif direction == "right" and idx < len(visible) - 1:
            nxt = visible[idx + 1]
            ni  = org_pages.index(nxt)
            org_pages[ri], org_pages[ni] = org_pages[ni], org_pages[ri]
        build_org_grid()

    def do_organize(save_as: bool = False):
        visible = [p for p in org_pages if not p["deleted"]]
        if not visible:
            snack("No quedan páginas", "#E53935"); return
        writer = PdfWriter()
        for pg in visible:
            f        = uploaded_files[pg["file_idx"]]
            page_obj = PdfReader(f["path"]).pages[pg["page_idx"]]
            if pg["rotation"]:
                page_obj.rotate(pg["rotation"])
            writer.add_page(page_obj)
        first_fi   = visible[0]["file_idx"]
        first_name = Path(uploaded_files[first_fi]["name"]).stem
        out_name   = f"{first_name}_Organized.pdf"
        if save_as:
            page._org_writer = writer
            save_pick_org.save_file(file_name=out_name, allowed_extensions=["pdf"])
        else:
            out = DOWNLOADS / out_name
            with open(out, "wb") as f:
                writer.write(f)
            if fasten_flag[0] or ajuste_flag[0]:
                def _org_pipeline(p=str(out)):
                    _apply_pipeline_sync(p, delete_input=True)
                threading.Thread(target=_org_pipeline, daemon=True).start()
            else:
                snack(f"✓ Guardado en Descargas: {out_name}")
            reset_and_go_home()

    def open_organize_view():
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return
        org_pages.clear()
        for fi, f in enumerate(uploaded_files):
            for pi in range(f["pages"]):
                org_pages.append({
                    "file_idx": fi, "page_idx": pi,
                    "label":    label_for(fi, pi),
                    "color":    FILE_COLORS[fi % len(FILE_COLORS)],
                    "rotation": 0, "deleted": False,
                })

        org_grid.controls.clear()

        legend = ft.Row(
            [
                ft.Row([
                    ft.Container(width=11, height=11,
                                 bgcolor=FILE_COLORS[i % len(FILE_COLORS)],
                                 border_radius=3),
                    ft.Text(f"Archivo {chr(65 + i)}", size=11, color="#9e9eb0"),
                ], spacing=4)
                for i in range(len(uploaded_files))
            ],
            spacing=14, wrap=True,
        )

        view = ft.View(
            "/organize",
            bgcolor="#1a1a2e",
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: go_back()),
                title=ft.Text("Organize – Gestionar páginas"),
                bgcolor="#12122a",
                actions=[
                    ft.Container(
                        ft.Row([
                            ft.Container(width=8, height=8, bgcolor="#1E88E5", border_radius=4),
                            ft.Text("Rotar", size=11, color="#9e9eb0"),
                            ft.Container(width=8, height=8, bgcolor="#E53935", border_radius=4),
                            ft.Text("Eliminar", size=11, color="#9e9eb0"),
                            ft.Container(width=8, height=8, bgcolor="#444460", border_radius=4),
                            ft.Text("Mover", size=11, color="#9e9eb0"),
                        ], spacing=6),
                        padding=ft.padding.only(right=16),
                    )
                ],
            ),
            controls=[
                ft.Container(
                    content=ft.Column([
                        legend,
                        ft.Container(
                            content=org_grid,
                            expand=True,
                            border=ft.border.all(1, "#2a2a4a"),
                            border_radius=12,
                            padding=10,
                        ),
                        ft.Row([
                            ft.ElevatedButton("⬇  Organize & Guardar en Descargas",
                                              icon=ft.icons.SAVE,
                                              bgcolor="#8E24AA", color="white",
                                              on_click=lambda _: do_organize(False)),
                            ft.OutlinedButton("Save As…", icon=ft.icons.FOLDER_OPEN,
                                              style=ft.ButtonStyle(color="white"),
                                              on_click=lambda _: do_organize(True)),
                        ], spacing=12),
                    ], spacing=10, expand=True),
                    padding=20, expand=True,
                ),
            ],
        )
        page.views.append(view)
        page.update()

        threading.Thread(target=build_org_grid, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  EDIT VIEW  (censurar texto + buscar y reemplazar)
    # ══════════════════════════════════════════════════════════════════════════
    def _file_dropdown() -> ft.Dropdown:
        return ft.Dropdown(
            value="0",
            expand=True,
            bgcolor="#1e1e3a", color="white",
            border_color="#3a3a5a", focused_border_color="#F4511E",
            text_size=13,
            options=[
                ft.dropdown.Option(str(i), f["name"])
                for i, f in enumerate(uploaded_files)
            ],
        )

    def open_edit_view():
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return
        if not HAS_FITZ:
            snack("PyMuPDF (fitz) no está instalado", "#E53935"); return

        file_dd = _file_dropdown()

        censor_field = ft.TextField(
            hint_text="Texto exacto a censurar",
            bgcolor="#1e1e3a", color="white",
            border_color="#3a3a5a", focused_border_color="#E53935",
            text_size=13, expand=True,
        )
        buscar_field = ft.TextField(
            hint_text="Buscar",
            bgcolor="#1e1e3a", color="white",
            border_color="#3a3a5a", focused_border_color="#1E88E5",
            text_size=13, expand=True,
        )
        reemplazar_field = ft.TextField(
            hint_text="Reemplazar por (vacío = eliminar)",
            bgcolor="#1e1e3a", color="white",
            border_color="#3a3a5a", focused_border_color="#1E88E5",
            text_size=13, expand=True,
        )

        def _selected_file():
            idx = int(file_dd.value)
            return uploaded_files[idx]

        def do_censor(_=None):
            texto = censor_field.value or ""
            if not texto.strip():
                snack("Escribe el texto a censurar", "#E53935"); return
            f = _selected_file()
            snack(f"Censurando en {f['name']}…", "#039BE5")
            def _run():
                out = censor_text_in_pdf(f["path"], texto)
                if out:
                    snack(f"✓ Censurado (sin vuelta atrás): {Path(out).name}")
                else:
                    snack("No se encontró ese texto en el PDF", "#F4511E")
            threading.Thread(target=_run, daemon=True).start()

        def do_find_replace(_=None):
            buscar     = buscar_field.value or ""
            reemplazar = reemplazar_field.value or ""
            if not buscar.strip():
                snack("Escribe el texto a buscar", "#E53935"); return
            f = _selected_file()
            snack(f"Buscando en {f['name']}…", "#039BE5")
            def _run():
                out = find_replace_in_pdf(f["path"], buscar, reemplazar)
                if out:
                    snack(f"✓ Reemplazado: {Path(out).name}")
                else:
                    snack("No se encontró ese texto en el PDF", "#F4511E")
            threading.Thread(target=_run, daemon=True).start()

        view = ft.View(
            "/edit",
            bgcolor="#1a1a2e",
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: go_back()),
                title=ft.Text("Edit – Censurar / Buscar y reemplazar"),
                bgcolor="#12122a",
            ),
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Text("Archivo:", size=13, color="#9e9eb0"),
                        file_dd,
                        ft.Container(height=14),
                        ft.Text("Censurar texto", size=15, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Text("El texto encontrado se cubre con una barra negra sólida "
                                "del tamaño del área ocupada y se elimina del documento. "
                                "Esta acción no se puede deshacer.",
                                size=11, color="#9e9eb0"),
                        ft.Row([censor_field,
                                ft.ElevatedButton("Censurar", icon=ft.icons.VISIBILITY_OFF,
                                                   bgcolor="#000000", color="white",
                                                   on_click=do_censor)], spacing=10),
                        ft.Divider(color="#2a2a4a"),
                        ft.Text("Buscar y reemplazar", size=15, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Row([buscar_field, reemplazar_field,
                                ft.ElevatedButton("Reemplazar", icon=ft.icons.FIND_REPLACE,
                                                   bgcolor="#1E88E5", color="white",
                                                   on_click=do_find_replace)], spacing=10),
                    ], spacing=10, expand=True),
                    padding=24, expand=True,
                ),
            ],
        )
        page.views.append(view)
        page.update()

    # ══════════════════════════════════════════════════════════════════════════
    #  METADATA VIEW
    # ══════════════════════════════════════════════════════════════════════════
    def open_metadata_view():
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return
        if not HAS_FITZ:
            snack("PyMuPDF (fitz) no está instalado", "#E53935"); return

        file_dd = _file_dropdown()

        title_field    = ft.TextField(label="Título", bgcolor="#1e1e3a", color="white",
                                       border_color="#3a3a5a", focused_border_color="#6D4C41", text_size=13)
        author_field   = ft.TextField(label="Autor", bgcolor="#1e1e3a", color="white",
                                       border_color="#3a3a5a", focused_border_color="#6D4C41", text_size=13)
        subject_field  = ft.TextField(label="Asunto", bgcolor="#1e1e3a", color="white",
                                       border_color="#3a3a5a", focused_border_color="#6D4C41", text_size=13)
        keywords_field = ft.TextField(label="Palabras clave", bgcolor="#1e1e3a", color="white",
                                       border_color="#3a3a5a", focused_border_color="#6D4C41", text_size=13)

        def _selected_file():
            idx = int(file_dd.value)
            return uploaded_files[idx]

        def _load_fields(_=None):
            meta = read_metadata(_selected_file()["path"])
            title_field.value    = meta.get("title", "") or ""
            author_field.value   = meta.get("author", "") or ""
            subject_field.value  = meta.get("subject", "") or ""
            keywords_field.value = meta.get("keywords", "") or ""
            for c in (title_field, author_field, subject_field, keywords_field):
                if c.page:
                    c.update()

        file_dd.on_change = _load_fields

        def do_save_metadata(_=None):
            f = _selected_file()
            meta = {
                "title":    title_field.value or "",
                "author":   author_field.value or "",
                "subject":  subject_field.value or "",
                "keywords": keywords_field.value or "",
            }
            out = write_metadata(f["path"], meta)
            if out:
                snack(f"✓ Metadatos guardados: {Path(out).name}")
            else:
                snack("No se pudieron guardar los metadatos", "#E53935")

        def do_clear_metadata(_=None):
            f = _selected_file()
            out = clear_metadata(f["path"])
            if out:
                snack(f"✓ Metadatos eliminados: {Path(out).name}")
                title_field.value = author_field.value = subject_field.value = keywords_field.value = ""
                for c in (title_field, author_field, subject_field, keywords_field):
                    if c.page:
                        c.update()
            else:
                snack("No se pudieron eliminar los metadatos", "#E53935")

        view = ft.View(
            "/metadata",
            bgcolor="#1a1a2e",
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: go_back()),
                title=ft.Text("Metadata – Ver / editar / borrar"),
                bgcolor="#12122a",
            ),
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Text("Archivo:", size=13, color="#9e9eb0"),
                        file_dd,
                        ft.Container(height=10),
                        title_field, author_field, subject_field, keywords_field,
                        ft.Row([
                            ft.ElevatedButton("Guardar cambios", icon=ft.icons.SAVE,
                                              bgcolor="#6D4C41", color="white",
                                              on_click=do_save_metadata),
                            ft.OutlinedButton("Borrar todos los metadatos", icon=ft.icons.DELETE_FOREVER,
                                              style=ft.ButtonStyle(color="#E53935"),
                                              on_click=do_clear_metadata),
                        ], spacing=12),
                    ], spacing=12, expand=True),
                    padding=24, expand=True,
                ),
            ],
        )
        page.views.append(view)
        page.update()
        _load_fields()

    # ══════════════════════════════════════════════════════════════════════════
    #  SPLIT VIEW  (dividir por N páginas / cada página en un archivo)
    # ══════════════════════════════════════════════════════════════════════════
    def open_split_view():
        if not uploaded_files:
            snack("Añade al menos un PDF", "#E53935"); return

        file_dd = _file_dropdown()

        n_field = ft.TextField(
            label="Páginas por archivo (N)", value="1",
            bgcolor="#1e1e3a", color="white",
            border_color="#3a3a5a", focused_border_color="#43A047",
            text_size=13, width=220,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        mode_radio = ft.RadioGroup(
            value="each",
            content=ft.Column([
                ft.Radio(value="each", label="Cada página en un archivo individual",
                         label_style=ft.TextStyle(color="white")),
                ft.Radio(value="n", label="Cada N páginas por archivo",
                         label_style=ft.TextStyle(color="white")),
            ]),
        )

        def _selected_file():
            idx = int(file_dd.value)
            return uploaded_files[idx]

        def do_split(_=None):
            f = _selected_file()
            if mode_radio.value == "each":
                n, label = 1, "pagina"
            else:
                try:
                    n = max(1, int(n_field.value))
                except (TypeError, ValueError):
                    snack("Indica un número de páginas válido", "#E53935"); return
                label = "parte"
            snack(f"Dividiendo {f['name']}…", "#039BE5")
            def _run():
                outputs = split_pdf(f["path"], n, label=label)
                if outputs:
                    snack(f"✓ {len(outputs)} archivo(s) generados en "
                          f"{Path(outputs[0]).parent.name}/")
                else:
                    snack("No se pudo dividir el PDF", "#E53935")
            threading.Thread(target=_run, daemon=True).start()

        view = ft.View(
            "/split",
            bgcolor="#1a1a2e",
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: go_back()),
                title=ft.Text("Split – Dividir PDF"),
                bgcolor="#12122a",
            ),
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Text("Archivo:", size=13, color="#9e9eb0"),
                        file_dd,
                        ft.Container(height=10),
                        mode_radio,
                        n_field,
                        ft.Container(height=10),
                        ft.ElevatedButton("Dividir", icon=ft.icons.CONTENT_CUT,
                                          bgcolor="#43A047", color="white",
                                          on_click=do_split),
                    ], spacing=10, expand=True),
                    padding=24, expand=True,
                ),
            ],
        )
        page.views.append(view)
        page.update()

    # ── HOME VIEW ─────────────────────────────────────────────────────────────
    home_view = ft.View(
        "/",
        bgcolor="#1a1a2e",
        padding=0,
        controls=[
            ft.Column([
                header,
                ft.Container(
                    content=ft.Column([
                        ft.Row([url_field, url_btn, browse_btn, drop_btn], spacing=6),
                        ft.Container(height=8),
                        ft.Container(content=file_list_col, expand=True),
                        ft.Container(height=6),
                        ft.Container(
                            content=action_row,
                            bgcolor="#12122a",
                            border_radius=10,
                            padding=ft.padding.symmetric(horizontal=8, vertical=6),
                        ),
                    ], spacing=0, expand=True),
                    padding=20,
                    expand=True,
                ),
            ], spacing=0, expand=True),
        ],
    )

    def reset_and_go_home():
        """Vuelve a la pantalla principal y limpia todos los archivos cargados."""
        uploaded_files.clear()
        fasten_flag[0] = False
        dpi_value[0]          = 300
        ajuste_flag[0]         = False
        fasten_checkbox.value  = False
        ajuste_checkbox.value  = False
        dpi_dropdown.value     = "300"
        dpi_dropdown.disabled  = True
        if fasten_checkbox.page:
            fasten_checkbox.update()
        if ajuste_checkbox.page:
            ajuste_checkbox.update()
        if dpi_dropdown.page:
            dpi_dropdown.update()
        go_back()
        refresh_file_list()

    def go_back():
        if len(page.views) > 1:
            page.views.pop()
            page.update()

    def route_change(e):
        page.views.clear()
        page.views.append(home_view)
        page.update()

    page.on_route_change = route_change
    page.go("/")


ft.app(target=main)
