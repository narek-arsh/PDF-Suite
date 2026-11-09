# -*- coding: utf-8 -*-
"""
backend.py — Toda la lógica de manipulación de PDF, sin dependencias de UI.
Usada por la interfaz PySide6 (pdf_qt.py). Pensada para reutilizarse igual
desde cualquier otra interfaz futura.
"""
import difflib
import io
import itertools
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from pypdf import PdfReader, PdfWriter

import winfonts

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from PIL import Image, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

DOWNLOADS = Path.home() / "Downloads"
DOWNLOADS.mkdir(exist_ok=True)

# Paleta categórica: colores claramente distinguibles entre sí (no solo
# tonos tierra de la marca) para identificar de un vistazo de qué PDF viene
# cada página al mezclar varios archivos en Organize.
FILE_COLORS = [
    "#C08258",  # cobre (acento de marca)
    "#5B8DEF",  # azul
    "#E0607E",  # rosa
    "#6FCF97",  # verde
    "#BB86FC",  # lila
    "#F2C94C",  # amarillo
    "#56CCF2",  # cian
    "#EB5757",  # rojo coral
    "#9B51E0",  # violeta
    "#27AE97",  # verde azulado
    "#F2994A",  # naranja
    "#828BDB",  # azul grisáceo
]


def resource_path(relative: str) -> str:
    """Ruta correcta tanto en .py como en .exe (PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base / relative)


def label_for(fi: int, pi: int) -> str:
    return f"{chr(65 + fi)}{pi + 1}"


def safe_page_count(path: str) -> int:
    try:
        return len(PdfReader(path).pages)
    except Exception:
        return 0


_thumb_cache: dict = {}


def get_page_thumbnail_png(file_path: str, page_idx: int, rotation: int = 0,
                            width: int = 160) -> bytes | None:
    """Devuelve los bytes PNG de la miniatura de una página (para QPixmap)."""
    if not HAS_FITZ:
        return None
    try:
        mtime = Path(file_path).stat().st_mtime_ns
    except OSError:
        mtime = 0
    key = (file_path, mtime, page_idx, rotation, width)
    if key in _thumb_cache:
        return _thumb_cache[key]
    try:
        doc = fitz.open(file_path)
        pg = doc[page_idx]
        rect = pg.rect
        base_w = rect.height if rotation in (90, 270) else rect.width
        scale = width / base_w if base_w > 0 else 1
        mat = fitz.Matrix(scale, scale).prerotate(rotation)
        pix = pg.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        _thumb_cache[key] = png_bytes
        doc.close()
        return png_bytes
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


# ── MERGE / ORGANIZE ─────────────────────────────────────────────────────
def merge_pdfs(paths_in_order: list[str], out_path: str) -> None:
    writer = PdfWriter()
    for p in paths_in_order:
        for page in PdfReader(p).pages:
            writer.add_page(page)
    with open(out_path, "wb") as f:
        writer.write(f)


def organize_pdf(pages: list[dict], out_path: str) -> None:
    """pages: [{"path": str, "page_idx": int, "rotation": int}, ...]"""
    writer = PdfWriter()
    readers: dict[str, PdfReader] = {}
    for pg in pages:
        path = pg["path"]
        if path not in readers:
            readers[path] = PdfReader(path)
        page_obj = readers[path].pages[pg["page_idx"]]
        if pg.get("rotation"):
            page_obj.rotate(pg["rotation"])
        writer.add_page(page_obj)
    with open(out_path, "wb") as f:
        writer.write(f)


# ── CENSURA / BUSCAR Y REEMPLAZAR ────────────────────────────────────────
def censor_text_in_pdf(path: str, texto: str) -> str | None:
    """
    Busca 'texto' en todas las páginas y lo cubre con una caja negra sólida
    del tamaño exacto de la zona de texto (censura permanente, elimina el
    texto subyacente). Devuelve la ruta del PDF censurado o None.
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


_SYMBOL_FONT_FILE = Path(r"C:\Windows\Fonts\seguisym.ttf")
_FONT_SEQ = itertools.count(1)    # nombre de fuente nuevo en cada dibujo (reutilizarlo tras redactar la pierde)
_IGNORED_CHARS = {"\ufe0f", "\ufe0e", "\u200d"}   # selectores de variante y unión de emojis


def _rgb_tuple(color) -> tuple[float, float, float]:
    """Color de un span de PyMuPDF (entero 0xRRGGBB) -> (r, g, b) de 0 a 1."""
    c = int(color or 0)
    return ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)


def _insert_text_with_fallback(page, pos, text: str, size: float, fontfile: str | None = None,
                               color=(0, 0, 0), base14: str = "helv"):
    """Inserta texto en pos. Los caracteres que la fuente principal no tiene
    (emojis, símbolos) se dibujan con Segoe UI Symbol, en monocromo. Sin esos
    caracteres usa insert_text normal, igual que antes. base14 es la fuente
    de respaldo (helv, hebo, heit, hebi) cuando no hay archivo de fuente."""
    text = "".join(c for c in text if c not in _IGNORED_CHARS)
    if not fontfile:
        # Las fuentes base (helv…) chocan con las que ya tiene la página y salen con otra
        # codificación («Pág.» → «PÆg.»). Arial tiene la misma métrica que Helvetica y un nombre propio.
        fontfile = winfonts.find_styled_font("Arial", base14 in ("hebo", "hebi"), base14 in ("heit", "hebi"))
    main = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font(base14)
    missing = [c for c in text if c.strip() and not main.has_glyph(ord(c))]
    if not missing or not _SYMBOL_FONT_FILE.is_file():
        # Con archivo, el nombre debe ser único: si coincide con una fuente que la
        # página ya usa (p. ej. "helv"), PyMuPDF reutiliza esa y ignora el archivo.
        kwargs = ({"fontfile": fontfile, "fontname": f"wf_{Path(fontfile).stem}_{page.xref}_{next(_FONT_SEQ)}"}
                  if fontfile else {"fontname": base14})
        page.insert_text(pos, text, fontsize=size, color=color, **kwargs)
        return
    symbols = fitz.Font(fontfile=str(_SYMBOL_FONT_FILE))
    tw = fitz.TextWriter(page.rect)
    cursor = fitz.Point(pos)
    runs: list[tuple[str, fitz.Font]] = []
    for c in text:
        use_symbols = c.strip() and not main.has_glyph(ord(c)) and symbols.has_glyph(ord(c))
        font = symbols if use_symbols else main
        if runs and runs[-1][1] is font:
            runs[-1] = (runs[-1][0] + c, font)
        else:
            runs.append((c, font))
    for run, font in runs:
        tw.append(cursor, run, font=font, fontsize=size)
        cursor = tw.last_point
    tw.write_text(page, color=color)


def find_replace_in_pdf(path: str, buscar: str, reemplazar: str) -> str | None:
    """Busca 'buscar' y lo sustituye por 'reemplazar' en la misma posición."""
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
                        _insert_text_with_fallback(page, pos, reemplazar, size)
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


# ── EDITOR VISUAL (clic sobre el texto para editarlo) ───────────────────
def open_edit_session(path: str):
    """Abre el PDF para una sesión de edición en memoria (varios cambios
    sin tocar disco hasta que se guarde). Devuelve el fitz.Document o None."""
    if not HAS_FITZ:
        return None
    try:
        return fitz.open(path)
    except Exception:
        return None


def render_doc_page_png(doc, page_idx: int, zoom: float = 1.6, annots: bool = True) -> bytes | None:
    """Renderiza una página de un documento YA ABIERTO (refleja ediciones
    en memoria aún no guardadas). zoom es el factor punto-PDF -> píxel."""
    try:
        pg = doc[page_idx]
        mat = fitz.Matrix(zoom, zoom)
        pix = pg.get_pixmap(matrix=mat, annots=annots)
        return pix.tobytes("png")
    except Exception:
        return None


def get_page_text_spans(doc, page_idx: int) -> list[dict]:
    """Fragmentos de texto de una página (de un documento ya abierto), con
    su caja en puntos PDF (mismo sistema que page.rect), tamaño y fuente."""
    try:
        pg = doc[page_idx]
        data = pg.get_text("dict")
    except Exception:
        return []
    spans = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                spans.append({
                    "text": text,
                    "bbox": tuple(span["bbox"]),
                    "size": span.get("size", 10.0),
                    "color": span.get("color", 0),
                    "font": span.get("font", ""),
                })
    return spans


def recolor_text_in_boxes(doc, page_idx: int, boxes: list, rgb) -> int:
    """Cambia el color del texto que queda dentro de las cajas (p. ej. a azul de hipervínculo) conservando la fuente, el
    tamaño y la posición. Solo cambia lo que está dentro: un tramo a medias de una línea se parte en lo que se
    recolorea y lo que no. Devuelve cuántos tramos cambió."""
    try:
        pg = doc[page_idx]
        data = pg.get_text("rawdict")
    except Exception:
        return 0
    zones = [fitz.Rect(b) for b in boxes]
    runs = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                cur = []
                for ch in span.get("chars", []):
                    cb = fitz.Rect(ch["bbox"])
                    centre = fitz.Point((cb.x0 + cb.x1) / 2, (cb.y0 + cb.y1) / 2)
                    if any(z.contains(centre) for z in zones):
                        cur.append(ch)
                    elif cur:
                        runs.append((span, cur))
                        cur = []
                if cur:
                    runs.append((span, cur))
    clean = []
    for span, chars in runs:                      # sin espacios sueltos al principio o al final de un tramo
        while chars and not chars[0]["c"].strip():
            chars = chars[1:]
        while chars and not chars[-1]["c"].strip():
            chars = chars[:-1]
        if chars:
            clean.append((span, chars))
    if not clean:
        return 0
    for span, chars in clean:
        r = fitz.Rect(chars[0]["bbox"])
        for ch in chars[1:]:
            r |= fitz.Rect(ch["bbox"])
        pg.add_redact_annot(r, fill=False)
    pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                        text=fitz.PDF_REDACT_TEXT_REMOVE)
    color = tuple(float(c) for c in rgb)
    for span, chars in clean:
        text = "".join(ch["c"] for ch in chars)
        font = span.get("font", "")
        flags = span.get("flags", 0)
        bold, italic = winfonts.style_from_ps_name(font)
        bold, italic = bold or bool(flags & 16), italic or bool(flags & 2)
        matched, family = winfonts.find_font_file(font) if font else (None, "")
        if matched and (bold or italic):
            matched = winfonts.find_styled_font(family, bold, italic) or matched
        base14 = {(False, False): "helv", (True, False): "hebo", (False, True): "heit", (True, True): "hebi"}[(bold, italic)]
        _insert_text_with_fallback(pg, fitz.Point(chars[0]["origin"]), text, float(span.get("size", 10.0)), matched,
                                   color, base14)
    return len(clean)


# ── Edición por párrafos con reflujo ──────────────────────────────────────
_LABEL_RE = re.compile(r"^\s*(?:\(?[A-Za-z0-9]{1,4}(?:\.[A-Za-z0-9]{1,4})*[\.\)]|[-–—•·*])\s*$")


def _is_label(text: str) -> bool:
    """Etiqueta de lista: «h)», «3.», una viñeta o una flecha."""
    t = text.strip()
    return bool(t) and (bool(_LABEL_RE.match(t)) or (len(t) == 1 and not t.isalnum()))


def _span_style(s: dict) -> dict:
    font = s.get("font", "")
    bold, italic = winfonts.style_from_ps_name(font)
    flags = s.get("flags", 0)
    return {"font": font, "family": None, "bold": bold or bool(flags & 16),
            "italic": italic or bool(flags & 2), "size": round(float(s.get("size", 10.0)), 1),
            "color": int(s.get("color", 0)) & 0xFFFFFF}


def _mk_line(spans: list, bbox: tuple, y: float) -> dict:
    label = False
    if spans and _is_label(spans[0]["text"]):
        rest = [s for s in spans[1:] if s["text"].strip()]
        if rest:
            first = spans.index(rest[0])
            label = (first > 1 or spans[0]["text"].endswith(" ")      # hay un espacio de por medio
                     or rest[0]["bbox"][0] - spans[0]["bbox"][2] > 1.0)
    return {"spans": spans, "bbox": tuple(bbox), "y": y, "label": label}


