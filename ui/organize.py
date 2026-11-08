# -*- coding: utf-8 -*-
"""Pantalla Organizar: cuadrícula de miniaturas de páginas."""
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
from ui.common import FILE_COLORS, _btn
from ui.widgets import BackHeader, render_page_card


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
