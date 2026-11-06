# -*- coding: utf-8 -*-
"""click_icons.py — Iconos de «haz clic aquí» (cursor y mano, con distintos efectos) para poner sobre un enlace.
Se dibujan con Qt en un lienzo cuadrado con margen, de modo que se pueden girar sin cortarse."""
import math
import os
import shutil
import time
from pathlib import Path

from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice, QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF

DARK = QColor("#1C1409")
LIGHT = QColor("#FFFFFF")

# (clave, etiqueta, base, decoración)
LEGACY_KINDS = (
    ("arrow", "Cursor", "arrow", None),
    ("arrow_rays", "Cursor con destellos", "arrow", "rays"),
    ("arrow_ripple", "Cursor con ondas", "arrow", "ripple"),
    ("arrow_dots", "Cursor con puntos", "arrow", "dots"),
    ("hand", "Mano", "hand", None),
    ("hand_rays", "Mano con destellos", "hand", "rays"),
    ("hand_ripple", "Mano con ondas", "hand", "ripple"),
    ("hand_dots", "Mano con puntos", "hand", "dots"),
)
_BY_KEY = {k[0]: k for k in LEGACY_KINDS}

# Iconos dibujados por el usuario (click_icons.svg): primera fila cursores, segunda manos; cada icono es un grupo
SVG_ICONS = (("svg:g11", "Cursor 1"), ("svg:g2", "Cursor 2"), ("svg:g3", "Cursor 3"), ("svg:g4", "Cursor 4"),
             ("svg:g5", "Cursor 5"), ("svg:g10", "Mano 1"), ("svg:g9", "Mano 2"), ("svg:g8", "Mano 3"),
             ("svg:g7", "Mano 4"), ("svg:g6", "Mano 5"))
_SVG = None


def _svg_renderer():
    global _SVG
    if _SVG is None:
        from PySide6.QtSvg import QSvgRenderer
        path = Path(__file__).with_name("click_icons.svg")
        if not path.is_file():
            try:
                import backend
                path = Path(backend.resource_path("click_icons.svg"))
            except Exception:
                pass
        _SVG = QSvgRenderer(str(path)) if path.is_file() else False
        if _SVG is not False and not _SVG.isValid():
            _SVG = False
    return _SVG


def builtin_kinds() -> list:
    """(clave, etiqueta) de los iconos incluidos: los del SVG, o los dibujados por código si falta el archivo."""
    if _svg_renderer():
        return list(SVG_ICONS)
    return [(k[0], k[1]) for k in LEGACY_KINDS]


KINDS = LEGACY_KINDS
CANVAS = 140.0          # unidades del lienzo; el dibujo ocupa ~100 y deja margen para efectos y giros


def _arrow_path(ox, oy):
    pts = [(22, 10), (22, 72), (38, 57), (50, 86), (62, 80), (50, 52), (72, 52)]
    return QPainterPath(), QPolygonF([QPointF(x + ox, y + oy) for x, y in pts]), (22 + ox, 10 + oy), 135.0


def _hand_path(ox, oy):
    """Mano con el índice señalando: dedo redondeado, tres dedos doblados, pulgar y palma, con curvas."""
    path = QPainterPath()
    P = lambda x, y: QPointF(x + ox, y + oy)
    path.moveTo(P(33, 54))
    path.lineTo(P(33, 17))
    path.cubicTo(P(33, 2), P(52, 2), P(52, 17))
    path.lineTo(P(52, 38))
    path.cubicTo(P(52, 30), P(65, 30), P(65, 39))
    path.cubicTo(P(65, 33), P(78, 33), P(78, 43))
    path.cubicTo(P(78, 37), P(91, 37), P(91, 47))
    path.lineTo(P(91, 62))
    path.cubicTo(P(91, 78), P(85, 86), P(79, 94))
    path.lineTo(P(46, 94))
    path.cubicTo(P(40, 82), P(28, 72), P(14, 62))
    path.cubicTo(P(6, 56), P(13, 46), P(21, 51))
    path.cubicTo(P(25, 54), P(29, 59), P(33, 63))
    path.closeSubpath()
    return path, None, (42.5 + ox, 4 + oy), 90.0


def _polar(c, ang_deg, r):
    a = math.radians(ang_deg)
    return QPointF(c[0] + r * math.cos(a), c[1] - r * math.sin(a))


def custom_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "PDFManager" / "click_icons"


def list_custom() -> list:
    """Claves («file:nombre.png») de los iconos propios que el usuario ha importado."""
    d = custom_dir()
    return ["file:" + f.name for f in sorted(d.glob("*.png"), key=lambda f: f.stat().st_mtime)] if d.is_dir() else []


def _load_any(path: str):
    """Imagen (QImage) de un archivo: PNG, JPG, SVG…, o Illustrator (.ai con compatibilidad PDF) y PDF. EPS solo si el
    equipo tiene Ghostscript (si no, devuelve el motivo)."""
    ext = Path(path).suffix.lower()
    if ext in (".ai", ".pdf"):
        import fitz
        doc = fitz.open(str(path), filetype="pdf")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=True)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGBA8888).copy()
        doc.close()
        return img, None
    if ext in (".eps", ".ps"):
        try:
            from PIL import Image
            im = Image.open(path)
            im.load(scale=4)
            im = im.convert("RGBA")
            return QImage(im.tobytes("raw", "RGBA"), im.width, im.height, im.width * 4,
                          QImage.Format_RGBA8888).copy(), None
        except Exception:
            return None, ("Un EPS necesita Ghostscript instalado para leerse. Expórtalo a PNG, SVG o PDF desde tu "
                          "programa de diseño, o usa la versión .ai o .jpeg.")
    img = QImage(str(path))
    return (None, "No se pudo leer esa imagen.") if img.isNull() else (img, None)


