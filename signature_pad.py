# -*- coding: utf-8 -*-
"""
signature_pad.py — Crear una firma (dibujada con el ratón, escrita con letra manuscrita o a partir
de una imagen), guardarla para reutilizarla y devolverla como PNG con fondo transparente.

Las firmas guardadas viven en %APPDATA%\\PDFManager\\signatures. Nada sale del ordenador.
"""
import json
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QSize
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget)

from theme import TEXT, ACCENT, BORDER

COLORS = {"Negro": "#111111", "Azul oscuro": "#1B2A6B", "Azul": "#1E50C8"}
SCRIPT_FONTS = ["Segoe Script", "Ink Free", "Lucida Handwriting", "Brush Script MT", "Segoe Print", "Mistral",
                "Freestyle Script", "Monotype Corsiva", "Lucida Calligraphy", "Kunstler Script", "Vladimir Script",
                "French Script MT", "Edwardian Script ITC", "Segoe UI"]


def signatures_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "PDFManager" / "signatures"


def list_saved() -> list[Path]:
    d = signatures_dir()
    return sorted(d.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []


def _meta_path(png: Path) -> Path:
    return Path(png).with_suffix(".json")


def load_meta(png: Path) -> dict:
    """Nombre y datos de edición de una firma guardada ({} si no hay)."""
    try:
        return json.loads(_meta_path(png).read_text(encoding="utf-8"))
    except Exception:
        return {}


def display_name(png: Path) -> str:
    n = load_meta(png).get("name")
    if n:
        return n
    stem = Path(png).stem.replace("firma_", "")
    try:
        return "Firma " + time.strftime("%d/%m/%Y %H:%M", time.strptime(stem, "%Y%m%d_%H%M%S"))
    except ValueError:
        return "Firma"


def save_png(img: QImage, keep: bool = True, name: str = "", meta: dict | None = None,
             replace: Path | None = None) -> Path:
    """Guarda la firma; si `keep` es False va a la carpeta temporal (solo para este documento).
    `meta` guarda cómo se hizo (para poder editarla luego) y `replace` sobrescribe una firma ya guardada."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    if replace is not None:
        path = Path(replace)
    elif keep:
        d = signatures_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"firma_{stamp}.png"
    else:
        path = Path(tempfile.gettempdir()) / f"pdfmanager_firma_{stamp}.png"
    img.save(str(path), "PNG")
    if keep or replace is not None:
        data = dict(meta or {})
        data["name"] = name.strip() or load_meta(path).get("name") or ""
        try:
            _meta_path(path).write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass
    return path


def rename(png: Path, name: str) -> bool:
    data = load_meta(png)
    data["name"] = name.strip()
    try:
        _meta_path(png).write_text(json.dumps(data), encoding="utf-8")
        return True
    except OSError:
        return False


def strokes_meta(strokes: list, color: str, width: float) -> dict:
    return {"type": "draw", "color": color, "width": width,
            "strokes": [[[q.x(), q.y()] for q in s] for s in strokes]}


def delete_saved(path: Path) -> bool:
    try:
        path.unlink()
        try:
            _meta_path(path).unlink()
        except OSError:
            pass
        return True
    except OSError:
        return False


def _crop_transparent(img: QImage, pad: int = 10) -> QImage | None:
    """Recorta el margen transparente alrededor del dibujo."""
    img = img.convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if (img.pixel(x, y) >> 24) > 8:
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    if x1 < 0:
        return None
    x0, y0 = max(x0 - pad, 0), max(y0 - pad, 0)
    x1, y1 = min(x1 + pad, w - 1), min(y1 + pad, h - 1)
    return img.copy(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def render_strokes(strokes: list, color: str, width: float, scale: float = 3.0) -> QImage | None:
    """Trazos dibujados -> PNG transparente recortado, a mayor resolución para que se vea nítido."""
    if not any(len(s) > 1 for s in strokes):
        return None
    xs = [p.x() for s in strokes for p in s]
    ys = [p.y() for s in strokes for p in s]
    pad = width * 3
    W, H = int((max(xs) - min(xs) + pad * 2) * scale) + 2, int((max(ys) - min(ys) + pad * 2) * scale) + 2
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), width * scale)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    for s in strokes:
        if len(s) < 2:
            continue
        pts = [QPointF((q.x() - min(xs) + pad) * scale, (q.y() - min(ys) + pad) * scale) for q in s]
        path = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            path.quadTo(a, QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2))
        path.lineTo(pts[-1])
        p.drawPath(path)
    p.end()
    return _crop_transparent(img)


def render_text(text: str, family: str, color: str) -> QImage | None:
    text = text.strip()
    if not text:
        return None
    font = QFont(family)
    font.setPixelSize(160)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    box = path.boundingRect()
    pad = 24
    img = QImage(int(box.width()) + pad * 2, int(box.height()) + pad * 2, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(pad - box.x(), pad - box.y())
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(path)
    p.end()
    return _crop_transparent(img)


def from_image_file(path: str, remove_white: bool = True) -> QImage | None:
    """Imagen de una firma en papel (foto o escaneo): el fondo claro se vuelve transparente."""
    try:
        from PIL import Image
    except ImportError:
        img = QImage(path)
        return None if img.isNull() else img
    try:
        im = Image.open(path).convert("RGBA")
    except Exception:
        return None
    if remove_white:
        lum = im.convert("L").point(lambda v: max(0, min(255, int((245 - v) * 5))))
        im.putalpha(lum)
    if max(im.size) > 1600:
        im.thumbnail((1600, 1600))
    data = im.tobytes("raw", "RGBA")
    qimg = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888).copy()
    return _crop_transparent(qimg) if remove_white else qimg


class SignaturePad(QWidget):
    """Lienzo donde se firma con el ratón."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(560, 210)
        self.setCursor(Qt.CrossCursor)
        self.strokes: list[list[QPointF]] = []
        self.color = COLORS["Negro"]
        self.pen_width = 2.6

    def clear(self):
        self.strokes = []
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.strokes.append([QPointF(e.position())])
            self.update()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self.strokes:
            self.strokes[-1].append(QPointF(e.position()))
            self.update()

    def mouseReleaseEvent(self, e):
        if self.strokes and len(self.strokes[-1]) == 1:        # un clic suelto = un punto
            self.strokes[-1].append(self.strokes[-1][0] + QPointF(0.1, 0.1))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#C9C9C9"), 1, Qt.DashLine))
        y = int(self.height() * 0.72)
        p.drawLine(20, y, self.width() - 20, y)
        if not self.strokes:
            p.setPen(QColor("#9A9A9A"))
            p.drawText(self.rect(), Qt.AlignCenter, "Firma aquí con el ratón")
        pen = QPen(QColor(self.color), self.pen_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        for s in self.strokes:
            if len(s) < 2:
                continue
            path = QPainterPath(s[0])
            for a, b in zip(s, s[1:]):
                path.quadTo(a, QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2))
            path.lineTo(s[-1])
            p.drawPath(path)


class _ColorRow(QWidget):
    def __init__(self, on_change):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("Color:"))
        self._buttons = []
        self._on_change = on_change
        for name, hexc in COLORS.items():
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setCheckable(True)
            b.setToolTip(name)
            b.setStyleSheet(f"QPushButton {{ background:{hexc}; border:2px solid {BORDER}; border-radius:13px; }}"
                            f"QPushButton:checked {{ border:3px solid {ACCENT}; }}")
            b.clicked.connect(lambda _=False, h=hexc, btn=b: self._pick(h, btn))
            self._buttons.append(b)
            lay.addWidget(b)
        lay.addStretch(1)
        self._buttons[0].setChecked(True)

    def _pick(self, hexc, btn):
        for b in self._buttons:
            b.setChecked(b is btn)
        self._on_change(hexc)


