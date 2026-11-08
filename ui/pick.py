# -*- coding: utf-8 -*-
"""Pantalla «Elige un archivo»: se llega a ella al pulsar una herramienta sin tener todavía los PDFs necesarios."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import pdf_tools as ptl
from ui.common import _btn
from ui.widgets import BackHeader, DropArea


class PickFilePage(QWidget):
    """Pide los archivos que faltan para la herramienta elegida y, cuando están, la abre sola."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(BackHeader("", self._back))
        self.title = QLabel("")
        self.title.setObjectName("Header")
        root.addWidget(self.title)
        self.msg = QLabel("")
        self.msg.setObjectName("Hint")
        self.msg.setWordWrap(True)
        root.addWidget(self.msg)
        self.drop = DropArea(lambda paths: self.win.add_files_any(paths))
        root.addWidget(self.drop, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        pick = _btn("Elegir archivos…", "clip", "Primary")
        pick.clicked.connect(self._browse)
        row.addWidget(pick)
        row.addStretch(1)
        root.addLayout(row)

    def show_for(self, title: str, minimum: int):
        have = len(self.win.uploaded_files)
        self.title.setText(title)
        if minimum <= 1:
            self.msg.setText("Esta herramienta trabaja sobre un PDF. Súbelo aquí y se abrirá en cuanto esté cargado.")
        else:
            falta = minimum - have
            self.msg.setText(f"Hacen falta al menos {minimum} PDFs. Tienes {have}: añade {falta} más y se abrirá "
                             "en cuanto estén cargados.")

    def _browse(self):
        exts = " ".join("*" + e for e in sorted(ptl.accepted_extensions()))
        paths, _ = QFileDialog.getOpenFileNames(self, "Elegir PDFs o fotos", "",
                                                f"PDF y fotos ({exts});;Todos los archivos (*.*)")
        if paths:
            self.win.add_files_any(paths)

    def _back(self):
        self.win.cancel_pending()
        self.win.go_home()
