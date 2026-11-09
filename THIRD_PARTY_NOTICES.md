# Avisos de terceros / Third-party notices

PDF Manager by Provecto se distribuye bajo **GNU AGPL-3.0** (ver `LICENSE`).
Utiliza los siguientes componentes de terceros, cada uno con su propia licencia:

| Componente | Uso | Licencia |
|---|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) (MuPDF, Artifex) | Lectura, edición y renderizado de PDF | AGPL-3.0 (o licencia comercial de Artifex) |
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | Interfaz gráfica | LGPL-3.0 |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) y datos `tessdata` (eng, spa, por) | OCR | Apache-2.0 |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) | OCR con redes neuronales (modelos incluidos) | Apache-2.0 |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Ejecución de modelos OCR | MIT |
| [OpenCV (headless)](https://opencv.org/) | Tratamiento de imagen | Apache-2.0 |
| [NumPy](https://numpy.org/) | Cálculo numérico | BSD-3-Clause |
| [Pillow](https://python-pillow.org/) | Imágenes | MIT-CMU |
| [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) | PDF a Word | MIT |
| [python-docx](https://github.com/python-openxml/python-docx) | Escritura de .docx | MIT |
| [openpyxl](https://openpyxl.readthedocs.io/) | Exportar tablas a Excel | MIT |
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) | Verificación de firmas digitales | MIT |
| [fontTools](https://github.com/fonttools/fonttools) | Lectura de fuentes | MIT |
| [pypdf](https://github.com/py-pdf/pypdf) | Utilidades PDF | BSD-3-Clause |
| [Requests](https://requests.readthedocs.io/) | Descargas | Apache-2.0 |
| [PyInstaller](https://pyinstaller.org/) | Empaquetado del ejecutable | GPL-2.0+ con excepción para programas distribuidos |

Qt (LGPL-3.0): los archivos de Qt se incluyen como bibliotecas dinámicas dentro de la carpeta
del programa, por lo que se pueden sustituir por otra versión compatible.

LibreOffice (opcional) no se incluye: si el usuario lo instala, la aplicación lo utiliza solo
como programa externo para convertir documentos de Office.

Los textos completos de cada licencia se encuentran en los repositorios enlazados.