def _remove_white_background(img: QImage) -> QImage:
    """Los JPEG no tienen transparencia: el blanco que rodea al dibujo se vuelve transparente (el blanco de dentro se
    queda). Se rellena desde los bordes, sin tocar lo que queda encerrado por el contorno."""
    from PIL import Image, ImageDraw
    rgba = img.convertToFormat(QImage.Format_RGBA8888)
    im = Image.frombytes("RGBA", (rgba.width(), rgba.height()), bytes(rgba.constBits()), "raw", "RGBA", rgba.bytesPerLine())
    w, h = im.size
    for pt in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)):
        if sum(im.getpixel(pt)[:3]) > 720:
            ImageDraw.floodfill(im, pt, (255, 255, 255, 0), thresh=60)
    return QImage(im.tobytes("raw", "RGBA"), w, h, w * 4, QImage.Format_RGBA8888).copy()


def import_custom(path: str):
    """Guarda una imagen del usuario como icono propio. Devuelve (clave, None) o (None, motivo del fallo)."""
    try:
        img, err = _load_any(path)
    except Exception as e:                     # archivo dañado, protegido, etc.
        return None, "No se pudo leer ese archivo (%s)." % e
    if img is None:
        return None, err
    if not img.hasAlphaChannel() or Path(path).suffix.lower() in (".jpg", ".jpeg", ".bmp"):
        img = _remove_white_background(img)
    d = custom_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = "icono_%s_%d.png" % (time.strftime("%Y%m%d_%H%M%S"), len(list(d.glob("*.png"))))
    img.convertToFormat(QImage.Format_ARGB32).save(str(d / name), "PNG")
    return "file:" + name, None


def _render_custom(key: str, angle: float, size: int) -> QImage:
    src = QImage(str(custom_dir() / key[5:]))
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    if src.isNull():
        return img
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(size / 2, size / 2)
    p.rotate(angle)
    box = size * 100.0 / CANVAS
    s = src.scaled(int(box), int(box), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawImage(QPointF(-s.width() / 2, -s.height() / 2), s)
    p.end()
    return img


def _render_svg(key: str, angle: float, size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    r = _svg_renderer()
    if not r:
        return img
    eid = key[4:]
    b = r.boundsOnElement(eid)
    if b.isEmpty():
        return img
    box = size * 100.0 / CANVAS
    s = min(box / b.width(), box / b.height())
    w, h = b.width() * s, b.height() * s
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(size / 2, size / 2)
    p.rotate(angle)
    r.render(p, eid, QRectF(-w / 2, -h / 2, w, h))
    p.end()
    return img


def render_image(key: str, angle: float = 0.0, size: int = 256) -> QImage:
    if key.startswith("file:"):
        return _render_custom(key, angle, size)
    if key.startswith("svg:"):
        return _render_svg(key, angle, size)
    _k, _label, base, deco = _BY_KEY.get(key, KINDS[0])
    k = size / CANVAS
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(size / 2, size / 2)
    p.rotate(angle)
    p.translate(-size / 2, -size / 2)
    p.scale(k, k)
    ox, oy = 20, 28
    path, poly, tip, up = (_arrow_path if base == "arrow" else _hand_path)(ox, oy)
    p.setPen(Qt.NoPen)                                  # sombra desplazada, como en los cursores clásicos
    p.setBrush(DARK)
    p.save()
    p.translate(4, 4)
    if poly is not None:
        p.drawPolygon(poly)
    else:
        p.drawPath(path)
    p.restore()
    p.setPen(QPen(DARK, 4.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(LIGHT)
    if poly is not None:
        p.drawPolygon(poly)
    else:
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(DARK, 3.0, Qt.SolidLine, Qt.RoundCap))
        for x, y0, y1 in ((52, 40, 58), (65, 41, 58), (78, 45, 60)):    # separación entre dedos
            p.drawLine(QPointF(x + ox, y0 + oy), QPointF(x + ox, y1 + oy))
    if deco:
        p.setBrush(Qt.NoBrush)
        pen = QPen(DARK, 3.2, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        if deco == "rays":
            for off in (-38, 0, 38):
                p.drawLine(_polar(tip, up + off, 19), _polar(tip, up + off, 31))
        elif deco == "ripple":
            for r in (20, 31):
                rect = QRectF(tip[0] - r, tip[1] - r, 2 * r, 2 * r)
                p.drawArc(rect, int((up - 38) * 16), int(76 * 16))
        elif deco == "dots":
            p.setPen(Qt.NoPen)
            p.setBrush(DARK)
            for off in (-44, -22, 0, 22, 44):
                c = _polar(tip, up + off, 25)
                p.drawEllipse(c, 2.6, 2.6)
    p.end()
    return img


def render_png(key: str, angle: float = 0.0, size: int = 256) -> bytes:
    img = render_image(key, angle, size)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def subject(key: str, angle: float) -> str:
    return f"clickicon|{key}|{int(round(angle)) % 360}"


def parse_subject(s: str):
    """('clave', ángulo) si el texto describe un icono de clic, o None."""
    try:
        tag, key, ang = (s or "").split("|")
        if tag == "clickicon" and (key in _BY_KEY or key.startswith(("file:", "svg:"))):
            return key, float(ang)
    except ValueError:
        pass
    return None
