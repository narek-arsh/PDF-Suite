# -*- coding: utf-8 -*-
"""Lanzador: abre la versión actual (PySide6) de PDF Manager."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_qt import main

if __name__ == "__main__":
    main()
