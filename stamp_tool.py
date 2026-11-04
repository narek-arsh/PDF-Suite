# -*- coding: utf-8 -*-
"""
stamp_tool.py — Sellos de texto (APROBADO, RECIBIDO…) con fecha y autor opcionales, como PNG transparente
que se coloca en la página como una imagen (se puede mover, escalar y duplicar).
"""
import json
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from theme import TEXT, ACCENT, BORDER

PRESETS = [("APROBADO", "#1E8E3E"), ("RECHAZADO", "#C5221F"), ("REVISADO", "#1E8E3E"), ("RECIBIDO", "#1A5FD0"),
           ("BORRADOR", "#6B7280"), ("CONFIDENCIAL", "#C5221F"), ("URGENTE", "#E8710A"), ("PAGADO", "#1E8E3E"),
           ("COPIA", "#6B7280"), ("PENDIENTE", "#E8710A")]
COLORS = {"Verde": "#1E8E3E", "Rojo": "#C5221F", "Azul": "#1A5FD0", "Naranja": "#E8710A", "Gris": "#6B7280",
          "Negro": "#111111"}
DATE_MODES = (("none", "Sin fecha"), ("date", "Fecha"), ("datetime", "Fecha y hora"))


def _settings_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "PDFManager" / "stamp.json"


