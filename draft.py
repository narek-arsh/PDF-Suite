"""Borrador automático del documento que se está editando, guardado en la carpeta temporal.

Sirve para dos cosas: recuperar el trabajo si la aplicación se cierra de golpe, y reabrir el mismo documento al
reiniciar la aplicación (p. ej. tras instalar una fuente)."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path


def folder() -> Path:
    d = Path(tempfile.gettempdir()) / "PDFManager_borrador"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _paths() -> tuple[Path, Path]:
    d = folder()
    return d / "borrador.pdf", d / "borrador.json"


def save(doc, name: str, restart: bool = False, dirty: bool = True) -> bool:
    """Guarda el estado actual del documento. Devuelve False si no se pudo (no es grave)."""
    try:
        pdf, meta = _paths()
        tmp = pdf.with_suffix(".tmp")
        doc.save(str(tmp), garbage=0, deflate=True)
        tmp.replace(pdf)
        meta.write_text(json.dumps({"name": name, "restart": bool(restart), "dirty": bool(dirty), "time": time.time()}),
                        encoding="utf-8")
        return True
    except Exception:
        return False


def load() -> dict | None:
    """{'path', 'name', 'restart', 'time'} del borrador pendiente, o None."""
    try:
        pdf, meta = _paths()
        if not pdf.is_file() or not meta.is_file():
            return None
        info = json.loads(meta.read_text(encoding="utf-8"))
        info["path"] = str(pdf)
        return info
    except Exception:
        return None


def clear() -> None:
    try:
        for p in _paths():
            p.unlink(missing_ok=True)
        (folder() / "borrador.tmp").unlink(missing_ok=True)
    except Exception:
        pass
