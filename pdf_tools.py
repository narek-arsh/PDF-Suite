# -*- coding: utf-8 -*-
"""
pdf_tools.py — Herramientas de archivo completo: comprimir, bloquear y desbloquear con contraseña, marca de agua,
aplanar, reparar, convertir a PDF (imágenes, texto, Markdown, HTML, Word/Excel/PowerPoint si hay Office o
LibreOffice) y OCR. Sin dependencias de interfaz. Cada función recibe rutas y devuelve un resultado simple;
los errores esperables (contraseña incorrecta, falta un motor…) llegan como ToolError con un mensaje claro.
"""
import html
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz

DOWNLOADS = Path.home() / "Downloads"


class ToolError(Exception):
    """Fallo esperable, con un mensaje listo para enseñar al usuario."""


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    n = 2
    while True:
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def out_path(src: str, suffix: str, ext: str = ".pdf") -> Path:
    DOWNLOADS.mkdir(exist_ok=True)
    return _unique(DOWNLOADS / f"{Path(src).stem}{suffix}{ext}")


def _open(path: str, password: str = ""):
    doc = fitz.open(path)
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            doc.close()
            raise ToolError("Este PDF tiene contraseña de apertura. Desbloquéalo primero (o escribe la contraseña).")
    return doc


def is_locked(path: str) -> bool:
    """True si hace falta contraseña para abrir el PDF."""
    try:
        d = fitz.open(path)
        r = d.needs_pass
        d.close()
        return bool(r)
    except Exception:
        return False


# ── Comprimir ─────────────────────────────────────────────────────────────
COMPRESS_LEVELS = {
    "low": ("Calidad alta (ahorra poco)", dict(dpi_threshold=300, dpi_target=220, quality=90)),
    "medium": ("Equilibrada (recomendada)", dict(dpi_threshold=200, dpi_target=150, quality=75)),
    "high": ("Máxima compresión (calidad menor)", dict(dpi_threshold=130, dpi_target=100, quality=55)),
}


def compress(path: str, level: str = "medium", password: str = "") -> dict:
    """Reduce el peso reescalando imágenes grandes, comprimiendo fuentes y limpiando objetos sin uso.
    Si el resultado no pesa menos que el original, no se guarda: {"ok": False, "reason": ...}."""
    before = os.path.getsize(path)
    doc = _open(path, password)
    try:
        params = COMPRESS_LEVELS[level][1]
        try:
            doc.rewrite_images(**params)
        except Exception:
            pass                                               # sin imágenes o formatos raros: se sigue con lo demás
        try:
            doc.subset_fonts()
        except Exception:
            pass
        dest = out_path(path, "_comprimido")
        doc.save(str(dest), garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, use_objstms=1)
    finally:
        doc.close()
    after = os.path.getsize(dest)
    if after >= before:
        dest.unlink(missing_ok=True)
        return {"ok": False, "before": before, "after": after,
                "reason": "El archivo ya estaba bien comprimido: no se ha podido reducir más."}
    return {"ok": True, "out": str(dest), "before": before, "after": after}


# ── Bloquear / desbloquear ────────────────────────────────────────────────
def lock(path: str, user_pw: str, owner_pw: str = "", allow_print: bool = True, allow_copy: bool = False,
         allow_edit: bool = False, allow_annot: bool = False, password: str = "") -> str:
    """Cifra con AES-256. user_pw: para abrirlo (puede ir vacío si solo se quieren restricciones).
    owner_pw: para quitar las restricciones (si va vacío se usa la de apertura)."""
    if not user_pw and not (not allow_print or not allow_copy or not allow_edit or not allow_annot):
        raise ToolError("Escribe una contraseña de apertura o quita algún permiso.")
    perm = int(fitz.PDF_PERM_ACCESSIBILITY)
    if allow_print:
        perm |= int(fitz.PDF_PERM_PRINT) | int(fitz.PDF_PERM_PRINT_HQ)
    if allow_copy:
        perm |= int(fitz.PDF_PERM_COPY)
    if allow_edit:
        perm |= int(fitz.PDF_PERM_MODIFY) | int(fitz.PDF_PERM_ASSEMBLE) | int(fitz.PDF_PERM_FORM)
    if allow_annot:
        perm |= int(fitz.PDF_PERM_ANNOTATE) | int(fitz.PDF_PERM_FORM)
    doc = _open(path, password)
    try:
        dest = out_path(path, "_protegido")
        doc.save(str(dest), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=user_pw,
                 owner_pw=owner_pw or user_pw or os.urandom(8).hex(), permissions=perm, garbage=3, deflate=True)
    finally:
        doc.close()
    return str(dest)


