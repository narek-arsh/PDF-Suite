# PDF Manager by Provecto

Aplicación de escritorio para trabajar con PDF sin subir nada a internet: unir, dividir,
organizar, editar, comparar, comprimir, proteger, marca de agua, numerar páginas, OCR,
conversión desde/hacia PDF, verificación de firmas y más. Interfaz en español, inglés y portugués,
con modo claro y oscuro.

Más información: <https://provecto.app>

## Ejecutar desde el código

Requiere Python 3.12 o superior.

```bash
pip install PySide6 PyMuPDF pillow numpy opencv-python-headless rapidocr onnxruntime \
            pdf2docx python-docx openpyxl pyhanko fonttools pypdf requests
python PDF.py
```

## Crear el ejecutable de Windows

```bash
pip install pyinstaller
pyinstaller PDF.spec --noconfirm
```

El resultado queda en `dist/PDFManager/`.

## Licencia

Copyright (C) 2026 Provecto.

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la
**GNU Affero General Public License v3.0** (ver [LICENSE](LICENSE)). Se distribuye sin ninguna
garantía. El código fuente de la versión distribuida está disponible en este repositorio:
<https://github.com/provecto-app/PDF-Manager>.

Los componentes de terceros y sus licencias están en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
