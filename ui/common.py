# -*- coding: utf-8 -*-
"""Utilidades compartidas de la interfaz: botones, hilos, sombras y logo."""
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


def init_bridge():
    """Crea el puente al hilo de la pantalla (hay que llamarlo desde ese hilo)."""
    global _GUI_BRIDGE
    _GUI_BRIDGE = _GuiBridge()


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


# ══════════════════════════════════════════════════════════════════════════
#  WORKFLOWS (macros): guardar, editar, ejecutar
# ══════════════════════════════════════════════════════════════════════════
_LIST_SELECT_QSS = (
    f"QListWidget::item {{ border-radius: 8px; padding: 6px 8px; color: {TEXT}; }}"
    f"QListWidget::item:selected {{ background-color: rgba(192,130,88,0.28); color: {TEXT}; }}"
    f"QListWidget::item:hover {{ background-color: rgba(243,241,228,0.06); color: {TEXT}; }}")
