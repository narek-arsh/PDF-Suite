# -*- coding: utf-8 -*-
"""Diálogos de ajuste de imagen (brillo, contraste…)."""
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
from ui.common import _btn, pil_to_qpixmap
from ui.widgets import make_slider_row


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
