# -*- mode: python ; coding: utf-8 -*-
# PDF Manager – Travel Agent Edition
# Ejecutar con:  pyinstaller PDF.spec

import sys
from pathlib import Path

block_cipher = None

# ── Archivos extra que el exe necesita en tiempo de ejecución ────────────────
added_files = [
    # Fuente Myriad Pro  (origen, destino dentro del bundle)
    (str(Path("Font") / "MYRIADPRO-REGULAR.OTF"), "Font"),
    # Icono de la ventana
    ("icono.ico", "."),
]

a = Analysis(
    ["PDF.py"],
    pathex=["."],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        # Drag & Drop
        "tkinterdnd2",
        # Flet internals
        "flet",
        "flet.fastapi",
        "flet_core",
        "flet_runtime",
        # PDF libs
        "pypdf",
        "pypdf._reader",
        "pypdf._writer",
        "fitz",
        "pdfplumber",
        "pdfminer",
        "pdfminer.high_level",
        "pdfminer.layout",
        # Otros
        "requests",
        "urllib3",
        "charset_normalizer",
        "certifi",
        "PIL",
        "PIL.Image",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # ← sin ventana de terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icono.ico",       # ← icono de la app
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PDFManager",      # carpeta en dist/
)