def _has_encrypt_dict(doc) -> bool:
    """El archivo declara cifrado aunque se abra sin contraseña (solo restricciones de uso)."""
    try:
        return doc.xref_get_key(-1, "Encrypt")[0] != "null"
    except Exception:
        return False


def unlock(path: str, password: str = "") -> dict:
    """Quita la protección. Si hace falta contraseña de apertura y no es correcta, ToolError. Las restricciones
    sin contraseña de apertura (no copiar, no imprimir…) se quitan sin más."""
    doc = fitz.open(path)
    try:
        was_encrypted = doc.is_encrypted or _has_encrypt_dict(doc)
        needed = doc.needs_pass
        if needed and (not password or not doc.authenticate(password)):
            raise ToolError("Contraseña incorrecta." if password else "Este PDF necesita su contraseña para abrirse.")
        if not was_encrypted:
            raise ToolError("Este PDF no tiene ninguna protección.")
        dest = out_path(path, "_desbloqueado")
        doc.save(str(dest), encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
    finally:
        doc.close()
    return {"out": str(dest), "needed_password": needed}


# ── Marca de agua ─────────────────────────────────────────────────────────
WM_COLORS = {"Gris": (0.5, 0.5, 0.5), "Rojo": (0.8, 0.1, 0.1), "Azul": (0.1, 0.3, 0.8), "Negro": (0, 0, 0),
             "Verde": (0.1, 0.55, 0.25)}


def parse_pages(spec: str, n: int) -> list:
    """'1-3, 5, 8-' → [0,1,2,4,7,…] (base 0). Vacío = todas. 'impares' / 'pares' también valen."""
    spec = (spec or "").strip().lower()
    if not spec or spec in ("todas", "all"):
        return list(range(n))
    if spec.startswith("impar"):
        return list(range(0, n, 2))
    if spec.startswith("par"):
        return list(range(1, n, 2))
    out = set()
    for part in spec.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if m:
            a = int(m.group(1)) if m.group(1) else 1
            b = int(m.group(2)) if m.group(2) else n
            out.update(range(max(a, 1) - 1, min(b, n)))
        elif part.isdigit():
            if 1 <= int(part) <= n:
                out.add(int(part) - 1)
        else:
            raise ToolError(f"No entiendo «{part}» en las páginas. Usa por ejemplo: 1-3, 5, 8-")
    return sorted(out)


def _wm_font():
    """Arial de Windows (tiene tildes y ñ); si no, la fuente estándar del PDF."""
    for p in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"):
        if os.path.exists(p):
            return p
    return None


def watermark(path: str, text: str = "", image: str = "", opacity: float = 0.25, angle: float = 45.0,
              size: float = 0.0, color: str = "Gris", pages: str = "", tile: bool = False,
              password: str = "") -> str:
    """Marca de agua de texto o imagen en las páginas elegidas. size=0: automático (ocupa ~70 % del ancho).
    El texto se pinta con transparencia y queda detrás del contenido, para no tapar nada."""
    text = (text or "").strip()
    if not text and not image:
        raise ToolError("Escribe el texto de la marca de agua o elige una imagen.")
    doc = _open(path, password)
    try:
        idx = parse_pages(pages, len(doc))
        if not idx:
            raise ToolError("Esas páginas no existen en este documento.")
        col = WM_COLORS.get(color, WM_COLORS["Gris"])
        fontfile = _wm_font()
        fname = f"wm{abs(hash(fontfile or 'helv')) % 10 ** 6}"
        for i in idx:
            page = doc[i]
            r = page.rect
            if image:
                iw, ih = fitz.Pixmap(image).width, fitz.Pixmap(image).height
                w = r.width * 0.6
                h = w * ih / max(iw, 1)
                centers = [fitz.Point(r.width / 2, r.height / 2)]
                if tile:
                    centers = [fitz.Point(x, y) for y in (r.height * 0.2, r.height * 0.5, r.height * 0.8)
                               for x in (r.width * 0.25, r.width * 0.75)]
                    w, h = r.width * 0.3, r.width * 0.3 * ih / max(iw, 1)
                for c in centers:
                    box = fitz.Rect(c.x - w / 2, c.y - h / 2, c.x + w / 2, c.y + h / 2)
                    _stamp_image_alpha(doc, page, box, image, opacity, angle)
                continue
            font = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font("helv")
            ca, sa = abs(math.cos(math.radians(angle))), abs(math.sin(math.radians(angle)))
            span_w = 0.34 if tile else 0.86                      # fracción de la página que puede ocupar
            lmax = min(r.width * span_w / max(ca, 0.12), r.height * (0.3 if tile else 0.86) / max(sa, 0.12))
            fs = size or max(10.0, min(140.0, 100.0 * lmax / max(font.text_length(text, fontsize=100), 1)))
            tw_w = font.text_length(text, fontsize=fs)
            centers = [fitz.Point(r.width / 2, r.height / 2)]
            if tile:
                centers = [fitz.Point(x, y) for y in (r.height * 0.18, r.height * 0.5, r.height * 0.82)
                           for x in (r.width * 0.27, r.width * 0.73)]
            for c in centers:
                origin = fitz.Point(c.x - tw_w / 2, c.y + fs * 0.3)
                morph = (c, fitz.Matrix(-angle)) if angle else None
                page.insert_text(origin, text, fontsize=fs, fontname=fname, fontfile=fontfile, color=col,
                                 fill_opacity=opacity, stroke_opacity=opacity, overlay=False, morph=morph)
        dest = out_path(path, "_marca")
        doc.save(str(dest), garbage=3, deflate=True)
    finally:
        doc.close()
    return str(dest)


def _stamp_image_alpha(doc, page, box, image_path, opacity, angle):
    """Imagen con opacidad y giro cualquiera (se prepara con Pillow y se inserta como PNG con transparencia)."""
    import io
    from PIL import Image
    try:
        im = Image.open(image_path).convert("RGBA")
    except Exception:
        raise ToolError("No se pudo leer la imagen de la marca de agua.")
    alpha = im.getchannel("A").point(lambda v: int(v * max(0.0, min(1.0, opacity))))
    im.putalpha(alpha)
    im.thumbnail((1600, 1600))
    if angle:
        im = im.rotate(angle, expand=True, resample=Image.BICUBIC)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    ratio = im.height / im.width
    w = box.width
    rect = fitz.Rect(cx - w / 2, cy - w * ratio / 2, cx + w / 2, cy + w * ratio / 2)
    page.insert_image(rect, stream=buf.getvalue(), overlay=False, keep_proportion=True)


# ── Aplanar ───────────────────────────────────────────────────────────────
def flatten(path: str, annots: bool = True, widgets: bool = True, password: str = "") -> dict:
    """Convierte anotaciones y campos de formulario en contenido fijo de la página."""
    doc = _open(path, password)
    try:
        n_ann = sum(len(list(doc[i].annots() or [])) for i in range(len(doc)))
        n_wid = sum(len(list(doc[i].widgets() or [])) for i in range(len(doc)))
        if not ((annots and n_ann) or (widgets and n_wid)):
            raise ToolError("No hay anotaciones ni campos de formulario que aplanar.")
        doc.bake(annots=annots, widgets=widgets)
        dest = out_path(path, "_aplanado")
        doc.save(str(dest), garbage=3, deflate=True)
    finally:
        doc.close()
    return {"out": str(dest), "annots": n_ann if annots else 0, "widgets": n_wid if widgets else 0}


# ── Reparar ───────────────────────────────────────────────────────────────
def repair(path: str, password: str = "") -> dict:
    """Reconstruye el PDF: PyMuPDF rehace la tabla de objetos si está dañada y se guarda limpio. Si falla, lo
    intenta con pikepdf. {"out", "was_damaged", "pages", "engine"}."""
    try:
        doc = fitz.open(path)
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                raise ToolError("Este PDF tiene contraseña: desbloquéalo antes de repararlo.")
        was = bool(getattr(doc, "is_repaired", False))
        n = len(doc)
        if n == 0:
            raise RuntimeError("sin páginas")
        dest = out_path(path, "_reparado")
        doc.save(str(dest), garbage=4, clean=True, deflate=True)
        doc.close()
        chk = fitz.open(str(dest))
        ok_pages = 0
        for i in range(len(chk)):
            try:
                chk[i].get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
                ok_pages += 1
            except Exception:
                pass
        chk.close()
        return {"out": str(dest), "was_damaged": was, "pages": n, "readable": ok_pages, "engine": "PyMuPDF"}
    except ToolError:
        raise
    except Exception:
        pass
    try:
        import pikepdf
        dest = out_path(path, "_reparado")
        with pikepdf.open(path, password=password or "", attempt_recovery=True) as pdf:
            pdf.save(str(dest))
        chk = fitz.open(str(dest))
        n = len(chk)
        chk.close()
        return {"out": str(dest), "was_damaged": True, "pages": n, "readable": n, "engine": "pikepdf"}
    except Exception:
        raise ToolError("No se ha podido reparar: el archivo está demasiado dañado o no es un PDF.")


# ── Convertir a PDF ───────────────────────────────────────────────────────
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
TEXT_EXT = {".txt", ".log", ".csv"}
HTML_EXT = {".html", ".htm"}
OFFICE_EXT = {".doc", ".docx", ".rtf", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp"}
NATIVE_EXT = {".xps", ".oxps", ".epub", ".svg", ".cbz", ".mobi", ".fb2"}
PAGE_SIZES = {"A4": (595.28, 841.89), "Carta": (612, 792)}


def supported_extensions() -> list:
    return sorted(IMAGE_EXT | TEXT_EXT | HTML_EXT | {".md"} | OFFICE_EXT | NATIVE_EXT)


def images_to_pdf(paths: list, page_size: str = "A4", margin: float = 24.0, dest_name: str = "") -> str:
    """Una imagen por página. page_size 'Ajustar' = cada página del tamaño de su imagen; 'A4'/'Carta' = centrada."""
    if not paths:
        raise ToolError("No hay imágenes.")
    doc = fitz.open()
    for p in paths:
        try:
            img = fitz.open(p)                                    # soporta también TIFF de varias páginas
            for k in range(len(img)):
                pix = img[k].get_pixmap(dpi=150) if len(img) > 1 else None
                src = fitz.Pixmap(p) if pix is None else pix
                w, h = src.width * 72 / 96, src.height * 72 / 96
                if page_size == "Ajustar":
                    page = doc.new_page(width=w, height=h)
                    rect = page.rect
                else:
                    pw, ph = PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])
                    if w > h:
                        pw, ph = ph, pw
                    page = doc.new_page(width=pw, height=ph)
                    rect = fitz.Rect(margin, margin, pw - margin, ph - margin)
                if pix is None:
                    page.insert_image(rect, filename=p)
                else:
                    page.insert_image(rect, pixmap=pix)
            img.close()
        except Exception:
            doc.close()
            raise ToolError(f"No se pudo leer la imagen «{Path(p).name}».")
    dest = _unique(DOWNLOADS / ((dest_name or (Path(paths[0]).stem if len(paths) == 1 else "imagenes")) + ".pdf"))
    doc.save(str(dest), garbage=3, deflate=True)
    doc.close()
    return str(dest)


