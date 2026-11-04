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


# ── Preparación de la imagen para el OCR ─────────────────────────────────
def _pil_from_pix(pix):
    from PIL import Image
    if pix.colorspace is None or pix.colorspace.n != 3 or pix.alpha:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _otsu(a):
    import numpy as np
    hist, _ = np.histogram(a, bins=256, range=(0, 256))
    tot, s = a.size, float(np.dot(np.arange(256), hist))
    sum_b = w_b = 0.0
    best, thr = 0.0, 128
    for k in range(256):
        w_b += hist[k]
        if w_b == 0:
            continue
        w_f = tot - w_b
        if w_f == 0:
            break
        sum_b += k * hist[k]
        v = w_b * w_f * (sum_b / w_b - (s - sum_b) / w_f) ** 2
        if v > best:
            best, thr = v, k
    return thr


def _noise_level(gray) -> tuple:
    """(ruido de fondo, fracción de píxeles sueltos): 0 en imágenes limpias, ~20 en escaneos ruidosos."""
    import numpy as np
    from PIL import ImageFilter
    a = np.asarray(gray, dtype=np.float32)
    med = np.asarray(gray.filter(ImageFilter.MedianFilter(3)), dtype=np.float32)
    gy, gx = np.gradient(np.asarray(gray.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32))
    flat = np.hypot(gx, gy) < 2.0
    r = (a - med)[flat] if flat.sum() > 1000 else (a - med).ravel()
    noise = float(1.4826 * np.median(np.abs(r - np.median(r))))
    speck = float((np.abs(a - med) > 90).mean())
    return noise, speck


def _deskew_angle(gray, rng: float = 20.0) -> float:
    """Inclinación del texto (grados a aplicar para enderezarlo), hasta ±20°. Prueba giros y se queda con el que deja
    las líneas de letras más nítidas (las bases de las letras se alinean y el perfil de filas se afila): primero a pasos
    de 1° y después afinando alrededor del mejor."""
    import numpy as np
    from PIL import Image
    sm = gray.resize((700, max(1, int(gray.height * 700 / max(gray.width, 1)))))
    a = np.asarray(sm)
    bw = Image.fromarray(((a < _otsu(a)) * 255).astype(np.uint8))

    def score(ang: float) -> float:
        prof = np.asarray(bw.rotate(float(ang), resample=Image.BILINEAR, fillcolor=0), dtype=np.float32).sum(axis=1)
        return float(np.sum(np.diff(prof) ** 2))
    coarse = {float(x): score(x) for x in np.arange(-rng, rng + 1e-6, 1.0)}
    best = max(coarse, key=coarse.get)
    fine = {float(x): score(x) for x in np.arange(best - 1.0, best + 1.0 + 1e-6, 0.2)}
    best = max(fine, key=fine.get)
    return best if abs(best) >= 0.2 else 0.0


def _runs_mask(dark, length: int, axis: int):
    """Máscara de los píxeles que forman parte de un tramo recto oscuro de al menos `length` píxeles."""
    import numpy as np
    m = dark if axis == 1 else dark.T
    h, w = m.shape
    if w <= length:
        return np.zeros_like(dark)
    cs = np.cumsum(np.pad(m.astype(np.int32), ((0, 0), (1, 0))), axis=1)
    starts = ((cs[:, length:] - cs[:, :-length]) == length).astype(np.int32)         # inicios de ventanas oscuras
    c2 = np.cumsum(np.pad(starts, ((0, 0), (1, 0))), axis=1)
    n_starts = c2.shape[1] - 1
    out = np.zeros((h, w), dtype=bool)
    idx = np.arange(w)
    hi = np.minimum(idx, n_starts - 1) + 1
    lo = np.maximum(idx - length + 1, 0)
    out = (c2[:, hi] - c2[:, lo]) > 0
    return out if axis == 1 else out.T