def _merge_lines(a: dict, b: dict) -> dict:
    """Dos trozos de la misma línea visual (p. ej. «h)» y su texto), de izquierda a derecha."""
    bb = (min(a["bbox"][0], b["bbox"][0]), min(a["bbox"][1], b["bbox"][1]),
          max(a["bbox"][2], b["bbox"][2]), max(a["bbox"][3], b["bbox"][3]))
    return _mk_line(a["spans"] + b["spans"], bb, b["y"])


def _label_only(line: dict) -> bool:
    """Línea que es solo una etiqueta o viñeta (puede ir seguida de un espacio)."""
    sp = line["spans"]
    return bool(sp) and _is_label(sp[0]["text"]) and all(not s["text"].strip() for s in sp[1:])


def _same_line(prev: dict, cur: dict) -> bool:
    """¿cur es la continuación, a la derecha y a la misma altura, de prev?"""
    size = float(prev["spans"][0].get("size", 10.0))
    gap = cur["bbox"][0] - prev["bbox"][2]
    label_only = _label_only(prev)
    return (abs(cur["y"] - prev["y"]) < 0.4 * size and gap >= -1
            and (gap < 80 if label_only else gap < 1.5 * size))


def _read_lines(block: dict) -> list[dict]:
    """Líneas de un bloque (sin las que solo tienen espacios)."""
    lines: list[dict] = []
    for ln in block.get("lines", []):
        spans = [s for s in ln.get("spans", []) if s.get("text") is not None]
        if not "".join(s["text"] for s in spans).strip():
            continue
        lines.append(_mk_line(spans, ln["bbox"], spans[0]["origin"][1]))
    return lines


def _attach_labels(lines: list[dict]) -> list[dict]:
    """Une cada etiqueta suelta («e)», una viñeta) con la línea del cuerpo que tiene a su
    derecha, aunque no sean consecutivas (tras mover contenido, PyMuPDF las separa)."""
    out = list(lines)
    for lab in [ln for ln in lines if _label_only(ln)]:
        size = float(lab["spans"][0].get("size", 10.0))
        best = None
        for other in out:
            if other is lab or _label_only(other):
                continue
            gap = other["bbox"][0] - lab["bbox"][2]
            if abs(other["y"] - lab["y"]) < 0.5 * size and 0 <= gap < 80:
                if best is None or gap < best[0]:
                    best = (gap, other)
        if best is not None:
            merged = _merge_lines(lab, best[1])
            out[out.index(best[1])] = merged
            out.remove(lab)
    return out


def _join_same_baseline(lines: list[dict]) -> list[dict]:
    out: list[dict] = []
    for ln in lines:
        if out and _same_line(out[-1], ln):
            out[-1] = _merge_lines(out[-1], ln)
        else:
            out.append(ln)
    return out


def _line_style(line: dict) -> tuple:
    """Estilo dominante de una línea (tamaño, negrita, color), sin contar la etiqueta."""
    spans = [s for s in line["spans"][1:] if s["text"].strip()] if line["label"] else line["spans"]
    weight: dict[tuple, int] = {}
    for s in spans:
        st = _span_style(s)
        key = (round(st["size"] * 2) / 2, st["bold"], st["color"])
        weight[key] = weight.get(key, 0) + len(s["text"].strip())
    return max(weight, key=weight.get) if weight else (0, False, 0)


def _split_lines(lines: list[dict]) -> list[tuple[list[dict], float | None]]:
    """Agrupa las líneas de la página en párrafos (PyMuPDF los reparte en bloques que
    no coinciden con ellos). Un párrafo nuevo empieza tras un hueco mayor que el
    interlineado de ese tamaño de letra, al cambiar el estilo de la línea, en una
    línea con etiqueta de lista o si la línea sube (otra columna)."""
    pitches: dict[float, float] = {}
    for a, b in zip(lines, lines[1:]):
        ka, kb = _line_style(a), _line_style(b)
        gap = b["y"] - a["y"]
        if ka == kb and 0.5 < gap < 3 * (ka[0] or 10.0):
            pitches[ka[0]] = min(pitches.get(ka[0], gap), gap)
    groups: list[tuple[list[dict], float | None]] = []
    for ln in lines:
        new = not groups
        if groups:
            prev = groups[-1][0][-1]
            size = _line_style(prev)[0] or 10.0
            hint = pitches.get(size)
            gap = ln["y"] - prev["y"]
            new = (gap < 0.5 or gap > (hint or size * 1.25) * 1.2 or ln["label"]
                   or _line_style(ln) != _line_style(prev))
        if new:
            groups.append(([], pitches.get(_line_style(ln)[0])))
        groups[-1][0].append(ln)
    return groups