class SignatureDialog(QDialog):
    """Crear una firma: dibujarla, escribirla o usar una imagen. `result_path` = PNG resultante."""
    def __init__(self, parent=None, default_name: str = "", edit_path: Path | None = None):
        super().__init__(parent)
        self.edit_path = Path(edit_path) if edit_path else None
        self.setWindowTitle("Editar firma" if edit_path else "Crear firma")
        self.resize(640, 560)
        self.result_path: Path | None = None
        self._image: QImage | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("Editar firma" if edit_path else "Crear firma")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # ── Dibujar
        t1 = QWidget(); l1 = QVBoxLayout(t1)
        self.pad = SignaturePad()
        l1.addWidget(self.pad)
        row = QHBoxLayout()
        row.addWidget(_ColorRow(self._set_pad_color))
        row.addWidget(QLabel("Grosor:"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(10, 60)
        self.width_slider.setValue(26)
        self.width_slider.setFixedWidth(120)
        self.width_slider.valueChanged.connect(lambda v: (setattr(self.pad, "pen_width", v / 10), self.pad.update()))
        row.addWidget(self.width_slider)
        clear = QPushButton("Borrar")
        clear.setObjectName("Secondary")
        clear.clicked.connect(self.pad.clear)
        row.addWidget(clear)
        l1.addLayout(row)
        self.tabs.addTab(t1, "Dibujar")

        # ── Escribir
        t2 = QWidget(); l2 = QVBoxLayout(t2)
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setPlaceholderText("Escribe tu nombre")
        self.name_edit.textChanged.connect(self._refresh_fonts)
        l2.addWidget(self.name_edit)
        self.type_color = COLORS["Negro"]
        l2.addWidget(_ColorRow(self._set_type_color))
        self.font_list = QListWidget()
        installed = set(QFontDatabase.families())
        self._fonts = [f for f in SCRIPT_FONTS if f in installed] or ["Segoe UI"]
        for fam in self._fonts:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, fam)
            self.font_list.addItem(it)
        self.font_list.setCurrentRow(0)
        l2.addWidget(self.font_list, 1)
        self._refresh_fonts()
        self.tabs.addTab(t2, "Escribir")

        # ── Imagen
        t3 = QWidget(); l3 = QVBoxLayout(t3)
        pick = QPushButton("Elegir imagen de una firma…")
        pick.setObjectName("Secondary")
        pick.clicked.connect(self._pick_image)
        l3.addWidget(pick, 0, Qt.AlignLeft)
        self.remove_white = QCheckBox("Quitar el fondo claro (para una foto o escaneo de una firma en papel)")
        self.remove_white.setChecked(True)
        self.remove_white.toggled.connect(lambda _: self._load_image(self._image_path) if getattr(self, "_image_path", None) else None)
        l3.addWidget(self.remove_white)
        self.preview = QLabel("Aún no has elegido ninguna imagen.")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#FFFFFF; color:#777777; border-radius:8px;")
        self.preview.setMinimumHeight(200)
        l3.addWidget(self.preview, 1)
        self.tabs.addTab(t3, "Imagen")

        self.sig_name = QLineEdit()
        self.sig_name.setPlaceholderText("Nombre de la firma (p. ej. «Firma corta», «Rúbrica empresa»)")
        lay.addWidget(self.sig_name)
        self.keep = QCheckBox("Guardar esta firma para usarla en otros documentos")
        self.keep.setChecked(True)
        lay.addWidget(self.keep)
        if self.edit_path is not None:
            self._load_for_edit()
        self.note = QLabel("")
        self.note.setObjectName("Hint")
        lay.addWidget(self.note)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancelar"); cancel.setObjectName("Secondary"); cancel.clicked.connect(self.reject)
        ok = QPushButton("Usar firma"); ok.setObjectName("Primary"); ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

    def _load_for_edit(self):
        meta = load_meta(self.edit_path)
        self.sig_name.setText(meta.get("name", ""))
        self.keep.setChecked(True)
        self.keep.setEnabled(False)
        if meta.get("type") == "draw":
            self.pad.strokes = [[QPointF(x, y) for x, y in s] for s in meta.get("strokes", [])]
            self.pad.color = meta.get("color", self.pad.color)
            self.pad.pen_width = float(meta.get("width", self.pad.pen_width))
            self.width_slider.setValue(int(self.pad.pen_width * 10))
            self.tabs.setCurrentIndex(0)
        elif meta.get("type") == "text":
            self.name_edit.setText(meta.get("text", ""))
            self.type_color = meta.get("color", self.type_color)
            fam = meta.get("font")
            for i in range(self.font_list.count()):
                if self.font_list.item(i).data(Qt.UserRole) == fam:
                    self.font_list.setCurrentRow(i)
            self._refresh_fonts()
            self.tabs.setCurrentIndex(1)

    def _set_pad_color(self, hexc):
        self.pad.color = hexc
        self.pad.update()

    def _set_type_color(self, hexc):
        self.type_color = hexc
        self._refresh_fonts()

    def _refresh_fonts(self, *_):
        text = self.name_edit.text().strip() or "Tu nombre"
        for i in range(self.font_list.count()):
            it = self.font_list.item(i)
            fam = it.data(Qt.UserRole)
            f = QFont(fam)
            f.setPixelSize(34)
            it.setFont(f)
            it.setText(text)
            it.setForeground(QColor(self.type_color))
            it.setSizeHint(QSize(100, 54))
        self.font_list.setStyleSheet(
            f"QListWidget {{ background:#FFFFFF; border-radius:8px; }}"
            f"QListWidget::item {{ padding:4px 10px; }}"
            f"QListWidget::item:selected {{ background:#FBE6D0; }}")

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Elige la imagen de tu firma", str(Path.home() / "Pictures"),
                                              "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)")
        if path:
            self._image_path = path
            self._load_image(path)

    def _load_image(self, path):
        img = from_image_file(path, self.remove_white.isChecked())
        self._image = img
        if img is None:
            self.preview.setText("No se pudo leer esa imagen.")
            self.preview.setPixmap(QPixmap())
            return
        self.preview.setText("")
        self.preview.setPixmap(QPixmap.fromImage(img).scaled(self.preview.size() - QSize(20, 20), Qt.KeepAspectRatio,
                                                             Qt.SmoothTransformation))

    def build_image(self) -> QImage | None:
        tab = self.tabs.currentIndex()
        if tab == 0:
            return render_strokes(self.pad.strokes, self.pad.color, self.pad.pen_width)
        if tab == 1:
            it = self.font_list.currentItem()
            return render_text(self.name_edit.text(), it.data(Qt.UserRole) if it else "Segoe UI", self.type_color)
        return self._image

    def _accept(self):
        img = self.build_image()
        if img is None or img.isNull():
            self.note.setText({0: "Dibuja tu firma en el recuadro.", 1: "Escribe tu nombre.",
                               2: "Elige una imagen."}[self.tabs.currentIndex()])
            return
        tab = self.tabs.currentIndex()
        meta = {}
        if tab == 0:
            meta = strokes_meta(self.pad.strokes, self.pad.color, self.pad.pen_width)
        elif tab == 1:
            it = self.font_list.currentItem()
            meta = {"type": "text", "text": self.name_edit.text(), "font": it.data(Qt.UserRole) if it else "Segoe UI",
                    "color": self.type_color}
        self.result_path = save_png(img, keep=self.keep.isChecked(), name=self.sig_name.text(), meta=meta,
                                    replace=self.edit_path)
        self.accept()
