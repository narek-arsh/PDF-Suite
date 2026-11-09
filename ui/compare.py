# -*- coding: utf-8 -*-
"""Pantalla Comparar: dos PDFs, página a página, con las diferencias resaltadas."""
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QFrame,
    QComboBox,
    QPlainTextEdit,
    QSizePolicy,
    QProgressBar,
    QAbstractItemView,
)

import fitz
import pdf_tools as ptl
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import ICON_DARK, _ToolJob, _btn, add_shadow
from ui.widgets import BackHeader

STATUS_COLOR = {"igual": "#92976C", "diferente": "#D47268", "añadida": "#C08258", "quitada": "#D47268"}
STATUS_LABEL = {"igual": tr("Igual"), "diferente": tr("Diferente"), "añadida": tr("Solo en B (añadida)"),
                "quitada": tr("Solo en A (quitada)")}


class ComparePage(QWidget):
    """Compara dos PDFs ya subidos, página a página: texto y aspecto visual. No modifica ninguno de los dos."""

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self._job = None
        self._result = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader(tr("Comparar PDFs"), lambda: win.go_home()))

        hint = QLabel(tr("Elige dos PDFs ya subidos (o añade uno nuevo desde el disco) y pulsa «Comparar». Se "
                      "compara el texto y el aspecto de cada página; no se modifica ninguno de los dos archivos."))
        hint.setObjectName("Hint"); hint.setWordWrap(True)
        root.addWidget(hint)

        pick_card = QFrame(); pick_card.setObjectName("Card")
        add_shadow(pick_card, blur=18, dy=4, alpha=70)
        pc = QVBoxLayout(pick_card)
        for label, attr in ((tr("Archivo A"), "a"), (tr("Archivo B"), "b")):
            row = QHBoxLayout()
            row.addWidget(QLabel(label + ":"))
            combo = QComboBox(); combo.setMinimumWidth(220)
            setattr(self, f"{attr}_combo", combo)
            row.addWidget(combo, 1)
            row.addWidget(QLabel(tr("Contraseña:")))
            pw = QLineEdit(); pw.setEchoMode(QLineEdit.Password); pw.setPlaceholderText(tr("solo si la tiene"))
            pw.setFixedWidth(150)
            setattr(self, f"{attr}_pw", pw)
            row.addWidget(pw)
            pc.addLayout(row)
        btn_row = QHBoxLayout()
        self.compare_btn = _btn(tr("Comparar"), "swap", "Primary", icon_color=ICON_DARK)
        self.compare_btn.clicked.connect(self._do_compare)
        btn_row.addWidget(self.compare_btn)
        btn_row.addStretch(1)
        self.bar = QProgressBar(); self.bar.setRange(0, 1); self.bar.setValue(0); self.bar.setTextVisible(False)
        self.bar.setFixedWidth(140)
        btn_row.addWidget(self.bar)
        pc.addLayout(btn_row)
        self.summary = QLabel(""); self.summary.setObjectName("Hint"); self.summary.setWordWrap(True)
        pc.addWidget(self.summary)
        root.addWidget(pick_card)

        body = QHBoxLayout(); body.setSpacing(14)
        self.page_list = QListWidget()
        self.page_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.page_list.setMaximumWidth(230)
        self.page_list.currentRowChanged.connect(self._show_page)
        body.addWidget(self.page_list, 0)

        right = QVBoxLayout()
        imgs = QHBoxLayout()
        self.view_a = self._thumb_label("A")
        self.view_diff = self._thumb_label(tr("Diferencias"))
        self.view_b = self._thumb_label("B")
        for v in (self.view_a, self.view_diff, self.view_b):
            imgs.addWidget(v["card"], 1)
        right.addLayout(imgs, 3)

        self.text_diff = QPlainTextEdit(); self.text_diff.setReadOnly(True)
        self.text_diff.setPlaceholderText(tr("El texto de la página aparece aquí cuando hay diferencias."))
        self.text_diff.setMaximumHeight(140)
        right.addWidget(self.text_diff)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

    def _thumb_label(self, title: str) -> dict:
        card = QFrame(); card.setObjectName("Card")
        c = QVBoxLayout(card)
        t = QLabel(title); t.setObjectName("Hint"); t.setAlignment(Qt.AlignCenter)
        c.addWidget(t)
        img = QLabel(""); img.setAlignment(Qt.AlignCenter)
        img.setMinimumSize(180, 240)
        img.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        c.addWidget(img, 1)
        return {"card": card, "title": t, "img": img}

    # ── Preparar ──────────────────────────────────────────────────────────
    def populate(self):
        for attr in ("a", "b"):
            combo = getattr(self, f"{attr}_combo")
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for f in self.win.uploaded_files:
                combo.addItem(("🔒 " if f.get("locked") else "") + f["name"], f["path"])
            combo.addItem(tr("Elegir desde el disco…"), "__browse__")
            if current and combo.findData(current) >= 0:
                combo.setCurrentIndex(combo.findData(current))
            combo.blockSignals(False)
        if self.win.uploaded_files:
            self.a_combo.setCurrentIndex(0)
            self.b_combo.setCurrentIndex(1 if len(self.win.uploaded_files) > 1 else 0)
        self.page_list.clear()
        self.summary.setText("")
        self._result = None
        self._clear_preview()

    def _clear_preview(self):
        for v in (self.view_a, self.view_diff, self.view_b):
            v["img"].setPixmap(QPixmap())
            v["img"].setText("")
        self.text_diff.setPlainText("")

    def _resolve_path(self, attr: str) -> str:
        combo = getattr(self, f"{attr}_combo")
        if combo.currentData() == "__browse__":
            p, _ = QFileDialog.getOpenFileName(self, tr("Elige un PDF"), str(Path.home()), "PDF (*.pdf)")
            if not p:
                return ""
            self.win.add_file(p, Path(p).name)
            self.populate()
            combo.setCurrentIndex(combo.findData(p))
            return p
        return combo.currentData() or ""

    # ── Comparar ──────────────────────────────────────────────────────────
    def _do_compare(self):
        if self._job is not None and self._job.isRunning():
            return
        path_a, path_b = self._resolve_path("a"), self._resolve_path("b")
        if not path_a or not path_b:
            self.win.snack(tr("Elige los dos archivos a comparar."), "error")
            return
        if path_a == path_b:
            self.win.snack(tr("Elige dos archivos distintos."), "error")
            return
        pw_a, pw_b = self.a_pw.text(), self.b_pw.text()
        self.summary.setText(tr("Comparando…"))
        self.bar.setRange(0, 0)
        job = _ToolJob(lambda cb: ptl.compare_pdfs(path_a, path_b, pw_a, pw_b))
        job.finished_ok.connect(self._on_compare_done)
        job.failed.connect(self._on_compare_failed)
        self._job = job
        job.start()

    def _on_compare_failed(self, msg: str):
        self.bar.setRange(0, 1); self.bar.setValue(0)
        self.summary.setText(msg)
        self.win.snack(msg, "error")

    def _on_compare_done(self, res: dict):
        self.bar.setRange(0, 1); self.bar.setValue(0)
        self._result = res
        if res["identical"]:
            self.summary.setText(tr("✓ Son idénticos: {n} páginas, sin ninguna diferencia.", n=res['n_a']))
        else:
            bits = [tr("{n} distinta(s)", n=res['diferente']) if res['diferente'] else None,
                    tr("{n} añadida(s)", n=res['añadida']) if res['añadida'] else None,
                    tr("{n} quitada(s)", n=res['quitada']) if res['quitada'] else None]
            self.summary.setText(tr("A tiene {n_a} páginas, B tiene {n_b}", n_a=res['n_a'], n_b=res['n_b']) +
                                 ". " + ", ".join(b for b in bits if b) + ".")
        self.page_list.clear()
        for pg in res["pages"]:
            item = QListWidgetItem(tr("Página {n} — {label}", n=pg['index'] + 1, label=STATUS_LABEL[pg['status']]))
            item.setForeground(QColor(STATUS_COLOR[pg["status"]]))
            self.page_list.addItem(item)
        if res["pages"]:
            self.page_list.setCurrentRow(0)
        self.win.snack(tr("Comparación hecha."), "success")

    def _show_page(self, row: int):
        if not self._result or row < 0 or row >= len(self._result["pages"]):
            self._clear_preview()
            return
        pg = self._result["pages"][row]
        path_a, path_b = self._resolve_path_cached()
        self._render_side(self.view_a, path_a, self.a_pw.text(), pg["index"] if pg["status"] != "añadida" else -1)
        self._render_side(self.view_b, path_b, self.b_pw.text(), pg["index"] if pg["status"] != "quitada" else -1)
        if pg.get("diff_image") and os.path.exists(pg["diff_image"]):
            pm = QPixmap(pg["diff_image"])
            self.view_diff["img"].setPixmap(pm.scaled(self.view_diff["img"].size(), Qt.KeepAspectRatio,
                                                       Qt.SmoothTransformation))
            self.view_diff["img"].setText("")
        else:
            self.view_diff["img"].setPixmap(QPixmap())
            self.view_diff["img"].setText(tr("Sin diferencias") if pg["status"] == "igual" else tr("No aplica"))
        if pg["status"] == "igual":
            self.text_diff.setPlainText("")
        else:
            import difflib
            diff = difflib.unified_diff((pg["text_a"] or "").splitlines(), (pg["text_b"] or "").splitlines(),
                                        fromfile="A", tofile="B", lineterm="")
            self.text_diff.setPlainText("\n".join(diff) or tr("(sin texto)"))

    def _resolve_path_cached(self):
        a = self.a_combo.currentData(); b = self.b_combo.currentData()
        return (a if a != "__browse__" else ""), (b if b != "__browse__" else "")

    def _render_side(self, view: dict, path: str, password: str, index: int):
        if not path or index < 0:
            view["img"].setPixmap(QPixmap())
            view["img"].setText(tr("No existe en este archivo"))
            return
        try:
            doc = ptl._open(path, password)
            page = doc[index]
            z = min((view["img"].width() - 8) / max(page.rect.width, 1),
                    (view["img"].height() - 8) / max(page.rect.height, 1))
            z = max(0.2, min(z, 3.0))
            pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
            qi = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            doc.close()
        except Exception:
            view["img"].setPixmap(QPixmap())
            view["img"].setText(tr("No se puede mostrar"))
            return
        view["img"].setPixmap(QPixmap.fromImage(qi))
        view["img"].setText("")
