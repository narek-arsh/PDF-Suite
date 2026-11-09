# -*- coding: utf-8 -*-
"""OCR: editor de esquinas, enderezado de fotos y revisión del texto reconocido."""

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QThread
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QFontMetrics, QPen, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QCheckBox,
    QDialog,
    QMessageBox,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

from PySide6.QtWidgets import QScrollArea
import pdf_tools as ptl
import photo_fix as pf
from theme import TEXT, TEXT_SOFT, ACCENT, DANGER
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.tools import ToolsPage
from ui.common import ICON_DARK, _btn


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: TAMAÑO Y MÁRGENES
# ══════════════════════════════════════════════════════════════════════════
class CornerCanvas(QWidget):
    """Foto con cuatro puntos arrastrables en las esquinas del papel. Con «ver resultado» muestra la página ya estirada."""
    changed = Signal()
    clicked = Signal()                                        # solo en modo no editable: pulsar abre el editor grande

    def __init__(self, image=None):
        super().__init__()
        self.editable = True                                  # False: no se mueven los puntos, solo se pulsa
        self.loupe = False                                    # True: al arrastrar un punto aparece una lupa con cruz
        self._sel = None                                      # punto elegido (las flechas del teclado lo mueven)
        self.setFocusPolicy(Qt.StrongFocus)
        self.image = None                                     # PIL, ya reducida para la pantalla
        self.pix = QPixmap()
        self.corners = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]      # fracciones: TL, TR, BR, BL
        self.preview = None                                   # QPixmap de la página corregida, si se está viendo
        self.show_corners = True                              # False: solo la imagen, sin puntos ni arrastre
        self._drag = None
        if image is not None:
            self.set_image(image)
        self.setMinimumSize(520, 520)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    def set_image(self, image):
        self.image = image
        self.pix = QPixmap.fromImage(QImage(image.tobytes(), image.width, image.height, image.width * 3,
                                            QImage.Format_RGB888).copy())
        self.preview = None
        self.update()

    def _box(self) -> QRectF:
        src = self.preview if self.preview is not None else self.pix
        if src.isNull():
            return QRectF()
        s = min((self.width() - 20) / src.width(), (self.height() - 20) / src.height())
        w, h = src.width() * s, src.height() * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _pt(self, frac) -> QPointF:
        b = self._box()
        return QPointF(b.x() + frac[0] * b.width(), b.y() + frac[1] * b.height())

    def set_corners(self, fr):
        self.corners = [(float(x), float(y)) for x, y in fr]
        self.update()
        self.changed.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#141108"))
        b = self._box()
        src = self.preview if self.preview is not None else self.pix
        if src.isNull():
            return
        p.drawPixmap(b, src, QRectF(src.rect()))
        if self.preview is not None or not self.show_corners:
            return
        pts = [self._pt(c) for c in self.corners]
        path = QPainterPath()
        path.addRect(b)
        poly = QPainterPath()
        poly.moveTo(pts[0])
        for q in pts[1:]:
            poly.lineTo(q)
        poly.closeSubpath()
        shade = path.subtracted(poly)
        p.fillPath(shade, QColor(0, 0, 0, 110))                 # oscurece lo que quedará fuera
        p.setPen(QPen(QColor(ACCENT), 2))
        p.drawPath(poly)
        for i, q in enumerate(pts):
            p.setBrush(QColor(ACCENT) if i == self._sel else QColor("#FFFFFF"))
            p.setPen(QPen(QColor(ACCENT), 2.5))
            p.drawEllipse(q, 9, 9)
            p.setPen(QColor("#1C1409"))
            p.drawText(QRectF(q.x() - 9, q.y() - 9, 18, 18), Qt.AlignCenter, str(i + 1))
        if self.loupe and self._drag is not None:
            self._paint_loupe(p, b)

    def _paint_loupe(self, p: QPainter, b: QRectF):
        """Círculo con zoom sobre el punto que se arrastra, con una cruz en el centro y los lados del recuadro."""
        R, Z = 90.0, 4.0                                      # radio en pantalla y aumento sobre lo que se ve
        fx, fy = self.corners[self._drag]
        q = self._pt((fx, fy))
        k = (b.width() / self.pix.width()) * Z                # píxeles de pantalla por píxel de la imagen, en la lupa
        cx, cy = fx * self.pix.width(), fy * self.pix.height()
        lx = q.x() + (R + 34 if q.x() < self.width() / 2 else -(R + 34))
        ly = q.y() + (R + 34 if q.y() < 2 * R + 50 else -(R + 34))
        lx = min(max(lx, R + 4), self.width() - R - 4)
        ly = min(max(ly, R + 4), self.height() - R - 4)
        circle = QPainterPath()
        circle.addEllipse(QPointF(lx, ly), R, R)
        p.save()
        p.setClipPath(circle)
        p.fillRect(QRectF(lx - R, ly - R, 2 * R, 2 * R), QColor("#141108"))
        half = R / k
        p.drawPixmap(QRectF(lx - R, ly - R, 2 * R, 2 * R), self.pix, QRectF(cx - half, cy - half, 2 * half, 2 * half))
        pts = [QPointF(lx + (c[0] * self.pix.width() - cx) * k, ly + (c[1] * self.pix.height() - cy) * k)
               for c in self.corners]
        p.setPen(QPen(QColor(ACCENT), 1.5))
        poly = QPainterPath()
        poly.moveTo(pts[0])
        for pt_ in pts[1:]:
            poly.lineTo(pt_)
        poly.closeSubpath()
        p.drawPath(poly)
        p.setCompositionMode(QPainter.CompositionMode_Difference)   # cruz en negativo: negra sobre claro, blanca sobre oscuro
        p.setPen(QPen(QColor("#FFFFFF"), 1.5))                       # «+» fina, con hueco en el centro
        gap = 7
        p.drawLine(QPointF(lx - R, ly), QPointF(lx - gap, ly))
        p.drawLine(QPointF(lx + gap, ly), QPointF(lx + R, ly))
        p.drawLine(QPointF(lx, ly - R), QPointF(lx, ly - gap))
        p.drawLine(QPointF(lx, ly + gap), QPointF(lx, ly + R))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(ACCENT), 3))
        p.drawEllipse(QPointF(lx, ly), R, R)

    def keyPressEvent(self, e):
        step = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}.get(e.key())
        if step is None or self._sel is None or not self.editable or self.pix.isNull():
            super().keyPressEvent(e)
            return
        n = 5 if e.modifiers() & Qt.ShiftModifier else 1      # píxeles reales de la imagen
        x, y = self.corners[self._sel]
        x = min(max(x + step[0] * n / self.pix.width(), 0.0), 1.0)
        y = min(max(y + step[1] * n / self.pix.height(), 0.0), 1.0)
        self.corners[self._sel] = (x, y)
        self.update()
        self.changed.emit()

    def _hit(self, pos):
        for i, c in enumerate(self.corners):
            q = self._pt(c)
            if (q.x() - pos.x()) ** 2 + (q.y() - pos.y()) ** 2 <= 16 ** 2:
                return i
        return None

    def mousePressEvent(self, e):
        if not self.editable:
            if e.button() == Qt.LeftButton:
                self.clicked.emit()
            return
        if self.preview is None and self.show_corners and not self.pix.isNull() and e.button() == Qt.LeftButton:
            self._drag = self._hit(e.position())
            if self._drag is not None:
                self._sel = self._drag
            self.setFocus()
            self.update()

    def mouseMoveEvent(self, e):
        if not self.editable or self.preview is not None or not self.show_corners or self.pix.isNull():
            return
        if self._drag is None:
            self.setCursor(Qt.PointingHandCursor if self._hit(e.position()) is not None else Qt.CrossCursor)
            return
        b = self._box()
        x = min(max((e.position().x() - b.x()) / b.width(), 0.0), 1.0)
        y = min(max((e.position().y() - b.y()) / b.height(), 0.0), 1.0)
        self.corners[self._drag] = (x, y)
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, _e):
        self._drag = None
        self.update()


