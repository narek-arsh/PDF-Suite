# -*- coding: utf-8 -*-
"""Lanzador: abre la versión actual (PySide6) de PDF Manager."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _selftest(report_path: str) -> int:
    """Comprobación del paquete (usada para verificar el .exe): importa todo lo que la app carga bajo demanda
    y escribe el resultado en `report_path`."""
    import tempfile
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    lines, ok = [], True

    def check(name, fn):
        nonlocal ok
        try:
            lines.append(f"OK   {name}: {fn() or ''}")
        except Exception as e:
            ok = False
            lines.append(f"FAIL {name}: {type(e).__name__}: {e}")

    check("interfaz", lambda: __import__("pdf_qt").MainWindow.__name__)
    for mod in ("cv2", "onnxruntime", "pdf2docx", "docx", "openpyxl", "fontTools", "pyhanko.sign.validation",
                "pypdf", "requests"):
        check(f"import {mod}", lambda m=mod: __import__(m).__name__)

    def tess():
        import pdf_tools as ptl
        dirs = [str(d) for d in ptl.tessdata_dirs() if (d / "spa.traineddata").is_file()]
        assert dirs, "no se encuentra spa.traineddata"
        return dirs[0]
    check("tessdata", tess)

    def rapid():
        from rapidocr import RapidOCR
        RapidOCR()
        return "modelos cargados"
    check("RapidOCR", rapid)

    def render_and_word():
        import fitz
        import pdf_tools as ptl
        tmp = tempfile.mkdtemp(prefix="selftest_")
        ptl.DOWNLOADS = __import__("pathlib").Path(tmp)   # no escribir en las Descargas del usuario
        src = os.path.join(tmp, "t.pdf")
        d = fitz.open()
        d.new_page().insert_text((72, 100), "Prueba de paquete")
        d.save(src)
        d.close()
        out = ptl.pdf_to_word(src) if hasattr(ptl, "pdf_to_word") else None
        return f"pdf_to_word -> {os.path.basename(str(out))}" if out else "ok"
    check("PDF a Word", render_and_word)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\nRESULTADO: OK\n" if ok else "\nRESULTADO: FALLO\n"))
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        from PySide6.QtWidgets import QApplication
        _app = QApplication([])
        sys.exit(_selftest(sys.argv[2]))
    from pdf_qt import main
    main()
