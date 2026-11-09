# -*- coding: utf-8 -*-
"""
annot_tools.py — Herramientas de anotación sobre un documento YA ABIERTO (sesión de edición):
resaltar, subrayar y tachar texto, y quitar esas marcas. Sin dependencias de interfaz.

Las marcas son anotaciones estándar del PDF (las ve cualquier lector) y no tocan el texto.
Coordenadas siempre en puntos PDF de la página.
"""
import os
import fitz

# Colores (RGB 0-1) de las marcas
COLORS = {
    "amarillo": (1.0, 0.92, 0.2),
    "verde": (0.45, 0.88, 0.45),
    "azul": (0.45, 0.78, 1.0),
    "rosa": (1.0, 0.55, 0.75),
    "naranja": (1.0, 0.7, 0.3),
    "rojo": (0.9, 0.15, 0.15),
    "azul oscuro": (0.1, 0.3, 0.85),
}
DEFAULT_COLOR = {"highlight": "amarillo", "underline": "rojo", "strike": "rojo"}
_ADD = {"highlight": "add_highlight_annot", "underline": "add_underline_annot", "strike": "add_strikeout_annot"}
_TYPES = {fitz.PDF_ANNOT_HIGHLIGHT, fitz.PDF_ANNOT_UNDERLINE, fitz.PDF_ANNOT_STRIKE_OUT}


def page_words(doc, page_idx: int) -> list[tuple]:
    """Palabras de la página en orden de lectura: (x0, y0, x1, y1, texto, bloque, línea, palabra)."""
    try:
        return doc[page_idx].get_text("words")
    except Exception:
        return []


def _dist(word, pt) -> float:
    x0, y0, x1, y1 = word[:4]
    dx = max(x0 - pt[0], 0, pt[0] - x1)
    dy = max(y0 - pt[1], 0, pt[1] - y1)
    return (dx * dx + dy * dy) ** 0.5


def _nearest(words, pt, max_dist=None) -> int | None:
    best, best_d = None, 1e9
    for i, w in enumerate(words):
        d = _dist(w, pt)
        if d < best_d:
            best, best_d = i, d
    if best is None or (max_dist is not None and best_d > max_dist):
        return None
    return best


def select_words(words: list, p0: tuple, p1: tuple, click_tolerance: float = 14.0) -> list[int]:
    """Índices de las palabras entre dos puntos, como una selección de texto: desde la palabra
    más cercana al primer punto hasta la más cercana al segundo (en orden de lectura).
    Un clic sin arrastre marca solo la palabra tocada (si hay una a menos de `click_tolerance`)."""
    if not words:
        return []
    is_click = abs(p0[0] - p1[0]) < 3 and abs(p0[1] - p1[1]) < 3
    if is_click:
        i = _nearest(words, p0, click_tolerance)
        return [] if i is None else [i]
    a, b = _nearest(words, p0), _nearest(words, p1)
    if a is None or b is None:
        return []
    lo, hi = min(a, b), max(a, b)
    return list(range(lo, hi + 1))


def line_rects(words: list, indices: list[int]) -> list[fitz.Rect]:
    """Une las palabras seguidas de una misma línea en una sola caja (una marca por línea)."""
    rects: list[fitz.Rect] = []
    cur = None
    cur_key = None
    for i in indices:
        w = words[i]
        key = (w[5], w[6])                 # bloque y línea
        r = fitz.Rect(w[:4])
        if cur is not None and key == cur_key:
            cur |= r
        else:
            if cur is not None:
                rects.append(cur)
            cur, cur_key = fitz.Rect(r), key
    if cur is not None:
        rects.append(cur)
    return rects


def add_markup(doc, page_idx: int, rects: list, kind: str, color_name: str | None = None) -> int:
    """Añade una marca (highlight / underline / strike) sobre las cajas dadas. Devuelve cuántas líneas marcó."""
    if kind not in _ADD or not rects:
        return 0
    color = (tuple(float(c) for c in color_name) if isinstance(color_name, (tuple, list))
             else COLORS.get(color_name or DEFAULT_COLOR[kind], COLORS["amarillo"]))
    page = doc[page_idx]
    n = 0
    for r in rects:
        try:
            annot = getattr(page, _ADD[kind])(quads=[fitz.Rect(r).quad])
            annot.set_colors(stroke=color)
            annot.set_opacity(1.0)
            annot.update()
            n += 1
        except Exception:
            continue
    return n


def remove_markup_at(doc, page_idx: int, pt: tuple, dry: bool = False) -> bool:
    """Quita la marca (resaltado, subrayado o tachado) que haya bajo el punto. Con dry=True solo comprueba si hay."""
    page = doc[page_idx]
    p = fitz.Point(pt)
    for annot in list(page.annots() or []):
        if annot.type[0] in _SHAPE_TYPES and _shape_hit(annot, pt):
            if not dry:
                page.delete_annot(annot)
            return True
        if annot.type[0] == fitz.PDF_ANNOT_POLYGON and _poly_hit(annot, pt):
            if not dry:
                page.delete_annot(annot)
            return True
        if annot.type[0] == fitz.PDF_ANNOT_STAMP and annot.rect.contains(fitz.Point(pt)):
            if not dry:
                page.delete_annot(annot)
            return True
        if annot.type[0] == fitz.PDF_ANNOT_INK and _ink_hit(annot, pt):
            if not dry:
                page.delete_annot(annot)
            return True
        if annot.type[0] not in _TYPES:
            continue
        r = annot.rect
        if fitz.Rect(r.x0 - 1, r.y0 - 2, r.x1 + 1, r.y1 + 2).contains(p):
            if not dry:
                page.delete_annot(annot)
            return True
    return False


