# -*- coding: utf-8 -*-
"""Portada: lista de archivos y barra lateral de herramientas."""
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
from ui.common import ICON_DARK, _btn, add_shadow, on_gui, provecto_logo_pixmap, run_bg
from ui.widgets import DropArea, FileListWidget


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