_CSS = ("body{font-family:sans-serif;font-size:11pt;line-height:1.35;} h1{font-size:20pt;} h2{font-size:16pt;} "
        "h3{font-size:13pt;} pre,code{font-family:monospace;font-size:9.5pt;} table{border-collapse:collapse;} "
        "td,th{border:1px solid #999;padding:3px 6px;} blockquote{margin-left:14pt;color:#555;}")


def _md_to_html(text: str) -> str:
    """Markdown básico: títulos, negrita, cursiva, código, listas, citas y enlaces."""
    out, in_list, in_code = [], None, False
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None
    for line in text.splitlines():
        if line.strip().startswith("```"):
            close_list()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            close_list()
            out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>")
            continue
        m = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)", line)
        if m:
            tag = "ol" if m.group(1)[0].isdigit() else "ul"
            if in_list != tag:
                close_list()
                out.append(f"<{tag}>")
                in_list = tag
            out.append(f"<li>{inline(m.group(2))}</li>")
            continue
        close_list()
        if line.startswith(">"):
            out.append(f"<blockquote>{inline(line.lstrip('> '))}</blockquote>")
        elif line.strip() in ("---", "***"):
            out.append("<hr/>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    close_list()
    return "\n".join(out)


def _read_text(path: str) -> str:
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _html_to_pdf(html_text: str, dest: Path, base_dir: str, page_size: str = "A4"):
    pw, ph = PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])
    mediabox = fitz.Rect(0, 0, pw, ph)
    where = mediabox + (48, 48, -48, -48)
    story = fitz.Story(html=html_text, user_css=_CSS, archive=fitz.Archive(base_dir) if base_dir else None)
    writer = fitz.DocumentWriter(str(dest))
    more = 1
    guard = 0
    while more and guard < 2000:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
        guard += 1
    writer.close()


