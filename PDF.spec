# -*- mode: python ; coding: utf-8 -*-
# PDF Manager by Provecto
# Ejecutar con:  pyinstaller PDF.spec --noconfirm

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas = [
    ("tessdata", "tessdata"),                 # idiomas de OCR (pdf_tools.tessdata_dirs busca en _MEIPASS/tessdata)
    ("provecto_icon.ico", "."),
    ("provecto_logo.svg", "."),
    ("click_icons.svg", "."),
    ("LICENSE", "."),                         # AGPL-3.0: se distribuye junto al programa
    ("THIRD_PARTY_NOTICES.md", "."),
]
binaries = []
hiddenimports = [
    "i18n", "theme", "backend", "pdf_tools", "layout_tools", "numfix", "photo_fix",
    "workflows", "draft", "click_icons", "stamp_tool", "signature_pad", "form_tools",
    "fontmanager", "winfonts", "annot_tools", "icons", "flow_layout",
    "ui.home", "ui.tools", "ui.edit_page", "ui.editor_view", "ui.editor_parts", "ui.ocr",
    "ui.organize", "ui.split", "ui.metadata", "ui.size_nup", "ui.compare", "ui.pick",
    "ui.ajuste", "ui.workflows_ui", "ui.widgets", "ui.common",
]

# Paquetes con datos/modelos/imports dinámicos: se recogen enteros (si falta alguno, se avisa y se sigue).
for pkg in ("rapidocr", "onnxruntime", "pdf2docx", "pyhanko", "pyhanko_certvalidator",
            "fitz", "pymupdf", "docx", "openpyxl", "fontTools", "certifi"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:
        print(f"[spec] aviso: no se pudo recoger {pkg}: {e}")

a = Analysis(
    ["PDF.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pandas", "scipy", "IPython", "pytest", "flet",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtNetworkAuth",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # UPX rompe DLLs de Qt y dispara antivirus
    console=False,            # sin ventana de terminal
    disable_windowed_traceback=False,
    icon="provecto_icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PDFManager",        # carpeta dist/PDFManager/
)
