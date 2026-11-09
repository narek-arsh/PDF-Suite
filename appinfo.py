# -*- coding: utf-8 -*-
"""Datos de la aplicación y de dónde recibir comentarios."""
import platform
import sys

APP_NAME = "PDF Manager by Provecto"
APP_VERSION = "1.0.0"
REPO_URL = "https://github.com/provecto-app/PDF-Manager"
ISSUES_NEW_URL = REPO_URL + "/issues/new"
FEEDBACK_EMAIL = ""      # si se rellena, el formulario ofrece también «Enviar por correo»


def system_summary() -> str:
    packaged = "exe" if getattr(sys, "frozen", False) else "código fuente"
    return f"{platform.system()} {platform.release()} ({platform.machine()}) · Python {platform.python_version()} · {packaged}"