def text_to_pdf(path: str, page_size: str = "A4") -> str:
    ext = Path(path).suffix.lower()
    text = _read_text(path)
    if ext == ".md":
        body = _md_to_html(text)
    elif ext in HTML_EXT:
        body = text
    else:
        body = "<pre>" + html.escape(text) + "</pre>"
    dest = out_path(path, "")
    if dest.suffix.lower() != ".pdf":
        dest = dest.with_suffix(".pdf")
    try:
        _html_to_pdf(body, dest, str(Path(path).parent) if ext in HTML_EXT else "", page_size)
    except Exception:
        dest.unlink(missing_ok=True)
        raise ToolError("No se pudo convertir ese archivo de texto.")
    return str(dest)


def native_to_pdf(path: str) -> str:
    """XPS, EPUB, SVG, CBZ… que PyMuPDF abre directamente."""
    try:
        doc = fitz.open(path)
        data = doc.convert_to_pdf()
        doc.close()
        pdf = fitz.open("pdf", data)
        dest = out_path(path, "")
        dest = dest.with_suffix(".pdf")
        pdf.save(str(dest), garbage=3, deflate=True)
        pdf.close()
        return str(dest)
    except Exception:
        raise ToolError("No se pudo convertir ese archivo.")


# La conversión con el propio Word/Excel/PowerPoint (automatización COM) está DESACTIVADA hasta verificarla: en las
# primeras pruebas fallaba y dejaba procesos de Office abiertos. LibreOffice (línea de comandos) sí está activa.
OFFICE_COM_ENABLED = False


