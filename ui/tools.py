# -*- coding: utf-8 -*-
"""Pantalla Herramientas: comprimir, proteger, marca de agua, reparar, convertir y OCR."""
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
from ui.common import ICON_DARK, _ToolJob, _btn, _human_size
from ui.ocr import OcrPagesPanel, OcrReviewDialog
from ui.widgets import BackHeader


class ToolPreview(QFrame):
    """Vista previa de la página del archivo elegido, con ‹ › para recorrerlas. Una herramienta puede ponerle un
    «hook» que transforma la página antes de mostrarla (la marca de agua, por ejemplo)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self._path, self._pw, self._n, self._i = "", "", 0, 0
        self.hook = None                                      # hook(ruta de un PDF de 1 página, nº de página) -> ruta | None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._render)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        nav = QHBoxLayout()
        self.prev_b = _btn("‹", None, "Flat")
        self.prev_b.setFixedWidth(34)
        self.next_b = _btn("›", None, "Flat")
        self.next_b.setFixedWidth(34)
        self.prev_b.clicked.connect(lambda: self.goto(self._i - 1))
        self.next_b.clicked.connect(lambda: self.goto(self._i + 1))
        self.lbl = QLabel("")
        self.lbl.setObjectName("Hint")
        self.lbl.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.prev_b)
        nav.addWidget(self.lbl, 1)
        nav.addWidget(self.next_b)
        lay.addLayout(nav)
        self.view = QLabel("")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(240, 300)
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        lay.addWidget(self.view, 1)

    def set_file(self, f: dict | None, password: str = ""):
        self._pw = password
        if not f or f.get("locked") and not password:
            self._path, self._n, self._i = "", 0, 0
            self._clear("Sin vista previa" if not f else "🔒 Protegido con contraseña")
            return
        if f["path"] != self._path:
            self._i = 0
        self._path = f["path"]
        try:
            doc = ptl._open(self._path, self._pw)
            self._n = len(doc)
            doc.close()
        except Exception:
            self._n = 0
            self._clear("No se puede mostrar este archivo")
            return
        self._i = min(self._i, max(0, self._n - 1))
        self.refresh()

    def _clear(self, text: str):
        self.view.setPixmap(QPixmap())
        self.view.setText(text)
        self.lbl.setText("")
        self.prev_b.setEnabled(False)
        self.next_b.setEnabled(False)

    def goto(self, i: int):
        if 0 <= i < self._n:
            self._i = i
            self.refresh()

    def refresh(self, delay: int = 0):
        """Vuelve a dibujar la página (con un pequeño retraso se agrupan los cambios seguidos, p. ej. al escribir)."""
        self._timer.start(delay)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._path:
            self.refresh(120)

    def _render(self):
        if not self._path or self._n == 0 or not self.isVisible():
            return
        import fitz as _fz
        try:
            doc = ptl._open(self._path, self._pw)
            try:
                page_doc, k, tmp = doc, self._i, None
                if self.hook is not None:
                    import tempfile
                    one = _fz.open()
                    one.insert_pdf(doc, from_page=self._i, to_page=self._i)
                    tmp = os.path.join(tempfile.mkdtemp(prefix="pdfm_prev_"), "p.pdf")
                    one.save(tmp)
                    one.close()
                    out = self.hook(tmp, self._i)
                    if out:
                        page_doc, k = ptl._open(out, ""), 0
                    else:
                        page_doc, k = ptl._open(tmp, ""), 0
                page = page_doc[k]
                z = min((self.view.width() - 8) / max(page.rect.width, 1), (self.view.height() - 8) / max(page.rect.height, 1))
                z = max(0.2, min(z, 3.0))
                pix = page.get_pixmap(matrix=_fz.Matrix(z, z), alpha=False)
                qi = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                if page_doc is not doc:
                    page_doc.close()
            finally:
                doc.close()
        except Exception:
            self._clear("No se puede mostrar la página")
            return
        self.view.setText("")
        self.view.setPixmap(QPixmap.fromImage(qi))
        self.lbl.setText(f"Página {self._i + 1} de {self._n}")
        self.prev_b.setEnabled(self._i > 0)
        self.next_b.setEnabled(self._i < self._n - 1)


class _ConvList(QListWidget):
    """Lista de archivos a convertir: acepta soltar archivos y muestra una ayuda mientras está vacía."""
    def __init__(self, on_paths):
        super().__init__()
        self._on_paths = on_paths
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setStyleSheet("QListWidget { border: 1px dashed #767A56; border-radius: 10px; }")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        self._on_paths([u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()])

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(TEXT_SOFT))
            p.drawText(self.viewport().rect(), Qt.AlignCenter, "Arrastra aquí los archivos a convertir\no pulsa «Añadir archivos…»")


class ToolsPage(QWidget):
    """Herramientas de archivo completo: comprimir, proteger, marca de agua, aplanar, reparar, convertir y OCR."""
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self._job = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        self.back = BackHeader("Herramientas", lambda: win.go_home())
        root.addWidget(self.back)

        self.file_row = QWidget()
        row = QHBoxLayout(self.file_row)
        row.setContentsMargins(0, 0, 0, 0)
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
        self.pw_field.editingFinished.connect(lambda: self.preview.set_file(self._file(), self.pw_field.text()))
        root.addWidget(self.file_row)
        self.info = QLabel("")
        self.info.setObjectName("Hint")
        root.addWidget(self.info)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()                              # cada herramienta se elige en la barra lateral
        body.addWidget(self.tabs, 3)
        self.preview = ToolPreview()
        body.addWidget(self.preview, 2)
        root.addLayout(body, 1)
        self._build_compress()
        self._build_protect()
        self._build_watermark()
        self._build_fix()
        self._build_convert()
        self._build_ocr()
        self._wm_timer_widgets()

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

    TOOLS = ("Comprimir", "Proteger", "Marca de agua", "Aplanar y reparar", "Convertir a PDF", "OCR")
    WITH_PREVIEW = ("Comprimir", "Proteger", "Marca de agua", "Aplanar y reparar")

    def show_tool(self, name: str):
        """Muestra una sola herramienta: título, opciones y, si la tiene, la vista previa del archivo."""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == name:
                self.tabs.setCurrentIndex(i)
        self.back.title_lbl.setText(name)
        self.file_row.setVisible(name != "Convertir a PDF")
        self.info.setVisible(name != "Convertir a PDF")
        self.preview.setVisible(name in self.WITH_PREVIEW)
        self.preview.hook = self._wm_hook if name == "Marca de agua" else None
        self.populate()
        self.preview.refresh()

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
            self.info.setText("Añade un PDF en la pantalla principal para usar esta herramienta.")
            self.preview.set_file(None)
            return
        try:
            size = _human_size(os.path.getsize(f["path"]))
        except OSError:
            size = "?"
        self.info.setText(f"{size}" + (" · tiene contraseña de apertura" if f.get("locked") else f" · {f['pages']} pág."))
        self.compress_now.setText(f"Peso actual: {size}")
        self.preview.set_file(f, self.pw_field.text())
        self._load_ocr_panel()

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

    def _wm_kwargs(self) -> dict:
        use_img = self.wm_img_rb.isChecked()
        return dict(text="" if use_img else self.wm_text.text(), image=self.wm_img_path.text() if use_img else "",
                    opacity=self.wm_opacity.value() / 100, angle=float(self.wm_angle.value()),
                    color=self.wm_color.currentText(), pages=self.wm_pages.text(), tile=self.wm_tile.isChecked(),
                    password="")

    def _wm_hook(self, tmp_path: str, page_idx: int):
        """Pone la marca de agua en la página que se está viendo (si está entre las páginas elegidas)."""
        f = self._file()
        kw = self._wm_kwargs()
        if f and page_idx not in ptl.parse_pages(kw["pages"], f.get("pages", 1)):
            return None
        kw["pages"] = ""
        try:
            return ptl.watermark(tmp_path, **kw)
        except ptl.ToolError:
            return None

    def _wm_timer_widgets(self):
        """Cualquier cambio en las opciones de la marca de agua redibuja la vista previa."""
        for w, sig in ((self.wm_text, "textChanged"), (self.wm_img_path, "textChanged"), (self.wm_pages, "textChanged"),
                       (self.wm_color, "currentIndexChanged"), (self.wm_opacity, "valueChanged"),
                       (self.wm_angle, "valueChanged"), (self.wm_tile, "toggled"), (self.wm_text_rb, "toggled")):
            getattr(w, sig).connect(lambda *_: self.preview.hook is not None and self.preview.refresh(250))

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
        kw = self._wm_kwargs()
        kw["password"] = self.pw_field.text()
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
        self.conv_list = _ConvList(self._conv_add_paths)
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
        self._conv_add_paths(paths)

    def _conv_add_paths(self, paths: list):
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
        self.ocr_only = QCheckBox("Solo las páginas sin texto"); self.ocr_only.setChecked(True)
        r.addWidget(self.ocr_only)
        self.ocr_precise = QCheckBox("Máxima precisión")
        self.ocr_precise.setToolTip("Usa datos de idioma de alta precisión (tessdata_best, unos 15 MB por idioma, se "
                                    "descargan una vez). Más lento, pero lee mucho mejor el texto borroso o de baja "
                                    "resolución.")
        r.addWidget(self.ocr_precise)
        self.ocr_review = QCheckBox("Revisar el texto antes de guardar")
        self.ocr_review.setChecked(True)
        self.ocr_review.setToolTip("Tras leer, se abre una vista para comparar el texto con la página y corregirlo. "
                                   "Desde ahí también puedes crear un PDF nuevo redibujado con el texto.")
        r.addWidget(self.ocr_review)
        # ── Enderezar (opcional, dentro del mismo OCR)
        self.ocr_straighten = QCheckBox("Enderezar las páginas torcidas")
        self.ocr_straighten.setChecked(True)
        self.ocr_straighten.setToolTip("Busca solo el papel, corrige la perspectiva y gira la página hasta que las líneas "
                                       "de texto queden horizontales (se guía por la base de las letras). Las páginas que "
                                       "ya están rectas no se tocan. Sirve para papel plano: una hoja arrugada no se aplana.")
        r.addWidget(self.ocr_straighten)
        r.addStretch(1)
        lay.addLayout(r)
        self.ocr_panel = OcrPagesPanel(self)
        lay.addWidget(self.ocr_panel, 1)
        self.ocr_straighten.toggled.connect(self.ocr_panel.setVisible)
        self.ocr_only.toggled.connect(lambda _on: self.ocr_panel.refresh_all())
        self.tabs.currentChanged.connect(lambda _i: self._load_ocr_panel())
        b = _btn("Reconocer texto", "play", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_ocr)
        lay.addWidget(b, 0, Qt.AlignLeft)
        self._ocr_checks: dict = {}
        self._ocr_engine_changed()
        page = lay.parentWidget()                               # la pestaña entera se desplaza si la ventana es baja
        idx = self.tabs.indexOf(page)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        sc.setWidget(page)
        self.tabs.removeTab(idx)
        self.tabs.insertTab(idx, sc, "OCR")

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

    def _load_ocr_panel(self):
        """Las miniaturas y la detección de esquinas solo se calculan cuando se abre la pestaña OCR."""
        if self.tabs.tabText(self.tabs.currentIndex()) == "OCR":
            self.ocr_panel.load(self._file(), self.pw_field.text())

    def _do_ocr(self):
        f = self._need_file()
        if not f:
            return
        engine = self.ocr_engine.currentData()
        langs = [c for c, cb in self._ocr_checks.items() if cb.isChecked()]
        if not langs and engine != "rapid":
            self._say("Marca al menos un idioma (o instala uno de la lista).", "error")
            return
        dpi, only, pw = 300, self.ocr_only.isChecked(), self.pw_field.text()   # tope; cada página se lee a la resolución de su escaneo (ptl.render_dpi_for)
        enhance = True                      # siempre: quita ruido y líneas de tabla solo para leer mejor
        straighten, flatten = self.ocr_straighten.isChecked(), True
        manual = self.ocr_panel.manual() if straighten else {}
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