def _find_rules(gray):
    """Líneas de tabla: ([(y, x0, x1)], [(x, y0, y1)], máscara de píxeles de línea). Coordenadas en píxeles."""
    import numpy as np
    a = np.asarray(gray)
    dark = a < min(_otsu(a), 140)
    hgt, wid = dark.shape
    mh = _runs_mask(dark, max(60, int(wid * 0.08)), 1)
    mv = _runs_mask(dark, max(60, int(hgt * 0.05)), 0)

    def bands(mask, along_rows: bool):
        prof = mask.sum(axis=1 if along_rows else 0)
        thr = (mask.shape[1] if along_rows else mask.shape[0]) * 0.08
        idx = np.nonzero(prof >= thr)[0]
        out, start = [], None
        for i, k in enumerate(idx):
            if start is None:
                start = prev = k
            elif k - prev > 2:
                out.append((start, prev))
                start = k
            prev = k
        if start is not None:
            out.append((start, prev))
        lines = []
        for s, e in out:
            if e - s > 8:                                        # demasiado grueso: es texto o un bloque, no una línea
                continue
            sel = mask[s:e + 1].any(axis=0) if along_rows else mask[:, s:e + 1].any(axis=1)
            pos = np.nonzero(sel)[0]
            if not len(pos):
                continue
            runs, a0, pv = [], pos[0], pos[0]
            for p in pos[1:]:
                if p - pv > 25:
                    runs.append((a0, pv))
                    a0 = p
                pv = p
            runs.append((a0, pv))
            for r0, r1 in runs:
                if r1 - r0 >= (mask.shape[1] if along_rows else mask.shape[0]) * 0.08:
                    lines.append(((s + e) / 2.0, float(r0), float(r1)))
        return lines
    h_lines = bands(mh, True)
    v_lines = bands(mv, False)
    if len(h_lines) > 60 or len(v_lines) > 60:                   # demasiadas «líneas»: se está leyendo texto o ruido
        return [], [], None
    clear = mh | mv
    if clear.sum() > 0.35 * max(int(dark.sum()), 1):             # lo detectado es gran parte de la tinta: no son líneas
        return [], [], None
    if clear.any():                                              # engrosa 1 píxel para borrar también el borde
        c = clear.copy()
        c[1:] |= clear[:-1]; c[:-1] |= clear[1:]
        c[:, 1:] |= clear[:, :-1]; c[:, :-1] |= clear[:, 1:]
        clear = c
    return h_lines, v_lines, clear


def prepare_image(pix, enhance: bool = True, dpi: int = 200) -> dict:
    """Imagen lista para el OCR y lo necesario para volver a las coordenadas de la página:
    {"img", "w", "h" (tamaño tras enderezar), "angle", "factor", "h_lines", "v_lines", "noise", "mode"}."""
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps
    im = _pil_from_pix(pix)
    gray = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    mode, factor, angle = "original", 1.0, 0.0
    noise = speck = 0.0
    if enhance:
        noise, speck = _noise_level(gray)
        if noise >= 27 or speck >= 0.04:
            gray = gray.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
            mode, factor = "ruido alto", 2.0
        elif noise >= 3:
            gray = gray.filter(ImageFilter.MedianFilter(3))
            mode, factor = "ruido medio", 1.5
        else:
            mode, factor = "limpia", (300.0 / dpi if dpi < 200 else 1.0)
        angle = _deskew_angle(gray)
        if angle:
            gray = gray.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    w, h = gray.size
    h_lines, v_lines, clear = _find_rules(gray) if (enhance and mode != "ruido alto") else ([], [], None)
    if clear is not None and clear.any():
        arr = np.asarray(gray).copy()
        arr[clear] = 255
        gray = Image.fromarray(arr)
    if factor != 1.0:
        gray = gray.resize((int(w * factor), int(h * factor)), Image.LANCZOS)
    return {"img": gray.convert("RGB"), "w": w, "h": h, "angle": angle, "factor": factor,
            "h_lines": h_lines, "v_lines": v_lines, "noise": noise, "mode": mode}


def _text_font():
    for p in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\calibri.ttf"):
        if os.path.exists(p):
            return p
    return None


def _ocr_layer(prep: dict, lang: str, folder: str):
    """Texto reconocido: [(x0, y0, x1, y1, texto)] en píxeles de la imagen enderezada (sin ampliar)."""
    pm = fitz.Pixmap(fitz.csRGB, prep["img"].width, prep["img"].height, prep["img"].tobytes(), False)
    layer = fitz.open("pdf", pm.pdfocr_tobytes(language=lang, tessdata=folder))
    lp = layer[0]
    sx, sy = prep["img"].width / lp.rect.width, prep["img"].height / lp.rect.height
    f = prep["factor"]
    out = [(w[0] * sx / f, w[1] * sy / f, w[2] * sx / f, w[3] * sy / f, w[4]) for w in lp.get_text("words")]
    layer.close()
    return out