def office_engines() -> dict:
    """Qué programas hay en este equipo para convertir Word/Excel/PowerPoint."""
    found = {"word": False, "excel": False, "powerpoint": False, "libreoffice": None}
    if os.name == "nt":
        for key, prog in (("word", "Word.Application"), ("excel", "Excel.Application"),
                          ("powerpoint", "PowerPoint.Application")):
            try:
                r = subprocess.run(["reg", "query", rf"HKCR\{prog}\CLSID"], capture_output=True, timeout=5,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                found[key] = r.returncode == 0
            except Exception:
                pass
    for cand in (shutil.which("soffice"), r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if cand and os.path.exists(cand):
            found["libreoffice"] = cand
            break
    return found


_PS_WORD = r'''
$ErrorActionPreference = "Stop"
$src = $env:PDFM_SRC; $dst = $env:PDFM_DST; $app = $null
try {
  $app = New-Object -ComObject Word.Application
  $app.Visible = $false; $app.DisplayAlerts = 0
  try { $app.AutomationSecurity = 3 } catch {}
  $doc = $app.Documents.Open($src, $false, $true)
  $doc.ExportAsFixedFormat($dst, 17)
  $doc.Close($false)
} finally { if ($app) { $app.Quit() } }
'''
_PS_EXCEL = r'''
$ErrorActionPreference = "Stop"
$src = $env:PDFM_SRC; $dst = $env:PDFM_DST; $app = $null
try {
  $app = New-Object -ComObject Excel.Application
  $app.Visible = $false; $app.DisplayAlerts = $false
  try { $app.AutomationSecurity = 3 } catch {}
  $wb = $app.Workbooks.Open($src, 0, $true)
  $wb.ExportAsFixedFormat(0, $dst)
  $wb.Close($false)
} finally { if ($app) { $app.Quit() } }
'''
_PS_PPT = r'''
$ErrorActionPreference = "Stop"
$src = $env:PDFM_SRC; $dst = $env:PDFM_DST; $app = $null
try {
  $app = New-Object -ComObject PowerPoint.Application
  $p = $app.Presentations.Open($src, -1, 0, 0)
  $p.SaveAs($dst, 32)
  $p.Close()
} finally { if ($app) { $app.Quit() } }
'''


def _kill_office(kind: str):
    exe = {"word": "WINWORD.EXE", "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE"}[kind]
    try:
        subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def office_to_pdf(path: str) -> str:
    """Word/Excel/PowerPoint con el propio Office si está instalado (sin macros, en modo solo lectura) o, si no,
    con LibreOffice. Si no hay ninguno, ToolError explicando qué instalar."""
    ext = Path(path).suffix.lower()
    eng = office_engines()
    kind = ("word" if ext in (".doc", ".docx", ".rtf", ".odt") else
            "excel" if ext in (".xls", ".xlsx", ".ods") else "powerpoint")
    dest = out_path(path, "").with_suffix(".pdf")
    names0 = {"word": "Microsoft Word", "excel": "Microsoft Excel", "powerpoint": "Microsoft PowerPoint"}
    tried = []
    if eng.get(kind) and OFFICE_COM_ENABLED:
        script = {"word": _PS_WORD, "excel": _PS_EXCEL, "powerpoint": _PS_PPT}[kind]
        env = dict(os.environ, PDFM_SRC=str(Path(path).resolve()), PDFM_DST=str(dest.resolve()))
        try:
            tried.append(names0[kind])
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-Command", script], capture_output=True, timeout=180, env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0 and dest.exists():
                return str(dest)
        except subprocess.TimeoutExpired:
            _kill_office(kind)
            raise ToolError(f"{names0[kind]} ha tardado demasiado y se ha cancelado la conversión (¿archivo muy "
                            "grande o con una ventana pendiente de confirmar?).")
        except Exception:
            pass
    if eng.get("libreoffice"):
        tmp = tempfile.mkdtemp(prefix="pdfm_lo_")
        try:
            tried.append("LibreOffice")
            subprocess.run([eng["libreoffice"], "--headless", "--norestore", "--convert-to", "pdf", "--outdir", tmp,
                            str(Path(path).resolve())], capture_output=True, timeout=240,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            made = Path(tmp) / (Path(path).stem + ".pdf")
            if made.exists():
                shutil.move(str(made), str(dest))
                return str(dest)
        except Exception:
            pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    names = names0
    if tried:
        raise ToolError(f"No se pudo convertir con {' ni con '.join(tried)}: el archivo puede estar dañado, protegido "
                        "con contraseña o ser de un formato que ese programa no abre.")
    raise ToolError("Para convertir Word, Excel o PowerPoint hace falta tener LibreOffice (gratuito, libreoffice.org) "
                    "instalado; no lo he encontrado. Mientras tanto, abre el archivo en su programa y guárdalo como "
                    "PDF (Archivo → Guardar como → PDF).")


def convert_to_pdf(paths: list, page_size: str = "A4") -> list:
    """Convierte varios archivos. Devuelve [(origen, ruta_pdf_o_None, mensaje_de_error)]. Las imágenes se juntan
    en un solo PDF si son varias y todas imágenes ('Ajustar' / A4 / Carta)."""
    results = []
    imgs = [p for p in paths if Path(p).suffix.lower() in IMAGE_EXT]
    others = [p for p in paths if p not in imgs]
    if imgs:
        try:
            out = images_to_pdf(imgs, page_size)
            results.append((", ".join(Path(p).name for p in imgs)[:80], out, ""))
        except ToolError as e:
            results.append((imgs[0], None, str(e)))
    for p in others:
        ext = Path(p).suffix.lower()
        try:
            if ext in TEXT_EXT or ext in HTML_EXT or ext == ".md":
                out = text_to_pdf(p, page_size)
            elif ext in OFFICE_EXT:
                out = office_to_pdf(p)
            elif ext in NATIVE_EXT:
                out = native_to_pdf(p)
            else:
                raise ToolError(f"No sé convertir archivos «{ext}».")
            results.append((p, out, ""))
        except ToolError as e:
            results.append((p, None, str(e)))
    return results


# ── OCR ───────────────────────────────────────────────────────────────────
# Idiomas que vienen incluidos con el programa (carpeta «tessdata» junto al .exe); el resto se descarga a demanda.
DEFAULT_LANGS = ("spa", "por", "eng")
LANG_NAMES = {
    "spa": "Español", "por": "Portugués", "eng": "Inglés", "fra": "Francés", "deu": "Alemán", "ita": "Italiano",
    "cat": "Catalán", "glg": "Gallego", "eus": "Euskera", "nld": "Neerlandés", "dan": "Danés", "nor": "Noruego",
    "swe": "Sueco", "fin": "Finés", "pol": "Polaco", "ces": "Checo", "slk": "Eslovaco", "slv": "Esloveno",
    "hun": "Húngaro", "ron": "Rumano", "bul": "Búlgaro", "hrv": "Croata", "srp": "Serbio", "ell": "Griego",
    "tur": "Turco", "rus": "Ruso", "ukr": "Ucraniano", "heb": "Hebreo", "ara": "Árabe", "hin": "Hindi",
    "chi_sim": "Chino simplificado", "chi_tra": "Chino tradicional", "jpn": "Japonés", "kor": "Coreano",
    "tha": "Tailandés", "vie": "Vietnamita", "ind": "Indonesio", "lat": "Latín",
}
TESSDATA_FAST_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"


def user_tessdata_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "PDFManager" / "tessdata"


def tessdata_dirs() -> list:
    """Carpetas donde buscar idiomas, por orden: junto al programa (instalador), carpeta del usuario, Tesseract
    instalado, TESSDATA_PREFIX."""
    dirs = []
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    dirs += [base / "tessdata", Path(sys.executable).parent / "tessdata", user_tessdata_dir()]
    for p in (r"C:\Program Files\Tesseract-OCR\tessdata", r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
              os.environ.get("TESSDATA_PREFIX") or ""):
        if p:
            dirs.append(Path(p))
    return [d for d in dirs if d.is_dir()]


def available_languages() -> dict:
    """{código: carpeta} de los idiomas con datos disponibles (osd no es un idioma)."""
    found = {}
    for d in tessdata_dirs():
        for f in d.glob("*.traineddata"):
            if f.stem != "osd":
                found.setdefault(f.stem, str(d))
    return found


def ocr_needed_pages(doc, min_chars: int = 25) -> list:
    """Páginas sin texto real (escaneadas)."""
    out = []
    for i in range(len(doc)):
        if len(doc[i].get_text().strip()) < min_chars:
            out.append(i)
    return out


def _ascii_tessdata(languages: list, avail: dict) -> str:
    """Tesseract en Windows no abre archivos cuyo camino tenga tildes, ñ u otros caracteres no ASCII (por ejemplo
    una carpeta de usuario con tilde). Se copian los idiomas pedidos a una carpeta de ruta sencilla y se usa esa."""
    cands = [Path(tempfile.gettempdir()) / "pdfm_tessdata",
             Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "PDFManager" / "tessdata",
             Path(r"C:\Users\Public\PDFManager\tessdata")]
    for d in cands:
        if not str(d).isascii():
            continue
        try:
            d.mkdir(parents=True, exist_ok=True)
            for lang in languages:
                src = Path(avail[lang]) / f"{lang}.traineddata"
                dst = d / f"{lang}.traineddata"
                if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                    shutil.copy2(src, dst)
            return str(d)
        except OSError:
            continue
    if all(str(Path(avail[l])).isascii() for l in languages) and len({avail[l] for l in languages}) == 1:
        return avail[languages[0]]
    raise ToolError("No encuentro una carpeta con ruta sencilla (sin tildes) donde preparar el idioma del OCR.")


def ocr(path: str, languages: list, dpi: int = 200, only_scanned: bool = True, password: str = "",
        progress=None) -> dict:
    """Añade una capa de texto invisible a las páginas escaneadas, sin cambiar su aspecto: el PDF pasa a poder
    buscarse y copiarse. `languages` p. ej. ['spa', 'eng']. progress(i, n) opcional."""
    avail = available_languages()
    missing = [l for l in languages if l not in avail]
    if not languages or missing:
        raise ToolError("Faltan los datos del idioma: " + ", ".join(LANG_NAMES.get(l, l) for l in (missing or ["?"])))
    folder = _ascii_tessdata(languages, avail)
    doc = _open(path, password)
    try:
        pages = ocr_needed_pages(doc) if only_scanned else list(range(len(doc)))
        if not pages:
            raise ToolError("Todas las páginas ya tienen texto: no hay nada que reconocer.")
        lang = "+".join(languages)
        for k, i in enumerate(pages):
            if progress:
                progress(k, len(pages))
            page = doc[i]
            pm = page.get_pixmap(dpi=dpi)
            layer = fitz.open("pdf", pm.pdfocr_tobytes(language=lang, tessdata=folder))
            keep = page.rect
            new = doc.new_page(pno=i + 1, width=keep.width, height=keep.height)
            new.show_pdf_page(new.rect, layer, 0)
            layer.close()
            doc.delete_page(i)
        dest = out_path(path, "_ocr")
        doc.save(str(dest), garbage=3, deflate=True)
        words = sum(len(doc[i].get_text().split()) for i in pages)
    finally:
        doc.close()
    if progress:
        progress(len(pages), len(pages))
    return {"out": str(dest), "pages": len(pages), "words": words}


def download_language(lang: str, timeout: int = 60, dest_dir: Path | None = None) -> Path:
    """Descarga los datos de un idioma (tessdata_fast, de los autores de Tesseract) a la carpeta del usuario."""
    import requests
    if lang not in LANG_NAMES:
        raise ToolError("Idioma no válido.")
    dest_dir = Path(dest_dir) if dest_dir else user_tessdata_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(TESSDATA_FAST_URL.format(lang=lang), timeout=timeout,
                         headers={"User-Agent": "PDFManager/1.0 (descarga de idioma pedida por el usuario)"})
        r.raise_for_status()
    except requests.RequestException as e:
        raise ToolError("No se pudo descargar el idioma. Comprueba tu conexión a internet.") from e
    data = r.content
    if len(data) < 50_000 or len(data) > 80 * 1024 * 1024:
        raise ToolError("El archivo descargado no parece un idioma válido.")
    target = dest_dir / f"{lang}.traineddata"
    target.write_bytes(data)
    return target
