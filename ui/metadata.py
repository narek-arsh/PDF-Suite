# -*- coding: utf-8 -*-
"""Pantalla Metadatos."""

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QComboBox,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

import backend as be
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import add_shadow, ask_scope, _ToolJob
from ui.widgets import BackHeader


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: METADATA
# ══════════════════════════════════════════════════════════════════════════
class MetadataPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self._job = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader(tr("Metadata – Ver / editar / borrar"), lambda: win.go_home()))

        self.file_row = QWidget()
        fr = QHBoxLayout(self.file_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.addWidget(QLabel(tr("Archivo:")))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._load_fields)
        fr.addWidget(self.file_combo, 1)
        root.addWidget(self.file_row)

        card = QFrame(); card.setObjectName("Card")
        add_shadow(card, blur=18, dy=4, alpha=70)
        c = QVBoxLayout(card)
        self.title_field    = self._field(tr("Título"))
        self.author_field   = self._field(tr("Autor"))
        self.subject_field  = self._field(tr("Asunto"))
        self.keywords_field = self._field(tr("Palabras clave"))
        self.creator_field  = self._field(tr("Creador (programa de origen)"))
        self.producer_field = self._field(tr("Productor (motor que generó el PDF)"))
        for w in (self.title_field, self.author_field, self.subject_field, self.keywords_field,
                  self.creator_field, self.producer_field):
            c.addWidget(w)

        dates_row = QHBoxLayout()
        self.creation_date_label = QLabel(tr("Creado: —"))
        self.creation_date_label.setObjectName("Hint")
        self.mod_date_label = QLabel(tr("Modificado: —"))
        self.mod_date_label.setObjectName("Hint")
        dates_row.addWidget(self.creation_date_label)
        dates_row.addWidget(self.mod_date_label)
        dates_row.addStretch(1)
        c.addLayout(dates_row)

        root.addWidget(card)

        btn_row = QHBoxLayout()
        save_btn = QPushButton(tr("Guardar cambios"))
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._do_save)
        clear_btn = QPushButton(tr("Borrar todos los metadatos"))
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
        self.file_row.setVisible(len(self.win.uploaded_files) > 1)
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
            tr("Creado: {d}", d=be.format_pdf_date(meta.get('creationDate', ''))))
        self.mod_date_label.setText(
            tr("Modificado: {d}", d=be.format_pdf_date(meta.get('modDate', ''))))

    def _targets(self, scope: str) -> list:
        if scope == "all":
            return list(self.win.uploaded_files)
        f = self._selected_file()
        return [f] if f else []

    def _run_batch(self, targets: list, call, start_msg: str, ok_label: str):
        job = _ToolJob(lambda cb: [(f, call(f)) for f in targets])
        self.win.snack(start_msg, "info")

        def done(results):
            oks = [f for f, out in results if out]
            fails = [f for f, out in results if not out]
            for f, out in results:
                if out:
                    self.win.replace_file(f, out)
            self.populate()
            msg = (tr("✓ {ok_label} en {n} archivo{s}.", ok_label=ok_label, n=len(oks),
                      s=('s' if len(oks) != 1 else ''))
                  if oks else tr("No se pudo en ningún archivo."))
            if fails:
                msg += tr(" ({n} con error)", n=len(fails))
            self.win.snack(msg, "success" if oks and not fails else ("error" if not oks else "info"))

        def failed(msg):
            self.win.snack(msg, "error")
        job.finished_ok.connect(done)
        job.failed.connect(failed)
        self._job = job
        job.start()

    def _do_save(self):
        if not self._selected_file():
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        scope = ask_scope(self, self.win, self._selected_file()["name"])
        if not scope:
            return
        meta = {
            "title": self.title_field.text(),
            "author": self.author_field.text(),
            "subject": self.subject_field.text(),
            "keywords": self.keywords_field.text(),
            "creator": self.creator_field.text(),
            "producer": self.producer_field.text(),
        }

        def call(f):
            out = be.write_metadata(f["path"], meta)
            if out:
                orig = be.read_metadata(f["path"])
                changed = {k: v for k, v in meta.items() if (orig.get(k) or "") != v}
                if changed:
                    self.win.record_step("metadata", changed)
            return out
        self._run_batch(self._targets(scope), call, tr("Guardando metadatos…"), tr("Metadatos guardados"))

    def _do_clear(self):
        if not self._selected_file():
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        scope = ask_scope(self, self.win, self._selected_file()["name"])
        if not scope:
            return

        def call(f):
            out = be.clear_metadata(f["path"])
            if out:
                self.win.record_step("metadata_clear")
            return out
        self._run_batch(self._targets(scope), call, tr("Eliminando metadatos…"), tr("Metadatos eliminados"))
