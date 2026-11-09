# -*- coding: utf-8 -*-
"""Formulario para reportar un error o enviar una sugerencia (sin enviar nada por su cuenta:
abre una issue de GitHub o un correo ya redactados, y el usuario decide)."""
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout,
)

import appinfo
import i18n
from i18n import tr
from ui.common import _btn

KINDS = ("error", "sugerencia")
MAX_TEXT = 4000


def build_report(kind: str, text: str, include_tech: bool) -> tuple[str, str]:
    """(título, cuerpo) del informe. Solo lleva lo que escribe el usuario y, si quiere, datos técnicos generales."""
    text = (text or "").strip()[:MAX_TEXT]
    label = tr("Error") if kind == "error" else tr("Sugerencia")
    first_line = text.splitlines()[0][:70] if text else ""
    title = f"[{label}] {first_line}".strip()
    body = text
    if include_tech:
        body += (f"\n\n---\n{appinfo.APP_NAME} {appinfo.APP_VERSION}\n"
                 f"{appinfo.system_summary()}\n{tr('Idioma')}: {i18n.LANG}")
    return title, body


def github_url(kind: str, text: str, include_tech: bool) -> str:
    title, body = build_report(kind, text, include_tech)
    labels = "bug" if kind == "error" else "enhancement"
    return f"{appinfo.ISSUES_NEW_URL}?title={quote(title)}&body={quote(body)}&labels={labels}"


def mailto_url(kind: str, text: str, include_tech: bool) -> str:
    title, body = build_report(kind, text, include_tech)
    return f"mailto:{appinfo.FEEDBACK_EMAIL}?subject={quote(title)}&body={quote(body)}"


class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Enviar comentarios"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)

        intro = QLabel(tr("Cuéntanos qué ha fallado o qué te gustaría que hiciera la aplicación. "
                          "Nunca se envían tus PDF ni su contenido: solo lo que escribas aquí."))
        intro.setObjectName("Hint")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.kind = QComboBox()
        self.kind.addItem(tr("Error"), "error")
        self.kind.addItem(tr("Sugerencia"), "sugerencia")
        lay.addWidget(self.kind)

        self.text = QPlainTextEdit()
        self.text.setPlaceholderText(tr("Describe el problema o la idea (qué hacías, qué esperabas y qué pasó)"))
        self.text.setMinimumHeight(140)
        self.text.textChanged.connect(self._refresh)
        lay.addWidget(self.text)

        self.tech = QCheckBox(tr("Incluir información técnica (versión, sistema operativo e idioma)"))
        self.tech.setChecked(True)
        self.tech.toggled.connect(self._refresh)
        lay.addWidget(self.tech)

        preview_lbl = QLabel(tr("Esto es lo que se enviará:"))
        preview_lbl.setObjectName("Hint")
        lay.addWidget(preview_lbl)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(110)
        lay.addWidget(self.preview)

        self.status = QLabel("")
        self.status.setObjectName("Hint")
        lay.addWidget(self.status)

        row = QHBoxLayout()
        cancel = _btn(tr("Cancelar"), None, "Flat")
        cancel.clicked.connect(self.reject)
        self.copy_btn = _btn(tr("Copiar texto"), "copy")
        self.copy_btn.clicked.connect(self._copy)
        self.mail_btn = _btn(tr("Enviar por correo"), "download")
        self.mail_btn.clicked.connect(lambda: self._open(mailto_url))
        self.mail_btn.setVisible(bool(appinfo.FEEDBACK_EMAIL))
        self.gh_btn = _btn(tr("Abrir en GitHub"), "link", "Primary")
        self.gh_btn.clicked.connect(lambda: self._open(github_url))
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(self.copy_btn)
        row.addWidget(self.mail_btn)
        row.addWidget(self.gh_btn)
        lay.addLayout(row)
        self._refresh()

    def _state(self):
        return self.kind.currentData(), self.text.toPlainText(), self.tech.isChecked()

    def _refresh(self):
        kind, text, tech = self._state()
        title, body = build_report(kind, text, tech)
        self.preview.setPlainText(f"{title}\n\n{body}" if text.strip() else "")
        has = bool(text.strip())
        for b in (self.copy_btn, self.mail_btn, self.gh_btn):
            b.setEnabled(has)

    def _open(self, make_url):
        kind, text, tech = self._state()
        QDesktopServices.openUrl(QUrl(make_url(kind, text, tech)))
        self.status.setText(tr("Se ha abierto tu navegador con el mensaje ya redactado: revísalo y envíalo."))

    def _copy(self):
        kind, text, tech = self._state()
        title, body = build_report(kind, text, tech)
        QGuiApplication.clipboard().setText(f"{title}\n\n{body}")
        self.status.setText(tr("Copiado al portapapeles."))
