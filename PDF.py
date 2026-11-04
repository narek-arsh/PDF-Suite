# -*- coding: utf-8 -*-
"""Lanzador: abre la versión actual (PySide6) de PDF Manager.
La versión antigua en Flet está en PDF_flet_antiguo.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_qt import main

if __name__ == "__main__":
    main()