# ── Formas y líneas ───────────────────────────────────────────────────────
SHAPE_COLORS = {
    "negro": (0.1, 0.1, 0.1), "rojo": (0.9, 0.15, 0.15), "azul": (0.15, 0.4, 0.9), "verde": (0.1, 0.65, 0.3),
    "naranja": (1.0, 0.55, 0.1), "amarillo": (1.0, 0.85, 0.1), "rosa": (1.0, 0.45, 0.7), "gris": (0.55, 0.55, 0.55),
}
SHAPE_KINDS = ("rect", "ellipse", "line", "arrow")


def rgb_of(c):
    """Color como (r, g, b) en 0..1 a partir de un nombre de SHAPE_COLORS, un '#rrggbb' o una tupla."""
    if c is None:
        return None
    if isinstance(c, str):
        if c.startswith("#") and len(c) == 7:
            return tuple(int(c[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        return SHAPE_COLORS.get(c, SHAPE_COLORS["rojo"])
    return tuple(float(v) for v in c)


# Puntas de flecha: nombre -> (extremo inicial, extremo final)
_LE = fitz
HEADS = {
    "closed": (fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW),
    "open": (fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW),
    "diamond": (fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_DIAMOND),
    "circle": (fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CIRCLE),
    "square": (fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_SQUARE),
    "double": (fitz.PDF_ANNOT_LE_CLOSED_ARROW, fitz.PDF_ANNOT_LE_CLOSED_ARROW),
}
HEAD_LABELS = (("closed", "Punta triangular"), ("open", "Punta abierta"), ("diamond", "Rombo"),
               ("circle", "Círculo"), ("square", "Cuadrado"), ("double", "Doble flecha"))


def head_of(annot) -> str:
    le = tuple(annot.line_ends or (0, 0))
    for name, ends in HEADS.items():
        if tuple(le) == tuple(ends):
            return name
    return "closed"
TAG = "PDFManager"          # lo que dibuja el editor lleva esta marca; lo que trae el PDF no se toca
_SHAPE_TYPES = {fitz.PDF_ANNOT_SQUARE, fitz.PDF_ANNOT_CIRCLE, fitz.PDF_ANNOT_LINE}


def _snap(p0, p1, kind):
    """Con Mayús: cuadrado/círculo perfecto, o línea horizontal/vertical/a 45°."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    if kind in ("rect", "ellipse"):
        s = max(abs(dx), abs(dy))
        return (p0[0] + (s if dx >= 0 else -s), p0[1] + (s if dy >= 0 else -s))
    ax, ay = abs(dx), abs(dy)
    if ax > 2 * ay:
        return (p1[0], p0[1])
    if ay > 2 * ax:
        return (p0[0], p1[1])
    s = max(ax, ay)
    return (p0[0] + (s if dx >= 0 else -s), p0[1] + (s if dy >= 0 else -s))


def snap_points(p0, p1, kind):
    return _snap(p0, p1, kind)


FILL_KEY = "PDFMgrFillCA"


def _patch_fill_opacity(annot, stroke_op: float, fill_op) -> None:
    """Opacidad del relleno distinta de la del trazo: se corrige el estado gráfico de la apariencia (/ca) y se anota
    en el propio objeto para poder leerla luego. Debe llamarse DESPUÉS de annot.update()."""
    try:
        doc = annot.parent.parent
        x = annot.xref
        if fill_op is None or abs(float(fill_op) - float(stroke_op)) < 0.005:
            doc.xref_set_key(x, FILL_KEY, "null")
            return
        ap = doc.xref_get_key(x, "AP/N")
        if ap[0] == "xref":
            n = int(ap[1].split()[0])
            stream = doc.xref_stream(n) or b""
            if b"/H gs" not in stream:                 # con opacidad 100 % la apariencia no trae estado gráfico
                if stream.startswith(b"q\n"):
                    stream = b"q\n/H gs\n" + stream[2:]
                else:
                    stream = b"q\n/H gs\n" + stream + b"\nQ\n"
                doc.update_stream(n, stream)
            doc.xref_set_key(n, "Resources/ExtGState/H", "<</CA %.3f /ca %.3f>>" % (float(stroke_op), float(fill_op)))
        doc.xref_set_key(x, FILL_KEY, "%.3f" % float(fill_op))
    except Exception:
        pass


def add_shape(doc, page_idx: int, kind: str, p0: tuple, p1: tuple, color="rojo",
              width: float = 2.0, fill=None, opacity: float = 1.0, head: str = "closed",
              stroke_opacity=None, fill_opacity=None) -> bool:
    """Dibuja un rectángulo, elipse, línea o flecha como anotación del PDF."""
    if kind not in SHAPE_KINDS:
        return False
    if abs(p0[0] - p1[0]) < 2 and abs(p0[1] - p1[1]) < 2:
        return False
    page = doc[page_idx]
    stroke = rgb_of(color) or SHAPE_COLORS["rojo"]
    fillc = rgb_of(fill) if fill else None
    try:
        if kind in ("rect", "ellipse"):
            r = fitz.Rect(min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]))
            annot = page.add_rect_annot(r) if kind == "rect" else page.add_circle_annot(r)
            annot.set_colors(stroke=stroke, fill=fillc)
            annot.set_opacity(float(stroke_opacity if stroke_opacity is not None else opacity))
        else:
            annot = page.add_line_annot(fitz.Point(p0), fitz.Point(p1))
            annot.set_colors(stroke=stroke, fill=stroke if kind == "arrow" else None)   # punta rellena
            if kind == "arrow":
                annot.set_line_ends(*HEADS.get(head, HEADS["closed"]))
        if kind not in ("rect", "ellipse"):
            annot.set_opacity(float(stroke_opacity if stroke_opacity is not None else opacity))
        annot.set_border(width=float(width))
        annot.set_info(title=TAG)
        annot.update()
        if kind in ("rect", "ellipse") and fillc:
            _patch_fill_opacity(annot, stroke_opacity if stroke_opacity is not None else opacity,
                                fill_opacity if fill_opacity is not None else opacity)
        return True
    except Exception:
        return False


def _seg_dist(p, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((p[0] - ax) ** 2 + (p[1] - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return ((p[0] - ax - t * dx) ** 2 + (p[1] - ay - t * dy) ** 2) ** 0.5


def _shape_hit(annot, pt, tol=5.0, ignore_fill=False) -> bool:
    t = annot.type[0]
    r = annot.rect
    if t == fitz.PDF_ANNOT_LINE:
        v = annot.vertices
        return bool(v) and len(v) >= 2 and _seg_dist(pt, v[0], v[-1]) <= tol
    filled = bool(annot.colors.get("fill")) and not ignore_fill
    inside = r.x0 <= pt[0] <= r.x1 and r.y0 <= pt[1] <= r.y1
    if t == fitz.PDF_ANNOT_CIRCLE:
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        a, b = max(r.width / 2, 1e-3), max(r.height / 2, 1e-3)
        d = (((pt[0] - cx) / a) ** 2 + ((pt[1] - cy) / b) ** 2) ** 0.5
        edge = tol / min(a, b)
        return d <= 1 + edge if filled else abs(d - 1) <= edge
    if not inside and not (r.x0 - tol <= pt[0] <= r.x1 + tol and r.y0 - tol <= pt[1] <= r.y1 + tol):
        return False
    if filled:
        return True
    return min(abs(pt[0] - r.x0), abs(pt[0] - r.x1), abs(pt[1] - r.y0), abs(pt[1] - r.y1)) <= tol


def move_shape(doc, page_idx: int, desc: dict, dx: float, dy: float) -> bool:
    """Mueve una forma: se vuelve a crear en la nueva posición con los mismos colores y grosor."""
    page = doc[page_idx]
    annot = page.load_annot(desc["xref"]) if hasattr(page, "load_annot") else None
    if annot is None:
        return False
    try:
        page.delete_annot(annot)
        p0 = (desc["p0"][0] + dx, desc["p0"][1] + dy)
        p1 = (desc["p1"][0] + dx, desc["p1"][1] + dy)
        if desc["kind"] in ("rect", "ellipse"):
            r = fitz.Rect(min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]))
            new = page.add_rect_annot(r) if desc["kind"] == "rect" else page.add_circle_annot(r)
        else:
            new = page.add_line_annot(fitz.Point(p0), fitz.Point(p1))
            if desc["kind"] == "arrow":
                new.set_line_ends(*HEADS.get(desc.get("head", "closed"), HEADS["closed"]))
        new.set_colors(stroke=desc["stroke"], fill=desc["fill"])
        new.set_opacity(desc["opacity"] if desc["opacity"] >= 0 else 1.0)
        new.set_border(width=float(desc["width"]))
        new.update()
        if desc["kind"] in ("rect", "ellipse"):
            _patch_fill_opacity(new, desc["opacity"] if desc["opacity"] >= 0 else 1.0, desc.get("fill_opacity"))
        return True
    except Exception:
        return False


# ── Dibujo libre (lápiz y rotulador) ──────────────────────────────────────
def _smooth(points: list, passes: int = 2) -> list:
    """Suaviza un trazo (media móvil) para que no salga dentado."""
    pts = list(points)
    for _ in range(passes):
        if len(pts) < 3:
            break
        pts = [pts[0]] + [((pts[i - 1][0] + 2 * pts[i][0] + pts[i + 1][0]) / 4,
                           (pts[i - 1][1] + 2 * pts[i][1] + pts[i + 1][1]) / 4)
                          for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts


def add_ink(doc, page_idx: int, points: list, color: str = "rojo", width: float = 2.0, marker: bool = False) -> bool:
    """Guarda un trazo a mano alzada como anotación. `marker` = rotulador (ancho y semitransparente)."""
    if len(points) < 2:
        return False
    pts = _smooth(points)
    page = doc[page_idx]
    try:
        annot = page.add_ink_annot([[(float(x), float(y)) for x, y in pts]])
        annot.set_colors(stroke=rgb_of(color) or SHAPE_COLORS["rojo"])
        annot.set_border(width=float(width) * (5 if marker else 1))
        annot.set_opacity(0.4 if marker else 1.0)
        annot.set_info(title=TAG, subject="marker" if marker else "pen")
        annot.update()
        return True
    except Exception:
        return False


def _ink_hit(annot, pt, tol=6.0) -> bool:
    for stroke in (annot.vertices or []):
        for i in range(len(stroke) - 1):
            if _seg_dist(pt, stroke[i], stroke[i + 1]) <= tol:
                return True
    return False


# ── Imágenes (y firmas) como sellos: se pueden mover, escalar y borrar ────
def readable_image(source):
    """Devuelve la imagen en un formato que PyMuPDF lee. WEBP y otros que PyMuPDF no conoce se pasan a PNG con
    Pillow (con su transparencia): ruta nueva en una carpeta temporal si era un archivo, o bytes si eran bytes."""
    try:
        fitz.Pixmap(source)
        return source
    except Exception:
        pass
    import io
    import tempfile
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
        im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA", "PA") else im.convert("RGB")
        if isinstance(source, (bytes, bytearray)):
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return buf.getvalue()
        out = os.path.join(tempfile.mkdtemp(prefix="pdfm_img_"), os.path.splitext(os.path.basename(source))[0] + ".png")
        im.save(out, "PNG")
        return out
    except Exception:
        return source


def image_size(source) -> tuple[int, int]:
    """Tamaño en píxeles de una imagen (ruta o bytes)."""
    pm = fitz.Pixmap(readable_image(source))
    return pm.width, pm.height


def default_image_rect(page_rect, img_w: int, img_h: int, center: tuple | None = None, max_frac: float = 0.45):
    """Rectángulo inicial de una imagen: su tamaño natural (a 96 ppp) sin pasar del 45 % del ancho de la página."""
    w = img_w * 0.75
    h = img_h * 0.75
    limit = page_rect.width * max_frac
    if w > limit:
        h, w = h * limit / w, limit
    if h > page_rect.height * 0.6:
        w, h = w * page_rect.height * 0.6 / h, page_rect.height * 0.6
    w, h = max(w, 24), max(h, 24)
    cx, cy = center if center else (page_rect.width / 2, page_rect.height / 2)
    r = fitz.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    # que no se salga de la página
    dx = max(page_rect.x0 - r.x0, 0) + min(page_rect.x1 - r.x1, 0)
    dy = max(page_rect.y0 - r.y0, 0) + min(page_rect.y1 - r.y1, 0)
    return r + (dx, dy, dx, dy)


def add_image(doc, page_idx: int, rect, source) -> int | None:
    """Añade una imagen (ruta o bytes) como sello; devuelve su xref, o None si falla."""
    page = doc[page_idx]
    try:
        annot = page.add_stamp_annot(fitz.Rect(rect), stamp=readable_image(source))
        annot.update()
        return annot.xref
    except Exception:
        return None


def add_click_icon(doc, page_idx: int, rect, key: str, angle: float = 0.0) -> int | None:
    """Icono de «haz clic aquí» (cursor o mano) como sello que se puede mover, escalar y girar."""
    import click_icons as ci
    try:
        annot = doc[page_idx].add_stamp_annot(fitz.Rect(rect), stamp=ci.render_png(key, angle, 256))
        annot.set_info(subject=ci.subject(key, angle))
        annot.update()
        return annot.xref
    except Exception:
        return None


def rotate_click_icon(doc, page_idx: int, xref: int, angle: float, key: str | None = None):
    """Vuelve a dibujar un icono de clic girado a `angle` grados, en la misma caja. Devuelve (xref nuevo, caja) o None."""
    import click_icons as ci
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            parsed = ci.parse_subject((annot.info or {}).get("subject", ""))
            if not parsed:
                return None
            r = annot.rect
            rect = (r.x0, r.y0, r.x1, r.y1)
            try:
                page.delete_annot(annot)
            except Exception:
                return None
            new = add_click_icon(doc, page_idx, rect, key or parsed[0], angle)
            return (new, rect) if new else None
    return None


def stamp_png(doc, page_idx: int, xref: int):
    """PNG (con transparencia) de un sello/imagen/icono, para mostrarlo mientras se arrastra."""
    for annot in (doc[page_idx].annots() or []):
        if annot.xref == xref:
            try:
                return annot.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=True).tobytes("png")
            except Exception:
                return None
    return None


def set_stamp_hidden(doc, page_idx: int, xref: int, hidden: bool) -> bool:
    """Oculta o muestra un sello mientras se arrastra (no se borra: solo deja de dibujarse)."""
    for annot in (doc[page_idx].annots() or []):
        if annot.xref == xref:
            try:
                fl = annot.flags
                annot.set_flags((fl | fitz.PDF_ANNOT_IS_HIDDEN) if hidden else (fl & ~fitz.PDF_ANNOT_IS_HIDDEN))
                return True
            except Exception:
                return False
    return False


def stamp_at(doc, page_idx: int, pt: tuple) -> dict | None:
    """Sello (imagen/firma) bajo el punto: {xref, rect}. El de encima si hay varios."""
    page = doc[page_idx]
    found = None
    for annot in (page.annots() or []):
        if annot.type[0] == fitz.PDF_ANNOT_STAMP:
            r = annot.rect
            if r.x0 <= pt[0] <= r.x1 and r.y0 <= pt[1] <= r.y1:
                found = {"xref": annot.xref, "rect": (r.x0, r.y0, r.x1, r.y1),
                         "subject": (annot.info or {}).get("subject", "")}
    return found


def set_stamp_rect(doc, page_idx: int, xref: int, rect) -> bool:
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            try:
                annot.set_rect(fitz.Rect(rect))
                annot.update()
                return True
            except Exception:
                return False
    return False


def delete_stamp(doc, page_idx: int, xref: int) -> bool:
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            page.delete_annot(annot)
            return True
    return False


# ── Enlaces ───────────────────────────────────────────────────────────────
_ALLOWED_SCHEMES = ("http", "https", "mailto", "tel")


def normalize_uri(text: str) -> str | None:
    """Deja una dirección lista para un enlace: añade https:// si falta, convierte un correo en mailto: y
    rechaza esquemas peligrosos (javascript:, file:, etc.). None si no es válida."""
    t = (text or "").strip()
    if not t or " " in t:
        return None
    low = t.lower()
    if "://" in low or low.startswith(("mailto:", "tel:")):
        scheme = low.split(":", 1)[0]
        return t if scheme in _ALLOWED_SCHEMES else None
    if ":" in low.split("/")[0] and not low.split(":")[0].isalnum():
        return None
    if "@" in t and "/" not in t:
        return "mailto:" + t
    if low.split(":")[0] in ("javascript", "file", "data", "vbscript"):
        return None
    return "https://" + t


def describe_link(link: dict) -> str:
    if link.get("kind") == fitz.LINK_GOTO:
        return f"Página {link.get('page', 0) + 1} de este documento"
    if link.get("kind") == fitz.LINK_URI:
        return link.get("uri", "")
    if link.get("kind") == fitz.LINK_NAMED:
        return "Destino con nombre: " + str(link.get("name", ""))
    return "Enlace"


def list_links(doc, page_idx: int) -> list[dict]:
    """Enlaces de una página: dicts de PyMuPDF con una clave extra 'rect' (x0, y0, x1, y1)."""
    try:
        page = doc[page_idx]
        out = []
        for l in page.get_links():
            r = fitz.Rect(l["from"])
            l = dict(l)
            l["rect"] = (r.x0, r.y0, r.x1, r.y1)
            l["group"] = _group_of_id(l.get("id"))
            out.append(l)
        return out
    except Exception:
        return []


def link_at(doc, page_idx: int, pt: tuple) -> dict | None:
    hit = None
    for l in list_links(doc, page_idx):
        r = l["rect"]
        if r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]:
            hit = l                      # el último (el de encima)
    return hit


def add_link(doc, page_idx: int, rect, dest: dict, group: str | None = None, index: int = 0) -> bool:
    """dest = {"kind": "uri", "uri": ...} o {"kind": "goto", "page": n (desde 0)}.
    `group`: identificador compartido por las zonas de un mismo enlace (se editan y quitan juntas)."""
    page = doc[page_idx]
    try:
        before = {x[0] for x in page.annot_xrefs()}
        r = fitz.Rect(rect)
        if dest["kind"] == "uri":
            uri = normalize_uri(dest["uri"])
            if not uri:
                return False
            page.insert_link({"kind": fitz.LINK_URI, "from": r, "uri": uri})
        else:
            target = max(0, min(int(dest["page"]), len(doc) - 1))
            page.insert_link({"kind": fitz.LINK_GOTO, "from": r, "page": target, "to": fitz.Point(0, 0), "zoom": 0})
        if group:
            for x in page.annot_xrefs():
                if x[0] not in before:
                    doc.xref_set_key(x[0], "NM", f"({group}-{index})")
        return True
    except Exception:
        return False


def delete_link(doc, page_idx: int, link: dict) -> bool:
    page = doc[page_idx]
    try:
        for l in page.get_links():
            if l.get("xref") == link.get("xref"):
                page.delete_link(l)
                return True
    except Exception:
        pass
    return False


# ── Seleccionar, mover, escalar y duplicar lo dibujado desde el editor ────
def _ours(annot) -> bool:
    try:
        return (annot.info or {}).get("title") == TAG
    except Exception:
        return False


def _bbox_of(d: dict) -> tuple:
    if d["kind"] == "ink":
        xs = [p[0] for st in d["strokes"] for p in st]
        ys = [p[1] for st in d["strokes"] for p in st]
        return (min(xs), min(ys), max(xs), max(ys))
    if d["kind"] == "poly":
        xs = [p[0] for p in d["pts"]]
        ys = [p[1] for p in d["pts"]]
        return (min(xs), min(ys), max(xs), max(ys))
    (x0, y0), (x1, y1) = d["p0"], d["p1"]
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def with_geom(d: dict, geom: dict) -> dict:
    """Copia de la descripción con otra geometría (p0/p1, strokes o pts; y quizá otro tipo) y su caja recalculada."""
    n = dict(d)
    n.update(geom)
    n["bbox"] = _bbox_of(n)
    return n


def describe_editable(annot) -> dict:
    t = annot.type[0]
    cols = annot.colors or {}
    op = annot.opacity
    d = {"xref": annot.xref, "stroke": cols.get("stroke") or None, "fill": cols.get("fill") or None,
         "width": (annot.border or {}).get("width", 1.0) or 1.0, "opacity": op if op is not None and op >= 0 else 1.0}
    try:
        fo = annot.parent.parent.xref_get_key(annot.xref, FILL_KEY)
        d["fill_opacity"] = float(fo[1]) if fo[0] != "null" else d["opacity"]
    except Exception:
        d["fill_opacity"] = d["opacity"]
    if t == fitz.PDF_ANNOT_INK:
        d["kind"] = "ink"
        d["strokes"] = [[(float(p[0]), float(p[1])) for p in st] for st in (annot.vertices or [])]
        subj = (annot.info or {}).get("subject", "")
        d["marker"] = (subj == "marker") if subj in ("marker", "pen") else d["opacity"] < 0.9
    elif t == fitz.PDF_ANNOT_POLYGON:
        d["kind"] = "poly"
        d["pts"] = [(float(p[0]), float(p[1])) for p in (annot.vertices or [])]
    elif t == fitz.PDF_ANNOT_LINE:
        v = annot.vertices
        d["kind"] = "arrow" if annot.line_ends and any(e != fitz.PDF_ANNOT_LE_NONE for e in annot.line_ends) else "line"
        d["head"] = head_of(annot)
        d["p0"], d["p1"] = (float(v[0][0]), float(v[0][1])), (float(v[-1][0]), float(v[-1][1]))
    else:
        r = annot.rect
        d["kind"] = "rect" if t == fitz.PDF_ANNOT_SQUARE else "ellipse"
        d["p0"], d["p1"] = (r.x0, r.y0), (r.x1, r.y1)
    d["bbox"] = _bbox_of(d)
    return d


def _in_polygon(pt, pts) -> bool:
    x, y, inside = pt[0], pt[1], False
    n = len(pts)
    for i in range(n):
        x1, y1, x2, y2 = pts[i][0], pts[i][1], pts[(i + 1) % n][0], pts[(i + 1) % n][1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1:
            inside = not inside
    return inside


def _poly_hit(annot, pt, tol=6.0, ignore_fill=False) -> bool:
    pts = [(float(p[0]), float(p[1])) for p in (annot.vertices or [])]
    if len(pts) < 3:
        return False
    if (annot.colors or {}).get("fill") and not ignore_fill and _in_polygon(pt, pts):
        return True
    return any(_seg_dist(pt, pts[i], pts[(i + 1) % len(pts)]) <= tol for i in range(len(pts)))


def editable_at(doc, page_idx: int, pt: tuple, edge_only: bool = False) -> dict | None:
    """Forma o trazo creado por el editor bajo el punto (el de encima), o None. Lo que ya traía el PDF no cuenta.
    Con edge_only, las formas rellenas solo se agarran por el borde."""
    page = doc[page_idx]
    found = None
    for annot in (page.annots() or []):
        t = annot.type[0]
        if not _ours(annot):
            continue
        if ((t in _SHAPE_TYPES and _shape_hit(annot, pt, ignore_fill=edge_only))
                or (t == fitz.PDF_ANNOT_INK and _ink_hit(annot, pt, 7.0))
                or (t == fitz.PDF_ANNOT_POLYGON and _poly_hit(annot, pt, ignore_fill=edge_only))):
            found = annot
    return describe_editable(found) if found is not None else None


def last_editable(doc, page_idx: int) -> dict | None:
    """La última forma o trazo creado por el editor en la página (la recién dibujada)."""
    found = None
    for annot in (doc[page_idx].annots() or []):
        t = annot.type[0]
        if _ours(annot) and (t in _SHAPE_TYPES or t in (fitz.PDF_ANNOT_INK, fitz.PDF_ANNOT_POLYGON)):
            found = describe_editable(annot)
    return found


ROT_OFFSET = 22.0           # distancia (puntos) del tirador de giro sobre la caja


def center_of(d: dict) -> tuple:
    x0, y0, x1, y1 = d["bbox"]
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def handles_of(d: dict) -> dict:
    """Tiradores de la selección: dos extremos en una línea; en lo demás, cuatro esquinas y uno de giro."""
    if d["kind"] in ("line", "arrow"):
        return {"a": d["p0"], "b": d["p1"]}
    x0, y0, x1, y1 = d["bbox"]
    return {"nw": (x0, y0), "ne": (x1, y0), "sw": (x0, y1), "se": (x1, y1), "rot": ((x0 + x1) / 2, y0 - ROT_OFFSET)}


def shifted_geom(d: dict, dx: float, dy: float) -> dict:
    if d["kind"] == "ink":
        return {"strokes": [[(x + dx, y + dy) for x, y in st] for st in d["strokes"]]}
    if d["kind"] == "poly":
        return {"pts": [(x + dx, y + dy) for x, y in d["pts"]]}
    return {"p0": (d["p0"][0] + dx, d["p0"][1] + dy), "p1": (d["p1"][0] + dx, d["p1"][1] + dy)}


def scaled_geom(d: dict, nb: tuple) -> dict:
    """Geometría ajustada a una nueva caja (formas, polígonos y trazos)."""
    if d["kind"] not in ("ink", "poly"):
        return {"p0": (nb[0], nb[1]), "p1": (nb[2], nb[3])}
    x0, y0, x1, y1 = d["bbox"]
    sx = (nb[2] - nb[0]) / (x1 - x0) if x1 - x0 > 1e-3 else 1.0
    sy = (nb[3] - nb[1]) / (y1 - y0) if y1 - y0 > 1e-3 else 1.0
    f = lambda x, y: (nb[0] + (x - x0) * sx, nb[1] + (y - y0) * sy)
    if d["kind"] == "poly":
        return {"pts": [f(x, y) for x, y in d["pts"]]}
    return {"strokes": [[f(x, y) for x, y in st] for st in d["strokes"]]}


def geom_of(d: dict) -> dict:
    """Geometría actual de una descripción, lista para volver a crearla."""
    if d["kind"] == "ink":
        return {"strokes": d["strokes"]}
    if d["kind"] == "poly":
        return {"pts": d["pts"]}
    return {"p0": d["p0"], "p1": d["p1"]}


def rotate_geom(d: dict, angle_deg: float, center: tuple | None = None) -> dict:
    """Gira la forma alrededor de su centro. Un rectángulo o elipse pasa a ser un polígono (una anotación
    rectangular no puede inclinarse)."""
    import math
    cx, cy = center or center_of(d)
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    rot = lambda x, y: (cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca)
    k = d["kind"]
    if k == "ink":
        return {"strokes": [[rot(x, y) for x, y in st] for st in d["strokes"]]}
    if k == "poly":
        return {"pts": [rot(x, y) for x, y in d["pts"]]}
    if k in ("line", "arrow"):
        return {"p0": rot(*d["p0"]), "p1": rot(*d["p1"])}
    x0, y0, x1, y1 = d["bbox"]
    if k == "rect":
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    else:                                                          # elipse: 48 puntos
        ecx, ecy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        pts = [(ecx + rx * math.cos(2 * math.pi * i / 48), ecy + ry * math.sin(2 * math.pi * i / 48)) for i in range(48)]
    return {"kind": "poly", "pts": [rot(x, y) for x, y in pts]}


def rebuild(doc, page_idx: int, d: dict, geom: dict, delete_old: bool = True, style: dict | None = None) -> dict | None:
    """Crea la forma/trazo con otra geometría y/o estilo (colocar, escalar, girar, duplicar, cambiar color).
    Devuelve su nueva descripción (el xref cambia), o None si falla."""
    page = doc[page_idx]
    n = dict(d)
    n.update(style or {})
    try:
        if delete_old:
            old = next((x for x in (page.annots() or []) if x.xref == d["xref"]), None)
            if old is not None:
                page.delete_annot(old)
        kind = geom.get("kind", n["kind"])
        if kind == "ink":
            new = page.add_ink_annot([[(float(x), float(y)) for x, y in st] for st in geom["strokes"]])
            new.set_colors(stroke=n["stroke"])
        elif kind == "poly":
            new = page.add_polygon_annot([fitz.Point(x, y) for x, y in geom["pts"]])
            new.set_colors(stroke=n["stroke"], fill=n.get("fill"))
        elif kind in ("rect", "ellipse"):
            (x0, y0), (x1, y1) = geom["p0"], geom["p1"]
            r = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            new = page.add_rect_annot(r) if kind == "rect" else page.add_circle_annot(r)
            new.set_colors(stroke=n["stroke"], fill=n.get("fill"))
        else:
            new = page.add_line_annot(fitz.Point(geom["p0"]), fitz.Point(geom["p1"]))
            new.set_colors(stroke=n["stroke"], fill=n["stroke"] if kind == "arrow" else None)
            if kind == "arrow":
                new.set_line_ends(*HEADS.get(n.get("head", "closed"), HEADS["closed"]))
        new.set_opacity(float(n["opacity"]))
        new.set_border(width=float(n["width"]))
        if kind == "ink":
            new.set_info(title=TAG, subject="marker" if n.get("marker") else "pen")
        else:
            new.set_info(title=TAG)
        new.update()
        if kind in ("rect", "ellipse", "poly"):
            _patch_fill_opacity(new, n["opacity"], n.get("fill_opacity") if n.get("fill") else None)
        return describe_editable(new)
    except Exception:
        return None


def delete_editable(doc, page_idx: int, xref: int) -> bool:
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            page.delete_annot(annot)
            return True
    return False


# ── Grupos de enlaces: varias zonas (líneas) que se editan y se quitan juntas ─
def new_group_id() -> str:
    import uuid
    return "pdfm-" + uuid.uuid4().hex[:10]


def _group_of_id(link_id: str | None) -> str | None:
    if link_id and link_id.startswith("pdfm-") and link_id.count("-") >= 2:
        return link_id.rsplit("-", 1)[0]
    return None


def _same_dest(a: dict, b: dict) -> bool:
    return a.get("kind") == b.get("kind") and a.get("uri") == b.get("uri") and a.get("page") == b.get("page")


def _contiguous(ra, rb) -> bool:
    """Zonas de líneas seguidas (una debajo de la otra, tocándose) o en la misma línea y pegadas."""
    up, lo = (ra, rb) if ra[1] <= rb[1] else (rb, ra)
    if -2.0 <= lo[1] - up[3] <= 4.0:
        return True
    same_line = abs(ra[1] - rb[1]) < 2.0 and abs(ra[3] - rb[3]) < 2.0
    return same_line and (ra[0] - 3.0 <= rb[2] and rb[0] - 3.0 <= ra[2])


def group_of(doc, page_idx: int, link: dict) -> list[dict]:
    """Las zonas que forman un mismo enlace: las creadas juntas aquí, o (en enlaces ya existentes)
    las de líneas contiguas con el mismo destino."""
    links = list_links(doc, page_idx)
    if link.get("group"):
        return [l for l in links if l.get("group") == link["group"]]
    pool = [l for l in links if not l.get("group") and _same_dest(l, link)]
    comp = [next((l for l in pool if l.get("xref") == link.get("xref")), link)]
    changed = True
    while changed:
        changed = False
        for l in pool:
            if l not in comp and any(_contiguous(l["rect"], c["rect"]) for c in comp):
                comp.append(l)
                changed = True
    return comp


def delete_group(doc, page_idx: int, members: list[dict]) -> bool:
    ok = False
    for m in members:
        ok = delete_link(doc, page_idx, m) or ok
    return ok


def replace_group(doc, page_idx: int, members: list[dict], dest: dict) -> bool:
    """Cambia el destino de todas las zonas del enlace, que siguen juntas."""
    if dest["kind"] == "uri" and not normalize_uri(dest["uri"]):
        return False
    gid = members[0].get("group") or (new_group_id() if len(members) > 1 else None)
    rects = [m["rect"] for m in members]
    if not delete_group(doc, page_idx, members):
        return False
    ok = False
    for i, r in enumerate(rects):
        ok = add_link(doc, page_idx, r, dest, group=gid, index=i) or ok
    return ok


def duplicate_stamp(doc, page_idx: int, xref: int, dx: float = 14, dy: float = 14) -> tuple | None:
    """Copia una imagen/firma desplazada. Devuelve (xref_nuevo, rect) o None."""
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            try:
                pm = annot.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=True)
                r = annot.rect + (dx, dy, dx, dy)
                new = page.add_stamp_annot(r, stamp=pm)
                subj = (annot.info or {}).get("subject", "")
                if subj:
                    new.set_info(subject=subj)
                new.update()
                return new.xref, (r.x0, r.y0, r.x1, r.y1)
            except Exception:
                return None
    return None


# ── Imágenes que ya trae el PDF (contenido de la página) ──────────────────
def pdf_image_at(doc, page_idx: int, pt: tuple) -> dict | None:
    """Imagen del contenido de la página bajo el punto (la de encima): {xref, bbox}."""
    try:
        page = doc[page_idx]
        found = None
        for info in page.get_image_info(xrefs=True):
            x0, y0, x1, y1 = info["bbox"]
            if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1:
                found = {"xref": info.get("xref", 0), "bbox": (x0, y0, x1, y1)}
        return found
    except Exception:
        return None


def delete_pdf_image(doc, page_idx: int, bbox: tuple) -> bool:
    """Quita la imagen de ESTA página (si el mismo archivo se usa en otras páginas, se quedan). No toca texto ni dibujos."""
    try:
        page = doc[page_idx]
        r = fitz.Rect(bbox) + (-1, -1, 1, 1)
        page.add_redact_annot(r)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                              text=fitz.PDF_REDACT_TEXT_NONE)
        return True
    except Exception:
        return False


# ── Notas (comentarios) y archivos adjuntos ───────────────────────────────
NOTE_SUBJECT = "PDFManager-nota"
MAX_ATTACH = 25 * 1024 * 1024


def add_note(doc, page_idx: int, pt: tuple, text: str, author: str = "") -> bool:
    page = doc[page_idx]
    try:
        annot = page.add_text_annot(fitz.Point(pt), text, icon="Note")
        annot.set_colors(stroke=(1.0, 0.82, 0.1))
        annot.set_info(title=author, content=text, subject=NOTE_SUBJECT)
        annot.update()
        return True
    except Exception:
        return False


def note_at(doc, page_idx: int, pt: tuple) -> dict | None:
    page = doc[page_idx]
    found = None
    for annot in (page.annots() or []):
        if annot.type[0] == fitz.PDF_ANNOT_TEXT:
            r = annot.rect
            if r.x0 - 3 <= pt[0] <= r.x1 + 3 and r.y0 - 3 <= pt[1] <= r.y1 + 3:
                info = annot.info or {}
                found = {"xref": annot.xref, "text": info.get("content", ""), "author": info.get("title", ""),
                         "pos": (r.x0, r.y0)}
    return found


def update_note(doc, page_idx: int, xref: int, text: str) -> bool:
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            annot.set_info(content=text)
            annot.update()
            return True
    return False


def move_note(doc, page_idx: int, xref: int, pt: tuple) -> bool:
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            r = annot.rect
            annot.set_rect(fitz.Rect(pt[0], pt[1], pt[0] + r.width, pt[1] + r.height))
            annot.update()
            return True
    return False


def delete_annot_by_xref(doc, page_idx: int, xref: int) -> bool:
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            page.delete_annot(annot)
            return True
    return False


CLIP_SIZE = 18.0           # tamaño del clip en la página (puntos); su dibujo se hace sobre una caja de 22
_CLIP_BOX = 22.0

# Apariencia del clip: círculo oscuro con borde blanco y el clip en blanco (se ve sobre cualquier fondo, claro u oscuro)
_CLIP_AP = (b"q\n0.13 0.13 0.13 rg\n1 1 1 RG\n1 w\n"
            b"11 21.5 m\n16.8 21.5 21.5 16.8 21.5 11 c\n21.5 5.2 16.8 0.5 11 0.5 c\n5.2 0.5 0.5 5.2 0.5 11 c\n"
            b"0.5 16.8 5.2 21.5 11 21.5 c\nh B\n"
            b"1 1 1 RG\n1.5 w\n1 J\n1 j\n"
            b"8.4 6.4 m\n8.4 14.2 l\n8.4 16.6 13.2 16.6 13.2 14.2 c\n13.2 7.2 l\n13.2 5.4 10.2 5.4 10.2 7.2 c\n"
            b"10.2 13.0 l\nS\nQ\n")


def _clip_rect(page, cx: float, cy: float):
    """Caja del clip centrada en (cx, cy) y dentro de la página."""
    s = CLIP_SIZE
    x = min(max(page.rect.x0, cx - s / 2), page.rect.x1 - s)
    y = min(max(page.rect.y0, cy - s / 2), page.rect.y1 - s)
    return fitz.Rect(x, y, x + s, y + s)


def strip_popup(doc, page, annot) -> None:
    """Quita la anotación emergente (la caja amarilla con el texto) que PyMuPDF crea junto a notas y adjuntos: algunos
    visores, como Chrome, la dejan abierta tapando la página."""
    try:
        import re
        pk = doc.xref_get_key(annot.xref, "Popup")
        if pk[0] != "xref":
            return
        px = int(pk[1].split()[0])
        doc.xref_set_key(annot.xref, "Popup", "null")
        ak = doc.xref_get_key(page.xref, "Annots")
        if ak[0] == "array":
            refs = [r for r in re.findall(r"(\d+)\s+0\s+R", ak[1]) if int(r) != px]
            doc.xref_set_key(page.xref, "Annots", "[" + " ".join(f"{r} 0 R" for r in refs) + "]")
    except Exception:
        pass


def move_attachment(doc, page_idx: int, xref: int, dx: float, dy: float) -> bool:
    """Mueve el clip de un adjunto (conserva su apariencia)."""
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            try:
                r = annot.rect
                annot.set_rect(_clip_rect(page, (r.x0 + r.x1) / 2 + dx, (r.y0 + r.y1) / 2 + dy))
                return True
            except Exception:
                return False
    return False


def add_attachment(doc, page_idx: int, pt: tuple, path: str) -> bool:
    """Adjunta un archivo al PDF y pone el icono del clip CENTRADO en `pt`."""
    import os
    page = doc[page_idx]
    try:
        if os.path.getsize(path) > MAX_ATTACH:
            return False
        with open(path, "rb") as fh:
            data = fh.read()
        name = os.path.basename(path)
        annot = page.add_file_annot(fitz.Point(pt), data, name, desc=name, icon="Paperclip")
        annot.set_info(subject="PDFManager-adjunto")
        annot.update()
        xr = doc.get_new_xref()                                         # apariencia propia, con contraste
        doc.update_object(xr, "<</Type/XObject/Subtype/Form/BBox[0 0 %g %g]/Resources<<>>>>" % (_CLIP_BOX, _CLIP_BOX))
        doc.update_stream(xr, _CLIP_AP)
        doc.xref_set_key(annot.xref, "AP", "<</N %d 0 R>>" % xr)
        strip_popup(doc, page, annot)                                   # sin la «cajita» amarilla con el nombre
        annot.set_rect(_clip_rect(page, pt[0], pt[1]))
        return True
    except Exception:
        return False


def attachment_at(doc, page_idx: int, pt: tuple) -> dict | None:
    page = doc[page_idx]
    found = None
    for annot in (page.annots() or []):
        if annot.type[0] == fitz.PDF_ANNOT_FILE_ATTACHMENT:
            r = annot.rect
            if r.x0 - 3 <= pt[0] <= r.x1 + 3 and r.y0 - 3 <= pt[1] <= r.y1 + 3:
                fi = annot.file_info or {}
                found = {"xref": annot.xref, "name": fi.get("filename", "adjunto"), "size": fi.get("size", 0),
                         "rect": (r.x0, r.y0, r.x1, r.y1)}
    return found


def read_attachment(doc, page_idx: int, xref: int):
    """(nombre, bytes) de un adjunto, o None. Solo se lee: nunca se abre ni se ejecuta."""
    page = doc[page_idx]
    for annot in (page.annots() or []):
        if annot.xref == xref:
            try:
                return (annot.file_info or {}).get("filename", "adjunto"), annot.get_file()
            except Exception:
                return None
    return None