def load_settings() -> dict:
    try:
        return json.loads(_settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(d: dict):
    try:
        p = _settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def date_text(mode: str) -> str:
    if mode == "date":
        return time.strftime("%d/%m/%Y")
    if mode == "datetime":
        return time.strftime("%d/%m/%Y %H:%M")
    return ""


def render_stamp(text: str, color: str, date: str = "", author: str = "", tilt: bool = False) -> QImage | None:
    text = (text or "").strip().upper()
    if not text:
        return None
    families = set(QFontDatabase.families())
    big = QFont("Arial Black" if "Arial Black" in families else "Segoe UI")
    big.setPixelSize(110)
    big.setBold(True)
    small = QFont("Segoe UI")
    small.setPixelSize(44)
    small.setBold(True)
    sub = "  ·  ".join(x for x in (date, author.strip()) if x)
    fm_big, fm_small = QFontMetricsF(big), QFontMetricsF(small)
    w_text = fm_big.horizontalAdvance(text)
    w_sub = fm_small.horizontalAdvance(sub) if sub else 0
    pad, border = 34.0, 9.0
    inner_w = max(w_text, w_sub)
    W = inner_w + pad * 2 + border * 2
    H = fm_big.height() * 0.95 + (fm_small.height() + 8 if sub else 0) + pad * 1.4 + border * 2
    margin = 12
    img = QImage(int(W) + margin * 2, int(H) + margin * 2, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    col = QColor(color)
    pen = QPen(col, border)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(margin + border / 2, margin + border / 2, W - border, H - border), 26, 26)
    p.setFont(big)
    y_top = margin + border + pad * 0.7
    p.drawText(QRectF(margin, y_top, W, fm_big.height() * 0.95), Qt.AlignHCenter | Qt.AlignVCenter, text)
    if sub:
        p.setFont(small)
        p.drawText(QRectF(margin, y_top + fm_big.height() * 0.95 + 4, W, fm_small.height()),
                   Qt.AlignHCenter | Qt.AlignVCenter, sub)
    p.end()
    if tilt:
        t = QTransform().rotate(-9)
        img = img.transformed(t, Qt.SmoothTransformation)
        # recorta el margen transparente que deja el giro
        box = img.rect()
        l, tp, r, b = box.width(), box.height(), -1, -1
        for y in range(0, img.height(), 2):
            for x in range(0, img.width(), 2):
                if (img.pixel(x, y) >> 24) > 8:
                    l, tp, r, b = min(l, x), min(tp, y), max(r, x), max(b, y)
        if r >= 0:
            img = img.copy(max(l - 6, 0), max(tp - 6, 0), min(r - l + 12, img.width()), min(b - tp + 12, img.height()))
    return img


def save_temp_png(img: QImage) -> Path:
    path = Path(tempfile.gettempdir()) / f"pdfmanager_sello_{time.strftime('%Y%m%d_%H%M%S')}.png"
    img.save(str(path), "PNG")
    return path


class StampDialog(QDialog):
    """Elegir y personalizar un sello. `result_path` = PNG del sello (temporal) al aceptar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sello")
        self.resize(520, 520)
        self.result_path: Path | None = None
        st = load_settings()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("Sello")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        lay.addWidget(QLabel("Modelo"))
        self.preset = QComboBox()
        for name, col in PRESETS:
            self.preset.addItem(name, col)
        self.preset.addItem("Texto propio…", None)
        lay.addWidget(self.preset)
        self.text = QLineEdit(st.get("text", PRESETS[0][0]))
        self.text.setPlaceholderText("Texto del sello")
        lay.addWidget(self.text)
        row = QHBoxLayout()
        row.addWidget(QLabel("Color"))
        self.color = QComboBox()
        for name, col in COLORS.items():
            pm = QPixmap(14, 14)
            pm.fill(QColor(col))
            self.color.addItem(pm, name, col)
        row.addWidget(self.color, 1)
        row.addWidget(QLabel("Fecha"))
        self.date = QComboBox()
        for key, label in DATE_MODES:
            self.date.addItem(label, key)
        row.addWidget(self.date, 1)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        self.use_author = QCheckBox("Poner autor:")
        self.author = QLineEdit(st.get("author", os.environ.get("USERNAME", "")))
        row2.addWidget(self.use_author)
        row2.addWidget(self.author, 1)
        lay.addLayout(row2)
        self.tilt = QCheckBox("Inclinado, como un sello de goma")
        lay.addWidget(self.tilt)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(170)
        self.preview.setStyleSheet("background:#FFFFFF; border-radius:10px;")
        lay.addWidget(self.preview, 1)
        self.note = QLabel("")
        self.note.setObjectName("Hint")
        lay.addWidget(self.note)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancelar"); cancel.setObjectName("Secondary"); cancel.clicked.connect(self.reject)
        ok = QPushButton("Colocar sello"); ok.setObjectName("Primary"); ok.clicked.connect(self._ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        # valores guardados
        self.color.setCurrentIndex(max(0, self.color.findText(st.get("color", "Verde"))))
        self.date.setCurrentIndex(max(0, self.date.findData(st.get("date", "date"))))
        self.use_author.setChecked(bool(st.get("use_author", False)))
        self.tilt.setChecked(bool(st.get("tilt", False)))
        self.preset.currentIndexChanged.connect(self._preset_changed)
        for w in (self.text, self.author):
            w.textChanged.connect(self._refresh)
        for w in (self.color, self.date):
            w.currentIndexChanged.connect(self._refresh)
        for w in (self.use_author, self.tilt):
            w.toggled.connect(self._refresh)
        self._refresh()

    def _preset_changed(self):
        col = self.preset.currentData()
        if col is None:
            self.text.setText("")
            self.text.setFocus()
            return
        self.text.setText(self.preset.currentText())
        idx = next((i for i in range(self.color.count()) if self.color.itemData(i) == col), -1)
        if idx >= 0:
            self.color.setCurrentIndex(idx)

    def _build(self):
        return render_stamp(self.text.text(), self.color.currentData(), date_text(self.date.currentData()),
                            self.author.text() if self.use_author.isChecked() else "", self.tilt.isChecked())

    def _refresh(self, *_):
        img = self._build()
        if img is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Escribe el texto del sello")
            return
        self.preview.setText("")
        self.preview.setPixmap(QPixmap.fromImage(img).scaled(self.preview.width() - 24, self.preview.height() - 24,
                                                             Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _ok(self):
        img = self._build()
        if img is None:
            self.note.setText("Escribe el texto del sello.")
            return
        save_settings({"text": self.text.text(), "color": self.color.currentText(), "date": self.date.currentData(),
                       "use_author": self.use_author.isChecked(), "author": self.author.text(),
                       "tilt": self.tilt.isChecked()})
        self.result_path = save_temp_png(img)
        self.accept()