def _page_rect_of(prep: dict, page_rect, w: tuple) -> tuple:
    """Caja de una palabra (píxeles de la imagen enderezada) → puntos de la página original."""
    import math
    cx, cy = prep["w"] / 2.0, prep["h"] / 2.0
    th = math.radians(prep["angle"])
    cs, sn = math.cos(th), math.sin(th)
    pts = []
    for x, y in ((w[0], w[1]), (w[2], w[1]), (w[2], w[3]), (w[0], w[3])):
        dx, dy = x - cx, y - cy
        pts.append((cx + dx * cs - dy * sn, cy + dx * sn + dy * cs))      # inversa del giro de PIL
    kx, ky = page_rect.width / prep["w"], page_rect.height / prep["h"]
    xs, ys = [p[0] * kx for p in pts], [p[1] * ky for p in pts]
    return (min(xs) + page_rect.x0, min(ys) + page_rect.y0, max(xs) + page_rect.x0, max(ys) + page_rect.y0)


def _write_invisible_text(page, words: list, fontfile):
    """Escribe las palabras (en el orden dado) como texto invisible, ajustado a su caja."""
    fname = "ocrtxt"
    font = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font("helv")
    for x0, y0, x1, y1, text in words:
        text = str(text)
        bh, bw = y1 - y0, x1 - x0
        if bh < 1 or bw < 1 or not text.strip():
            continue
        fs = max(3.0, bh * 0.92)
        tl = font.text_length(text, fontsize=fs)
        if tl <= 0:
            continue
        sx = max(0.25, min(4.0, bw / tl))
        base = fitz.Point(x0, y1 - bh * 0.2)
        try:
            page.insert_text(base, text, fontsize=fs, fontname=fname, fontfile=fontfile, render_mode=3,
                             morph=(base, fitz.Matrix(sx, 1)))
        except Exception:
            continue


def native_dpi(page) -> float:
    """Resolución real del escaneo de la página (píxeles de su imagen principal por pulgada), 0 si no hay."""
    try:
        best, area = 0.0, 0.0
        for info in page.get_image_info():
            bw = info["bbox"][2] - info["bbox"][0]
            bh = info["bbox"][3] - info["bbox"][1]
            if bw > 0 and bw * bh > area:
                area, best = bw * bh, info["width"] * 72.0 / bw
        return best
    except Exception:
        return 0.0


def render_dpi_for(page, dpi: int) -> int:
    """Se lee a la resolución del propio escaneo (sin reescalar, que disimula el ruido y emborrona), con un tope
    según la calidad elegida; si la página no es una imagen, a la calidad elegida."""
    nat = native_dpi(page)
    if nat <= 0:
        return dpi
    cap = {150: 220, 200: 300, 300: 400}.get(dpi, int(dpi * 1.4))
    return int(max(100, min(nat, cap)))


def ocr_page_words(page, languages: list, dpi: int = 200, enhance: bool = True, folder: str = "") -> dict:
    """OCR de una página sin modificarla: palabras, bloques de maquetación y cómo se ha preparado la imagen."""
    import layout_tools as lt
    dpi = render_dpi_for(page, dpi)
    pix = page.get_pixmap(dpi=dpi)
    prep = prepare_image(pix, enhance, dpi)
    words = _ocr_layer(prep, "+".join(languages), folder)
    blocks = lt.analyze(words, prep["h_lines"], prep["v_lines"])
    return {"prep": prep, "words": words, "blocks": blocks}


def ocr(path: str, languages: list, dpi: int = 200, only_scanned: bool = True, password: str = "",
        progress=None, enhance: bool = True) -> dict:
    """Añade una capa de texto invisible a las páginas escaneadas: la página original NO se toca (misma imagen,
    mismo peso), pero pasa a poder buscarse y copiarse, con el texto en orden de lectura (columnas separadas,
    tablas por filas, párrafos). `enhance` prepara la imagen (ruido, inclinación, líneas de tabla) antes de leer.
    `languages` p. ej. ['spa', 'eng']. progress(i, n) opcional."""
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
        import layout_tools as lt
        fontfile = _text_font()
        n_words = n_tables = 0
        for k, i in enumerate(pages):
            if progress:
                progress(k, len(pages))
            page = doc[i]
            if page.rotation:                                     # página girada: se reemplaza por su versión con texto
                _ocr_replace_page(doc, i, "+".join(languages), folder, dpi)
                n_words += len(doc[i].get_text().split())
                continue
            res = ocr_page_words(page, languages, dpi, enhance, folder)
            prep = res["prep"]
            ordered = [(*_page_rect_of(prep, page.rect, w), w[4]) for w in lt.ordered_words(res["blocks"])]
            _write_invisible_text(page, ordered, fontfile)
            n_words += len(ordered)
            n_tables += sum(1 for b in res["blocks"] if b.kind == "table")
        try:
            doc.subset_fonts()
        except Exception:
            pass
        dest = out_path(path, "_ocr")
        doc.save(str(dest), garbage=4, deflate=True)
    finally:
        doc.close()
    if progress:
        progress(len(pages), len(pages))
    return {"out": str(dest), "pages": len(pages), "words": n_words, "tables": n_tables}


