# -*- coding: utf-8 -*-
"""icons.py — Set de iconos vectoriales monocromos (estilo silueta sólida,
pocas formas simples por icono para que no se deformen a tamaño pequeño)
para sustituir los emojis de Windows por algo consistente con la paleta
Provecto. Sin dependencias externas (sin QtSvg, sin archivos .png)."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon, QPainterPath, QPolygonF

_CACHE: dict[tuple, QIcon] = {}


def _canvas(size: int):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFFFFF"))
    return pix, p


def _stroke(p, size: int, width_factor: float = 0.11):
    """Cambia el painter a modo trazo (sin relleno) para las pocas formas
    que lo necesitan (flechas, chequeos, candado)."""
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(size * width_factor)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)


def _fill(p):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFFFFF"))


def _paint(name: str, size: int):
    pix, p = _canvas(size)
    _DRAWERS[name](p, size)
    p.end()
    return pix


def _recolor(pix: QPixmap, color: str) -> QPixmap:
    out = QPixmap(pix.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.drawPixmap(0, 0, pix)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(color))
    p.end()
    return out


def icon(name: str, color: str, size: int = 18) -> QIcon:
    key = (name, color, size)
    if key in _CACHE:
        return _CACHE[key]
    ic = QIcon(_recolor(_paint(name, size), color))
    _CACHE[key] = ic
    return ic


# ── dibujos (coordenadas relativas a un lienzo size×size, solo 1-3 formas
#    simples por icono: rects/elipses/polígonos rellenos o un trazo corto) ──
def _link(p, s):
    """Dos anillos de cadena en trazo (no relleno): rellenos y solapados se
    fundían en una sola mancha a tamaño de botón (17px); en trazo cada
    anillo se distingue aunque se solapen."""
    _stroke(p, s, 0.15)
    p.drawRoundedRect(QRectF(s * 0.08, s * 0.30, s * 0.46, s * 0.38), s * 0.17, s * 0.17)
    p.drawRoundedRect(QRectF(s * 0.46, s * 0.30, s * 0.46, s * 0.38), s * 0.17, s * 0.17)


def _grid(p, s):
    _fill(p)
    r = s * 0.07
    w = s * 0.40
    for x in (s * 0.08, s * 0.52):
        for y in (s * 0.08, s * 0.52):
            p.drawRoundedRect(QRectF(x, y, w, w), r, r)


def _printer(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.42, s * 0.76, s * 0.46), s * 0.09, s * 0.09)
    p.drawRoundedRect(QRectF(s * 0.28, s * 0.08, s * 0.44, s * 0.40), s * 0.04, s * 0.04)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawRoundedRect(QRectF(s * 0.36, s * 0.56, s * 0.28, s * 0.10), s * 0.02, s * 0.02)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _droplet(p, s):
    """Icono de 'ajuste' (brillo/contraste): círculo con una mitad rellena
    y la otra solo con el contorno."""
    _stroke(p, s, 0.09)
    p.drawEllipse(QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.80))
    _fill(p)
    path = QPainterPath()
    path.moveTo(s * 0.5, s * 0.10)
    path.arcTo(QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.80), 90, 180)
    path.closeSubpath()
    p.drawPath(path)


def _pencil(p, s):
    _fill(p)
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(45)
    p.drawRoundedRect(QRectF(-s * 0.10, -s * 0.46, s * 0.20, s * 0.72), s * 0.04, s * 0.04)
    tip = QPolygonF([QPointF(-s * 0.10, s * 0.26), QPointF(s * 0.10, s * 0.26), QPointF(0, s * 0.42)])
    p.drawPolygon(tip)
    p.restore()


def _info(p, s):
    _stroke(p, s, 0.10)
    p.drawEllipse(QRectF(s * 0.12, s * 0.12, s * 0.76, s * 0.76))
    _fill(p)
    p.drawEllipse(QRectF(s * 0.5 - s * 0.055, s * 0.28, s * 0.11, s * 0.11))
    _stroke(p, s, 0.12)
    p.drawLine(QPointF(s * 0.5, s * 0.47), QPointF(s * 0.5, s * 0.70))


def _scissors(p, s):
    """Página con una línea discontinua por donde se divide: metáfora
    estándar de 'dividir documento'. (La versión anterior, en puntos
    verticales, se leía como un menú '⋮'; la de dos bloques, como 'pausa'.)"""
    _stroke(p, s, 0.08)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.10, s * 0.72, s * 0.80), s * 0.08, s * 0.08)
    pen = p.pen()
    pen.setStyle(Qt.DashLine)
    pen.setWidthF(s * 0.09)
    p.setPen(pen)
    p.drawLine(QPointF(s * 0.14, s * 0.5), QPointF(s * 0.86, s * 0.5))


def _download(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.42, s * 0.10, s * 0.16, s * 0.40), s * 0.04, s * 0.04)
    arrow = QPolygonF([QPointF(s * 0.26, s * 0.46), QPointF(s * 0.74, s * 0.46), QPointF(s * 0.5, s * 0.74)])
    p.drawPolygon(arrow)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.80, s * 0.72, s * 0.11), s * 0.04, s * 0.04)


def _save(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.12, s * 0.72, s * 0.76), s * 0.10, s * 0.10)
    p.setBrush(QColor(0, 0, 0, 0))
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawRoundedRect(QRectF(s * 0.30, s * 0.14, s * 0.40, s * 0.22), s * 0.03, s * 0.03)
    p.drawRoundedRect(QRectF(s * 0.26, s * 0.50, s * 0.48, s * 0.30), s * 0.04, s * 0.04)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _folder(p, s):
    _fill(p)
    path = QPainterPath()
    path.moveTo(s * 0.10, s * 0.26)
    path.lineTo(s * 0.40, s * 0.26)
    path.lineTo(s * 0.48, s * 0.36)
    path.lineTo(s * 0.90, s * 0.36)
    path.lineTo(s * 0.90, s * 0.82)
    path.lineTo(s * 0.10, s * 0.82)
    path.closeSubpath()
    p.drawPath(path)


def _archive(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72), s * 0.08, s * 0.08)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    for y in (0.22, 0.38, 0.54, 0.70):
        p.drawRect(QRectF(s * 0.46, s * y, s * 0.08, s * 0.08))
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _lock(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.22, s * 0.46, s * 0.56, s * 0.42), s * 0.08, s * 0.08)
    _stroke(p, s, 0.13)
    path = QPainterPath()
    path.moveTo(s * 0.32, s * 0.50)
    path.lineTo(s * 0.32, s * 0.32)
    path.arcTo(QRectF(s * 0.32, s * 0.10, s * 0.36, s * 0.36), 180, -180)
    path.lineTo(s * 0.68, s * 0.50)
    p.drawPath(path)


def _swap(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.30, s * 0.58, s * 0.10), s * 0.04, s * 0.04)
    arrow_r = QPolygonF([QPointF(s * 0.68, s * 0.16), QPointF(s * 0.92, s * 0.35), QPointF(s * 0.68, s * 0.54)])
    p.drawPolygon(arrow_r)
    p.drawRoundedRect(QRectF(s * 0.28, s * 0.60, s * 0.58, s * 0.10), s * 0.04, s * 0.04)
    arrow_l = QPolygonF([QPointF(s * 0.32, s * 0.46), QPointF(s * 0.08, s * 0.65), QPointF(s * 0.32, s * 0.84)])
    p.drawPolygon(arrow_l)


def _chevron_left(p, s):
    _stroke(p, s, 0.13)
    p.drawLine(QPointF(s * 0.62, s * 0.18), QPointF(s * 0.34, s * 0.5))
    p.drawLine(QPointF(s * 0.34, s * 0.5), QPointF(s * 0.62, s * 0.82))


def _chevron_right(p, s):
    _stroke(p, s, 0.13)
    p.drawLine(QPointF(s * 0.38, s * 0.18), QPointF(s * 0.66, s * 0.5))
    p.drawLine(QPointF(s * 0.66, s * 0.5), QPointF(s * 0.38, s * 0.82))


def _back(p, s):
    _stroke(p, s, 0.13)
    p.drawLine(QPointF(s * 0.68, s * 0.22), QPointF(s * 0.34, s * 0.5))
    p.drawLine(QPointF(s * 0.34, s * 0.5), QPointF(s * 0.68, s * 0.78))
    p.drawLine(QPointF(s * 0.34, s * 0.5), QPointF(s * 0.86, s * 0.5))


def _forward(p, s):
    _stroke(p, s, 0.13)
    p.drawLine(QPointF(s * 0.32, s * 0.22), QPointF(s * 0.66, s * 0.5))
    p.drawLine(QPointF(s * 0.66, s * 0.5), QPointF(s * 0.32, s * 0.78))
    p.drawLine(QPointF(s * 0.66, s * 0.5), QPointF(s * 0.14, s * 0.5))


def _check(p, s):
    _stroke(p, s, 0.14)
    p.drawLine(QPointF(s * 0.20, s * 0.52), QPointF(s * 0.42, s * 0.74))
    p.drawLine(QPointF(s * 0.42, s * 0.74), QPointF(s * 0.82, s * 0.26))


def _close(p, s):
    _stroke(p, s, 0.13)
    p.drawLine(QPointF(s * 0.24, s * 0.24), QPointF(s * 0.76, s * 0.76))
    p.drawLine(QPointF(s * 0.76, s * 0.24), QPointF(s * 0.24, s * 0.76))


def _select(p, s):
    """Puntero de ratón."""
    _stroke(p, s, 0.09)
    poly = QPolygonF([QPointF(s * 0.28, s * 0.14), QPointF(s * 0.28, s * 0.80), QPointF(s * 0.46, s * 0.63),
                      QPointF(s * 0.60, s * 0.88), QPointF(s * 0.70, s * 0.83), QPointF(s * 0.56, s * 0.58),
                      QPointF(s * 0.80, s * 0.56)])
    p.drawPolygon(poly)


def _rect(p, s):
    _stroke(p, s, 0.10)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.24, s * 0.72, s * 0.52), s * 0.04, s * 0.04)


def _ellipse(p, s):
    _stroke(p, s, 0.10)
    p.drawEllipse(QRectF(s * 0.12, s * 0.22, s * 0.76, s * 0.56))


def _line(p, s):
    _stroke(p, s, 0.11)
    p.drawLine(QPointF(s * 0.16, s * 0.82), QPointF(s * 0.84, s * 0.18))


def _arrow(p, s):
    _stroke(p, s, 0.11)
    p.drawLine(QPointF(s * 0.16, s * 0.84), QPointF(s * 0.82, s * 0.18))
    p.drawLine(QPointF(s * 0.82, s * 0.18), QPointF(s * 0.82, s * 0.50))
    p.drawLine(QPointF(s * 0.82, s * 0.18), QPointF(s * 0.50, s * 0.18))


def _rot_right(p, s):
    """Flecha circular en sentido horario: arco de unos 270° con una punta triangular rellena al final."""
    import math
    _stroke(p, s, 0.11)
    cx, cy, r = s * 0.5, s * 0.54, s * 0.30
    start, sweep = 120.0, 250.0                         # empieza arriba a la izquierda y gira en sentido horario
    p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(start * 16), int(-sweep * 16))
    te = math.radians(start - sweep)
    ex, ey = cx + r * math.cos(te), cy - r * math.sin(te)
    tx, ty = math.sin(te), math.cos(te)                 # dirección de avance en el extremo
    nx, ny = -ty, tx                                    # normal
    h, w = s * 0.24, s * 0.15
    tip = QPointF(ex + tx * h * 0.55, ey + ty * h * 0.55)
    b1 = QPointF(ex - tx * h * 0.45 + nx * w, ey - ty * h * 0.45 + ny * w)
    b2 = QPointF(ex - tx * h * 0.45 - nx * w, ey - ty * h * 0.45 - ny * w)
    _fill(p)
    p.drawPolygon(QPolygonF([tip, b1, b2]))


def _rot_left(p, s):
    p.translate(s, 0)
    p.scale(-1, 1)
    _rot_right(p, s)


def _text_t(p, s):
    """Una T (texto plano)."""
    _stroke(p, s, 0.14)
    p.drawLine(QPointF(s * 0.2, s * 0.24), QPointF(s * 0.8, s * 0.24))
    p.drawLine(QPointF(s * 0.5, s * 0.24), QPointF(s * 0.5, s * 0.82))


def _text_add(p, s):
    """A con un + elevado (añadir texto nuevo)."""
    _stroke(p, s, 0.12)
    p.drawLine(QPointF(s * 0.10, s * 0.84), QPointF(s * 0.38, s * 0.24))
    p.drawLine(QPointF(s * 0.38, s * 0.24), QPointF(s * 0.66, s * 0.84))
    p.drawLine(QPointF(s * 0.20, s * 0.64), QPointF(s * 0.56, s * 0.64))
    _stroke(p, s, 0.09)
    p.drawLine(QPointF(s * 0.84, s * 0.10), QPointF(s * 0.84, s * 0.40))
    p.drawLine(QPointF(s * 0.69, s * 0.25), QPointF(s * 0.99, s * 0.25))


def _plus(p, s):
    _stroke(p, s, 0.12)
    p.drawLine(QPointF(s * 0.5, s * 0.2), QPointF(s * 0.5, s * 0.8))
    p.drawLine(QPointF(s * 0.2, s * 0.5), QPointF(s * 0.8, s * 0.5))


def _glyph(p, s, text: str, bold: bool = False, italic: bool = False):
    """Letra centrada, dibujada como contorno (para los iconos B e I)."""
    from PySide6.QtGui import QFont
    font = QFont("Segoe UI")
    font.setPixelSize(int(s * 0.95))
    font.setBold(bold)
    font.setItalic(italic)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    box = path.boundingRect()
    path.translate(s / 2 - box.center().x(), s / 2 - box.center().y())
    _fill(p)
    p.drawPath(path)


def _bold(p, s):
    _glyph(p, s * 0.92, "B", bold=True)


def _italic(p, s):
    _glyph(p, s * 0.92, "I", italic=True)


def _chevron_down(p, s):
    _stroke(p, s, 0.14)
    p.drawLine(QPointF(s * 0.20, s * 0.38), QPointF(s * 0.50, s * 0.68))
    p.drawLine(QPointF(s * 0.50, s * 0.68), QPointF(s * 0.80, s * 0.38))


def _trash(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.38, s * 0.08, s * 0.24, s * 0.10), s * 0.03, s * 0.03)
    p.drawRoundedRect(QRectF(s * 0.22, s * 0.26, s * 0.56, s * 0.64), s * 0.07, s * 0.07)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawRect(QRectF(s * 0.14, s * 0.18, s * 0.72, s * 0.08))
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.18, s * 0.72, s * 0.08), s * 0.03, s * 0.03)


def _clip(p, s):
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.42, s * 0.20, s * 0.16, s * 0.60), s * 0.08, s * 0.08)
    p.drawRoundedRect(QRectF(s * 0.20, s * 0.42, s * 0.60, s * 0.16), s * 0.08, s * 0.08)


def _document(p, s):
    _fill(p)
    path = QPainterPath()
    path.moveTo(s * 0.24, s * 0.08)
    path.lineTo(s * 0.60, s * 0.08)
    path.lineTo(s * 0.80, s * 0.28)
    path.lineTo(s * 0.80, s * 0.92)
    path.lineTo(s * 0.24, s * 0.92)
    path.closeSubpath()
    p.drawPath(path)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    for y in (0.52, 0.66, 0.80):
        p.drawRect(QRectF(s * 0.36, s * y, s * 0.32, s * 0.06))
    p.drawPolygon(QPolygonF([QPointF(s * 0.60, s * 0.08), QPointF(s * 0.80, s * 0.28), QPointF(s * 0.60, s * 0.28)]))
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _resize(p, s):
    _stroke(p, s, 0.10)
    p.drawLine(QPointF(s * 0.24, s * 0.24), QPointF(s * 0.76, s * 0.76))
    _fill(p)
    tl = QPolygonF([QPointF(s * 0.24, s * 0.24), QPointF(s * 0.24, s * 0.42), QPointF(s * 0.42, s * 0.24)])
    p.drawPolygon(tl)
    br = QPolygonF([QPointF(s * 0.76, s * 0.76), QPointF(s * 0.76, s * 0.58), QPointF(s * 0.58, s * 0.76)])
    p.drawPolygon(br)


def _crop(p, s):
    """Marcas de recorte en las 4 esquinas (icono estándar de 'recortar/márgenes')."""
    _stroke(p, s, 0.10)
    L = s * 0.26
    for cx, cy, dx, dy in ((0.16, 0.16, 1, 1), (0.84, 0.16, -1, 1),
                           (0.16, 0.84, 1, -1), (0.84, 0.84, -1, -1)):
        x, y = s * cx, s * cy
        p.drawLine(QPointF(x, y), QPointF(x + dx * L, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + dy * L))


def _nup(p, s):
    """Icono de N-Up: una hoja dividida en 4, para 'varias páginas por hoja'."""
    _stroke(p, s, 0.08)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.12, s * 0.76, s * 0.76), s * 0.08, s * 0.08)
    p.drawLine(QPointF(s * 0.5, s * 0.12), QPointF(s * 0.5, s * 0.88))
    p.drawLine(QPointF(s * 0.12, s * 0.5), QPointF(s * 0.88, s * 0.5))


def _bolt(p, s):
    """Rayo: automatización / workflows (un solo polígono, robusto a 17px)."""
    _fill(p)
    p.drawPolygon(QPolygonF([
        QPointF(s * 0.60, s * 0.06), QPointF(s * 0.20, s * 0.56), QPointF(s * 0.46, s * 0.56),
        QPointF(s * 0.38, s * 0.94), QPointF(s * 0.80, s * 0.40), QPointF(s * 0.54, s * 0.40)]))


def _play(p, s):
    _fill(p)
    p.drawPolygon(QPolygonF([QPointF(s * 0.26, s * 0.14), QPointF(s * 0.26, s * 0.86),
                             QPointF(s * 0.86, s * 0.50)]))


def _highlight(p, s):
    """Rotulador: punta inclinada y una barra de color debajo."""
    _fill(p)
    p.save()
    p.translate(s * 0.52, s * 0.40)
    p.rotate(40)
    p.drawRoundedRect(QRectF(-s * 0.11, -s * 0.34, s * 0.22, s * 0.46), s * 0.04, s * 0.04)
    p.drawPolygon(QPolygonF([QPointF(-s * 0.11, s * 0.14), QPointF(s * 0.11, s * 0.14), QPointF(s * 0.05, s * 0.28),
                             QPointF(-s * 0.05, s * 0.28)]))
    p.restore()
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.80, s * 0.76, s * 0.11), s * 0.04, s * 0.04)


def _underline(p, s):
    _glyph(p, s * 0.78, "U", bold=True)
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.84, s * 0.68, s * 0.10), s * 0.04, s * 0.04)


def _strike(p, s):
    _glyph(p, s * 0.82, "S", bold=True)
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.10, s * 0.45, s * 0.80, s * 0.10), s * 0.04, s * 0.04)


def _eraser(p, s):
    _fill(p)
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(-40)
    p.drawRoundedRect(QRectF(-s * 0.32, -s * 0.16, s * 0.64, s * 0.32), s * 0.06, s * 0.06)
    p.restore()
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.82, s * 0.76, s * 0.09), s * 0.04, s * 0.04)


def _shapes(p, s):
    _stroke(p, s, 0.10)
    p.drawRoundedRect(QRectF(s * 0.10, s * 0.14, s * 0.46, s * 0.46), s * 0.05, s * 0.05)
    p.drawEllipse(QRectF(s * 0.40, s * 0.42, s * 0.50, s * 0.46))


def _pen(p, s):
    """Trazo ondulado a mano alzada."""
    _stroke(p, s, 0.12)
    path = QPainterPath()
    path.moveTo(s * 0.10, s * 0.66)
    path.cubicTo(s * 0.25, s * 0.10, s * 0.40, s * 0.10, s * 0.50, s * 0.50)
    path.cubicTo(s * 0.60, s * 0.90, s * 0.75, s * 0.90, s * 0.90, s * 0.34)
    p.drawPath(path)


def _image(p, s):
    _stroke(p, s, 0.09)
    p.drawRoundedRect(QRectF(s * 0.10, s * 0.16, s * 0.80, s * 0.68), s * 0.08, s * 0.08)
    _fill(p)
    p.drawEllipse(QRectF(s * 0.26, s * 0.30, s * 0.15, s * 0.15))
    p.drawPolygon(QPolygonF([QPointF(s * 0.16, s * 0.78), QPointF(s * 0.40, s * 0.52), QPointF(s * 0.54, s * 0.66),
                             QPointF(s * 0.66, s * 0.50), QPointF(s * 0.86, s * 0.78)]))


def _signature(p, s):
    """Firma: garabato y línea de base."""
    _stroke(p, s, 0.10)
    path = QPainterPath()
    path.moveTo(s * 0.10, s * 0.62)
    path.cubicTo(s * 0.18, s * 0.20, s * 0.30, s * 0.20, s * 0.34, s * 0.52)
    path.cubicTo(s * 0.38, s * 0.76, s * 0.50, s * 0.34, s * 0.58, s * 0.50)
    path.cubicTo(s * 0.64, s * 0.62, s * 0.76, s * 0.46, s * 0.90, s * 0.46)
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.10, s * 0.82), QPointF(s * 0.90, s * 0.82))


def _form(p, s):
    """Formulario: hoja con una casilla y dos líneas de campo."""
    _stroke(p, s, 0.09)
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.08, s * 0.68, s * 0.84), s * 0.08, s * 0.08)
    p.drawRoundedRect(QRectF(s * 0.28, s * 0.22, s * 0.14, s * 0.14), s * 0.03, s * 0.03)
    p.drawLine(QPointF(s * 0.50, s * 0.29), QPointF(s * 0.72, s * 0.29))
    p.drawLine(QPointF(s * 0.28, s * 0.52), QPointF(s * 0.72, s * 0.52))
    p.drawLine(QPointF(s * 0.28, s * 0.72), QPointF(s * 0.72, s * 0.72))


def _note(p, s):
    """Bocadillo de comentario con dos líneas."""
    _stroke(p, s, 0.09)
    path = QPainterPath()
    path.addRoundedRect(QRectF(s * 0.10, s * 0.12, s * 0.80, s * 0.58), s * 0.10, s * 0.10)
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.28, s * 0.70), QPointF(s * 0.24, s * 0.90))
    p.drawLine(QPointF(s * 0.24, s * 0.90), QPointF(s * 0.46, s * 0.70))
    p.drawLine(QPointF(s * 0.26, s * 0.32), QPointF(s * 0.74, s * 0.32))
    p.drawLine(QPointF(s * 0.26, s * 0.50), QPointF(s * 0.58, s * 0.50))


def _stamp(p, s):
    """Sello: doble marco redondeado con una línea de texto."""
    _stroke(p, s, 0.09)
    p.drawRoundedRect(QRectF(s * 0.10, s * 0.22, s * 0.80, s * 0.56), s * 0.10, s * 0.10)
    _fill(p)
    p.drawRoundedRect(QRectF(s * 0.26, s * 0.42, s * 0.48, s * 0.09), s * 0.03, s * 0.03)
    p.drawRoundedRect(QRectF(s * 0.34, s * 0.58, s * 0.32, s * 0.06), s * 0.03, s * 0.03)


def _wrench(p, s):
    """Llave inglesa: cabeza abierta y mango."""
    _fill(p)
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(-45)
    p.drawRoundedRect(QRectF(-s * 0.07, -s * 0.10, s * 0.14, s * 0.50), s * 0.05, s * 0.05)
    path = QPainterPath()
    path.addEllipse(QRectF(-s * 0.21, -s * 0.46, s * 0.42, s * 0.42))
    p.drawPath(path)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawRoundedRect(QRectF(-s * 0.075, -s * 0.52, s * 0.15, s * 0.28), s * 0.02, s * 0.02)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.restore()


def _copy(p, s):
    """Dos hojas superpuestas."""
    _stroke(p, s, 0.09)
    p.drawRoundedRect(QRectF(s * 0.30, s * 0.10, s * 0.58, s * 0.62), s * 0.07, s * 0.07)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.30, s * 0.58, s * 0.62), s * 0.07, s * 0.07)


_DRAWERS = {
    "copy": _copy, "wrench": _wrench, "stamp": _stamp, "note": _note, "form": _form, "signature": _signature, "image": _image, "pen": _pen, "shapes": _shapes, "highlight": _highlight, "underline": _underline, "strike": _strike, "eraser": _eraser,
    "link": _link, "grid": _grid, "printer": _printer, "droplet": _droplet,
    "pencil": _pencil, "info": _info, "scissors": _scissors, "download": _download,
    "save": _save, "folder": _folder, "archive": _archive, "lock": _lock,
    "swap": _swap, "chevron_left": _chevron_left, "chevron_right": _chevron_right,
    "back": _back, "forward": _forward, "check": _check, "close": _close,
    "trash": _trash, "clip": _clip, "bold": _bold, "italic": _italic, "chevron_down": _chevron_down,
    "document": _document, "resize": _resize, "crop": _crop, "nup": _nup,
    "bolt": _bolt, "play": _play, "plus": _plus, "text_t": _text_t, "text_add": _text_add, "rot_left": _rot_left, "rot_right": _rot_right, "select": _select, "rect": _rect, "ellipse": _ellipse, "line": _line, "arrow": _arrow,
}
