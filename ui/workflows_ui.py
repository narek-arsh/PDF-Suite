# -*- coding: utf-8 -*-
"""Workflows: editor, preguntas al ejecutar y lista."""
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
from ui.common import _LIST_SELECT_QSS, _btn
from ui.widgets import BackHeader


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