def get_page_paragraphs(doc, page_idx: int, manual: bool = False) -> list[dict]:
    """Párrafos de una página, con su texto en tramos de estilo (runs), la etiqueta de
    lista si la tiene, la sangría, la alineación (izquierda, centro, justificado),
    el interlineado, el margen derecho hasta el que puede crecer y la franja
    horizontal que se desplaza si cambia su altura."""
    try:
        pg = doc[page_idx]
        data = pg.get_text("dict")
        page_w = pg.rect.width
    except Exception:
        return []
    all_lines: list[dict] = []
    for b in data.get("blocks", []):
        if b.get("type") == 0:
            all_lines.extend(_read_lines(b))
    joined = _join_same_baseline(_attach_labels(all_lines))
    # Modo manual: cada línea es una unidad, sin deducir párrafos ni listas.
    groups = [([ln], None) for ln in joined] if manual else _split_lines(joined)
    if not groups:
        return []
    margin_right = page_w - _doc_geometry(doc)["left"]       # margen simétrico al izquierdo

    paras = []
    for lines, base in groups:
        label = lines[0]["spans"][0] if lines[0]["label"] else None
        def _after_label(sp):
            sp = sp[1:]
            while sp and not sp[0]["text"].strip():
                sp = sp[1:]
            return sp

        body = [(_after_label(ln["spans"]) if (i == 0 and label) else ln["spans"])
                for i, ln in enumerate(lines)]
        x0 = min(ln["bbox"][0] for ln in lines)
        y0 = min(ln["bbox"][1] for ln in lines)
        x1 = max(ln["bbox"][2] for ln in lines)
        y1 = max(ln["bbox"][3] for ln in lines)
        x_first = body[0][0]["bbox"][0]
        x_cont = body[1][0]["bbox"][0] if len(lines) > 1 else x_first
        rights = [sp[-1]["bbox"][2] for sp in body]
        line_right_max = max(rights)

        # tramos de texto con su estilo; saltos de línea solo donde la línea era corta
        runs: list[dict] = []

        def add(text: str, st: dict):
            if not text:
                return
            if runs and all(runs[-1][k] == st[k] for k in st):
                runs[-1]["text"] += text
            else:
                runs.append({"text": text, **st})

        for i, sp in enumerate(body):
            for s in sp:
                add(s["text"].replace("\xa0", " ").replace("\xad", "-"), _span_style(s))
            if i < len(lines) - 1:
                full = rights[i] >= line_right_max - 0.2 * max(line_right_max - x_cont, 1.0)
                last = runs[-1] if runs else None
                if last is not None:
                    st = {k: last[k] for k in ("font", "family", "bold", "italic", "size", "color")}
                    if full:
                        if not last["text"].endswith(" "):
                            add(" ", st)
                    else:
                        last["text"] = last["text"].rstrip()
                        add("\n", st)
        if runs:
            runs[0]["text"] = runs[0]["text"].lstrip()
            if not runs[-1]["text"].strip():
                runs.pop()
        text = "".join(r["text"] for r in runs)

        weight: dict[tuple, int] = {}
        for r in runs:
            key = (r["size"], r["color"], r["font"])
            weight[key] = weight.get(key, 0) + len(r["text"].strip())
        dom = max(weight, key=weight.get) if weight else (10.0, 0, "")
        size, color, font = float(dom[0]), dom[1], dom[2]
        origins = [ln["y"] for ln in lines]
        diffs = sorted(b2 - a for a, b2 in zip(origins, origins[1:]) if b2 - a > 0.5)
        pitch = diffs[len(diffs) // 2] if diffs else (base or size * 1.2)
        pitch = min(max(pitch, size * 0.9), size * 3.0)

        justify = (len(lines) >= 2 and max(rights[:-1]) - min(rights[:-1]) <= 2.0
                   and min(rights[:-1]) - x_cont > 20)
        sure = len(lines) >= 3
        paras.append({
            "text": text, "runs": runs, "bbox": (x0, y0, x1, y1), "size": size, "color": color,
            "font": font, "pitch": pitch, "n_lines": len(lines), "origin_y": origins[0],
            "x_first": x_first, "x_cont": x_cont, "body_x": min(x_first, x_cont),
            "line_right": line_right_max, "align": "justify" if justify else "left",
            "label": ({"text": label["text"], "x": label["bbox"][0], "style": _span_style(label),
                       "span": label} if label else None), "_sure": sure,
            "shift_x0": 0.0, "shift_x1": page_w,
        })

    # segunda pasada: margen derecho y franja de desplazamiento según lo que hay al lado
    content_left = min(p["bbox"][0] for p in paras)
    content_right = max(p["bbox"][2] for p in paras)
    column_right = max((p["line_right"] for p in paras if p["align"] == "justify" and p["_sure"]),
                       default=content_right)
    for p in paras:
        if p["align"] == "justify" and not p["_sure"] and p["line_right"] < column_right - 3:
            p["align"] = "left"
        x0, y0, x1, y1 = p["bbox"]
        right = max(margin_right, content_right)
        for o in paras:
            if o is p or not (o["bbox"][1] < y1 and o["bbox"][3] > y0):
                continue                          # no comparte franja vertical
            if o["bbox"][0] >= x1 - 1:
                right = min(right, o["bbox"][0] - 6)
                p["shift_x1"] = min(p["shift_x1"], o["bbox"][0] - 1)
            elif o["bbox"][2] <= x0 + 1:
                p["shift_x0"] = max(p["shift_x0"], o["bbox"][2] + 1)
        if p["align"] == "justify":
            right = p["line_right"]               # el texto justificado ya fija el borde de la columna
        right = max(right, x1)
        centered = (not p["label"] and p["n_lines"] >= 1 and abs((x0 + x1) / 2 - page_w / 2) < 4
                    and x0 > content_left + 8 and p["align"] != "justify")
        if centered:
            p["align"] = "center"
            wrap = 2 * min((x0 + x1) / 2 - content_left, max(margin_right, content_right) - (x0 + x1) / 2)
            p["wrap_first"] = p["wrap_cont"] = p["wrap_w"] = max(wrap, x1 - x0)
        else:
            p["wrap_right"] = right
            p["wrap_first"] = right - p["x_first"]
            p["wrap_cont"] = right - p["x_cont"]
            p["wrap_w"] = right - p["body_x"]
    return paras


def _resolve_font(source_font: str, family, bold, italic):
    """(archivo de fuente o None, familia, base14 de respaldo, negrita, cursiva)."""
    src_bold, src_italic = winfonts.style_from_ps_name(source_font)
    bold = src_bold if bold is None else bold
    italic = src_italic if italic is None else italic
    matched_file, found_family = None, ""
    if family:
        matched_file, found_family = winfonts.find_styled_font(family, bold, italic), family
    elif source_font:
        matched_file, found_family = winfonts.find_font_file(source_font)
        if matched_file and (bold or italic):
            matched_file = winfonts.find_styled_font(found_family, bold, italic) or matched_file
    base14 = {(False, False): "helv", (True, False): "hebo",
              (False, True): "heit", (True, True): "hebi"}[(bool(bold), bool(italic))]
    return matched_file, found_family, base14


_GEO_CACHE: dict = {}


def _size_key(rect) -> tuple:
    return (round(rect.width), round(rect.height))


def _norm_text(text: str) -> str:
    """Texto sin dígitos ni espacios de más, para reconocer el mismo pie en otra página."""
    return re.sub(r"\d+", "#", " ".join(text.split())).lower()[:30]


def _norm_lines(doc, i: int) -> list:
    """(y0, y1, texto normalizado) de cada línea de texto de la página i."""
    out = []
    for b in doc[i].get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            text = "".join(s["text"] for s in ln["spans"])
            if text.strip():
                out.append((ln["bbox"][1], ln["bbox"][3], _norm_text(text)))
    return out


def _match_header_footer(doc, idxs: list, sig_h: set, sig_f: set) -> tuple:
    """(fin de cabecera, inicio de pie) de páginas donde no hay repetición que detectar (un
    anexo en horizontal), buscando las líneas de cabecera y pie que ya se conocen. Se
    compara por líneas: los bloques cambian de forma al reescribir el número de página."""
    header = footer = None
    for i in idxs:
        h = doc[i].rect.height
        for y0, y1, n in _norm_lines(doc, i):
            if n in sig_h and y1 < h * 0.3:
                header = max(header or 0.0, y1)
            if n in sig_f and y0 > h * 0.5 and (len(n) >= 4 or y0 > h * 0.8):
                footer = min(footer if footer is not None else 1e9, y0)
    return header, footer


def _detect_header_footer(doc, idxs: list) -> tuple:
    """(fin de la cabecera, inicio del pie, pares/impares distintos) a partir de las
    páginas idxs (todas del mismo tamaño): textos cortos en la franja superior o
    inferior que se repiten en la misma posición en la mitad de las páginas."""
    header = footer = None
    if len(idxs) < 2:
        return header, footer, False, (set(), set())
    top_seen: dict = {}
    bot_seen: dict = {}
    for i in idxs:
        h = doc[i].rect.height
        for b in doc[i].get_text("blocks"):
            if b[6] != 0 or not b[4].strip() or (b[3] - b[1]) > h * 0.06:
                continue
            if b[3] < h * 0.14:
                top_seen.setdefault(round(b[1] / 4), []).append((i, b))
            elif b[1] > h * 0.86:
                bot_seen.setdefault(round(b[1] / 4), []).append((i, b))
    need = max(2, len(idxs) // 2)
    rep_top = [b for items in top_seen.values() if len({i for i, _ in items}) >= need for _, b in items]
    rep_bot = [b for items in bot_seen.values() if len({i for i, _ in items}) >= need for _, b in items]
    if rep_top:
        header = max(b[3] for b in rep_top)
    if rep_bot:
        footer = min(b[1] for b in rep_bot)
    parity = False
    if (header or footer) and len(idxs) >= 3:
        sigs = {}
        for i in idxs:
            bl = [b for b in doc[i].get_text("blocks") if b[6] == 0 and b[4].strip() and (
                (header and b[3] <= header + 2) or (footer and b[1] >= footer - 2))]
            sigs[i] = tuple(sorted((round(b[0] / 12), round(b[1] / 12)) for b in bl))
        odd = {s for k, (i, s) in enumerate(sigs.items()) if k % 2 == 0}
        even = {s for k, (i, s) in enumerate(sigs.items()) if k % 2 == 1}
        parity = len(odd) == 1 and len(even) == 1 and odd != even
    sig_h, sig_f = set(), set()
    for i in idxs:
        for y0, y1, n in _norm_lines(doc, i):
            if header and y1 <= header + 1:
                sig_h.add(n)
            if footer and y0 >= footer - 1:
                sig_f.add(n)
    return header, footer, parity, (sig_h, sig_f)


def _doc_geometry(doc) -> dict:
    """Márgenes del documento: el izquierdo se deduce del texto más a la izquierda
    de varias páginas, y se supone simétrico (así el margen derecho no depende de
    lo ancho que sea el texto de una página concreta). 'unit' es el margen
    inferior/superior que se respeta al repartir texto entre páginas. Cabecera y
    pie se detectan por tamaño de página (un anexo en horizontal tiene los suyos)."""
    first = doc[0].get_text("blocks")[:6] if doc.page_count else []
    key = (id(doc), doc.page_count, hash(tuple(round(v) for b in first for v in b[:4])))
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]
    n = doc.page_count
    sample = list(range(n)) if n <= 20 else sorted({round(i * (n - 1) / 19) for i in range(20)})
    left = None
    for i in sample:
        w = doc[i].rect.width
        for b in doc[i].get_text("blocks"):
            if b[6] == 0 and b[4].strip() and b[0] < w * 0.25:
                left = b[0] if left is None else min(left, b[0])
    left = 56.0 if left is None else min(max(left, 8.0), 90.0)
    by_size: dict = {}
    for i in sample:
        by_size.setdefault(_size_key(doc[i].rect), []).append(i)
    classes, sigs = {}, []
    for k, idxs in by_size.items():
        h, f, p, sg = _detect_header_footer(doc, idxs)
        if h or f:
            classes[k] = {"header": h, "footer": f, "parity": p}
            sigs.append(sg)
    main = max(by_size, key=lambda k: len(by_size[k])) if by_size else (0, 0)
    if classes:                                   # otros tamaños (p. ej. un anexo en horizontal)
        sig_h = set().union(*(s[0] for s in sigs))
        sig_f = set().union(*(s[1] for s in sigs))
        for k, idxs in by_size.items():
            if k == main:
                continue
            mh, mf = _match_header_footer(doc, idxs, sig_h, sig_f)
            c = classes.get(k)
            if c is None:
                if mh or mf:
                    classes[k] = {"header": mh, "footer": mf, "parity": False}
            else:                                 # la repetición por bloques puede quedarse corta: se une
                hs = [x for x in (c["header"], mh) if x]
                fs = [x for x in (c["footer"], mf) if x]
                c["header"] = max(hs) if hs else None
                c["footer"] = min(fs) if fs else None
    geo = {"left": left, "unit": min(max(left, 36.0), 72.0), "classes": classes, "main": main,
           "parity": bool(classes.get(main, {}).get("parity")), "override": None}
    if len(_GEO_CACHE) > 8:
        _GEO_CACHE.clear()
    _GEO_CACHE[key] = geo
    return geo


def _hf(geo: dict, rect) -> tuple:
    """(fin de la cabecera, inicio del pie) de una página según su tamaño; None si no hay."""
    if geo.get("override") is not None:
        h, f, ref = geo["override"]
        k = rect.height / ref if ref else 1.0
        return (h * k if h else None), (f * k if f else None)
    c = geo["classes"].get(_size_key(rect))
    if c is not None:
        return c["header"], c["footer"]
    m = geo["classes"].get(geo["main"])
    if m and geo["main"][1]:
        k = rect.height / geo["main"][1]
        return (m["header"] * k if m["header"] else None), (m["footer"] * k if m["footer"] else None)
    return None, None


DEFAULT_HF = {"header_boxes": [], "footer_boxes": [], "repeat_header": True,
              "repeat_footer": True, "parity": False, "numbering": True, "background": True}


def _geo_with_settings(geo: dict, settings) -> dict:
    """Aplica los ajustes que dio el usuario (textos marcados como cabecera/pie).
    Con ajustes, mandan ellos y no la detección automática."""
    g = dict(geo)
    s = {**DEFAULT_HF, "parity": bool(geo.get("parity")), **(settings or {})}
    if settings is not None:
        g["override"] = (max((b[3] for b in s["header_boxes"]), default=None),
                         min((b[1] for b in s["footer_boxes"]), default=None),
                         s.get("ref_h") or geo["main"][1] or None)
    g["settings"] = s
    return g


def auto_header_footer(doc, page_idx: int = 0) -> tuple:
    """(fin de la cabecera, inicio del pie) detectados por repetición; None si no hay."""
    return _hf(_doc_geometry(doc), doc[page_idx].rect)


_PAGENUM_RE = re.compile(
    r"^(\s*(?:p[^\W\d_]g(?:ina|\.)?|pp?\.|page|folha|hoja|seite|[A-Z]{2,5})?\s*[-–—]?\s*)(\d{1,4})"
    r"(\s*[-–—]?\s*(?:(?:de|of|sur|von|di|/)\s*(\d{1,4}))?\s*)$", re.I)


def _band_lines(page, header, footer) -> list:
    """Líneas de la cabecera y del pie de una página, con su texto completo."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            spans = [s for s in ln["spans"] if s.get("text") is not None]
            text = "".join(s["text"] for s in spans).replace("\xa0", " ").replace("\xad", "-")
            if not text.strip():
                continue
            y0, y1 = ln["bbox"][1], ln["bbox"][3]
            if (header and y1 <= header + 2) or (footer and y0 >= footer - 2):
                out.append({"text": text, "bbox": ln["bbox"], "span": spans[0], "spans": spans})
    return out


def find_page_numbers(doc, page_idx: int, header, footer) -> list[str]:
    """Textos de la cabecera/pie que parecen una numeración de página (Pág. 2, - 3 -, 2 de 5…)."""
    try:
        return [ln["text"].strip() for ln in _band_lines(doc[page_idx], header, footer)
                if _PAGENUM_RE.match(ln["text"])]
    except Exception:
        return []


def _rewrite_line(page, line: dict, new_text: str):
    """Cambia el texto de una línea conservando el estilo de cada fragmento (una negrita
    en el número, un tamaño distinto…): solo se tocan los caracteres que cambian y los
    fragmentos siguientes se desplazan lo justo. La línea mantiene su borde de
    alineación (derecha, centro o izquierda)."""
    spans = line["spans"]
    def norm(x: str) -> str:
        return x.replace("\xa0", " ").replace("\xad", "-")

    old_full = norm("".join(s["text"] for s in spans))
    chars = [list(norm(s["text"])) for s in spans]
    offs, o = [], 0
    for s in spans:
        offs.append(o)
        o += len(s["text"])
    for tag, i1, i2, j1, j2 in reversed(difflib.SequenceMatcher(None, old_full, new_text,
                                                                autojunk=False).get_opcodes()):
        if tag == "equal":
            continue
        pos = i1 if tag != "insert" else max(i1 - 1, 0)       # inserción: en el fragmento anterior
        k = max((idx for idx in range(len(spans)) if offs[idx] <= pos), default=0)
        lo = i1 - offs[k] if tag != "insert" else i1 - offs[k]
        hi = min(i2 - offs[k], len(chars[k]))
        chars[k][lo:hi] = list(new_text[j1:j2])
        for kk in range(k + 1, len(spans)):                   # dígitos repartidos en varios fragmentos
            if offs[kk] < i2:
                end = min(i2 - offs[kk], len(chars[kk]))
                del chars[kk][0:end]
    new_spans = ["".join(c) for c in chars]

    x0, y0, x1, y1 = line["bbox"]
    page.add_redact_annot(fitz.Rect(x0, y0, x1, y1) + (0.3, 0.3, -0.3, -0.3), fill=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    fonts, deltas = [], []
    for s, newt in zip(spans, new_spans):
        mf, _fam, b14 = _resolve_font(s.get("font", ""), None, None, None)
        main = fitz.Font(fontfile=mf) if mf else fitz.Font(b14)
        size = float(s["size"])
        deltas.append(main.text_length(newt, fontsize=size)
                      - main.text_length(norm(s["text"]), fontsize=size))
        fonts.append((mf, b14))
    cx, pw = (x0 + x1) / 2, page.rect.width
    total = sum(deltas)
    base = -total / 2 if abs(cx - pw / 2) < 8 else (-total if cx > pw * 0.6 else 0.0)
    cum = 0.0
    for s, newt, (mf, b14), dlt in zip(spans, new_spans, fonts, deltas):
        if newt.strip():
            _insert_text_with_fallback(page, fitz.Point(s["bbox"][0] + base + cum, s["origin"][1]), newt,
                                       float(s["size"]), mf, _rgb_tuple(s.get("color", 0)), b14)
        cum += dlt


def _renumber_page(doc, pno: int, src_idx: int, geo: dict):
    """En la página nueva pno (copia de src_idx), sube el número de página."""
    delta = pno - src_idx
    header, footer = _hf(geo, doc[src_idx].rect)
    for ln in _band_lines(doc[src_idx], header, footer):
        m = _PAGENUM_RE.match(ln["text"])
        if m:
            _rewrite_line(doc[pno], ln, f"{m.group(1)}{int(m.group(2)) + delta}{m.group(3)}")


def _update_totals(doc, geo: dict, added: int, touched: set):
    """Con «Pág. 2 de 5» o «CMP 1/4», el total sube en todas las páginas al añadir páginas."""
    for i in range(doc.page_count):
        header, footer = _hf(geo, doc[i].rect)
        for ln in _band_lines(doc[i], header, footer):
            m = _PAGENUM_RE.match(ln["text"])
            if m and m.group(4):
                tail = re.sub(r"\d{1,4}(?=\s*$)", str(int(m.group(4)) + added), m.group(3).rstrip()) + \
                    m.group(3)[len(m.group(3).rstrip()):]
                _rewrite_line(doc[i], ln, f"{m.group(1)}{m.group(2)}{tail}")
                touched.add(i)


def _limit(geo: dict, rect) -> float:
    """Hasta dónde llega el cuerpo de la página: sin invadir margen inferior ni pie."""
    limit = rect.height - geo["unit"]
    footer = _hf(geo, rect)[1]
    if footer:
        limit = min(limit, footer - 4)
    return max(limit, geo["unit"] + 20)


def _atoms(doc, pno: int) -> list:
    """Unidades que no se parten al repartir una página: párrafos (los bloques de
    PyMuPDF a veces juntan varios) e imágenes. Cada una es (x0, y0, x1, y1, tipo)."""
    out = [(*p["bbox"], 0) for p in get_page_paragraphs(doc, pno)]
    out += [(b[0], b[1], b[2], b[3], 1) for b in doc[pno].get_text("blocks") if b[6] == 1]
    return out


def _move_overlays(page, y_from: float, y_to: float, sx0: float, sx1: float, dy: float):
    """Mueve dy los campos de formulario, anotaciones y enlaces que hay en esa franja:
    no son contenido de la página y no viajan con el resto."""
    def inside(r):
        return r.y0 >= y_from - 1 and r.y1 <= y_to + 1 and r.x0 >= sx0 - 1 and r.x1 <= sx1 + 1
    try:
        for w in list(page.widgets() or []):
            if inside(w.rect):
                w.rect = fitz.Rect(w.rect.x0, w.rect.y0 + dy, w.rect.x1, w.rect.y1 + dy)
                w.update()
        for a in list(page.annots() or []):
            if inside(a.rect):
                a.set_rect(fitz.Rect(a.rect.x0, a.rect.y0 + dy, a.rect.x1, a.rect.y1 + dy))
        for lk in page.get_links():
            r = fitz.Rect(lk["from"])
            if inside(r):
                lk["from"] = fitz.Rect(r.x0, r.y0 + dy, r.x1, r.y1 + dy)
                page.update_link(lk)
    except Exception:
        if os.environ.get("PDF_DEBUG"):
            import traceback
            traceback.print_exc()


def _shift_down(doc, pno: int, y_from: float, sx0: float, sx1: float, delta: float,
                geo: dict, touched: set, depth: int = 0):
    """Desplaza `delta` puntos lo que hay en la página pno entre y_from y su margen
    inferior (texto, imágenes y dibujos). Con delta > 0, lo que ya no cabe pasa
    al principio de la página siguiente, que a su vez se desplaza (en cascada,
    creando páginas si hace falta). El pie de página no se toca."""
    pg = doc[pno]
    page_h = pg.rect.height
    limit = _limit(geo, pg.rect)
    if y_from >= limit or depth > 60:
        return
    touched.add(pno)
    blocks = sorted((b for b in _atoms(doc, pno)
                     if b[1] >= y_from - 1 and b[1] < limit and b[0] >= sx0 - 1 and b[2] <= sx1 + 1),
                    key=lambda b: b[1])
    split_y = None
    if delta > 0:
        room = limit - geo["unit"]
        for b in blocks:
            if b[3] + delta > limit and (b[3] - b[1]) <= room:   # uno más alto que la página no se mueve
                split_y = max(b[1] - 0.5, y_from)
                break
    src = fitz.open()
    src.insert_pdf(doc, from_page=pno, to_page=pno)
    try:
        pg.add_redact_annot(fitz.Rect(sx0, y_from, sx1, limit), fill=False)
        pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
        keep_to = limit if split_y is None else split_y
        if keep_to > y_from + 0.5:
            pg.show_pdf_page(fitz.Rect(sx0, y_from + delta, sx1, keep_to + delta), src, 0,
                             clip=fitz.Rect(sx0, y_from, sx1, keep_to))
            _move_overlays(doc[pno], y_from, keep_to, sx0, sx1, delta)
        if split_y is not None:
            over = [b for b in blocks if b[1] >= split_y - 1]
            first = blocks.index(over[0])
            above = blocks[first - 1][3] if first > 0 else y_from       # hueco con lo anterior
            gap = min(max(blocks[first][1] - above, 4.0), 40.0)
            height = min(max(b[3] for b in over), page_h) - split_y + gap   # con el hueco entre párrafos
            _push_top(doc, pno + 1, src, fitz.Rect(sx0, split_y, sx1, limit), height, geo, touched, depth + 1)
    finally:
        src.close()


def _bump_page_numbers(doc, pno: int, delta: int, geo: dict):
    """Suma delta al número de página que lleve la cabecera o el pie de la página pno."""
    header, footer = _hf(geo, doc[pno].rect)
    for ln in _band_lines(doc[pno], header, footer):
        m = _PAGENUM_RE.match(ln["text"])
        if m:
            _rewrite_line(doc[pno], ln, f"{m.group(1)}{int(m.group(2)) + delta}{m.group(3)}")


def _ensure_page(doc, pno: int, geo: dict, touched: set | None = None):
    """Deja lista la página pno para recibir texto del final de la anterior. Si no
    existe, la crea al final; si existe pero es de otro tamaño (un anexo en
    horizontal), inserta una nueva delante, del tamaño de la anterior. La página
    nueva copia la cabecera y el pie de otra según los ajustes (la anterior, o la
    de dos antes si pares e impares son distintos) y sube el número de página; si
    se insertó en medio, las siguientes también suben."""
    prev = doc[pno - 1].rect
    in_middle = pno < doc.page_count
    if in_middle:
        cur = doc[pno].rect
        if abs(cur.width - prev.width) < 2 and abs(cur.height - prev.height) < 2:
            return
    s = geo["settings"]
    doc.new_page(pno if in_middle else -1, width=prev.width, height=prev.height)
    if touched is not None:
        touched.add(pno)
    src_idx = pno - 2 if s["parity"] and pno - 2 >= 0 else pno - 1
    src_idx = src_idx if _size_key(doc[src_idx].rect) == _size_key(prev) else pno - 1
    header, footer = _hf(geo, prev)
    bands = []
    if header and s["repeat_header"]:
        bands.append(fitz.Rect(0, 0, prev.width, header + 2))
    if footer and s["repeat_footer"] and footer < prev.height - 4:
        bands.append(fitz.Rect(0, footer - 2, prev.width, prev.height))
    if bands:
        src = fitz.open()
        try:
            src.insert_pdf(doc, from_page=src_idx, to_page=src_idx)
            for band in bands:
                doc[pno].show_pdf_page(band, src, 0, clip=band)
        finally:
            src.close()
        if s["numbering"]:
            _renumber_page(doc, pno, src_idx, geo)
    if in_middle and s["numbering"]:
        for p in range(pno + 1, doc.page_count):
            _bump_page_numbers(doc, p, 1, geo)
            if touched is not None:
                touched.add(p)


def _page_top(doc, pno: int, geo: dict) -> float:
    """Dónde empieza el cuerpo de una página: su texto más alto bajo la cabecera."""
    pg = doc[pno]
    header = _hf(geo, pg.rect)[0]
    floor = header - 2 if header else 0.0
    limit = _limit(geo, pg.rect)
    tops = [b[1] for b in _atoms(doc, pno) if b[4] == 0 and floor <= b[1] < limit]
    return min(tops) if tops else max(geo["unit"], (header or 0) + 4)


def _push_top(doc, pno: int, src, clip, height: float, geo: dict, touched: set, depth: int):
    """Coloca la región `clip` de `src` al principio de la página pno, bajando
    antes lo que ya hubiera ahí."""
    _ensure_page(doc, pno, geo, touched)
    top = _page_top(doc, pno, geo)
    _shift_down(doc, pno, top, 0, doc[pno].rect.width, height, geo, touched, depth)
    # Hay que volver a pedir la página: tras modificar el documento, las anteriores quedan huérfanas.
    doc[pno].show_pdf_page(fitz.Rect(clip.x0, top, clip.x1, top + clip.height), src, 0, clip=clip)
    touched.add(pno)


def _layout_runs(runs: list[dict], width_of, first_w: float, cont_w: float) -> list[dict]:
    """Reparte los tramos de texto en líneas. Cada línea es
    {"els": [("w", [(texto, estilo, ancho)…], ancho) | ("s", estilo, ancho)…],
     "width": ancho natural, "hard": termina en salto de línea o es la última}."""
    tokens: list[tuple] = []
    word: list[tuple] = []

    def flush():
        if word:
            tokens.append(("w", list(word)))
            word.clear()

    for r in runs:
        st = {k: r[k] for k in ("font", "family", "bold", "italic", "size", "color")}
        for part in re.split(r"( |\n)", r["text"]):
            if part == "":
                continue
            if part == " ":
                flush()
                tokens.append(("s", st))
            elif part == "\n":
                flush()
                tokens.append(("nl", st))
            else:
                word.append((part, st))
    flush()

    lines: list[dict] = []
    cur = {"els": [], "width": 0.0}
    pending_space = None

    def end_line(hard: bool):
        nonlocal cur, pending_space
        cur["hard"] = hard
        lines.append(cur)
        cur = {"els": [], "width": 0.0}
        pending_space = None

    for tk in tokens:
        max_w = first_w if not lines else cont_w
        if tk[0] == "nl":
            end_line(True)
        elif tk[0] == "s":
            if cur["els"]:
                pending_space = ("s", tk[1], width_of(" ", tk[1]))
        else:
            segs = [(t, st, width_of(t, st)) for t, st in tk[1]]
            w = sum(s[2] for s in segs)
            sp_w = pending_space[2] if pending_space else 0.0
            if cur["els"] and cur["width"] + sp_w + w > max_w:
                end_line(False)
                max_w = cont_w
                sp_w = 0.0
            if w > max_w and not cur["els"]:          # palabra más ancha que la línea: se parte
                text = "".join(s[0] for s in segs)
                st = segs[0][1]
                chunk = ""
                for ch in text:
                    if width_of(chunk + ch, st) > max_w and chunk:
                        cw = width_of(chunk, st)
                        cur["els"].append(("w", [(chunk, st, cw)], cw))
                        cur["width"] = cw
                        end_line(False)
                        chunk = ""
                    chunk += ch
                segs = [(chunk, st, width_of(chunk, st))]
                w = segs[0][2]
            if pending_space and cur["els"] and sp_w:
                cur["els"].append(pending_space)
                cur["width"] += sp_w
            pending_space = None
            cur["els"].append(("w", segs, w))
            cur["width"] += w
    if cur["els"] or not lines:
        end_line(True)
    elif lines:
        lines[-1]["hard"] = True
    return [ln for ln in lines if ln["els"] or ln["hard"]]


def render_text_free_clip(doc, page_idx: int, rect: tuple, zoom: float) -> bytes | None:
    """PNG de una zona de la página SIN su texto (con el fondo, dibujos e imágenes intactos). Sirve para tapar el texto
    original mientras se edita, sin pintar un recuadro: el editor se ve directamente sobre el fondo real de la página."""
    try:
        tmp = fitz.open()
        tmp.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        pg = tmp[0]
        r = fitz.Rect(rect) & pg.rect
        if r.is_empty:
            tmp.close()
            return None
        pg.add_redact_annot(r, fill=False)
        pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                            text=fitz.PDF_REDACT_TEXT_REMOVE)
        png = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=r).tobytes("png")
        tmp.close()
        return png
    except Exception:
        return None


def _replace_in_runs(runs: list, pattern, repl: str) -> tuple:
    """Sustituye en los tramos de estilo: el texto nuevo lleva el estilo del primer carácter reemplazado, y lo que no
    se toca conserva el suyo. Devuelve (tramos nuevos, nº de sustituciones)."""
    full = "".join(r["text"] for r in runs)
    matches = [m for m in pattern.finditer(full) if m.end() > m.start()]
    if not matches:
        return runs, 0
    bounds, pos = [], 0
    for r in runs:
        bounds.append((pos, pos + len(r["text"])))
        pos += len(r["text"])
    out: list = []

    def emit(i: int, text: str):
        if text:
            if out and all(out[-1][k] == runs[i][k] for k in runs[i] if k != "text"):
                out[-1]["text"] += text
            else:
                out.append({**runs[i], "text": text})

    mi, cursor = 0, 0
    while cursor < len(full):
        if mi < len(matches) and cursor == matches[mi].start():
            m = matches[mi]
            style_i = next((i for i, (a, b2) in enumerate(bounds) if a <= m.start() < b2), len(runs) - 1)
            emit(style_i, repl)
            cursor = m.end()
            mi += 1
            continue
        stop = matches[mi].start() if mi < len(matches) else len(full)
        i = next(i for i, (a, b2) in enumerate(bounds) if a <= cursor < b2)
        end = min(stop, bounds[i][1])
        emit(i, full[cursor:end])
        cursor = end
    return out, len(matches)


def replace_text_in_doc(doc, search: str, replacement: str, settings=None, manual: bool = False,
                        case: bool = False, before=None, ask_pages=None) -> dict:
    """Busca y reemplaza en todo el documento conservando fuente, tamaño y color de cada tramo, y recolocando el
    párrafo (justificación, líneas que cambian, cabecera y pie) como cualquier edición. `before()` se llama una vez, justo
    antes del primer cambio (para poder deshacer). `ask_pages(page, para, runs)` puede devolver False para cancelar si
    el cambio añadiría páginas. Devuelve {"count", "pages", "cancelled"}."""
    import re as _re
    res = {"count": 0, "pages": set(), "cancelled": False}
    if not search:
        return res
    pattern = _re.compile(_re.escape(search), 0 if case else _re.IGNORECASE)
    done = set()
    called = False
    p = 0
    while p < len(doc):
        for _ in range(400):
            target = None
            for para in get_page_paragraphs(doc, p, manual=manual):
                key = (p, para["text"])
                if key in done or not pattern.search(para["text"]):
                    continue
                target = para
                break
            if target is None:
                break
            runs = target.get("runs") or [{"text": target["text"], "font": target["font"], "family": None,
                                           "bold": False, "italic": False, "size": target["size"],
                                           "color": target["color"]}]
            new_runs, n = _replace_in_runs([dict(r) for r in runs], pattern, replacement)
            if n == 0:
                done.add((p, target["text"]))
                continue
            new_text = "".join(r["text"] for r in new_runs)
            if ask_pages is not None and ask_pages(p, target, new_runs) is False:
                res["cancelled"] = True
                return res
            if before is not None and not called:
                before()
                called = True
            r = replace_paragraph_in_doc(doc, p, target, new_text, target["size"], target["color"], settings=settings,
                                         runs=new_runs, shift=not manual)
            done.add((p, new_text))
            if r.get("ok"):
                res["count"] += n
                res["pages"].update(r.get("pages") or [p])
            else:
                done.add((p, target["text"]))
        p += 1
    return res


def replace_paragraph_in_doc(doc, page_idx: int, para: dict, new_text: str, size: float,
                             color, family=None, bold=None, italic=None, settings=None,
                             runs=None, shift: bool = True, insert_gap: float = 0.0) -> dict:
    """Reescribe un párrafo ajustándolo al margen, con el estilo de cada tramo de
    texto (runs: [{text, font, family, bold, italic, size, color}]); sin runs, todo el
    texto lleva el estilo dado. Mantiene la etiqueta de lista, la sangría y la
    justificación. Si cambia el número de líneas, lo de debajo se desplaza esa
    altura y lo que no cabe pasa a la página siguiente. Devuelve
    {ok, font_found, family, pages, delta} (pages = páginas modificadas)."""
    res = {"ok": False, "font_found": True, "family": "", "pages": [], "delta": 0.0}
    try:
        pg = doc[page_idx]
        geo = _geo_with_settings(_doc_geometry(doc), settings)
        pages_before = doc.page_count
        page_w, page_h = pg.rect.width, pg.rect.height
        limit = _limit(geo, pg.rect)
        x0, y0, x1, y1 = para["bbox"]
        pitch, k = para["pitch"], para["n_lines"]
        if runs is None:
            runs = [{"text": new_text, "font": para.get("font", ""), "family": family, "bold": bold,
                     "italic": italic, "size": size, "color": color}]
        runs = [r for r in runs if r["text"]]
        for r in runs:
            r["color"] = int(r["color"]) & 0xFFFFFF

        fcache: dict = {}

        def font_of(st: dict):
            key = (st["font"], st.get("family"), st.get("bold"), st.get("italic"))
            if key not in fcache:
                mf, ff, b14 = _resolve_font(st["font"], st.get("family"), st.get("bold"), st.get("italic"))
                fcache[key] = (mf, ff, b14, fitz.Font(fontfile=mf) if mf else fitz.Font(b14))
                if not mf and ff:
                    res["font_found"], res["family"] = False, ff
                elif mf and res["font_found"]:
                    res["family"] = ff
            return fcache[key]

        symbols = fitz.Font(fontfile=str(_SYMBOL_FONT_FILE)) if _SYMBOL_FONT_FILE.is_file() else None

        def width_of(s: str, st: dict) -> float:
            main = font_of(st)[3]
            return sum((symbols if symbols and c.strip() and not main.has_glyph(ord(c))
                        and symbols.has_glyph(ord(c)) else main).text_length(c, fontsize=st["size"])
                       for c in s if c not in _IGNORED_CHARS)

        def put(page, x: float, baseline: float, text: str, st: dict):
            if text.strip() or text == " ":
                mf, _ff, b14, _m = font_of(st)
                _insert_text_with_fallback(page, fitz.Point(x, baseline), text, st["size"], mf,
                                           _rgb_tuple(st["color"]), b14)

        lines = _layout_runs(runs, width_of, para["wrap_first"], para["wrap_cont"]) if runs else []
        max_size = max((r["size"] for r in runs), default=para["size"])
        new_pitch = pitch * max_size / para["size"]      # el interlineado crece con el tamaño
        # Líneas que caben en esta página; las demás pasan a la siguiente.
        n_fit = len(lines)
        if shift and para["origin_y"] <= limit:
            for i in range(len(lines)):
                if para["origin_y"] + i * new_pitch > limit:
                    n_fit = i
                    break
        delta = n_fit * new_pitch - k * pitch + (insert_gap if lines else 0.0)
        if shift and not lines and k:         # párrafo borrado: sube también el hueco que lo separaba
            nxt = [a[1] for a in _atoms(doc, page_idx) if a[4] == 0 and a[1] > y1 + 0.5]
            delta -= min(max(min(nxt) - y1, 4.0), 40.0) if nxt else 0.0
        if not shift:
            delta = 0.0                       # texto libre: no mueve nada
        res["delta"] = delta
        touched = {page_idx}

        # Con etiqueta o viñeta («h)», «•») solo se borra el cuerpo: así se conservan tal cual,
        # con su fuente (las viñetas suelen ser de la fuente Symbol). Si se vacía el párrafo, todo.
        keep_label = bool(para.get("label")) and bool(lines)
        left = para["body_x"] - 0.5 if keep_label else x0
        if y1 - y0 > 1.0:                     # un párrafo nuevo no tiene nada que borrar
            pg.add_redact_annot(fitz.Rect(left, y0, x1, y1) + (0.3, 0.3, -0.3, -0.3), fill=False)
            pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        if shift and abs(delta) > 0.01:
            _shift_down(doc, page_idx, y1 + 0.5, para["shift_x0"], para["shift_x1"], delta, geo, touched)

        centre = (x0 + x1) / 2
        justify = para["align"] == "justify"

        def draw(page, line: dict, baseline: float, first: bool):
            left = para["x_first"] if first else para["x_cont"]
            if para["align"] == "center":
                left = centre - line["width"] / 2
            if justify and not line["hard"]:
                spaces = sum(1 for e in line["els"] if e[0] == "s")
                extra = (para["wrap_right"] - left - line["width"]) / spaces if spaces else 0.0
                x = left
                for e in line["els"]:
                    if e[0] == "s":
                        put(page, x, baseline, " ", e[1])
                        x += e[2] + max(extra, 0.0)
                    else:
                        for text, st, w in e[1]:
                            put(page, x, baseline, text, st)
                            x += w
                return
            x, buf, buf_st = left, "", None
            for e in line["els"]:
                segs = [(" ", e[1], e[2])] if e[0] == "s" else e[1]
                for text, st, w in segs:
                    if buf_st is not None and st != buf_st:
                        put(page, x, baseline, buf, buf_st)
                        x += sum(width_of(c, buf_st) for c in buf)
                        buf = ""
                    buf_st = st
                    buf += text
            if buf:
                put(page, x, baseline, buf.rstrip() if buf.strip() else buf, buf_st)

        pg = doc[page_idx]                    # las páginas previas pueden haber quedado huérfanas
        for i, line in enumerate(lines[:n_fit]):
            draw(pg, line, para["origin_y"] + i * new_pitch, i == 0)
        extra_lines = lines[n_fit:]
        if extra_lines:
            nxt = page_idx + 1
            _ensure_page(doc, nxt, geo, touched)
            top = _page_top(doc, nxt, geo)
            below = [a[1] for a in _atoms(doc, page_idx) if a[4] == 0 and a[1] > y1 + 0.5]
            gap = min(max((min(below) - y1) if below else 0.7 * pitch, 4.0), 40.0)   # hueco tras el párrafo
            _shift_down(doc, nxt, top, 0, doc[nxt].rect.width, len(extra_lines) * new_pitch + gap,
                        geo, touched)
            for j, line in enumerate(extra_lines):
                draw(doc[nxt], line, top + (para["origin_y"] - y0) + j * new_pitch, False)
            touched.add(nxt)
        if shift and not lines and para.get("label"):        # se borró un elemento de lista: renumera
            _renumber_after_delete(doc, page_idx, y0 - 3, para["label"]["text"], touched)
        added = doc.page_count - pages_before
        if added and geo["settings"]["numbering"]:
            _update_totals(doc, geo, added, touched)
        res["pages"] = sorted(touched)
        res["ok"] = True
    except Exception:
        if os.environ.get("PDF_DEBUG"):
            import traceback
            traceback.print_exc()
        res["ok"] = False
    return res


def _parse_label(text: str):
    """«(a)», «a)», «1.», «1.1.», «2.3)» → (prefijo, [partes], sufijo); None si no es de texto."""
    m = re.match(r"^(\(?)([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)([\.\)])$", text.strip())
    if not m:
        return None
    return m.group(1), m.group(2).split("."), m.group(3)


def _fmt_label(pre: str, parts: list, suf: str) -> str:
    return pre + ".".join(parts) + suf


def _step_part(part: str, delta: int):
    """Una parte de la etiqueta ±1: 3 → 4, c → d (z → aa)."""
    if part.isdigit():
        v = int(part) + delta
        return str(v) if v >= 1 else None
    if len(part) == 1 and part.isalpha():
        if delta > 0 and part in "zZ":
            return "aa" if part == "z" else "AA"
        c = ord(part) + delta
        return chr(c) if (part.isupper() and 65 <= c <= 90) or (part.islower() and 97 <= c <= 122) else None
    return None


def _next_label(text: str):
    """Etiqueta siguiente en la serie: a) → b), 1. → 2., 1.1. → 1.2.; None si no es de texto."""
    p = _parse_label(text)
    if p is None:
        return None
    nxt = _step_part(p[1][-1], +1)
    return None if nxt is None else _fmt_label(p[0], p[1][:-1] + [nxt], p[2])


def _renumber_series(doc, page_idx: int, after_y: float, first_old: str, delta: int, touched: set):
    """Desplaza delta (+1 al insertar un elemento, −1 al borrarlo) la etiqueta de cada
    elemento de la serie que empieza en el que valía `first_old`, y con él los de sus
    subniveles (si «2.» pasa a «3.», «2.1.» pasa a «3.1.»). Sigue por las páginas
    siguientes. Las viñetas y las listas de otro tipo se saltan; una etiqueta del mismo
    tipo y nivel que no sea la esperada (u otra de nivel superior) cierra la serie."""
    base = _parse_label(first_old)
    if base is None:
        return
    pre, parts0, suf = base
    depth = len(parts0)
    expected = first_old.strip()
    last_old = last_new = None
    for pno in range(page_idx, doc.page_count):
        for p in sorted(get_page_paragraphs(doc, pno), key=lambda q: q["bbox"][1]):
            if pno == page_idx and p["bbox"][1] <= after_y:
                continue
            lab = p.get("label")
            parsed = _parse_label(lab["text"]) if lab else None
            if parsed is None or (parsed[0], parsed[2]) != (pre, suf):
                continue                                   # viñeta o lista de otro tipo
            parts = parsed[1]
            span = {"bbox": lab["span"]["bbox"], "spans": [lab["span"]], "text": lab["span"]["text"]}
            if len(parts) == depth:
                if lab["text"].strip() != expected:
                    return
                stepped = _step_part(parts[-1], delta)
                nxt_old = _step_part(parts[-1], +1)
                if stepped is None or nxt_old is None:
                    return
                new_parts = parts[:-1] + [stepped]
                _rewrite_line(doc[pno], span, _fmt_label(pre, new_parts, suf))
                touched.add(pno)
                last_old, last_new = parts, new_parts
                expected = _fmt_label(pre, parts[:-1] + [nxt_old], suf)
            elif len(parts) > depth and last_old is not None and parts[:depth] == last_old:
                _rewrite_line(doc[pno], span, _fmt_label(pre, last_new + parts[depth:], suf))
                touched.add(pno)
            elif len(parts) < depth:
                return                                     # sube de nivel: acaba la serie


def _renumber_siblings(doc, page_idx: int, after_y: float, expected: str, touched: set):
    """Tras insertar un elemento con la etiqueta `expected`, los siguientes suben una posición."""
    _renumber_series(doc, page_idx, after_y, expected, +1, touched)


def _renumber_after_delete(doc, page_idx: int, after_y: float, deleted_label: str, touched: set):
    """Al borrar un elemento, el siguiente toma su etiqueta, el siguiente la del anterior…"""
    nxt = _next_label(deleted_label)
    if nxt is not None:
        _renumber_series(doc, page_idx, after_y, nxt, -1, touched)


def _subtree_bottom(doc, page_idx: int, para: dict, limit: float) -> float:
    """Dónde acaba un elemento de lista con todo lo que cuelga de él en la página: subniveles,
    viñetas y párrafos sangrados. Acaba al volver al margen, en un hermano del mismo nivel
    o en uno de nivel superior."""
    bottom = para["bbox"][3]
    lab = para.get("label")
    parsed = _parse_label(lab["text"]) if lab else None
    if parsed is None:
        return bottom
    pre, parts, suf = parsed
    for q in sorted(get_page_paragraphs(doc, page_idx), key=lambda r: r["bbox"][1]):
        if q["bbox"][1] <= para["bbox"][1] + 1:
            continue
        if q["bbox"][1] >= limit or q["bbox"][0] < para["bbox"][0] - 0.5:
            break
        ql = q.get("label")
        qp = _parse_label(ql["text"]) if ql else None
        if qp is not None and (qp[0], qp[2]) == (pre, suf) and len(qp[1]) <= len(parts):
            break
        bottom = max(bottom, q["bbox"][3])
    return bottom


def insert_item_below(doc, page_idx: int, para: dict, text: str = "Novo elemento", settings=None) -> dict:
    """Inserta debajo de `para` un elemento con su mismo estilo y, si lo tenía,
    etiqueta siguiente (a) → b)) o viñeta copiada. Lo de abajo se desplaza y las
    etiquetas de la serie que seguían se renumeran. Devuelve {ok, page, y, pages}."""
    res = {"ok": False, "page": page_idx, "y": 0.0, "pages": [], "font_found": True, "family": ""}
    src = None
    try:
        pg = doc[page_idx]
        geo = _geo_with_settings(_doc_geometry(doc), settings)
        limit = _limit(geo, pg.rect)
        x0, y0, x1, y1 = para["bbox"]
        y1 = _subtree_bottom(doc, page_idx, para, limit)          # tras sus subniveles y viñetas
        pitch, offset = para["pitch"], para["origin_y"] - para["bbox"][1]
        below = [a[1] for a in _atoms(doc, page_idx) if a[4] == 0 and a[1] > y1 + 0.5]
        gap = min(max((min(below) - y1) if below else 0.8 * pitch, 4.0), 40.0)
        src = fitz.open()
        src.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        touched = {page_idx}
        target, anchor, y_top = page_idx, y1, y1 + gap
        if y_top + pitch > limit + 0.5:                   # no cabe aquí: va arriba de la página siguiente
            target = page_idx + 1
            _ensure_page(doc, target, geo, touched)
            y_top = _page_top(doc, target, geo)
            anchor = y_top - 0.5
        runs_src = para.get("runs") or []
        main = max(runs_src, key=lambda r: len(r["text"].strip())) if runs_src else None
        style = ({k: main[k] for k in ("font", "family", "bold", "italic", "size", "color")} if main else
                 {"font": para["font"], "family": None, "bold": None, "italic": None,
                  "size": para["size"], "color": para["color"]})
        syn = {"bbox": (x0, anchor, x1, anchor), "n_lines": 0, "pitch": pitch,
               "origin_y": y_top + offset, "size": para["size"], "font": para["font"],
               "color": para["color"], "x_first": para["x_first"], "x_cont": para["x_cont"],
               "body_x": para["body_x"], "align": para["align"], "label": None,
               "wrap_first": para["wrap_first"], "wrap_cont": para["wrap_cont"],
               "wrap_right": para.get("wrap_right", x1), "shift_x0": para["shift_x0"],
               "shift_x1": para["shift_x1"]}
        r = replace_paragraph_in_doc(doc, target, syn, text, para["size"], para["color"],
                                     settings=settings, runs=[{"text": text, **style}], insert_gap=gap)
        if not r["ok"]:
            return res
        touched.update(r["pages"])
        lab = para.get("label")
        if lab:
            span = lab["span"]
            new_label = _next_label(span["text"])
            if new_label:                                  # a) → b), 1.1. → 1.2.
                mf, _ff, b14 = _resolve_font(span["font"], None, None, None)
                _insert_text_with_fallback(doc[target], fitz.Point(span["bbox"][0], y_top + offset),
                                           new_label, span["size"], mf, _rgb_tuple(span["color"]), b14)
                # el propio elemento nuevo (una línea) no cuenta: se empieza tras él
                _renumber_siblings(doc, target, y_top + 0.9 * pitch, new_label, touched)
            else:                                          # viñeta: se copia tal cual (símbolo, no texto)
                dy = (y_top + offset) - para["origin_y"]
                box = fitz.Rect(span["bbox"])
                doc[target].show_pdf_page(box + (0, dy, 0, dy), src, 0, clip=box)
        res.update(ok=True, page=target, y=y_top, pages=sorted(touched),
                   font_found=r["font_found"], family=r["family"])
    except Exception:
        if os.environ.get("PDF_DEBUG"):
            import traceback
            traceback.print_exc()
    finally:
        if src is not None:
            src.close()
    return res


def add_text_box(doc, page_idx: int, x: float, y_top: float, runs: list, settings=None) -> dict:
    """Escribe texto libre en una página, con su esquina superior izquierda en (x, y_top).
    Se ajusta al margen derecho y no mueve nada del resto de la página."""
    runs = [r for r in runs if r["text"]]
    res = {"ok": False, "pages": [page_idx], "font_found": True, "family": ""}
    if not runs:
        return res
    pg = doc[page_idx]
    geo = _geo_with_settings(_doc_geometry(doc), settings)
    size = float(runs[0]["size"])
    right = max(pg.rect.width - geo["left"], x + 60)
    syn = {"bbox": (x, y_top, x, y_top), "n_lines": 0, "pitch": size * 1.2, "origin_y": y_top + size * 0.9,
           "size": size, "font": runs[0]["font"], "color": runs[0]["color"], "x_first": x, "x_cont": x,
           "body_x": x, "align": "left", "label": None, "wrap_first": right - x, "wrap_cont": right - x,
           "wrap_right": right, "shift_x0": 0.0, "shift_x1": pg.rect.width}
    r = replace_paragraph_in_doc(doc, page_idx, syn, "".join(r_["text"] for r_ in runs), size,
                                 runs[0]["color"], settings=settings, runs=runs, shift=False)
    res.update(ok=r["ok"], font_found=r["font_found"], family=r["family"])
    return res


BLANK_HF = {"header_boxes": [], "footer_boxes": [], "repeat_header": False, "repeat_footer": False,
            "numbering": False, "background": False}


def page_background(doc, idx: int) -> dict | None:
    """Fondo de página completa que se repite en el documento: {"images": [xref…], "fill": (r, g, b) o None}.
    Cuenta como fondo una imagen que cubre casi toda la página y es LA MISMA en otra página (si cada página tiene su
    propia imagen es un escaneo, no un fondo), o un rectángulo de color que llena la página. None si no hay."""
    try:
        page = doc[idx]
        r = page.rect
        area = max(r.width * r.height, 1.0)
        others = [i for i in range(len(doc)) if i != idx][:8]
        images = []
        for info in page.get_image_info(xrefs=True):
            x = info.get("xref") or 0
            b = fitz.Rect(info["bbox"]) & r
            if x and b.width * b.height >= 0.8 * area:
                if any(x in {im[0] for im in doc[o].get_images()} for o in others):
                    images.append(x)
        fill = None
        for d in page.get_drawings():
            rc = fitz.Rect(d["rect"]) & r
            if d.get("fill") and rc.width * rc.height >= 0.95 * area and not d.get("color"):
                if any(any(fitz.Rect(e["rect"]).get_area() >= 0.95 * area and e.get("fill") == d["fill"]
                           for e in doc[o].get_drawings()) for o in others[:3]):
                    fill = tuple(d["fill"])
                break
        if images or fill:
            return {"images": images, "fill": fill}
    except Exception:
        pass
    return None


def has_header_footer(doc, at: int, settings=None) -> bool:
    """¿Hay cabecera o pie que copiar a una página nueva en la posición `at`? (detectados o marcados por el usuario)"""
    try:
        if settings is not None:
            return bool(settings.get("header_boxes") or settings.get("footer_boxes"))
        ref = max(0, min(at - 1 if at > 0 else 0, doc.page_count - 1))
        h, f = auto_header_footer(doc, ref)
        return bool(h or f or page_background(doc, ref))
    except Exception:
        return False


def preview_inserted_page(doc, at: int, settings=None, width: int = 260) -> bytes | None:
    """PNG de cómo quedaría la página nueva en la posición `at` con esos ajustes (se prueba en una copia)."""
    try:
        tmp = fitz.open(stream=doc.tobytes(), filetype="pdf")
        res = insert_page(tmp, at, settings=settings)
        if not res.get("ok"):
            tmp.close()
            return None
        pg = tmp[min(at, tmp.page_count - 1)]
        z = width / max(pg.rect.width, 1.0)
        png = pg.get_pixmap(matrix=fitz.Matrix(z, z)).tobytes("png")
        tmp.close()
        return png
    except Exception:
        return None


def insert_pdf_pages(doc, at: int, path: str) -> dict:
    """Inserta todas las páginas de otro PDF en la posición `at`."""
    res = {"ok": False, "count": 0}
    try:
        src = fitz.open(path)
        if src.needs_pass:
            src.close()
            return res
        n = src.page_count
        doc.insert_pdf(src, start_at=max(0, min(at, doc.page_count)))
        src.close()
        res.update(ok=True, count=n)
    except Exception:
        pass
    return res


def insert_page(doc, at: int, settings=None) -> dict:
    """Añade una página en la posición `at` (0 = al principio, page_count = al final), del
    tamaño de la vecina. Copia la cabecera y el pie según los ajustes (iguales, o de la de
    dos antes si pares e impares difieren), pone su número de página y renumera las
    siguientes, incluidos los totales («de 5»)."""
    n = doc.page_count
    at = max(0, min(at, n))
    res = {"ok": False, "pages": [], "page": at}
    try:
        geo = _geo_with_settings(_doc_geometry(doc), settings)
        s = geo["settings"]
        ref_idx = at - 1 if at > 0 else 0
        ref = fitz.Rect(doc[ref_idx].rect)
        touched = {at}
        doc.new_page(at if at < n else -1, width=ref.width, height=ref.height)
        if s.get("background", True):                              # el fondo de página completa también se repite
            bg = page_background(doc, ref_idx if ref_idx != at else min(at + 1, doc.page_count - 1))
            if bg:
                newp = doc[at]
                if bg["fill"]:
                    newp.draw_rect(newp.rect, color=None, fill=bg["fill"], overlay=False)
                for x in bg["images"]:
                    newp.insert_image(newp.rect, xref=x, overlay=False)
        if at > 0:
            src_idx = at - 2 if s["parity"] and at - 2 >= 0 and _size_key(doc[at - 2].rect) == _size_key(ref) \
                else at - 1
        else:
            src_idx = 1 if doc.page_count > 1 else None
        if src_idx is not None:
            header, footer = _hf(geo, ref)
            bands = []
            if header and s["repeat_header"]:
                bands.append(fitz.Rect(0, 0, ref.width, header + 2))
            if footer and s["repeat_footer"] and footer < ref.height - 4:
                bands.append(fitz.Rect(0, footer - 2, ref.width, ref.height))
            if bands:
                src = fitz.open()
                try:
                    src.insert_pdf(doc, from_page=src_idx, to_page=src_idx)
                    for band in bands:
                        doc[at].show_pdf_page(band, src, 0, clip=band)
                finally:
                    src.close()
                if s["numbering"] and src_idx < at:
                    _renumber_page(doc, at, src_idx, geo)
        if s["numbering"]:
            for p in range(at + 1, doc.page_count):
                _bump_page_numbers(doc, p, 1, geo)
                touched.add(p)
            _update_totals(doc, geo, 1, touched)
        res.update(ok=True, pages=sorted(touched))
    except Exception:
        if os.environ.get("PDF_DEBUG"):
            import traceback
            traceback.print_exc()
    return res


def delete_pages(doc, indices: list, settings=None) -> dict:
    """Borra páginas (por posición, desde 0). Las siguientes bajan su número de página y
    los totales («de 5») se corrigen. No se puede borrar todo el documento."""
    res = {"ok": False, "pages": [], "removed": 0}
    idx = sorted({i for i in indices if 0 <= i < doc.page_count}, reverse=True)
    if not idx or len(idx) >= doc.page_count:
        return res
    try:
        geo = _geo_with_settings(_doc_geometry(doc), settings)
        numbering = geo["settings"]["numbering"]
        first = min(idx)
        for i in idx:
            doc.delete_page(i)
        touched = set()
        if numbering:
            # la página que ahora está en new_pos era la old_pos; baja tantos números como
            # páginas borradas hubiera antes de ella
            kept = [o for o in range(doc.page_count + len(idx)) if o not in set(idx)]
            for new_pos, old_pos in enumerate(kept):
                before = sum(1 for i in idx if i < old_pos)
                if before:
                    _bump_page_numbers(doc, new_pos, -before, geo)
                    touched.add(new_pos)
            _update_totals(doc, geo, -len(idx), touched)
        res.update(ok=True, pages=sorted(touched), removed=len(idx))
    except Exception:
        if os.environ.get("PDF_DEBUG"):
            import traceback
            traceback.print_exc()
    return res


def paragraph_edit_adds_pages(doc, page_idx: int, para: dict, new_text: str, size: float,
                              color, family=None, bold=None, italic=None, runs=None) -> int:
    """Cuántas páginas nuevas crearía esta edición (se prueba en una copia)."""
    try:
        tmp = fitz.open("pdf", doc.tobytes())
        try:
            before = tmp.page_count
            replace_paragraph_in_doc(tmp, page_idx, para, new_text, size, color, family, bold, italic,
                                     runs=[dict(r) for r in runs] if runs else None)
            return tmp.page_count - before
        finally:
            tmp.close()
    except Exception:
        return 0


def censor_rect_in_doc(doc, page_idx: int, bbox: tuple) -> bool:
    """Tapa con una barra negra sólida e irreversible un área rectangular
    exacta (en puntos PDF) de una página YA ABIERTA en sesión de edición.
    No busca nada: censura justo el rectángulo recibido tal cual (se usa
    para un clic directo sobre un fragmento de texto ya localizado)."""
    if not HAS_FITZ:
        return False
    try:
        pg = doc[page_idx]
        r = fitz.Rect(*bbox)
        pg.add_redact_annot(r, fill=(0, 0, 0))
        pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
        return True
    except Exception:
        return False


def censor_area_in_doc(doc, page_idx: int, bbox: tuple) -> bool:
    """Censura un área arrastrada con el ratón de forma inteligente: si hay
    texto dentro de esa zona, tapa solo las palabras exactas que caen en
    ella (nada de manchas negras gigantes); si no hay texto (una foto, una
    firma…), tapa el rectángulo completo tal como se arrastró."""
    if not HAS_FITZ:
        return False
    try:
        pg = doc[page_idx]
        r = fitz.Rect(*bbox)
        words = pg.get_text("words")
        hits = [fitz.Rect(w[:4]) for w in words if fitz.Rect(w[:4]).intersects(r)]
        if hits:
            for wr in hits:
                pg.add_redact_annot(wr, fill=(0, 0, 0))
            pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        else:
            pg.add_redact_annot(r, fill=(0, 0, 0))
            pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
        return True
    except Exception:
        return False


def rotate_pages(doc, idxs: list, delta: int) -> bool:
    """Gira páginas (múltiplos de 90°) con la marca estándar /Rotate: el contenido no se toca."""
    try:
        for i in idxs:
            pg = doc[i]
            pg.set_rotation((pg.rotation + int(delta)) % 360)
        return True
    except Exception:
        return False


def snapshot_doc_bytes(doc) -> bytes | None:
    """Captura el estado actual (en memoria) de una sesión de edición, para
    poder volver a él con 'deshacer'."""
    if not HAS_FITZ or doc is None:
        return None
    try:
        # Sin garbage: limpiar renumera los objetos del documento vivo y PyMuPDF guarda xref de fuentes
        return doc.tobytes(deflate=True)
    except Exception:
        return None


def doc_from_bytes(data: bytes):
    """Reabre una sesión de edición a partir de una foto tomada con
    snapshot_doc_bytes (deshacer/rehacer)."""
    if not HAS_FITZ or not data:
        return None
    try:
        return fitz.open(stream=data, filetype="pdf")
    except Exception:
        return None


def save_edit_session(doc, original_path: str) -> str | None:
    """Guarda los cambios acumulados de la sesión en un PDF nuevo en
    Descargas. No cierra el documento (la sesión puede seguir editando)."""
    try:
        stem = Path(original_path).stem
        out_path = DOWNLOADS / f"{stem}_editado.pdf"
        try:
            # Cada edición incrusta la fuente que usa: se reducen a los caracteres usados, en una
            # copia (la sesión puede seguir editando). Un PDF editado pasa de MB a unos KB.
            tmp = fitz.open("pdf", doc.tobytes())
            try:
                tmp.subset_fonts()
                tmp.save(str(out_path), deflate=True, garbage=4)
            finally:
                tmp.close()
        except Exception:
            doc.save(str(out_path), deflate=True, garbage=4)
        return str(out_path)
    except Exception:
        return None


# ── METADATOS ─────────────────────────────────────────────────────────────
def read_metadata(path: str) -> dict:
    if not HAS_FITZ:
        return {}
    try:
        doc = fitz.open(path)
        meta = dict(doc.metadata or {})
        doc.close()
        return meta
    except Exception:
        return {}


def format_pdf_date(raw: str) -> str:
    """'D:20240315142030+01'00'' -> '15/03/2024 14:20'. Vacío si no hay fecha."""
    if not raw or not raw.startswith("D:"):
        return "—"
    digits = raw[2:16]
    try:
        dt = datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(digits[:8], "%Y%m%d")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            return "—"


def write_metadata(path: str, meta: dict) -> str | None:
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


# ── DIVIDIR PDF ───────────────────────────────────────────────────────────


def extract_pages_as_files(path: str, pages_per_file: list[list[int]],
                            names: list[str]) -> list[tuple[str, bytes]]:
    """
    pages_per_file: una lista de listas de índices de página (0-based), una
    por archivo de salida. names: nombre (sin extensión) de cada archivo,
    mismo largo que pages_per_file. Devuelve [(nombre.pdf, bytes), ...],
    sin escribir nada a disco todavía (lo decide quien llame: carpeta o zip).
    """
    reader = PdfReader(path)
    outputs = []
    for idxs, name in zip(pages_per_file, names):
        writer = PdfWriter()
        for i in idxs:
            writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        safe_name = name if name.lower().endswith(".pdf") else f"{name}.pdf"
        outputs.append((safe_name, buf.getvalue()))
    return outputs


def save_outputs_to_folder(outputs: list[tuple[str, bytes]], folder: str) -> list[str]:
    out_dir = Path(folder)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, data in outputs:
        p = out_dir / name
        with open(p, "wb") as f:
            f.write(data)
        paths.append(str(p))
    return paths


def save_outputs_to_zip(outputs: list[tuple[str, bytes]], zip_path: str) -> str:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in outputs:
            zf.writestr(name, data)
    return zip_path


# ── AJUSTE DE IMAGEN (brillo / contraste / saturación / B&N) ────────────
def get_adjusted_page_image(path: str, page_idx: int, brillo: float,
                             contraste: float, saturacion: float,
                             bw: bool, zoom: float = 1.3):
    """Devuelve una PIL.Image con los ajustes aplicados a una página,
    para previsualización en la UI."""
    if not (HAS_FITZ and HAS_PIL):
        return None
    try:
        doc = fitz.open(path)
        pg = doc[page_idx]
        mat = fitz.Matrix(zoom, zoom)
        pix = pg.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        img = ImageEnhance.Brightness(img).enhance(1.0 + brillo)
        img = ImageEnhance.Contrast(img).enhance(contraste)
        if bw:
            img = img.convert("L").convert("RGB")
        else:
            img = ImageEnhance.Color(img).enhance(saturacion)
        return img
    except Exception:
        return None


def apply_adjustment_to_pdf(path: str, brillo: float, contraste: float,
                             saturacion: float, bw: bool,
                             pages: list[int] | None = None,
                             dpi: int = 150) -> str | None:
    """
    Aplica el ajuste a 'pages' (None = todas) y reinserta cada página como
    imagen. Las páginas no incluidas en 'pages' se copian sin modificar.
    Devuelve la ruta del PDF resultante.
    """
    if not (HAS_FITZ and HAS_PIL):
        return None
    try:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        doc = fitz.open(path)
        total = len(doc)
        target = set(pages) if pages is not None else set(range(total))
        out_doc = fitz.open()
        for pn in range(total):
            pg = doc[pn]
            pix = pg.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            if pn in target:
                img = ImageEnhance.Brightness(img).enhance(1.0 + brillo)
                img = ImageEnhance.Contrast(img).enhance(contraste)
                if bw:
                    img = img.convert("L").convert("RGB")
                else:
                    img = ImageEnhance.Color(img).enhance(saturacion)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            new_page = out_doc.new_page(width=pg.rect.width, height=pg.rect.height)
            new_page.insert_image(new_page.rect, stream=buf.read())
        stem = Path(path).stem
        suffix = "_bw" if bw else "_ajuste"
        out_path = DOWNLOADS / f"{stem}{suffix}.pdf"
        out_doc.save(str(out_path), deflate=True, garbage=4)
        out_doc.close()
        doc.close()
        return str(out_path)
    except Exception:
        return None


# ── TAMAÑO DE PÁGINA Y MÁRGENES ──────────────────────────────────────────
MM_TO_PT = 72.0 / 25.4

PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Carta (Letter)": (215.9, 279.4),
    "Legal": (215.9, 355.6),
}


def _target_size_pt(size_name: str, custom_w_mm: float | None,
                    custom_h_mm: float | None) -> tuple[float, float]:
    if size_name == "Personalizado" and custom_w_mm and custom_h_mm:
        return custom_w_mm * MM_TO_PT, custom_h_mm * MM_TO_PT
    w_mm, h_mm = PAGE_SIZES_MM.get(size_name, (210.0, 297.0))
    return w_mm * MM_TO_PT, h_mm * MM_TO_PT


def _resize_page_into(out_doc, doc, page_idx: int, tw: float, th: float, fit_mode: str):
    pg = doc[page_idx]
    new_page = out_doc.new_page(width=tw, height=th)
    if fit_mode == "center":
        ow, oh = pg.rect.width, pg.rect.height
        x0, y0 = (tw - ow) / 2.0, (th - oh) / 2.0
        rect = fitz.Rect(x0, y0, x0 + ow, y0 + oh)
    else:
        rect = new_page.rect
    new_page.show_pdf_page(rect, doc, page_idx)


def _apply_margins_to_page(pg, top_mm: float, bottom_mm: float,
                           left_mm: float, right_mm: float) -> bool:
    mb = pg.mediabox
    new_rect = fitz.Rect(
        mb.x0 - left_mm * MM_TO_PT,
        mb.y0 - bottom_mm * MM_TO_PT,
        mb.x1 + right_mm * MM_TO_PT,
        mb.y1 + top_mm * MM_TO_PT,
    )
    if new_rect.width < 10 or new_rect.height < 10:
        return False
    pg.set_mediabox(new_rect)
    return True


def _fit_cell(pw: float, ph: float, cw: float, ch: float,
              auto_rotate: bool) -> tuple[float, bool]:
    """(escala, girar90) para meter una página pw×ph en una celda cw×ch.
    Solo gira si así se aprovecha claramente más la celda (>1 %)."""
    s0 = min(cw / pw, ch / ph)
    if auto_rotate:
        s1 = min(cw / ph, ch / pw)
        if s1 > s0 * 1.01:
            return s1, True
    return s0, False


def _nup_sheet_into(out_doc, doc, start: int, cols: int, rows: int,
                    tw: float, th: float, gap: float, auto_rotate: bool = True) -> None:
    total = len(doc)
    cell_w = (tw - gap * (cols + 1)) / cols
    cell_h = (th - gap * (rows + 1)) / rows
    new_page = out_doc.new_page(width=tw, height=th)
    for i in range(cols * rows):
        src_idx = start + i
        if src_idx >= total:
            break
        col, row = i % cols, i // cols
        cx0 = gap + col * (cell_w + gap)
        cy0 = gap + row * (cell_h + gap)
        pr = doc[src_idx].rect
        scale, rot = _fit_cell(pr.width, pr.height, cell_w, cell_h, auto_rotate)
        dw, dh = (pr.height * scale, pr.width * scale) if rot else (pr.width * scale, pr.height * scale)
        dx = cx0 + (cell_w - dw) / 2.0
        dy = cy0 + (cell_h - dh) / 2.0
        new_page.show_pdf_page(fitz.Rect(dx, dy, dx + dw, dy + dh), doc, src_idx,
                               rotate=90 if rot else 0)


_AUTO_GAP_MM = 3.0
_MIN_CELL_PT = 20.0


def _max_gap_pt(tw: float, th: float, cols: int, rows: int) -> float:
    """Mayor espacio posible sin que las celdas queden por debajo de un mínimo."""
    return max(0.0, min((tw - cols * _MIN_CELL_PT) / (cols + 1),
                        (th - rows * _MIN_CELL_PT) / (rows + 1)))


def _auto_gap_pt(tw: float, th: float, cols: int, rows: int) -> float:
    """Espacio 'ideal' de 3 mm que se sacrifica (hasta 0) cuando la cuadrícula
    es tan densa que el hueco se comería más de un 8 % de la hoja."""
    return max(0.0, min(_AUTO_GAP_MM * MM_TO_PT,
                        0.08 * tw / (cols + 1), 0.08 * th / (rows + 1),
                        _max_gap_pt(tw, th, cols, rows)))


def _resolve_gap_pt(tw: float, th: float, cols: int, rows: int,
                    gap_mm: float | None) -> float:
    """gap_mm=None → automático; si no, el valor pedido, recortado solo lo
    imprescindible para que las celdas sigan existiendo."""
    if gap_mm is None:
        return _auto_gap_pt(tw, th, cols, rows)
    return min(gap_mm * MM_TO_PT, _max_gap_pt(tw, th, cols, rows))


def _oriented(tw: float, th: float, orientation: str) -> tuple[float, float]:
    short, long_ = sorted((tw, th))
    return (long_, short) if orientation == "landscape" else (short, long_)


def _nup_layout(doc, cols: int, rows: int, size_name: str, custom_w_mm: float | None,
                custom_h_mm: float | None, gap_mm: float | None,
                orientation: str = "auto",
                auto_rotate: bool = True) -> tuple[float, float, float, str]:
    """(ancho, alto, espacio, orientación elegida) de la hoja de salida.
    'auto' escoge la orientación en la que las páginas salen más grandes
    (con el giro por página en cuenta) y, a igualdad, la que gira menos."""
    base_w, base_h = _target_size_pt(size_name, custom_w_mm, custom_h_mm)
    rects = [doc[i].rect for i in range(min(len(doc), 60))]

    def layout(o: str):
        tw, th = _oriented(base_w, base_h, o)
        gap = _resolve_gap_pt(tw, th, cols, rows, gap_mm)
        return tw, th, gap, (tw - gap * (cols + 1)) / cols, (th - gap * (rows + 1)) / rows

    if orientation in ("portrait", "landscape"):
        chosen = orientation
    else:
        def score(o: str) -> tuple[float, int]:
            *_, cw, ch = layout(o)
            total, turned = 0.0, 0
            for r in rects:
                if r.width > 0 and r.height > 0:
                    s, rot = _fit_cell(r.width, r.height, cw, ch, auto_rotate)
                    total += s
                    turned += rot
            return total, turned
        (sp, rp), (sl, rl) = score("portrait"), score("landscape")
        better = sl > sp * 1.001
        tie = abs(sl - sp) <= sp * 0.001
        chosen = "landscape" if better or (tie and rl < rp) else "portrait"
    tw, th, gap, *_ = layout(chosen)
    return tw, th, gap, chosen


def nup_resolved_orientation(path: str, cols: int, rows: int, size_name: str = "A4",
                             custom_w_mm: float | None = None, custom_h_mm: float | None = None,
                             gap_mm: float | None = None, orientation: str = "auto",
                             auto_rotate: bool = True) -> str:
    """'portrait' o 'landscape': la orientación con la que saldría el N-Up."""
    if not HAS_FITZ:
        return "portrait"
    try:
        doc = fitz.open(path)
        o = _nup_layout(doc, max(1, int(cols)), max(1, int(rows)), size_name,
                        custom_w_mm, custom_h_mm, gap_mm, orientation, auto_rotate)[3]
        doc.close()
        return o
    except Exception:
        return "portrait"


def auto_gap_mm(size_name: str, custom_w_mm: float | None, custom_h_mm: float | None,
                cols: int, rows: int, orientation: str = "portrait") -> float:
    tw, th = _oriented(*_target_size_pt(size_name, custom_w_mm, custom_h_mm), orientation)
    return _auto_gap_pt(tw, th, max(1, int(cols)), max(1, int(rows))) / MM_TO_PT


def resize_pdf(path: str, size_name: str, fit_mode: str,
                custom_w_mm: float | None = None,
                custom_h_mm: float | None = None) -> str | None:
    """Cambia el tamaño de página de todo el documento.
    fit_mode: 'scale' escala el contenido para llenar la nueva hoja;
    'center' mantiene el tamaño original del contenido y lo centra."""
    if not HAS_FITZ:
        return None
    try:
        tw, th = _target_size_pt(size_name, custom_w_mm, custom_h_mm)
        doc = fitz.open(path)
        out_doc = fitz.open()
        for i in range(len(doc)):
            _resize_page_into(out_doc, doc, i, tw, th, fit_mode)
        stem = Path(path).stem
        safe_name = size_name.split()[0] if size_name != "Personalizado" else "custom"
        out_path = DOWNLOADS / f"{stem}_{safe_name}.pdf"
        out_doc.save(str(out_path), deflate=True, garbage=4)
        out_doc.close()
        doc.close()
        return str(out_path)
    except Exception:
        return None


def adjust_margins_pdf(path: str, top_mm: float, bottom_mm: float,
                        left_mm: float, right_mm: float) -> str | None:
    """Cambia los márgenes de cada página. Valores positivos añaden margen
    (espacio en blanco) en ese borde; valores negativos recortan ese borde
    (el contenido fuera de la nueva caja de página deja de verse/imprimirse)."""
    if not HAS_FITZ:
        return None
    try:
        doc = fitz.open(path)
        for pg in doc:
            _apply_margins_to_page(pg, top_mm, bottom_mm, left_mm, right_mm)
        stem = Path(path).stem
        out_path = DOWNLOADS / f"{stem}_margenes.pdf"
        doc.save(str(out_path), deflate=True, garbage=4)
        doc.close()
        return str(out_path)
    except Exception:
        return None


def n_up_pdf(path: str, cols: int, rows: int, size_name: str = "A4",
             custom_w_mm: float | None = None, custom_h_mm: float | None = None,
             gap_mm: float | None = None, orientation: str = "auto",
             auto_rotate: bool = True) -> str | None:
    """Combina varias páginas originales en cada hoja de salida (p.ej. 2x2 =
    4 páginas por hoja), cada una escalada para caber en su celda manteniendo
    proporción, en el orden original (izq→der, arriba→abajo).
    orientation: 'auto' | 'portrait' | 'landscape' (de la hoja de salida).
    auto_rotate: gira 90° las páginas que así llenan mejor su celda."""
    if not HAS_FITZ:
        return None
    try:
        cols, rows = max(1, int(cols)), max(1, int(rows))
        per_sheet = cols * rows
        doc = fitz.open(path)
        tw, th, gap, _ = _nup_layout(doc, cols, rows, size_name, custom_w_mm,
                                     custom_h_mm, gap_mm, orientation, auto_rotate)
        out_doc = fitz.open()
        for start in range(0, len(doc), per_sheet):
            _nup_sheet_into(out_doc, doc, start, cols, rows, tw, th, gap, auto_rotate)
        stem = Path(path).stem
        out_path = DOWNLOADS / f"{stem}_{per_sheet}up.pdf"
        out_doc.save(str(out_path), deflate=True, garbage=4)
        out_doc.close()
        doc.close()
        return str(out_path)
    except Exception:
        return None


# ── VISTA PREVIA (en memoria, sin escribir nada a disco) ─────────────────
def _page_png(page, max_w: int, max_h: int, scale: float = 2.0) -> bytes:
    r = page.rect
    z = min(max_w / r.width, max_h / r.height) * scale
    return page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).tobytes("png")


def preview_resize_png(path: str, page_idx: int, size_name: str, fit_mode: str,
                       custom_w_mm: float | None = None, custom_h_mm: float | None = None,
                       max_w: int = 420, max_h: int = 520) -> bytes | None:
    if not HAS_FITZ:
        return None
    try:
        tw, th = _target_size_pt(size_name, custom_w_mm, custom_h_mm)
        doc = fitz.open(path)
        out_doc = fitz.open()
        _resize_page_into(out_doc, doc, page_idx, tw, th, fit_mode)
        png = _page_png(out_doc[0], max_w, max_h)
        out_doc.close()
        doc.close()
        return png
    except Exception:
        return None


def preview_margins_png(path: str, page_idx: int, top_mm: float, bottom_mm: float,
                        left_mm: float, right_mm: float,
                        max_w: int = 420, max_h: int = 520) -> bytes | None:
    if not HAS_FITZ:
        return None
    try:
        doc = fitz.open(path)
        one = fitz.open()
        one.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        _apply_margins_to_page(one[0], top_mm, bottom_mm, left_mm, right_mm)
        png = _page_png(one[0], max_w, max_h)
        one.close()
        doc.close()
        return png
    except Exception:
        return None


def preview_nup_png(path: str, sheet_idx: int, cols: int, rows: int,
                    size_name: str = "A4", custom_w_mm: float | None = None,
                    custom_h_mm: float | None = None, gap_mm: float | None = None,
                    orientation: str = "auto", auto_rotate: bool = True,
                    max_w: int = 420, max_h: int = 520) -> bytes | None:
    if not HAS_FITZ:
        return None
    try:
        cols, rows = max(1, int(cols)), max(1, int(rows))
        doc = fitz.open(path)
        tw, th, gap, _ = _nup_layout(doc, cols, rows, size_name, custom_w_mm,
                                     custom_h_mm, gap_mm, orientation, auto_rotate)
        out_doc = fitz.open()
        _nup_sheet_into(out_doc, doc, sheet_idx * cols * rows, cols, rows, tw, th, gap,
                        auto_rotate)
        png = _page_png(out_doc[0], max_w, max_h)
        out_doc.close()
        doc.close()
        return png
    except Exception:
        return None