class CornerEditDialog(QDialog):
    """Ventana grande para colocar las cuatro esquinas con precisión: lupa al arrastrar y flechas para afinar."""
    def __init__(self, parent, image, corners, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        geo = (parent.screen() if parent is not None else QApplication.primaryScreen()).availableGeometry()
        self.resize(int(geo.width() * 0.92), int(geo.height() * 0.92))
        self.image = image
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        head = QLabel(title)
        head.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(head)
        hint = QLabel(tr("Arrastra cada punto a su esquina del papel: mientras arrastras aparece una lupa con una cruz «+». "
                      "Para afinar, elige un punto y mueve con las flechas del teclado (1 píxel; con Mayús, 5)."))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.canvas = CornerCanvas(image)
        self.canvas.loupe = True
        self.canvas.setMinimumSize(600, 400)
        self.canvas.corners = [tuple(c) for c in corners]
        lay.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        auto = _btn(tr("Detectar de nuevo"), "bolt", "Secondary", icon_color=TEXT)
        auto.clicked.connect(self._auto)
        full = _btn(tr("Toda la página"), "grid", "Secondary", icon_color=TEXT)
        full.clicked.connect(lambda: self._set([(0.02, 0.02), (0.98, 0.02), (0.98, 0.98), (0.02, 0.98)]))
        self.msg = QLabel("")
        self.msg.setObjectName("Hint")
        cancel = _btn(tr("Cancelar"), None, "Secondary", icon_color=TEXT)
        ok = _btn(tr("Aplicar"), "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        row.addWidget(auto)
        row.addWidget(full)
        row.addWidget(self.msg, 1)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def _set(self, corners):
        self.canvas.set_corners(corners)

    def _auto(self):
        det = pf.detect_corners(self.image)
        if det:
            w, h = self.image.size
            self._set([(x / w, y / h) for x, y in det])
            self.msg.setText(tr("Esquinas detectadas: comprueba que cada punto está en su sitio."))
        else:
            self.msg.setText(tr("No distingo el papel del fondo: colócalas a mano."))

    def corners(self) -> list:
        return [tuple(c) for c in self.canvas.corners]


class _WordEdit(QLineEdit):
    focused = Signal(object)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.focused.emit(self)


class _ReviewLine(QFrame):
    """Una línea de la revisión: arriba el texto reconocido, con cada palabra sobre la suya, y debajo la línea
    original recortada de la página. Así se cruzan de un vistazo."""
    removed = Signal(object)
    add_below = Signal(object)
    word_focused = Signal(object, int)

    def __init__(self, entry: dict, page_pm, z: float, rect: tuple, width: int):
        super().__init__()
        self.entry = entry
        self.z, self.x0p, self.y0p = z, rect[0], rect[1]
        self.setObjectName("Card")
        bbox = entry["bbox"]
        self._crop = None
        self._ytop = 0
        if bbox and page_pm is not None and not page_pm.isNull():
            pad = 3
            self._ytop = max(0, int((bbox[1] - self.y0p - pad) * z))
            ybot = min(page_pm.height(), int((bbox[3] - self.y0p + pad) * z) + 1)
            self._crop = page_pm.copy(0, self._ytop, page_pm.width(), max(10, ybot - self._ytop))
            lh = (bbox[3] - bbox[1]) * z
        else:
            lh = 14 * z
        self._font_px = int(min(max(lh * 0.62, 12), 22))
        row_h = self._font_px + 14

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 6, 0)
        outer.setSpacing(6)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.rec = QWidget()
        self.rec.setFixedSize(width, row_h)
        self.rec.setStyleSheet("background: rgba(192,130,88,0.10);")
        col.addWidget(self.rec)
        self.edits: list = []
        words = entry["words"]
        f = QFont()
        f.setPixelSize(self._font_px)
        fm = QFontMetrics(f)
        if words:
            for i, w in enumerate(words):
                x = int((w[0] - self.x0p) * z)
                nx = int((words[i + 1][0] - self.x0p) * z) if i + 1 < len(words) else width
                adv = fm.horizontalAdvance(str(w[4])) + 14
                wid = int(max((w[2] - w[0]) * z, min(adv, nx - x - 2), 28))
                self._add_edit(str(w[4]), x, wid, row_h, f, i)
        else:
            self._add_edit(entry.get("text", ""), 0, width - 12, row_h, f, 0)
            self.edits[0].setPlaceholderText(tr("Línea nueva"))
        self.orig_text = entry.get("orig", "")
        self.img = QLabel()
        self.img.setFixedWidth(width)
        self.img.setStyleSheet("background: white;")
        col.addWidget(self.img)
        outer.addLayout(col)
        side = QVBoxLayout()
        side.setContentsMargins(0, 4, 0, 4)
        rm = QPushButton("✕")
        rm.setObjectName("Flat")
        rm.setFixedSize(28, 28)
        rm.setToolTip(tr("Borrar esta línea"))
        rm.clicked.connect(lambda: self.removed.emit(self))
        ad = QPushButton("＋")
        ad.setObjectName("Flat")
        ad.setFixedSize(28, 28)
        ad.setToolTip(tr("Añadir una línea nueva debajo"))
        ad.clicked.connect(lambda: self.add_below.emit(self))
        side.addWidget(rm)
        side.addWidget(ad)
        side.addStretch(1)
        outer.addLayout(side)
        self.set_highlight(None)
        self._restyle()

    def _add_edit(self, text: str, x: int, wid: int, h: int, font: QFont, i: int):
        e = _WordEdit(text, self.rec)
        e.setFont(font)
        e.setGeometry(x, 2, wid, h - 4)
        e.setCursorPosition(0)
        e.textChanged.connect(self._restyle)
        e.focused.connect(lambda _e, i=i: self.word_focused.emit(self, i))
        e.returnPressed.connect(e.focusNextChild)
        self.edits.append(e)

    def _restyle(self, *_):
        orig = self.entry.get("orig_words") or []
        same = len(orig) == len(self.edits)
        for i, e in enumerate(self.edits):
            changed = (str(orig[i][4]) != e.text()) if same else (e.text() != self.entry.get("text", e.text()))
            if not self.entry["words"]:
                changed = True
            mark = (self.entry.get("marks") or {}).get(i) if same else None
            border = "rgba(255,255,255,0.12)"
            tip = ""
            bg = "rgba(255,214,0,0.28)" if changed else "rgba(0,0,0,0.25)"
            if mark and not changed:
                if mark[0] == "fixed":                      # separador corregido por su posición
                    bg, tip = "rgba(80,140,220,0.35)", tr("Corregido por su posición: el OCR había leído «{val}»", val=mark[1])
                else:                                       # dudoso: lo mira una persona
                    border, tip = "#E0A030", mark[1]
            e.setToolTip(tip)
            e.setStyleSheet(f"QLineEdit {{ background:{bg}; border:1px solid {border}; border-radius:3px; "
                            f"padding:0 3px; color:{TEXT}; }} QLineEdit:focus {{ border:1px solid {ACCENT}; }}")

    def text(self) -> str:
        return " ".join(t for t in (e.text().strip() for e in self.edits) if t)

    def set_highlight(self, i):
        """Marca en la línea original la palabra que se está editando."""
        if self._crop is None:
            self.img.setFixedHeight(18)
            self.img.setText("  " + tr("(línea añadida: no hay original)"))
            self.img.setStyleSheet("background: #2E3220; color: #A7AC80;")
            return
        pm = QPixmap(self._crop)
        orig = self.entry.get("orig_words") or []
        if i is not None and len(orig) == len(self.edits) and 0 <= i < len(orig):
            w = orig[i]
            qp = QPainter(pm)
            r = QRectF((w[0] - self.x0p) * self.z - 2, (w[1] - self.y0p) * self.z - self._ytop - 2,
                       (w[2] - w[0]) * self.z + 4, (w[3] - w[1]) * self.z + 4)
            qp.fillRect(r, QColor(255, 214, 0, 110))
            qp.setPen(QPen(QColor(230, 160, 0), 2))
            qp.drawRect(r)
            qp.end()
        self.img.setPixmap(pm)
        self.img.setFixedHeight(pm.height())


class OcrReviewDialog(QDialog):
    """Compara lo que ha leído el OCR con la página, línea a línea: cada renglón muestra el texto reconocido (con cada
    palabra encima de la suya) y debajo la línea original. Las palabras se corrigen en su sitio. Al aceptar se elige qué
    guardar: PDF con la imagen y el texto buscable, y/o un PDF nuevo redibujado con el texto."""
    WIDTH = 1000                                            # ancho de la página en pantalla

    def __init__(self, parent, review: dict):
        super().__init__(parent)
        self.setWindowTitle(tr("Revisar el texto reconocido"))
        geo = (parent.screen() if parent is not None else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1180, int(geo.width() * 0.95)), int(geo.height() * 0.92))
        self.review = review
        self.pages = review["pages"]
        self._orig = {pd["index"]: ptl.review_text(pd) for pd in self.pages}
        self._texts = dict(self._orig)
        self._k = -1
        self._doc = ptl._open(review["src"], review.get("password", ""))
        self._page_pm = None
        self._zoom = 1.0
        self._strips: list = []
        self._lit = None                                    # línea con una palabra resaltada
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        title = QLabel(tr("Revisar el texto reconocido"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        hint = QLabel(tr("Cada línea tiene el texto reconocido arriba (cada palabra sobre la suya) y la línea original debajo. "
                      "Corrige las palabras en su sitio: Tab pasa a la siguiente y la palabra original se marca en "
                      "amarillo. Las palabras que cambias se tiñen de amarillo; las cantidades con el separador corregido por "
                      "su posición, de azul; las dudosas llevan borde naranja. Con ✕ borras una línea y con ＋ añades "
                      "otra debajo."))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        nav = QHBoxLayout()
        self.prev_b = _btn(tr("Anterior"), None, "Secondary", icon_color=TEXT)
        self.next_b = _btn(tr("Siguiente"), None, "Secondary", icon_color=TEXT)
        self.prev_b.clicked.connect(lambda: self._goto(self._k - 1))
        self.next_b.clicked.connect(lambda: self._goto(self._k + 1))
        self.page_lbl = QLabel("")
        self.reset_b = _btn(tr("Restaurar el texto leído"), None, "Secondary", icon_color=TEXT)
        self.reset_b.clicked.connect(self._restore)
        nav.addWidget(self.prev_b)
        nav.addWidget(self.page_lbl)
        nav.addWidget(self.next_b)
        nav.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("Hint")
        nav.addWidget(self.count_lbl)
        nav.addWidget(self.reset_b)
        lay.addLayout(nav)

        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(10)
        self.body_lay.addStretch(1)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(self.body)
        sa.setFrameShape(QFrame.NoFrame)
        self.scroll = sa
        lay.addWidget(sa, 1)

        self.cb_search = QCheckBox(tr("PDF con la imagen y el texto detrás (se puede buscar y copiar) — recomendado"))
        self.cb_search.setChecked(True)
        self.cb_redraw = QCheckBox(tr("PDF nuevo redibujado solo con el texto (sin la imagen)"))
        self.cb_redraw.setToolTip(tr("Crea un segundo PDF donde el texto se dibuja a la vista en su posición, con las rayas de "
                                  "las tablas. Sirve para tener el documento limpio y editable. No conserva dibujos, "
                                  "sellos ni fotos."))
        lay.addWidget(self.cb_search)
        lay.addWidget(self.cb_redraw)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = _btn(tr("Cancelar"), None, "Secondary", icon_color=TEXT)
        self.ok = _btn(tr("Guardar"), "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self._goto(0)

    # ── páginas ─────────────────────────────────────────────────────────
    def _page_text(self) -> str:
        """Texto de la página tal como está ahora en pantalla: una línea por renglón y una en blanco entre bloques."""
        out, prev = [], None
        for s in self._strips:
            t = s.text()
            if not t:
                continue
            blk = s.entry["block"]
            if prev is not None and blk != prev:
                out.append("")
            out.append(t)
            prev = blk
        return "\n".join(out)

    def _stash(self):
        if 0 <= self._k < len(self.pages) and self._strips:
            self._texts[self.pages[self._k]["index"]] = self._page_text()

    def _entries(self, pd: dict, text: str) -> list:
        """Líneas que se muestran: cada línea del texto emparejada con la original que le corresponde."""
        old = pd["lines"]
        new = [s.strip() for s in text.split("\n") if s.strip()]
        out, prev_block = [], 0
        for oi, nj in ptl.align_lines([l["text"] for l in old], new):
            if nj is None:
                continue
            if oi is not None:
                ln = old[oi]
                words = list(ln["words"]) if new[nj] == ln["text"] else ptl._line_words(ln["bbox"], ln["words"], new[nj])
                out.append({"oi": oi, "block": ln.get("block", 0), "bbox": ln["bbox"], "words": words,
                            "orig": ln["text"], "orig_words": ln["words"],
                            "marks": ln.get("marks", {}) if len(words) == len(ln["words"]) else {}})
                prev_block = ln.get("block", 0)
            else:
                out.append({"oi": None, "block": prev_block, "bbox": None, "words": [], "text": new[nj], "orig": ""})
        return out

    def _clear(self):
        for s in self._strips:
            s.setParent(None)
            s.deleteLater()
        self._strips = []
        self._lit = None

    def _make_strip(self, entry: dict, pd: dict):
        s = _ReviewLine(entry, self._page_pm, self._zoom, pd["rect"], self.WIDTH)
        s.removed.connect(self._remove)
        s.add_below.connect(self._add_below)
        s.word_focused.connect(self._word_focused)
        for e in s.edits:
            e.textChanged.connect(self._count)
        return s

    def _goto(self, k: int):
        if not (0 <= k < len(self.pages)):
            return
        self._stash()
        self._k = k
        pd = self.pages[k]
        page = self._doc[pd["index"]]
        self._zoom = self.WIDTH / max(page.rect.width, 1.0)
        import fitz as _fz
        pix = page.get_pixmap(matrix=_fz.Matrix(self._zoom, self._zoom), alpha=False)
        self._page_pm = QPixmap.fromImage(QImage(pix.samples, pix.width, pix.height, pix.stride,
                                                 QImage.Format_RGB888).copy())
        self._clear()
        for entry in self._entries(pd, self._texts[pd["index"]]):
            s = self._make_strip(entry, pd)
            self.body_lay.insertWidget(len(self._strips), s)
            self._strips.append(s)
        self.page_lbl.setText("  " + tr("Página {n} de {total} (hoja {sheet} del PDF)",
                                        n=k + 1, total=len(self.pages), sheet=pd['index'] + 1) + "  ")
        self.prev_b.setEnabled(k > 0)
        self.next_b.setEnabled(k < len(self.pages) - 1)
        self.scroll.verticalScrollBar().setValue(0)
        self._count()

    def _restore(self):
        if self._k < 0:
            return
        idx = self.pages[self._k]["index"]
        self._texts[idx] = self._orig[idx]
        k, self._k = self._k, -1                            # evita que _goto guarde lo que hay en pantalla
        self._clear()
        self._goto(k)

    def _remove(self, strip):
        if strip in self._strips:
            self._strips.remove(strip)
            strip.setParent(None)
            strip.deleteLater()
            self._count()

    def _add_below(self, strip):
        if strip not in self._strips:
            return
        pd = self.pages[self._k]
        i = self._strips.index(strip) + 1
        new = self._make_strip({"oi": None, "block": strip.entry["block"], "bbox": None, "words": [], "text": "",
                                "orig": ""}, pd)
        self._strips.insert(i, new)
        self.body_lay.insertWidget(i, new)
        new.edits[0].setFocus()

    def _word_focused(self, strip, i: int):
        if self._lit is not None and self._lit is not strip:
            try:
                self._lit.set_highlight(None)
            except RuntimeError:
                pass
        strip.set_highlight(i)
        self._lit = strip

    def _count(self, *_):
        if not (0 <= self._k < len(self.pages)):
            return
        pd = self.pages[self._k]
        kept = {s.entry["oi"] for s in self._strips if s.entry["oi"] is not None}
        changed = sum(1 for s in self._strips if s.text() != s.orig_text)
        changed += sum(1 for i in range(len(pd["lines"])) if i not in kept)
        word_line = tr("línea") if changed == 1 else tr("líneas")
        word_changed = tr("cambiada") if changed == 1 else tr("cambiadas")
        self.count_lbl.setText(tr("Sin cambios") if changed == 0 else
                               f"{changed} {word_line} {word_changed}")

    # ── resultado ───────────────────────────────────────────────────────
    def _accept(self):
        if not (self.cb_search.isChecked() or self.cb_redraw.isChecked()):
            QMessageBox.information(self, tr("Guardar"), tr("Marca al menos una de las dos opciones de guardado."))
            return
        self._stash()
        self.accept()

    def texts(self) -> dict:
        return dict(self._texts)

    def searchable(self) -> bool:
        return self.cb_search.isChecked()

    def redrawn(self) -> bool:
        return self.cb_redraw.isChecked()

    def done(self, r):
        try:
            self._doc.close()
        except Exception:
            pass
        super().done(r)


_OCR_STATES = {
    "auto": ("Detectadas", ACCENT),
    "manual": ("Manual", "#6C9BD1"),
    "none": ("Sin detectar", DANGER),
    "skip": ("Ya tiene texto · se omite", TEXT_SOFT),
}


class _PageLoader(QThread):
    """Miniatura de cada página y esquinas del papel buscadas solas, sin bloquear la ventana."""
    page_ready = Signal(int, object, object, bool)       # página, miniatura (QImage), esquinas (fracciones) o None, ¿tiene texto?

    def __init__(self, path: str, password: str):
        super().__init__()
        self._path, self._pw = path, password
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        import fitz as _fz
        from PIL import Image
        try:
            doc = ptl._open(self._path, self._pw)
        except Exception:
            return
        try:
            for i in range(len(doc)):
                if self._stop:
                    return
                page = doc[i]
                has_text = len(page.get_text().strip()) >= 25
                k = 640.0 / max(page.rect.width, page.rect.height)
                pix = page.get_pixmap(matrix=_fz.Matrix(k, k), alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                try:
                    det = pf.detect_corners(img)
                except Exception:
                    det = None
                corners = [(x / img.width, y / img.height) for x, y in det] if det else None
                img.thumbnail((300, 300))
                qi = QImage(img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888).copy()
                self.page_ready.emit(i, qi, corners, has_text)
        finally:
            doc.close()


class _PageThumb(QFrame):
    clicked = Signal(int)

    def __init__(self, idx: int):
        super().__init__()
        self.idx, self.pix, self.corners = idx, QPixmap(), None
        self.state, self.selected = "none", False
        self.setObjectName("Card")
        self.setFixedSize(130, 190)
        self.setCursor(Qt.PointingHandCursor)

    def set_data(self, pix, corners, state, selected):
        self.pix, self.corners, self.state, self.selected = pix, corners, state, selected
        self.update()

    def mousePressEvent(self, _e):
        self.clicked.emit(self.idx)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        label_es, color = _OCR_STATES[self.state]
        label = tr(label_es)
        box = QRectF(8, 8, 114, 134)
        if not self.pix.isNull():
            s = min(box.width() / self.pix.width(), box.height() / self.pix.height())
            w, h = self.pix.width() * s, self.pix.height() * s
            r = QRectF(box.x() + (box.width() - w) / 2, box.y() + (box.height() - h) / 2, w, h)
            p.drawPixmap(r, self.pix, QRectF(self.pix.rect()))
            if self.corners and self.state in ("auto", "manual"):
                pts = [QPointF(r.x() + x * r.width(), r.y() + y * r.height()) for x, y in self.corners]
                p.setPen(QPen(QColor(color), 2))
                p.setBrush(Qt.NoBrush)
                p.drawPolygon(pts)
                p.setBrush(QColor("white"))
                for pt_ in pts:
                    p.drawEllipse(pt_, 3.5, 3.5)
        f = p.font()
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(8, 146, 114, 16), Qt.AlignLeft, tr("Página {n}", n=self.idx + 1))
        f.setBold(False)
        f.setPointSize(max(7, f.pointSize() - 1))
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(QRectF(8, 164, 114, 16), Qt.AlignLeft, label)
        if self.selected:
            p.setPen(QPen(QColor(ACCENT), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1.5, 1.5, 127, 187), 8, 8)


class OcrPagesPanel(QWidget):
    """Editor de esquinas del OCR: página grande arriba, tira con todas las páginas abajo y su estado."""
    def __init__(self, tools: "ToolsPage"):
        super().__init__()
        self.tools = tools
        self.pages: list[dict] = []
        self.sel = -1
        self._loader = None
        self._key = None
        self._busy = False                                    # True mientras el código mueve los puntos (no es un arrastre)
        self.setMinimumHeight(540)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        top = QHBoxLayout()
        self.canvas = CornerCanvas()
        self.canvas.setMinimumSize(320, 300)
        self.canvas.editable = False                          # los puntos se mueven en la ventana grande
        self.canvas.setCursor(Qt.PointingHandCursor)
        self.canvas.setToolTip(tr("Pulsa para ajustar las esquinas en grande"))
        self.canvas.clicked.connect(self.open_big)
        top.addWidget(self.canvas, 3)
        side = QFrame()
        side.setObjectName("Card")
        side.setFixedWidth(230)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 14, 14, 14)
        self.title = QLabel("")
        self.title.setStyleSheet(f"font-weight:600; color:{TEXT};")
        sl.addWidget(self.title)
        self.msg = QLabel("")
        self.msg.setObjectName("Hint")
        self.msg.setWordWrap(True)
        sl.addWidget(self.msg)
        for text, icon_name, slot, primary in ((tr("Ajustar en grande…"), "crop", self.open_big, True),
                                               (tr("Detectar esta página"), "bolt", self.detect_current, False),
                                               (tr("Detectar todas"), "bolt", self.detect_all, False),
                                               (tr("Toda la página"), "grid", self.full_page, False)):
            b = _btn(text, icon_name, "Primary" if primary else None)
            b.clicked.connect(slot)
            sl.addWidget(b)
        self.view = QCheckBox(tr("Ver resultado enderezado"))
        self.view.toggled.connect(self._toggle_preview)
        sl.addWidget(self.view)
        sl.addStretch(1)
        top.addWidget(side)
        lay.addLayout(top, 1)

        self.strip = QHBoxLayout()
        self.strip.setSpacing(10)
        self.strip.addStretch(1)
        host = QWidget()
        host.setLayout(self.strip)
        sc = QScrollArea()
        sc.setWidget(host)
        sc.setWidgetResizable(True)
        sc.setFixedHeight(214)
        sc.setFrameShape(QFrame.NoFrame)
        lay.addWidget(sc)
        self.summary = QLabel("")
        self.summary.setObjectName("Hint")
        lay.addWidget(self.summary)

    # ── carga ──────────────────────────────────────────────────────────
    def load(self, f: dict | None, password: str = ""):
        """Carga las páginas del archivo (una sola vez por archivo; se cancela la carga anterior)."""
        key = (f["path"], f.get("pages")) if f and not f.get("locked") else None
        if key == self._key:
            return
        self._key = key
        if self._loader is not None:
            self._loader.stop()
            self._loader.page_ready.disconnect()
            self._loader = None
        while self.strip.count():
            w = self.strip.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.strip.addStretch(1)
        self.pages, self.sel = [], -1
        self.canvas.pix = QPixmap()
        self.canvas.image = None
        self.canvas.preview = None
        self.canvas.update()
        self.title.setText("")
        self.summary.setText("")
        if key is None:
            self.msg.setText(tr("Este archivo no se puede previsualizar (tiene contraseña o no hay archivo)."))
            return
        self.msg.setText(tr("Cargando páginas…"))
        self._loader = _PageLoader(f["path"], password)
        self._loader.page_ready.connect(self._on_page)
        self._loader.start()

    def _on_page(self, idx: int, qimg, corners, has_text: bool):
        thumb = _PageThumb(idx)
        thumb.clicked.connect(self.select)
        self.strip.insertWidget(len(self.pages), thumb)
        self.pages.append({"pix": QPixmap.fromImage(qimg), "auto": corners, "corners": corners,
                           "src": "auto" if corners else "none", "has_text": has_text, "thumb": thumb})
        self._refresh(idx)
        if self.sel < 0:
            self.select(0)
        else:
            self.title.setText(tr("Página {n} de {total}", n=self.sel + 1, total=len(self.pages)))

    # ── estado ─────────────────────────────────────────────────────────
    def _state(self, i: int) -> str:
        st = self.pages[i]
        if st["has_text"] and self.tools.ocr_only.isChecked():
            return "skip"
        return st["src"]

    def _refresh(self, i: int):
        st = self.pages[i]
        st["thumb"].set_data(st["pix"], st["corners"], self._state(i), i == self.sel)
        self._summary()

    def refresh_all(self):
        for i in range(len(self.pages)):
            self._refresh(i)
        if 0 <= self.sel < len(self.pages):
            self._show_message()

    def _summary(self):
        counts = {"auto": 0, "manual": 0, "none": 0, "skip": 0}
        for i in range(len(self.pages)):
            counts[self._state(i)] += 1
        parts = [tr("{n} detectadas", n=counts['auto']), tr("{n} manual", n=counts['manual'])]
        if counts["none"]:
            parts.append(tr("{n} sin detectar (solo se endereza el texto)", n=counts['none']))
        if counts["skip"]:
            parts.append(tr("{n} ya tienen texto (se omiten)", n=counts['skip']))
        self.summary.setText(" · ".join(parts))

    def manual(self) -> dict:
        """{página: esquinas} de las páginas marcadas a mano; el resto las busca solo el programa."""
        return {i: [tuple(c) for c in st["corners"]] for i, st in enumerate(self.pages) if st["src"] == "manual"}

    # ── página seleccionada ────────────────────────────────────────────
    def select(self, i: int):
        if not 0 <= i < len(self.pages):
            return
        old, self.sel = self.sel, i
        if 0 <= old < len(self.pages):
            self._refresh(old)
        f = self.tools._file()
        try:
            doc = ptl._open(f["path"], self.tools.pw_field.text())
            try:
                img = pf.render_page(doc, i, 150, 1100)
            finally:
                doc.close()
        except Exception:
            return
        self._busy = True
        self.canvas.set_image(img)
        st = self.pages[i]
        self.canvas.corners = [tuple(c) for c in (st["corners"] or [(0.12, 0.12), (0.88, 0.12), (0.88, 0.88), (0.12, 0.88)])]
        self._busy = False
        self.view.setChecked(False)
        self._refresh(i)
        self._show_message()
        self.canvas.update()

    def _show_message(self):
        i = self.sel
        state = self._state(i)
        self.title.setText(tr("Página {n} de {total}", n=i + 1, total=len(self.pages)))
        self.canvas.show_corners = state != "skip"
        self.msg.setText({
            "auto": tr("Esquinas detectadas automáticamente. Si algo no encaja, pulsa «Ajustar en grande…»."),
            "manual": tr("Esquinas marcadas por ti. «Detectar esta página» vuelve a la detección automática."),
            "none": tr("No distingo el papel del fondo. Pulsa «Ajustar en grande…» para marcar las esquinas, o déjala "
                    "así (solo se endereza el texto)."),
            "skip": tr("Esta página ya tiene texto y se deja como está (desmarca «Solo las páginas sin texto» para "
                    "tratarla)."),
        }[state])
        self.canvas.update()

    def _set_corners(self, corners, src: str):
        st = self.pages[self.sel]
        st["corners"], st["src"] = corners, src
        self._busy = True
        if corners:
            self.canvas.corners = [tuple(c) for c in corners]
        self._busy = False
        self._refresh(self.sel)
        self._show_message()
        self._refresh_preview()

    # ── botones ────────────────────────────────────────────────────────
    def detect_current(self):
        if not 0 <= self.sel < len(self.pages) or self.canvas.image is None:
            return
        det = pf.detect_corners(self.canvas.image)
        w, h = self.canvas.image.size
        corners = [(x / w, y / h) for x, y in det] if det else None
        self.pages[self.sel]["auto"] = corners
        self._set_corners(corners, "auto" if corners else "none")

    def detect_all(self):
        for st in self.pages:
            st["corners"], st["src"] = st["auto"], ("auto" if st["auto"] else "none")
        if 0 <= self.sel < len(self.pages):
            st = self.pages[self.sel]
            if st["corners"]:
                self._busy = True
                self.canvas.corners = [tuple(c) for c in st["corners"]]
                self._busy = False
            self._refresh_preview()
        self.refresh_all()

    def open_big(self):
        if not 0 <= self.sel < len(self.pages) or self._state(self.sel) == "skip":
            return
        f = self.tools._file()
        try:
            doc = ptl._open(f["path"], self.tools.pw_field.text())
            try:
                img = pf.render_page(doc, self.sel, 200, 2600)
            finally:
                doc.close()
        except Exception:
            return
        st = self.pages[self.sel]
        start = st["corners"] or [(0.12, 0.12), (0.88, 0.12), (0.88, 0.88), (0.12, 0.88)]
        dlg = CornerEditDialog(self.window(), img, start, tr("Esquinas · página {n}", n=self.sel + 1))
        if dlg.exec() != QDialog.Accepted:
            return
        new = dlg.corners()
        moved = any(abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1e-4 for a, b in zip(new, start))
        if moved:
            self._set_corners(new, "manual")

    def full_page(self):
        if 0 <= self.sel < len(self.pages):
            self._set_corners([(0.02, 0.02), (0.98, 0.02), (0.98, 0.98), (0.02, 0.98)], "manual")

    def _toggle_preview(self, on: bool):
        self.canvas.preview = None
        if on:
            self._refresh_preview()
        else:
            self.canvas.update()

    def _refresh_preview(self):
        if not self.view.isChecked() or self.canvas.image is None:
            return
        img = self.canvas.image
        quad = pf.order_corners([(x * img.width, y * img.height) for x, y in self.canvas.corners])
        if not pf.is_convex(quad):
            self.canvas.preview = None
            return
        flat = pf.flatten_light(pf.warp(img, quad, pf.target_size(quad, "auto", max_side=900)))
        self.canvas.preview = QPixmap.fromImage(QImage(flat.tobytes(), flat.width, flat.height, flat.width * 3,
                                                       QImage.Format_RGB888).copy())
        self.canvas.update()
