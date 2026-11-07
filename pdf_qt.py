# -*- coding: utf-8 -*-
"""
PDF Manager – Travel Agent Edition (PySide6)
Interfaz nativa en Qt. Toda la lógica de PDF vive en backend.py.
"""
import copy
import shutil
import time
import os
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRect, QRectF, QUrl, QTimer, QEvent, QPoint, QPointF, Signal, QThread, QObject
from PySide6.QtGui import (
    QPixmap, QIcon, QImage, QPainter, QColor, QFont, QFontMetrics, QPen,
    QDesktopServices, QBrush, QShortcut, QKeySequence, QCursor, QFontDatabase,
    QTextBlockFormat, QTextCursor, QTextCharFormat, QTextFormat, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QFileDialog,
    QFrame, QStackedWidget, QComboBox, QCheckBox, QRadioButton, QButtonGroup,
    QSpinBox, QDoubleSpinBox, QSlider, QDialog, QMessageBox, QAbstractItemView,
    QGraphicsDropShadowEffect, QMenu, QStatusBar, QTextEdit, QInputDialog, QSizePolicy,
    QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QProgressDialog,
    QStyle, QGraphicsItem, QStyleOptionSlider, QColorDialog, QGridLayout, QProgressBar,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

import backend as be
import icons as ic
import winfonts
import fontmanager as fm
import annot_tools as at
import signature_pad as sp
import form_tools as ft
import stamp_tool as st_
from PySide6.QtWidgets import QPlainTextEdit, QSplitter, QScrollArea
import pdf_tools as ptl
import layout_tools as lt
import photo_fix as pf
import workflows as wf
import draft as dr
import click_icons as ci
from theme import QSS, BG, SURFACE, SURFACE_2, SURFACE_3, TEXT, TEXT_SOFT, ACCENT, BORDER, BORDER_STRONG, DANGER
from flow_layout import FlowLayout

ICON_DARK = "#1C1409"   # para iconos sobre fondo de acento (botones Primary)


def _btn(text: str, icon_name: str | None = None, object_name: str | None = None,
         icon_color: str | None = None, size: int = 17) -> QPushButton:
    """Crea un QPushButton con un icono vectorial propio (sin emoji)."""
    b = QPushButton(("  " + text) if (icon_name and text) else text)
    if object_name:
        b.setObjectName(object_name)
    if icon_name:
        color = icon_color or (ICON_DARK if object_name == "Primary" else TEXT)
        b.setIcon(ic.icon(icon_name, color, size))
        b.setIconSize(QSize(size, size))
    return b

FILE_COLORS = be.FILE_COLORS


# ── Helpers genéricos ───────────────────────────────────────────────────
def pil_to_qpixmap(img) -> QPixmap:
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


def run_bg(fn, *args, **kwargs):
    threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()


class _GuiBridge(QObject):
    """Deja que un hilo secundario pida que algo se ejecute en el hilo de la pantalla (Qt no admite tocar la
    interfaz desde otro hilo: da «Timers cannot be stopped from another thread» y cuelgues)."""
    run = Signal(object)

    def __init__(self):
        super().__init__()
        self.run.connect(lambda fn: fn())


_GUI_BRIDGE = None


def on_gui(fn):
    """Ejecuta fn() en el hilo de la pantalla; se puede llamar desde cualquier hilo."""
    if _GUI_BRIDGE is not None:
        _GUI_BRIDGE.run.emit(fn)
    else:
        fn()


_LOGO_CACHE: dict[int, QPixmap] = {}


def provecto_logo_pixmap(size: int = 40) -> QPixmap | None:
    """Renderiza el logo de Provecto (SVG) a un QPixmap cuadrado, cacheado."""
    if size in _LOGO_CACHE:
        return _LOGO_CACHE[size]
    svg_path = be.resource_path("provecto_logo.svg")
    pix = None
    if HAS_SVG and Path(svg_path).is_file():
        renderer = QSvgRenderer(svg_path)
        if renderer.isValid():
            img = QImage(size, size, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            renderer.render(p, QRectF(0, 0, size, size))
            p.end()
            pix = QPixmap.fromImage(img)
    _LOGO_CACHE[size] = pix
    return pix


def add_shadow(widget, blur=24, dy=6, alpha=90):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def render_file_card(name: str, pages: int, color: str, width: int = 620, height: int = 84,
                     path: str | None = None) -> QPixmap:
    """Pre-renderiza la tarjeta de un archivo como pixmap único: así el
    drag&drop interno de Qt mueve la tarjeta entera sin glitches."""
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(SURFACE_2))
    p.drawRoundedRect(0, 0, width, height, 13, 13)

    p.setBrush(QColor(color))
    p.drawRoundedRect(0, 10, 5, height - 20, 2, 2)

    box = QRect(18, 8, 56, height - 16)
    thumb = None
    png = be.get_page_thumbnail_png(path, 0, width=140) if path else None
    if png:
        t = QPixmap()
        if t.loadFromData(png):
            thumb = t.scaled(box.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if thumb:
        tx = box.x() + (box.width() - thumb.width()) // 2
        ty = box.y() + (box.height() - thumb.height()) // 2
        p.drawPixmap(tx, ty, thumb)
        p.setPen(QPen(QColor(243, 241, 228, 70), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(tx, ty, thumb.width() - 1, thumb.height() - 1)
        p.setPen(Qt.NoPen)
    else:
        doc_icon = ic.icon("document", TEXT, 22).pixmap(22, 22)
        p.drawPixmap(box.x() + (box.width() - 22) // 2, (height - 22) // 2, doc_icon)

    text_x = 90
    text_w = width - text_x - 60
    name_font = QFont("Segoe UI", 11, QFont.DemiBold)
    p.setFont(name_font)
    fm = QFontMetrics(name_font)
    elided = fm.elidedText(name, Qt.ElideRight, text_w)
    p.setPen(QColor(TEXT))
    p.drawText(QRect(text_x, 19, text_w, 24), Qt.AlignVCenter | Qt.AlignLeft, elided)

    pages_font = QFont("Segoe UI", 9)
    p.setFont(pages_font)
    p.setPen(QColor(TEXT_SOFT))
    p.drawText(QRect(text_x, 44, text_w, 20), Qt.AlignVCenter | Qt.AlignLeft,
               f"{pages} pág.")

    hint_font = QFont("Segoe UI", 8)
    p.setFont(hint_font)
    p.setPen(QColor(TEXT_SOFT))
    p.drawText(QRect(0, 0, width - 16, height), Qt.AlignVCenter | Qt.AlignRight, "⠿⠿")

    p.end()
    return pix


# ══════════════════════════════════════════════════════════════════════════
#  LISTA DE ARCHIVOS (home) — drop nativo del SO + reordenado nativo de Qt
# ══════════════════════════════════════════════════════════════════════════
class FileListWidget(QListWidget):
    """
    Nota de robustez: el drag&drop interno de Qt mueve los QListWidgetItem
    serializando sus datos (QDataStream) para construir el MIME interno.
    Guardar un dict de Python directamente en Qt.UserRole depende de que esa
    serialización trate bien un objeto arbitrario, lo cual no está garantizado.
    Por eso aquí solo se guarda un id() (int, se serializa sin problemas) y se
    resuelve contra un diccionario propio — así el orden sobrevive al drop
    pase lo que pase con la serialización de Qt.
    """
    def __init__(self, on_files_dropped, on_order_changed, on_remove, on_open):
        super().__init__()
        self._on_files_dropped = on_files_dropped
        self._on_order_changed = on_order_changed
        self._on_remove = on_remove
        self._on_open = on_open
        self._id_map: dict[int, dict] = {}

        self.setViewMode(QListWidget.ListMode)
        self.setFlow(QListWidget.TopToBottom)
        self.setWrapping(False)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(6)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setIconSize(QSize(620, 84))
        self.setCursor(Qt.OpenHandCursor)
        self.itemDoubleClicked.connect(lambda item: self._on_open(self._resolve(item)))

    def set_items(self, files: list[dict]):
        vbar = self.verticalScrollBar()
        scroll_val = vbar.value()
        self.clear()
        self._id_map = {id(f): f for f in files}
        for i, f in enumerate(files):
            color = FILE_COLORS[i % len(FILE_COLORS)]
            pix = render_file_card(f["name"], f["pages"], color, path=f["path"])
            item = QListWidgetItem(QIcon(pix), "")
            item.setData(Qt.UserRole, id(f))
            item.setSizeHint(QSize(pix.width(), pix.height() + 6))
            self.addItem(item)
        vbar.setValue(scroll_val)
        QTimer.singleShot(0, lambda: vbar.setValue(scroll_val))

    def _resolve(self, item: QListWidgetItem):
        return self._id_map.get(item.data(Qt.UserRole))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
            e.acceptProposedAction()
            if paths:
                self._on_files_dropped(paths)
        else:
            super().dropEvent(e)
            self._on_order_changed(self._current_order())

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            item = self.currentItem()
            if item:
                self._on_remove(self._resolve(item))
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        item = self.itemAt(e.pos())
        if not item:
            return
        f = self._resolve(item)
        menu = QMenu(self)
        open_act = menu.addAction("Abrir")
        remove_act = menu.addAction("Quitar archivo")
        action = menu.exec(e.globalPos())
        if action == remove_act:
            self._on_remove(f)
        elif action == open_act:
            self._on_open(f)

    def _current_order(self):
        order = [self._resolve(self.item(r)) for r in range(self.count())]
        return [f for f in order if f is not None]


class DropArea(QFrame):
    """Zona grande que acepta soltar PDFs incluso cuando la lista está vacía."""
    def __init__(self, on_files_dropped):
        super().__init__()
        self._on_files_dropped = on_files_dropped
        self.setAcceptDrops(True)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        icon = QLabel(alignment=Qt.AlignCenter)
        icon.setPixmap(ic.icon("folder", TEXT_SOFT, 34).pixmap(34, 34))
        txt = QLabel("Arrastra PDFs o fotos aquí (también texto, HTML, Word…)", alignment=Qt.AlignCenter)
        txt.setObjectName("Hint")
        lay.addStretch(1)
        lay.addWidget(icon)
        lay.addWidget(txt)
        lay.addStretch(1)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
        if paths:
            self._on_files_dropped(paths)


class BackHeader(QWidget):
    def __init__(self, title: str, on_back):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        back_btn = _btn("Volver", "back", "Flat")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(on_back)
        lbl = QLabel(title)
        lbl.setObjectName("Header")
        lay.addWidget(back_btn)
        lay.addSpacing(10)
        lay.addWidget(lbl)
        lay.addStretch(1)


# ══════════════════════════════════════════════════════════════════════════
#  AJUSTE B&N — diálogo con preview en vivo
# ══════════════════════════════════════════════════════════════════════════
class JumpSlider(QSlider):
    """Un clic sobre la barra salta directo a ese valor (Qt, por defecto,
    solo avanza un 'paso de página' hacia el clic) y sigue arrastrando."""
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.orientation() == Qt.Horizontal:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            style = self.style()
            groove = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
            handle = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            pos = e.position().toPoint()
            if not handle.contains(pos):
                span = max(1, groove.width() - handle.width())
                x = pos.x() - groove.x() - handle.width() // 2
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), x, span, opt.upsideDown))
        super().mousePressEvent(e)


def make_slider_row(label: str, lo: int, hi: int, val: int, on_change,
                    suffix: str = "") -> tuple[QWidget, QSlider]:
    """Fila 'etiqueta + barra + campo numérico' con ambos sincronizados."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label)
    lbl.setFixedWidth(90)
    lbl.setObjectName("Hint")
    sl = JumpSlider(Qt.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(val)
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    sp.setSuffix(suffix)
    sp.setKeyboardTracking(False)
    sp.setFixedWidth(92)
    sl.valueChanged.connect(sp.setValue)
    sp.valueChanged.connect(sl.setValue)
    sl.valueChanged.connect(on_change)
    lay.addWidget(lbl)
    lay.addWidget(sl, 1)
    lay.addWidget(sp)
    return w, sl


class AjusteDialog(QDialog):
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de imagen")
        self.resize(640, 660)
        self.path = path
        self.total_pages = be.safe_page_count(path)
        self.cur_page = 0
        self.bw = False
        self.result_path = None
        self.applied_params: dict | None = None   # valores aplicados (+ "pages" si no fue a todas)

        root = QVBoxLayout(self)

        self.preview = QLabel(alignment=Qt.AlignCenter)
        self.preview.setMinimumHeight(380)
        self.preview.setStyleSheet(f"background:{SURFACE}; border-radius:12px;")
        root.addWidget(self.preview, 1)

        nav = QHBoxLayout()
        prev_btn = _btn("", "chevron_left"); prev_btn.setFixedWidth(42)
        next_btn = _btn("", "chevron_right"); next_btn.setFixedWidth(42)
        prev_btn.clicked.connect(self._prev_page)
        next_btn.clicked.connect(self._next_page)
        self.page_lbl = QLabel(f"Página 1 / {self.total_pages}")
        self.page_lbl.setObjectName("Hint")
        nav.addWidget(prev_btn)
        nav.addWidget(self.page_lbl)
        nav.addWidget(next_btn)
        nav.addStretch(1)
        root.addLayout(nav)

        brillo_row, self.brillo_sl = make_slider_row("Brillo", -100, 100, 0, self._render_preview)
        contraste_row, self.contraste_sl = make_slider_row(
            "Contraste", 50, 200, 100, self._render_preview, " %")
        self.sat_row, self.sat_sl = make_slider_row(
            "Saturación", 0, 200, 100, self._render_preview, " %")
        root.addWidget(brillo_row)
        root.addWidget(contraste_row)
        root.addWidget(self.sat_row)

        self.bw_check = QCheckBox("Blanco y negro")
        self.bw_check.stateChanged.connect(self._on_bw_toggle)
        root.addWidget(self.bw_check)

        btn_row = QHBoxLayout()
        apply_page_btn = QPushButton("Aplicar a esta página")
        apply_page_btn.setObjectName("Primary")
        apply_all_btn = QPushButton("Aplicar a todas las páginas de este PDF")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("Danger")
        apply_page_btn.clicked.connect(lambda: self._apply(False))
        apply_all_btn.clicked.connect(lambda: self._apply(True))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(apply_page_btn)
        btn_row.addWidget(apply_all_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        self._render_preview()

    def _on_bw_toggle(self, state):
        self.bw = bool(state)
        self.sat_row.setDisabled(self.bw)
        self._render_preview()

    def _vals(self):
        return (self.brillo_sl.value() / 100.0,
                self.contraste_sl.value() / 100.0,
                self.sat_sl.value() / 100.0)

    def _render_preview(self, *_):
        brillo, contraste, sat = self._vals()
        img = be.get_adjusted_page_image(self.path, self.cur_page, brillo,
                                          contraste, sat, self.bw)
        if img is None:
            self.preview.setText("No se pudo generar la vista previa")
            return
        img.thumbnail((560, 380))
        self.preview.setPixmap(pil_to_qpixmap(img))

    def _prev_page(self):
        if self.cur_page > 0:
            self.cur_page -= 1
            self.page_lbl.setText(f"Página {self.cur_page + 1} / {self.total_pages}")
            self._render_preview()

    def _next_page(self):
        if self.cur_page < self.total_pages - 1:
            self.cur_page += 1
            self.page_lbl.setText(f"Página {self.cur_page + 1} / {self.total_pages}")
            self._render_preview()

    def _apply(self, apply_all: bool):
        brillo, contraste, sat = self._vals()
        pages = None if apply_all else [self.cur_page]
        out = be.apply_adjustment_to_pdf(self.path, brillo, contraste, sat,
                                          self.bw, pages=pages)
        if out:
            self.result_path = out
            self.applied_params = {"brillo": brillo, "contraste": contraste,
                                   "saturacion": sat, "bw": self.bw}
            if not apply_all:
                self.applied_params["pages"] = [self.cur_page]   # 0-based
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo aplicar el ajuste.")


# ══════════════════════════════════════════════════════════════════════════
#  AJUSTE B&N — varios archivos a la vez, navegando página a página por
#  todos ellos como si estuvieran unidos (sin unirlos de verdad)
# ══════════════════════════════════════════════════════════════════════════
class AjusteMultiDialog(QDialog):
    def __init__(self, files: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de imagen — varios archivos")
        self.resize(640, 700)
        self.files = files
        self.flat: list[tuple[int, int]] = []   # (file_idx, page_idx) por cada página, en orden
        for fi, f in enumerate(files):
            for pi in range(be.safe_page_count(f["path"])):
                self.flat.append((fi, pi))
        self.cur = 0
        self.bw = False
        self.results: dict[int, str] = {}   # file_idx -> ruta de salida (tras aplicar)
        self.applied_params: dict | None = None

        root = QVBoxLayout(self)

        hint = QLabel("Navega por las páginas de todos los archivos como en un merge. "
                       "El ajuste se aplicará a todas las páginas de todos los archivos cargados.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.preview = QLabel(alignment=Qt.AlignCenter)
        self.preview.setMinimumHeight(380)
        self.preview.setStyleSheet(f"background:{SURFACE}; border-radius:12px;")
        root.addWidget(self.preview, 1)

        nav = QHBoxLayout()
        prev_btn = _btn("", "chevron_left"); prev_btn.setFixedWidth(42)
        next_btn = _btn("", "chevron_right"); next_btn.setFixedWidth(42)
        prev_btn.clicked.connect(self._prev_page)
        next_btn.clicked.connect(self._next_page)
        self.page_lbl = QLabel()
        self.page_lbl.setObjectName("Hint")
        nav.addWidget(prev_btn)
        nav.addWidget(self.page_lbl)
        nav.addWidget(next_btn)
        nav.addStretch(1)
        root.addLayout(nav)

        brillo_row, self.brillo_sl = make_slider_row("Brillo", -100, 100, 0, self._render_preview)
        contraste_row, self.contraste_sl = make_slider_row(
            "Contraste", 50, 200, 100, self._render_preview, " %")
        self.sat_row, self.sat_sl = make_slider_row(
            "Saturación", 0, 200, 100, self._render_preview, " %")
        root.addWidget(brillo_row)
        root.addWidget(contraste_row)
        root.addWidget(self.sat_row)

        self.bw_check = QCheckBox("Blanco y negro")
        self.bw_check.stateChanged.connect(self._on_bw_toggle)
        root.addWidget(self.bw_check)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Aplicar a todos los archivos")
        apply_btn.setObjectName("Primary")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("Danger")
        apply_btn.clicked.connect(self._apply_all)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        self._update_label()
        self._render_preview()

    def _current(self):
        fi, pi = self.flat[self.cur]
        return self.files[fi], fi, pi

    def _update_label(self):
        f, fi, pi = self._current()
        total_local = be.safe_page_count(f["path"])
        self.page_lbl.setText(
            f"{f['name']} — página {pi + 1}/{total_local}   ·   "
            f"({self.cur + 1}/{len(self.flat)} en total)")

    def _on_bw_toggle(self, state):
        self.bw = bool(state)
        self.sat_row.setDisabled(self.bw)
        self._render_preview()

    def _vals(self):
        return (self.brillo_sl.value() / 100.0,
                self.contraste_sl.value() / 100.0,
                self.sat_sl.value() / 100.0)

    def _render_preview(self, *_):
        f, fi, pi = self._current()
        brillo, contraste, sat = self._vals()
        img = be.get_adjusted_page_image(f["path"], pi, brillo, contraste, sat, self.bw)
        if img is None:
            self.preview.setText("No se pudo generar la vista previa")
            return
        img.thumbnail((560, 380))
        self.preview.setPixmap(pil_to_qpixmap(img))

    def _prev_page(self):
        if self.cur > 0:
            self.cur -= 1
            self._update_label()
            self._render_preview()

    def _next_page(self):
        if self.cur < len(self.flat) - 1:
            self.cur += 1
            self._update_label()
            self._render_preview()

    def _apply_all(self):
        if not self.flat:
            self.reject(); return
        brillo, contraste, sat = self._vals()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for fi, f in enumerate(self.files):
                out = be.apply_adjustment_to_pdf(f["path"], brillo, contraste, sat, self.bw)
                if out:
                    self.results[fi] = out
        finally:
            QApplication.restoreOverrideCursor()
        if self.results:
            self.applied_params = {"brillo": brillo, "contraste": contraste,
                                   "saturacion": sat, "bw": self.bw}
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo aplicar el ajuste.")


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: HOME
# ══════════════════════════════════════════════════════════════════════════
class HomePage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.side = QFrame()
        self.side.setObjectName("Card")
        self.side.setFixedWidth(230)
        self._build_sidebar()
        root.addWidget(self.side)

        main = QWidget()
        root.addWidget(main, 1)
        col = QVBoxLayout(main)
        col.setContentsMargins(24, 20, 24, 20)
        col.setSpacing(12)

        url_row = QHBoxLayout()
        self.url_field = QLineEdit()
        self.url_field.setPlaceholderText("Pega un enlace a un PDF y pulsa Enter (o arrastra archivos aquí)")
        self.url_field.returnPressed.connect(self._load_from_url)
        attach_btn = _btn("Añadir archivos", "clip")
        attach_btn.setToolTip("Subir PDFs o fotos desde el ordenador")
        attach_btn.clicked.connect(self._browse_files)
        url_row.addWidget(self.url_field, 1)
        url_row.addWidget(attach_btn)
        col.addLayout(url_row)

        self.hint = QLabel()
        self.hint.setObjectName("Hint")
        col.addWidget(self.hint)

        self.drop_area = DropArea(self._handle_files_dropped)
        self.file_list = FileListWidget(
            on_files_dropped=self._handle_files_dropped,
            on_order_changed=self.win.reorder_files,
            on_remove=self.win.remove_file_obj,
            on_open=self.win.open_in_viewer,
        )
        col.addWidget(self.drop_area, 1)
        col.addWidget(self.file_list, 1)

        self.steps_bar = QFrame()
        self.steps_bar.setObjectName("Card")
        sb = QHBoxLayout(self.steps_bar)
        sb.setContentsMargins(14, 8, 10, 8)
        self.steps_lbl = QLabel()
        self.steps_lbl.setObjectName("Hint")
        self.steps_lbl.setWordWrap(True)
        self.save_wf_btn = _btn("Guardar como workflow", "bolt", "Primary")
        save_wf_btn = self.save_wf_btn
        save_wf_btn.clicked.connect(self.win.save_session_as_workflow)
        self.append_wf_btn = _btn("Añadir al workflow", "bolt", "Primary")
        self.append_wf_btn.clicked.connect(self.win.append_session_to_saved)
        self.append_wf_btn.setVisible(False)
        reset_btn = _btn("Descartar pasos", None, "Flat")
        reset_btn.setToolTip("Borra la lista de pasos anotados para empezar otro workflow "
                             "desde cero. No deshace nada en tus archivos.")
        reset_btn.clicked.connect(self.win.clear_steps)
        sb.addWidget(self.steps_lbl, 1)
        sb.addWidget(self.append_wf_btn)
        sb.addWidget(save_wf_btn)
        sb.addWidget(reset_btn)
        self.steps_bar.setVisible(False)
        col.addWidget(self.steps_bar)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("Card")
        add_shadow(self.action_bar)
        self._build_action_bar()
        col.addWidget(self.action_bar)

        self.refresh_file_list()

    def refresh_steps_bar(self):
        steps = self.win.session_steps
        self.steps_bar.setVisible(bool(steps))
        if not steps:
            return
        win = self.win
        saved = win.saved_upto == len(steps)
        pending = bool(win.saved_id) and len(steps) > win.saved_upto
        self.save_wf_btn.setVisible(not saved)
        self.save_wf_btn.setText("  Guardar como nuevo" if pending else "  Guardar como workflow")
        self.save_wf_btn.setObjectName("Secondary" if pending else "Primary")
        self.save_wf_btn.setIcon(ic.icon("bolt", ACCENT if pending else ICON_DARK, 17))
        self.save_wf_btn.style().unpolish(self.save_wf_btn)
        self.save_wf_btn.style().polish(self.save_wf_btn)
        self.append_wf_btn.setVisible(pending)
        if pending:
            name = win.saved_name if len(win.saved_name) <= 22 else win.saved_name[:21] + "…"
            self.append_wf_btn.setText(f"  Añadir a «{name}»")
            self.steps_lbl.setText(f"«{win.saved_name}» guardado  ·  pasos nuevos:  "
                                   + wf.summarize(steps[win.saved_upto:]))
        elif saved:
            self.steps_lbl.setText(f"✓ Guardado como «{win.saved_name}»  ·  " + wf.summarize(steps))
        else:
            self.steps_lbl.setText("Pasos aplicados:  " + wf.summarize(steps))

    def _handle_files_dropped(self, paths: list[str]):
        self.win.add_files_any(paths)

    def _build_sidebar(self):
        lay = QVBoxLayout(self.side)
        lay.setContentsMargins(16, 18, 16, 16)
        lay.setSpacing(4)

        header = QHBoxLayout()
        badge = QLabel()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignCenter)
        logo_pix = provecto_logo_pixmap(36)
        if logo_pix is not None:
            badge.setPixmap(logo_pix)
        else:
            badge.setObjectName("Badge")
            badge.setText("P")
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("PDF Manager")
        title.setObjectName("Header")
        subtitle = QLabel("Travel Agent Edition")
        subtitle.setObjectName("SubHeader")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addWidget(badge)
        header.addSpacing(10)
        header.addLayout(title_col)
        header.addStretch(1)
        lay.addLayout(header)
        lay.addSpacing(14)

        self.nav = QWidget()
        nav = QVBoxLayout(self.nav)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(4)
        w = self.win

        def group(text, items):
            g = QLabel(text.upper())
            g.setObjectName("Hint")
            g.setContentsMargins(6, 10, 0, 2)
            nav.addWidget(g)
            for label, icon_name, slot in items:
                b = _btn(label, icon_name, "Flat")
                b.setStyleSheet("text-align:left;padding:8px 10px;")
                b.clicked.connect(lambda _=False, s=slot: s())
                nav.addWidget(b)

        group("Combinar y dividir", [("Unir", "link", w.do_merge_standalone),
                                     ("Dividir", "scissors", w.open_split_view),
                                     ("Organizar páginas", "grid", w.open_organize_view)])
        group("Editar", [("Editor", "pencil", w.open_edit_view),
                         ("Metadatos", "info", w.open_metadata_view),
                         ("Ajuste de imagen", "droplet", w.do_ajuste_standalone)])
        group("Formato", [("Tamaño y márgenes", "resize", w.open_size_margins_view),
                          ("Varias por hoja", "nup", w.open_nup_view)])
        group("Más", [("Herramientas", "wrench", w.open_tools_view),
                      ("Workflows", "bolt", w.open_workflows_view)])
        lay.addWidget(self.nav)
        lay.addStretch(1)

    def _build_action_bar(self):
        lay = QHBoxLayout(self.action_bar)
        lay.setContentsMargins(14, 10, 14, 10)
        clear_btn = _btn("Limpiar todo", "trash", "Danger", icon_color=DANGER)
        clear_btn.clicked.connect(self.win.clear_all)
        save_btn = _btn("Guardar como…", "download")
        save_btn.clicked.connect(self.win.do_save_as_copy)
        self.merge_btn = _btn("Unir", "link", "Primary")
        self.merge_btn.clicked.connect(self.win.do_merge_standalone)
        lay.addWidget(clear_btn)
        lay.addStretch(1)
        lay.addWidget(save_btn)
        lay.addWidget(self.merge_btn)

    def _browse_files(self):
        exts = " ".join("*" + e for e in sorted(ptl.accepted_extensions()))
        photos = " ".join("*" + e for e in sorted(ptl.IMAGE_EXT))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegir PDFs o fotos", "",
            f"PDF y fotos ({exts});;PDF (*.pdf);;Fotos ({photos});;Todos los archivos (*.*)")
        self.win.add_files_any(paths)

    def _load_from_url(self):
        url = self.url_field.text().strip()
        if not url:
            return
        self.win.snack("Descargando PDF…", "info")

        def _dl():
            p = be.download_pdf_from_url(url)
            fn = url.split("/")[-1].split("?")[0] or "descargado.pdf"
            if not fn.lower().endswith(".pdf"):
                fn += ".pdf"
            if p:
                on_gui(lambda: self.win.add_file(p, fn))
            else:
                on_gui(lambda: self.win.snack("No se pudo descargar el PDF", "error"))

        run_bg(_dl)
        self.url_field.clear()

    def refresh_file_list(self):
        files = self.win.uploaded_files
        self.file_list.set_items(files)
        has_files = len(files) >= 1
        self.action_bar.setEnabled(has_files)
        self.nav.setEnabled(has_files)
        n = len(files)
        pages = sum(f.get("pages", 0) for f in files)
        self.hint.setText(
            f"{n} archivo{'s' if n != 1 else ''} · {pages} página{'s' if pages != 1 else ''} · "
            "arrastra las tarjetas para ordenarlas" if has_files
            else "Arrastra archivos o pega un enlace para empezar")
        self.merge_btn.setText(f"  Unir los {n} archivos" if n > 1 else "  Unir")
        self.merge_btn.setEnabled(n > 1)
        self.drop_area.setVisible(not has_files)
        self.file_list.setVisible(has_files)


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: ORGANIZE (grid de miniaturas con drag&drop nativo de Qt)
# ══════════════════════════════════════════════════════════════════════════
class PageGridWidget(QListWidget):
    """Igual que FileListWidget: el UserRole guarda solo un id() entero
    (robusto frente a la (de)serialización interna del drag&drop de Qt),
    resuelto contra self._id_map."""
    def __init__(self, on_rotate, on_delete, on_order_changed):
        super().__init__()
        self._on_rotate = on_rotate
        self._on_delete = on_delete
        self._on_order_changed = on_order_changed
        self._id_map: dict[int, dict] = {}

        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        # El drag&drop NATIVO de Qt/Windows para reordenar esta cuadrícula
        # resultó poco fiable (cursor "prohibido" incluso en casos simples).
        # En vez de depender de QDrag/OLE, se implementa un "arrastre" propio
        # solo con eventos de ratón: 100% bajo nuestro control, sin pasar por
        # el subsistema de drag nativo del sistema operativo.
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(10)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setIconSize(QSize(148, 196))
        self._drag_pg: dict | None = None
        self._drag_item: QListWidgetItem | None = None
        self._drag_start_pos = None
        self._dragging = False
        self._drag_preview: QLabel | None = None
        self._indicator: tuple | None = None   # (x, y0, y1) en coords. del viewport

    def set_items(self, pages: list[dict], render_fn):
        vbar = self.verticalScrollBar()
        scroll_val = vbar.value()
        self.clear()
        self._id_map = {id(pg): pg for pg in pages}
        for pg in pages:
            pix = render_fn(pg)
            item = QListWidgetItem(QIcon(pix), "")
            item.setData(Qt.UserRole, id(pg))
            item.setSizeHint(QSize(pix.width() + 6, pix.height() + 6))
            self.addItem(item)
        # clear() resetea el scroll al principio; lo restauramos tras volver
        # a poblar (rotar/eliminar una página no debe "saltar" la vista).
        vbar.setValue(scroll_val)
        QTimer.singleShot(0, lambda: vbar.setValue(scroll_val))

    def _resolve(self, item: QListWidgetItem):
        return self._id_map.get(item.data(Qt.UserRole))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            item = self.itemAt(e.pos())
            self._drag_pg = self._resolve(item) if item else None
            self._drag_item = item
            self._drag_start_pos = e.pos()
            self._dragging = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pg is not None and (e.buttons() & Qt.LeftButton):
            if not self._dragging:
                moved = (e.pos() - self._drag_start_pos).manhattanLength()
                if moved > QApplication.startDragDistance():
                    self._dragging = True
                    self.setCursor(Qt.ClosedHandCursor)
                    self._start_drag_preview(self._drag_item)
            if self._dragging:
                self._move_drag_preview(e.globalPosition().toPoint())
                self._indicator = self._indicator_line(e.pos())
                self.viewport().update()
                return  # mientras "arrastramos" a mano, no dejar que Qt gestione la selección
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._dragging and self._drag_pg is not None:
            self._drop_at(e.pos(), self._drag_pg)
            self.unsetCursor()
        self._end_drag_preview()
        self._dragging = False
        self._drag_pg = None
        self._indicator = None
        self.viewport().update()
        super().mouseReleaseEvent(e)

    # ── Miniatura flotante que sigue al cursor ──────────────────────────
    def _start_drag_preview(self, item: QListWidgetItem | None):
        if item is None:
            return
        pix = item.icon().pixmap(self.iconSize())
        ghost = QPixmap(pix.size())
        ghost.fill(Qt.transparent)
        p = QPainter(ghost)
        p.setOpacity(0.78)
        p.drawPixmap(0, 0, pix)
        p.end()

        self._drag_preview = QLabel(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self._drag_preview.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._drag_preview.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_preview.setPixmap(ghost)
        self._drag_preview.resize(ghost.size())
        self._drag_preview.show()

    def _move_drag_preview(self, global_pos: QPoint):
        if self._drag_preview:
            size = self._drag_preview.size()
            self._drag_preview.move(global_pos.x() - size.width() // 2,
                                     global_pos.y() - size.height() // 2)

    def _end_drag_preview(self):
        if self._drag_preview:
            self._drag_preview.hide()
            self._drag_preview.deleteLater()
            self._drag_preview = None

    # ── Barra vertical: dónde se insertará la página ────────────────────
    def _resolve_target(self, pos):
        """(item objetivo o None, insertar_después: bool) para esa posición."""
        item = self.itemAt(pos)
        if item is None:
            return None, True
        rect = self.visualItemRect(item)
        return item, pos.x() > rect.center().x()

    def _indicator_line(self, pos):
        item, after = self._resolve_target(pos)
        if item is None:
            if self.count() == 0:
                return None
            item = self.item(self.count() - 1)
            after = True
        rect = self.visualItemRect(item)
        x = rect.right() + 5 if after else rect.left() - 5
        return (x, rect.top(), rect.bottom())

    def viewportEvent(self, e):
        result = super().viewportEvent(e)
        if e.type() == QEvent.Type.Paint and self._dragging and self._indicator:
            x, y0, y1 = self._indicator
            painter = QPainter(self.viewport())
            pen = QPen(QColor(ACCENT))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawLine(x, y0, x, y1)
            painter.end()
        return result

    def _drop_at(self, pos, dragged_pg: dict):
        target_item, after = self._resolve_target(pos)
        order = self._current_order()
        order = [pg for pg in order if pg is not dragged_pg]

        if target_item is None:
            insert_at = len(order)
        else:
            target_pg = self._resolve(target_item)
            insert_at = order.index(target_pg) if target_pg in order else len(order)
            if after:
                insert_at += 1

        order.insert(insert_at, dragged_pg)
        self._on_order_changed(order)

    def keyPressEvent(self, e):
        item = self.currentItem()
        if item and e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self._on_delete(self._resolve(item))
        elif item and e.key() == Qt.Key_R:
            self._on_rotate(self._resolve(item))
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        item = self.itemAt(e.pos())
        if not item:
            return
        pg = self._resolve(item)
        menu = QMenu(self)
        rot_act = menu.addAction("⟳  Rotar 90°")
        del_act = menu.addAction("✕  Eliminar página")
        action = menu.exec(e.globalPos())
        if action == rot_act:
            self._on_rotate(pg)
        elif action == del_act:
            self._on_delete(pg)

    def _current_order(self):
        order = [self._resolve(self.item(r)) for r in range(self.count())]
        return [pg for pg in order if pg is not None]


class OrganizePage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.org_pages: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("Organize – Gestionar páginas", lambda: win.go_home()))

        hint = QLabel("Arrastra las páginas para reordenarlas · clic derecho o R/Supr para rotar/eliminar")
        hint.setObjectName("Hint")
        root.addWidget(hint)

        self.grid = PageGridWidget(
            on_rotate=self._rotate, on_delete=self._delete,
            on_order_changed=self._on_reordered,
        )
        root.addWidget(self.grid, 1)

        btn_row = QHBoxLayout()
        save_btn = _btn("Organize y guardar en Descargas", "download", "Primary")
        save_btn.clicked.connect(lambda: self._do_save(False))
        save_as_btn = QPushButton("Guardar como…")
        save_as_btn.clicked.connect(lambda: self._do_save(True))
        btn_row.addWidget(save_btn)
        btn_row.addWidget(save_as_btn)
        root.addLayout(btn_row)

    def populate(self):
        self.org_pages.clear()
        for fi, f in enumerate(self.win.uploaded_files):
            for pi in range(f["pages"]):
                self.org_pages.append({
                    "file_idx": fi, "page_idx": pi,
                    "label": be.label_for(fi, pi),
                    "color": FILE_COLORS[fi % len(FILE_COLORS)],
                    "rotation": 0,
                })
        self._rebuild_grid()

    def _rebuild_grid(self):
        def render(pg):
            path = self.win.uploaded_files[pg["file_idx"]]["path"]
            png = be.get_page_thumbnail_png(path, pg["page_idx"], rotation=pg["rotation"])
            return render_page_card(png, pg["label"], pg["color"])
        self.grid.set_items(self.org_pages, render)

    def _rotate(self, pg: dict):
        pg["rotation"] = (pg["rotation"] + 90) % 360
        self._rebuild_grid()

    def _delete(self, pg: dict):
        if pg in self.org_pages:
            self.org_pages.remove(pg)
        self._rebuild_grid()

    def _on_reordered(self, new_order: list[dict]):
        self.org_pages = new_order
        self._rebuild_grid()

    def _do_save(self, save_as: bool):
        if not self.org_pages:
            self.win.snack("No quedan páginas", "error"); return
        pages = [{
            "path": self.win.uploaded_files[pg["file_idx"]]["path"],
            "page_idx": pg["page_idx"],
            "rotation": pg["rotation"],
        } for pg in self.org_pages]
        first_fi = self.org_pages[0]["file_idx"]
        first_name = Path(self.win.uploaded_files[first_fi]["name"]).stem
        out_name = f"{first_name}_Organized.pdf"
        if save_as:
            dest, _ = QFileDialog.getSaveFileName(self, "Guardar como", out_name, "PDF (*.pdf)")
            if not dest:
                return
        else:
            dest = str(be.DOWNLOADS / out_name)
        be.organize_pdf(pages, dest)
        self.win.after_save(dest)


# ══════════════════════════════════════════════════════════════════════════
#  EDITOR VISUAL — clic sobre el texto para editarlo
# ══════════════════════════════════════════════════════════════════════════
class SpanRectItem(QGraphicsRectItem):
    """Zona clicable invisible sobre un fragmento de texto de la página."""
    def __init__(self, rect: QRectF, span: dict, page_idx: int, on_click, mode_provider=None):
        super().__init__(rect)
        self.span = span
        self.page_idx = page_idx
        self._on_click = on_click
        self._mode_provider = mode_provider
        self.kind = "edit"
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(Qt.NoPen))
        self._normal = QBrush(QColor(0, 0, 0, 0))
        self._hover_edit = QBrush(QColor(192, 130, 88, 70))
        self._hover_censor = QBrush(QColor(212, 114, 104, 120))
        self.setBrush(self._normal)

    def _mode(self) -> str:
        return self._mode_provider() if self._mode_provider else "edit"

    def hoverEnterEvent(self, e):
        censor = self._mode() == "censor"
        self.setBrush(self._hover_censor if censor else self._hover_edit)
        self.setCursor(Qt.CrossCursor if censor else Qt.IBeamCursor)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.setBrush(self._normal)
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if self._mode() == "censor":
            e.ignore()   # deja que la vista gestione el clic/arrastre de censura
            return
        self._on_click(self)
        super().mousePressEvent(e)


def _toggle_icon(name: str, size: int = 18) -> QIcon:
    """Icono claro normal y oscuro cuando el botón está marcado (fondo de acento)."""
    icon = QIcon()
    icon.addPixmap(ic.icon(name, TEXT, size).pixmap(size, size), QIcon.Normal, QIcon.Off)
    icon.addPixmap(ic.icon(name, ICON_DARK, size).pixmap(size, size), QIcon.Normal, QIcon.On)
    return icon


class _ToolBar(QFrame):
    """Barra de formato flotante. Absorbe los clics: si no, los de las zonas que
    no son botón llegarían a la página de fondo y cerrarían el editor."""
    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        e.accept()

    def mouseDoubleClickEvent(self, e):
        e.accept()


class _Swatch(QPushButton):
    """Círculo de color dibujado con suavizado (los bordes redondeados de la
    hoja de estilo salen pixelados a este tamaño)."""
    def __init__(self, hexc: str, selected: bool):
        super().__init__()
        self.hexc, self.selected = hexc, selected
        self.setFixedSize(30, 30)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        disc = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.hexc))
        p.drawEllipse(disc)
        if self.selected or self.underMouse():
            pen = QPen(QColor(ACCENT if self.selected else TEXT))
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(disc.adjusted(-3, -3, 3, 3))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(disc)


class _ToolPopup(QFrame):
    """Panel flotante que se cierra al hacer clic fuera: sirve de menú
    desplegable de la barra de formato (tamaño, fuente, color)."""
    def __init__(self, parent):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        # Fondo sólido: la transparencia de las ventanas emergentes se pinta a medias en Windows.
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(SURFACE_2))
        self.setPalette(pal)
        self.setObjectName("ToolPopup")
        self.setStyleSheet(
            f"#ToolPopup {{ background:{SURFACE_2}; border:1px solid {BORDER_STRONG}; border-radius:4px; }}")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(8, 8, 8, 8)
        self.lay.setSpacing(6)


def _popup_list(width: int, height: int) -> QListWidget:
    lst = QListWidget()
    lst.setFixedSize(width, height)
    lst.setFocusPolicy(Qt.NoFocus)
    lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    lst.setStyleSheet(
        f"QListWidget {{ background:transparent; border:none; color:{TEXT}; outline:0; }}"
        f"QScrollBar:vertical {{ background:transparent; width:8px; margin:2px 0; border:none; }}"
        f"QScrollBar::handle:vertical {{ background:rgba(243,241,228,0.28); border-radius:4px; min-height:24px; }}"
        f"QScrollBar::handle:vertical:hover {{ background:rgba(243,241,228,0.45); }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}"
        f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}"
        f"QListWidget::item {{ padding:5px 8px; border-radius:6px; color:{TEXT}; }}"
        f"QListWidget::item:hover {{ background:rgba(243,241,228,0.10); }}"
        f"QListWidget::item:selected {{ background:{ACCENT}; color:{ICON_DARK}; }}")
    return lst


class _VirtualItem:
    """Lo que el editor necesita de un elemento que aún no existe en el PDF (texto libre nuevo)."""
    kind = "new"

    def __init__(self, page_idx: int, rect: QRectF, span: dict):
        self.page_idx, self._rect, self.span = page_idx, rect, span

    def rect(self) -> QRectF:
        return self._rect


_PROP_FONT = 0x100001      # propiedad de formato: fuente original del PDF
_PROP_FAMILY = 0x100002    # propiedad de formato: el usuario eligió otra fuente
_PROP_SIZE = 0x100003      # propiedad de formato: tamaño exacto en pt (el píxel del editor lo redondea)


class _HFBlock(QGraphicsRectItem):
    """Texto de la página que se puede marcar con un clic como cabecera o pie."""
    COLORS = {"header": QColor(80, 140, 210, 120), "footer": QColor(90, 170, 110, 120)}

    def __init__(self, rect: QRectF, bbox: tuple, on_click):
        super().__init__(rect)
        self.bbox, self._on_click, self.role = bbox, on_click, None
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self._paint()

    def set_role(self, role):
        self.role = role
        self._paint()

    def _paint(self, hover=False):
        self.setPen(QPen(QColor(192, 130, 88, 200 if hover else 90), 1))
        self.setBrush(QBrush(self.COLORS.get(self.role, QColor(192, 130, 88, 60 if hover else 0))))

    def hoverEnterEvent(self, e):
        self._paint(True)

    def hoverLeaveEvent(self, e):
        self._paint(False)

    def mousePressEvent(self, e):
        self._on_click(self)


class InsertPageDialog(QDialog):
    """¿Qué se inserta aquí? Una página en blanco (con o sin la cabecera y el pie detectados, con vista previa) o
    las páginas de otro PDF."""

    def __init__(self, view, doc, at: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insertar página")
        self.view, self.doc, self.at = view, doc, at
        self.choice = None                    # "blank" | "pdf"
        self.settings = None                  # ajustes de cabecera/pie para la hoja en blanco (None = detección automática)
        self.pdf_path = None
        self._cache = {}
        self.has_hf = be.has_header_footer(doc, at, view.hf)
        self.resize(640, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(self._title("¿Qué quieres insertar aquí?"))
        row = QHBoxLayout()
        self.blank_rb = QRadioButton("Una página en blanco")
        self.pdf_rb = QRadioButton("Páginas de otro documento (PDF)…")
        self.blank_rb.setChecked(True)
        row.addWidget(self.blank_rb)
        row.addWidget(self.pdf_rb)
        row.addStretch(1)
        lay.addLayout(row)

        self.hf_box = QWidget()
        hl = QHBoxLayout(self.hf_box)
        hl.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        info = QLabel("Se ha detectado cabecera, pie o fondo de página en este documento." if view.hf is None
                      else "Este documento tiene la cabecera y el pie que configuraste.")
        info.setWordWrap(True)
        left.addWidget(info)
        self.keep_rb = QRadioButton("Mantener cabecera, pie y fondo")
        self.empty_rb = QRadioButton("Hoja totalmente en blanco")
        self.conf_rb = QRadioButton("Configurar cabecera y pie…")
        self.keep_rb.setChecked(True)
        for rb in (self.keep_rb, self.empty_rb, self.conf_rb):
            left.addWidget(rb)
            rb.toggled.connect(self._on_option)
        left.addStretch(1)
        hl.addLayout(left, 1)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(250, 330)
        self.preview.setStyleSheet("background:#FFFFFF; border:1px solid %s;" % BORDER_STRONG)
        hl.addWidget(self.preview)
        lay.addWidget(self.hf_box, 1)
        self.hf_box.setVisible(self.has_hf)

        self.pdf_lbl = QLabel("")
        self.pdf_lbl.setObjectName("Hint")
        lay.addWidget(self.pdf_lbl)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = _btn("Cancelar", None, "Secondary")
        self.ok_btn = _btn("Insertar", "plus", "Primary")
        cancel.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(self.ok_btn)
        lay.addLayout(btns)
        self.blank_rb.toggled.connect(self._on_kind)
        self._on_kind()
        self._refresh_preview()

    @staticmethod
    def _title(text):
        l = QLabel(text)
        l.setObjectName("SectionTitle")
        return l

    def _on_kind(self):
        blank = self.blank_rb.isChecked()
        self.hf_box.setVisible(blank and self.has_hf)
        self.pdf_lbl.setText("" if blank else "Al pulsar «Insertar» elegirás el PDF cuyas páginas se añaden aquí.")

    def _current_settings(self):
        if self.empty_rb.isChecked():
            return be.BLANK_HF
        return self.view.hf                      # None = detección automática

    def _on_option(self, checked):
        if not checked:
            return
        if self.conf_rb.isChecked():
            if self.view.ask_header_footer(max(0, min(self.at - 1, len(self.doc) - 1))):
                self._cache.clear()
            self.keep_rb.setChecked(True)
            return
        self._refresh_preview()

    def _refresh_preview(self):
        key = "empty" if self.empty_rb.isChecked() else "keep"
        if key not in self._cache:
            self._cache[key] = be.preview_inserted_page(self.doc, self.at, self._current_settings(), 250)
        png = self._cache[key]
        pm = QPixmap()
        if png:
            pm.loadFromData(png)
            self.preview.setPixmap(pm)
        else:
            self.preview.setText("Sin vista previa")

    def _accept(self):
        if self.pdf_rb.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "Elige el PDF a insertar", str(Path.home()),
                                                  "PDF (*.pdf);;Todos los archivos (*.*)")
            if not path:
                return
            self.choice, self.pdf_path = "pdf", path
        else:
            self.choice = "blank"
            self.settings = self._current_settings() if self.has_hf else self.view.hf
        self.accept()


class ClickIconDialog(QDialog):
    """Elegir un icono de «haz clic aquí» para poner sobre el enlace de una imagen."""

    def __init__(self, parent=None, live=None):
        super().__init__(parent)
        self.live = live
        self.setWindowTitle("Cambiar icono" if live else "Icono de «clic aquí»")
        self.kind = None
        lay = QVBoxLayout(self)
        lbl = QLabel("Pulsa un icono para cambiarlo al momento; puedes probar varios." if live else
                     "El enlace está sobre una imagen. ¿Quieres insertar alguno de estos iconos para indicar a quien "
                     "lea el PDF que puede hacer clic? Después podrás moverlo y girarlo un poco para que no tape nada.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        grid = QGridLayout()
        entries = ci.builtin_kinds() + [(k, "Tu imagen") for k in ci.list_custom()]
        for i, (key, label) in enumerate(entries):
            pm = QPixmap(84, 84)
            pm.fill(QColor("#FFFFFF"))
            pa = QPainter(pm)
            pa.setRenderHint(QPainter.SmoothPixmapTransform)
            pa.drawImage(QRectF(0, 0, 84, 84), ci.render_image(key, 0, 168))
            pa.end()
            b = QPushButton()
            b.setIcon(QIcon(pm))
            b.setIconSize(QSize(84, 84))
            b.setFixedSize(100, 100)
            b.setToolTip(label)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            grid.addWidget(b, i // 4, i % 4)
        lay.addLayout(grid)
        row = QHBoxLayout()
        own = _btn("Usar mi propia imagen…", "image", "Secondary")
        own.setToolTip("Importa un PNG, JPG o SVG para usarlo como icono (queda guardado para otros documentos)")
        own.clicked.connect(self._own)
        row.addWidget(own)
        row.addStretch(1)
        no = _btn("Cerrar" if live else "No, gracias", None, "Secondary")
        no.clicked.connect(self.reject)
        row.addWidget(no)
        lay.addLayout(row)

    def _own(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elige las imágenes de tus iconos", str(Path.home() / "Pictures"),
            "Imágenes e ilustraciones (*.png *.jpg *.jpeg *.svg *.ai *.eps *.pdf *.webp *.gif *.bmp);;Todos (*.*)")
        keys, errors = [], []
        for pth in paths:
            key, err = ci.import_custom(pth)
            if key:
                keys.append(key)
            else:
                errors.append(f"{Path(pth).name}: {err}")
        if errors:
            QMessageBox.warning(self, "Icono", "\n".join(errors))
        if keys:
            self._pick(keys[0])                 # el primero se usa ya; los demás quedan guardados en la lista

    def _pick(self, key):
        self.kind = key
        if self.live is not None:
            self.live(key)                 # modo «jugar»: se aplica al momento y la ventana sigue abierta
            return
        self.accept()


class HeaderFooterDialog(QDialog):
    """Pregunta qué es cabecera y pie de página (clic sobre el texto) y cómo
    repetirlos en las páginas nuevas: igual en todas o distinto en pares e
    impares, y si se sigue la numeración."""
    def __init__(self, doc, page_idx: int, settings, parent=None, intro: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Cabecera y pie de página")
        self.doc, self.page_idx, self.settings = doc, page_idx, settings
        auto_h, auto_f = be.auto_header_footer(doc, page_idx)
        s = {**be.DEFAULT_HF, **(settings or {})}
        self.resize(900, 660)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)

        # ── Vista previa con los textos clicables ────────────────────────
        page = doc[page_idx]
        zoom = min(1.3, 560 / page.rect.height)
        png = be.render_doc_page_png(doc, page_idx, zoom=zoom)
        pm = QPixmap()
        if png:
            pm.loadFromData(png)
        scene = QGraphicsScene(self)
        scene.addPixmap(pm)
        self.items: list[_HFBlock] = []
        for b in page.get_text("blocks"):
            if b[6] != 0 or not b[4].strip():
                continue
            it = _HFBlock(QRectF(b[0] * zoom, b[1] * zoom, (b[2] - b[0]) * zoom, (b[3] - b[1]) * zoom),
                          tuple(b[:4]), self._clicked)
            if settings is not None:
                it.role = ("header" if any(abs(b[1] - h[1]) < 1.5 and abs(b[0] - h[0]) < 1.5 for h in s["header_boxes"])
                           else "footer" if any(abs(b[1] - f[1]) < 1.5 and abs(b[0] - f[0]) < 1.5 for f in s["footer_boxes"])
                           else None)
            else:
                it.role = ("header" if auto_h and b[3] <= auto_h + 2
                           else "footer" if auto_f and b[1] >= auto_f - 2 else None)
            it.set_role(it.role)
            scene.addItem(it)
            self.items.append(it)
        scene.setSceneRect(0, 0, pm.width(), pm.height())
        view = QGraphicsView(scene)
        view.setStyleSheet(f"background:{SURFACE}; border:none; border-radius:10px;")
        view.setFixedSize(pm.width() + 4, min(pm.height() + 4, 600))
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(view)

        # ── Opciones ─────────────────────────────────────────────────────
        side = QVBoxLayout()
        side.setSpacing(10)
        title = QLabel("Cabecera y pie de página")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        side.addWidget(title)
        text = intro or ("Marca con un clic los textos que son cabecera o pie: no se moverán al "
                         "repartir el texto entre páginas y se podrán repetir en las páginas nuevas.")
        info = QLabel(text)
        info.setObjectName("Hint")
        info.setWordWrap(True)
        side.addWidget(info)

        side.addWidget(QLabel("Cada clic marca el texto como:"))
        self.role_header = QRadioButton("Cabecera (azul)")
        self.role_footer = QRadioButton("Pie de página (verde)")
        self.role_header.setChecked(True)
        side.addWidget(self.role_header)
        side.addWidget(self.role_footer)
        self.rep_header = QCheckBox("Repetir la cabecera en las páginas nuevas")
        self.rep_header.setChecked(s["repeat_header"])
        self.rep_footer = QCheckBox("Repetir el pie en las páginas nuevas")
        self.rep_footer.setChecked(s["repeat_footer"])
        side.addSpacing(6)
        side.addWidget(self.rep_header)
        side.addWidget(self.rep_footer)

        side.addSpacing(6)
        side.addWidget(QLabel("¿Son iguales en todas las páginas?"))
        self.same_all = QRadioButton("Iguales en todas")
        self.parity = QRadioButton("Distintos en pares e impares")
        (self.parity if s["parity"] else self.same_all).setChecked(True)
        par_hint = QLabel("La página nueva copia la de dos antes, o la anterior si no hay.")
        par_hint.setObjectName("Hint")
        par_hint.setWordWrap(True)
        side.addWidget(self.same_all)
        side.addWidget(self.parity)
        side.addWidget(par_hint)

        side.addSpacing(6)
        self.numbering = QCheckBox("Seguir la numeración de página")
        self.numbering.setChecked(s["numbering"])
        self.num_info = QLabel()
        self.num_info.setObjectName("Hint")
        self.num_info.setWordWrap(True)
        side.addWidget(self.numbering)
        side.addWidget(self.num_info)
        side.addStretch(1)

        btns = QHBoxLayout()
        cancel = _btn("Cancelar", None, "Secondary", icon_color=TEXT)
        ok = _btn("Continuar", "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        side.addLayout(btns)
        wrap = QWidget()
        wrap.setLayout(side)
        wrap.setFixedWidth(320)
        root.addWidget(wrap)
        self._refresh_numbers()

    def _clicked(self, item: "_HFBlock"):
        role = "header" if self.role_header.isChecked() else "footer"
        item.set_role(None if item.role == role else role)
        self._refresh_numbers()

    def _bounds(self):
        hb = max((i.bbox[3] for i in self.items if i.role == "header"), default=None)
        fb = min((i.bbox[1] for i in self.items if i.role == "footer"), default=None)
        return hb, fb

    def _refresh_numbers(self):
        hb, fb = self._bounds()
        found = be.find_page_numbers(self.doc, self.page_idx, hb, fb)
        self.num_info.setText(
            "Número de página detectado: " + ", ".join(f"«{t}»" for t in found) +
            ". En la página nueva subirá solo."
            if found else "No se ha detectado ningún número de página en lo marcado.")

    def _accept(self):
        self.settings = {
            "header_boxes": [i.bbox for i in self.items if i.role == "header"],
            "footer_boxes": [i.bbox for i in self.items if i.role == "footer"],
            "repeat_header": self.rep_header.isChecked(),
            "repeat_footer": self.rep_footer.isChecked(),
            "parity": self.parity.isChecked(),
            "numbering": self.numbering.isChecked(),
            "ref_h": self.doc[self.page_idx].rect.height,
        }
        self.accept()


def fitz_rect(x0, y0, x1, y1):
    return (x0, y0, x1, y1)


class CopyDialog(QDialog):
    """Texto de la zona elegida, con párrafos, columnas y tablas respetados. Se puede editar antes de copiar."""
    def __init__(self, parent, blocks: list, note: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Copiar texto")
        self.resize(640, 520)
        self.blocks = blocks
        self.xlsx_path = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        title = QLabel("Texto de la zona")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.summary = QLabel("")
        self.summary.setObjectName("Hint")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        if note:
            n = QLabel(note)
            n.setObjectName("Hint")
            n.setWordWrap(True)
            lay.addWidget(n)
        self.reflow = QCheckBox("Unir las líneas de cada párrafo (quita los saltos de línea del escaneo o de la maquetación)")
        self.reflow.setChecked(True)
        self.reflow.toggled.connect(self._fill)
        lay.addWidget(self.reflow)
        self.edit = QTextEdit()
        self.edit.setAcceptRichText(False)
        self.edit.setLineWrapMode(QTextEdit.WidgetWidth)
        lay.addWidget(self.edit, 1)
        self.hint = QLabel("")
        self.hint.setObjectName("Hint")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        btns = QHBoxLayout()
        self.xlsx_btn = _btn("Tablas a Excel…", "download", "Secondary", icon_color=TEXT)
        self.xlsx_btn.clicked.connect(self._export)
        btns.addWidget(self.xlsx_btn)
        btns.addStretch(1)
        close = _btn("Cerrar", None, "Secondary", icon_color=TEXT)
        self.copy_btn = _btn("Copiar", "copy", "Primary", icon_color=ICON_DARK)
        close.clicked.connect(self.accept)
        self.copy_btn.clicked.connect(self._copy)
        btns.addWidget(close)
        btns.addWidget(self.copy_btn)
        lay.addLayout(btns)
        self._fill()

    def _fill(self, *_):
        text = lt.blocks_to_text(self.blocks, self.reflow.isChecked())
        self.edit.setPlainText(text)
        n_t = sum(1 for b in self.blocks if b.kind == "table")
        n_p = sum(len(b.paragraphs) for b in self.blocks if b.kind == "text")
        n_r = sum(1 for b in self.blocks if b.kind == "row")
        parts = []
        if n_p:
            parts.append(f"{n_p} párrafo{'s' if n_p != 1 else ''}")
        if n_t:
            parts.append(f"{n_t} tabla{'s' if n_t != 1 else ''}")
        if n_r:
            parts.append(f"{n_r} fila{'s' if n_r != 1 else ''} suelta{'s' if n_r != 1 else ''}")
        self.summary.setText("Se ha reconocido: " + (", ".join(parts) or "nada de texto") + ".")
        self.xlsx_btn.setVisible(n_t > 0)
        self.hint.setText("Las celdas de tablas y filas van separadas por tabuladores: al pegarlo en Excel o en una tabla "
                          "de Word cada una cae en su columna." if (n_t or n_r) else "")
        self.copy_btn.setEnabled(bool(text.strip()))

    def _copy(self):
        QApplication.clipboard().setText(self.edit.toPlainText())
        self.hint.setText("✓ Copiado al portapapeles.")

    def _export(self):
        tables = [b.rows for b in self.blocks if b.kind == "table"]
        dest, _ = QFileDialog.getSaveFileName(self, "Guardar tablas", str(Path.home() / "Downloads" / "tablas.xlsx"),
                                              "Excel (*.xlsx)")
        if not dest:
            return
        try:
            ptl.tables_to_xlsx(tables, dest)
            self.xlsx_path = dest
            self.hint.setText(f"✓ Guardado: {Path(dest).name} ({len(tables)} hoja{'s' if len(tables) != 1 else ''}).")
        except Exception as e:
            self.hint.setText(f"No se pudo guardar: {e}")


class NoteDialog(QDialog):
    def __init__(self, parent, text: str = "", author: str = "", existing: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Editar nota" if existing else "Nueva nota")
        self.setMinimumWidth(420)
        self.remove = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("Editar nota" if existing else "Nueva nota")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        if author:
            a = QLabel(f"Autor: {author}")
            a.setObjectName("Hint")
            lay.addWidget(a)
        self.edit = QTextEdit()
        self.edit.setAcceptRichText(False)
        self.edit.setPlainText(text)
        self.edit.setMinimumHeight(120)
        lay.addWidget(self.edit)
        btns = QHBoxLayout()
        if existing:
            rm = _btn("Eliminar nota", "trash", "Flat", icon_color=DANGER)
            rm.clicked.connect(self._remove)
            btns.addWidget(rm)
        btns.addStretch(1)
        cancel = _btn("Cancelar", None, "Secondary", icon_color=TEXT)
        ok = _btn("Guardar", "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.edit.setFocus()

    def _remove(self):
        self.remove = True
        self.accept()


class _FieldEditor(QTextEdit):
    """Caja para escribir en un campo de formulario, justo encima del campo. Intro (o Ctrl+Intro si el campo es
    de varias líneas) o salir de la caja confirma; Esc cancela."""
    committed = Signal(str)
    cancelled = Signal()
    tabbed = Signal(bool)                 # Tab (True) o Mayús+Tab (False): confirmar y pasar al campo siguiente o anterior

    def __init__(self, parent, text: str, multiline: bool, font_px: float):
        super().__init__(parent)
        self._multi, self._done = multiline, False
        self.setAcceptRichText(False)
        self.setPlainText(text)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff if not multiline else Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth if multiline else QTextEdit.NoWrap)
        f = self.font()
        f.setPixelSize(max(9, int(font_px)))
        self.setFont(f)
        self.document().setDocumentMargin(0)
        # sin caja ni fondo: se escribe directamente sobre el campo y solo se ve el cursor parpadeante
        self.setStyleSheet("QTextEdit { background:transparent; color:#000000; border:none; padding:0; }")
        self.setCursorWidth(max(2, round(font_px * 0.07)))
        pal = self.palette()
        pal.setColor(pal.ColorRole.Text, QColor("#000000"))
        self.setPalette(pal)

    def _finish(self, ok: bool):
        if self._done:
            return
        self._done = True
        (self.committed.emit(self.toPlainText()) if ok else self.cancelled.emit())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._finish(False)
            return
        if e.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            fwd = e.key() == Qt.Key_Tab and not (e.modifiers() & Qt.ShiftModifier)
            self._finish(True)
            self.tabbed.emit(fwd)
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and (not self._multi or e.modifiers() & Qt.ControlModifier):
            self._finish(True)
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        # Cambiar de ventana o abrir un menú no debe cerrar la caja; hacer clic en otro sitio, sí.
        if e.reason() in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason):
            return
        self._finish(True)


class FieldDialog(QDialog):
    """Datos de un campo de formulario nuevo."""
    TYPES = (("text", "Texto (una línea)"), ("multiline", "Texto (varias líneas)"), ("checkbox", "Casilla"),
             ("combo", "Lista desplegable"), ("list", "Lista de selección"),
             ("radio", "Botones de opción (elegir uno)"))

    def __init__(self, parent, default_name: str):
        super().__init__(parent)
        self.setWindowTitle("Nuevo campo")
        self.setMinimumWidth(420)
        self.spec = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("Nuevo campo de formulario")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.kind = QComboBox()
        for key, label in self.TYPES:
            self.kind.addItem(label, key)
        lay.addWidget(QLabel("Tipo de campo"))
        lay.addWidget(self.kind)
        lay.addWidget(QLabel("Nombre del campo (así se identifica al exportar los datos)"))
        self.name = QLineEdit(default_name)
        lay.addWidget(self.name)
        self.opts_lbl = QLabel("Opciones (una por línea)")
        self.opts = QTextEdit()
        self.opts.setAcceptRichText(False)
        self.opts.setFixedHeight(90)
        self.opts.setPlainText("Opción 1\nOpción 2\nOpción 3")
        lay.addWidget(self.opts_lbl)
        lay.addWidget(self.opts)
        self.val_lbl = QLabel("Valor inicial (opcional)")
        self.value = QLineEdit()
        lay.addWidget(self.val_lbl)
        lay.addWidget(self.value)
        self.kind.currentIndexChanged.connect(self._sync)
        self._sync()
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = _btn("Cancelar", None, "Secondary", icon_color=TEXT)
        ok = _btn("Crear campo", "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

    def _sync(self):
        k = self.kind.currentData()
        lists = k in ("combo", "list", "radio")
        self.opts_lbl.setVisible(lists)
        self.opts.setVisible(lists)
        self.opts_lbl.setText("Opciones (una por línea, mínimo 2)" if k == "radio" else "Opciones (una por línea)")
        self.val_lbl.setVisible(k not in ("checkbox", "radio"))

    def _ok(self):
        k = self.kind.currentData()
        self.spec = {"kind": k, "name": self.name.text().strip() or "campo", "value": self.value.text(),
                     "choices": [l.strip() for l in self.opts.toPlainText().splitlines() if l.strip()]}
        self.accept()


# Colores para el texto de un enlace; el primero es el azul de hipervínculo habitual
LINK_COLORS = (("Azul de hipervínculo", (5 / 255, 99 / 255, 193 / 255)), ("Azul oscuro", (0.1, 0.2, 0.6)),
               ("Morado (visitado)", (0.4, 0.2, 0.6)), ("Rojo", (0.8, 0.1, 0.1)), ("Verde", (0.1, 0.5, 0.2)),
               ("Naranja", (0.9, 0.45, 0.05)), ("Negro", (0.1, 0.1, 0.1)))


class LinkDialog(QDialog):
    """Elegir adónde lleva un enlace: una web, una página del documento o un correo."""
    def __init__(self, parent, n_pages: int, existing: dict | None = None, n_zones: int = 1,
                 allow_underline: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Editar enlace" if existing else "Nuevo enlace")
        self.setMinimumWidth(460)
        self.result_dest = None
        self.remove = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("Editar enlace" if existing else "Nuevo enlace")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.r_web = QRadioButton("Dirección web (o correo electrónico)")
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://ejemplo.com  ·  nombre@correo.com")
        self.r_page = QRadioButton("Una página de este documento")
        self.page = QSpinBox()
        self.page.setRange(1, max(n_pages, 1))
        self.page.setPrefix("Página ")
        self.page.setSuffix(f" de {n_pages}")
        lay.addWidget(self.r_web)
        lay.addWidget(self.url)
        lay.addWidget(self.r_page)
        lay.addWidget(self.page)
        self.link_color = LINK_COLORS[0][1]
        style_row = QHBoxLayout()
        self.underline_cb = QCheckBox("Poner el texto en azul y subrayarlo, como un hipervínculo")
        self.underline_cb.setChecked(existing is None and allow_underline)
        self.color_btn = QPushButton()
        self.color_btn.setObjectName("Secondary")
        self.color_btn.setToolTip("Color del texto y del subrayado")
        self.color_btn.clicked.connect(self._color_menu)
        self._paint_color_btn()
        style_row.addWidget(self.underline_cb, 1)
        style_row.addWidget(self.color_btn)
        style_row.setContentsMargins(0, 0, 0, 0)
        self.style_box = QWidget()
        self.style_box.setLayout(style_row)
        self.style_box.setVisible(existing is None and allow_underline)
        lay.addWidget(self.style_box)
        self.note = QLabel("Este enlace ocupa %d zonas (líneas): se editan y se quitan juntas." % n_zones
                           if n_zones > 1 else "")
        self.note.setObjectName("Hint")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        if existing and existing.get("kind") == 1:             # LINK_GOTO
            self.r_page.setChecked(True)
            self.page.setValue(existing.get("page", 0) + 1)
        else:
            self.r_web.setChecked(True)
            self.url.setText((existing or {}).get("uri", "") or "")
        self.url.textChanged.connect(lambda: self.r_web.setChecked(True))
        self.page.valueChanged.connect(lambda: self.r_page.setChecked(True))
        btns = QHBoxLayout()
        if existing:
            rm = _btn("Quitar enlace", "trash", "Flat", icon_color=DANGER)
            rm.clicked.connect(self._remove)
            btns.addWidget(rm)
        btns.addStretch(1)
        cancel = _btn("Cancelar", None, "Secondary", icon_color=TEXT)
        ok = _btn("Guardar enlace", "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.url.setFocus()

    def _paint_color_btn(self):
        pm = QPixmap(16, 16)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.5))
        pa.setBrush(QColor(*(int(c * 255) for c in self.link_color)))
        pa.drawEllipse(1, 1, 14, 14)
        pa.end()
        self.color_btn.setIcon(QIcon(pm))
        self.color_btn.setText("  Color")

    def _color_menu(self):
        m = QMenu(self)
        for name, rgb in LINK_COLORS:
            m.addAction(SelectionBar._swatch(rgb), name, lambda c=rgb: self._set_color(c))
        m.addSeparator()

        def other():
            c = QColorDialog.getColor(QColor(*(int(v * 255) for v in self.link_color)), self, "Color del enlace")
            if c.isValid():
                self._set_color((c.redF(), c.greenF(), c.blueF()))
        m.addAction("Otro color…", other)
        m.exec(self.color_btn.mapToGlobal(self.color_btn.rect().bottomLeft()))

    def _set_color(self, rgb):
        self.link_color = tuple(rgb)
        self._paint_color_btn()

    def _remove(self):
        self.remove = True
        self.accept()

    def _ok(self):
        if self.r_page.isChecked():
            self.result_dest = {"kind": "goto", "page": self.page.value() - 1}
            self.accept()
            return
        uri = at.normalize_uri(self.url.text())
        if not uri:
            self.note.setText("Esa dirección no es válida. Usa una web (https://…), un correo o un teléfono; "
                              "por seguridad no se admiten otros tipos de enlace.")
            return
        self.result_dest = {"kind": "uri", "uri": uri}
        self.accept()


def color_menu(parent, view, fill: bool, apply):
    """Menú de colores: paleta, «Otro color…» y cuentagotas. `apply` recibe un nombre, una tupla (r,g,b) o "" (sin relleno)."""
    m = QMenu(parent)
    sw = SelectionBar._swatch
    if fill:
        m.addAction(sw(None), "Sin relleno", lambda: apply(""))
    for name, rgb in at.SHAPE_COLORS.items():
        m.addAction(sw(rgb), name.capitalize(), lambda n=name: apply(n))
    m.addSeparator()

    def other():
        c = QColorDialog.getColor(QColor(200, 60, 60), parent, "Elige un color")
        if c.isValid():
            apply((c.redF(), c.greenF(), c.blueF()))
    m.addAction("Otro color…", other)
    m.addAction("Cuentagotas (tomar de la página)", lambda: view.start_eyedropper(apply))
    return m


OPACITIES = ((1.0, "100 %"), (0.75, "75 %"), (0.5, "50 %"), (0.25, "25 %"))


def opacity_menu(parent, apply, has_fill: bool = True, current=None):
    """Opacidad: total (trazo y relleno a la vez) y, opcionalmente, solo del trazo o solo del relleno.
    `apply(parte, valor)` con parte = "total" | "stroke" | "fill"."""
    m = QMenu(parent)
    tot = m.addMenu("Opacidad total")
    for v, label in OPACITIES:
        a = tot.addAction(label, lambda x=v: apply("total", x))
        a.setCheckable(True)
        a.setChecked(bool(current) and abs(current[0] - v) < 0.01 and abs(current[1] - v) < 0.01)
    st = m.addMenu("Solo el trazo (opcional)")
    for v, label in OPACITIES:
        st.addAction(label, lambda x=v: apply("stroke", x))
    if has_fill:
        fl = m.addMenu("Solo el relleno (opcional)")
        for v, label in OPACITIES:
            fl.addAction(label, lambda x=v: apply("fill", x))
    return m


class SelectionBar(QFrame):
    """Opciones sobre la forma seleccionada: color del borde, relleno, grosor, duplicar y borrar."""

    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self.setObjectName("SelBar")
        self.setStyleSheet(
            "QFrame#SelBar { background:%s; border:1px solid %s; border-radius:8px; }"
            "QPushButton { background:transparent; border:none; padding:4px 6px; border-radius:6px; color:%s; font-size:12px; }"
            "QPushButton:hover { background:%s; }" % (SURFACE, BORDER_STRONG, TEXT, SURFACE_3))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        self.stroke_btn = QPushButton(); self.stroke_btn.setToolTip("Color del borde")
        self.fill_btn = QPushButton(); self.fill_btn.setToolTip("Color de relleno")
        self.width_btn = QPushButton(); self.width_btn.setToolTip("Grosor")
        self.op_btn = QPushButton(); self.op_btn.setToolTip("Opacidad del relleno")
        self.head_btn = QPushButton(); self.head_btn.setToolTip("Forma de la punta de la flecha")
        self.dup_btn = _btn("", "copy", None, icon_color=TEXT, size=16); self.dup_btn.setToolTip("Duplicar (Ctrl+D)")
        self.del_btn = _btn("", "trash", None, icon_color=TEXT, size=16); self.del_btn.setToolTip("Borrar (Supr)")
        for b in (self.stroke_btn, self.fill_btn, self.op_btn, self.width_btn, self.head_btn, self.dup_btn, self.del_btn):
            lay.addWidget(b)
            b.setCursor(Qt.PointingHandCursor)
        self.stroke_btn.clicked.connect(lambda: self._color_menu(self.stroke_btn, False))
        self.fill_btn.clicked.connect(lambda: self._color_menu(self.fill_btn, True))
        self.width_btn.clicked.connect(self._width_menu)
        self.op_btn.clicked.connect(self._opacity_menu)
        self.head_btn.clicked.connect(self._head_menu)
        self.dup_btn.clicked.connect(lambda: self.view.duplicate_selection())
        self.del_btn.clicked.connect(lambda: self.view.delete_selection())
        self.hide()

    @staticmethod
    def _swatch(rgb, ring=True):
        pm = QPixmap(18, 18)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.5))
        pa.setBrush(QColor(*(int(c * 255) for c in rgb)) if rgb else QBrush(Qt.NoBrush))
        pa.drawEllipse(2, 2, 14, 14)
        if not rgb:
            pa.setPen(QPen(QColor("#E05050"), 1.5))
            pa.drawLine(4, 14, 14, 4)
        pa.end()
        return QIcon(pm)

    def _color_menu(self, anchor, fill: bool):
        ap = (lambda v: self.view.restyle_selection(fill=v)) if fill else (lambda v: self.view.restyle_selection(color=v))
        m = color_menu(self, self.view, fill, ap)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _opacity_menu(self):
        d = (self.view._ss_sel or {}).get("desc", {})
        s = d.get("opacity", 1.0)
        cur = (s, d.get("fill_opacity", s))

        def ap(part, v):
            kw = {"total": "opacity", "stroke": "stroke_op", "fill": "fill_op"}[part]
            self.view.restyle_selection(**{kw: v})
        m = opacity_menu(self, ap, has_fill=d.get("kind") in ("rect", "ellipse", "poly") and bool(d.get("fill")),
                         current=cur)
        m.exec(self.op_btn.mapToGlobal(self.op_btn.rect().bottomLeft()))

    def _head_menu(self):
        m = QMenu(self)
        for name, label in at.HEAD_LABELS:
            m.addAction(label, lambda n=name: self.view.restyle_selection(head=n))
        m.exec(self.head_btn.mapToGlobal(self.head_btn.rect().bottomLeft()))

    def _width_menu(self):
        m = QMenu(self)
        for w, label in ((1.0, "Fino"), (2.0, "Normal"), (4.0, "Grueso"), (7.0, "Muy grueso")):
            m.addAction(label, lambda v=w: self.view.restyle_selection(width=v))
        m.exec(self.width_btn.mapToGlobal(self.width_btn.rect().bottomLeft()))

    def refresh(self, d: dict):
        self.stroke_btn.setIcon(self._swatch(d.get("stroke") or (0.1, 0.1, 0.1)))
        self.stroke_btn.setText(" Borde")
        can_fill = d["kind"] in ("rect", "ellipse", "poly")
        self.fill_btn.setVisible(can_fill)
        if can_fill:
            self.fill_btn.setIcon(self._swatch(d.get("fill")))
            self.fill_btn.setText(" Relleno")
        self.width_btn.setText("Grosor")
        s = d.get("opacity", 1.0) if d.get("opacity", 1.0) >= 0 else 1.0
        f = d.get("fill_opacity", s)
        self.op_btn.setVisible(True)
        self.op_btn.setText("Opacidad %d %%" % round(s * 100) if (not (can_fill and d.get("fill")) or abs(s - f) < 0.01)
                            else "Opacidad %d/%d %%" % (round(s * 100), round(f * 100)))
        self.op_btn.setToolTip("Opacidad total; dentro puedes dar otra solo al trazo o solo al relleno")
        self.head_btn.setVisible(d["kind"] == "arrow")
        self.head_btn.setText("Punta")
        self.adjustSize()


class GutterPlusItem(QGraphicsItem):
    """Botón «+» entre dos páginas (vista general): inserta una página en ese hueco."""
    D = 24

    def __init__(self, at_idx: int, callback):
        super().__init__()
        self.at_idx, self.cb, self._hover = at_idx, callback, False
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Insertar una página aquí")

    def boundingRect(self):
        return QRectF(-1, -1, self.D + 2, self.D + 2)

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(ACCENT if self._hover else SURFACE_3))
        p.setPen(QPen(QColor(ACCENT), 1.5))
        p.drawEllipse(QRectF(0, 0, self.D, self.D))
        p.setPen(QPen(QColor(ICON_DARK if self._hover else TEXT), 2))
        c, a = self.D / 2, self.D * 0.27
        p.drawLine(QPointF(c - a, c), QPointF(c + a, c))
        p.drawLine(QPointF(c, c - a), QPointF(c, c + a))

    def hoverEnterEvent(self, e):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.cb("insert", self.at_idx)


class PageBarItem(QGraphicsItem):
    """Barra de acciones de una página (borrar, acercar, alejar, girar, insertar). Se dibuja y atiende los clics ella
    misma, sin widgets incrustados (esos daban cierres bruscos al recargar la escena)."""
    H = 26

    def __init__(self, idx: int, last: bool, callback, compact: bool = False):
        super().__init__()
        self.idx, self.last, self.cb, self.compact = idx, last, callback, compact
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = None
        self._btns = []          # (rect, acción, texto, icono, ayuda)
        x = 0.0
        bw = 28 if compact else 38
        if not last:
            x = 24.0 if compact else 34.0             # sitio para el número de página
            acts = [("delete", "", "trash", "Borrar esta página")]
            if not compact:
                acts += [("zoomin", "+", None, "Acercar"), ("zoomout", "−", None, "Alejar")]
            acts += [("rotl", "", "rot_left", "Girar a la izquierda"), ("rotr", "", "rot_right", "Girar a la derecha")]
            for act, txt, icon, tip in acts:
                self._btns.append((QRectF(x, 0, bw, self.H), act, txt, icon, tip))
                x += bw
            x += 6 if compact else 14
        if compact:
            self.width_ = x - 6                          # en la vista general «insertar» va entre páginas
        else:
            self._btns.append((QRectF(x, 0, 150, self.H), "insert", "Insertar página aquí", "plus",
                               "Insertar una página aquí"))
            self.width_ = x + 150

    def boundingRect(self):
        return QRectF(-1, -1, self.width_ + 2, self.H + 2)

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.Antialiasing, False)
        if not self.last:
            p.setPen(QColor(ACCENT))
            f = p.font(); f.setPixelSize(14 if self.compact else 20); p.setFont(f)
            p.drawText(QRectF(0, 0, 26, self.H), Qt.AlignVCenter | Qt.AlignLeft, str(self.idx + 1))
        f = p.font(); f.setPixelSize(12); p.setFont(f)
        for i, (r, act, txt, icon, tip) in enumerate(self._btns):
            p.setBrush(QColor(SURFACE_3 if self._hover == i else SURFACE))
            p.setPen(QColor(BORDER_STRONG))
            p.drawRect(r)
            p.setPen(QColor(TEXT))
            if icon:
                isz = 19 if icon in ("rot_left", "rot_right") else 15
                pm = ic.icon(icon, TEXT, isz).pixmap(isz, isz)
                if txt:
                    p.drawPixmap(int(r.left() + 10), int(r.center().y() - 7), pm)
                    p.drawText(r.adjusted(30, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, txt)
                else:
                    p.drawPixmap(int(r.center().x() - pm.width() / 2), int(r.center().y() - pm.height() / 2), pm)
            else:
                f2 = p.font(); f2.setPixelSize(16); p.setFont(f2)
                p.drawText(r, Qt.AlignCenter, txt)
                p.setFont(f)

    def _at(self, pos):
        for i, b in enumerate(self._btns):
            if b[0].contains(pos):
                return i
        return None

    def hoverMoveEvent(self, e):
        i = self._at(e.pos())
        if i != self._hover:
            self._hover = i
            self.setToolTip(self._btns[i][4] if i is not None else "")
            self.update()

    def hoverLeaveEvent(self, e):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        i = self._at(e.pos())
        if i is not None and e.button() == Qt.LeftButton:
            self.cb(self._btns[i][1], self.idx)


class PageEditorView(QGraphicsView):
    """Muestra TODAS las páginas apiladas verticalmente (scroll continuo),
    con cada fragmento de texto clicable; al clicar, abre un QLineEdit
    flotando justo encima para editarlo in situ."""
    mode_changed = Signal(str)
    page_action = Signal(str, int)
    shape_kind_changed = Signal(str)
    icon_picker_requested = Signal()                  # clic sobre un icono de «clic aquí» ya seleccionado
    save_signature_requested = Signal(object)         # descripción del dibujo libre que se guarda como firma
    replace_requested = Signal(str)                   # texto sobre el que se pidió «Reemplazar…» con el clic derecho
    link_requested = Signal(int, object, object)      # página, cajas (puntos PDF) o None, enlace existente o None
    field_requested = Signal(int, object)             # página y caja (puntos PDF) donde crear un campo nuevo
    copy_requested = Signal(int, object, object)      # página, caja (puntos PDF) o None, punto del clic o None
    zoomed = Signal(float)
    note_requested = Signal(int, object, object)      # página, punto PDF, nota existente o None
    attach_clicked = Signal(int, object, object)      # página, adjunto, posición global del clic
    ZOOM_MIN, ZOOM_MAX = 0.2, 4.0

    def __init__(self, on_dirty, on_font_missing, on_page_visible=None, on_before_mutate=None,
                 on_notice=None):
        super().__init__()
        # Atributos primero: setStyleSheet/setScene ya pueden disparar
        # eventos que pasan por nuestro eventFilter antes de seguir aquí.
        self._on_notice = on_notice
        self.hf = None          # ajustes de cabecera/pie de este documento (None = detección automática)
        self.manual = False     # True: cada línea es una unidad y no se deduce ni se mueve nada
        self._text0 = ""
        self._on_dirty = on_dirty
        self._on_font_missing = on_font_missing
        self._on_page_visible = on_page_visible
        self._on_before_mutate = on_before_mutate
        self.doc = None
        self.zoom = 1.6
        self._editor: QTextEdit | None = None
        self._editing_item: SpanRectItem | None = None
        self._toolbar: QFrame | None = None
        self._dialog_open = False
        self._page_items: list = []
        self._page_span_items: list[list] = []
        self._page_tops: list[float] = []
        self._current_page = 0
        self._page_gap = 52
        self._cols = 1                      # páginas por fila (más de 1 con el zoom muy alejado)
        self._bar_press = False
        self._bar_h = 34
        self.mode = "edit"                 # "edit" | "censor"
        self._censor_drag_start: QPointF | None = None
        self._censor_rect_item = None
        self.markup_kind = "highlight"     # highlight | underline | strike | erase
        self.markup_color = None           # nombre en annot_tools.COLORS (None = el de la herramienta)
        self._mk_page = None               # página donde empezó el arrastre
        self._mk_start = None              # punto PDF inicial
        self._mk_words: list = []
        self._mk_preview: list = []
        self.shape_kind = "rect"           # rect | ellipse | line | arrow
        self.shape_color = "rojo"
        self.shape_width = 2.0
        self.shape_fill = None             # None = sin relleno
        self.shape_opacity = 1.0           # opacidad total (1 = sólido)
        self.shape_stroke_op = None        # opacidad solo del trazo (None = la total)
        self.shape_fill_op = None          # opacidad solo del relleno (None = la total)
        self.shape_head = "closed"         # forma de la punta de las flechas
        self._pressure = None              # presión del lápiz óptico (None = ratón)
        self._sh_pressures: list = []
        self._eraser_hit = None
        self._eyedrop = None               # función a llamar con el color tomado de la página (cuentagotas)
        self._sh_page = None
        self._sh_start = None              # punto PDF donde empezó el arrastre
        self._sh_move = None               # forma existente que se está moviendo
        self._sh_preview: list = []
        self._sh_stroke: list = []         # puntos del trazo libre en curso (lápiz / rotulador)
        self._ss_sel = None                # forma/trazo seleccionado: {"page", "desc"}
        self._ss_drag = None               # arrastre en curso sobre la selección
        self._lk_items: list = []          # recuadros de los enlaces existentes (modo enlaces)
        self._fm_items: list = []          # recuadros de los campos de formulario (modo formulario)
        self._fm_cache: dict = {}          # página -> campos
        self._fm_editor = None             # caja de texto abierta sobre un campo
        self._fm_down = None               # clic en curso
        self._fm_rubber = None
        self._cp_down = None               # clic o arrastre en curso del modo «copiar»
        self._cp_rubber = None
        self._fm_sel = None                # campo propio seleccionado: {"page","xref","rect","kind"}
        self._reload_cb = None             # la pantalla recarga el documento (hace falta al crear botones de opción)
        self.hide_annots = False           # ver el PDF sin sus anotaciones (solo la vista; no cambia el archivo)
        self.pending_attach = None         # ruta del archivo a adjuntar con el próximo clic
        self._nt_down = None
        self.pending_image = None          # imagen (ruta o bytes) a colocar con el próximo clic
        self._pending_frac = 0.45          # ancho máximo inicial, como fracción del ancho de la página
        self._img_size = (1, 1)
        self._img_sel = None               # {"page", "xref", "rect"} del sello seleccionado (puntos PDF)
        self._img_items: list = []         # marco y tiradores de la selección
        self._img_drag = None              # {"op": "move"|"place"|nw|ne|sw|se, "start", "rect0"}

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setStyleSheet(f"background:{SURFACE}; border:none; border-radius:10px;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._zoom_pending = None
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.timeout.connect(lambda: self.set_zoom(self._zoom_pending))
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.verticalScrollBar().valueChanged.connect(self._update_current_page)
        self._sel_bar = SelectionBar(self)
        self.verticalScrollBar().valueChanged.connect(lambda _=0: self._update_sel_bar())
        self.horizontalScrollBar().valueChanged.connect(lambda _=0: self._update_sel_bar())

    def page_count(self) -> int:
        return len(self._page_items)

    def set_mode(self, mode: str):
        self.mode = mode
        self.viewport().setCursor({"censor": Qt.CrossCursor, "text": Qt.IBeamCursor, "markup": Qt.IBeamCursor,
                                   "shape": Qt.CrossCursor, "link": Qt.IBeamCursor, "note": Qt.CrossCursor, "copy": Qt.CrossCursor,
                                   "attach": Qt.CrossCursor}.get(mode, Qt.ArrowCursor))
        for page_items in self._page_span_items:
            for item in page_items:
                item.setVisible(item.kind == mode)
        self._mk_clear_preview()
        self._attach_ghost_clear()
        self._sh_clear()
        self._ss_sel, self._ss_drag = None, None
        self._update_sel_bar()
        self._fm_sel = None
        if mode != "image":
            self.pending_image = None
            self._img_select(None)
        self._lk_refresh()
        self._fm_close(False)
        self._fm_refresh()
        if mode != "attach":
            self.pending_attach = None
        if self.hide_annots and mode != "edit":              # al usar una herramienta, las anotaciones vuelven a verse
            self.hide_annots = False
            QTimer.singleShot(0, self.reload_preserving_scroll)
        self.mode_changed.emit(mode)

    # ── Notas y adjuntos ──
    def _nt_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        hit = at.note_at(self.doc, page_idx, pt) if self.mode == "note" else None
        att = None if hit else at.attachment_at(self.doc, page_idx, pt)       # un clip se puede coger desde ambos modos
        self._nt_down = {"page": page_idx, "pt": pt, "hit": hit, "att": att, "moved": False}

    def _clip_pixmap(self) -> QPixmap:
        """El clip tal como quedará, dibujado al tamaño actual del zoom."""
        s = int(round(at.CLIP_SIZE * self.zoom))
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        k = s / at.CLIP_SIZE
        pa.scale(k, k)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.0))
        pa.setBrush(QColor("#212121"))
        pa.drawEllipse(QRectF(0.5, 0.5, 21.0, 21.0))
        pen = QPen(QColor("#FFFFFF"), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        pa.setPen(pen)
        pa.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(8.4, 15.6))                         # mismo dibujo que la apariencia del PDF (y invertida)
        path.lineTo(8.4, 7.8)
        path.cubicTo(8.4, 5.4, 13.2, 5.4, 13.2, 7.8)
        path.lineTo(13.2, 14.8)
        path.cubicTo(13.2, 16.6, 10.2, 16.6, 10.2, 14.8)
        path.lineTo(10.2, 9.0)
        pa.drawPath(path)
        pa.end()
        return pm

    def _attach_ghost_move(self, scene_pos: QPointF):
        """Mientras se coloca un adjunto: el clip (semitransparente) viaja con el ratón, centrado donde se colocará."""
        if self.mode != "attach" or not self.pending_attach or self._page_at_y(scene_pos.y(), quiet=True) is None:
            self._attach_ghost_clear()
            return
        g = getattr(self, "_attach_ghost", None)
        if g is None:
            g = self.scene_.addPixmap(self._clip_pixmap())
            g.setOpacity(0.55)
            g.setZValue(70)
            g.setAcceptedMouseButtons(Qt.NoButton)
            self._attach_ghost = g
        w = g.pixmap().width()
        g.setPos(scene_pos.x() - w / 2, scene_pos.y() - w / 2)
        self.viewport().setCursor(Qt.BlankCursor)

    def _attach_ghost_clear(self):
        g, self._attach_ghost = getattr(self, "_attach_ghost", None), None
        if g is not None:
            try:
                self.scene_.removeItem(g)
            except RuntimeError:
                pass

    def leaveEvent(self, e):
        self._attach_ghost_clear()
        super().leaveEvent(e)

    def _nt_move(self, scene_pos: QPointF):
        self._attach_ghost_move(scene_pos)
        d = self._nt_down
        if d and (d["hit"] or d.get("att")):
            pt = self._mk_pdf_point(scene_pos, d["page"])
            if abs(pt[0] - d["pt"][0]) > 4 or abs(pt[1] - d["pt"][1]) > 4:
                d["moved"] = True
                self.viewport().setCursor(Qt.SizeAllCursor)

    def _nt_release(self, scene_pos: QPointF, global_pos):
        d, self._nt_down = self._nt_down, None
        if not d:
            return
        page_idx = d["page"]
        pt = self._mk_pdf_point(scene_pos, page_idx)
        self.viewport().setCursor(Qt.BlankCursor if (self.mode == "attach" and self.pending_attach) else Qt.CrossCursor)
        if d.get("att"):
            if d["moved"]:                                          # arrastrar el clip: cambia de sitio
                if self._on_before_mutate:
                    self._on_before_mutate()
                if at.move_attachment(self.doc, page_idx, d["att"]["xref"], pt[0] - d["pt"][0], pt[1] - d["pt"][1]):
                    self._on_dirty()
                    self.refresh_page(page_idx)
            else:                                                   # clic: guardar copia o quitar
                self.attach_clicked.emit(page_idx, d["att"], global_pos)
            return
        if self.mode == "note":
            if d["hit"] and d["moved"]:
                if self._on_before_mutate:
                    self._on_before_mutate()
                nx, ny = d["hit"]["pos"][0] + pt[0] - d["pt"][0], d["hit"]["pos"][1] + pt[1] - d["pt"][1]
                if at.move_note(self.doc, page_idx, d["hit"]["xref"], (nx, ny)):
                    self._on_dirty()
                    self.refresh_page(page_idx)
            else:
                self.note_requested.emit(page_idx, pt, d["hit"])
            return
        # modo adjuntar
        att = at.attachment_at(self.doc, page_idx, pt)
        if att:
            self.attach_clicked.emit(page_idx, att, global_pos)
        elif self.pending_attach:
            if self._on_before_mutate:
                self._on_before_mutate()
            if at.add_attachment(self.doc, page_idx, pt, self.pending_attach):
                self._on_dirty()
                self.refresh_page(page_idx)
                self.pending_attach = None
                self._attach_ghost_clear()
                self.set_mode("edit")
                if self._on_notice:
                    self._on_notice("Archivo adjuntado (el clip). Clic en el clip para guardar una copia o quitarlo.")
        elif self._on_notice:
            self._on_notice("Elige antes el archivo: Notas → Adjuntar archivo…")

    def apply_note(self, page_idx: int, pt, existing, text: str, author: str, remove: bool = False) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        if existing is not None:
            ok = (at.delete_annot_by_xref(self.doc, page_idx, existing["xref"]) if remove
                  else at.update_note(self.doc, page_idx, existing["xref"], text))
        else:
            ok = at.add_note(self.doc, page_idx, pt, text, author)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
        return ok

    def remove_attachment(self, page_idx: int, xref: int) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = at.delete_annot_by_xref(self.doc, page_idx, xref)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
        return ok

    def set_hide_annots(self, hide: bool):
        if self.hide_annots != hide:
            self.hide_annots = hide
            self.reload_preserving_scroll()

    # ── Modo copiar: arrastrar una zona, o hacer clic en un párrafo o tabla ──
    def _cp_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        self._cp_down = {"page": page_idx, "pt": self._mk_pdf_point(scene_pos, page_idx), "moved": False}

    def _cp_move(self, scene_pos: QPointF):
        d = self._cp_down
        if not d:
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if abs(pt[0] - d["pt"][0]) > 4 or abs(pt[1] - d["pt"][1]) > 4:
            d["moved"] = True
        if not d["moved"]:
            return
        if self._cp_rubber is not None:
            self.scene_.removeItem(self._cp_rubber)
        box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
        self._cp_rubber = self.scene_.addRect(self._img_scene_rect(d["page"], box), QPen(QColor(ACCENT), 1.5, Qt.DashLine),
                                              QBrush(QColor(192, 130, 88, 60)))
        self._cp_rubber.setZValue(50)

    def _cp_release(self, scene_pos: QPointF):
        d, self._cp_down = self._cp_down, None
        if self._cp_rubber is not None:
            self.scene_.removeItem(self._cp_rubber)
            self._cp_rubber = None
        if not d:
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if d["moved"]:
            box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
            self.copy_requested.emit(d["page"], box, None)
        else:
            self.copy_requested.emit(d["page"], None, d["pt"])

    def show_copy_highlight(self, page_idx: int, rect):
        """Marca en pantalla la zona que se está copiando (se quita al terminar)."""
        self.clear_copy_highlight()
        if rect is None:
            return
        it = self.scene_.addRect(self._img_scene_rect(page_idx, rect), QPen(QColor(ACCENT), 1.5),
                                 QBrush(QColor(192, 130, 88, 55)))
        it.setZValue(48)
        self._cp_rubber = it

    def clear_copy_highlight(self):
        if self._cp_rubber is not None:
            try:
                self.scene_.removeItem(self._cp_rubber)
            except RuntimeError:
                pass
            self._cp_rubber = None

    # ── Modo formulario: rellenar campos, crear campos nuevos, borrarlos ──
    def _fm_refresh(self):
        for it in self._fm_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._fm_items, self._fm_cache = [], {}
        if self.mode != "form" or not self.doc or self._cols > 1:
            return
        for pi in range(len(self._page_tops)):
            ws = ft.widgets_of(self.doc, pi)
            self._fm_cache[pi] = ws
            for w in ws:
                it = self.scene_.addRect(self._img_scene_rect(pi, w["rect"]), QPen(QColor(70, 140, 255), 1.2, Qt.DashLine),
                                         QBrush(QColor(70, 140, 255, 28)))
                it.setZValue(40)
                it.setToolTip(f"{ft.KIND_LABELS.get(w['kind'], 'Campo')}: {w['name']}")
                self._fm_items.append(it)

    def _fm_hit(self, page_idx: int, pt: tuple):
        hit = None
        for w in self._fm_cache.get(page_idx, []):
            r = w["rect"]
            if r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]:
                hit = w
        return hit

    def _fm_close(self, commit: bool):
        ed = self._fm_editor
        if ed is not None:
            ed._finish(commit)

    def _fm_done(self, ed, info, text):
        if self._fm_editor is ed:
            self._fm_editor = None
        ed.hide()
        ed.deleteLater()
        cover, self._fm_cover = getattr(self, "_fm_cover", None), None
        if cover is not None:
            try:
                self.scene_.removeItem(cover)
            except RuntimeError:
                pass
        if info is not None:
            self._fm_set(info["page"], info["xref"], text)

    def _fm_open_editor(self, page_idx: int, w: dict):
        self._fm_close(True)
        vr = self.mapFromScene(self._img_scene_rect(page_idx, w["rect"])).boundingRect()
        # tamaño de letra: el del campo, pero sin pasar de lo que cabe en su altura (si no, el texto se corta y no se ve)
        fs = float(w["fontsize"] or 0) * self.zoom
        if w["multiline"]:
            px = fs if fs > 0 else 14.0 * self.zoom / 1.6
        else:
            fit = max(9.0, (vr.height() - 8) * 0.78)
            px = min(fs, fit) if fs > 0 else min(fit, 15.0)
        ed = _FieldEditor(self.viewport(), str(w["value"] or ""), w["multiline"], px)
        geo = vr.adjusted(-1, -1, 1, 1)
        need = QFontMetrics(ed.font()).height() + 10          # alto mínimo para que se vea la línea entera
        if not w["multiline"] and geo.height() < need:
            geo.setTop(geo.center().y() - need // 2)
            geo.setHeight(need)
        ed.setGeometry(geo)
        if not w["multiline"]:                                  # texto centrado en vertical dentro del campo
            ed.setViewportMargins(3, max(0, (geo.height() - QFontMetrics(ed.font()).height()) // 2), 3, 0)
        else:
            ed.setViewportMargins(3, 2, 3, 2)
        # tapa el valor que ya tenía el campo (con el color de fondo del propio campo) para que no se duplique
        r = self._img_scene_rect(page_idx, w["rect"]).adjusted(2, 2, -2, -2)
        if r.width() > 2 and r.height() > 2 and page_idx < len(self._page_items):
            it = self._page_items[page_idx]
            col = it.pixmap().toImage().pixelColor(max(0, int(r.x() + 1 - it.x())), max(0, int(r.y() + 1 - it.y())))
            cov = self.scene_.addRect(r, QPen(Qt.NoPen), QBrush(col))
            cov.setZValue(44)
            self._fm_cover = cov
        ed.show()
        ed.setFocus()
        ed.selectAll()
        info = {"page": page_idx, "xref": w["xref"]}
        ed.committed.connect(lambda txt, i=info, e=ed: self._fm_done(e, i, txt))
        ed.cancelled.connect(lambda e=ed: self._fm_done(e, None, None))
        ed.tabbed.connect(lambda fwd, i=info: QTimer.singleShot(0, lambda: self._fm_tab(i, fwd)))
        self._fm_editor = ed

    def _fm_tab(self, info: dict, forward: bool):
        """Tab / Mayús+Tab: ya confirmado el campo actual, abre el siguiente (o el anterior) campo de texto, siguiendo el
        orden de tabulación del documento (por filas por defecto, o por columnas)."""
        order = ft.get_tab_order(self.doc) if self.doc is not None else "R"
        items = [(pi, w) for pi, ws in sorted(self._fm_cache.items()) for w in ws
                 if w["kind"] == "text" and not w["readonly"]]
        if not items:
            return
        if order == "C":
            items.sort(key=lambda it: (it[0], round(it[1]["rect"][0] / 10), it[1]["rect"][1]))
        else:
            items.sort(key=lambda it: (it[0], round((it[1]["rect"][1] + it[1]["rect"][3]) / 2 / 6), it[1]["rect"][0]))
        idx = next((i for i, (pi, w) in enumerate(items) if w["xref"] == info["xref"]), None)
        if idx is None:
            return
        pi, w = items[(idx + (1 if forward else -1)) % len(items)]
        self.ensureVisible(self._img_scene_rect(pi, w["rect"]), 60, 90)
        self._fm_open_editor(pi, w)

    def _fm_set(self, page_idx: int, xref: int, value):
        cur = next((w for w in self._fm_cache.get(page_idx, []) if w["xref"] == xref), None)
        if cur is not None and cur["kind"] in ("text", "combo", "list") and str(cur["value"] or "") == str(value):
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        if ft.set_widget_value(self.doc, page_idx, xref, value):
            self._on_dirty()
            self.refresh_page(page_idx)
            self._fm_refresh()

    def _fm_activate(self, page_idx: int, w: dict, scene_pos: QPointF):
        if w["readonly"]:
            if self._on_notice:
                self._on_notice("Este campo es de solo lectura.")
            return
        k = w["kind"]
        if k == "text":
            self._fm_open_editor(page_idx, w)
        elif k == "checkbox":
            self._fm_set(page_idx, w["xref"], not w["checked"])
        elif k == "radio":
            if not w["checked"]:
                self._fm_set(page_idx, w["xref"], True)
        elif k in ("combo", "list"):
            m = QMenu(self)
            for c in w["choices"]:
                act = m.addAction(c)
                act.setCheckable(True)
                act.setChecked(c == str(w["value"]))
                act.triggered.connect(lambda _=False, v=c: self._fm_set(page_idx, w["xref"], v))
            m.exec(self.viewport().mapToGlobal(self.mapFromScene(scene_pos)))
        elif k == "signature" and self._on_notice:
            self._on_notice("Para firmar, usa el botón Firma.")
        elif self._on_notice:
            self._on_notice("Este botón no se puede rellenar.")

    def _fm_handle_at(self, scene_pos: QPointF):
        sel = self._fm_sel
        if not sel:
            return None
        r = self._img_scene_rect(sel["page"], sel["rect"])
        tol = self._HANDLE + 4
        for name, pt in (("nw", r.topLeft()), ("ne", r.topRight()), ("sw", r.bottomLeft()), ("se", r.bottomRight())):
            if abs(scene_pos.x() - pt.x()) <= tol and abs(scene_pos.y() - pt.y()) <= tol:
                return name
        return None

    def _fm_select(self, page_idx, w):
        """Selecciona un campo creado aquí (marco y tiradores) o quita la selección (w=None)."""
        self._img_select(None)
        self._fm_sel = None if w is None else {"page": page_idx, "xref": w["xref"], "rect": tuple(w["rect"]),
                                               "kind": w["kind"]}
        if w is not None:
            self._img_draw(page_idx, w["rect"])

    def _fm_press(self, scene_pos: QPointF):
        self._fm_close(True)
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        op = self._fm_handle_at(scene_pos) if self._fm_sel and self._fm_sel["page"] == page_idx else None
        self._fm_down = {"page": page_idx, "pt": pt, "hit": self._fm_hit(page_idx, pt), "scene": scene_pos,
                         "moved": False, "op": op, "newrect": None}

    def _fm_new_rect(self, d, pt):
        sel = self._fm_sel
        x0, y0, x1, y1 = sel["rect"] if d["op"] else d["hit"]["rect"]
        if not d["op"]:                                           # mover
            dx, dy = pt[0] - d["pt"][0], pt[1] - d["pt"][1]
            return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        anchor = {"nw": (x1, y1), "ne": (x0, y1), "sw": (x1, y0), "se": (x0, y0)}[d["op"]]
        if sel["kind"] in ("checkbox", "radio"):
            return self._img_aspect_rect(anchor, pt, 1.0)
        nb = (min(anchor[0], pt[0]), min(anchor[1], pt[1]), max(anchor[0], pt[0]), max(anchor[1], pt[1]))
        return (nb[0], nb[1], max(nb[2], nb[0] + 14), max(nb[3], nb[1] + 10))

    def _fm_move(self, scene_pos: QPointF):
        d = self._fm_down
        if not d:
            h = self._fm_handle_at(scene_pos)
            if h:
                self.viewport().setCursor(Qt.SizeFDiagCursor if h in ("nw", "se") else Qt.SizeBDiagCursor)
                return
            page_idx = self._page_at_y(scene_pos.y(), quiet=True)
            over = page_idx is not None and self._fm_hit(page_idx, self._mk_pdf_point(scene_pos, page_idx))
            self.viewport().setCursor(Qt.PointingHandCursor if over else Qt.CrossCursor)
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if abs(pt[0] - d["pt"][0]) > 3 or abs(pt[1] - d["pt"][1]) > 3:
            d["moved"] = True
        if not d["moved"]:
            return
        movable = d["op"] or (d["hit"] and d["hit"].get("ours"))
        if movable:
            if not d["op"]:
                self._fm_select(d["page"], d["hit"])
            d["newrect"] = self._fm_new_rect(d, pt)
            self._img_draw(d["page"], d["newrect"])
            return
        if not d["hit"]:
            if self._fm_rubber is not None:
                self.scene_.removeItem(self._fm_rubber)
            box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
            self._fm_rubber = self.scene_.addRect(self._img_scene_rect(d["page"], box),
                                                  QPen(QColor(70, 140, 255), 1.5, Qt.DashLine),
                                                  QBrush(QColor(70, 140, 255, 50)))
            self._fm_rubber.setZValue(50)

    def _fm_release(self, scene_pos: QPointF):
        d, self._fm_down = self._fm_down, None
        if self._fm_rubber is not None:
            self.scene_.removeItem(self._fm_rubber)
            self._fm_rubber = None
        if not d:
            return
        if d.get("newrect") and self._fm_sel:
            sel = self._fm_sel
            if self._on_before_mutate:
                self._on_before_mutate()
            if ft.set_field_rect(self.doc, sel["page"], sel["xref"], d["newrect"]):
                self._on_dirty()
                self.refresh_page(sel["page"])
                self._fm_refresh()
                nw = next((w for w in self._fm_cache.get(sel["page"], []) if w["xref"] == sel["xref"]), None)
                self._fm_select(sel["page"], nw)
            return
        if d["hit"] and not d["moved"]:
            self._fm_select(d["page"], d["hit"] if d["hit"].get("ours") else None)
            self._fm_activate(d["page"], d["hit"], scene_pos)
            return
        if not d["hit"] and d["moved"]:
            pt = self._mk_pdf_point(scene_pos, d["page"])
            box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
            if box[2] - box[0] >= 10 and box[3] - box[1] >= 8:
                self.field_requested.emit(d["page"], box)
            elif self._on_notice:
                self._on_notice("Arrastra un recuadro más grande para crear el campo.")
        elif not d["hit"]:
            self._fm_select(None, None)
            if self._on_notice:
                self._on_notice("Haz clic en un campo para rellenarlo, o arrastra un recuadro para crear uno nuevo.")

    def show_candidates(self, found):
        """Marca en verde los campos que se podrían crear (o los quita con None)."""
        for it in getattr(self, "_fm_cand", []):
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._fm_cand = []
        for pi, items in (found or {}).items():
            for c in items:
                it = self.scene_.addRect(self._img_scene_rect(pi, c["rect"]), QPen(QColor(40, 170, 90), 1.6, Qt.DashLine),
                                         QBrush(QColor(40, 170, 90, 55)))
                it.setZValue(45)
                self._fm_cand.append(it)

    def apply_new_field(self, page_idx: int, rect, spec: dict) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = ft.add_field(self.doc, page_idx, rect, spec)
        if ok and spec.get("kind") == "radio" and self._reload_cb:
            self._on_dirty()
            self._reload_cb()                       # PyMuPDF no ve los botones nuevos hasta reabrir el documento
            return True
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._fm_refresh()
        return ok

    def delete_field(self, page_idx: int, xref: int) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = ft.delete_field(self.doc, page_idx, xref)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._fm_refresh()
        return ok

    # ── Modo enlaces: crear sobre texto o área, y editar o quitar los existentes ──
    def _lk_refresh(self):
        """Dibuja un recuadro azul sobre cada enlace de todas las páginas (solo en modo enlaces)."""
        for it in self._lk_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._lk_items = []
        self._lk_hover_clear()
        self._lk_words_cache = None
        if self.mode != "link" or not self.doc or self._cols > 1:
            return
        for pi in range(len(self._page_tops)):
            for l in at.list_links(self.doc, pi):
                it = self.scene_.addRect(self._img_scene_rect(pi, l["rect"]), QPen(QColor(70, 140, 255), 1.2),
                                         QBrush(QColor(70, 140, 255, 45)))
                it.setZValue(40)
                it.setToolTip(at.describe_link(l))
                self._lk_items.append(it)

    def _lk_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        self._mk_page, self._mk_start = page_idx, pt
        self._mk_words = at.page_words(self.doc, page_idx)

    def _lk_boxes(self, scene_pos: QPointF):
        """Cajas del enlace en curso: las líneas de texto seleccionadas o, si no hay texto, el área arrastrada."""
        pt = self._mk_pdf_point(scene_pos, self._mk_page)
        idx = at.select_words(self._mk_words, self._mk_start, pt)
        moved = abs(pt[0] - self._mk_start[0]) > 6 or abs(pt[1] - self._mk_start[1]) > 6
        if idx and moved:
            return at.line_rects(self._mk_words, idx)
        if moved:
            return [fitz_rect(min(self._mk_start[0], pt[0]), min(self._mk_start[1], pt[1]),
                              max(self._mk_start[0], pt[0]), max(self._mk_start[1], pt[1]))]
        return at.line_rects(self._mk_words, idx) if idx else []

    def _lk_hover_clear(self):
        for it in getattr(self, "_lk_hover_items", []):
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._lk_hover_items = []
        self._lk_hover_key = None

    def _lk_hover(self, scene_pos: QPointF):
        """Sin pulsar: marca el área que se convertiría en enlace si haces clic aquí (palabra, imagen o dibujo), o el
        enlace ya existente (en otro color) si lo hay."""
        page_idx = self._page_at_y(scene_pos.y(), quiet=True)
        if page_idx is None or not self.doc or self._cols > 1:
            self._lk_hover_clear()
            self.viewport().setCursor(Qt.IBeamCursor)
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        rects, existing = [], False
        link = at.link_at(self.doc, page_idx, pt)
        if link:
            rects = [tuple(l["rect"]) for l in at.group_of(self.doc, page_idx, link)]
            existing = True
        else:
            cache = getattr(self, "_lk_words_cache", None)
            if cache is None or cache[0] != (id(self.doc), page_idx):
                cache = ((id(self.doc), page_idx), at.page_words(self.doc, page_idx))
                self._lk_words_cache = cache
            idx = at.select_words(cache[1], pt, pt, 4.0)
            if idx:
                rects = [tuple(r) for r in at.line_rects(cache[1], idx)]
            else:
                obj = self._lk_object_box(page_idx, pt)
                if obj:
                    rects = [obj]
        key = (page_idx, tuple(rects), existing)
        if key == getattr(self, "_lk_hover_key", None):
            return
        self._lk_hover_clear()
        self._lk_hover_key = key
        if rects:
            col = QColor(255, 150, 60) if existing else QColor(70, 140, 255)
            for r in rects:
                it = self.scene_.addRect(self._img_scene_rect(page_idx, r), QPen(col, 1.5),
                                         QBrush(QColor(col.red(), col.green(), col.blue(), 60)))
                it.setZValue(49)
                self._lk_hover_items.append(it)
        self.viewport().setCursor(Qt.PointingHandCursor if rects else Qt.IBeamCursor)

    def _lk_move(self, scene_pos: QPointF):
        if self._mk_start is None:
            self._lk_hover(scene_pos)
            return
        self._lk_hover_clear()
        for it in self._mk_preview:
            self.scene_.removeItem(it)
        self._mk_preview = []
        for r in self._lk_boxes(scene_pos):
            it = self.scene_.addRect(self._img_scene_rect(self._mk_page, (r[0], r[1], r[2], r[3])),
                                     QPen(QColor(70, 140, 255), 1.5, Qt.DashLine), QBrush(QColor(70, 140, 255, 70)))
            it.setZValue(50)
            self._mk_preview.append(it)

    def _lk_object_box(self, page_idx: int, pt: tuple):
        """Caja de la imagen (o del dibujo hecho en el editor) que hay bajo el punto, la más pequeña si hay varias."""
        best = None
        try:
            page = self.doc[page_idx]
            for info in page.get_image_info():
                x0, y0, x1, y1 = info["bbox"]
                if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1:
                    area = (x1 - x0) * (y1 - y0)
                    if best is None or area < best[0]:
                        best = (area, (x0, y0, x1, y1))
        except Exception:
            pass
        if best is None:
            hit = at.editable_at(self.doc, page_idx, pt)
            if hit:
                return tuple(hit["bbox"])
        return best[1] if best else None

    def _lk_release(self, scene_pos: QPointF):
        if self._mk_start is None:
            return
        page_idx, start = self._mk_page, self._mk_start
        pt = self._mk_pdf_point(scene_pos, page_idx)
        moved = abs(pt[0] - start[0]) > 6 or abs(pt[1] - start[1]) > 6
        self._lk_from_object = False
        existing = None if moved else at.link_at(self.doc, page_idx, pt)
        boxes = None if existing else [tuple(b) for b in self._lk_boxes(scene_pos)]
        if existing is None and not boxes and not moved:
            obj = self._lk_object_box(page_idx, pt)          # clic sobre una imagen o dibujo: el enlace cubre todo el objeto
            if obj:
                boxes = [obj]
                self._lk_from_object = True
        self._mk_clear_preview()
        if existing is None and not boxes:
            if self._on_notice:
                self._on_notice("Arrastra sobre el texto o el área, o haz clic sobre una imagen o dibujo, para convertirlo en enlace.")
            return
        self.link_requested.emit(page_idx, boxes, existing)

    def apply_link(self, page_idx: int, boxes, existing, dest, underline: bool = False, obj: bool = False,
                   color=None):
        """Crea el enlace en cada caja, o cambia / quita el existente (dest=None quita)."""
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = False
        if existing is not None:
            members = at.group_of(self.doc, page_idx, existing)      # todas las zonas del mismo enlace
            ok = at.delete_group(self.doc, page_idx, members) if dest is None else at.replace_group(
                self.doc, page_idx, members, dest)
        else:
            col = tuple(color) if color else LINK_COLORS[0][1]
            if underline and not obj:                                # texto: se pone en el color del enlace
                be.recolor_text_in_boxes(self.doc, page_idx, [tuple(b) for b in boxes], col)
            gid = at.new_group_id() if len(boxes) > 1 else None      # las zonas de un enlace van juntas
            for i, b in enumerate(boxes):
                ok = at.add_link(self.doc, page_idx, b, dest, group=gid, index=i) or ok
            if ok and underline:                                   # que se note: subrayado azul
                at.add_markup(self.doc, page_idx, [tuple(b) for b in boxes], "underline", col)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._lk_refresh()
        return ok

    # ── Modo imagen: colocar, seleccionar, mover, escalar y borrar imágenes y firmas ──
    _HANDLE = 9.0

    def start_place_image(self, source, size: tuple, max_frac: float = 0.45):
        """Deja lista una imagen para colocarla con el siguiente clic (o arrastre) sobre la página."""
        self._img_select(None)
        self.set_mode("image")
        self.pending_image, self._img_size, self._pending_frac = source, size, max_frac
        self.viewport().setCursor(Qt.CrossCursor)

    def _img_select(self, sel):
        for it in self._img_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._img_items = []
        self._img_sel = sel
        if not sel:
            return
        self._img_draw(sel["page"], sel["rect"], handles=not sel.get("pdf"), rot=bool(sel.get("icon")))

    def _img_scene_rect(self, page_idx, rect):
        top, z = self._page_tops[page_idx], self.zoom
        return QRectF(rect[0] * z, top + rect[1] * z, (rect[2] - rect[0]) * z, (rect[3] - rect[1]) * z)

    _ROT_OFFSET = 26.0

    def _img_draw(self, page_idx, rect, handles: bool = True, rot: bool = False):
        for it in self._img_items:
            self.scene_.removeItem(it)
        self._img_items = []
        r = self._img_scene_rect(page_idx, rect)
        pen = QPen(QColor(ACCENT), 1.5, Qt.DashLine)
        frame = self.scene_.addRect(r, pen, QBrush(Qt.NoBrush))
        frame.setZValue(60)
        self._img_items.append(frame)
        if rot:                                           # tirador de giro (solo en los iconos de «clic aquí»)
            c = QPointF(r.center().x(), r.top() - self._ROT_OFFSET)
            cord = self.scene_.addLine(r.center().x(), r.top(), c.x(), c.y(), QPen(QColor(ACCENT), 1.2))
            cord.setZValue(60)
            hd = self.scene_.addEllipse(QRectF(c.x() - 5.5, c.y() - 5.5, 11, 11), QPen(QColor(ACCENT), 1.5),
                                        QBrush(QColor("#FFFFFF")))
            hd.setZValue(61)
            self._img_items += [cord, hd]
        h = self._HANDLE
        for pt in ((r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()) if handles else ()):
            hd = self.scene_.addRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h), QPen(QColor(ACCENT)),
                                     QBrush(QColor("#FFFFFF")))
            hd.setZValue(61)
            self._img_items.append(hd)

    def _img_handle_at(self, scene_pos: QPointF):
        if not self._img_sel or self._img_sel.get("pdf"):
            return None
        r = self._img_scene_rect(self._img_sel["page"], self._img_sel["rect"])
        h = self._HANDLE + 4
        handles = [("nw", r.topLeft()), ("ne", r.topRight()), ("sw", r.bottomLeft()), ("se", r.bottomRight())]
        if self._img_sel.get("icon"):
            handles.append(("rot", QPointF(r.center().x(), r.top() - self._ROT_OFFSET)))
        for name, pt in handles:
            if abs(scene_pos.x() - pt.x()) <= h and abs(scene_pos.y() - pt.y()) <= h:
                return name
        return None

    def _img_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        if self.pending_image is not None:
            self._img_drag = {"op": "place", "start": pt, "page": page_idx, "rect": None}
            return
        handle = self._img_handle_at(scene_pos)
        if handle:
            self._img_drag = {"op": handle, "start": pt, "page": self._img_sel["page"],
                              "rect0": tuple(self._img_sel["rect"]), "rect": None}
            if handle == "rot":
                self._img_drag["angle0"] = (self._img_sel.get("icon") or ("", 0.0))[1]
            return
        hit = at.stamp_at(self.doc, page_idx, pt)
        if hit:
            again = bool(self._img_sel and self._img_sel.get("xref") == hit["xref"] and self._img_sel.get("icon"))
            self._img_select({"page": page_idx, "xref": hit["xref"], "rect": hit["rect"],
                              "icon": ci.parse_subject(hit.get("subject", ""))})
            self._img_drag = {"op": "move", "start": pt, "page": page_idx, "rect0": tuple(hit["rect"]), "rect": None,
                              "reclick": again}
            self.viewport().setCursor(Qt.SizeAllCursor)
        else:
            pimg = at.pdf_image_at(self.doc, page_idx, pt)       # imagen del propio PDF: se puede borrar
            if pimg:
                self._img_select({"page": page_idx, "xref": None, "rect": pimg["bbox"], "pdf": True})
                if self._on_notice:
                    self._on_notice("Imagen del PDF seleccionada: pulsa Supr para quitarla de esta página.")
            else:
                self._img_select(None)

    def _img_aspect_rect(self, anchor, pt, aspect):
        """Caja con una esquina en `anchor` y la opuesta lo más cerca posible de `pt`, manteniendo la proporción."""
        dx, dy = pt[0] - anchor[0], pt[1] - anchor[1]
        w = max(abs(dx), abs(dy) * aspect, 12.0)
        h = w / aspect
        x1 = anchor[0] + (w if dx >= 0 else -w)
        y1 = anchor[1] + (h if dy >= 0 else -h)
        return (min(anchor[0], x1), min(anchor[1], y1), max(anchor[0], x1), max(anchor[1], y1))

    def _img_compute(self, drag, pt, shift=False):
        op = drag["op"]
        if op == "move":
            dx, dy = pt[0] - drag["start"][0], pt[1] - drag["start"][1]
            x0, y0, x1, y1 = drag["rect0"]
            return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        if op == "place":
            aspect = self._img_size[0] / max(self._img_size[1], 1)
            return self._img_aspect_rect(drag["start"], pt, aspect)
        x0, y0, x1, y1 = drag["rect0"]
        if op == "rot":
            return drag["rect0"]
        anchor = {"nw": (x1, y1), "ne": (x0, y1), "sw": (x1, y0), "se": (x0, y0)}[op]
        if shift:                                   # con Mayús, deformar libremente
            return (min(anchor[0], pt[0]), min(anchor[1], pt[1]), max(anchor[0], pt[0]), max(anchor[1], pt[1]))
        return self._img_aspect_rect(anchor, pt, (x1 - x0) / max(y1 - y0, 1e-3))

    def _img_ghost_begin(self, d) -> None:
        """Al empezar a arrastrar o girar un sello/icono: se guarda su imagen y se oculta el original, para que lo que
        se ve moverse sea la propia imagen y no solo su marco."""
        if d.get("ghost_pm") is not None or d.get("op") == "place":
            return
        sel = self._img_sel
        if not sel or sel.get("pdf") or not sel.get("xref"):
            return
        png = at.stamp_png(self.doc, d["page"], sel["xref"])
        if not png:
            return
        pm = QPixmap()
        pm.loadFromData(png)
        d["ghost_pm"] = pm
        if at.set_stamp_hidden(self.doc, d["page"], sel["xref"], True):
            d["hidden"] = True
            img = be.render_doc_page_png(self.doc, d["page"], zoom=self.zoom, annots=not self.hide_annots)
            if img:
                page_pm = QPixmap()
                page_pm.loadFromData(img)
                self._page_items[d["page"]].setPixmap(page_pm)

    def _img_ghost_draw(self, d, rect) -> None:
        pm = d.get("ghost_pm")
        if pm is None:
            return
        r = self._img_scene_rect(d["page"], rect)
        item = self.scene_.addPixmap(pm.scaled(max(1, int(r.width())), max(1, int(r.height())),
                                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        item.setPos(r.topLeft())
        item.setZValue(59)
        self._img_items.append(item)

    def _img_move(self, scene_pos: QPointF, shift: bool):
        d = self._img_drag
        if not d:
            h = self._img_handle_at(scene_pos)
            self.viewport().setCursor({"nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor, "ne": Qt.SizeBDiagCursor,
                                       "sw": Qt.SizeBDiagCursor}.get(h, Qt.CrossCursor if self.pending_image is not None
                                                                     else Qt.ArrowCursor))
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if d["op"] == "place" and abs(pt[0] - d["start"][0]) < 3 and abs(pt[1] - d["start"][1]) < 3:
            return
        if d["op"] == "rot":
            import math
            x0, y0, x1, y1 = d["rect0"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            a0 = math.atan2(d["start"][1] - cy, d["start"][0] - cx)
            a1 = math.atan2(pt[1] - cy, pt[0] - cx)
            step = 15.0 if shift else 5.0
            d["angle"] = round((d["angle0"] + math.degrees(a1 - a0)) / step) * step
            self._img_ghost_begin(d)
            d["rect"] = d["rect0"]
            self._img_draw(d["page"], d["rect0"], handles=False, rot=True)
            key = (self._img_sel.get("icon") or ("arrow", 0))[0]
            pm = QPixmap.fromImage(ci.render_image(key, d["angle"], 192))
            item = self.scene_.addPixmap(pm.scaled(int(self._img_scene_rect(d["page"], d["rect0"]).width()),
                                                   int(self._img_scene_rect(d["page"], d["rect0"]).height()),
                                                   Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            item.setPos(self._img_scene_rect(d["page"], d["rect0"]).topLeft())
            item.setZValue(59)
            self._img_items.append(item)
            return
        self._img_ghost_begin(d)
        d["rect"] = self._img_compute(d, pt, shift)
        self._img_draw(d["page"], d["rect"], rot=False)
        self._img_ghost_draw(d, d["rect"])

    def _img_release(self, scene_pos: QPointF, shift: bool):
        d, self._img_drag = self._img_drag, None
        if not d:
            return
        page_idx = d["page"]
        if d.get("hidden") and self._img_sel:
            at.set_stamp_hidden(self.doc, page_idx, self._img_sel["xref"], False)
            d["hidden"] = False
        pt = self._mk_pdf_point(scene_pos, page_idx)
        moved = abs(pt[0] - d["start"][0]) >= 3 or abs(pt[1] - d["start"][1]) >= 3
        if d["op"] == "place":
            src = self.pending_image
            if moved:
                rect = self._img_compute(d, pt)
            else:
                page_rect = self.doc[page_idx].rect
                rect = tuple(at.default_image_rect(page_rect, self._img_size[0], self._img_size[1],
                                                   center=d["start"], max_frac=self._pending_frac))
            if self._on_before_mutate:
                self._on_before_mutate()
            xref = at.add_image(self.doc, page_idx, rect, src)
            self.pending_image = None
            if xref:
                self._on_dirty()
                self.refresh_page(page_idx)
                self._img_select({"page": page_idx, "xref": xref, "rect": rect})
            self.viewport().setCursor(Qt.ArrowCursor)
            return
        if not moved or not self._img_sel:
            self.viewport().setCursor(Qt.ArrowCursor)
            if d.get("ghost_pm") is not None:
                self.refresh_page(page_idx)
            self._img_select(self._img_sel)
            if d.get("reclick") and not moved:
                self.icon_picker_requested.emit()
            return
        if d["op"] == "rot":
            self.viewport().setCursor(Qt.ArrowCursor)
            self.rotate_selected_icon(d.get("angle", d["angle0"]) - d["angle0"])
            return
        rect = self._img_compute(d, pt, shift)
        if self._on_before_mutate:
            self._on_before_mutate()
        if at.set_stamp_rect(self.doc, page_idx, self._img_sel["xref"], rect):
            xref = self._img_sel["xref"]
            icon = self._img_sel.get("icon")
            self._on_dirty()
            self.refresh_page(page_idx)
            self._img_select({"page": page_idx, "xref": xref, "rect": rect, "icon": icon})
        self.viewport().setCursor(Qt.ArrowCursor)

    def swap_selected_icon(self, key: str) -> bool:
        """Cambia el dibujo del icono seleccionado por otro, conservando su sitio, tamaño y giro."""
        sel = self._img_sel
        if not sel or not sel.get("icon") or not self.doc:
            return False
        old_key, ang = sel["icon"]
        if key == old_key:
            return True
        if self._on_before_mutate:
            self._on_before_mutate()
        res = at.rotate_click_icon(self.doc, sel["page"], sel["xref"], ang, key=key)
        if not res:
            return False
        self._on_dirty()
        self.refresh_page(sel["page"])
        self._img_select({"page": sel["page"], "xref": res[0], "rect": res[1], "icon": (key, ang)})
        return True

    def rotate_selected_icon(self, delta: float) -> bool:
        """Gira el icono de «clic aquí» seleccionado `delta` grados."""
        sel = self._img_sel
        if not sel or not sel.get("icon") or not self.doc:
            return False
        key, ang = sel["icon"]
        new_ang = (ang + delta) % 360
        if self._on_before_mutate:
            self._on_before_mutate()
        res = at.rotate_click_icon(self.doc, sel["page"], sel["xref"], new_ang)
        if not res:
            return False
        self._on_dirty()
        self.refresh_page(sel["page"])
        self._img_select({"page": sel["page"], "xref": res[0], "rect": res[1], "icon": (key, new_ang)})
        return True

    def duplicate_selected_image(self) -> bool:
        sel = self._img_sel
        if not sel or not self.doc or sel.get("pdf"):
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        res = at.duplicate_stamp(self.doc, sel["page"], sel["xref"])
        if not res:
            return False
        self._on_dirty()
        self.refresh_page(sel["page"])
        self._img_select({"page": sel["page"], "xref": res[0], "rect": res[1], "icon": sel.get("icon")})
        return True

    def delete_selected_image(self) -> bool:
        sel = self._img_sel
        if not sel or not self.doc:
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = (at.delete_pdf_image(self.doc, sel["page"], sel["rect"]) if sel.get("pdf")
              else at.delete_stamp(self.doc, sel["page"], sel["xref"]))
        self._img_select(None)
        if ok:
            self._on_dirty()
            self.refresh_page(sel["page"])
        return ok

    def contextMenuEvent(self, e):
        if self.doc is not None and self._cols == 1 and self._editor is None and self.mode in ("edit", "shape"):
            sp_ = self.mapToScene(e.pos())
            pi = self._page_at_y(sp_.y(), quiet=True)
            hit = at.editable_at(self.doc, pi, self._mk_pdf_point(sp_, pi)) if pi is not None else None
            if hit and hit["kind"] == "ink":
                menu = QMenu(self)
                menu.addAction(ic.icon("signature", TEXT, 16), "Guardar como firma…",
                               lambda: self.save_signature_requested.emit(hit))
                menu.addAction(ic.icon("trash", TEXT, 16), "Eliminar este dibujo",
                               lambda: (self._ss_select(pi, hit), self.delete_selection()))
                menu.exec(e.globalPos())
                e.accept()
                return
        if self.mode == "edit" and self._editor is None and self.doc is not None:
            sp0 = self.mapToScene(e.pos())
            item = next((it for it in self.scene_.items(sp0) if isinstance(it, SpanRectItem) and it.kind == "edit"), None)
            if item is not None:
                pt = self._mk_pdf_point(sp0, item.page_idx)
                word = self._word_at(item.page_idx, pt)
                whole = " ".join(str(item.span.get("text", "")).split())
                menu = QMenu(self)
                a_edit = menu.addAction(ic.icon("pencil", TEXT, 16), "Editar este texto")
                a_edit.triggered.connect(lambda _=False, it=item: self._open_inline_editor(it))
                menu.addSeparator()
                if word:
                    menu.addAction(ic.icon("swap", TEXT, 16), f"Reemplazar «{word}»…").triggered.connect(
                        lambda _=False, w=word: self.replace_requested.emit(w))
                if whole and whole != word:
                    shown = whole if len(whole) <= 36 else whole[:34] + "…"
                    menu.addAction(ic.icon("swap", TEXT, 16), f"Reemplazar «{shown}»…").triggered.connect(
                        lambda _=False, w=whole: self.replace_requested.emit(w))
                menu.exec(e.globalPos())
                e.accept()
                return
        if self.mode == "form":
            sp_ = self.mapToScene(e.pos())
            pi = self._page_at_y(sp_.y())
            w = self._fm_hit(pi, self._mk_pdf_point(sp_, pi)) if pi is not None else None
            if w:
                m = QMenu(self)
                m.addAction("Rellenar / cambiar", lambda: self._fm_activate(pi, w, sp_))
                m.addAction("Eliminar campo «%s»" % w["name"], lambda: self.delete_field(pi, w["xref"]))
                m.exec(e.globalPos())
            e.accept()
            return
        if self.mode == "image" and self._img_sel:
            m = QMenu(self)
            if self._img_sel.get("icon"):
                m.addAction("Cambiar de icono…", self.icon_picker_requested.emit)
                m.addAction("Girar 15° a la izquierda\t[", lambda: self.rotate_selected_icon(-15))
                m.addAction("Girar 15° a la derecha\t]", lambda: self.rotate_selected_icon(15))
                m.addSeparator()
            m.addAction("Duplicar	Ctrl+D", self.duplicate_selected_image)
            m.addAction("Eliminar	Supr", self.delete_selected_image)
            m.exec(e.globalPos())
            e.accept()
            return
        if self.mode == "shape" and self._ss_sel:
            m = QMenu(self)
            m.addAction("Duplicar\tCtrl+D", self.duplicate_selection)
            m.addAction("Eliminar\tSupr", self.delete_selection)
            m.exec(e.globalPos())
            e.accept()
            return
        super().contextMenuEvent(e)

    def keyPressEvent(self, e):
        if self.mode == "shape":
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._ss_sel:
                self.delete_selection()
                e.accept()
                return
            if e.key() == Qt.Key_D and (e.modifiers() & Qt.ControlModifier) and self._ss_sel:
                self.duplicate_selection()
                e.accept()
                return
            if e.key() == Qt.Key_Escape:
                if self._ss_sel:
                    self._ss_select(None, None)
                else:
                    self.set_mode("edit")
                e.accept()
                return
        if self.mode in ("note", "attach", "copy") and e.key() == Qt.Key_Escape:
            self.set_mode("edit")
            e.accept()
            return
        if self.mode == "form" and e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._fm_sel \
                and self._fm_editor is None:
            sel, self._fm_sel = self._fm_sel, None
            self.delete_field(sel["page"], sel["xref"])
            e.accept()
            return
        if self.mode == "form" and e.key() == Qt.Key_Escape:
            self.set_mode("edit")
            e.accept()
            return
        if self.mode == "image" and self._img_sel and self._img_sel.get("icon") and e.key() in (Qt.Key_BracketLeft,
                                                                                               Qt.Key_BracketRight):
            self.rotate_selected_icon(-15 if e.key() == Qt.Key_BracketLeft else 15)
            e.accept()
            return
        if self.mode == "link" and e.key() == Qt.Key_Escape:
            self.set_mode("edit")
            e.accept()
            return
        if self.mode == "image":
            if e.key() == Qt.Key_D and (e.modifiers() & Qt.ControlModifier) and self._img_sel:
                self.duplicate_selected_image()
                e.accept()
                return
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._img_sel:
                self.delete_selected_image()
                e.accept()
                return
            if e.key() == Qt.Key_Escape:
                if self.pending_image is not None or self._img_sel:
                    self.pending_image = None
                    self._img_select(None)
                else:
                    self.set_mode("edit")
                e.accept()
                return
        super().keyPressEvent(e)

    # ── Seleccionar, mover, escalar, duplicar y borrar lo dibujado desde el editor ──
    def _ss_select(self, page_idx, desc):
        self._img_select(None)                    # quita marco y tiradores anteriores
        self._ss_sel = None if desc is None else {"page": page_idx, "desc": desc}
        if desc is not None:
            self._ss_draw(page_idx, desc)
        self._update_sel_bar()

    def _update_sel_bar(self):
        """Coloca las opciones justo encima de la forma seleccionada (o las oculta)."""
        bar = getattr(self, "_sel_bar", None)
        if bar is None:
            return
        sel = self._ss_sel
        if not sel or self.mode != "shape" or self._ss_drag is not None:
            bar.hide()
            return
        d, page_idx = sel["desc"], sel["page"]
        z, top = self.zoom, self._page_tops[page_idx]
        if d["kind"] in ("line", "arrow"):
            xs = [d["p0"][0], d["p1"][0]]; ys = [d["p0"][1], d["p1"][1]]
            x0, x1, y0 = min(xs), max(xs), min(ys)
        else:
            x0, y0, x1, _y1 = d["bbox"]
        bar.refresh(d)
        cx = (x0 + x1) / 2 * z
        pt = self.mapFromScene(QPointF(cx, top + y0 * z))
        x = int(pt.x() - bar.width() / 2)
        y = int(pt.y() - bar.height() - 34)          # por encima del tirador de giro
        if y < 2:
            y = int(self.mapFromScene(QPointF(cx, top + (d["bbox"][3] if "bbox" in d else y0) * z)).y() + 14)
        x = max(4, min(x, self.viewport().width() - bar.width() - 4))
        bar.move(x, max(2, y))
        bar.show()
        bar.raise_()

    def _ss_draw(self, page_idx, d):
        for it in self._img_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._img_items = []
        z, top = self.zoom, self._page_tops[page_idx]
        pen = QPen(QColor(ACCENT), 1.5, Qt.DashLine)
        hs = self._HANDLE
        if d["kind"] in ("line", "arrow"):
            a, b = d["p0"], d["p1"]
            fr = self.scene_.addLine(a[0] * z, top + a[1] * z, b[0] * z, top + b[1] * z, pen)
        else:
            x0, y0, x1, y1 = d["bbox"]
            fr = self.scene_.addRect(QRectF(x0 * z, top + y0 * z, (x1 - x0) * z, (y1 - y0) * z), pen, QBrush(Qt.NoBrush))
        fr.setZValue(60)
        self._img_items.append(fr)
        for name, (hx, hy) in at.handles_of(d).items():
            if name == "rot":
                x0, y0, x1, y1 = d["bbox"]
                cord = self.scene_.addLine((x0 + x1) / 2 * z, top + y0 * z, hx * z, top + hy * z, QPen(QColor(ACCENT), 1.2))
                cord.setZValue(60)
                self._img_items.append(cord)
                hd = self.scene_.addEllipse(QRectF(hx * z - hs / 2 - 1, top + hy * z - hs / 2 - 1, hs + 2, hs + 2),
                                            QPen(QColor(ACCENT), 1.5), QBrush(QColor("#FFFFFF")))
            else:
                hd = self.scene_.addRect(QRectF(hx * z - hs / 2, top + hy * z - hs / 2, hs, hs), QPen(QColor(ACCENT)),
                                         QBrush(QColor("#FFFFFF")))
            hd.setZValue(61)
            self._img_items.append(hd)

    def _ss_handle_at(self, scene_pos: QPointF):
        if not self._ss_sel:
            return None
        z, top = self.zoom, self._page_tops[self._ss_sel["page"]]
        tol = self._HANDLE + 4
        for name, (hx, hy) in at.handles_of(self._ss_sel["desc"]).items():
            if abs(scene_pos.x() - hx * z) <= tol and abs(scene_pos.y() - (top + hy * z)) <= tol:
                return name
        return None

    def _ss_press(self, scene_pos: QPointF, page_idx: int, pt: tuple, allow_pick: bool) -> bool:
        """True si el clic se ha usado para seleccionar / mover / escalar algo ya dibujado."""
        sel = self._ss_sel
        if sel and sel["page"] == page_idx:
            h = self._ss_handle_at(scene_pos)
            if h:
                self._ss_drag = {"op": h, "start": pt, "page": page_idx, "desc": sel["desc"], "geom": None}
                return True
        if sel and sel["page"] == page_idx and sel["desc"]["kind"] == "ink":
            x0, y0, x1, y1 = sel["desc"]["bbox"]                  # un trazo fino se agarra desde todo su recuadro
            if x0 - 6 <= pt[0] <= x1 + 6 and y0 - 6 <= pt[1] <= y1 + 6:
                self._ss_drag = {"op": "move", "start": pt, "page": page_idx, "desc": sel["desc"], "geom": None}
                self.viewport().setCursor(Qt.SizeAllCursor)
                return True
        if allow_pick:
            hit = at.editable_at(self.doc, page_idx, pt, edge_only=self.shape_kind != "select")
            if hit:
                self._ss_select(page_idx, hit)
                self._ss_drag = {"op": "move", "start": pt, "page": page_idx, "desc": hit, "geom": None}
                self.viewport().setCursor(Qt.SizeAllCursor)
                return True
            self._ss_select(None, None)
        return self.shape_kind == "select"

    def _ss_compute(self, drag, pt, shift):
        d, op = drag["desc"], drag["op"]
        if op == "move":
            return at.shifted_geom(d, pt[0] - drag["start"][0], pt[1] - drag["start"][1])
        if op == "rot":
            import math
            cx, cy = at.center_of(d)
            a0 = math.atan2(drag["start"][1] - cy, drag["start"][0] - cx)
            a1 = math.atan2(pt[1] - cy, pt[0] - cx)
            delta = math.degrees(a1 - a0)
            if shift:
                delta = round(delta / 15.0) * 15.0
            return at.rotate_geom(d, delta, (cx, cy))
        if d["kind"] in ("line", "arrow"):
            other = d["p1"] if op == "a" else d["p0"]
            np_ = at.snap_points(other, pt, "line") if shift else pt
            return {"p0": np_, "p1": other} if op == "a" else {"p0": other, "p1": np_}
        x0, y0, x1, y1 = d["bbox"]
        anchor = {"nw": (x1, y1), "ne": (x0, y1), "sw": (x1, y0), "se": (x0, y0)}[op]
        if shift:
            nb = self._img_aspect_rect(anchor, pt, (x1 - x0) / max(y1 - y0, 1e-3))
        else:
            nb = (min(anchor[0], pt[0]), min(anchor[1], pt[1]), max(anchor[0], pt[0]), max(anchor[1], pt[1]))
            if nb[2] - nb[0] < 4:
                nb = (nb[0], nb[1], nb[0] + 4, nb[3])
            if nb[3] - nb[1] < 4 and d["kind"] != "ink":
                nb = (nb[0], nb[1], nb[2], nb[1] + 4)
        return at.scaled_geom(d, nb)

    def _ss_ghost(self, page_idx, d, geom):
        """Vista previa mientras se arrastra: la forma en su nueva posición y el marco con tiradores."""
        tmp = at.with_geom(d, geom)
        self._sh_page = page_idx
        z, top = self.zoom, self._page_tops[page_idx]
        names = at.SHAPE_COLORS
        cname = self._sh_color_name(d["stroke"])
        if tmp["kind"] == "poly":
            for it in self._sh_preview:
                self.scene_.removeItem(it)
            self._sh_preview = []
            r, g, b = (int(c * 255) for c in (d["stroke"] or at.rgb_of(cname)))
            path = QPainterPath(QPointF(tmp["pts"][0][0] * z, top + tmp["pts"][0][1] * z))
            for x, y in tmp["pts"][1:]:
                path.lineTo(x * z, top + y * z)
            path.closeSubpath()
            fillc = d.get("fill")
            brush = QBrush(QColor(*(int(c * 255) for c in fillc), 120)) if fillc else QBrush(Qt.NoBrush)
            it = self.scene_.addPath(path, QPen(QColor(r, g, b), max(1.0, d["width"] * z)), brush)
            it.setZValue(50)
            self._sh_preview.append(it)
        elif tmp["kind"] == "ink":
            for it in self._sh_preview:
                self.scene_.removeItem(it)
            self._sh_preview = []
            r, g, b = (int(c * 255) for c in (d["stroke"] or at.rgb_of(cname)))
            pen = QPen(QColor(r, g, b, 100 if d.get("marker") else 255), max(1.0, d["width"] * z))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            for st in tmp["strokes"]:
                if len(st) < 2:
                    continue
                path = QPainterPath(QPointF(st[0][0] * z, top + st[0][1] * z))
                for x, y in st[1:]:
                    path.lineTo(x * z, top + y * z)
                it = self.scene_.addPath(path, pen)
                it.setZValue(50)
                self._sh_preview.append(it)
        else:
            fill = self._sh_color_name(d["fill"]) if d.get("fill") and tmp["kind"] in ("rect", "ellipse") else None
            self._sh_draw_preview(tmp["kind"], tmp["p0"], tmp["p1"], cname, d["width"], fill)
        self._ss_draw(page_idx, tmp)

    def _ss_move_evt(self, scene_pos: QPointF, shift: bool):
        drag = self._ss_drag
        if not drag:
            h = self._ss_handle_at(scene_pos)
            cur = {"nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor, "ne": Qt.SizeBDiagCursor,
                   "sw": Qt.SizeBDiagCursor, "a": Qt.CrossCursor, "b": Qt.CrossCursor, "rot": Qt.PointingHandCursor}.get(h)
            self.viewport().setCursor(cur or (Qt.ArrowCursor if self.shape_kind == "select" else Qt.CrossCursor))
            return False
        pt = self._mk_pdf_point(scene_pos, drag["page"])
        if abs(pt[0] - drag["start"][0]) < 1.5 and abs(pt[1] - drag["start"][1]) < 1.5 and drag["geom"] is None:
            return True
        drag["geom"] = self._ss_compute(drag, pt, shift)
        self._sel_bar.hide()
        self._ss_ghost(drag["page"], drag["desc"], drag["geom"])
        return True

    def _ss_release(self, scene_pos: QPointF, shift: bool):
        drag, self._ss_drag = self._ss_drag, None
        page_idx, d = drag["page"], drag["desc"]
        pt = self._mk_pdf_point(scene_pos, page_idx)
        self._sh_clear()
        self.viewport().setCursor(Qt.ArrowCursor if self.shape_kind == "select" else Qt.CrossCursor)
        if drag["geom"] is None:
            self._ss_select(page_idx, d)
            return
        geom = self._ss_compute(drag, pt, shift)
        if self._on_before_mutate:
            self._on_before_mutate()
        new = at.rebuild(self.doc, page_idx, d, geom)
        if new:
            self._on_dirty()
            self.refresh_page(page_idx)
        self._ss_select(page_idx, new or d)

    def duplicate_selection(self):
        sel = self._ss_sel
        if not sel or not self.doc:
            return False
        d, page_idx = sel["desc"], sel["page"]
        if self._on_before_mutate:
            self._on_before_mutate()
        new = at.rebuild(self.doc, page_idx, d, at.shifted_geom(d, 14, 14), delete_old=False)
        if new:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._ss_select(page_idx, new)
        return bool(new)

    def delete_selection(self):
        sel = self._ss_sel
        if not sel or not self.doc:
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = at.delete_editable(self.doc, sel["page"], sel["desc"]["xref"])
        self._ss_select(None, None)
        if ok:
            self._on_dirty()
            self.refresh_page(sel["page"])
        return ok

    def restyle_selection(self, color=None, width=None, fill=None, opacity=None, head=None,
                          stroke_op=None, fill_op=None):
        """Cambia color, grosor, relleno, opacidad del relleno o punta de lo seleccionado (fill=\"\" quita el relleno)."""
        sel = self._ss_sel
        if not sel or not self.doc:
            return False
        d, page_idx = sel["desc"], sel["page"]
        style = {}
        if color:
            style["stroke"] = at.rgb_of(color)
            if d["kind"] == "arrow":
                style["fill"] = at.rgb_of(color)
        if width:
            style["width"] = width * (5 if d.get("marker") else 1)
        if fill is not None and d["kind"] in ("rect", "ellipse", "poly"):
            style["fill"] = at.rgb_of(fill) if fill else None
        if opacity is not None or stroke_op is not None or fill_op is not None:
            s_cur = d.get("opacity", 1.0)
            f_cur = d.get("fill_opacity", s_cur)
            s_new, f_new = s_cur, f_cur
            if opacity is not None:                       # total: trazo y relleno
                s_new = f_new = float(opacity)
            if stroke_op is not None:
                s_new = float(stroke_op)
            if fill_op is not None:
                f_new = float(fill_op)
            style["opacity"], style["fill_opacity"] = s_new, f_new
        if head and d["kind"] == "arrow":
            style["head"] = head
        if not style:
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        new = at.rebuild(self.doc, page_idx, d, at.geom_of(d), style=style)
        if new:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._ss_select(page_idx, new)
        return bool(new)

    # ── Modo formas: rectángulo, elipse, línea, flecha (y mover las ya dibujadas) ──
    def _sh_clear(self):
        for it in self._sh_preview:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._sh_preview = []
        self._sh_start = self._sh_page = self._sh_move = None
        self._sh_stroke = []

    def _sh_draw_preview(self, kind, p0, p1, color, width, fill):
        for it in self._sh_preview:
            self.scene_.removeItem(it)
        self._sh_preview = []
        top = self._page_tops[self._sh_page]
        z = self.zoom
        r, g, b = (int(c * 255) for c in (at.rgb_of(color) or at.SHAPE_COLORS["rojo"]))
        pen = QPen(QColor(r, g, b), max(1.0, width * z))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        if kind in ("pen", "marker"):
            pts = self._sh_stroke
            path = QPainterPath(QPointF(pts[0][0] * z, top + pts[0][1] * z))
            for x, y in pts[1:]:
                path.lineTo(x * z, top + y * z)
            if kind == "marker":
                pen.setWidthF(max(1.0, width * 5 * z))
                pen.setColor(QColor(r, g, b, 100))
            it = self.scene_.addPath(path, pen)
            it.setZValue(50)
            self._sh_preview.append(it)
            return
        a = QPointF(p0[0] * z, top + p0[1] * z)
        c = QPointF(p1[0] * z, top + p1[1] * z)
        if kind in ("rect", "ellipse"):
            brush = QBrush(QColor(*(int(v * 255) for v in at.rgb_of(fill)), int(255 * (self.shape_fill_op if self.shape_fill_op is not None else self.shape_opacity)))) if fill else QBrush(Qt.NoBrush)
            box = QRectF(a, c).normalized()
            it = (self.scene_.addRect(box, pen, brush) if kind == "rect" else self.scene_.addEllipse(box, pen, brush))
            self._sh_preview.append(it)
        else:
            self._sh_preview.append(self.scene_.addLine(a.x(), a.y(), c.x(), c.y(), pen))
            if kind == "arrow":
                import math
                ang = math.atan2(c.y() - a.y(), c.x() - a.x())
                size = max(10.0, width * z * 4)
                for da in (2.6, -2.6):
                    self._sh_preview.append(self.scene_.addLine(
                        c.x(), c.y(), c.x() + size * math.cos(ang + da), c.y() + size * math.sin(ang + da), pen))
        for it in self._sh_preview:
            it.setZValue(50)

    def _sh_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        if self._ss_press(scene_pos, page_idx, pt, allow_pick=self.shape_kind not in ("pen", "marker")):
            return
        self._sh_page, self._sh_start = page_idx, pt
        if self.shape_kind in ("pen", "marker"):
            self._sh_stroke = [pt]
            self._sh_pressures = [self._pressure] if self._pressure else []
            return

    def _sh_current(self, scene_pos: QPointF, shift: bool):
        pt = self._mk_pdf_point(scene_pos, self._sh_page)
        if self._sh_move is None and shift:
            pt = at.snap_points(self._sh_start, pt, self.shape_kind)
        return pt

    def _sh_move_evt(self, scene_pos: QPointF, shift: bool):
        if self._sh_start is None:
            return
        if self.shape_kind in ("pen", "marker"):
            pt = self._mk_pdf_point(scene_pos, self._sh_page)
            last = self._sh_stroke[-1]
            if (pt[0] - last[0]) ** 2 + (pt[1] - last[1]) ** 2 >= 0.6:
                self._sh_stroke.append(pt)
                if self._pressure:
                    self._sh_pressures.append(self._pressure)
                self._sh_draw_preview(self.shape_kind, None, None, self.shape_color, self.shape_width, None)
            return
        pt = self._sh_current(scene_pos, shift)
        if self._sh_move:
            d = self._sh_move
            dx, dy = pt[0] - self._sh_start[0], pt[1] - self._sh_start[1]
            self._sh_draw_preview(d["kind"], (d["p0"][0] + dx, d["p0"][1] + dy), (d["p1"][0] + dx, d["p1"][1] + dy),
                                  self._sh_color_name(d["stroke"]), d["width"], None)
        else:
            self._sh_draw_preview(self.shape_kind, self._sh_start, pt, self.shape_color, self.shape_width,
                                  self.shape_fill)

    @staticmethod
    def _sh_color_name(rgb):
        return tuple(rgb) if rgb else "negro"

    def _sh_release(self, scene_pos: QPointF, shift: bool):
        if self._sh_start is None:
            return
        page_idx, start, moving = self._sh_page, self._sh_start, self._sh_move
        if self.shape_kind in ("pen", "marker"):
            stroke = list(self._sh_stroke)
            self._sh_clear()
            if len(stroke) >= 2:
                if self._on_before_mutate:
                    self._on_before_mutate()
                width = self.shape_width
                if self._sh_pressures:                     # lápiz óptico: la presión media da el grosor (0,5x a 1,5x)
                    width *= 0.5 + sum(self._sh_pressures) / len(self._sh_pressures)
                self._sh_pressures = []
                if at.add_ink(self.doc, page_idx, stroke, self.shape_color, width,
                              marker=self.shape_kind == "marker"):
                    self._on_dirty()
                    self.refresh_page(page_idx)
            return
        pt = self._sh_current(scene_pos, shift)
        self._sh_clear()
        self.viewport().setCursor(Qt.CrossCursor)
        dx, dy = pt[0] - start[0], pt[1] - start[1]
        if abs(dx) < 2 and abs(dy) < 2:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        if moving:
            ok = at.move_shape(self.doc, page_idx, moving, dx, dy)
        else:
            ok = at.add_shape(self.doc, page_idx, self.shape_kind, start, pt, self.shape_color,
                              self.shape_width, self.shape_fill, self.shape_opacity, self.shape_head,
                              self.shape_stroke_op, self.shape_fill_op)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            if not moving:
                # una forma por vez: se acaba el dibujo y queda seleccionada, con sus opciones encima
                self.shape_kind = "select"
                self.shape_kind_changed.emit("select")
                self.viewport().setCursor(Qt.ArrowCursor)
                self._ss_select(page_idx, at.last_editable(self.doc, page_idx))

    # ── Modo marcar: resaltar, subrayar, tachar, quitar marca ───────────
    def _mk_clear_preview(self):
        for it in self._mk_preview:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._mk_preview = []
        self._mk_start = None
        self._mk_page = None

    def _mk_pdf_point(self, scene_pos: QPointF, page_idx: int) -> tuple:
        return (scene_pos.x() / self.zoom, (scene_pos.y() - self._page_tops[page_idx]) / self.zoom)

    def _mk_color_rgb(self):
        name = self.markup_color or at.DEFAULT_COLOR.get(self.markup_kind, "amarillo")
        return at.COLORS.get(name, at.COLORS["amarillo"])

    def _mk_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        if self.markup_kind == "erase":
            if not at.remove_markup_at(self.doc, page_idx, pt, dry=True):
                if self._on_notice:
                    self._on_notice("No hay ninguna marca ahí.")
                return
            if self._on_before_mutate:
                self._on_before_mutate()
            at.remove_markup_at(self.doc, page_idx, pt)
            self._on_dirty()
            self.refresh_page(page_idx)
            return
        self._mk_page, self._mk_start = page_idx, pt
        self._mk_words = at.page_words(self.doc, page_idx)

    def _mk_selection(self, scene_pos: QPointF):
        pt = self._mk_pdf_point(scene_pos, self._mk_page)
        idx = at.select_words(self._mk_words, self._mk_start, pt)
        return at.line_rects(self._mk_words, idx)

    def _mk_move(self, scene_pos: QPointF):
        if self._mk_start is None:
            return
        for it in self._mk_preview:
            self.scene_.removeItem(it)
        self._mk_preview = []
        r, g, b = (int(c * 255) for c in self._mk_color_rgb())
        top = self._page_tops[self._mk_page]
        for rect in self._mk_selection(scene_pos):
            qr = QRectF(rect.x0 * self.zoom, top + rect.y0 * self.zoom,
                        (rect.x1 - rect.x0) * self.zoom, (rect.y1 - rect.y0) * self.zoom)
            if self.markup_kind == "highlight":
                it = self.scene_.addRect(qr, QPen(Qt.NoPen), QBrush(QColor(r, g, b, 110)))
            else:
                y = qr.bottom() - 2 if self.markup_kind == "underline" else qr.center().y()
                it = self.scene_.addLine(qr.left(), y, qr.right(), y, QPen(QColor(r, g, b), 2))
            it.setZValue(50)
            self._mk_preview.append(it)

    def _mk_release(self, scene_pos: QPointF):
        if self._mk_start is None:
            return
        page_idx = self._mk_page
        rects = self._mk_selection(scene_pos)
        self._mk_clear_preview()
        if not rects:
            if self._on_notice:
                self._on_notice("Arrastra sobre el texto que quieras marcar.")
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        if at.add_markup(self.doc, page_idx, rects, self.markup_kind, self.markup_color):
            self._on_dirty()
            self.refresh_page(page_idx)

    def load_doc(self, doc):
        """Renderiza el documento entero, una página debajo de otra."""
        self._close_inline_editor(commit=False)
        self.doc = doc
        self.scene_.clear()
        self._page_items = []
        self._page_span_items = []
        self._page_tops = []
        self._img_items, self._img_sel, self._img_drag = [], None, None      # la escena se vació
        self._edit_cover = None
        self._ss_sel, self._ss_drag = None, None
        self._sel_bar.hide()
        self._sh_preview, self._mk_preview, self._lk_items = [], [], []
        self._fm_items, self._fm_cache, self._fm_editor, self._fm_down, self._fm_rubber = [], {}, None, None, None
        self._fm_sel = None
        self._cp_down, self._cp_rubber = None, None
        if not doc:
            return
        cols = self._calc_cols()
        self._cols = cols
        gap_x = 24.0
        cell_w = max(doc[i].rect.width for i in range(len(doc))) * self.zoom
        x0 = max(0.0, (self.viewport().width() - (cols * (cell_w + gap_x) - gap_x)) / 2) if cols > 1 else 0.0
        y = float(self._page_gap - 8)
        max_w = 0.0
        row_h = 0.0
        pending_bars = []
        for page_idx in range(len(doc)):
            png = be.render_doc_page_png(doc, page_idx, zoom=self.zoom, annots=not self.hide_annots)
            if not png:
                continue
            pix = QPixmap()
            pix.loadFromData(png)
            col = page_idx % cols
            if col == 0 and page_idx > 0:
                y += row_h + self._page_gap
                row_h = 0.0
            px = x0 + col * (cell_w + gap_x) + ((cell_w - pix.width()) / 2 if cols > 1 else 0.0)
            pending_bars.append((page_idx, y, pix.width(), px))
            pm_item = self.scene_.addPixmap(pix)
            pm_item.setPos(px, y)
            self._page_items.append(pm_item)
            self._page_tops.append(y)
            row_h = max(row_h, float(pix.height()))
            max_w = max(max_w, px + pix.width())
            self._page_span_items.append(self._build_spans(doc, page_idx, y))
        end_y = y + row_h + 8
        for page_idx, top, w, px in pending_bars:
            self._add_page_bar(page_idx, top, w, max_w, px=px)
        if cols > 1:                                   # «+» en los huecos entre páginas
            cb = lambda a, i: self.page_action.emit(a, i)
            for k, (page_idx, top, w, px) in enumerate(pending_bars):
                h = self._page_items[k].pixmap().height()
                if k == 0:
                    g = GutterPlusItem(0, cb)
                    g.setPos(px - 12 - GutterPlusItem.D / 2 - 6, top + h / 2 - GutterPlusItem.D / 2)
                    g.setZValue(60); self.scene_.addItem(g)
                g = GutterPlusItem(page_idx + 1, cb)
                g.setPos(px + w + 12 - GutterPlusItem.D / 2 + (6 if (page_idx % cols) == cols - 1 else 0),
                         top + h / 2 - GutterPlusItem.D / 2)
                g.setZValue(60); self.scene_.addItem(g)
        else:
            self._add_page_bar(len(doc), end_y + 10 + self._bar_h + 6, 0, max_w, last=True)
        self.scene_.setSceneRect(0, 0, max_w, end_y + 10 + self._bar_h + 24)
        self._current_page = 0
        self._lk_refresh()
        self._fm_refresh()
        if self._on_page_visible:
            self._on_page_visible(0, len(self._page_items))

    def _calc_cols(self) -> int:
        """Páginas por fila: con mucho zoom una; si se aleja tanto que caben varias, se reparten en filas."""
        if not self.doc or len(self.doc) < 2:
            return 1
        cell = max(self.doc[i].rect.width for i in range(len(self.doc))) * self.zoom + 24.0
        avail = self.viewport().width() - 12 - 2 * 30          # hueco a los lados para los «+»
        return max(1, min(len(self.doc), int((avail + 24.0) // cell)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.doc is not None and self._page_items and self._calc_cols() != self._cols:
            QTimer.singleShot(0, self._relayout_if_needed)

    def _relayout_if_needed(self):
        if self.doc is not None and self._calc_cols() != self._cols:
            self.reload_preserving_scroll()

    def _overview_click(self, scene_pos: QPointF):
        """Con varias páginas por fila (vista general): un clic en una página la acerca para trabajar en ella."""
        for i, it in enumerate(self._page_items):
            if it.sceneBoundingRect().contains(scene_pos):
                self.fit_width()
                self.scroll_to_page(i)
                if self._on_notice:
                    self._on_notice("Vista general: has acercado la página %d para poder editarla." % (i + 1))
                return

    def _add_page_bar(self, idx: int, top: float, page_w: float, max_w: float, last: bool = False, px: float = 0.0):
        """Barra encima de cada página (y una al final) para borrar, girar, acercar o insertar una página."""
        w = page_w if page_w else max_w
        item = PageBarItem(idx, last, lambda a, i: self.page_action.emit(a, i), compact=self._cols > 1)
        if last and self._cols > 1:
            px = 0.0
        item.setPos(px + max(0.0, (w - item.width_) / 2), top - self._bar_h - 6)
        item.setZValue(60)
        self.scene_.addItem(item)

    def _build_spans(self, doc, page_idx: int, y_offset: float) -> list:
        """Zonas clicables: un párrafo entero para editar y, para censurar,
        cada fragmento de texto por separado (solo se ve la de su modo)."""
        items = []
        if self._is_rotated(page_idx) or self._cols > 1:
            return items
        for kind, source in (("edit", be.get_page_paragraphs(doc, page_idx, manual=self.manual)),
                             ("censor", be.get_page_text_spans(doc, page_idx))):
            for span in source:
                x0, y0, x1, y1 = span["bbox"]
                rect = QRectF(x0 * self.zoom, y_offset + y0 * self.zoom,
                               (x1 - x0) * self.zoom, (y1 - y0) * self.zoom)
                item = SpanRectItem(rect, span, page_idx, self._open_inline_editor,
                                     mode_provider=lambda: self.mode)
                item.kind = kind
                item.setVisible(kind == self.mode)
                self.scene_.addItem(item)
                items.append(item)
        return items

    def reload_preserving_scroll(self):
        vbar = self.verticalScrollBar()
        val = vbar.value()
        self.load_doc(self.doc)
        vbar.setValue(val)

    def refresh_page(self, page_idx: int):
        """Vuelve a renderizar SOLO la página indicada (tras una edición o
        censura), sin tocar el resto del documento: mucho más rápido que
        recargarlo entero en PDFs de muchas páginas."""
        if not self.doc or not (0 <= page_idx < len(self._page_items)):
            self.reload_preserving_scroll()
            return
        png = be.render_doc_page_png(self.doc, page_idx, zoom=self.zoom, annots=not self.hide_annots)
        if not png:
            return
        pix = QPixmap()
        pix.loadFromData(png)
        self._page_items[page_idx].setPixmap(pix)
        for item in self._page_span_items[page_idx]:
            self.scene_.removeItem(item)
        self._page_span_items[page_idx] = self._build_spans(
            self.doc, page_idx, self._page_tops[page_idx])

    def scroll_to_page(self, idx: int):
        if not self._page_items:
            return
        idx = max(0, min(idx, len(self._page_items) - 1))
        top = self._page_tops[idx]
        self.verticalScrollBar().setValue(max(0, int(top - self._bar_h - 8)))

    def _update_current_page(self, _value=None):
        if not self._page_tops:
            return
        top_y = self.mapToScene(0, 4).y()
        idx = 0
        for i, t in enumerate(self._page_tops):
            if t - self._bar_h - 8 <= top_y + 2:
                idx = i
            else:
                break
        if idx != self._current_page:
            self._current_page = idx
            if self._on_page_visible:
                self._on_page_visible(idx, len(self._page_items))

    # ── Modo censurar: clic o clic-y-arrastre sobre el área a tapar ─────
    def tabletEvent(self, e):
        """Lápiz óptico: guarda la presión (grosor del trazo) y usa el extremo borrador para borrar dibujos libres.
        El resto sigue como ratón (Qt genera los eventos de ratón si aquí no se acepta)."""
        from PySide6.QtGui import QPointingDevice
        ptype = e.pointerType()
        if ptype == QPointingDevice.PointerType.Eraser:
            if (self.doc is not None and self._cols == 1 and self.mode in ("edit", "shape")
                    and self._editor is None and e.pressure() > 0):
                sp_ = self.mapToScene(e.position().toPoint())
                pi = self._page_at_y(sp_.y(), quiet=True)
                hit = at.editable_at(self.doc, pi, self._mk_pdf_point(sp_, pi)) if pi is not None else None
                if hit and hit["kind"] == "ink":
                    self._ss_sel = {"page": pi, "desc": hit}
                    self.delete_selection()
            e.accept()
            return
        self._pressure = e.pressure() if (ptype == QPointingDevice.PointerType.Pen and e.pressure() > 0) else None
        e.ignore()

    def start_eyedropper(self, callback):
        """El siguiente clic sobre una página toma ese color (se pasa a `callback` como (r, g, b) en 0..1)."""
        self._eyedrop = callback
        self.viewport().setCursor(Qt.CrossCursor)
        if self._on_notice:
            self._on_notice("Cuentagotas: haz clic en cualquier punto de la página para tomar su color.")

    def _eyedrop_pick(self, e):
        cb, self._eyedrop = self._eyedrop, None
        self.viewport().setCursor(Qt.ArrowCursor if self.mode in ("edit", "shape") else Qt.CrossCursor)
        sp0 = self.mapToScene(e.pos())
        for it in self._page_items:
            if it.sceneBoundingRect().contains(sp0):
                img = it.pixmap().toImage()
                c = img.pixelColor(int(sp0.x() - it.x()), int(sp0.y() - it.y()))
                cb((c.redF(), c.greenF(), c.blueF()))
                return

    def mousePressEvent(self, e):
        if self._eyedrop is not None and e.button() == Qt.LeftButton:
            self._eyedrop_pick(e)
            e.accept()
            return
        if isinstance(self.itemAt(e.pos()), (PageBarItem, GutterPlusItem)):
            self._bar_press = True
            super().mousePressEvent(e)
            return
        if self._cols > 1:
            if e.button() == Qt.LeftButton:
                self._overview_click(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "markup" and e.button() == Qt.LeftButton:
            self._mk_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "shape" and e.button() == Qt.LeftButton:
            self.setFocus()
            self._sh_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "image" and e.button() == Qt.LeftButton:
            self.setFocus()
            self._img_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "link" and e.button() == Qt.LeftButton:
            self._lk_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "form" and e.button() == Qt.LeftButton:
            self._fm_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode in ("note", "attach") and e.button() == Qt.LeftButton:
            self._nt_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "copy" and e.button() == Qt.LeftButton:
            self._cp_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "text" and e.button() == Qt.LeftButton:
            self._open_new_text(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "censor" and e.button() == Qt.LeftButton:
            self._censor_drag_start = self.mapToScene(e.pos())
            self._censor_rect_item = self.scene_.addRect(
                QRectF(self._censor_drag_start, self._censor_drag_start),
                QPen(Qt.NoPen), QBrush(QColor(20, 18, 12, 190)))
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._cols > 1 or self._bar_press:
            super().mouseMoveEvent(e)
            return
        if self.mode == "markup":
            self._mk_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "shape":
            if not self._ss_move_evt(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier)):
                self._sh_move_evt(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "image":
            self._img_move(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "link":
            self._lk_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "form":
            self._fm_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode in ("note", "attach"):
            self._nt_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "copy":
            self._cp_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "censor" and self._censor_drag_start is not None:
            cur = self.mapToScene(e.pos())
            self._censor_rect_item.setRect(QRectF(self._censor_drag_start, cur).normalized())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._bar_press or self._cols > 1:
            self._bar_press = False
            super().mouseReleaseEvent(e)
            return
        if self.mode == "markup" and e.button() == Qt.LeftButton:
            self._mk_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "shape" and e.button() == Qt.LeftButton:
            if self._ss_drag:
                self._ss_release(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            else:
                self._sh_release(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "image" and e.button() == Qt.LeftButton:
            self._img_release(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "link" and e.button() == Qt.LeftButton:
            self._lk_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "form" and e.button() == Qt.LeftButton:
            self._fm_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode in ("note", "attach") and e.button() == Qt.LeftButton:
            self._nt_release(self.mapToScene(e.pos()), e.globalPosition().toPoint())
            e.accept()
            return
        if self.mode == "copy" and e.button() == Qt.LeftButton:
            self._cp_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "censor" and self._censor_drag_start is not None:
            start = self._censor_drag_start
            cur = self.mapToScene(e.pos())
            self._censor_drag_start = None
            if self._censor_rect_item is not None:
                self.scene_.removeItem(self._censor_rect_item)
                self._censor_rect_item = None
            rect = QRectF(start, cur).normalized()
            if rect.width() < 4 and rect.height() < 4:
                item = self.scene_.itemAt(cur, self.transform())
                if isinstance(item, SpanRectItem):
                    self._censor_pdf_rect(item.page_idx, item.span["bbox"])
                else:
                    half_w, half_h = 55.0, 11.0
                    self._censor_scene_rect(QRectF(cur.x() - half_w, cur.y() - half_h,
                                                    half_w * 2, half_h * 2))
            else:
                self._censor_scene_rect(rect)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def _page_index(self, y: float):
        if not self._page_tops:
            return None
        idx = 0
        for i, t in enumerate(self._page_tops):
            if t <= y:
                idx = i
            else:
                break
        return idx

    def _is_rotated(self, idx) -> bool:
        try:
            return idx is not None and bool(self.doc) and self.doc[idx].rotation % 360 != 0
        except Exception:
            return False

    def _page_at_y(self, y: float, quiet: bool = False):
        """Página bajo una coordenada, para las herramientas de edición. En páginas giradas devuelve None
        (las coordenadas de edición no coinciden con lo que se ve): hay que volver a girarlas antes."""
        idx = self._page_index(y)
        if self._is_rotated(idx):
            if not quiet and self._on_notice:
                self._on_notice("Esta página está girada: para editarla, vuelve a girarla a su posición original "
                                "(botones de giro sobre la página).")
            return None
        return idx

    # ── Zoom ────────────────────────────────────────────────────────────
    def set_zoom(self, z):
        if z is None or not self.doc:
            return
        z = max(self.ZOOM_MIN, min(self.ZOOM_MAX, float(z)))
        self._zoom_pending = None
        if abs(z - self.zoom) < 0.005:
            self.zoomed.emit(self.zoom)
            return
        self._close_inline_editor(commit=True)
        self._fm_close(True)
        top_y = self.mapToScene(0, 0).y()
        pi = self._page_index(top_y) or 0
        off = (top_y - self._page_tops[pi]) / self.zoom if self._page_tops else 0.0
        hx = self.horizontalScrollBar().value() / self.zoom
        self.zoom = z
        self.load_doc(self.doc)
        if self._page_tops:
            self.verticalScrollBar().setValue(int(self._page_tops[min(pi, len(self._page_tops) - 1)] + off * z))
        self.horizontalScrollBar().setValue(int(hx * z))
        self.zoomed.emit(z)

    def zoom_by(self, factor: float):
        self.set_zoom(self.zoom * factor)

    def fit_width(self):
        if not self.doc or not len(self.doc):
            return
        pw = max(self.doc[i].rect.width for i in range(len(self.doc)))
        self.set_zoom((self.viewport().width() - 6) / max(pw, 1.0))

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            base_z = self._zoom_pending or self.zoom
            self._zoom_pending = max(self.ZOOM_MIN, min(self.ZOOM_MAX, base_z * (1.12 ** (e.angleDelta().y() / 120))))
            self._zoom_timer.start(140)
            e.accept()
            return
        super().wheelEvent(e)

    def _censor_scene_rect(self, rect: QRectF):
        """Clic-sin-span o arrastre: usa censura 'inteligente' por palabras,
        que solo tapa el texto real dentro del área (si lo hay)."""
        page_idx = self._page_at_y(rect.center().y())
        if page_idx is None:
            return
        y_off = self._page_tops[page_idx]
        bbox = (rect.x() / self.zoom, (rect.y() - y_off) / self.zoom,
                (rect.x() + rect.width()) / self.zoom, (rect.y() + rect.height() - y_off) / self.zoom)
        if not self.doc:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = be.censor_area_in_doc(self.doc, page_idx, bbox)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)

    def _censor_pdf_rect(self, page_idx: int, bbox: tuple):
        """Clic directo sobre un fragmento ya localizado: tapa exactamente
        esa caja, sin necesidad de volver a buscar texto."""
        if not self.doc:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = be.censor_rect_in_doc(self.doc, page_idx, bbox)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)

    def _open_inline_editor(self, item: SpanRectItem):
        self._close_inline_editor(commit=True)   # confirma cualquier edición pendiente
        view_rect = self.mapFromScene(item.rect()).boundingRect()
        editor = QTextEdit(self.viewport())
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.WidgetWidth)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setFrameShape(QFrame.NoFrame)
        editor.document().setDocumentMargin(0)
        editor.viewport().setAutoFillBackground(False)
        editor.setContextMenuPolicy(Qt.CustomContextMenu)
        editor.customContextMenuRequested.connect(self._editor_menu)
        self._view_rect = view_rect
        self._editor = editor
        self._editing_item = item
        self._deleting = False
        para = item.span
        # El texto se muestra con el estilo de cada tramo (negrita, color, tamaño, fuente).
        runs = para.get("runs") or [{"text": para["text"], "font": para["font"], "family": None,
                                     "bold": winfonts.style_from_ps_name(para["font"])[0],
                                     "italic": winfonts.style_from_ps_name(para["font"])[1],
                                     "size": para["size"], "color": para["color"]}]
        cur = QTextCursor(editor.document())
        for r in runs:
            fmt = self._char_format(r)
            for i, part in enumerate(r["text"].split("\n")):
                if i:
                    cur.insertBlock(QTextBlockFormat(), fmt)
                cur.insertText(part, fmt)
        editor.setCurrentCharFormat(self._char_format(runs[-1]))      # lo que se escriba lleva este estilo
        self._apply_editor_style()
        self._cover_original_text(item)
        editor.document().setModified(False)
        self._text0 = editor.toPlainText()
        editor.show()
        editor.setFocus()
        self._fit_editor()                      # ya con el ancho real, para que la altura sea exacta
        # Cursor parpadeando justo donde se hizo clic (sin seleccionar todo).
        editor.setTextCursor(editor.cursorForPosition(
            editor.viewport().mapFromGlobal(QCursor.pos())))
        editor.textChanged.connect(self._fit_editor)
        editor.cursorPositionChanged.connect(self._refresh_toolbar)
        editor.installEventFilter(self)
        self._build_toolbar()

    def _cover_original_text(self, item):
        """Tapa el texto original con la misma zona de la página SIN ese texto (fondo, dibujos e imágenes intactos):
        así el editor se ve directamente sobre la página, sin recuadro ni parches de color."""
        self._remove_cover()
        para = item.span
        if para.get("new") or not self.doc:
            return
        wrap = para["wrap_w"]
        if para["align"] == "center":
            left = (para["bbox"][0] + para["bbox"][2]) / 2 - wrap / 2
        else:
            left = para.get("body_x", para["bbox"][0])
        rect = (left, para["bbox"][1], left + wrap + 2, para["bbox"][3] + 1)
        png = be.render_text_free_clip(self.doc, item.page_idx, rect, self.zoom)
        if not png:
            return
        pm = QPixmap()
        pm.loadFromData(png)
        cover = self.scene_.addPixmap(pm)
        cover.setPos(rect[0] * self.zoom, self._page_tops[item.page_idx] + rect[1] * self.zoom)
        cover.setZValue(45)
        self._edit_cover = cover

    def _remove_cover(self):
        cover = getattr(self, "_edit_cover", None)
        self._edit_cover = None
        if cover is not None:
            try:
                self.scene_.removeItem(cover)
            except RuntimeError:
                pass

    def _word_at(self, page_idx: int, pt: tuple) -> str:
        """Palabra del PDF que hay bajo el punto (sin signos de puntuación en los extremos)."""
        try:
            words = self.doc[page_idx].get_text("words")
        except Exception:
            return ""
        best, best_d = "", 1e9
        for w in words:
            dx = max(w[0] - pt[0], 0, pt[0] - w[2])
            dy = max(w[1] - pt[1], 0, pt[1] - w[3])
            d = (dx * dx + dy * dy) ** 0.5
            if d < best_d:
                best, best_d = w[4], d
        return best.strip(" \t.,;:()[]{}«»\"'¿?¡!") if best_d < 6 else ""

    def _editor_menu(self, pos):
        """Clic derecho dentro del editor: el menú normal más «Reemplazar…» con el texto elegido ya puesto."""
        ed = self._editor
        if ed is None:
            return
        menu = ed.createStandardContextMenu()
        cur = ed.textCursor()
        sel = cur.selectedText().replace("\u2029", "\n").replace("\u2028", "\n")
        if not sel.strip():
            c2 = ed.cursorForPosition(pos)
            c2.select(QTextCursor.WordUnderCursor)
            sel = c2.selectedText()
        sel = sel.strip()
        if sel:
            menu.addSeparator()
            shown = sel if len(sel) <= 32 else sel[:30] + "…"
            act = menu.addAction(ic.icon("swap", TEXT, 16), f"Reemplazar «{shown}»…")
            act.triggered.connect(lambda _=False, s=sel: self.replace_requested.emit(s))
        menu.exec(ed.mapToGlobal(pos))

    # ── Formato de los tramos de texto ──────────────────────────────────
    _FALLBACK_FONT = "Arial"

    def _font_installed(self, ps_name: str, family: str) -> bool:
        cache = self.__dict__.setdefault("_font_ok", {})
        if ps_name not in cache:
            cache[ps_name] = (winfonts.find_font_file(ps_name)[0] is not None) or QFontDatabase.hasFamily(family)
        return cache[ps_name]

    def _ps_family(self, ps_name: str) -> str:
        fam = winfonts.guess_family_from_ps_name(ps_name)
        if fam.lower() in ("helvetica", "helv"):
            return "Arial"                                  # Windows no tiene Helvetica
        # Si la fuente no está instalada se muestra (y se guarda) con la misma de respaldo: lo que ves es lo que sale.
        return fam if self._font_installed(ps_name, fam) else self._FALLBACK_FONT

    def _char_format(self, run: dict) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamilies([run.get("family") or self._ps_family(run["font"])])
        fmt.setFontWeight(700 if run["bold"] else 400)
        fmt.setFontItalic(bool(run["italic"]))
        fmt.setProperty(QTextFormat.Property.FontPixelSize, max(6, int(round(run["size"] * self.zoom))))
        fmt.setForeground(QBrush(QColor.fromRgb(int(run["color"]) & 0xFFFFFF)))
        fmt.setProperty(_PROP_FONT, run["font"])             # fuente original del PDF
        fmt.setProperty(_PROP_SIZE, float(run["size"]))
        if run.get("family"):
            fmt.setProperty(_PROP_FAMILY, True)              # el usuario eligió otra fuente
        return fmt

    def _style_of(self, fmt: QTextCharFormat) -> dict:
        para = self._editing_item.span
        px = fmt.intProperty(QTextFormat.Property.FontPixelSize)
        fams = fmt.fontFamilies()
        fam = fams[0] if fams else self._ps_family(para["font"])
        brush = fmt.foreground()
        color = (brush.color().rgb() & 0xFFFFFF) if brush.style() != Qt.NoBrush else int(para["color"])
        ps = fmt.property(_PROP_FONT)
        exact = fmt.property(_PROP_SIZE)
        return {"font": ps if isinstance(ps, str) and ps else para["font"],
                "family": fam if fmt.property(_PROP_FAMILY) else None, "display_family": fam,
                "bold": fmt.fontWeight() >= 600, "italic": fmt.fontItalic(),
                "size": (float(exact) if isinstance(exact, (int, float)) and exact > 0
                         else round(px / self.zoom, 1) if px > 0 else para["size"]), "color": color}

    def _current_style(self) -> dict:
        return self._style_of(self._editor.currentCharFormat())

    def _collect_runs(self) -> list[dict]:
        """Texto del editor como tramos con su estilo, para guardarlo en el PDF."""
        runs: list[dict] = []

        def add(text: str, st: dict):
            if not text:
                return
            st = {k: st[k] for k in ("font", "family", "bold", "italic", "size", "color")}
            if runs and all(runs[-1][k] == st[k] for k in st):
                runs[-1]["text"] += text
            else:
                runs.append({"text": text, **st})

        blk = self._editor.document().begin()
        first, last = True, None
        while blk.isValid():
            if not first and last is not None:
                add("\n", last)
            first = False
            it = blk.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    last = self._style_of(frag.charFormat())
                    add(frag.text().replace("\u2028", "\n"), last)
                it += 1
            blk = blk.next()
        return runs

    # ── Barra flotante de formato (negrita, cursiva, tamaño, fuente, color) ─
    def _apply_editor_style(self):
        """Aspecto del editor (fondo de papel, borde) y su interlineado, ancho y posición."""
        ed = self._editor
        para = self._editing_item.span
        col = int(para["color"]) & 0xFFFFFF
        # Sin caja, sin borde y sin fondo: solo el texto y el cursor (el texto original se tapa con el propio fondo
        # de la página, ver _cover_original_text). La selección se pinta suave para que el texto siga leyéndose.
        ed.setStyleSheet(
            f"QTextEdit {{ background:transparent; color:#{col:06x}; border:none; padding:0px; "
            f"selection-background-color:rgba(192,130,88,0.38); selection-color:#{col:06x}; }}")
        pal = ed.palette()
        pal.setColor(pal.ColorRole.Text, QColor.fromRgb(col))               # el cursor toma el color del texto
        ed.setPalette(pal)
        ed.setCursorWidth(max(2, int(round(para["size"] * self.zoom * 0.07))))
        # Interlineado del PDF: así el editor ocupa la altura que tendrá el párrafo.
        base = QFont(self._ps_family(para["font"]))
        base.setPixelSize(max(6, int(round(para["size"] * self.zoom))))
        natural = max(QFontMetrics(base).lineSpacing(), 1)
        block = QTextBlockFormat()
        block.setLineHeight(max(100.0, para["pitch"] * self.zoom / natural * 100),
                            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block.setAlignment({"center": Qt.AlignHCenter, "justify": Qt.AlignJustify}.get(
            para["align"], Qt.AlignLeft))
        cur = QTextCursor(ed.document())
        cur.select(QTextCursor.Document)
        cur.mergeBlockFormat(block)
        r = self._view_rect
        pad = 0
        wrap_px = para["wrap_w"] * self.zoom
        if para["align"] == "center":
            left = r.center().x() - wrap_px / 2
        else:                                   # con etiqueta («h)», viñeta) el texto empieza a su derecha
            left = r.x() + (para.get("body_x", para["bbox"][0]) - para["bbox"][0]) * self.zoom
        self._min_h = r.height()
        ed.setGeometry(int(left - pad), int(r.y() - pad), int(wrap_px + pad * 2 + 4), int(self._min_h))
        self._fit_editor()
        self._refresh_toolbar()

    def _fit_editor(self, *_):
        """Ajusta la altura del editor al texto (el ancho es el margen de la página)."""
        ed = self._editor
        if ed is None:
            return
        ed.document().setTextWidth(ed.viewport().width())
        height = int(ed.document().size().height()) + 1
        ed.setFixedHeight(max(height, int(self._min_h)))
        self._place_toolbar()

    def _build_toolbar(self):
        tb = _ToolBar(self.viewport())
        tb.setObjectName("EditToolbar")
        # Un clic en la barra (o en un botón sin foco) le da el foco al primer
        # ancestro que lo acepte; con el editor de proxy, el foco se queda en el texto.
        tb.setFocusPolicy(Qt.ClickFocus)
        tb.setFocusProxy(self._editor)
        tb.setStyleSheet(
            f"#EditToolbar {{ background:{SURFACE_2}; border:1px solid {BORDER_STRONG}; border-radius:10px; }}"
            f"#EditToolbar QPushButton {{ background:transparent; border:none; border-radius:7px;"
            f" color:{TEXT}; min-height:30px; max-height:30px; padding:0 8px; font-size:13px; }}"
            f"#EditToolbar QPushButton:hover {{ background:rgba(243,241,228,0.10); }}"
            f"#EditToolbar QPushButton:checked {{ background:{ACCENT}; }}"
            f"#EditToolbar QFrame#Sep {{ background:{BORDER_STRONG}; }}")
        shadow = QGraphicsDropShadowEffect(tb)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 120))
        tb.setGraphicsEffect(shadow)
        lay = QHBoxLayout(tb)
        lay.setContentsMargins(5, 4, 5, 4)
        lay.setSpacing(2)

        def button(tip, icon_name=None, checkable=False, width=None):
            b = QPushButton()
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.NoFocus)          # el cursor sigue en el texto
            b.setCursor(Qt.PointingHandCursor)
            if icon_name:
                b.setIcon(_toggle_icon(icon_name))
                b.setIconSize(QSize(18, 18))
            if width:
                b.setFixedWidth(width)
            return b

        def dropdown(b):
            b.setLayoutDirection(Qt.RightToLeft)   # la flecha a la derecha del texto
            b.setIcon(ic.icon("chevron_down", TEXT_SOFT, 12))
            b.setIconSize(QSize(11, 11))
            return b

        def sep():
            s = QFrame()
            s.setObjectName("Sep")
            s.setFixedSize(1, 20)
            return s

        self._tb_font = dropdown(button("Fuente", width=134))
        self._tb_font.clicked.connect(self._open_font_popup)
        self._tb_size = dropdown(button("Tamaño del texto", width=58))
        self._tb_size.clicked.connect(self._open_size_popup)
        self._tb_bold = button("Negrita", "bold", True, 32)
        self._tb_bold.toggled.connect(lambda on: self._set_fmt("bold", on))
        self._tb_italic = button("Cursiva", "italic", True, 32)
        self._tb_italic.toggled.connect(lambda on: self._set_fmt("italic", on))
        self._tb_color = button("Color del texto", width=52)
        self._tb_color.setIconSize(QSize(34, 16))
        self._tb_color.clicked.connect(self._open_color_popup)
        trash = button("Borrar este texto", "trash", width=32)
        trash.clicked.connect(self._delete_text)
        plus = button("Añadir un elemento debajo (con su etiqueta o viñeta, y renumera los siguientes)",
                      "clip", width=32)
        plus.clicked.connect(self._insert_below)
        plus.setVisible(not self.manual and not self._editing_item.span.get("new"))

        for w in (self._tb_font, self._tb_size, sep(), self._tb_bold, self._tb_italic,
                  self._tb_color, sep(), plus, trash):
            lay.addWidget(w)
        tb.adjustSize()
        self._toolbar = tb
        self._refresh_toolbar()
        tb.show()
        self._place_toolbar()

    def _refresh_toolbar(self):
        """Pone en la barra el formato del texto bajo el cursor (o de la selección)."""
        if getattr(self, "_toolbar", None) is None or self._editor is None:
            return
        st = self._current_style()
        self._tb_font.setText(QFontMetrics(self._tb_font.font()).elidedText(
            st["display_family"], Qt.ElideRight, 100))
        self._tb_size.setText(f"{round(st['size'], 1):g}")
        for btn, key in ((self._tb_bold, "bold"), (self._tb_italic, "italic")):
            btn.blockSignals(True)
            btn.setChecked(st[key])
            btn.blockSignals(False)
        pm = QPixmap(34, 16)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 110), 1))
        p.setBrush(QColor.fromRgb(st["color"]))
        p.drawEllipse(1, 1, 14, 14)
        p.drawPixmap(20, 2, ic.icon("chevron_down", TEXT_SOFT, 12).pixmap(12, 12))
        p.end()
        self._tb_color.setIcon(QIcon(pm))

    def _popup_below(self, button, build) -> "_ToolPopup":
        pop = _ToolPopup(self.viewport())
        build(pop)
        pop.adjustSize()
        pop.move(button.mapToGlobal(QPoint(0, button.height() + 6)))
        pop.show()
        return pop

    def _choose(self, pop, key, value):
        pop.close()
        self._set_fmt(key, value)

    def _open_size_popup(self):
        size = self._current_style()["size"]

        def build(pop):
            spin = QSpinBox()
            spin.setRange(4, 300)
            spin.setSuffix(" pt")
            spin.setValue(int(round(size)))
            spin.editingFinished.connect(lambda: self._choose(pop, "size", float(spin.value())))
            lst = _popup_list(96, 230)
            current = None
            for s in (6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72, 96):
                it = QListWidgetItem(f"{s}")
                it.setData(Qt.UserRole, s)
                lst.addItem(it)
                if abs(size - s) < 0.5:
                    current = it
            if current:
                lst.setCurrentItem(current)
            lst.itemClicked.connect(lambda it: self._choose(pop, "size", float(it.data(Qt.UserRole))))
            pop.lay.addWidget(spin)
            pop.lay.addWidget(lst)
        self._popup_below(self._tb_size, build)

    def _open_font_popup(self):
        cur_family = self._current_style()["display_family"]

        def build(pop):
            search = QLineEdit()
            search.setPlaceholderText("Buscar fuente…")
            lst = _popup_list(250, 300)
            families = QFontDatabase.families()
            for fam in families:
                it = QListWidgetItem(fam)
                it.setFont(QFont(fam, 11))        # cada nombre con su propia fuente
                lst.addItem(it)
            for i in range(lst.count()):
                if lst.item(i).text() == cur_family:
                    lst.setCurrentRow(i)
                    lst.scrollToItem(lst.item(i), QAbstractItemView.PositionAtCenter)
                    break

            def filt(text):
                t = text.lower()
                for i in range(lst.count()):
                    lst.item(i).setHidden(t not in lst.item(i).text().lower())
            search.textChanged.connect(filt)
            lst.itemClicked.connect(lambda it: self._choose(pop, "family", it.text()))
            pop.lay.addWidget(search)
            pop.lay.addWidget(lst)
        self._popup_below(self._tb_font, build)

    def _open_color_popup(self):
        palette = ["#000000", "#434343", "#666666", "#999999", "#cccccc", "#ffffff",
                   "#c0392b", "#e67e22", "#f1c40f", "#27ae60", "#16a085", "#2980b9",
                   "#8e44ad", "#d81b60", "#795548", "#1f8033", "#0b5394", "#7f6000"]
        current = self._current_style()["color"]
        original = int(self._editing_item.span["color"]) & 0xFFFFFF

        def build(pop):
            grid = QGridLayout()
            grid.setSpacing(6)
            colors = [f"#{original:06x}"] + palette
            for i, hexc in enumerate(colors):
                b = _Swatch(hexc, QColor(hexc).rgb() & 0xFFFFFF == current)
                b.setToolTip("Color original" if i == 0 else hexc)
                b.clicked.connect(lambda _=False, h=hexc: self._choose(
                    pop, "color", QColor(h).rgb() & 0xFFFFFF))
                grid.addWidget(b, i // 6, i % 6)
            more = QPushButton("Otro color…")
            more.setFocusPolicy(Qt.NoFocus)
            more.clicked.connect(lambda: (pop.close(), self._pick_color()))
            pop.lay.addLayout(grid)
            pop.lay.addWidget(more)
        self._popup_below(self._tb_color, build)

    def _place_toolbar(self):
        tb = getattr(self, "_toolbar", None)
        if tb is None or self._editor is None:
            return
        ed = self._editor.geometry()
        x = max(4, min(ed.x(), self.viewport().width() - tb.width() - 4))
        y = ed.y() - tb.height() - 6
        if y < 2:
            y = ed.bottom() + 6
        tb.move(x, y)
        tb.raise_()

    def _set_fmt(self, key, value):
        """Aplica un formato a la selección; sin selección, a todo el párrafo."""
        if self._editor is None:
            return
        ed = self._editor
        fmt = QTextCharFormat()
        if key == "bold":
            fmt.setFontWeight(700 if value else 400)
        elif key == "italic":
            fmt.setFontItalic(bool(value))
        elif key == "size":
            fmt.setProperty(QTextFormat.Property.FontPixelSize, max(6, int(round(float(value) * self.zoom))))
            fmt.setProperty(_PROP_SIZE, float(value))
        elif key == "family":
            fmt.setFontFamilies([value])
            fmt.setProperty(_PROP_FAMILY, True)
        elif key == "color":
            fmt.setForeground(QBrush(QColor.fromRgb(int(value) & 0xFFFFFF)))
        cur = ed.textCursor()
        target = QTextCursor(cur)
        if not cur.hasSelection():
            target.select(QTextCursor.Document)
            ed.mergeCurrentCharFormat(fmt)          # y lo que se escriba a continuación
        target.mergeCharFormat(fmt)
        ed.setFocus()
        self._fit_editor()
        self._refresh_toolbar()

    def _pick_color(self):
        if self._editor is None:
            return
        self._dialog_open = True
        col = QColorDialog.getColor(QColor.fromRgb(self._current_style()["color"]), self, "Color del texto")
        self._dialog_open = False
        if self._editor is None:
            return
        if col.isValid():
            self._set_fmt("color", col.rgb() & 0xFFFFFF)
        self._editor.setFocus()

    def _open_new_text(self, scene_pos: QPointF):
        """Modo texto libre: un clic en la página abre un editor vacío justo ahí."""
        if not self.doc:
            return
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None:
            return
        y_off = self._page_tops[page_idx]
        x, y = scene_pos.x() / self.zoom, (scene_pos.y() - y_off) / self.zoom
        page_w = self.doc[page_idx].rect.width
        near = min((it for it in self._page_span_items[page_idx] if it.kind == "edit"),
                   key=lambda it: abs((it.span["bbox"][1] + it.span["bbox"][3]) / 2 - y), default=None)
        base = near.span if near else {"font": "ArialMT", "size": 11.0, "color": 0}
        size = float(base["size"])
        right = max(page_w - be._doc_geometry(self.doc)["left"], x + 80)
        span = {"text": "", "runs": [], "bbox": (x, y, x + 10, y + size * 1.25), "size": size,
                "color": base["color"], "font": base["font"], "pitch": size * 1.2, "n_lines": 0,
                "origin_y": y + size * 0.9, "x_first": x, "x_cont": x, "body_x": x, "align": "left",
                "label": None, "wrap_w": right - x, "wrap_first": right - x, "wrap_cont": right - x,
                "wrap_right": right, "shift_x0": 0.0, "shift_x1": page_w, "new": True}
        rect = QRectF(x * self.zoom, y_off + y * self.zoom, (right - x) * self.zoom, size * 1.25 * self.zoom)
        self.set_mode("edit")
        self.mode_changed.emit("edit")
        self._open_inline_editor(_VirtualItem(page_idx, rect, span))

    def _edit_at(self, page_idx: int, y_top: float):
        """Abre el editor en el elemento que empieza en y_top (tras insertarlo)."""
        for it in self._page_span_items[page_idx] if page_idx < len(self._page_span_items) else []:
            if it.kind == "edit" and abs(it.span["bbox"][1] - y_top) < 8:
                self._open_inline_editor(it)
                self._editor.selectAll()
                return

    def _insert_below(self):
        """Botón «+»: añade debajo del elemento en edición otro igual (con su etiqueta)."""
        item = self._editing_item
        if self._editor is None or item is None or item.span.get("new") or self.manual:
            return
        page_idx, y0, x0 = item.page_idx, item.span["bbox"][1], item.span["bbox"][0]
        self._close_inline_editor(commit=True)               # confirma lo escrito
        cand = [p for p in be.get_page_paragraphs(self.doc, page_idx)
                if abs(p["bbox"][1] - y0) < 3 and abs(p["bbox"][0] - x0) < 3]
        if not cand:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        pages_before = len(self.doc)
        res = be.insert_item_below(self.doc, page_idx, cand[0], "Novo elemento", settings=self.hf)
        if not res["ok"]:
            if self._on_notice:
                self._on_notice("No se pudo añadir el elemento.")
            return
        self._on_dirty()
        if len(self.doc) != pages_before:
            self.reload_preserving_scroll()
        else:
            for p in res["pages"]:
                self.refresh_page(p)
        QTimer.singleShot(0, lambda: self._edit_at(res["page"], res["y"]))

    def _delete_text(self):
        if self._editor is not None:
            self._editor.setPlainText("")
            self._deleting = True
            self._close_inline_editor(commit=True)

    def ask_header_footer(self, page_idx: int, intro: str = "") -> bool:
        """Abre el diálogo de cabecera y pie; guarda los ajustes si se acepta."""
        if not self.doc:
            return False
        dlg = HeaderFooterDialog(self.doc, page_idx, self.hf, self.window(), intro)
        if dlg.exec() == QDialog.Accepted:
            self.hf = dlg.settings
            return True
        return False

    def _maybe_close_editor(self, source=None):
        """Cerrar al perder el foco, salvo que sea por usar la barra de formato. `source` es el
        editor que lo provocó: si ya se cerró y hay otro abierto, no se toca el nuevo."""
        if self._editor is None or getattr(self, "_dialog_open", False):
            return
        if source is not None and source is not self._editor:
            return
        fw = QApplication.focusWidget()
        tb = getattr(self, "_toolbar", None)
        if QApplication.activePopupWidget() is not None or fw is self._editor \
                or (tb is not None and fw is not None and tb.isAncestorOf(fw)):
            return
        self._close_inline_editor(commit=True)

    def eventFilter(self, obj, e):
        if obj is self._editor:
            if e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key_Escape:
                self._close_inline_editor(commit=False)
                return True
            if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key_Return, Qt.Key_Enter) \
                    and e.modifiers() & Qt.ControlModifier:
                self._close_inline_editor(commit=True)      # Ctrl+Enter confirma; Enter = línea nueva
                return True
            if e.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(0, lambda ed=obj: self._maybe_close_editor(ed))
        return super().eventFilter(obj, e)

    def _close_inline_editor(self, commit: bool):
        if self._editor is None:
            return
        editor, item = self._editor, self._editing_item
        self._remove_cover()
        runs = self._collect_runs()
        changed = editor.document().isModified() or editor.toPlainText() != self._text0
        toolbar = getattr(self, "_toolbar", None)
        self._editor, self._editing_item, self._toolbar = None, None, None
        editor.removeEventFilter(self)
        editor.hide()
        editor.deleteLater()
        if toolbar is not None:
            toolbar.hide()
            toolbar.deleteLater()
        if commit and item is not None and changed:
            para = item.span
            new_text = "".join(r["text"] for r in runs)
            if para.get("new"):                                   # texto libre nuevo
                if new_text.strip():
                    if self._on_before_mutate:
                        self._on_before_mutate()
                    res = be.add_text_box(self.doc, item.page_idx, para["x_first"], para["bbox"][1],
                                          [dict(r) for r in runs], settings=self.hf)
                    if res["ok"]:
                        self._on_dirty()
                        self.refresh_page(item.page_idx)
                return
            # Con una sola página no se pueden deducir cabecera y pie (hay que ver qué
            # se repite): si la edición crea una página nueva, se pregunta antes.
            if self.hf is None and len(self.doc) < 2 and not self.manual:
                added = be.paragraph_edit_adds_pages(
                    self.doc, item.page_idx, para, new_text, para["size"], para["color"],
                    runs=[dict(r) for r in runs])
                if added and not self.ask_header_footer(
                        item.page_idx, "Este texto no cabe en la página y se creará una nueva. "
                        "Marca la cabecera y el pie para no tocarlos y decide cómo se repiten. "
                        "Si cancelas, el cambio se descarta."):
                    return
            if self._on_before_mutate:
                self._on_before_mutate()
            pages_before = len(self.doc)
            res = be.replace_paragraph_in_doc(
                self.doc, item.page_idx, para, new_text, para["size"], para["color"],
                settings=self.hf, runs=[dict(r) for r in runs], shift=not self.manual)
            if res["ok"]:
                self._on_dirty()
                if not res["font_found"] and res["family"]:
                    self._on_font_missing(res["family"])
                spilled = [p + 1 for p in res["pages"] if p != item.page_idx]
                if spilled and self._on_notice:
                    self._on_notice("El texto que no cabía pasó a la página " +
                                    ", ".join(str(p) for p in spilled) + ".")
                if len(self.doc) != pages_before:
                    self.reload_preserving_scroll()          # se añadió alguna página
                else:
                    for p in res["pages"]:
                        self.refresh_page(p)

# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: EDIT — editor visual + censurar / buscar y reemplazar
# ══════════════════════════════════════════════════════════════════════════
class _FontLookupWorker(QThread):
    """Busca en Google Fonts las familias que faltan (sin bloquear la ventana)."""
    found = Signal(str, object)         # familia, {"info": …, "substitute": …}
    failed = Signal(str)

    def __init__(self, groups):
        super().__init__()
        self.groups = groups

    def run(self):
        for g in self.groups:
            try:
                info = fm.find_on_google(g["candidates"])
                sub_info = None
                sub_name = fm.SUBSTITUTES.get(g["family"].lower())
                if info is None and sub_name:
                    sub_info = fm.google_lookup(sub_name)
                self.found.emit(g["family"], {"info": info, "substitute": sub_info, "sub_name": sub_name})
            except OSError as e:
                self.failed.emit(str(e))
                return


class _FontDownloadWorker(QThread):
    progress = Signal(str)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, jobs, to_windows):
        super().__init__()
        self.jobs, self.to_windows = jobs, to_windows

    def run(self):
        installed = []
        try:
            for family, info, styles in self.jobs:
                paths = fm.download_family(
                    info, styles, progress=lambda i, n, name, fam=family: self.progress.emit(
                        f"Descargando «{fam}»: {name} ({i + 1}/{n})" if name else f"«{fam}» descargada"))
                if self.to_windows:
                    self.progress.emit(f"Instalando «{family}» en Windows…")
                    fm.install_in_windows(paths)
                installed.append(info["family"])
            self.done.emit(installed)
        except OSError as e:
            self.failed.emit(str(e))


class FontDownloadDialog(QDialog):
    """Lista las fuentes del PDF que no están instaladas y deja descargarlas de Google Fonts,
    instalándolas solo en el programa o también en Windows."""
    def __init__(self, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fuentes que faltan")
        self.resize(640, 520)
        self.groups = groups
        self.rows: dict[str, dict] = {}
        self.installed: list[str] = []
        self._workers = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        title = QLabel("Fuentes que faltan")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        info = QLabel("Este PDF usa fuentes que no están en tu ordenador. Sin ellas, al editar se usa una "
                      "parecida y el texto puede verse algo distinto. Las que publica Google Fonts "
                      "(licencia libre) se pueden descargar aquí. Las de Microsoft, Adobe o de pago no.")
        info.setObjectName("Hint")
        info.setWordWrap(True)
        lay.addWidget(info)

        self.list = QListWidget()
        self.list.setStyleSheet(_LIST_SELECT_QSS)
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for g in groups:
            it = QListWidgetItem(f"«{g['family']}» — comprobando en Google Fonts…")
            it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable)
            self.list.addItem(it)
            self.rows[g["family"]] = {"group": g, "item": it, "info": None, "substitute": None}
        lay.addWidget(self.list, 1)

        self.search_btn = _btn("Buscar la seleccionada en Google Fonts", None, "Flat", icon_color=TEXT)
        self.search_btn.clicked.connect(self._search_web)
        lay.addWidget(self.search_btn, 0, Qt.AlignLeft)

        self.opt_app = QRadioButton("Instalar solo en este programa (recomendado: no cambia nada en Windows)")
        self.opt_win = QRadioButton("Instalar también en Windows (para todos tus programas; solo para tu "
                                    "usuario, sin permisos de administrador)")
        self.opt_app.setChecked(True)
        lay.addWidget(self.opt_app)
        lay.addWidget(self.opt_win)

        self.status = QLabel("")
        self.status.setObjectName("Hint")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        lay.addWidget(self.bar)

        btns = QHBoxLayout()
        self.close_btn = _btn("Cerrar", None, "Secondary", icon_color=TEXT)
        self.go_btn = _btn("Descargar e instalar", "download", "Primary", icon_color=ICON_DARK)
        self.go_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        self.go_btn.clicked.connect(self._start_download)
        btns.addStretch(1)
        btns.addWidget(self.close_btn)
        btns.addWidget(self.go_btn)
        lay.addLayout(btns)

        w = _FontLookupWorker(groups)
        w.found.connect(self._on_found)
        w.failed.connect(self._on_lookup_failed)
        w.finished.connect(self._on_lookup_done)
        self._workers.append(w)
        w.start()

    def _on_found(self, family: str, data: dict):
        row = self.rows[family]
        it = row["item"]
        row["info"], row["substitute"] = data["info"], data["substitute"]
        n_styles = len(row["group"]["styles"])
        if data["info"]:
            it.setText(f"«{family}» — disponible en Google Fonts ({len(data['info']['files'])} estilos)")
        elif data["substitute"]:
            it.setText(f"«{family}» — de Microsoft; «{data['sub_name']}» (Google Fonts) tiene las mismas medidas")
            it.setToolTip(f"«{family}» no se puede descargar (es de Microsoft). «{data['sub_name']}» es una "
                          f"fuente libre con medidas idénticas: el texto ocupa lo mismo y no se descoloca.")
        else:
            it.setText(f"«{family}» — no está en Google Fonts: se usa «Arial» en su lugar. Si quieres usar «{family}», "
                       f"instálala en Windows (doble clic en el archivo de la fuente → Instalar) y reabre la aplicación.")
            it.setToolTip("Suele ser una fuente de pago o del sistema, y no se puede descargar de aquí.")
            return
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked)

    def _on_lookup_failed(self, msg: str):
        self.status.setText("No se pudo conectar con Google Fonts. Comprueba tu conexión a internet.")
        for row in self.rows.values():
            if row["info"] is None and row["substitute"] is None:
                row["item"].setText(row["item"].text().replace("comprobando en Google Fonts…", "sin conexión"))

    def _on_lookup_done(self):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.go_btn.setEnabled(any(r["info"] or r["substitute"] for r in self.rows.values()))

    def _search_web(self):
        it = self.list.currentItem() or (self.list.item(0) if self.list.count() else None)
        if it is None:
            return
        fam = next(k for k, r in self.rows.items() if r["item"] is it)
        QDesktopServices.openUrl(QUrl("https://fonts.google.com/?query=" + fam.replace(" ", "+")))

    def _start_download(self):
        jobs = []
        for fam, r in self.rows.items():
            if r["item"].flags() & Qt.ItemIsUserCheckable and r["item"].checkState() == Qt.Checked:
                jobs.append((fam, r["info"] or r["substitute"], set(r["group"]["styles"])))
        if not jobs:
            self.status.setText("Marca al menos una fuente.")
            return
        self.go_btn.setEnabled(False)
        self.bar.setRange(0, 0)
        w = _FontDownloadWorker(jobs, self.opt_win.isChecked())
        w.progress.connect(self.status.setText)
        w.done.connect(self._on_downloaded)
        w.failed.connect(self._on_download_failed)
        self._workers.append(w)
        w.start()

    def _on_downloaded(self, names: list):
        self.installed = names
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.status.setText("Listo: " + ", ".join(f"«{n}»" for n in names) +
                            " instalada(s). Ya se usarán al editar este PDF.")
        self.close_btn.setText("  Cerrar")

    def _on_download_failed(self, msg: str):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.go_btn.setEnabled(True)
        self.status.setText(f"No se pudo descargar: {msg}")


class EditPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.doc = None
        self.current_file: dict | None = None
        self.page_idx = 0
        self.dirty = False
        self._warned_fonts: set[str] = set()
        self._active_panel: str | None = None
        self._undo_stack: list[bytes] = []
        self._redo_stack: list[bytes] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(BackHeader("Edit", lambda: win.go_home()))

        root.addWidget(QLabel("Archivo:"))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        root.addWidget(self.file_combo)

        hint = QLabel("Clic sobre cualquier texto de la página para editarlo directamente, "
                       "sobre la propia página. Enter hace una línea nueva, Ctrl+Enter confirma y Esc cancela. Usa la fuente original del "
                       "PDF si la tienes instalada en Windows; si no, avisa y usa una de respaldo.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Aviso de fuentes que faltan (solo aparece si el PDF usa alguna que no tienes)
        self.font_banner = QFrame()
        self.font_banner.setStyleSheet(
            f"QFrame {{ background:rgba(192,130,88,0.16); border:1px solid {ACCENT}; border-radius:10px; }}"
            f"QLabel {{ background:transparent; border:none; }}")
        fb = QHBoxLayout(self.font_banner)
        fb.setContentsMargins(14, 10, 14, 10)
        self.font_banner_lbl = QLabel()
        self.font_banner_lbl.setWordWrap(True)
        fb_get = _btn("Descargar fuentes…", "download", "Primary", icon_color=ICON_DARK)
        fb_get.clicked.connect(self._open_font_dialog)
        fb_skip = _btn("Ignorar", None, "Flat", icon_color=TEXT)
        fb_skip.clicked.connect(self._ignore_fonts)
        fb_restart = _btn("Reiniciar con este documento", "back", "Secondary", icon_color=TEXT)
        fb_restart.setToolTip("Cierra y vuelve a abrir la aplicación con este mismo documento y sus cambios, para "
                              "que reconozca una fuente recién instalada")
        fb_restart.clicked.connect(self._restart_with_doc)
        fb.addWidget(self.font_banner_lbl, 1)
        fb.addWidget(fb_restart)
        fb.addWidget(fb_get)
        self.font_get_btn = fb_get
        fb.addWidget(fb_skip)
        self.font_banner.hide()
        self._missing_fonts: list = []
        self._ignored_fonts: set = set()
        self._font_state: dict = {}              # familia -> "google" | "no" (según la búsqueda en Google Fonts)
        self._lookup_worker = None
        root.addWidget(self.font_banner)

        # ── Barra de herramientas superior ───────────────────────────────
        toolbar = QFrame(); toolbar.setObjectName("Toolbar")
        toolbar.setStyleSheet("QFrame#Toolbar QPushButton { padding-left:8px; padding-right:8px; font-size:12px; }")
        outer = QVBoxLayout(toolbar)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)
        tb = QHBoxLayout()           # fila 1: deshacer/rehacer, páginas y guardar
        tools_row = QWidget()        # fila 2: herramientas (salta de línea si la ventana es estrecha)
        tb2 = FlowLayout(tools_row, margin=0, hspacing=8, vspacing=6)
        outer.addLayout(tb)
        outer.addWidget(tools_row)
        self.undo_btn = _btn("", "back"); self.undo_btn.setFixedWidth(38)
        self.undo_btn.setToolTip("Deshacer (Ctrl+Z)")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._do_undo)
        self.redo_btn = _btn("", "forward"); self.redo_btn.setFixedWidth(38)
        self.redo_btn.setToolTip("Rehacer (Ctrl+Y)")
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._do_redo)
        tb.addWidget(self.undo_btn)
        tb.addWidget(self.redo_btn)
        tb.addSpacing(10)
        self.censor_btn = _btn("Censurar", "lock", "Secondary", icon_color=TEXT)
        self.censor_btn.setToolTip("Tapar texto con una barra negra")
        self.censor_btn.setCheckable(True)
        self.censor_btn.clicked.connect(lambda: self._toggle_panel("censor"))
        self.fr_btn = _btn("Reemplazar", "swap", "Secondary", icon_color=TEXT)
        self.fr_btn.setToolTip("Buscar y reemplazar texto")
        self.fr_btn.setCheckable(True)
        self.fr_btn.clicked.connect(lambda: self._toggle_panel("find"))
        self.edit_btn = _btn("Editar", "pencil", "Secondary", icon_color=TEXT)
        self.edit_btn.setCheckable(True)
        self.edit_btn.setChecked(True)
        self.edit_btn.setToolTip("Editar el texto existente: haz clic sobre un texto y cámbialo")
        self.edit_btn.clicked.connect(self._go_edit_mode)
        self.hf_btn = _btn("Configurar página", "document", "Secondary", icon_color=TEXT)
        self.hf_btn.setToolTip("Marca qué es cabecera y pie de página y cómo se repiten en páginas nuevas")
        self.hf_btn.clicked.connect(lambda: self.editor_view.ask_header_footer(self.page_idx))
        self.text_btn = _btn("Texto", "text_add", "Secondary", icon_color=TEXT)
        self.text_btn.setCheckable(True)
        self.text_btn.setToolTip("Añadir texto nuevo: haz clic en cualquier punto de la página y escribe")
        self.text_btn.clicked.connect(self._toggle_text_mode)
        self.manual_btn = _btn("Automático", "bolt", "Secondary", icon_color=TEXT)
        self.manual_btn.setCheckable(True)
        self.manual_btn.setToolTip(
            "Automático: deduce párrafos, listas, cabecera, pie y numeración, y reparte el texto "
            "entre páginas.\nManual: cada línea se edita por separado y no se mueve nada más.")
        self.manual_btn.clicked.connect(self._toggle_manual)
        self.annot_btn = _btn("Marcar", "highlight", "Secondary", icon_color=TEXT)
        self.annot_btn.setCheckable(True)
        self.annot_btn.setToolTip("Resaltar, subrayar o tachar texto arrastrando sobre él")
        self.annot_menu = QMenu(self.annot_btn)
        self.annot_btn.setMenu(self.annot_menu)
        self.annot_menu.aboutToShow.connect(self._fill_annot_menu)
        self.shape_btn = _btn("Dibujar", "pen", "Secondary", icon_color=TEXT)
        self.shape_btn.setCheckable(True)
        self.shape_btn.setToolTip("Dibujo libre (lápiz, rotulador), rectángulos, elipses, líneas y flechas")
        self.shape_btn.clicked.connect(self._toggle_shape_panel)
        self.image_btn = _btn("Imagen", "image", "Secondary", icon_color=TEXT)
        self.image_btn.setCheckable(True)
        self.image_btn.setToolTip("Insertar una imagen, o seleccionar, mover y borrar las que ya hay en el PDF")
        self.image_menu = QMenu(self.image_btn)
        self.image_btn.setMenu(self.image_menu)
        self.image_menu.aboutToShow.connect(self._fill_image_menu)
        tb2.addWidget(self.edit_btn)
        tb2.addWidget(self.fr_btn)
        tb2.addWidget(self.annot_btn)
        tb2.addWidget(self.image_btn)
        tb2.addWidget(self.shape_btn)
        self.sign_btn = _btn("Firma", "signature", "Secondary", icon_color=TEXT)
        self.sign_btn.setToolTip("Firmar: dibuja, escribe o usa una imagen; se guarda para volver a usarla")
        self.sign_menu = QMenu(self.sign_btn)
        self.sign_btn.setMenu(self.sign_menu)
        self.sign_menu.aboutToShow.connect(self._fill_sign_menu)
        self.link_btn = _btn("Enlace", "link", "Secondary", icon_color=TEXT)
        self.link_btn.setCheckable(True)
        self.link_btn.setToolTip("Convertir un texto, un área, una imagen o un dibujo en un enlace; clic en uno existente para editarlo")
        self.link_btn.clicked.connect(self._toggle_link_mode)
        tb2.addWidget(self.sign_btn)
        tb2.addWidget(self.link_btn)
        tb2.addWidget(self.censor_btn)
        self.form_btn = _btn("Formulario", "form", "Secondary", icon_color=TEXT)
        self.form_btn.setCheckable(True)
        self.form_btn.setToolTip("Rellenar los campos del PDF, crear campos nuevos o aplanar el formulario")
        self.form_btn.clicked.connect(self._toggle_form_mode)
        tb2.addWidget(self.form_btn)
        self.notes_btn = _btn("Notas", "note", "Secondary", icon_color=TEXT)
        self.notes_btn.setCheckable(True)
        self.notes_btn.setToolTip("Notas y comentarios, archivos adjuntos y ocultar las anotaciones")
        self.notes_menu = QMenu(self.notes_btn)
        self.notes_btn.setMenu(self.notes_menu)
        self.notes_menu.aboutToShow.connect(self._fill_notes_menu)
        tb2.addWidget(self.notes_btn)
        self.copy_btn = _btn("Copiar texto", "text_t", "Secondary", icon_color=TEXT)
        self.copy_btn.setCheckable(True)
        self.copy_btn.setToolTip("Copiar texto con sentido: arrastra una zona o haz clic en un párrafo o tabla. "
                                 "Entiende párrafos, columnas y tablas (también en escaneos)")
        self.copy_btn.clicked.connect(self._toggle_copy_mode)
        tb2.addWidget(self.copy_btn)
        self.stamp_btn = _btn("Sello", "stamp", "Secondary", icon_color=TEXT)
        self.stamp_btn.setToolTip("Sello de texto (APROBADO, RECIBIDO…) con fecha y autor")
        self.stamp_btn.clicked.connect(self._new_stamp)
        tb2.addWidget(self.stamp_btn)
        tb2.addWidget(self.text_btn)
        self.manual_btn.hide()           # el modo Automático es el único: ya no se ofrece como opción
        tb2.addWidget(self.hf_btn)
        tb.addStretch(1)
        prev_btn = _btn("", "chevron_left"); prev_btn.setFixedWidth(38)
        next_btn = _btn("", "chevron_right"); next_btn.setFixedWidth(38)
        prev_btn.clicked.connect(self._prev_page)
        next_btn.clicked.connect(self._next_page)
        self.page_lbl = QLabel("—")
        self.page_lbl.setObjectName("Hint")
        self.page_lbl.setFixedWidth(84)
        self.page_lbl.setAlignment(Qt.AlignCenter)
        tb.addWidget(prev_btn)
        tb.addWidget(self.page_lbl)
        tb.addWidget(next_btn)
        tb.addSpacing(10)
        zo = _btn("−", None); zo.setFixedWidth(34); zo.setToolTip("Alejar (Ctrl y −, o Ctrl + rueda)")
        zi = _btn("+", None); zi.setFixedWidth(34); zi.setToolTip("Acercar (Ctrl y +, o Ctrl + rueda)")
        self.zoom_btn = _btn("120 %", None, "Secondary", icon_color=TEXT)
        self.zoom_btn.setFixedWidth(64)
        self.zoom_btn.setToolTip("Ajustar al ancho de la ventana (Ctrl+0)")
        zo.clicked.connect(lambda: self.editor_view.zoom_by(1 / 1.2))
        zi.clicked.connect(lambda: self.editor_view.zoom_by(1.2))
        self.zoom_btn.clicked.connect(lambda: self.editor_view.fit_width())
        tb.addWidget(zo)
        tb.addWidget(self.zoom_btn)
        tb.addWidget(zi)
        tb.addSpacing(10)
        save_btn = _btn("Guardar", "save", "Primary")
        save_btn.clicked.connect(self._save_changes)
        tb.addWidget(save_btn)
        root.addWidget(toolbar)

        # ── Panel colapsable: censurar / buscar y reemplazar ─────────────
        self.tools_panel = QFrame(); self.tools_panel.setObjectName("Card")
        add_shadow(self.tools_panel, blur=18, dy=4, alpha=70)
        panel_lay = QVBoxLayout(self.tools_panel)

        self.censor_content = QWidget()
        c1 = QVBoxLayout(self.censor_content)
        c1.setContentsMargins(0, 0, 0, 0)
        censor_title = QLabel("Censurar")
        censor_title.setObjectName("SectionTitle")
        c1.addWidget(censor_title)
        censor_hint = QLabel("Con este panel abierto, clica sobre cualquier fragmento de texto "
                              "de la página para taparlo al instante, o clica y arrastra sobre "
                              "cualquier área (también fotos o firmas) para censurar justo esa "
                              "zona. También puedes buscar un texto exacto aquí abajo. "
                              "Esta acción no se puede deshacer.")
        censor_hint.setObjectName("Hint")
        censor_hint.setWordWrap(True)
        c1.addWidget(censor_hint)
        censor_row = QHBoxLayout()
        self.censor_field = QLineEdit()
        self.censor_field.setPlaceholderText("O escribe aquí un texto exacto a censurar")
        censor_go_btn = _btn("Censurar texto", "lock", "Primary")
        censor_go_btn.clicked.connect(self._do_censor)
        censor_row.addWidget(self.censor_field, 1)
        censor_row.addWidget(censor_go_btn)
        c1.addLayout(censor_row)
        panel_lay.addWidget(self.censor_content)

        self.find_content = QWidget()
        c2 = QVBoxLayout(self.find_content)
        c2.setContentsMargins(0, 0, 0, 0)
        fr_title = QLabel("Buscar y reemplazar")
        fr_title.setObjectName("SectionTitle")
        c2.addWidget(fr_title)
        fr_row = QHBoxLayout()
        self.buscar_field = QLineEdit()
        self.buscar_field.setPlaceholderText("Buscar")
        self.reemplazar_field = QLineEdit()
        self.reemplazar_field.setPlaceholderText("Reemplazar por (vacío = eliminar)")
        fr_go_btn = _btn("Reemplazar", "swap", "Primary")
        fr_go_btn.clicked.connect(self._do_find_replace)
        fr_row.addWidget(self.buscar_field, 1)
        fr_row.addWidget(self.reemplazar_field, 1)
        fr_row.addWidget(fr_go_btn)
        c2.addLayout(fr_row)
        fr_opts = QHBoxLayout()
        self.case_cb = QCheckBox("Distinguir mayúsculas y minúsculas")
        fr_hint = QLabel("Reemplaza en todo el documento conservando la fuente, el tamaño y el color. Ctrl+Z lo deshace.")
        fr_hint.setObjectName("Hint")
        fr_opts.addWidget(self.case_cb)
        fr_opts.addWidget(fr_hint, 1)
        c2.addLayout(fr_opts)
        panel_lay.addWidget(self.find_content)

        self.tools_panel.hide()
        root.addWidget(self.tools_panel)
        self._build_shape_panel(root)
        self._build_form_panel(root)

        # ── Vista continua de todas las páginas ──────────────────────────
        self.editor_view = PageEditorView(on_dirty=self._mark_dirty,
                                           on_font_missing=self._warn_font_missing,
                                           on_page_visible=self._on_page_visible,
                                           on_before_mutate=self._before_mutate,
                                           on_notice=lambda m: self.win.snack(m, "info"))
        self.editor_view.mode_changed.connect(self._on_view_mode)
        self.editor_view.page_action.connect(self._on_page_action)
        self.editor_view.shape_kind_changed.connect(self._on_shape_kind_changed)
        self.editor_view.icon_picker_requested.connect(self._open_icon_picker)
        self.editor_view.save_signature_requested.connect(self._on_save_signature)
        self.editor_view.zoomed.connect(lambda z: self.zoom_btn.setText(f"{round(z / 1.3333 * 100)} %"))
        for seq, fn in ((QKeySequence.StandardKey.ZoomIn, lambda: self.editor_view.zoom_by(1.2)),
                        (QKeySequence.StandardKey.ZoomOut, lambda: self.editor_view.zoom_by(1 / 1.2)),
                        (QKeySequence("Ctrl+0"), lambda: self.editor_view.fit_width())):
            sc_ = QShortcut(seq, self)
            sc_.activated.connect(fn)
        self.editor_view.link_requested.connect(self._on_link_requested)
        self.editor_view.field_requested.connect(self._on_field_requested)
        self.editor_view._reload_cb = self._reload_doc_from_bytes
        self.editor_view.note_requested.connect(self._on_note_requested)
        self.editor_view.copy_requested.connect(self._on_copy_requested)
        self.editor_view.replace_requested.connect(self._on_replace_requested)
        self._copy_cache: dict = {}
        self.editor_view.attach_clicked.connect(self._on_attach_clicked)
        root.addWidget(self.editor_view, 1)

        undo_sc = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_sc.activated.connect(self._do_undo)
        redo_sc = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_sc.activated.connect(self._do_redo)

    # ── Ciclo de vida de la pestaña / sesión de edición ─────────────────
    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)
        if self.win.uploaded_files:
            self.file_combo.setCurrentIndex(0)
            self._load_file(self.win.uploaded_files[0])

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _on_file_changed(self, idx: int):
        if 0 <= idx < len(self.win.uploaded_files):
            self._maybe_prompt_save()
            self._load_file(self.win.uploaded_files[idx])

    def _load_file(self, f: dict):
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:
                pass
        self.current_file = f
        self.doc = be.open_edit_session(f["path"])
        self.page_idx = 0
        self.dirty = False
        dr.clear()
        self._warned_fonts.clear()
        self._copy_cache = {}
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()
        self.editor_view.hf = None
        self._ignored_fonts = set()
        self._font_state = {}
        if not self.doc:
            self.page_lbl.setText("—")
        self.editor_view.load_doc(self.doc)
        self._refresh_font_banner()
        if self.doc is not None and ft.has_fields(self.doc):
            self.win.snack("Este PDF tiene campos de formulario: usa el botón Formulario para rellenarlos.", "info")

    def _before_mutate(self):
        """Llamado justo antes de cualquier cambio (editar texto, censurar)
        para poder deshacerlo luego."""
        if self.doc is None:
            return
        snap = be.snapshot_doc_bytes(self.doc)
        if snap:
            self._undo_stack.append(snap)
            self._redo_stack.clear()
            self._update_undo_redo_buttons()

    def _swap_doc(self, new_bytes: bytes):
        new_doc = be.doc_from_bytes(new_bytes)
        if new_doc is None:
            return False
        old_doc = self.doc
        self.doc = new_doc
        self._copy_cache = {}
        try:
            if old_doc is not None:
                old_doc.close()
        except Exception:
            pass
        vbar_val = self.editor_view.verticalScrollBar().value()
        self.editor_view.load_doc(self.doc)
        self.editor_view.verticalScrollBar().setValue(vbar_val)
        return True

    def _do_undo(self):
        if not self._undo_stack or self.editor_view._editor is not None:
            return
        cur = be.snapshot_doc_bytes(self.doc)
        prev_bytes = self._undo_stack.pop()
        if self._swap_doc(prev_bytes):
            if cur:
                self._redo_stack.append(cur)
            self.dirty = bool(self._undo_stack)
            self._schedule_draft()
            self._update_undo_redo_buttons()
            self.win.snack("↩ Deshecho", "info")

    def _do_redo(self):
        if not self._redo_stack or self.editor_view._editor is not None:
            return
        cur = be.snapshot_doc_bytes(self.doc)
        next_bytes = self._redo_stack.pop()
        if self._swap_doc(next_bytes):
            if cur:
                self._undo_stack.append(cur)
            self.dirty = True
            self._schedule_draft()
            self._update_undo_redo_buttons()
            self.win.snack("↪ Rehecho", "info")

    def _update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(bool(self._undo_stack))
        self.redo_btn.setEnabled(bool(self._redo_stack))

    def _on_page_visible(self, idx: int, total: int):
        self.page_idx = idx
        self.page_lbl.setText(f"Pág. {idx + 1} / {total}" if total else "—")

    def _prev_page(self):
        if self.doc and self.page_idx > 0:
            self.editor_view.scroll_to_page(self.page_idx - 1)

    def _next_page(self):
        if self.doc and self.page_idx < len(self.doc) - 1:
            self.editor_view.scroll_to_page(self.page_idx + 1)

    def _close_panel(self):
        self._active_panel = None
        self.tools_panel.hide()
        self.censor_btn.setChecked(False)
        self.fr_btn.setChecked(False)
        self.editor_view.set_mode("edit")

    def _toggle_panel(self, which: str):
        if self._active_panel == which:
            self._close_panel()
            return
        self._active_panel = which
        self.tools_panel.show()
        if which == "censor":
            self.censor_content.show()
            self.find_content.hide()
            self.censor_btn.setChecked(True)
            self.fr_btn.setChecked(False)
            self.editor_view.set_mode("censor")
        else:
            self.find_content.show()
            self.censor_content.hide()
            self.fr_btn.setChecked(True)
            self.censor_btn.setChecked(False)
            self.editor_view.set_mode("edit")

    # ── Fuentes que faltan ──────────────────────────────────────────────
    def _font_banner_text(self) -> str:
        fb = self.editor_view._FALLBACK_FONT
        lines = []
        for g in self._missing_fonts:
            fam, st = g["family"], self._font_state.get(g["family"])
            if st == "google":
                lines.append(f"La fuente «{fam}» no está instalada, pero está en Google Fonts: pulsa «Descargar "
                             f"fuentes…» para instalarla. Mientras tanto se usa «{fb}».")
            elif st == "no":
                lines.append(f"La fuente «{fam}» no está en Google Fonts (suele ser de pago o de otro programa): se está "
                             f"usando «{fb}» en su lugar. Si quieres usar «{fam}», descárgala e instálala en Windows "
                             f"(doble clic en el archivo de la fuente → Instalar) y pulsa «Reiniciar con este documento».")
            else:
                lines.append(f"La fuente «{fam}» no está instalada: se está usando «{fb}» en su lugar. Si quieres usar "
                             f"«{fam}», instálala en Windows y reabre la aplicación (o mira si está en Google Fonts "
                             f"con «Descargar fuentes…»).")
        return "\n".join(lines)

    def _refresh_font_banner(self):
        """Muestra el aviso si el PDF usa fuentes que no están instaladas, diciendo cuál se usa en su lugar."""
        missing = fm.missing_fonts(self.doc) if self.doc is not None else []
        self._missing_fonts = [g for g in missing if g["family"] not in self._ignored_fonts]
        if not self._missing_fonts:
            self.font_banner.hide()
            return
        self.font_banner_lbl.setText(self._font_banner_text())
        self._sync_font_buttons()
        self.font_banner.show()
        todo = [g for g in self._missing_fonts if g["family"] not in self._font_state]
        if todo and (self._lookup_worker is None or not self._lookup_worker.isRunning()):
            w = _FontLookupWorker(todo)
            w.found.connect(self._on_font_looked_up)
            self._lookup_worker = w
            w.start()

    def _on_font_looked_up(self, family: str, data: dict):
        self._font_state[family] = "google" if (data["info"] or data["substitute"]) else "no"
        if self._missing_fonts:
            self.font_banner_lbl.setText(self._font_banner_text())
            self._sync_font_buttons()

    def _sync_font_buttons(self):
        """«Descargar fuentes» solo tiene sentido si alguna está (o puede estar) en Google Fonts."""
        self.font_get_btn.setVisible(any(self._font_state.get(g["family"]) != "no" for g in self._missing_fonts))

    def _ignore_fonts(self):
        self._ignored_fonts |= {g["family"] for g in self._missing_fonts}
        self._refresh_font_banner()

    def _open_font_dialog(self):
        dlg = FontDownloadDialog(self._missing_fonts, self.window())
        dlg.exec()
        if dlg.installed:
            winfonts.refresh_installed_fonts()
            self._refresh_font_banner()
            self.editor_view.reload_preserving_scroll()
            self.win.snack("Fuentes instaladas: " + ", ".join(dlg.installed), "success")

    # ── Páginas, texto libre y modo manual ──────────────────────────────
    def _fill_pages_menu(self, menu: QMenu):
        menu.clear()
        n = self.page_idx + 1
        menu.addAction("Añadir página al final", lambda: self._add_page(len(self.doc)))
        menu.addAction(f"Añadir página después de la {n}", lambda: self._add_page(self.page_idx + 1))
        menu.addAction(f"Añadir página antes de la {n}", lambda: self._add_page(self.page_idx))
        menu.addSeparator()
        menu.addAction(f"Girar la página {n} a la derecha", lambda: self._rotate([self.page_idx], 90))
        menu.addAction(f"Girar la página {n} a la izquierda", lambda: self._rotate([self.page_idx], -90))
        menu.addAction("Girar todas las páginas a la derecha",
                       lambda: self._rotate(list(range(len(self.doc))), 90))
        menu.addSeparator()
        menu.addAction(f"Borrar la página {n}", self._delete_page)

    def _add_page(self, at: int):
        if not self.doc:
            return
        ev = self.editor_view
        dlg = InsertPageDialog(ev, self.doc, at, self.window())
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.choice == "pdf":
            self._before_mutate()
            res = be.insert_pdf_pages(self.doc, at, dlg.pdf_path)
            if res["ok"]:
                self._mark_dirty()
                ev.reload_preserving_scroll()
                ev.scroll_to_page(at)
                self.win.snack(f"{res['count']} página{'s' if res['count'] != 1 else ''} insertada"
                               f"{'s' if res['count'] != 1 else ''}.", "success")
            else:
                self.win.snack("No se pudo insertar ese PDF (¿tiene contraseña?).", "error")
            return
        self._insert_blank(at, dlg.settings)

    def _insert_blank(self, at: int, settings):
        ev = self.editor_view
        if (ev.manual or len(self.doc) < 2) and settings is None and ev.hf is None:
            # Con una sola página (o en modo manual) no se puede deducir cabecera, pie y numeración.
            if not ev.ask_header_footer(self.page_idx, "Marca la cabecera y el pie de página para "
                                        "copiarlos a la página nueva y decide cómo se numera."):
                return
            settings = ev.hf
        self._before_mutate()
        res = be.insert_page(self.doc, at, settings=settings)
        if res["ok"]:
            self._mark_dirty()
            ev.reload_preserving_scroll()
            ev.scroll_to_page(at)
            self.win.snack(f"Página añadida (ahora es la {at + 1}).", "success")
        else:
            self.win.snack("No se pudo añadir la página.", "error")

    def _rotate(self, idxs: list, delta: int):
        if not self.doc:
            return
        self._before_mutate()
        if be.rotate_pages(self.doc, idxs, delta):
            self._mark_dirty()
            self.editor_view.reload_preserving_scroll()
            self.win.snack("Página girada. Mientras esté girada no se puede editar su contenido; vuelve a girarla "
                           "a su posición para hacerlo." if len(idxs) == 1 else "Páginas giradas.", "info")
        else:
            self.win.snack("No se pudo girar.", "error")

    def _delete_page(self):
        if not self.doc:
            return
        if len(self.doc) < 2:
            self.win.snack("No se puede borrar la única página del documento.", "error")
            return
        n = self.page_idx + 1
        if QMessageBox.question(
                self, "Borrar página", f"¿Borrar la página {n} con todo su contenido?\n"
                "Las siguientes se renumeran. Puedes deshacerlo con Ctrl+Z.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._before_mutate()
        res = be.delete_pages(self.doc, [self.page_idx], settings=self.editor_view.hf)
        if res["ok"]:
            self._mark_dirty()
            self.editor_view.reload_preserving_scroll()
            self.editor_view.scroll_to_page(min(self.page_idx, len(self.doc) - 1))
            self.win.snack(f"Página {n} borrada.", "success")
        else:
            self.win.snack("No se pudo borrar la página.", "error")

    def _toggle_text_mode(self, checked: bool):
        if checked:
            self._close_panel()
            self.text_btn.setChecked(True)
            self.editor_view.set_mode("text")
            self.win.snack("Haz clic en la página donde quieras escribir.", "info")
        else:
            self.editor_view.set_mode("edit")

    def _on_page_action(self, action: str, idx: int):
        # se aplica fuera del clic: recargar la escena destruye el propio botón que se está pulsando
        QTimer.singleShot(0, lambda: self._do_page_action(action, idx))

    def _do_page_action(self, action: str, idx: int):
        if not self.doc:
            return
        self.page_idx = min(idx, len(self.doc) - 1)
        if action in ("zoomin", "zoomout"):
            self.editor_view.zoom_by(1.2 if action == "zoomin" else 1 / 1.2)
        elif action == "insert":
            self._add_page(idx)
        elif action == "delete":
            self._delete_page()
        elif action == "rotl":
            self._rotate([idx], -90)
        elif action == "rotr":
            self._rotate([idx], 90)

    def _go_edit_mode(self):
        self._close_panel()
        self.editor_view.set_mode("edit")
        self.edit_btn.setChecked(True)

    def _on_view_mode(self, mode: str):
        self.edit_btn.setChecked(mode == "edit")
        self.text_btn.setChecked(mode == "text")
        self.annot_btn.setChecked(mode == "markup")
        if mode != "markup":
            self.annot_btn.setText("  Marcar")
        self.shape_btn.setChecked(mode == "shape")
        self.shape_panel.setVisible(mode == "shape")
        if mode == "shape":
            self._sync_shape_panel()
        self.image_btn.setChecked(mode == "image")
        self.link_btn.setChecked(mode == "link")
        self.form_btn.setChecked(mode == "form")
        self.form_panel.setVisible(mode == "form")
        self.notes_btn.setChecked(mode in ("note", "attach"))
        self.copy_btn.setChecked(mode == "copy")
        if mode != "shape":
            self.shape_btn.setText("  Dibujar")

    # ── Enlaces ─────────────────────────────────────────────────────────
    # ── Sellos ──────────────────────────────────────────────────────────
    def _new_stamp(self):
        if self.doc is None:
            return
        self._close_panel()
        dlg = st_.StampDialog(self.window())
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            try:
                size = at.image_size(str(dlg.result_path))
            except Exception:
                self.win.snack("No se pudo crear el sello.", "error")
                return
            self.begin_place_image(str(dlg.result_path), size, max_frac=0.28, what="el sello")

    # ── Copiar texto con sentido ────────────────────────────────────────
    def _toggle_copy_mode(self, checked: bool):
        if checked:
            self._close_panel()
            self.editor_view.set_mode("copy")
            self.win.snack("Arrastra para copiar una zona, o haz clic en un párrafo o una tabla. Esc para salir.", "info")
        else:
            self.editor_view.set_mode("edit")

    def _ocr_langs_for_copy(self) -> list:
        tp = getattr(self.win, "tools_page", None)
        chosen = [c for c, cb in getattr(tp, "_ocr_checks", {}).items() if cb.isChecked()] if tp else []
        return chosen or ["spa", "por", "eng"][:1]

    def _page_layout(self, page_idx: int):
        key = (id(self.doc), page_idx)
        if key in self._copy_cache:
            return self._copy_cache[key]
        tp = getattr(self.win, "tools_page", None)
        engine = tp.ocr_engine.currentData() if tp is not None and hasattr(tp, "ocr_engine") else "tesseract"
        entry = ptl.page_layout(self.doc[page_idx], self._ocr_langs_for_copy(), engine=engine)
        self._copy_cache[key] = entry
        return entry

    def _on_copy_requested(self, page_idx: int, rect, pt):
        ev = self.editor_view
        if self.doc is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            entry = self._page_layout(page_idx)
        except ptl.ToolError as e:
            QApplication.restoreOverrideCursor()
            self.win.snack(str(e), "error")
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.win.snack(f"No se pudo analizar la página: {e}", "error")
            return
        QApplication.restoreOverrideCursor()
        if not entry["words"]:
            self.win.snack("No he encontrado texto en esa página.", "info")
            return
        if rect is not None:                                           # zona arrastrada
            d_rect = ptl.to_analysis_rect(entry, rect)
            res = lt.region_to_text(entry["words"], d_rect, True, entry["h_lines"], entry["v_lines"])
            blocks, shown = res["blocks"], rect
        else:                                                          # clic: el párrafo o la tabla que hay ahí
            d_pt = ptl.to_analysis_rect(entry, (pt[0], pt[1], pt[0], pt[1]))[:2]
            blk = lt.block_at(entry["blocks"], d_pt)
            if blk is None:
                self.win.snack("Ahí no hay texto. Arrastra para elegir una zona.", "info")
                return
            blocks = [blk]
            shown = ptl.from_analysis_rect(entry, blk.bbox)
        if not blocks:
            self.win.snack("Esa zona no contiene texto.", "info")
            return
        ev.show_copy_highlight(page_idx, shown)
        note = ""
        if entry["ocr"]:
            note = ("Esta página es una imagen: el texto se ha reconocido ahora mismo (OCR, idioma: "
                    + ", ".join(ptl.LANG_NAMES.get(l, l) for l in entry.get("langs", [])) + "). Para tenerlo siempre "
                    "buscable y copiable en cualquier lector, usa Herramientas → OCR.")
        dlg = CopyDialog(self.window(), blocks, note)
        dlg.exec()
        ev.clear_copy_highlight()

    # ── Notas, adjuntos y ocultar anotaciones ───────────────────────────
    def _fill_notes_menu(self):
        m = self.notes_menu
        m.clear()
        ev = self.editor_view
        m.addAction(ic.icon("note", TEXT, 17), "Añadir nota", self._enter_note)
        m.addAction(ic.icon("link", TEXT, 17), "Adjuntar archivo…", self._pick_attachment)
        m.addSeparator()
        a = m.addAction("Ocultar anotaciones (solo en pantalla)")
        a.setCheckable(True)
        a.setChecked(ev.hide_annots)
        a.triggered.connect(lambda on: ev.set_hide_annots(bool(on)))
        if ev.mode in ("note", "attach"):
            m.addSeparator()
            m.addAction("Terminar", lambda: ev.set_mode("edit"))

    def _enter_note(self):
        if self.doc is None:
            return
        self._close_panel()
        self.editor_view.set_mode("note")
        self.win.snack("Haz clic donde quieras la nota. Clic en una nota para editarla; arrástrala para moverla.", "info")

    def _on_note_requested(self, page_idx: int, pt, existing):
        author = os.environ.get("USERNAME", "")
        dlg = NoteDialog(self.window(), (existing or {}).get("text", ""), (existing or {}).get("author", "") or author,
                         existing is not None)
        if dlg.exec() != QDialog.Accepted:
            return
        text = dlg.edit.toPlainText().strip()
        if existing is None and not text:
            return
        if not self.editor_view.apply_note(page_idx, pt, existing, text, author, remove=dlg.remove):
            self.win.snack("No se pudo guardar la nota.", "error")

    def _pick_attachment(self):
        if self.doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Elige el archivo que quieres adjuntar", str(Path.home()))
        if not path:
            return
        if os.path.getsize(path) > at.MAX_ATTACH:
            self.win.snack("Ese archivo pesa más de 25 MB; no se adjunta.", "error")
            return
        self._close_panel()
        self.editor_view.set_mode("attach")
        self.editor_view.pending_attach = path
        self.editor_view.viewport().setCursor(Qt.BlankCursor)             # en su lugar viaja el clip con el ratón
        self.win.snack("Mueve el clip hasta donde quieras ponerlo y haz clic. Esc cancela.", "info")

    def _on_attach_clicked(self, page_idx: int, att: dict, gpos):
        m = QMenu(self)
        m.addAction(f"Guardar una copia de «{att['name']}»…", lambda: self._save_attachment(page_idx, att))
        m.addAction("Quitar adjunto", lambda: self.editor_view.remove_attachment(page_idx, att["xref"]))
        m.exec(gpos)

    def _save_attachment(self, page_idx: int, att: dict):
        got = at.read_attachment(self.doc, page_idx, att["xref"])
        if not got:
            self.win.snack("No se pudo leer el adjunto.", "error")
            return
        name, data = got
        dest, _ = QFileDialog.getSaveFileName(self, "Guardar adjunto", str(Path.home() / "Downloads" / Path(name).name))
        if dest:
            Path(dest).write_bytes(data)
            self.win.snack(f"Adjunto guardado: {Path(dest).name}. No se abre solo: ábrelo tú si te fías de su origen.",
                           "success")

    def _reload_doc_from_bytes(self):
        """Reabre el documento desde su estado actual en memoria (conserva deshacer y modo)."""
        snap = be.snapshot_doc_bytes(self.doc)
        if snap:
            self._swap_doc(snap)
            self.editor_view._fm_refresh()

    # ── Formularios ─────────────────────────────────────────────────────
    def _build_form_panel(self, root):
        """Barra del modo formulario: los campos del PDF se rellenan con solo entrar; aquí van las demás acciones."""
        self.form_panel = QFrame()
        self.form_panel.setObjectName("Card")
        self.form_panel.setStyleSheet("QFrame#Card QPushButton { padding:5px 9px; font-size:12px; }")
        fl = FlowLayout(self.form_panel, margin=8, hspacing=6, vspacing=6)
        hint = QLabel("Haz clic en un campo (recuadro azul) para rellenarlo. Arrastra en un hueco para crear uno nuevo.")
        hint.setObjectName("Hint")
        fl.addWidget(hint)
        det = _btn("Detectar campos automáticamente…", "bolt", "Secondary", icon_color=TEXT)
        det.setToolTip("Busca rayas, recuadros vacíos y casillas para convertirlos en campos")
        det.clicked.connect(self._detect_fields)
        fl.addWidget(det)
        tab = _btn("Orden de tabulación", "swap", "Secondary", icon_color=TEXT)
        tab_menu = QMenu(tab)

        def fill_tab():
            tab_menu.clear()
            cur = ft.get_tab_order(self.doc) if self.doc is not None else None
            for key, label in ft.TAB_ORDERS.items():
                a = tab_menu.addAction(label)
                a.setCheckable(True)
                a.setChecked(cur == key)
                a.triggered.connect(lambda _=False, k=key: self._set_tab_order(k))
        tab_menu.aboutToShow.connect(fill_tab)
        tab.setMenu(tab_menu)
        fl.addWidget(tab)
        flat = _btn("Aplanar formulario…", "download", "Secondary", icon_color=TEXT)
        flat.setToolTip("Convierte los campos rellenados en contenido fijo de la página")
        flat.clicked.connect(self._flatten_form)
        fl.addWidget(flat)
        self.form_panel.hide()
        root.addWidget(self.form_panel)

    def _toggle_form_mode(self, checked: bool = False):
        if self.editor_view.mode == "form":
            self.editor_view.set_mode("edit")
        else:
            self._enter_form()

    def _fill_form_menu(self):
        m = self.form_menu
        m.clear()
        active = self.editor_view.mode == "form"
        a = m.addAction("Rellenar y crear campos")
        a.setCheckable(True)
        a.setChecked(active)
        a.triggered.connect(self._enter_form)
        m.addAction("Detectar campos automáticamente…", self._detect_fields)
        tabs = m.addMenu("Orden de tabulación")
        cur = ft.get_tab_order(self.doc) if self.doc is not None else None
        for key, label in ft.TAB_ORDERS.items():
            a = tabs.addAction(label)
            a.setCheckable(True)
            a.setChecked(cur == key)
            a.triggered.connect(lambda _=False, k=key: self._set_tab_order(k))
        m.addAction("Aplanar formulario…", self._flatten_form)
        if active:
            m.addSeparator()
            m.addAction("Terminar", lambda: self.editor_view.set_mode("edit"))

    def _enter_form(self):
        if self.doc is None:
            return
        self._close_panel()
        self.editor_view.set_mode("form")
        n = sum(len(v) for v in self.editor_view._fm_cache.values())
        self.win.snack(("Hay %d campos (recuadros azules): haz clic en uno para rellenarlo. " % n if n else
                        "Este PDF no tiene campos. ") + "Arrastra un recuadro vacío para crear uno nuevo; clic derecho "
                       "sobre un campo para eliminarlo.", "info")

    def _detect_fields(self):
        if self.doc is None:
            return
        found = ft.detect_all(self.doc)
        total = sum(len(v) for v in found.values())
        if not total:
            self.win.snack("No encontré rayas, recuadros vacíos ni casillas que convertir en campos.", "info")
            return
        self._close_panel()
        self.editor_view.set_mode("form")
        self.editor_view.show_candidates(found)
        first = min(found)
        self.editor_view.scroll_to_page(first)
        n_chk = sum(1 for v in found.values() for c in v if c["kind"] == "checkbox")
        resp = QMessageBox.question(
            self, "Detectar campos",
            f"He encontrado {total} posibles campos (marcados en verde): {total - n_chk} de texto y {n_chk} casillas.\n\n"
            "Salen de rayas, recuadros vacíos y cuadritos de la página; revisa que no sobre ninguno (puedes borrar "
            "los que no quieras con clic derecho). ¿Crearlos?", QMessageBox.Yes | QMessageBox.No)
        self.editor_view.show_candidates(None)
        if resp != QMessageBox.Yes:
            return
        self._before_mutate()
        n = ft.create_detected(self.doc, found)
        if n:
            self._mark_dirty()
            self.editor_view.reload_preserving_scroll()
            self.editor_view._fm_refresh()
            self.win.snack(f"{n} campos creados. Haz clic en uno para rellenarlo.", "success")
        else:
            self.win.snack("No se pudo crear ningún campo.", "error")

    def _set_tab_order(self, order: str):
        if self.doc is None:
            return
        if not ft.has_fields(self.doc):
            self.win.snack("Este PDF no tiene campos de formulario.", "info")
            return
        self._before_mutate()
        n = ft.set_tab_order(self.doc, order)
        if n:
            self._mark_dirty()
            self.win.snack(f"Orden de tabulación: {ft.TAB_ORDERS[order].lower()} (en {n} página{'s' if n != 1 else ''}).",
                           "success")

    def _on_field_requested(self, page_idx: int, rect):
        dlg = FieldDialog(self.window(), ft.unique_name(self.doc, "campo"))
        if dlg.exec() == QDialog.Accepted and dlg.spec:
            if self.editor_view.apply_new_field(page_idx, rect, dlg.spec):
                self.win.snack("Campo creado.", "success")
            else:
                self.win.snack("No se pudo crear el campo.", "error")

    def _flatten_form(self):
        if self.doc is None:
            return
        if not ft.has_fields(self.doc):
            self.win.snack("Este PDF no tiene campos de formulario.", "info")
            return
        if QMessageBox.question(self, "Aplanar formulario",
                                "Los campos pasarán a ser contenido fijo de la página, con lo que hayas rellenado: "
                                "ya no se podrán editar. Puedes deshacerlo con Ctrl+Z hasta que guardes.\n\n"
                                "¿Aplanar el formulario?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._before_mutate()
        if ft.flatten(self.doc):
            self._mark_dirty()
            self.editor_view.set_mode("edit")
            self.editor_view.reload_preserving_scroll()
            self.win.snack("Formulario aplanado.", "success")
        else:
            self.win.snack("No se pudo aplanar el formulario.", "error")

    def _toggle_link_mode(self, checked: bool):
        if checked:
            self._close_panel()
            self.editor_view.set_mode("link")
            self.win.snack("Arrastra sobre un texto o un área para crear un enlace. Haz clic en un recuadro azul "
                           "para editarlo o quitarlo.", "info")
        else:
            self.editor_view.set_mode("edit")

    def _on_link_requested(self, page_idx: int, boxes, existing):
        n_zones = len(at.group_of(self.doc, page_idx, existing)) if existing else len(boxes)
        from_obj = bool(getattr(self.editor_view, "_lk_from_object", False)) and existing is None
        dlg = LinkDialog(self.window(), len(self.doc), existing, n_zones, allow_underline=not from_obj)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.remove:
            if self.editor_view.apply_link(page_idx, boxes, existing, None):
                self.win.snack("Enlace quitado.", "info")
            return
        if self.editor_view.apply_link(page_idx, boxes, existing, dlg.result_dest,
                                       underline=existing is None and dlg.underline_cb.isChecked(), obj=from_obj,
                                       color=dlg.link_color):
            self.win.snack("Enlace guardado." if existing else
                           f"Enlace creado ({len(boxes)} zona{'s' if len(boxes) != 1 else ''}).", "success")
            if from_obj and len(boxes) == 1:
                dlg2 = ClickIconDialog(self.window())
                if dlg2.exec() == QDialog.Accepted and dlg2.kind:
                    self._add_click_icon(page_idx, boxes[0], dlg2.kind)
        else:
            self.win.snack("No se pudo guardar el enlace.", "error")

    def _open_icon_picker(self):
        ev = self.editor_view
        if not (ev._img_sel and ev._img_sel.get("icon")):
            return
        old = getattr(self, "_icon_picker", None)
        if old is not None:
            try:
                old.close()
            except RuntimeError:
                pass
        dlg = ClickIconDialog(self.window(), live=ev.swap_selected_icon)
        dlg.setWindowFlag(Qt.Tool, True)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        self._icon_picker = dlg
        dlg.show()

    def _add_click_icon(self, page_idx: int, box, kind: str):
        """Pone el icono elegido («clic aquí») en la esquina inferior derecha de la imagen enlazada; queda
        seleccionado para moverlo o girarlo."""
        x0, y0, x1, y1 = box
        s = max(30.0, min(60.0, 0.5 * min(x1 - x0, y1 - y0)))
        rect = (x1 - s - 4, y1 - s - 4, x1 - 4, y1 - 4)
        self._before_mutate()
        xref = at.add_click_icon(self.doc, page_idx, rect, kind, 0.0)
        if not xref:
            self.win.snack("No se pudo añadir el icono.", "error")
            return
        self._mark_dirty()
        ev = self.editor_view
        ev.refresh_page(page_idx)
        ev.set_mode("image")
        ev._img_select({"page": page_idx, "xref": xref, "rect": rect, "icon": (kind, 0.0)})
        self.win.snack("Icono añadido. Arrástralo para moverlo; el punto de arriba lo gira (o las teclas [ y ]).",
                       "success")

    # ── Imagen ──────────────────────────────────────────────────────────
    def _fill_image_menu(self):
        m = self.image_menu
        m.clear()
        m.addAction(ic.icon("image", TEXT, 17), "Insertar una imagen…", self._pick_image)
        m.addAction(ic.icon("select", TEXT, 17), "Seleccionar, mover o borrar imágenes", self._image_select_mode)
        if self.editor_view.mode == "image":
            m.addSeparator()
            m.addAction("Terminar", lambda: self.editor_view.set_mode("edit"))

    def _image_select_mode(self):
        """Modo imagen sin insertar nada: clic en una imagen (del PDF o puesta aquí) para moverla, escalarla o borrarla."""
        if self.doc is None:
            return
        self._close_panel()
        self.editor_view._img_select(None)
        self.editor_view.set_mode("image")
        self.editor_view.viewport().setCursor(Qt.ArrowCursor)
        self.win.snack("Haz clic en una imagen para seleccionarla: arrástrala para moverla, usa los puntos para cambiar "
                       "el tamaño y pulsa Supr para borrarla (en las imágenes del PDF, solo borrar). Esc para salir.",
                       "info")

    def _pick_image(self):
        if self.doc is None:
            self.image_btn.setChecked(False)
            return
        self._close_panel()                      # suelta lo que hubiera activo (Marcar, Dibujar…) antes de elegir
        path, _ = QFileDialog.getOpenFileName(
            self, "Elige una imagen", str(Path.home() / "Pictures"),
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;Todos los archivos (*.*)")
        if not path:
            self.image_btn.setChecked(self.editor_view.mode == "image")
            return
        try:
            size = at.image_size(path)
        except Exception:
            self.image_btn.setChecked(False)
            self.win.snack("No se pudo leer esa imagen.", "error")
            return
        self.begin_place_image(path, size)

    def begin_place_image(self, source, size, max_frac: float = 0.45, what: str = "la imagen"):
        self._close_panel()
        self.editor_view.start_place_image(source, size, max_frac)
        self.win.snack(f"Haz clic donde quieras {what} (o arrastra para dibujarle el tamaño). Después puedes "
                       "moverla, cambiarle el tamaño por las esquinas (Mayús = deformar) y borrarla con Supr.", "info")

    # ── Firma ───────────────────────────────────────────────────────────
    def _sig_thumb(self, path) -> QIcon:
        pm = QPixmap(str(path))
        thumb = QPixmap(96, 34)
        thumb.fill(QColor("#FFFFFF"))
        if not pm.isNull():
            pa = QPainter(thumb)
            pa.setRenderHint(QPainter.SmoothPixmapTransform)
            scaled = pm.scaled(88, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pa.drawPixmap((96 - scaled.width()) // 2, (34 - scaled.height()) // 2, scaled)
            pa.end()
        return QIcon(thumb)

    def _fill_sign_menu(self):
        m = self.sign_menu
        m.clear()
        saved = sp.list_saved()
        for path in saved[:10]:
            act = m.addAction(self._sig_thumb(path), "  " + sp.display_name(path))
            act.triggered.connect(lambda _=False, p_=path: self._place_signature(p_))
        if saved:
            m.addSeparator()
        m.addAction("Crear firma nueva…", self._new_signature)
        if saved:
            dm = m.addMenu("Gestionar mis firmas")
            for path in saved[:10]:
                sm = dm.addMenu(self._sig_thumb(path), "  " + sp.display_name(path))
                sm.addAction("Cambiar el nombre…", lambda _=False, p_=path: self._rename_signature(p_))
                if sp.load_meta(path).get("type") in ("draw", "text"):
                    sm.addAction("Editar…", lambda _=False, p_=path: self._edit_signature(p_))
                sm.addAction("Borrar", lambda _=False, p_=path: self._delete_signature(p_))

    def _rename_signature(self, path):
        name, ok = QInputDialog.getText(self, "Nombre de la firma", "Nombre:", text=sp.display_name(path))
        if ok and name.strip():
            sp.rename(path, name)
            self.win.snack("Firma renombrada.", "info")

    def _edit_signature(self, path):
        dlg = sp.SignatureDialog(self.window(), edit_path=path)
        if dlg.exec() == QDialog.Accepted:
            self.win.snack("Firma actualizada. Se usará la nueva versión en los documentos siguientes.", "success")

    def _on_save_signature(self, desc: dict):
        """Clic derecho sobre un dibujo libre → guardarlo como firma reutilizable."""
        strokes = [[QPointF(x, y) for x, y in st] for st in desc.get("strokes", []) if len(st) > 1]
        rgb = desc.get("stroke") or (0.1, 0.1, 0.1)
        color = "#%02x%02x%02x" % tuple(int(c * 255) for c in rgb)
        width = max(1.0, float(desc.get("width", 2.0)) / (5 if desc.get("marker") else 1))
        img = sp.render_strokes(strokes, color, width, scale=5.0)
        if img is None:
            self.win.snack("Ese dibujo no se puede guardar como firma.", "error")
            return
        name, ok = QInputDialog.getText(self, "Guardar como firma", "Nombre de la firma:", text="Firma")
        if not ok:
            return
        sp.save_png(img, keep=True, name=name, meta=sp.strokes_meta(strokes, color, width))
        self.win.snack("Firma guardada: la tienes en el menú Firma.", "success")

    def _new_signature(self):
        if self.doc is None:
            return
        self._close_panel()
        dlg = sp.SignatureDialog(self.window())
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            self._place_signature(dlg.result_path)

    def _place_signature(self, path):
        try:
            size = at.image_size(str(path))
        except Exception:
            self.win.snack("No se pudo abrir esa firma.", "error")
            return
        self.begin_place_image(str(path), size, max_frac=0.22, what="la firma")

    def _delete_signature(self, path):
        if QMessageBox.question(self, "Borrar firma", "¿Borrar esta firma guardada?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            sp.delete_saved(path)
            self.win.snack("Firma borrada.", "info")

    # ── Formas: rectángulo, elipse, línea, flecha ───────────────────────
    # ── Barra de dibujo: formas + color, relleno y grosor ───────────────
    def _build_shape_panel(self, root):
        self.shape_panel = QFrame()
        self.shape_panel.setObjectName("Card")
        self.shape_panel.setStyleSheet(
            "QFrame#Card QPushButton { padding:5px 9px; font-size:12px; }")
        fl = FlowLayout(self.shape_panel, margin=8, hspacing=6, vspacing=6)
        self._shape_tool_btns = {}
        for kind, label in self._SHAPE_TOOLS:
            icon_name = {"select": "select", "pen": "pen", "marker": "highlight", "rect": "rect", "ellipse": "ellipse",
                         "line": "line", "arrow": "arrow"}[kind]
            b = _btn(label, icon_name, "Secondary", icon_color=TEXT)
            b.setCheckable(True)
            b.setToolTip(label)
            b.clicked.connect(lambda _=False, k=kind: self._enter_shape(kind=k))
            fl.addWidget(b)
            self._shape_tool_btns[kind] = b
        self.sh_stroke_btn = QPushButton(); self.sh_fill_btn = QPushButton()
        for b, tip in ((self.sh_stroke_btn, "Color del borde / trazo"), (self.sh_fill_btn, "Color de relleno (rectángulo y elipse)")):
            b.setObjectName("Secondary")
            b.setToolTip(tip)
            fl.addWidget(b)
        self.sh_stroke_btn.clicked.connect(lambda: self._shape_color_menu(self.sh_stroke_btn, False))
        self.sh_fill_btn.clicked.connect(lambda: self._shape_color_menu(self.sh_fill_btn, True))
        self.sh_width_combo = QComboBox()
        for w, label in ((1.0, "Fino"), (2.0, "Normal"), (4.0, "Grueso"), (7.0, "Muy grueso")):
            self.sh_width_combo.addItem("Grosor: " + label, w)
        self.sh_width_combo.setToolTip("Grosor de la línea")
        self.sh_width_combo.activated.connect(lambda i: self._enter_shape(width=self.sh_width_combo.itemData(i)))
        fl.addWidget(self.sh_width_combo)
        self.sh_op_btn = QPushButton()
        self.sh_op_btn.setObjectName("Secondary")
        self.sh_op_btn.setToolTip("Opacidad: total por defecto 100 %; opcionalmente otra para el trazo o el relleno")
        self.sh_op_btn.clicked.connect(self._shape_opacity_menu)
        fl.addWidget(self.sh_op_btn)
        self.sh_head_combo = QComboBox()
        for name, label in at.HEAD_LABELS:
            self.sh_head_combo.addItem(label, name)
        self.sh_head_combo.setToolTip("Forma de la punta de las flechas")
        self.sh_head_combo.activated.connect(lambda i: self._set_shape_head(self.sh_head_combo.itemData(i)))
        fl.addWidget(self.sh_head_combo)
        self.shape_panel.hide()
        root.addWidget(self.shape_panel)

    def _shape_color_menu(self, anchor, fill: bool):
        ap = (lambda v: self._enter_shape(fill=v)) if fill else (lambda v: self._enter_shape(color=v))
        m = color_menu(self, self.editor_view, fill, ap)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _shape_opacity_menu(self):
        ev = self.editor_view
        so = ev.shape_stroke_op if ev.shape_stroke_op is not None else ev.shape_opacity
        fo = ev.shape_fill_op if ev.shape_fill_op is not None else ev.shape_opacity
        m = opacity_menu(self, self._set_shape_opacity, has_fill=True, current=(so, fo))
        m.exec(self.sh_op_btn.mapToGlobal(self.sh_op_btn.rect().bottomLeft()))

    def _set_shape_opacity(self, part, v):
        ev = self.editor_view
        v = float(v)
        if part == "total":
            ev.shape_opacity, ev.shape_stroke_op, ev.shape_fill_op = v, None, None
        elif part == "stroke":
            ev.shape_stroke_op = v
        else:
            ev.shape_fill_op = v
        if ev._ss_sel and ev.mode == "shape":
            kw = {"total": "opacity", "stroke": "stroke_op", "fill": "fill_op"}[part]
            ev.restyle_selection(**{kw: v})
        self._sync_shape_panel()

    def _set_shape_head(self, name):
        ev = self.editor_view
        ev.shape_head = name
        if ev._ss_sel and ev.mode == "shape":
            ev.restyle_selection(head=name)

    def _sync_shape_panel(self):
        ev = self.editor_view
        for kind, b in self._shape_tool_btns.items():
            b.setChecked(kind == ev.shape_kind)
        self.sh_stroke_btn.setIcon(SelectionBar._swatch(at.rgb_of(ev.shape_color)))
        self.sh_stroke_btn.setText("  Borde")
        self.sh_fill_btn.setIcon(SelectionBar._swatch(at.rgb_of(ev.shape_fill) if ev.shape_fill else None))
        so = ev.shape_stroke_op if ev.shape_stroke_op is not None else ev.shape_opacity
        fo = ev.shape_fill_op if ev.shape_fill_op is not None else ev.shape_opacity
        self.sh_op_btn.setText("  Opacidad %d %%" % round(so * 100) if abs(so - fo) < 0.01
                               else "  Opacidad %d/%d %%" % (round(so * 100), round(fo * 100)))
        i = self.sh_head_combo.findData(ev.shape_head)
        if i >= 0:
            self.sh_head_combo.setCurrentIndex(i)
        self.sh_fill_btn.setText("  Relleno")
        i = self.sh_width_combo.findData(ev.shape_width)
        if i >= 0:
            self.sh_width_combo.setCurrentIndex(i)

    def _toggle_shape_panel(self, checked: bool = False):
        if self.editor_view.mode == "shape":
            self.editor_view.set_mode("edit")
            return
        if self.editor_view.shape_kind == "select":
            self.editor_view.shape_kind = "rect"
        self._enter_shape()

    def _on_shape_kind_changed(self, kind: str):
        self._sync_shape_panel()

    _SHAPE_TOOLS = (("select", "Seleccionar / mover"), ("pen", "Lápiz libre"), ("marker", "Rotulador libre"),
                    ("rect", "Rectángulo"),
                    ("ellipse", "Elipse"), ("line", "Línea"), ("arrow", "Flecha"))

    def _fill_shape_menu(self):
        m = self.shape_menu
        m.clear()
        ev = self.editor_view
        active = ev.mode == "shape"
        for kind, label in self._SHAPE_TOOLS:
            act = m.addAction(label)
            act.setCheckable(True)
            act.setChecked(active and ev.shape_kind == kind)
            act.triggered.connect(lambda _=False, k=kind: self._enter_shape(kind=k))
            if kind in ("select", "marker"):
                m.addSeparator()
        if active and ev._ss_sel:
            m.addAction("Duplicar selección\tCtrl+D", ev.duplicate_selection)
            m.addAction("Eliminar selección\tSupr", ev.delete_selection)
        m.addSeparator()

        def swatch(rgb):
            pm = QPixmap(14, 14)
            pm.fill(QColor(*(int(c * 255) for c in rgb)))
            return QIcon(pm)
        sub_c = m.addMenu("Color del borde")
        for name, rgb in at.SHAPE_COLORS.items():
            a = sub_c.addAction(swatch(rgb), name.capitalize())
            a.setCheckable(True)
            a.setChecked(name == ev.shape_color)
            a.triggered.connect(lambda _=False, n=name: self._enter_shape(color=n))
        sub_w = m.addMenu("Grosor")
        for w, label in ((1.0, "Fino"), (2.0, "Normal"), (4.0, "Grueso"), (7.0, "Muy grueso")):
            a = sub_w.addAction(label)
            a.setCheckable(True)
            a.setChecked(ev.shape_width == w)
            a.triggered.connect(lambda _=False, v=w: self._enter_shape(width=v))
        sub_f = m.addMenu("Relleno (formas)")
        a = sub_f.addAction("Sin relleno")
        a.setCheckable(True)
        a.setChecked(ev.shape_fill is None)
        a.triggered.connect(lambda _=False: self._enter_shape(fill=""))
        for name, rgb in at.SHAPE_COLORS.items():
            a = sub_f.addAction(swatch(rgb), name.capitalize())
            a.setCheckable(True)
            a.setChecked(ev.shape_fill == name)
            a.triggered.connect(lambda _=False, n=name: self._enter_shape(fill=n))
        if active:
            m.addSeparator()
            m.addAction("Terminar de dibujar", lambda: ev.set_mode("edit"))

    def _enter_shape(self, kind=None, color=None, width=None, fill=None):
        ev = self.editor_view
        sel = ev._ss_sel if ev.mode == "shape" else None
        if kind:
            ev.shape_kind = kind
        if color:
            ev.shape_color = color
        if width:
            ev.shape_width = width
        if fill is not None:
            ev.shape_fill = fill or None
        self._close_panel()
        ev.set_mode("shape")
        ev.viewport().setCursor(Qt.ArrowCursor if ev.shape_kind == "select" else Qt.CrossCursor)
        self._sync_shape_panel()
        if sel and not kind and (color or width or fill is not None):
            ev._ss_select(sel["page"], sel["desc"])              # la selección sigue; cambia su estilo
            ev.restyle_selection(color, width, fill)
            return
        if ev.shape_kind == "select":
            self.win.snack("Clic en una forma o trazo para seleccionarlo: arrastra para mover, puntos blancos para "
                           "cambiar el tamaño, Ctrl+D duplica, Supr borra.", "info")
            return
        if ev.shape_kind in ("pen", "marker"):
            self.win.snack("Dibuja con el ratón. Para mover, escalar o duplicar un trazo: «Seleccionar / mover».", "info")
        else:
            self.win.snack("Arrastra para dibujar (Mayús para proporción exacta). Para mover, escalar o duplicar "
                           "una forma ya dibujada, elige «Seleccionar / mover» o haz clic en su borde.", "info")

    # ── Marcar texto: resaltar, subrayar, tachar ────────────────────────
    _MARK_TOOLS = (("highlight", "Resaltar", "highlight"), ("underline", "Subrayar", "underline"),
                   ("strike", "Tachar", "strike"), ("erase", "Quitar marca", "eraser"))

    def _fill_annot_menu(self):
        m = self.annot_menu
        m.clear()
        ev = self.editor_view
        active = ev.mode == "markup"
        for kind, label, icon_name in self._MARK_TOOLS:
            act = m.addAction(ic.icon(icon_name, TEXT, 17), label)
            act.setCheckable(True)
            act.setChecked(active and ev.markup_kind == kind)
            act.triggered.connect(lambda _=False, k=kind: self._enter_markup(k))
        m.addSeparator()
        sub = m.addMenu("Color")
        cur = ev.markup_color or at.DEFAULT_COLOR.get(ev.markup_kind, "amarillo")
        for name, rgb in at.COLORS.items():
            pm = QPixmap(14, 14)
            pm.fill(QColor(*(int(c * 255) for c in rgb)))
            act = sub.addAction(QIcon(pm), name.capitalize())
            act.setCheckable(True)
            act.setChecked(name == cur)
            act.triggered.connect(lambda _=False, n=name: self._set_markup_color(n))
        if active:
            m.addSeparator()
            m.addAction("Terminar de marcar", lambda: ev.set_mode("edit"))

    def _enter_markup(self, kind: str):
        ev = self.editor_view
        if kind != ev.markup_kind:
            ev.markup_color = None             # cada herramienta vuelve a su color normal
        ev.markup_kind = kind
        self._close_panel()
        ev.set_mode("markup")
        label = {"highlight": "Resaltar", "underline": "Subrayar", "strike": "Tachar", "erase": "Quitar marca"}[kind]
        self.annot_btn.setText("  " + label)
        self.win.snack("Haz clic sobre una marca para quitarla." if kind == "erase"
                       else "Arrastra sobre el texto (o haz clic en una palabra) para marcarlo.", "info")

    def _set_markup_color(self, name: str):
        ev = self.editor_view
        ev.markup_color = name
        if ev.markup_kind == "erase":
            ev.markup_kind = "highlight"
        self._enter_markup(ev.markup_kind)

    def _toggle_manual(self, checked: bool):
        ev = self.editor_view
        ev.manual = checked
        self.manual_btn.setText("Manual" if checked else "Automático")
        ev.reload_preserving_scroll()
        self.win.snack("Modo manual: cada línea se edita por separado y no se mueve nada más." if checked
                       else "Modo automático: párrafos, listas, cabecera, pie y numeración.", "info")

    def _mark_dirty(self):
        self.dirty = True
        self._schedule_draft()

    # ── Borrador automático (carpeta temporal) ─────────────────────────
    def _schedule_draft(self):
        t = getattr(self, "_draft_timer", None)
        if t is None:
            t = self._draft_timer = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(2500)
            t.timeout.connect(self._write_draft)
        t.start()

    def _write_draft(self):
        if self.doc is None:
            return
        if self.dirty:
            dr.save(self.doc, (self.current_file or {}).get("name", "documento.pdf"))
        else:
            dr.clear()

    def _restart_with_doc(self):
        """Reinicia la aplicación y reabre este mismo documento (con sus cambios sin guardar)."""
        if self.doc is None:
            return
        if self.editor_view._editor is not None:
            self.editor_view._close_inline_editor(commit=True)
        name = (self.current_file or {}).get("name", "documento.pdf")
        if not dr.save(self.doc, name, restart=True, dirty=self.dirty):
            self.win.snack("No se pudo guardar el borrador para reiniciar.", "error")
            return
        from PySide6.QtCore import QProcess
        args = [os.path.abspath(sys.argv[0])] if not getattr(sys, "frozen", False) else []
        if QProcess.startDetached(sys.executable, args, os.getcwd()):
            self.win._force_quit = True
            self.win.close()
        else:
            self.win.snack("No se pudo reiniciar la aplicación; ábrela tú y te preguntará si continúas.", "error")

    def _warn_font_missing(self, family: str):
        if family in self._warned_fonts:
            return
        self._warned_fonts.add(family)
        fb = self.editor_view._FALLBACK_FONT
        self.win.snack(
            f"La fuente «{family}» no está instalada: se ha usado «{fb}» en su lugar. Si quieres usar «{family}», "
            f"instálala en Windows (doble clic en su archivo → Instalar) y reabre la aplicación.", "info")

    def _maybe_prompt_save(self):
        if self.dirty and self.doc is not None:
            resp = QMessageBox.question(
                self, "Cambios sin guardar",
                "Tienes cambios sin guardar en este PDF. ¿Guardarlos antes de cambiar de archivo?",
                QMessageBox.Yes | QMessageBox.No)
            if resp == QMessageBox.Yes:
                self._save_changes()

    def _save_changes(self):
        if not self.doc or not self.current_file:
            self.win.snack("Selecciona un archivo", "error"); return
        out = be.save_edit_session(self.doc, self.current_file["path"])
        if out:
            idx = self.file_combo.currentIndex()
            new_f = self.win.replace_file(self.current_file, out)
            self.current_file = new_f
            self.file_combo.blockSignals(True)
            self.file_combo.setItemText(idx, new_f["name"])
            self.file_combo.blockSignals(False)
            self.dirty = False
            dr.clear()
            self.win.snack(f"✓ Guardado: {Path(out).name} — "
                            "listo para guardar una copia o seguir con otra herramienta", "success")
        else:
            self.win.snack("No se pudo guardar", "error")

    # ── Censurar texto (global, por búsqueda) ───────────────────────────
    def _do_censor(self):
        texto = self.censor_field.text().strip()
        if not texto:
            self.win.snack("Escribe el texto a censurar", "error"); return
        f = self._selected_file()
        if not f:
            self.win.snack("Selecciona un archivo", "error"); return
        self.win.snack("Censurando…", "info")

        def _run():
            out = be.censor_text_in_pdf(f["path"], texto)

            def done():                                           # esto sí toca la pantalla: en su hilo
                if out:
                    self.win.record_step("censor", {"texto": texto})
                    self.win.replace_file(f, out)
                    self.win.snack(f"✓ Censurado (sin vuelta atrás): {Path(out).name} — "
                                    "listo para guardar o seguir con otra herramienta", "success")
                    self.populate()
                    self._close_panel()
                else:
                    self.win.snack("No se encontró ese texto en el PDF", "error")
            on_gui(done)

        run_bg(_run)

    def _on_replace_requested(self, text: str):
        """«Reemplazar…» desde el clic derecho: abre el panel con el texto ya puesto, solo falta escribir el nuevo."""
        self.editor_view._close_inline_editor(commit=True)
        if self._active_panel != "find":
            self._toggle_panel("find")
        self.buscar_field.setText(text.strip())
        self.reemplazar_field.clear()
        self.reemplazar_field.setFocus()
        self.win.snack("Escribe el texto nuevo y pulsa Reemplazar.", "info")

    def _do_find_replace(self):
        buscar = self.buscar_field.text().strip()
        reemplazar = self.reemplazar_field.text()
        if not buscar:
            self.win.snack("Escribe el texto a buscar", "error"); return
        if self.doc is None:
            self.win.snack("Selecciona un archivo", "error"); return
        ev = self.editor_view
        ev._close_inline_editor(commit=True)

        def ask(page, para, new_runs):
            # Con una sola página no se pueden deducir cabecera y pie: si el cambio crea una página, se pregunta antes.
            if ev.hf is None and len(self.doc) < 2 and not ev.manual:
                added = be.paragraph_edit_adds_pages(self.doc, page, para, "".join(r["text"] for r in new_runs),
                                                     para["size"], para["color"], runs=[dict(r) for r in new_runs])
                if added and not ev.ask_header_footer(
                        page, "El texto nuevo no cabe y se creará una página. Marca la cabecera y el pie para no "
                              "tocarlos y decide cómo se repiten. Si cancelas, no se reemplaza nada más."):
                    return False
            return True

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = be.replace_text_in_doc(self.doc, buscar, reemplazar, settings=ev.hf, manual=ev.manual,
                                         case=self.case_cb.isChecked(), before=self._before_mutate, ask_pages=ask)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.win.snack(f"No se pudo reemplazar: {e}", "error")
            return
        QApplication.restoreOverrideCursor()
        if res["cancelled"]:
            if res["count"]:
                self._do_undo()                                  # no se deja a medias
            self.win.snack("Cancelado: no se ha reemplazado nada.", "info")
            return
        if not res["count"]:
            self.win.snack("No se encontró ese texto en el PDF.", "error")
            return
        self._mark_dirty()
        self.win.record_step("find_replace", {"buscar": buscar, "reemplazar": reemplazar})
        ev.reload_preserving_scroll()
        self.win.snack(f"✓ {res['count']} cambio{'s' if res['count'] != 1 else ''} en "
                       f"{len(res['pages'])} página{'s' if len(res['pages']) != 1 else ''}. Ctrl+Z lo deshace.", "success")


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: METADATA
# ══════════════════════════════════════════════════════════════════════════
class MetadataPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("Metadata – Ver / editar / borrar", lambda: win.go_home()))

        root.addWidget(QLabel("Archivo:"))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._load_fields)
        root.addWidget(self.file_combo)

        card = QFrame(); card.setObjectName("Card")
        add_shadow(card, blur=18, dy=4, alpha=70)
        c = QVBoxLayout(card)
        self.title_field    = self._field("Título")
        self.author_field   = self._field("Autor")
        self.subject_field  = self._field("Asunto")
        self.keywords_field = self._field("Palabras clave")
        self.creator_field  = self._field("Creador (programa de origen)")
        self.producer_field = self._field("Productor (motor que generó el PDF)")
        for w in (self.title_field, self.author_field, self.subject_field, self.keywords_field,
                  self.creator_field, self.producer_field):
            c.addWidget(w)

        dates_row = QHBoxLayout()
        self.creation_date_label = QLabel("Creado: —")
        self.creation_date_label.setObjectName("Hint")
        self.mod_date_label = QLabel("Modificado: —")
        self.mod_date_label.setObjectName("Hint")
        dates_row.addWidget(self.creation_date_label)
        dates_row.addWidget(self.mod_date_label)
        dates_row.addStretch(1)
        c.addLayout(dates_row)

        root.addWidget(card)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Guardar cambios")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._do_save)
        clear_btn = QPushButton("Borrar todos los metadatos")
        clear_btn.setObjectName("Danger")
        clear_btn.clicked.connect(self._do_clear)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        root.addLayout(btn_row)
        root.addStretch(1)

    def _field(self, label: str) -> QLineEdit:
        f = QLineEdit()
        f.setPlaceholderText(label)
        return f

    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)
        self._load_fields()

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _load_fields(self, *_):
        f = self._selected_file()
        if not f:
            return
        meta = be.read_metadata(f["path"])
        self.title_field.setText(meta.get("title", "") or "")
        self.author_field.setText(meta.get("author", "") or "")
        self.subject_field.setText(meta.get("subject", "") or "")
        self.keywords_field.setText(meta.get("keywords", "") or "")
        self.creator_field.setText(meta.get("creator", "") or "")
        self.producer_field.setText(meta.get("producer", "") or "")
        self.creation_date_label.setText(
            f"Creado: {be.format_pdf_date(meta.get('creationDate', ''))}")
        self.mod_date_label.setText(
            f"Modificado: {be.format_pdf_date(meta.get('modDate', ''))}")

    def _do_save(self):
        f = self._selected_file()
        if not f:
            self.win.snack("Selecciona un archivo", "error"); return
        meta = {
            "title": self.title_field.text(),
            "author": self.author_field.text(),
            "subject": self.subject_field.text(),
            "keywords": self.keywords_field.text(),
            "creator": self.creator_field.text(),
            "producer": self.producer_field.text(),
        }
        out = be.write_metadata(f["path"], meta)
        if out:
            orig = be.read_metadata(f["path"])
            changed = {k: v for k, v in meta.items() if (orig.get(k) or "") != v}
            if changed:
                self.win.record_step("metadata", changed)
            self.win.replace_file(f, out)
            self.populate()
            self.win.snack(f"✓ Metadatos guardados: {Path(out).name} — "
                            "listo para guardar o seguir con otra herramienta", "success")
        else:
            self.win.snack("No se pudieron guardar los metadatos", "error")

    def _do_clear(self):
        f = self._selected_file()
        if not f:
            self.win.snack("Selecciona un archivo", "error"); return
        out = be.clear_metadata(f["path"])
        if out:
            self.win.record_step("metadata_clear")
            self.win.replace_file(f, out)
            self.populate()
            self.win.snack(f"✓ Metadatos eliminados: {Path(out).name} — "
                            "listo para guardar o seguir con otra herramienta", "success")
        else:
            self.win.snack("No se pudieron eliminar los metadatos", "error")


# ══════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: ¿dónde guardar? (carpeta o .zip)
# ══════════════════════════════════════════════════════════════════════════
class DestinationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("¿Dónde guardar?")
        self.choice = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("¿Cómo quieres guardar los archivos generados?"))
        btn_row = QHBoxLayout()
        folder_btn = _btn("En una carpeta", "folder", "Primary")
        zip_btn = _btn("Como archivo .zip", "archive")
        folder_btn.clicked.connect(lambda: self._pick("folder"))
        zip_btn.clicked.connect(lambda: self._pick("zip"))
        btn_row.addWidget(folder_btn)
        btn_row.addWidget(zip_btn)
        lay.addLayout(btn_row)

    def _pick(self, choice: str):
        self.choice = choice
        self.accept()


# ══════════════════════════════════════════════════════════════════════════
#  GRID DE PÁGINAS SELECCIONABLES (sin reordenar) — para elegir con el ratón
# ══════════════════════════════════════════════════════════════════════════
class SelectablePageGrid(QListWidget):
    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSpacing(10)
        self.setIconSize(QSize(148, 196))
        self.itemSelectionChanged.connect(self._refresh_icons)

    def _refresh_icons(self):
        for r in range(self.count()):
            item = self.item(r)
            pg = item.data(Qt.UserRole)
            pix = render_page_card(pg["png"], pg["label"], pg["color"],
                                    selected=item.isSelected())
            item.setIcon(QIcon(pix))


def render_page_card(png_bytes: bytes | None, label: str, color: str,
                      width: int = 148, height: int = 196, selected: bool = False) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    p.setBrush(QColor(ACCENT) if selected else QColor(SURFACE_2))
    pen = QPen(QColor(color)); pen.setWidth(3 if selected else 2)
    p.setPen(pen)
    p.drawRoundedRect(1, 1, width - 2, height - 2, 12, 12)

    thumb_area = QRect(10, 10, width - 20, height - 48)
    p.setPen(Qt.NoPen)
    if png_bytes:
        thumb = QPixmap()
        thumb.loadFromData(png_bytes)
        thumb = thumb.scaled(thumb_area.width(), thumb_area.height(),
                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = thumb_area.x() + (thumb_area.width() - thumb.width()) // 2
        y = thumb_area.y() + (thumb_area.height() - thumb.height()) // 2
        p.drawPixmap(x, y, thumb)
    else:
        fallback_icon = ic.icon("document", TEXT_SOFT, 28).pixmap(28, 28)
        p.drawPixmap(thumb_area.center().x() - 14, thumb_area.center().y() - 14, fallback_icon)

    chip = QRect(10, height - 32, width - 20, 22)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(chip, 7, 7)
    p.setPen(QColor("#1C1409"))
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.drawText(chip, Qt.AlignCenter, (f"✓ {label}" if selected else label))

    p.end()
    return pix


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: SPLIT  —  3 modos: cada página individual / elegir con el ratón /
#  dividir por página de referencia
# ══════════════════════════════════════════════════════════════════════════
class SplitPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("Split – Dividir PDF", lambda: win.go_home()))

        root.addWidget(QLabel("Archivo:"))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        root.addWidget(self.file_combo)

        mode_row = QWidget()
        mode_flow = FlowLayout(mode_row, margin=0, hspacing=16, vspacing=4)
        self.radio_each = QRadioButton("Cada página en un archivo")
        self.radio_pick = QRadioButton("Elegir páginas con el ratón")
        self.radio_ref  = QRadioButton("Dividir por página de referencia")
        self.radio_each.setChecked(True)
        group = QButtonGroup(self)
        for rb in (self.radio_each, self.radio_pick, self.radio_ref):
            group.addButton(rb)
            mode_flow.addWidget(rb)
        root.addWidget(mode_row)
        self.radio_each.toggled.connect(self._switch_panel)
        self.radio_pick.toggled.connect(self._switch_panel)
        self.radio_ref.toggled.connect(self._switch_panel)

        self.panels = QStackedWidget()
        root.addWidget(self.panels, 1)
        self.panel_each = self._build_panel_each()
        self.panel_pick = self._build_panel_pick()
        self.panel_ref  = self._build_panel_ref()
        self.panels.addWidget(self.panel_each)
        self.panels.addWidget(self.panel_pick)
        self.panels.addWidget(self.panel_ref)

    # ── Panel 1: cada página en un archivo ──────────────────────────────
    def _build_panel_each(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        card = QFrame(); card.setObjectName("Card")
        add_shadow(card, blur=18, dy=4, alpha=70)
        c = QVBoxLayout(card)

        self.naming_prefix_radio = QRadioButton("Prefijo + número de página")
        self.naming_list_radio   = QRadioButton("Lista de nombres (una por línea)")
        self.naming_prefix_radio.setChecked(True)
        ngroup = QButtonGroup(w)
        ngroup.addButton(self.naming_prefix_radio)
        ngroup.addButton(self.naming_list_radio)
        c.addWidget(self.naming_prefix_radio)

        self.prefix_field = QLineEdit()
        self.prefix_field.setPlaceholderText("Prefijo, p.ej. Pagina_")
        self.prefix_field.setText("Pagina_")
        c.addWidget(self.prefix_field)

        c.addWidget(self.naming_list_radio)
        self.names_text = QTextEdit()
        self.names_text.setPlaceholderText("Casa\nSilla\nMesa\n…\n(una línea = el nombre de cada página, en orden)")
        self.names_text.setFixedHeight(140)
        c.addWidget(self.names_text)

        lay.addWidget(card)

        split_btn = _btn("Dividir en páginas sueltas", "scissors", "Primary")
        split_btn.clicked.connect(self._do_split_each)
        lay.addWidget(split_btn)
        lay.addStretch(1)
        return w

    # ── Panel 2: elegir páginas con el ratón ────────────────────────────
    def _build_panel_pick(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel("Clic para seleccionar · Ctrl/Shift+clic para varias páginas")
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        self.pick_grid = SelectablePageGrid()
        lay.addWidget(self.pick_grid, 1)
        btn_row = QWidget()
        btn_flow = FlowLayout(btn_row, margin=0, hspacing=8, vspacing=6)
        save_sel_btn = _btn("Guardar selección", "save", "Primary")
        save_sel_btn.clicked.connect(self._do_save_selection)
        split_two_btn = _btn("Dividir en 2 (seleccionadas / resto)", "scissors", "Secondary", icon_color=TEXT)
        split_two_btn.clicked.connect(self._do_split_selection_vs_rest)
        btn_flow.addWidget(save_sel_btn)
        btn_flow.addWidget(split_two_btn)
        lay.addWidget(btn_row)
        return w

    # ── Panel 3: dividir por página de referencia ───────────────────────
    def _build_panel_ref(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        card = QFrame(); card.setObjectName("Card")
        add_shadow(card, blur=18, dy=4, alpha=70)
        c = QVBoxLayout(card)
        c.addWidget(QLabel("Página de referencia:"))
        self.ref_spin = QSpinBox()
        self.ref_spin.setRange(2, 2)
        c.addWidget(self.ref_spin)
        hint = QLabel("El primer archivo tendrá las páginas anteriores a la de referencia; "
                       "el segundo, desde la página de referencia hasta el final.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        c.addWidget(hint)
        lay.addWidget(card)

        ref_btn = _btn("Dividir por página de referencia", "scissors", "Primary")
        ref_btn.clicked.connect(self._do_split_reference)
        lay.addWidget(ref_btn)
        lay.addStretch(1)
        return w

    def _switch_panel(self):
        if self.radio_each.isChecked():
            self.panels.setCurrentWidget(self.panel_each)
        elif self.radio_pick.isChecked():
            self.panels.setCurrentWidget(self.panel_pick)
            self._populate_pick_grid()
        else:
            self.panels.setCurrentWidget(self.panel_ref)

    # ── Datos comunes ────────────────────────────────────────────────────
    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)
        self._on_file_changed()
        self._switch_panel()

    def _on_file_changed(self, *_):
        total = be.safe_page_count(self._selected_path() or "")
        self.ref_spin.setRange(2, max(2, total))
        if self.panels.currentWidget() is self.panel_pick:
            self._populate_pick_grid()

    def _selected_path(self) -> str | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]["path"]

    def _populate_pick_grid(self):
        self.pick_grid.clear()
        path = self._selected_path()
        if not path:
            return
        total = be.safe_page_count(path)
        for i in range(total):
            png = be.get_page_thumbnail_png(path, i)
            pg = {"idx": i, "label": f"Pág. {i + 1}", "color": ACCENT, "png": png}
            pix = render_page_card(png, pg["label"], pg["color"])
            item = QListWidgetItem(QIcon(pix), "")
            item.setData(Qt.UserRole, pg)
            item.setSizeHint(QSize(pix.width() + 6, pix.height() + 6))
            self.pick_grid.addItem(item)

    def _ask_destination_and_save(self, outputs: list[tuple[str, bytes]], default_name: str):
        if not outputs:
            self.win.snack("No hay páginas que guardar", "error"); return
        if len(outputs) == 1:
            name, data = outputs[0]
            dest, _ = QFileDialog.getSaveFileName(self, "Guardar como", name, "PDF (*.pdf)")
            if not dest:
                return
            Path(dest).write_bytes(data)
            self.win.snack(f"✓ Guardado: {Path(dest).name}")
            return
        dlg = DestinationDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.choice == "folder":
            folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta destino")
            if not folder:
                return
            paths = be.save_outputs_to_folder(outputs, folder)
            self.win.snack(f"✓ {len(paths)} archivo(s) guardados en {Path(folder).name}/")
        else:
            zip_path, _ = QFileDialog.getSaveFileName(
                self, "Guardar como ZIP", f"{default_name}.zip", "ZIP (*.zip)")
            if not zip_path:
                return
            be.save_outputs_to_zip(outputs, zip_path)
            self.win.snack(f"✓ ZIP guardado: {Path(zip_path).name}")

    # ── Acción: cada página en un archivo ───────────────────────────────
    def _do_split_each(self):
        path = self._selected_path()
        if not path:
            self.win.snack("Selecciona un archivo", "error"); return
        total = be.safe_page_count(path)
        if total == 0:
            self.win.snack("El PDF no tiene páginas", "error"); return
        stem = Path(path).stem

        if self.naming_list_radio.isChecked():
            raw_lines = self.names_text.toPlainText().split("\n")
            while raw_lines and raw_lines[-1].strip() == "":
                raw_lines.pop()  # solo quita el salto de línea final sobrante
            lines = [ln.strip() for ln in raw_lines]
            names = []
            faltan = False
            for i in range(total):
                if i < len(lines) and lines[i]:
                    names.append(lines[i])
                else:
                    names.append(f"Pagina_{i + 1}")
                    faltan = True
            if faltan:
                QMessageBox.warning(
                    self, "Faltan nombres",
                    f"El PDF tiene {total} páginas pero diste menos nombres. "
                    "A las páginas sin nombre se les asignará 'Pagina_N'.")
        else:
            prefix = self.prefix_field.text().strip() or "Pagina_"
            names = [f"{prefix}{i + 1}" for i in range(total)]

        pages_per_file = [[i] for i in range(total)]
        outputs = be.extract_pages_as_files(path, pages_per_file, names)
        self._ask_destination_and_save(outputs, f"{stem}_paginas")

    # ── Acción: guardar selección (panel 2) ─────────────────────────────
    def _do_save_selection(self):
        path = self._selected_path()
        if not path:
            self.win.snack("Selecciona un archivo", "error"); return
        idxs = sorted(it.data(Qt.UserRole)["idx"] for it in self.pick_grid.selectedItems())
        if not idxs:
            self.win.snack("Selecciona al menos una página", "error"); return
        stem = Path(path).stem
        outputs = be.extract_pages_as_files(path, [idxs], [f"{stem}_seleccion"])
        self._ask_destination_and_save(outputs, f"{stem}_seleccion")

    # ── Acción: dividir en 2 (seleccionadas / resto) ────────────────────
    def _do_split_selection_vs_rest(self):
        path = self._selected_path()
        if not path:
            self.win.snack("Selecciona un archivo", "error"); return
        total = be.safe_page_count(path)
        selected = sorted(it.data(Qt.UserRole)["idx"] for it in self.pick_grid.selectedItems())
        if not selected:
            self.win.snack("Selecciona al menos una página", "error"); return
        rest = [i for i in range(total) if i not in set(selected)]
        if not rest:
            self.win.snack("No quedan páginas fuera de la selección", "error"); return
        stem = Path(path).stem
        outputs = be.extract_pages_as_files(
            path, [selected, rest], [f"{stem}_seleccionadas", f"{stem}_resto"])
        self._ask_destination_and_save(outputs, f"{stem}_dividido")

    # ── Acción: dividir por página de referencia ────────────────────────
    def _do_split_reference(self):
        path = self._selected_path()
        if not path:
            self.win.snack("Selecciona un archivo", "error"); return
        total = be.safe_page_count(path)
        ref = self.ref_spin.value()  # 1-indexado; primera página del 2º archivo
        if ref < 2 or ref > total:
            self.win.snack("Página de referencia fuera de rango", "error"); return
        before = list(range(0, ref - 1))
        after  = list(range(ref - 1, total))
        stem = Path(path).stem
        outputs = be.extract_pages_as_files(
            path, [before, after], [f"{stem}_parte1", f"{stem}_parte2"])
        self._ask_destination_and_save(outputs, f"{stem}_dividido")


# ══════════════════════════════════════════════════════════════════════════
#  PANEL DE VISTA PREVIA (reutilizable: Tamaño/Márgenes y N-Up)
# ══════════════════════════════════════════════════════════════════════════
class PreviewPanel(QFrame):
    """Vista previa en vivo con navegación. render_fn(idx) -> bytes PNG | None.
    Los cambios de controles llaman a schedule(): se agrupan (debounce) para
    no re-renderizar a cada pulsación de flecha de un spinbox."""
    def __init__(self, render_fn, item_word: str = "Página"):
        super().__init__()
        self.setObjectName("Card")
        add_shadow(self, blur=18, dy=4, alpha=70)
        self._render_fn = render_fn
        self._item_word = item_word
        self._idx = 0
        self._total = 1
        self._orig: QPixmap | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(160)
        self._timer.timeout.connect(self._render)

        lay = QVBoxLayout(self)
        self.caption = QLabel("Vista previa")
        self.caption.setObjectName("SectionTitle")
        lay.addWidget(self.caption)

        self.img = QLabel(alignment=Qt.AlignCenter)
        self.img.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.img.setMinimumSize(240, 300)
        self.img.setStyleSheet(f"background:{BG}; border-radius:10px;")
        lay.addWidget(self.img, 1)

        nav = QHBoxLayout()
        self.prev_btn = _btn("", "chevron_left"); self.prev_btn.setFixedWidth(42)
        self.next_btn = _btn("", "chevron_right"); self.next_btn.setFixedWidth(42)
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))
        self.nav_lbl = QLabel()
        self.nav_lbl.setObjectName("Hint")
        nav.addStretch(1)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.nav_lbl)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        lay.addLayout(nav)
        self._update_nav()

    def set_caption(self, text: str):
        self.caption.setText(text)

    def set_total(self, total: int):
        self._total = max(1, total)
        self._idx = min(self._idx, self._total - 1)
        self._update_nav()

    def schedule(self):
        self._timer.start()

    def _step(self, delta: int):
        new = self._idx + delta
        if 0 <= new < self._total:
            self._idx = new
            self._update_nav()
            self._render()

    def _update_nav(self):
        self.nav_lbl.setText(f"{self._item_word} {self._idx + 1} / {self._total}")
        self.prev_btn.setEnabled(self._idx > 0)
        self.next_btn.setEnabled(self._idx < self._total - 1)

    def _render(self):
        png = self._render_fn(self._idx)
        if not png:
            self._orig = None
            self.img.setPixmap(QPixmap())
            self.img.setText("No se pudo generar la vista previa")
            return
        pix = QPixmap()
        pix.loadFromData(png)
        self._orig = pix
        self._fit()

    def _fit(self):
        if self._orig is None:
            return
        target = self.img.size() - QSize(16, 16)
        if target.width() > 0 and target.height() > 0:
            self.img.setPixmap(self._orig.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: TAMAÑO Y MÁRGENES
# ══════════════════════════════════════════════════════════════════════════
class CornerCanvas(QWidget):
    """Foto con cuatro puntos arrastrables en las esquinas del papel. Con «ver resultado» muestra la página ya estirada."""
    changed = Signal()

    def __init__(self, image):
        super().__init__()
        self.image = image                                    # PIL, ya reducida para la pantalla
        self.pix = QPixmap.fromImage(QImage(image.tobytes(), image.width, image.height, image.width * 3,
                                            QImage.Format_RGB888).copy())
        self.corners = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]      # fracciones: TL, TR, BR, BL
        self.preview = None                                   # QPixmap de la página corregida, si se está viendo
        self._drag = None
        self.setMinimumSize(520, 520)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    def _box(self) -> QRectF:
        src = self.preview if self.preview is not None else self.pix
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
        p.drawPixmap(b, src, QRectF(src.rect()))
        if self.preview is not None:
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
            p.setBrush(QColor("#FFFFFF"))
            p.setPen(QPen(QColor(ACCENT), 2.5))
            p.drawEllipse(q, 9, 9)
            p.setPen(QColor("#1C1409"))
            p.drawText(QRectF(q.x() - 9, q.y() - 9, 18, 18), Qt.AlignCenter, str(i + 1))

    def _hit(self, pos):
        for i, c in enumerate(self.corners):
            q = self._pt(c)
            if (q.x() - pos.x()) ** 2 + (q.y() - pos.y()) ** 2 <= 16 ** 2:
                return i
        return None

    def mousePressEvent(self, e):
        if self.preview is None and e.button() == Qt.LeftButton:
            self._drag = self._hit(e.position())

    def mouseMoveEvent(self, e):
        if self.preview is not None:
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


class PhotoFixDialog(QDialog):
    """Ajusta las cuatro esquinas del papel de una foto para estirarla a una página plana."""
    def __init__(self, parent, image):
        super().__init__(parent)
        self.setWindowTitle("Enderezar foto")
        self.resize(940, 860)
        self.image = image
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        title = QLabel("Enderezar foto")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.msg = QLabel("")
        self.msg.setObjectName("Hint")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.canvas = CornerCanvas(image)
        lay.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        auto = _btn("Detectar de nuevo", "bolt", "Secondary", icon_color=TEXT)
        auto.clicked.connect(self._auto)
        full = _btn("Toda la imagen", None, "Secondary", icon_color=TEXT)
        full.clicked.connect(lambda: (self.canvas.set_corners([(0.02, 0.02), (0.98, 0.02), (0.98, 0.98), (0.02, 0.98)]),
                                      self._set_msg("Arrastra cada punto a su esquina del papel.")))
        row.addWidget(auto)
        row.addWidget(full)
        row.addSpacing(10)
        row.addWidget(QLabel("Formato"))
        self.snap = QComboBox()
        for label, key in (("Automático", "auto"), ("A4", "A4"), ("Carta", "Carta"), ("Como se ve", "medido")):
            self.snap.addItem(label, key)
        self.snap.currentIndexChanged.connect(self._refresh_preview)
        row.addWidget(self.snap)
        self.flatten = QCheckBox("Aclarar fondo y luz")
        self.flatten.setChecked(True)
        self.flatten.toggled.connect(self._refresh_preview)
        row.addWidget(self.flatten)
        self.view = QCheckBox("Ver resultado")
        self.view.toggled.connect(self._toggle_preview)
        row.addWidget(self.view)
        row.addStretch(1)
        lay.addLayout(row)
        btns = QHBoxLayout()
        self.note = QLabel("Una hoja arrugada o curvada no se puede aplanar así: usa una foto con el papel plano y bien iluminado.")
        self.note.setObjectName("Hint")
        self.note.setWordWrap(True)
        btns.addWidget(self.note, 1)
        cancel = _btn("Cancelar", None, "Secondary", icon_color=TEXT)
        ok = _btn("Corregir página", "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.canvas.changed.connect(self._refresh_preview)
        self._auto()

    def _set_msg(self, text: str):
        self.msg.setText(text)

    def _auto(self):
        det = pf.detect_corners(self.image)
        if det:
            self.canvas.set_corners([(x / self.image.width, y / self.image.height) for x, y in det])
            self._set_msg("He encontrado las esquinas del papel. Comprueba que los cuatro puntos están en su sitio y "
                          "arrástralos si hace falta.")
            self.detected = True
        else:
            self.canvas.set_corners([(0.12, 0.12), (0.88, 0.12), (0.88, 0.88), (0.12, 0.88)])
            self._set_msg("No distingo bien el papel del fondo: arrastra los cuatro puntos a las esquinas de la hoja.")
            self.detected = False

    def _quad(self):
        return pf.order_corners([(x * self.image.width, y * self.image.height) for x, y in self.canvas.corners])

    def _toggle_preview(self, on: bool):
        self.canvas.preview = None
        if on:
            self._refresh_preview()
        else:
            self.canvas.update()

    def _refresh_preview(self, *_):
        if not self.view.isChecked():
            return
        q = self._quad()
        if not pf.is_convex(q):
            self.canvas.preview = None
            return
        size = pf.target_size(q, self.snap.currentData(), max_side=900)
        flat = pf.warp(self.image, q, size)
        if self.flatten.isChecked():
            flat = pf.flatten_light(flat)
        self.canvas.preview = QPixmap.fromImage(QImage(flat.tobytes(), flat.width, flat.height, flat.width * 3,
                                                       QImage.Format_RGB888).copy())
        self.canvas.update()

    def result(self) -> dict:
        return {"corners": self.canvas.corners, "snap": self.snap.currentData(), "flatten": self.flatten.isChecked()}


class _ToolJob(QThread):
    """Ejecuta una operación pesada fuera del hilo de la ventana."""
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.finished_ok.emit(self._fn(lambda i, n: self.progress.emit(i, n)))
        except ptl.ToolError as e:
            self.failed.emit(str(e))
        except Exception as e:                                  # fallo inesperado: se cuenta, no se traga
            self.failed.emit(f"Ha ocurrido un error inesperado: {e}")


def _human_size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


class OcrReviewDialog(QDialog):
    """Compara lo que ha leído el OCR con la página y deja corregir el texto en texto plano. La línea donde está el
    cursor se marca en la imagen. Al aceptar se elige qué guardar: PDF con la imagen y el texto buscable, y/o un PDF
    nuevo redibujado con el texto."""
    WIDTH = 600                                             # ancho de la página en pantalla

    def __init__(self, parent, review: dict):
        super().__init__(parent)
        import fitz as _fz
        self.setWindowTitle("Revisar el texto reconocido")
        self.resize(1240, 800)
        self.review = review
        self.pages = review["pages"]
        self._orig = {pd["index"]: ptl.review_text(pd) for pd in self.pages}
        self._texts = dict(self._orig)
        self._k = -1
        self._doc = ptl._open(review["src"], review.get("password", ""))
        self._base = None
        self._zoom = 1.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        title = QLabel("Revisar el texto reconocido")
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        hint = QLabel("Compara con la página (a la izquierda) y corrige lo que no coincida. La línea donde está el "
                      "cursor se marca en amarillo. Una línea por renglón; puedes añadir, borrar o cambiar líneas. "
                      "Lo que escribas en una línea en blanco se separa como párrafo.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        nav = QHBoxLayout()
        self.prev_b = _btn("Anterior", None, "Secondary", icon_color=TEXT)
        self.next_b = _btn("Siguiente", None, "Secondary", icon_color=TEXT)
        self.prev_b.clicked.connect(lambda: self._goto(self._k - 1))
        self.next_b.clicked.connect(lambda: self._goto(self._k + 1))
        self.page_lbl = QLabel("")
        self.reset_b = _btn("Restaurar el texto leído", None, "Secondary", icon_color=TEXT)
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

        split = QSplitter(Qt.Horizontal)
        self.img = QLabel()
        self.img.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(self.img)
        self.scroll = sa
        self.edit = QPlainTextEdit()
        f = self.edit.font()
        f.setPointSize(11)
        self.edit.setFont(f)
        self.edit.setTabChangesFocus(True)
        self.edit.cursorPositionChanged.connect(self._mark)
        self.edit.textChanged.connect(self._count)
        split.addWidget(sa)
        split.addWidget(self.edit)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 4)
        split.setChildrenCollapsible(False)
        split.setSizes([self.WIDTH + 40, 560])
        sa.setMinimumWidth(self.WIDTH // 2)
        self.img.setStyleSheet("background: transparent;")
        lay.addWidget(split, 1)

        self.cb_search = QCheckBox("PDF con la imagen y el texto detrás (se puede buscar y copiar) — recomendado")
        self.cb_search.setChecked(True)
        self.cb_redraw = QCheckBox("PDF nuevo redibujado solo con el texto (sin la imagen)")
        self.cb_redraw.setToolTip("Crea un segundo PDF donde el texto se dibuja a la vista en su posición, con las rayas de "
                                  "las tablas. Sirve para tener el documento limpio y editable. No conserva dibujos, "
                                  "sellos ni fotos.")
        lay.addWidget(self.cb_search)
        lay.addWidget(self.cb_redraw)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = _btn("Cancelar", None, "Secondary", icon_color=TEXT)
        self.ok = _btn("Guardar", "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self._goto(0)

    # ── páginas ─────────────────────────────────────────────────────────
    def _stash(self):
        if 0 <= self._k < len(self.pages):
            self._texts[self.pages[self._k]["index"]] = self.edit.toPlainText()

    def _goto(self, k: int):
        if not (0 <= k < len(self.pages)):
            return
        self._stash()
        self._k = k
        pd = self.pages[k]
        self.edit.blockSignals(True)
        self.edit.setPlainText(self._texts[pd["index"]])
        self.edit.blockSignals(False)
        page = self._doc[pd["index"]]
        self._zoom = self.WIDTH / max(page.rect.width, 1.0)
        import fitz as _fz
        pix = page.get_pixmap(matrix=_fz.Matrix(self._zoom, self._zoom), alpha=False)
        qi = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        self._base = QPixmap.fromImage(qi)
        self.page_lbl.setText(f"  Página {k + 1} de {len(self.pages)} (hoja {pd['index'] + 1} del PDF)  ")
        self.prev_b.setEnabled(k > 0)
        self.next_b.setEnabled(k < len(self.pages) - 1)
        self.scroll.verticalScrollBar().setValue(0)
        self._count()
        self._mark()

    def _restore(self):
        if self._k < 0:
            return
        idx = self.pages[self._k]["index"]
        self.edit.setPlainText(self._orig[idx])

    def _lines(self) -> list:
        return [s.strip() for s in self.edit.toPlainText().split("\n") if s.strip()]

    def _count(self):
        pd = self.pages[self._k]
        new = self._lines()
        old = [l["text"] for l in pd["lines"]]
        changed = sum(1 for oi, nj in ptl.align_lines(old, new) if oi is None or nj is None or old[oi] != new[nj])
        self.count_lbl.setText("Sin cambios" if changed == 0 else f"{changed} línea{'s' if changed != 1 else ''} cambiada{'s' if changed != 1 else ''}")
        self._mark()

    def _mark(self):
        """Dibuja sobre la página las líneas leídas (tenue) y la del cursor (amarillo)."""
        if self._base is None or self._k < 0:
            return
        pd = self.pages[self._k]
        pm = QPixmap(self._base)
        qp = QPainter(pm)
        z = self._zoom
        x0p, y0p = pd["rect"][0], pd["rect"][1]
        qp.setPen(QPen(QColor(80, 140, 220, 120), 1))
        for ln in pd["lines"]:
            a, b, c, d = ln["bbox"]
            qp.drawRect(QRectF((a - x0p) * z, (b - y0p) * z, (c - a) * z, (d - b) * z))
        cur = self.edit.textCursor().blockNumber()
        blocks = self.edit.toPlainText().split("\n")
        if 0 <= cur < len(blocks) and blocks[cur].strip():
            n = sum(1 for s in blocks[:cur] if s.strip())
            for oi, nj in ptl.align_lines([l["text"] for l in pd["lines"]], self._lines()):
                if nj == n and oi is not None:
                    a, b, c, d = pd["lines"][oi]["bbox"]
                    r = QRectF((a - x0p) * z - 2, (b - y0p) * z - 2, (c - a) * z + 4, (d - b) * z + 4)
                    qp.fillRect(r, QColor(255, 214, 0, 110))
                    qp.setPen(QPen(QColor(230, 160, 0), 2))
                    qp.drawRect(r)
                    break
        qp.end()
        self.img.setPixmap(pm)

    # ── resultado ───────────────────────────────────────────────────────
    def _accept(self):
        if not (self.cb_search.isChecked() or self.cb_redraw.isChecked()):
            QMessageBox.information(self, "Guardar", "Marca al menos una de las dos opciones de guardado.")
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


class ToolsPage(QWidget):
    """Herramientas de archivo completo: comprimir, proteger, marca de agua, aplanar, reparar, convertir y OCR."""
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self._job = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("Herramientas", lambda: win.go_home()))

        row = QHBoxLayout()
        row.addWidget(QLabel("Archivo:"))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._file_changed)
        row.addWidget(self.file_combo, 1)
        row.addWidget(QLabel("Contraseña del PDF:"))
        self.pw_field = QLineEdit()
        self.pw_field.setEchoMode(QLineEdit.Password)
        self.pw_field.setPlaceholderText("solo si lo necesita")
        self.pw_field.setFixedWidth(170)
        row.addWidget(self.pw_field)
        root.addLayout(row)
        self.info = QLabel("")
        self.info.setObjectName("Hint")
        root.addWidget(self.info)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_compress()
        self._build_protect()
        self._build_watermark()
        self._build_fix()
        self._build_convert()
        self._build_ocr()

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        root.addWidget(self.bar)

    # ── comunes ─────────────────────────────────────────────────────────
    def _tab(self, title: str, hint: str):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)
        h = QLabel(hint)
        h.setObjectName("Hint")
        h.setWordWrap(True)
        lay.addWidget(h)
        self.tabs.addTab(w, title)
        return lay

    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(("🔒 " if f.get("locked") else "") + f["name"])
        self.file_combo.blockSignals(False)
        self._file_changed()
        self._refresh_ocr_langs()
        self.status.setText("")

    def _file(self):
        i = self.file_combo.currentIndex()
        return self.win.uploaded_files[i] if 0 <= i < len(self.win.uploaded_files) else None

    def _file_changed(self, *_):
        f = self._file()
        if not f:
            self.info.setText("Añade un PDF en la pantalla principal para usar estas herramientas (convertir a PDF "
                              "no necesita ninguno).")
            return
        try:
            size = _human_size(os.path.getsize(f["path"]))
        except OSError:
            size = "?"
        self.info.setText(f"{size}" + (" · tiene contraseña de apertura" if f.get("locked") else f" · {f['pages']} pág."))
        self.ocr_corner_page.setRange(1, max(1, f["pages"]))
        self.compress_now.setText(f"Peso actual: {size}")

    def _need_file(self):
        f = self._file()
        if not f:
            self._say("Añade primero un PDF en la pantalla principal.", "error")
        return f

    def _say(self, msg: str, kind: str = "info"):
        col = {"ok": "#92976C", "error": "#D47268", "info": TEXT_SOFT}[kind]
        self.status.setStyleSheet(f"color:{col};")
        self.status.setText(msg)

    def _run(self, fn, on_done, start_msg: str):
        if self._job is not None and self._job.isRunning():
            return
        self._say(start_msg, "info")
        self.bar.setRange(0, 0)
        job = _ToolJob(fn)
        job.finished_ok.connect(lambda res: (self._finish(), on_done(res)))
        job.failed.connect(lambda msg: (self._finish(), self._say(msg, "error"), self.win.snack(msg, "error")))
        job.progress.connect(self._progress)
        self._job = job
        job.start()

    def _progress(self, i: int, n: int):
        if n > 0:
            self.bar.setRange(0, n)
            self.bar.setValue(i)
            self.status.setText(f"Procesando página {min(i + 1, n)} de {n}…")

    def _finish(self):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)

    def _adopt(self, out: str, f: dict | None, msg: str):
        """El resultado sustituye al archivo en la lista (como las demás herramientas) y se avisa dónde está."""
        if f is not None and out:
            new_f = self.win.replace_file(f, out)
            self.populate()
            self.file_combo.setCurrentIndex(max(0, self.win.uploaded_files.index(new_f)))
        self._say(f"✓ {msg}  Guardado en Descargas: {Path(out).name}", "ok")
        self.win.snack(f"✓ {msg}", "success")

    # ── Comprimir ───────────────────────────────────────────────────────
    def _build_compress(self):
        lay = self._tab("Comprimir", "Reduce el peso del PDF reescalando las imágenes grandes y limpiando lo que sobra. "
                                     "El texto no cambia.")
        self.compress_now = QLabel("")
        lay.addWidget(self.compress_now)
        self.level_group = QButtonGroup(self)
        for key, (label, _p) in ptl.COMPRESS_LEVELS.items():
            rb = QRadioButton(label)
            rb.setProperty("level", key)
            self.level_group.addButton(rb)
            lay.addWidget(rb)
            if key == "medium":
                rb.setChecked(True)
        b = _btn("Comprimir", "download", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_compress)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)

    def _do_compress(self):
        f = self._need_file()
        if not f:
            return
        level = self.level_group.checkedButton().property("level")
        pw = self.pw_field.text()

        def done(r):
            if not r["ok"]:
                self._say(r["reason"], "info")
                return
            saved = 100 - 100 * r["after"] / r["before"]
            self._adopt(r["out"], f, f"Comprimido: {_human_size(r['before'])} → {_human_size(r['after'])} "
                                     f"(−{saved:.0f} %).")
        self._run(lambda cb: ptl.compress(f["path"], level, pw), done, "Comprimiendo…")

    # ── Proteger ────────────────────────────────────────────────────────
    def _build_protect(self):
        lay = self._tab("Proteger", "Bloquea el PDF con contraseña (cifrado AES-256) o quita la protección de uno que "
                                    "ya tengas. Si olvidas la contraseña, nadie podrá recuperarla: guárdala.")
        card = QFrame(); card.setObjectName("Card")
        c = QVBoxLayout(card)
        t = QLabel("Bloquear")
        t.setObjectName("SectionTitle")
        c.addWidget(t)
        self.lock_pw = QLineEdit(); self.lock_pw.setEchoMode(QLineEdit.Password)
        self.lock_pw.setPlaceholderText("Contraseña para abrirlo (déjala vacía para solo limitar permisos)")
        self.lock_pw2 = QLineEdit(); self.lock_pw2.setEchoMode(QLineEdit.Password)
        self.lock_pw2.setPlaceholderText("Repite la contraseña")
        self.lock_owner = QLineEdit(); self.lock_owner.setEchoMode(QLineEdit.Password)
        self.lock_owner.setPlaceholderText("Contraseña de propietario para cambiar permisos (opcional)")
        for w in (self.lock_pw, self.lock_pw2, self.lock_owner):
            c.addWidget(w)
        c.addWidget(QLabel("Permitir a quien lo abra:"))
        perms = QHBoxLayout()
        self.perm_print = QCheckBox("Imprimir"); self.perm_print.setChecked(True)
        self.perm_copy = QCheckBox("Copiar texto")
        self.perm_edit = QCheckBox("Modificar")
        self.perm_annot = QCheckBox("Anotar y rellenar")
        for w in (self.perm_print, self.perm_copy, self.perm_edit, self.perm_annot):
            perms.addWidget(w)
        perms.addStretch(1)
        c.addLayout(perms)
        b = _btn("Bloquear", "lock", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_lock)
        c.addWidget(b, 0, Qt.AlignLeft)
        lay.addWidget(card)
        card2 = QFrame(); card2.setObjectName("Card")
        c2 = QVBoxLayout(card2)
        t2 = QLabel("Desbloquear")
        t2.setObjectName("SectionTitle")
        c2.addWidget(t2)
        h2 = QLabel("Escribe arriba la «Contraseña del PDF» si hace falta para abrirlo. Úsalo solo con documentos que "
                    "sean tuyos o que tengas permiso para modificar.")
        h2.setObjectName("Hint"); h2.setWordWrap(True)
        c2.addWidget(h2)
        b2 = _btn("Quitar protección", "check", "Secondary", icon_color=TEXT)
        b2.clicked.connect(self._do_unlock)
        c2.addWidget(b2, 0, Qt.AlignLeft)
        lay.addWidget(card2)
        lay.addStretch(1)

    def _do_lock(self):
        f = self._need_file()
        if not f:
            return
        if f.get("locked"):
            self._say("Este PDF ya tiene contraseña: desbloquéalo primero.", "error")
            return
        pw, pw2 = self.lock_pw.text(), self.lock_pw2.text()
        if pw != pw2:
            self._say("Las dos contraseñas no coinciden.", "error")
            return
        if pw and len(pw) < 4:
            self._say("Usa una contraseña de al menos 4 caracteres.", "error")
            return
        args = dict(user_pw=pw, owner_pw=self.lock_owner.text(), allow_print=self.perm_print.isChecked(),
                    allow_copy=self.perm_copy.isChecked(), allow_edit=self.perm_edit.isChecked(),
                    allow_annot=self.perm_annot.isChecked(), password=self.pw_field.text())

        def done(out):
            self.lock_pw.clear(); self.lock_pw2.clear(); self.lock_owner.clear()
            f["locked"] = bool(pw)
            self._adopt(out, f, "PDF protegido." if pw else "Permisos limitados.")
            nf = self._file()
            if nf is not None and pw:
                nf["locked"] = True
                self.populate()
        self._run(lambda cb: ptl.lock(f["path"], **args), done, "Protegiendo…")

    def _do_unlock(self):
        f = self._need_file()
        if not f:
            return
        pw = self.pw_field.text()

        def done(r):
            f2 = dict(f)
            self._adopt(r["out"], f, "Protección quitada.")
            nf = self._file()
            if nf is not None:
                nf["locked"] = False
                self.populate()
        self._run(lambda cb: ptl.unlock(f["path"], pw), done, "Quitando protección…")

    # ── Marca de agua ───────────────────────────────────────────────────
    def _build_watermark(self):
        lay = self._tab("Marca de agua", "Añade un texto o una imagen detrás del contenido de las páginas, con "
                                         "transparencia. No tapa nada.")
        self.wm_text_rb = QRadioButton("Texto"); self.wm_text_rb.setChecked(True)
        self.wm_img_rb = QRadioButton("Imagen")
        g = QButtonGroup(self); g.addButton(self.wm_text_rb); g.addButton(self.wm_img_rb)
        r1 = QHBoxLayout()
        r1.addWidget(self.wm_text_rb)
        self.wm_text = QLineEdit("CONFIDENCIAL")
        r1.addWidget(self.wm_text, 1)
        lay.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(self.wm_img_rb)
        self.wm_img_path = QLineEdit(); self.wm_img_path.setReadOnly(True)
        self.wm_img_path.setPlaceholderText("Elige una imagen (PNG con fondo transparente queda mejor)")
        pick = _btn("Elegir…", None, "Secondary", icon_color=TEXT)
        pick.clicked.connect(self._wm_pick)
        r2.addWidget(self.wm_img_path, 1)
        r2.addWidget(pick)
        lay.addLayout(r2)
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Color"))
        self.wm_color = QComboBox()
        for n in ptl.WM_COLORS:
            self.wm_color.addItem(n)
        r3.addWidget(self.wm_color)
        r3.addWidget(QLabel("Opacidad"))
        self.wm_opacity = QSlider(Qt.Horizontal)
        self.wm_opacity.setRange(5, 80); self.wm_opacity.setValue(25); self.wm_opacity.setFixedWidth(120)
        r3.addWidget(self.wm_opacity)
        r3.addWidget(QLabel("Giro"))
        self.wm_angle = QSpinBox(); self.wm_angle.setRange(-90, 90); self.wm_angle.setValue(45); self.wm_angle.setSuffix("°")
        r3.addWidget(self.wm_angle)
        self.wm_tile = QCheckBox("Repetir (mosaico)")
        r3.addWidget(self.wm_tile)
        r3.addStretch(1)
        lay.addLayout(r3)
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Páginas"))
        self.wm_pages = QLineEdit()
        self.wm_pages.setPlaceholderText("todas  ·  ejemplos: 1-3, 5, 8-   ·   pares   ·   impares")
        r4.addWidget(self.wm_pages, 1)
        lay.addLayout(r4)
        b = _btn("Añadir marca de agua", "stamp", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_wm)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)

    def _wm_pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "Imagen de la marca de agua", str(Path.home() / "Pictures"),
                                           "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            self.wm_img_path.setText(p)
            self.wm_img_rb.setChecked(True)

    def _do_wm(self):
        f = self._need_file()
        if not f:
            return
        use_img = self.wm_img_rb.isChecked()
        kw = dict(text="" if use_img else self.wm_text.text(), image=self.wm_img_path.text() if use_img else "",
                  opacity=self.wm_opacity.value() / 100, angle=float(self.wm_angle.value()),
                  color=self.wm_color.currentText(), pages=self.wm_pages.text(), tile=self.wm_tile.isChecked(),
                  password=self.pw_field.text())
        self._run(lambda cb: ptl.watermark(f["path"], **kw),
                  lambda out: self._adopt(out, f, "Marca de agua añadida."), "Añadiendo marca de agua…")

    # ── Aplanar y reparar ───────────────────────────────────────────────
    def _build_fix(self):
        lay = self._tab("Aplanar y reparar", "Aplanar convierte comentarios, dibujos y campos de formulario en contenido "
                                             "fijo (ya no se pueden editar). Reparar reconstruye un PDF dañado o que no "
                                             "se abre bien.")
        card = QFrame(); card.setObjectName("Card")
        c = QVBoxLayout(card)
        t = QLabel("Aplanar"); t.setObjectName("SectionTitle"); c.addWidget(t)
        self.flat_annots = QCheckBox("Anotaciones (resaltados, dibujos, notas, sellos…)"); self.flat_annots.setChecked(True)
        self.flat_widgets = QCheckBox("Campos de formulario (con lo rellenado)"); self.flat_widgets.setChecked(True)
        c.addWidget(self.flat_annots); c.addWidget(self.flat_widgets)
        b = _btn("Aplanar", "document", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_flatten)
        c.addWidget(b, 0, Qt.AlignLeft)
        lay.addWidget(card)
        card2 = QFrame(); card2.setObjectName("Card")
        c2 = QVBoxLayout(card2)
        t2 = QLabel("Reparar"); t2.setObjectName("SectionTitle"); c2.addWidget(t2)
        b2 = _btn("Reparar PDF", "bolt", "Secondary", icon_color=TEXT)
        b2.clicked.connect(self._do_repair)
        c2.addWidget(b2, 0, Qt.AlignLeft)
        lay.addWidget(card2)
        lay.addStretch(1)

    def _do_flatten(self):
        f = self._need_file()
        if not f:
            return
        a, w, pw = self.flat_annots.isChecked(), self.flat_widgets.isChecked(), self.pw_field.text()
        self._run(lambda cb: ptl.flatten(f["path"], a, w, pw),
                  lambda r: self._adopt(r["out"], f, f"Aplanado ({r['annots']} anotaciones, {r['widgets']} campos)."),
                  "Aplanando…")

    def _do_repair(self):
        f = self._file()
        if not f:
            self._say("Añade primero un PDF en la pantalla principal.", "error")
            return
        pw = self.pw_field.text()

        def done(r):
            msg = ("Reparado" if r["was_damaged"] else "Revisado: no tenía daños, se ha guardado limpio") + \
                  f" ({r['readable']} de {r['pages']} páginas legibles)."
            self._adopt(r["out"], f, msg)
        self._run(lambda cb: ptl.repair(f["path"], pw), done, "Reparando…")

    # ── Convertir a PDF ─────────────────────────────────────────────────
    def _build_convert(self):
        exts = " ".join(ptl.supported_extensions())
        lay = self._tab("Convertir a PDF", "Convierte imágenes, texto, Markdown, HTML y otros formatos a PDF. Word, "
                                           "Excel y PowerPoint necesitan LibreOffice instalado. Formatos: " + exts)
        self.conv_list = QListWidget()
        self.conv_list.setMinimumHeight(120)
        lay.addWidget(self.conv_list, 1)
        r = QHBoxLayout()
        add = _btn("Añadir archivos…", "clip", "Secondary", icon_color=TEXT)
        add.clicked.connect(self._conv_add)
        rm = _btn("Quitar", "trash", "Flat", icon_color=TEXT)
        rm.clicked.connect(lambda: [self.conv_list.takeItem(self.conv_list.row(i)) for i in self.conv_list.selectedItems()])
        r.addWidget(add); r.addWidget(rm); r.addStretch(1)
        r.addWidget(QLabel("Imágenes en página:"))
        self.conv_size = QComboBox()
        for n in ("A4", "Carta", "Ajustar"):
            self.conv_size.addItem(n)
        r.addWidget(self.conv_size)
        lay.addLayout(r)
        b = _btn("Convertir", "play", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_convert)
        lay.addWidget(b, 0, Qt.AlignLeft)

    def _conv_add(self):
        flt = "Todos los compatibles (" + " ".join("*" + e for e in ptl.supported_extensions()) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, "Archivos a convertir", str(Path.home()), flt)
        existing = {self.conv_list.item(i).data(Qt.UserRole) for i in range(self.conv_list.count())}
        for p in paths:
            if p not in existing:
                it = QListWidgetItem(Path(p).name)
                it.setData(Qt.UserRole, p)
                self.conv_list.addItem(it)

    def _do_convert(self):
        paths = [self.conv_list.item(i).data(Qt.UserRole) for i in range(self.conv_list.count())]
        if not paths:
            self._say("Añade al menos un archivo.", "error")
            return
        size = self.conv_size.currentText()

        def done(results):
            ok = [r for r in results if r[1]]
            bad = [r for r in results if not r[1]]
            for _src, out, _e in ok:
                self.win.add_file(out, Path(out).name)
            self.conv_list.clear()
            self.populate()
            msg = f"✓ {len(ok)} PDF creado{'s' if len(ok) != 1 else ''} (están en la lista y en Descargas)."
            if bad:
                msg += "  No se pudo: " + " · ".join(f"{Path(s).name if os.path.exists(str(s)) else s}: {e}" for s, _o, e in bad)
            self._say(msg, "ok" if ok and not bad else "error" if not ok else "info")
        self._run(lambda cb: ptl.convert_to_pdf(paths, size), done, "Convirtiendo…")

    # ── OCR ─────────────────────────────────────────────────────────────
    def _build_ocr(self):
        lay = self._tab("OCR", "Reconoce el texto de un PDF escaneado (o hecho de imágenes) y lo añade de forma invisible: "
                               "ya se puede buscar y copiar. Si la página es una foto torcida, puede enderezarla antes en "
                               "el mismo paso. Funciona sin internet; los idiomas son archivos pequeños que se "
                               "instalan una vez.")
        er = QHBoxLayout()
        er.addWidget(QLabel("Motor"))
        self.ocr_engine = QComboBox()
        self.ocr_engine.addItem("RapidOCR · recomendado", "rapid")
        self.ocr_engine.addItem("Tesseract · rápido", "tesseract")
        if not ptl.rapid_available():
            self.ocr_engine.setCurrentIndex(1)
            self.ocr_engine.model().item(0).setEnabled(False)
            self.ocr_engine.setToolTip("RapidOCR no está instalado: pip install rapidocr")
        else:
            self.ocr_engine.setToolTip("RapidOCR usa redes neuronales (sin internet, gratis) y lee mucho mejor las fotos "
                                       "borrosas o pequeñas. Tesseract es más rápido y va bien con escaneos limpios.")
        self.ocr_engine.currentIndexChanged.connect(self._ocr_engine_changed)
        er.addWidget(self.ocr_engine)
        er.addStretch(1)
        lay.addLayout(er)
        self.ocr_engine_note = QLabel()
        self.ocr_engine_note.setObjectName("Hint")
        self.ocr_engine_note.setWordWrap(True)
        lay.addWidget(self.ocr_engine_note)
        self.ocr_lang_panel = QWidget()
        lp = QVBoxLayout(self.ocr_lang_panel)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.addWidget(QLabel("Idiomas del documento:"))
        self.ocr_langs_box = QHBoxLayout()
        wrap = QWidget(); wrap.setLayout(self.ocr_langs_box)
        lp.addWidget(wrap)
        self.ocr_missing_box = QHBoxLayout()
        wrap2 = QWidget(); wrap2.setLayout(self.ocr_missing_box)
        lp.addWidget(wrap2)
        lay.addWidget(self.ocr_lang_panel)
        r = QHBoxLayout()
        r.addWidget(QLabel("Calidad"))
        self.ocr_dpi = QComboBox()
        for label, dpi in (("Rápida (150 ppp)", 150), ("Normal (200 ppp)", 200), ("Alta (300 ppp)", 300)):
            self.ocr_dpi.addItem(label, dpi)
        self.ocr_dpi.setCurrentIndex(1)
        r.addWidget(self.ocr_dpi)
        self.ocr_only = QCheckBox("Solo las páginas sin texto"); self.ocr_only.setChecked(True)
        r.addWidget(self.ocr_only)
        self.ocr_enhance = QCheckBox("Mejorar la imagen antes de leer")
        self.ocr_enhance.setChecked(True)
        self.ocr_enhance.setToolTip("Quita el ruido, endereza la página (hasta ~15°) y borra las líneas de las tablas "
                                    "para leer mejor. Tarda algo más por página.")
        r.addWidget(self.ocr_enhance)
        self.ocr_precise = QCheckBox("Máxima precisión")
        self.ocr_precise.setToolTip("Usa datos de idioma de alta precisión (tessdata_best, unos 15 MB por idioma, se "
                                    "descargan una vez). Más lento, pero lee mucho mejor el texto borroso o de baja "
                                    "resolución.")
        r.addWidget(self.ocr_precise)
        r.addStretch(1)
        lay.addLayout(r)
        self.ocr_review = QCheckBox("Revisar y corregir el texto antes de guardar")
        self.ocr_review.setChecked(True)
        self.ocr_review.setToolTip("Tras leer, se abre una vista para comparar el texto con la página y corregirlo. "
                                   "Desde ahí también puedes crear un PDF nuevo redibujado con el texto.")
        lay.addWidget(self.ocr_review)
        # ── Enderezar (opcional, dentro del mismo OCR)
        self.ocr_straighten = QCheckBox("Enderezar las páginas antes (fotos o escaneos torcidos)")
        self.ocr_straighten.setChecked(True)
        self.ocr_straighten.setToolTip("Busca solo el papel, corrige la perspectiva y gira la página hasta que las líneas "
                                       "de texto queden horizontales (se guía por la base de las letras). Las páginas que "
                                       "ya están rectas no se tocan. Sirve para papel plano: una hoja arrugada no se aplana.")
        lay.addWidget(self.ocr_straighten)
        self.ocr_str_box = QWidget()
        sr = QHBoxLayout(self.ocr_str_box)
        sr.setContentsMargins(24, 0, 0, 0)
        self.ocr_flatten = QCheckBox("Aclarar el fondo y quitar sombras")
        self.ocr_flatten.setChecked(True)
        sr.addWidget(self.ocr_flatten)
        sr.addWidget(QLabel("Esquinas a mano, página:"))
        self.ocr_corner_page = QSpinBox()
        self.ocr_corner_page.setRange(1, 1)
        sr.addWidget(self.ocr_corner_page)
        self.ocr_corner_btn = _btn("Marcar esquinas…", "crop", "Secondary", icon_color=TEXT)
        self.ocr_corner_btn.setToolTip("Si no encuentra bien el papel, marca tú las cuatro esquinas de esa página")
        self.ocr_corner_btn.clicked.connect(self._ocr_mark_corners)
        sr.addWidget(self.ocr_corner_btn)
        self.ocr_corner_lbl = QLabel("")
        self.ocr_corner_lbl.setObjectName("Hint")
        sr.addWidget(self.ocr_corner_lbl)
        sr.addStretch(1)
        lay.addWidget(self.ocr_str_box)
        self.ocr_straighten.toggled.connect(self.ocr_str_box.setVisible)
        self._ocr_manual: dict = {}
        b = _btn("Reconocer texto", "play", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_ocr)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)
        self._ocr_checks: dict = {}
        self._ocr_engine_changed()

    def _refresh_ocr_langs(self):
        for box in (self.ocr_langs_box, self.ocr_missing_box):
            while box.count():
                w = box.takeAt(0).widget()
                if w:
                    w.deleteLater()
        prev = {k: c.isChecked() for k, c in self._ocr_checks.items()}
        self._ocr_checks = {}
        avail = ptl.available_languages()
        for code in sorted(avail, key=lambda c: (c not in ("spa", "por", "eng"), c)):
            cb = QCheckBox(ptl.LANG_NAMES.get(code, code))
            cb.setChecked(prev.get(code, code in ("spa", "por") or (code == "eng" and not ({"spa", "por"} & set(avail)))))
            self._ocr_checks[code] = cb
            self.ocr_langs_box.addWidget(cb)
        self.ocr_langs_box.addStretch(1)
        missing = sorted((c for c in ptl.LANG_NAMES if c not in avail), key=lambda c: ptl.LANG_NAMES[c])
        if missing:
            lbl = QLabel("¿Otro idioma?")
            lbl.setObjectName("Hint")
            self.ocr_missing_box.addWidget(lbl)
            combo = QComboBox()
            combo.setMinimumWidth(260)
            combo.addItem("Descargar otro idioma…", None)
            for code in missing:
                combo.addItem(f"{ptl.LANG_NAMES[code]}  ({code})", code)
            combo.activated.connect(lambda i, c=combo: self._lang_picked(c))
            self.ocr_lang_combo = combo
            self.ocr_missing_box.addWidget(combo)
        self.ocr_missing_box.addStretch(1)
        self._ocr_engine_changed()

    def _lang_picked(self, combo: QComboBox):
        code = combo.currentData()
        combo.setCurrentIndex(0)
        if code:
            self._install_lang(code)

    def _install_lang(self, code: str):
        name = ptl.LANG_NAMES.get(code, code)
        if QMessageBox.question(
                self, "Instalar idioma",
                f"Se descargará el idioma «{name}» ({code}.traineddata, unos 1–10 MB) del repositorio oficial de Tesseract "
                f"(github.com/tesseract-ocr/tessdata_fast) y se guardará en tu carpeta de datos del programa.\n\n"
                "¿Descargarlo?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._run(lambda cb: ptl.download_language(code),
                  lambda _p: (self._refresh_ocr_langs(), self._say(f"✓ Idioma «{name}» instalado.", "ok")),
                  f"Descargando «{name}»…")

    def _ocr_engine_changed(self, *_):
        """Idiomas y «Máxima precisión» solo cuentan con Tesseract; RapidOCR reconoce los idiomas con alfabeto latino solo."""
        rapid = self.ocr_engine.currentData() == "rapid"
        self.ocr_precise.setVisible(not rapid)
        if rapid:
            self.ocr_precise.setChecked(False)
        self.ocr_lang_panel.setVisible(not rapid)
        self.ocr_engine_note.setText(
            "Lee bien fotos, escaneos borrosos y papel torcido. Detecta solo el idioma (alfabeto latino): no hace falta "
            "elegirlo. Es algo más lento." if rapid else
            "Muy rápido y va bien con escaneos limpios y rectos. Elige abajo el idioma del documento; para fotos o "
            "texto borroso usa RapidOCR.")

    def _ocr_mark_corners(self):
        """Marcar a mano las esquinas del papel de una página (si la detección automática no acierta)."""
        f = self._need_file()
        if not f:
            return
        if f.get("locked"):
            self._say("Este PDF tiene contraseña: desbloquéalo primero.", "error")
            return
        idx = self.ocr_corner_page.value() - 1
        try:
            import fitz as _fz
            doc = _fz.open(f["path"])
            try:
                img = pf.render_page(doc, idx, max_dpi=150, max_px=1500)
            finally:
                doc.close()
        except Exception as e:
            self._say(f"No se pudo abrir la página: {e}", "error")
            return
        dlg = PhotoFixDialog(self.window(), img)
        if dlg.exec() != QDialog.Accepted:
            return
        self._ocr_manual[idx] = dlg.result()["corners"]
        self.ocr_corner_lbl.setText("Esquinas marcadas en página(s): " + ", ".join(str(i + 1) for i in sorted(self._ocr_manual)))

    def _do_ocr(self):
        f = self._need_file()
        if not f:
            return
        engine = self.ocr_engine.currentData()
        langs = [c for c, cb in self._ocr_checks.items() if cb.isChecked()]
        if not langs and engine != "rapid":
            self._say("Marca al menos un idioma (o instala uno de la lista).", "error")
            return
        dpi, only, pw = self.ocr_dpi.currentData(), self.ocr_only.isChecked(), self.pw_field.text()
        enhance = self.ocr_enhance.isChecked()
        straighten, flatten = self.ocr_straighten.isChecked(), self.ocr_flatten.isChecked()
        manual = dict(self._ocr_manual)
        precise = self.ocr_precise.isChecked()
        review = self.ocr_review.isChecked()
        missing_hq = [l for l in langs if not ptl.best_available(l)] if precise else []
        if missing_hq:
            names = ", ".join(f"{ptl.LANG_NAMES.get(l, l)} ({l}.traineddata)" for l in missing_hq)
            if QMessageBox.question(
                    self, "Descargar datos de alta precisión",
                    f"Para la máxima precisión se descargará, una sola vez: {names}.\n\nOrigen: "
                    "github.com/tesseract-ocr/tessdata_best (repositorio oficial de Tesseract). Unos 15 MB por idioma "
                    "(el de inglés pesa 15 MB). Se guardan en tu carpeta de datos del programa.\n\n¿Descargarlos?",
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return

        def saved(r):
            outs = r.get("outs") or [r["out"]]
            more = f" También: {Path(outs[1]).name}." if len(outs) > 1 else ""
            self._adopt(r["out"], f, f"Texto guardado en {r['pages']} página{'s' if r['pages'] != 1 else ''} "
                                     f"({r['words']} palabras)." + more)

        def done(r):
            if r.get("review"):
                if not r["pages"]:                                  # nada que revisar (p. ej. solo páginas giradas)
                    self._job.wait()
                    self._run(lambda cb: ptl.ocr_apply(r, {}, True, False, progress=cb), saved, "Guardando…")
                    return
                dlg = OcrReviewDialog(self.window(), r)
                if dlg.exec() != QDialog.Accepted:
                    self._say("Revisión cancelada: no se ha guardado nada.", "info")
                    return
                texts, s, rd = dlg.texts(), dlg.searchable(), dlg.redrawn()
                self._job.wait()
                self._run(lambda cb: ptl.ocr_apply(r, texts, s, rd, progress=cb), saved, "Guardando el texto…")
                return
            extra = f", {r['tables']} tabla{'s' if r['tables'] != 1 else ''}" if r.get("tables") else ""
            n_str = r.get("straightened", 0)
            tail = (f" {n_str} página{'s' if n_str != 1 else ''} enderezada{'s' if n_str != 1 else ''}."
                    if straighten and n_str else " La página original no se ha tocado.")
            self._adopt(r["out"], f, f"Texto reconocido en {r['pages']} página{'s' if r['pages'] != 1 else ''} "
                                     f"({r['words']} palabras{extra})." + tail)
        def work(cb):
            for l in missing_hq:                                   # primero los datos de alta precisión que falten
                ptl.download_language(l, best=True)
            return pf.ocr_straight(f["path"], langs, dpi, only, pw, progress=cb, enhance=enhance,
                                   straighten=straighten, flatten=flatten, manual=manual, precise=precise,
                                   engine=engine, review=review)
        self._run(work, done,
                  "Enderezando y reconociendo texto…" if straighten else "Reconociendo texto…")


class SizeMarginsPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("Tamaño y márgenes", lambda: win.go_home()))

        root.addWidget(QLabel("Archivo:"))
        self.file_combo = QComboBox()
        root.addWidget(self.file_combo)

        self._mode = "size"
        self.preview = PreviewPanel(self._render_preview, "Página")
        self.preview.set_caption("Vista previa · tamaño")
        self.file_combo.currentIndexChanged.connect(self.refresh_preview)
        body = QHBoxLayout(); body.setSpacing(16)
        left = QVBoxLayout()

        # ── Tamaño de página ──────────────────────────────────────────
        size_card = QFrame(); size_card.setObjectName("Card")
        add_shadow(size_card, blur=18, dy=4, alpha=70)
        sc = QVBoxLayout(size_card)
        title1 = QLabel("Cambiar tamaño de página"); title1.setObjectName("SectionTitle")
        sc.addWidget(title1)

        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A5", "A3", "Carta (Letter)", "Legal", "Personalizado"])
        self.size_combo.currentTextChanged.connect(self._on_size_choice_changed)
        self.size_combo.currentTextChanged.connect(lambda *_: self._touch("size"))
        sc.addWidget(self.size_combo)

        self.custom_row_widget = QWidget()
        custom_row = QHBoxLayout(self.custom_row_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        self.custom_w = QDoubleSpinBox(); self.custom_w.setRange(10, 2000)
        self.custom_w.setValue(210); self.custom_w.setSuffix(" mm")
        self.custom_h = QDoubleSpinBox(); self.custom_h.setRange(10, 2000)
        self.custom_h.setValue(297); self.custom_h.setSuffix(" mm")
        custom_row.addWidget(QLabel("Ancho:")); custom_row.addWidget(self.custom_w)
        custom_row.addWidget(QLabel("Alto:"));  custom_row.addWidget(self.custom_h)
        self.custom_row_widget.setVisible(False)
        self.custom_w.valueChanged.connect(lambda *_: self._touch("size"))
        self.custom_h.valueChanged.connect(lambda *_: self._touch("size"))
        sc.addWidget(self.custom_row_widget)

        fit_row = QHBoxLayout()
        self.fit_scale_radio  = QRadioButton("Escalar contenido para llenar la hoja")
        self.fit_center_radio = QRadioButton("Mantener tamaño original y centrar")
        self.fit_scale_radio.setChecked(True)
        fgroup = QButtonGroup(self)
        fgroup.addButton(self.fit_scale_radio); fgroup.addButton(self.fit_center_radio)
        fit_row.addWidget(self.fit_scale_radio); fit_row.addWidget(self.fit_center_radio)
        self.fit_scale_radio.toggled.connect(lambda *_: self._touch("size"))
        sc.addLayout(fit_row)

        resize_btn = _btn("Aplicar tamaño", "resize", "Primary")
        resize_btn.clicked.connect(self._do_resize)
        sc.addWidget(resize_btn)
        left.addWidget(size_card)

        # ── Márgenes ──────────────────────────────────────────────────
        margin_card = QFrame(); margin_card.setObjectName("Card")
        add_shadow(margin_card, blur=18, dy=4, alpha=70)
        mc = QVBoxLayout(margin_card)
        title2 = QLabel("Cambiar márgenes"); title2.setObjectName("SectionTitle")
        mc.addWidget(title2)
        hint = QLabel("Valores positivos añaden margen en blanco en ese borde; "
                       "valores negativos recortan ese borde de la página.")
        hint.setObjectName("Hint"); hint.setWordWrap(True)
        mc.addWidget(hint)

        grid_row = QHBoxLayout()
        self.margin_top    = self._mm_spin()
        self.margin_bottom = self._mm_spin()
        self.margin_left   = self._mm_spin()
        self.margin_right  = self._mm_spin()
        for label, field in (("Arriba", self.margin_top), ("Abajo", self.margin_bottom),
                              ("Izquierda", self.margin_left), ("Derecha", self.margin_right)):
            col = QVBoxLayout()
            lbl = QLabel(label); lbl.setObjectName("Hint")
            col.addWidget(lbl)
            col.addWidget(field)
            grid_row.addLayout(col)
        mc.addLayout(grid_row)
        for sp in (self.margin_top, self.margin_bottom, self.margin_left, self.margin_right):
            sp.valueChanged.connect(lambda *_: self._touch("margins"))

        margin_btn = _btn("Aplicar márgenes", "crop", "Primary")
        margin_btn.clicked.connect(self._do_margins)
        mc.addWidget(margin_btn)
        left.addWidget(margin_card)
        left.addStretch(1)
        body.addLayout(left, 1)
        body.addWidget(self.preview, 1)
        root.addLayout(body, 1)

    def _touch(self, mode: str):
        self._mode = mode
        self.preview.set_caption("Vista previa · tamaño" if mode == "size"
                                  else "Vista previa · márgenes")
        self.preview.schedule()

    def refresh_preview(self, *_):
        f = self._selected_file()
        self.preview.set_total(f["pages"] if f else 1)
        self.preview.schedule()

    def _render_preview(self, idx: int):
        f = self._selected_file()
        if not f:
            return None
        if self._mode == "margins":
            return be.preview_margins_png(
                f["path"], idx, self.margin_top.value(), self.margin_bottom.value(),
                self.margin_left.value(), self.margin_right.value())
        fit_mode = "scale" if self.fit_scale_radio.isChecked() else "center"
        return be.preview_resize_png(
            f["path"], idx, self.size_combo.currentText(), fit_mode,
            custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value())

    def _mm_spin(self) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(-100.0, 100.0)
        sp.setValue(0.0)
        sp.setSuffix(" mm")
        sp.setSingleStep(5.0)
        return sp

    def _on_size_choice_changed(self, text: str):
        self.custom_row_widget.setVisible(text == "Personalizado")

    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _do_resize(self):
        f = self._selected_file()
        if not f:
            self.win.snack("Selecciona un archivo", "error"); return
        size_name = self.size_combo.currentText()
        fit_mode = "scale" if self.fit_scale_radio.isChecked() else "center"
        out = be.resize_pdf(f["path"], size_name, fit_mode,
                             custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value())
        if out:
            self.win.record_step("resize", {
                "size_name": size_name, "fit_mode": fit_mode,
                "custom_w_mm": self.custom_w.value(), "custom_h_mm": self.custom_h.value()})
            self.win.replace_file(f, out)
            self.populate()
            self.refresh_preview()
            self.win.snack(f"✓ Tamaño aplicado: {Path(out).name}")
        else:
            self.win.snack("No se pudo cambiar el tamaño", "error")

    def _do_margins(self):
        f = self._selected_file()
        if not f:
            self.win.snack("Selecciona un archivo", "error"); return
        out = be.adjust_margins_pdf(
            f["path"], top_mm=self.margin_top.value(), bottom_mm=self.margin_bottom.value(),
            left_mm=self.margin_left.value(), right_mm=self.margin_right.value())
        if out:
            self.win.record_step("margins", {
                "top_mm": self.margin_top.value(), "bottom_mm": self.margin_bottom.value(),
                "left_mm": self.margin_left.value(), "right_mm": self.margin_right.value()})
            self.win.replace_file(f, out)
            self.populate()
            for sp in (self.margin_top, self.margin_bottom, self.margin_left, self.margin_right):
                sp.setValue(0.0)
            self.refresh_preview()
            self.win.snack(f"✓ Márgenes aplicados: {Path(out).name}")
        else:
            self.win.snack("No se pudieron aplicar los márgenes", "error")


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: N-UP (varias páginas por hoja)
# ══════════════════════════════════════════════════════════════════════════
class NUpPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("N-Up – Varias páginas por hoja", lambda: win.go_home()))

        self.file_lbl = QLabel("Archivo:")
        root.addWidget(self.file_lbl)
        self.file_combo = QComboBox()
        root.addWidget(self.file_combo)
        self._merge_dir = tempfile.mkdtemp(prefix="pdfmgr_nup_")
        self._merge_key: tuple | None = None
        self._merge_info: dict | None = None

        self.preview = PreviewPanel(self._render_preview, "Hoja")
        self.preview.set_caption("Vista previa · hoja de salida")
        self.file_combo.currentIndexChanged.connect(self.refresh_preview)
        body = QHBoxLayout(); body.setSpacing(16)
        left = QVBoxLayout()

        card = QFrame(); card.setObjectName("Card")
        add_shadow(card, blur=18, dy=4, alpha=70)
        c = QVBoxLayout(card)

        grid_row = QHBoxLayout()
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(1, 6); self.cols_spin.setValue(2)
        self.rows_spin = QSpinBox(); self.rows_spin.setRange(1, 6); self.rows_spin.setValue(2)
        self.cols_spin.valueChanged.connect(self._update_total_label)
        self.rows_spin.valueChanged.connect(self._update_total_label)
        self.cols_spin.valueChanged.connect(self.refresh_preview)
        self.rows_spin.valueChanged.connect(self.refresh_preview)
        grid_row.addWidget(QLabel("Columnas:")); grid_row.addWidget(self.cols_spin)
        grid_row.addWidget(QLabel("Filas:"));    grid_row.addWidget(self.rows_spin)
        c.addLayout(grid_row)

        self.total_label = QLabel()
        self.total_label.setObjectName("Hint")
        c.addWidget(self.total_label)

        c.addWidget(QLabel("Tamaño de la hoja de salida:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A5", "A3", "Carta (Letter)", "Legal", "Personalizado"])
        self.size_combo.currentTextChanged.connect(self._on_size_choice_changed)
        self.size_combo.currentTextChanged.connect(lambda *_: self.preview.schedule())
        c.addWidget(self.size_combo)

        self.custom_row_widget = QWidget()
        custom_row = QHBoxLayout(self.custom_row_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        self.custom_w = QDoubleSpinBox(); self.custom_w.setRange(10, 2000)
        self.custom_w.setValue(297); self.custom_w.setSuffix(" mm")
        self.custom_h = QDoubleSpinBox(); self.custom_h.setRange(10, 2000)
        self.custom_h.setValue(210); self.custom_h.setSuffix(" mm")
        custom_row.addWidget(QLabel("Ancho:")); custom_row.addWidget(self.custom_w)
        custom_row.addWidget(QLabel("Alto:"));  custom_row.addWidget(self.custom_h)
        self.custom_row_widget.setVisible(False)
        self.custom_w.valueChanged.connect(lambda *_: self.preview.schedule())
        self.custom_h.valueChanged.connect(lambda *_: self.preview.schedule())
        c.addWidget(self.custom_row_widget)

        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel("Orientación de la hoja:"))
        self.orient_combo = QComboBox()
        self.orient_combo.addItem("Automática", "auto")
        self.orient_combo.addItem("Vertical", "portrait")
        self.orient_combo.addItem("Horizontal", "landscape")
        self.orient_combo.setToolTip("Automática: elige la orientación en la que las páginas salen más grandes")
        self.orient_combo.currentIndexChanged.connect(lambda *_: self.preview.schedule())
        orient_row.addWidget(self.orient_combo, 1)
        c.addLayout(orient_row)

        self.rotate_check = QCheckBox("Girar páginas para aprovechar mejor la hoja")
        self.rotate_check.setChecked(True)
        self.rotate_check.setToolTip("Si una página llena mejor su celda girada 90°, se gira "
                                     "(útil con documentos de páginas mezcladas)")
        self.rotate_check.toggled.connect(lambda *_: self.preview.schedule())
        c.addWidget(self.rotate_check)

        gap_row = QHBoxLayout()
        gap_row.addWidget(QLabel("Espacio entre páginas:"))
        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setDecimals(1)
        self.gap_spin.setSingleStep(0.5)
        self.gap_spin.setRange(-0.5, 30)
        self.gap_spin.setSuffix(" mm")
        self.gap_spin.setSpecialValueText("Auto")
        self.gap_spin.setValue(-0.5)
        gap_row.addWidget(self.gap_spin)
        self.gap_spin.valueChanged.connect(lambda *_: self.preview.schedule())
        c.addLayout(gap_row)

        left.addWidget(card)

        apply_btn = _btn("Aplicar N-Up", "nup", "Primary")
        apply_btn.clicked.connect(self._do_nup)
        left.addWidget(apply_btn)
        left.addStretch(1)
        body.addLayout(left, 1)
        body.addWidget(self.preview, 1)
        root.addLayout(body, 1)

        self._update_total_label()

    def _update_total_label(self, *_):
        n = self.cols_spin.value() * self.rows_spin.value()
        self.total_label.setText(f"= {n} página(s) por hoja")

    def _gap_value(self) -> float | None:
        """None = 'Auto' (valor mínimo del campo, que se muestra como texto)."""
        v = self.gap_spin.value()
        return None if v <= self.gap_spin.minimum() else v

    def _orientation(self) -> str:
        return self.orient_combo.currentData() or "auto"

    def _update_gap_tooltip(self, orientation: str = "portrait"):
        v = be.auto_gap_mm(self.size_combo.currentText(), self.custom_w.value(),
                           self.custom_h.value(), self.cols_spin.value(), self.rows_spin.value(),
                           orientation)
        self.gap_spin.setToolTip(
            f"Auto: ahora {v:.1f} mm (3 mm, reducido hasta 0 si la cuadrícula necesita el sitio)")

    def _source(self) -> dict | None:
        """Con varios archivos cargados, N-Up trabaja sobre su unión (en el
        orden de la lista); con uno solo, sobre el archivo elegido."""
        files = self.win.uploaded_files
        if not files:
            return None
        if len(files) == 1:
            return self._selected_file() or files[0]
        key = tuple(f["path"] for f in files)
        if self._merge_key != key:
            out = str(Path(self._merge_dir) / f"{Path(files[0]['name']).stem}_Merged.pdf")
            be.merge_pdfs([f["path"] for f in files], out)
            self._merge_key = key
            self._merge_info = {"name": Path(out).name, "path": out,
                                "pages": be.safe_page_count(out)}
        return self._merge_info

    def refresh_preview(self, *_):
        n_files = len(self.win.uploaded_files)
        multi = n_files > 1
        self.file_combo.setVisible(not multi)
        src = self._source()
        pages = src["pages"] if src else 1
        self.file_lbl.setText(
            f"Se unirán {n_files} archivos en el orden de la lista ({pages} páginas) "
            "y después se aplicará N-Up" if multi else "Archivo:")
        per_sheet = self.cols_spin.value() * self.rows_spin.value()
        self.preview.set_total(-(-pages // per_sheet))
        self.preview.schedule()

    def _render_preview(self, idx: int):
        f = self._source()
        if not f:
            return None
        ori = be.nup_resolved_orientation(
            f["path"], self.cols_spin.value(), self.rows_spin.value(),
            self.size_combo.currentText(), self.custom_w.value(), self.custom_h.value(),
            self._gap_value(), self._orientation(), self.rotate_check.isChecked())
        self._update_gap_tooltip(ori)
        self.preview.set_caption(
            f"Vista previa · hoja {'horizontal' if ori == 'landscape' else 'vertical'}")
        return be.preview_nup_png(
            f["path"], idx, self.cols_spin.value(), self.rows_spin.value(),
            size_name=self.size_combo.currentText(),
            custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value(),
            gap_mm=self._gap_value(), orientation=self._orientation(),
            auto_rotate=self.rotate_check.isChecked())

    def _on_size_choice_changed(self, text: str):
        self.custom_row_widget.setVisible(text == "Personalizado")

    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _do_nup(self):
        f = self._source()
        if not f:
            self.win.snack("Selecciona un archivo", "error"); return
        multi = len(self.win.uploaded_files) > 1
        out = be.n_up_pdf(
            f["path"], cols=self.cols_spin.value(), rows=self.rows_spin.value(),
            size_name=self.size_combo.currentText(),
            custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value(),
            gap_mm=self._gap_value(), orientation=self._orientation(),
            auto_rotate=self.rotate_check.isChecked())
        if out:
            if multi:
                self.win.record_step("merge")
            self.win.record_step("nup", {
                "cols": self.cols_spin.value(), "rows": self.rows_spin.value(),
                "size_name": self.size_combo.currentText(),
                "custom_w_mm": self.custom_w.value(), "custom_h_mm": self.custom_h.value(),
                "gap_mm": self._gap_value(), "orientation": self._orientation(),
                "auto_rotate": self.rotate_check.isChecked()})
        if out and multi:
            self.win.load_single_result(out)
        elif out:
            self.win.replace_file(f, out)
            self.populate()
            self.refresh_preview()
            self.win.snack(f"✓ N-Up aplicado: {Path(out).name}")
        else:
            self.win.snack("No se pudo aplicar N-Up", "error")


# ══════════════════════════════════════════════════════════════════════════
#  WORKFLOWS (macros): guardar, editar, ejecutar
# ══════════════════════════════════════════════════════════════════════════
_LIST_SELECT_QSS = (
    f"QListWidget::item {{ border-radius: 8px; padding: 6px 8px; color: {TEXT}; }}"
    f"QListWidget::item:selected {{ background-color: rgba(192,130,88,0.28); color: {TEXT}; }}"
    f"QListWidget::item:hover {{ background-color: rgba(243,241,228,0.06); color: {TEXT}; }}")


class WorkflowEditorDialog(QDialog):
    """Nombra un workflow, reordena/quita pasos y marca qué valores de texto
    se preguntan al ejecutar (los que cambian en cada archivo)."""
    def __init__(self, steps: list[dict], name: str = "", parent=None,
                 title: str = "Guardar como workflow"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 600)
        self.steps = [copy.deepcopy(s) for s in steps]
        self.name = ""

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Nombre del workflow:"))
        self.name_field = QLineEdit(name)
        self.name_field.setPlaceholderText("p.ej. Enviar a cliente")
        root.addWidget(self.name_field)

        hint = QLabel("Estos pasos se aplicarán, en orden, a cada archivo que subas "
                       "(«Unir archivos» junta todos en uno). Quita los que no quieras.")
        hint.setObjectName("Hint"); hint.setWordWrap(True)
        root.addWidget(hint)

        self.list = QListWidget()
        self.list.setStyleSheet(_LIST_SELECT_QSS)
        self.list.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self.list, 1)

        row = QHBoxLayout()
        up_btn = QPushButton("Subir");  up_btn.clicked.connect(lambda: self._move(-1))
        down_btn = QPushButton("Bajar"); down_btn.clicked.connect(lambda: self._move(1))
        del_btn = _btn("Quitar paso", "trash", "Danger", icon_color=DANGER)
        del_btn.clicked.connect(self._remove)
        row.addWidget(up_btn); row.addWidget(down_btn); row.addStretch(1); row.addWidget(del_btn)
        root.addLayout(row)

        self.ask_card = QFrame(); self.ask_card.setObjectName("Card")
        ask_lay = QVBoxLayout(self.ask_card)
        t = QLabel("Preguntar al ejecutar"); t.setObjectName("SectionTitle")
        ask_lay.addWidget(t)
        ask_hint = QLabel("Marca lo que cambia en cada archivo: se te pedirá al lanzar el workflow.")
        ask_hint.setObjectName("Hint"); ask_hint.setWordWrap(True)
        ask_lay.addWidget(ask_hint)
        self.ask_box = QVBoxLayout()
        ask_lay.addLayout(self.ask_box)
        root.addWidget(self.ask_card)

        btns = QHBoxLayout()
        save_btn = _btn("Guardar", "save", "Primary")
        cancel_btn = QPushButton("Cancelar")
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch(1); btns.addWidget(cancel_btn); btns.addWidget(save_btn)
        root.addLayout(btns)

        self._refresh(0)

    def _refresh(self, select: int = 0):
        self.list.blockSignals(True)
        self.list.clear()
        for i, s in enumerate(self.steps):
            self.list.addItem(f"{i + 1}.  {wf.describe(s)}")
        self.list.blockSignals(False)
        if self.steps:
            self.list.setCurrentRow(max(0, min(select, len(self.steps) - 1)))
        self._on_row_changed(self.list.currentRow())

    def _askable(self, step: dict) -> list[str]:
        names = wf.PROMPTABLE.get(step["type"], {})
        if step["type"] == "metadata":
            return [k for k in names if k in step["params"]]
        return list(names)

    def _on_row_changed(self, row: int):
        while self.ask_box.count():
            w = self.ask_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not (0 <= row < len(self.steps)):
            return
        step = self.steps[row]
        names = self._askable(step)
        if not names:
            lbl = QLabel("Este paso no tiene valores de texto que preguntar.")
            lbl.setObjectName("Hint")
            self.ask_box.addWidget(lbl)
            return
        for name in names:
            label = wf.PROMPTABLE[step["type"]][name]
            cb = QCheckBox(f"{label}  (valor guardado: «{step['params'].get(name, '')}»)")
            cb.setChecked(name in step.get("ask", []))
            cb.toggled.connect(lambda on, n=name, r=row: self._toggle_ask(r, n, on))
            self.ask_box.addWidget(cb)

    def _toggle_ask(self, row: int, name: str, on: bool):
        ask = self.steps[row].setdefault("ask", [])
        if on and name not in ask:
            ask.append(name)
        elif not on and name in ask:
            ask.remove(name)
        self.list.item(row).setText(f"{row + 1}.  {wf.describe(self.steps[row])}")

    def _move(self, delta: int):
        r = self.list.currentRow()
        n = r + delta
        if 0 <= r < len(self.steps) and 0 <= n < len(self.steps):
            self.steps[r], self.steps[n] = self.steps[n], self.steps[r]
            self._refresh(n)

    def _remove(self):
        r = self.list.currentRow()
        if 0 <= r < len(self.steps):
            del self.steps[r]
            self._refresh(r)

    def _save(self):
        name = self.name_field.text().strip()
        if not name:
            QMessageBox.warning(self, "Falta el nombre", "Ponle un nombre al workflow."); return
        if not self.steps:
            QMessageBox.warning(self, "Sin pasos", "El workflow no tiene ningún paso."); return
        self.name = name
        self.accept()


class AskValuesDialog(QDialog):
    """Pide, al ejecutar, los valores marcados como 'preguntar al ejecutar'."""
    def __init__(self, workflow: dict, fields: list[tuple[int, str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ejecutar: {workflow['name']}")
        self.resize(520, 200)
        self.values: dict[int, dict] = {}
        self._fields = fields
        self._edits: list[QLineEdit] = []
        root = QVBoxLayout(self)
        intro = QLabel("Rellena los valores de esta vez:")
        intro.setObjectName("Hint")
        root.addWidget(intro)
        for si, name, label in fields:
            step = workflow["steps"][si]
            lbl = QLabel(f"{label}  ·  paso {si + 1}: {wf.STEP_LABELS.get(step['type'], step['type'])}")
            edit = QLineEdit(step["params"].get(name, ""))
            root.addWidget(lbl)
            root.addWidget(edit)
            self._edits.append(edit)
        btns = QHBoxLayout()
        run_btn = _btn("Ejecutar", "play", "Primary")
        cancel_btn = QPushButton("Cancelar")
        run_btn.clicked.connect(self._ok)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch(1); btns.addWidget(cancel_btn); btns.addWidget(run_btn)
        root.addLayout(btns)
        if self._edits:
            self._edits[0].setFocus()
            self._edits[0].selectAll()

    def _ok(self):
        out: dict[int, dict] = {}
        for (si, name, label), edit in zip(self._fields, self._edits):
            text = edit.text()
            if name in ("buscar", "texto") and not text.strip():
                QMessageBox.warning(self, "Falta un valor", f"«{label}» no puede estar vacío.")
                edit.setFocus(); return
            out.setdefault(si, {})[name] = text
        self.values = out
        self.accept()


class WorkflowsPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self._wfs: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader("Workflows", lambda: win.go_home()))

        hint = QLabel("Secuencias de pasos guardadas. Elige una, sube los archivos y se ejecuta sola. "
                       "Para crear una: aplica tus herramientas como siempre y pulsa "
                       "«Guardar como workflow» en la pantalla principal.")
        hint.setObjectName("Hint"); hint.setWordWrap(True)
        root.addWidget(hint)

        self.list = QListWidget()
        self.list.setStyleSheet(_LIST_SELECT_QSS)
        self.list.setSpacing(4)
        self.list.itemDoubleClicked.connect(lambda *_: self._run())
        root.addWidget(self.list, 1)

        self.empty_lbl = QLabel("Todavía no hay ningún workflow guardado.")
        self.empty_lbl.setObjectName("Hint")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self.empty_lbl)

        row = QHBoxLayout()
        run_btn = _btn("Ejecutar", "play", "Primary")
        edit_btn = _btn("Editar", "pencil")
        del_btn = _btn("Borrar", "trash", "Danger", icon_color=DANGER)
        run_btn.clicked.connect(self._run)
        edit_btn.clicked.connect(self._edit)
        del_btn.clicked.connect(self._delete)
        row.addWidget(run_btn); row.addWidget(edit_btn); row.addStretch(1); row.addWidget(del_btn)
        root.addLayout(row)

    def populate(self):
        self._wfs = wf.load_workflows()
        self.list.clear()
        for w in self._wfs:
            item = QListWidgetItem()
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.setSpacing(2)
            name = QLabel(w["name"])
            name.setStyleSheet("font-size:14px; font-weight:700; background:transparent;")
            summ = QLabel(wf.summarize(w["steps"]))
            summ.setObjectName("Hint"); summ.setWordWrap(True)
            summ.setStyleSheet("background:transparent;")
            lay.addWidget(name); lay.addWidget(summ)
            box.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            item.setSizeHint(box.sizeHint() + QSize(0, 8))
            self.list.addItem(item)
            self.list.setItemWidget(item, box)
        if self._wfs:
            self.list.setCurrentRow(0)
        self.empty_lbl.setVisible(not self._wfs)

    def _current(self) -> dict | None:
        r = self.list.currentRow()
        return self._wfs[r] if 0 <= r < len(self._wfs) else None

    def _run(self):
        w = self._current()
        if not w:
            self.win.snack("Elige un workflow", "error"); return
        self.win.run_workflow(w)

    def _edit(self):
        w = self._current()
        if not w:
            self.win.snack("Elige un workflow", "error"); return
        dlg = WorkflowEditorDialog(w["steps"], w["name"], self, title="Editar workflow")
        if dlg.exec() == QDialog.Accepted:
            w["name"], w["steps"] = dlg.name, dlg.steps
            wf.save_workflows(self._wfs)
            self.populate()
            self.win.snack(f"✓ Workflow «{w['name']}» actualizado")

    def _delete(self):
        w = self._current()
        if not w:
            return
        ans = QMessageBox.question(self, "Borrar workflow", f"¿Borrar «{w['name']}»?")
        if ans == QMessageBox.Yes:
            self._wfs.remove(w)
            wf.save_workflows(self._wfs)
            self.populate()


# ══════════════════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    steps_changed = Signal()
    workflow_done = Signal(object, object)   # (rutas de salida, avisos)
    workflow_progress = Signal(str)
    file_ready = Signal(str, str)            # (ruta, nombre): un archivo ya convertido, listo para la lista
    notice = Signal(str, str)                # (mensaje, tipo): avisos desde hilos secundarios

    def __init__(self):
        super().__init__()
        global _GUI_BRIDGE
        _GUI_BRIDGE = _GuiBridge()           # se crea aquí: en el hilo de la pantalla
        self.file_ready.connect(self.add_file)
        self.notice.connect(self.snack)
        self.session_steps: list[dict] = []
        self.saved_upto = 0          # cuántos pasos de la sesión ya están guardados
        self.saved_name = ""
        self.saved_id = ""           # workflow al que se pueden añadir los pasos nuevos
        self.setWindowTitle("PDF Manager – Travel Agent Edition")
        self.setMinimumSize(480, 480)
        self.resize(1080, 820)
        icon_path = be.resource_path("provecto_icon.ico")
        if Path(icon_path).is_file():
            self.setWindowIcon(QIcon(icon_path))

        self.uploaded_files: list[dict] = []

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_page = HomePage(self)
        self.organize_page = OrganizePage(self)
        self.edit_page = EditPage(self)
        self.metadata_page = MetadataPage(self)
        self.split_page = SplitPage(self)
        self.size_margins_page = SizeMarginsPage(self)
        self.nup_page = NUpPage(self)
        self.workflows_page = WorkflowsPage(self)
        self.tools_page = ToolsPage(self)

        for p in (self.home_page, self.organize_page,
                  self.edit_page, self.metadata_page, self.split_page,
                  self.size_margins_page, self.nup_page, self.workflows_page, self.tools_page):
            self.stack.addWidget(p)
        self.stack.setCurrentWidget(self.home_page)

        self._wf_progress: QProgressDialog | None = None
        self.steps_changed.connect(self.home_page.refresh_steps_bar)
        self.workflow_done.connect(self._on_workflow_done)
        self.workflow_progress.connect(self._on_workflow_progress)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

    # ── Utilidades ──────────────────────────────────────────────────────
    def snack(self, msg: str, kind: str = "success"):
        colors = {"success": "#92976C", "error": "#D47268", "info": "#C08258"}
        self.status.setStyleSheet(f"color:{colors.get(kind, '#92976C')};")
        self.status.showMessage(msg, 4000)

    def go_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def add_files_any(self, paths: list):
        """Añade PDFs tal cual y convierte a PDF lo demás (fotos, texto, HTML, Word…). Las fotos se convierten una
        a una (cada una su PDF, con su tamaño) para poder ordenarlas o unirlas después. Lo que no se reconoce se avisa."""
        accepted = ptl.accepted_extensions()
        convert, unknown = [], []
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext == ".pdf":
                self.add_file(p, Path(p).name)
            elif ext in accepted:
                convert.append(p)
            elif p:
                unknown.append(Path(p).name)
        unknown_msg = ""
        if unknown:
            shown = ", ".join(unknown[:3]) + ("…" if len(unknown) > 3 else "")
            unknown_msg = (f"No sé abrir: {shown}. Aceptados: PDF, fotos (JPG, PNG, TIFF, BMP, WEBP, GIF), texto, "
                           "Markdown, HTML y, con LibreOffice, Word/Excel/PowerPoint.")
        if not convert:
            if unknown_msg:
                self.snack(unknown_msg, "error")
            return
        self.snack(f"Convirtiendo {len(convert)} archivo{'s' if len(convert) != 1 else ''} a PDF…", "info")

        def work():
            fails = []
            for p in convert:
                try:
                    out = ptl.convert_one(p)
                    self.file_ready.emit(out, Path(out).name)
                except ptl.ToolError as e:
                    fails.append(f"{Path(p).name}: {e}")
                except Exception as e:
                    fails.append(f"{Path(p).name}: error inesperado ({e})")
            if fails or unknown_msg:
                self.notice.emit(" · ".join(fails + ([unknown_msg] if unknown_msg else []))[:500], "error")
        run_bg(work)

    def add_file(self, path: str, name: str):
        if not path or not Path(path).exists():
            self.snack(f"No se pudo cargar: {name}", "error"); return
        pages = be.safe_page_count(path)
        locked = False
        if pages == 0:
            locked = ptl.is_locked(path)
            if locked:
                try:
                    import fitz as _fz
                    pages = 1
                except Exception:
                    pages = 1
            else:
                self.snack(f"PDF inválido: {name}", "error"); return
        self.uploaded_files.append({"name": name, "path": path, "pages": pages, "locked": locked})
        self.home_page.refresh_file_list()
        if locked:
            self.snack(f"🔒 {name} tiene contraseña: desbloquéalo en Herramientas → Proteger antes de usarlo.", "info")
        else:
            self.snack(f"✓ {name} ({pages} pág.)")

    def remove_file_obj(self, f: dict):
        if f in self.uploaded_files:
            self.uploaded_files.remove(f)
            self.home_page.refresh_file_list()

    def reorder_files(self, new_order: list[dict]):
        self.uploaded_files = list(new_order)

    def closeEvent(self, e):
        ep = getattr(self, "edit_page", None)
        if not getattr(self, "_force_quit", False) and ep is not None and ep.dirty and ep.doc is not None:
            r = QMessageBox.question(self, "Cambios sin guardar",
                                     "Tienes cambios sin guardar en el editor. ¿Guardarlos antes de salir?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if r == QMessageBox.Cancel:
                e.ignore()
                return
            if r == QMessageBox.Save:
                ep._save_changes()
            dr.clear()
        elif not getattr(self, "_force_quit", False):
            dr.clear()
        super().closeEvent(e)

    def check_draft(self):
        """Al arrancar: si quedó un borrador (cierre brusco o reinicio pedido), lo recupera."""
        d = dr.load()
        if not d:
            return
        if not d.get("restart"):
            when = time.strftime("%d/%m/%Y %H:%M", time.localtime(d.get("time", 0)))
            r = QMessageBox.question(
                self, "Recuperar trabajo anterior",
                f"La aplicación se cerró sin guardar «{d.get('name', 'documento.pdf')}» (borrador del {when}).\n"
                "¿Quieres continuar con el trabajo anterior?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if r != QMessageBox.Yes:
                dr.clear()
                return
        name = d.get("name") or "documento.pdf"
        dest = Path(tempfile.mkdtemp(prefix="recuperado_")) / name
        try:
            shutil.copy(d["path"], dest)
        except Exception:
            self.snack("No se pudo recuperar el borrador.", "error")
            return
        self.uploaded_files.clear()
        self.add_file(str(dest), name)
        self.open_edit_view()
        ep = self.edit_page
        if ep.doc is not None:
            ep.dirty = bool(d.get("dirty", True))
            if ep.dirty:
                ep._write_draft()
            else:
                dr.clear()
            self.snack("Documento reabierto" + (" con tus cambios sin guardar." if ep.dirty else "."), "success")

    def open_in_viewer(self, f: dict):
        QDesktopServices.openUrl(QUrl.fromLocalFile(f["path"]))

    def clear_all(self):
        self.uploaded_files.clear()
        self.home_page.refresh_file_list()
        self.clear_steps()

    def record_step(self, step_type: str, params: dict | None = None):
        """Registra en silencio cada herramienta aplicada, para poder
        guardar la secuencia como workflow. Seguro desde hilos (señal)."""
        self.session_steps.append(wf.new_step(step_type, params))
        self.steps_changed.emit()

    def clear_steps(self):
        self.session_steps.clear()
        self.saved_upto = 0
        self.saved_name = ""
        self.saved_id = ""
        self.steps_changed.emit()

    def load_single_result(self, out_path: str):
        """Tras procesar: el resultado pasa a ser el único archivo cargado,
        listo para guardarlo o encadenar otra herramienta de la suite."""
        pages = be.safe_page_count(out_path)
        self.uploaded_files = [{"name": Path(out_path).name, "path": out_path, "pages": pages}]
        self.home_page.refresh_file_list()
        self.go_home()
        self.snack(f"✓ {Path(out_path).name} — guardado en Descargas. "
                    "Puedes guardarlo como o seguir con otra herramienta.")

    def replace_file(self, old_f: dict, new_path: str):
        """Sustituye un archivo concreto (p.ej. tras Edit/Metadata) por su
        versión procesada, sin tocar el resto de archivos cargados."""
        pages = be.safe_page_count(new_path)
        new_f = {"name": Path(new_path).name, "path": new_path, "pages": pages}
        if old_f in self.uploaded_files:
            self.uploaded_files[self.uploaded_files.index(old_f)] = new_f
        else:
            self.uploaded_files.append(new_f)
        self.home_page.refresh_file_list()
        return new_f

    def do_save_as_copy(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        src = self.uploaded_files[0]["path"]
        dest, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", self.uploaded_files[0]["name"], "PDF (*.pdf)")
        if not dest:
            return
        import shutil
        shutil.copy2(src, dest)
        self.snack(f"✓ Guardado: {Path(dest).name}")

    def after_save(self, out_path: str):
        """Tras Merge/Organize: el resultado pasa a ser el archivo cargado."""
        self.load_single_result(out_path)

    # ── Acciones de la barra principal ──────────────────────────────────
    def do_merge_standalone(self):
        if len(self.uploaded_files) < 2:
            self.snack("Añade al menos 2 PDFs para unir", "error"); return
        paths = [f["path"] for f in self.uploaded_files]
        first = Path(self.uploaded_files[0]["name"]).stem
        out_name = f"{first}_Merged.pdf"
        dest = str(be.DOWNLOADS / out_name)
        be.merge_pdfs(paths, dest)
        self.record_step("merge")
        self.after_save(dest)

    def do_ajuste_standalone(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return

        if len(self.uploaded_files) == 1:
            self._open_ajuste_for_file(self.uploaded_files[0], single=True)
            return

        choice, ok = QInputDialog.getItem(
            self, "Ajuste de imagen", "¿Qué quieres ajustar?",
            ["Todos los archivos juntos (navegar como en un merge)",
             "Solo un archivo suelto"],
            0, False)
        if not ok:
            return

        if choice.startswith("Todos"):
            dlg = AjusteMultiDialog(self.uploaded_files, self)
            if dlg.exec() == QDialog.Accepted and dlg.results:
                for fi, out in dlg.results.items():
                    self.snack(f"✓ Ajuste: {Path(out).name}")
                    self.replace_file(self.uploaded_files[fi], out)
                if dlg.applied_params:
                    self.record_step("adjust", dlg.applied_params)
        else:
            names = [f["name"] for f in self.uploaded_files]
            name, ok2 = QInputDialog.getItem(
                self, "Elegir archivo", "¿Qué PDF quieres ajustar?", names, 0, False)
            if not ok2:
                return
            f = next((f for f in self.uploaded_files if f["name"] == name), None)
            if f:
                self._open_ajuste_for_file(f, single=False)

    def _open_ajuste_for_file(self, f: dict, single: bool):
        dlg = AjusteDialog(f["path"], self)
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            self.snack(f"✓ Ajuste: {Path(dlg.result_path).name}")
            if dlg.applied_params:
                self.record_step("adjust", dlg.applied_params)
            if single:
                self.load_single_result(dlg.result_path)
            else:
                self.replace_file(f, dlg.result_path)

    # ── Navegación a vistas ──────────────────────────────────────────────
    def _locked_file(self):
        """Primer PDF cargado que aún tiene contraseña de apertura (las demás pantallas no pueden abrirlo)."""
        for f in self.uploaded_files:
            if f.get("locked"):
                return f
        return None

    def open_tools_view(self):
        self.tools_page.populate()
        self.stack.setCurrentWidget(self.tools_page)

    def open_organize_view(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        lf = self._locked_file()
        if lf:
            self.snack(f"«{lf['name']}» tiene contraseña: desbloquéalo en Herramientas → Proteger.", "error"); return
        self.organize_page.populate()
        self.stack.setCurrentWidget(self.organize_page)

    def open_edit_view(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        lf = self._locked_file()
        if lf:
            self.snack(f"«{lf['name']}» tiene contraseña: desbloquéalo en Herramientas → Proteger.", "error"); return
        if not be.HAS_FITZ:
            self.snack("PyMuPDF (fitz) no está instalado", "error"); return
        self.edit_page.populate()
        self.stack.setCurrentWidget(self.edit_page)

    def open_metadata_view(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        lf = self._locked_file()
        if lf:
            self.snack(f"«{lf['name']}» tiene contraseña: desbloquéalo en Herramientas → Proteger.", "error"); return
        if not be.HAS_FITZ:
            self.snack("PyMuPDF (fitz) no está instalado", "error"); return
        self.metadata_page.populate()
        self.stack.setCurrentWidget(self.metadata_page)

    def open_split_view(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        lf = self._locked_file()
        if lf:
            self.snack(f"«{lf['name']}» tiene contraseña: desbloquéalo en Herramientas → Proteger.", "error"); return
        self.split_page.populate()
        self.stack.setCurrentWidget(self.split_page)

    def open_size_margins_view(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        lf = self._locked_file()
        if lf:
            self.snack(f"«{lf['name']}» tiene contraseña: desbloquéalo en Herramientas → Proteger.", "error"); return
        if not be.HAS_FITZ:
            self.snack("PyMuPDF (fitz) no está instalado", "error"); return
        self.size_margins_page.populate()
        self.size_margins_page.refresh_preview()
        self.stack.setCurrentWidget(self.size_margins_page)

    # ── Workflows ────────────────────────────────────────────────────────
    def open_workflows_view(self):
        self.workflows_page.populate()
        self.stack.setCurrentWidget(self.workflows_page)

    def save_session_as_workflow(self):
        if not self.session_steps:
            self.snack("Aún no has aplicado ninguna herramienta", "error"); return
        workflows = wf.load_workflows()
        dup = wf.find_duplicate(self.session_steps, workflows)
        if dup:
            self.saved_upto = len(self.session_steps)
            self.saved_name = dup["name"]
            self.saved_id = dup["id"]
            self.steps_changed.emit()
            QMessageBox.information(
                self, "Ya está guardado",
                f"Ya tienes el workflow «{dup['name']}» con exactamente estos pasos.")
            return
        dlg = WorkflowEditorDialog(self.session_steps, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_wf = wf.new_workflow(dlg.name, dlg.steps)
        workflows.append(new_wf)
        if wf.save_workflows(workflows):
            self.saved_upto = len(self.session_steps)
            self.saved_name = dlg.name
            self.saved_id = new_wf["id"]
            self.steps_changed.emit()
            self.snack(f"✓ Workflow «{dlg.name}» guardado — lo tienes en Workflows")
        else:
            self.snack("No se pudo guardar el workflow", "error")

    def append_session_to_saved(self):
        """Añade al workflow ya guardado solo los pasos aplicados después."""
        workflows = wf.load_workflows()
        target = next((w for w in workflows if w["id"] == self.saved_id), None)
        new_steps = self.session_steps[self.saved_upto:]
        if target is None:
            self.snack("Ese workflow ya no existe: guárdalo como nuevo", "error")
            self.saved_id = ""
            self.steps_changed.emit()
            return
        if not new_steps:
            return
        dlg = WorkflowEditorDialog(new_steps, target["name"], self,
                                   title=f"Añadir pasos a «{target['name']}»")
        if dlg.exec() != QDialog.Accepted:
            return
        target["steps"].extend(dlg.steps)
        target["name"] = dlg.name
        if wf.save_workflows(workflows):
            self.saved_upto = len(self.session_steps)
            self.saved_name = target["name"]
            self.steps_changed.emit()
            self.snack(f"✓ {len(dlg.steps)} paso(s) añadidos a «{target['name']}»")
        else:
            self.snack("No se pudo guardar el workflow", "error")

    def run_workflow(self, w: dict):
        files = [f["path"] for f in self.uploaded_files]
        if not files:
            files, _ = QFileDialog.getOpenFileNames(
                self, f"Archivos para «{w['name']}»", "", "PDF (*.pdf)")
            if not files:
                return
        fields = wf.prompt_fields(w["steps"])
        values: dict[int, dict] = {}
        if fields:
            dlg = AskValuesDialog(w, fields, self)
            if dlg.exec() != QDialog.Accepted:
                return
            values = dlg.values
        prog = QProgressDialog(f"Ejecutando «{w['name']}»…", None, 0, 0, self)
        prog.setWindowTitle("Workflow")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setCancelButton(None)
        prog.show()
        self._wf_progress = prog
        steps = copy.deepcopy(w["steps"])

        def _job():
            try:
                outs, warns = wf.run_workflow(
                    steps, files, values,
                    progress=lambda i, n, label: self.workflow_progress.emit(
                        f"Paso {min(i + 1, n)} de {n}: {label}"))
            except Exception as e:
                outs, warns = [], [f"Error inesperado: {e}"]
            self.workflow_done.emit(outs, warns)

        run_bg(_job)

    def _on_workflow_progress(self, text: str):
        if self._wf_progress is not None:
            self._wf_progress.setLabelText(text)

    def _on_workflow_done(self, outs: list, warns: list):
        if self._wf_progress is not None:
            self._wf_progress.close()
            self._wf_progress = None
        if outs:
            self.uploaded_files = [
                {"name": Path(o).name, "path": o, "pages": be.safe_page_count(o)} for o in outs]
            self.home_page.refresh_file_list()
            self.go_home()
            self.snack(f"✓ Workflow terminado: {len(outs)} archivo(s) en Descargas")
        else:
            self.snack("El workflow no generó ningún archivo", "error")
        if warns:
            QMessageBox.information(self, "Avisos del workflow", "\n".join(f"• {w}" for w in warns))

    def open_nup_view(self):
        if not self.uploaded_files:
            self.snack("Añade al menos un PDF", "error"); return
        lf = self._locked_file()
        if lf:
            self.snack(f"«{lf['name']}» tiene contraseña: desbloquéalo en Herramientas → Proteger.", "error"); return
        if not be.HAS_FITZ:
            self.snack("PyMuPDF (fitz) no está instalado", "error"); return
        self.nup_page.populate()
        self.nup_page.refresh_preview()
        self.stack.setCurrentWidget(self.nup_page)


def main():
    if sys.platform == "win32":
        # Sin esto, Windows agrupa la ventana bajo el icono de python.exe en
        # la barra de tareas en vez de usar el nuestro (setWindowIcon).
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Provecto.PDFManager.1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    try:                                         # menús y botones estándar de Qt en español (Cortar, Copiar, Pegar…)
        from PySide6.QtCore import QTranslator, QLibraryInfo
        _tr = QTranslator()
        if _tr.load("qtbase_es", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(_tr)
            app._qt_translator = _tr
    except Exception:
        pass
    icon_path = be.resource_path("provecto_icon.ico")
    if Path(icon_path).is_file():
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    QTimer.singleShot(500, win.check_draft)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
