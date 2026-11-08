# -*- coding: utf-8 -*-
"""Pantalla Dividir y sus componentes de selección de páginas."""
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
from ui.common import _btn, add_shadow
from ui.widgets import BackHeader, SelectablePageGrid, render_page_card


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
