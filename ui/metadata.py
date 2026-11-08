# -*- coding: utf-8 -*-
"""Pantalla Metadatos."""
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
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import add_shadow
from ui.widgets import BackHeader


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