def _ocr_replace_page(doc, i: int, lang: str, folder: str, dpi: int):
    """Plan B para páginas con giro: se sustituye la página por una imagen con la capa de texto."""
    page = doc[i]
    pm = page.get_pixmap(dpi=dpi)
    layer = fitz.open("pdf", pm.pdfocr_tobytes(language=lang, tessdata=folder))
    keep = page.rect
    new = doc.new_page(pno=i + 1, width=keep.width, height=keep.height)
    new.show_pdf_page(new.rect, layer, 0)
    layer.close()
    doc.delete_page(i)


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


# ── Maquetación de una página para copiar zonas ──────────────────────────
def page_layout(page, languages: list | None = None, dpi: int = 200, enhance: bool = True) -> dict:
    """Palabras, líneas y bloques de una página, listos para copiar zonas. Si la página tiene texto se usa tal cual;
    si es un escaneo se reconoce al momento (no se modifica el PDF). Todo queda en un mismo sistema de coordenadas
    ("espacio de análisis"), que para un escaneo girado es el de la imagen enderezada. Devuelve
    {"words", "h_lines", "v_lines", "blocks", "ocr", "angle", "w", "h", "rect"}."""
    import layout_tools as lt
    rect = page.rect
    words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
    if len(" ".join(w[4] for w in words)) >= 25:
        hl, vl = lt.lines_from_page(page)
        return {"words": words, "h_lines": hl, "v_lines": vl, "blocks": lt.analyze(words, hl, vl), "ocr": False,
                "angle": 0.0, "w": rect.width, "h": rect.height, "rect": rect}
    avail = available_languages()
    langs = [l for l in (languages or []) if l in avail] or [l for l in DEFAULT_LANGS if l in avail][:1]
    if not langs:
        raise ToolError("Esta página es una imagen y no hay ningún idioma de OCR instalado (Herramientas → OCR).")
    folder = _ascii_tessdata(langs, avail)
    res = ocr_page_words(page, langs, dpi, enhance, folder)
    prep = res["prep"]
    return {"words": res["words"], "h_lines": [(y / 1.0, x0, x1) for y, x0, x1 in prep["h_lines"]],
            "v_lines": prep["v_lines"], "blocks": res["blocks"], "ocr": True, "angle": prep["angle"],
            "w": prep["w"], "h": prep["h"], "rect": rect, "langs": langs}


def to_analysis_rect(entry: dict, rect: tuple) -> tuple:
    """Rectángulo en puntos de página → espacio de análisis de `page_layout`."""
    if not entry["ocr"]:
        return rect
    import math
    r = entry["rect"]
    kx, ky = entry["w"] / r.width, entry["h"] / r.height
    cx, cy = entry["w"] / 2.0, entry["h"] / 2.0
    th = math.radians(entry["angle"])
    cs, sn = math.cos(th), math.sin(th)
    pts = []
    for x, y in ((rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])):
        px, py = (x - r.x0) * kx, (y - r.y0) * ky
        dx, dy = px - cx, py - cy
        pts.append((cx + dx * cs + dy * sn, cy - dx * sn + dy * cs))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def from_analysis_rect(entry: dict, rect: tuple) -> tuple:
    """Rectángulo del espacio de análisis → puntos de página (para dibujar en pantalla)."""
    if not entry["ocr"]:
        return rect
    prep = {"w": entry["w"], "h": entry["h"], "angle": entry["angle"]}
    return _page_rect_of(prep, entry["rect"], rect)


def tables_to_xlsx(tables: list, dest: str) -> str:
    """Guarda cada tabla en una hoja de Excel. Los números con formato español (3.600,00 €) pasan a ser números."""
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for n, rows in enumerate(tables, 1):
        ws = wb.create_sheet(f"Tabla {n}")
        for r in rows:
            ws.append([_to_cell(c) for c in r])
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 8), 60)
    if not tables:
        raise ToolError("No hay tablas que guardar.")
    wb.save(dest)
    return dest


def _to_cell(text: str):
    s = (text or "").strip()
    m = re.fullmatch(r"([-+]?)\s?([€$£]?)\s?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s?([€$£%]?)", s)
    if not m:
        return s
    try:
        num = float(m.group(3).replace(".", "") + ("." + m.group(4) if m.group(4) else ""))
    except ValueError:
        return s
    if m.group(1) == "-":
        num = -num
    return int(num) if num == int(num) and not m.group(4) else num
