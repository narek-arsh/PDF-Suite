# -*- coding: utf-8 -*-
"""
workflows.py — Pasos encadenables ("macros"): modelo, ejecución y guardado.
Sin dependencias de UI. Un workflow es una lista de pasos; cada paso es
{"type": ..., "params": {...}, "ask": [nombres de parámetros a preguntar al
ejecutar]}. Cada paso toma un PDF y devuelve otro, así que se encadenan.
"""
import json
import os
import uuid
from pathlib import Path

import backend as be

# Parámetros de texto que se pueden marcar como "preguntar al ejecutar".
PROMPTABLE: dict[str, dict[str, str]] = {
    "find_replace": {"buscar": "Buscar", "reemplazar": "Reemplazar por"},
    "censor": {"texto": "Texto a censurar"},
    "metadata": {"title": "Título", "author": "Autor", "subject": "Asunto",
                 "keywords": "Palabras clave", "creator": "Creador", "producer": "Productor"},
}

STEP_LABELS = {
    "merge": "Unir archivos",
    "resize": "Tamaño de página",
    "margins": "Márgenes",
    "nup": "N-Up",
    "adjust": "Ajuste de imagen",
    "find_replace": "Buscar y reemplazar",
    "censor": "Censurar texto",
    "metadata": "Metadatos",
    "metadata_clear": "Borrar metadatos",
}


def new_step(step_type: str, params: dict | None = None) -> dict:
    return {"type": step_type, "params": dict(params or {}), "ask": []}


def _q(text: str) -> str:
    return f"«{text}»"


def describe(step: dict) -> str:
    """Texto corto y legible del paso, para listas y la barra de pasos."""
    t, p, ask = step["type"], step.get("params", {}), set(step.get("ask", []))

    def val(name: str) -> str:
        return "«?»" if name in ask else _q(p.get(name, ""))

    if t == "merge":
        return "Unir archivos"
    if t == "resize":
        size = p.get("size_name", "A4")
        if size == "Personalizado":
            size = f"{p.get('custom_w_mm', 0):g}×{p.get('custom_h_mm', 0):g} mm"
        modo = "escalar" if p.get("fit_mode", "scale") == "scale" else "centrar"
        return f"Tamaño {size} ({modo})"
    if t == "margins":
        return ("Márgenes mm: arriba {top_mm:g}, abajo {bottom_mm:g}, "
                "izq. {left_mm:g}, der. {right_mm:g}").format(**{
                    k: p.get(k, 0) for k in ("top_mm", "bottom_mm", "left_mm", "right_mm")})
    if t == "nup":
        gap = p.get("gap_mm")
        ori = {"portrait": "vertical", "landscape": "horizontal"}.get(p.get("orientation", "auto"), "orientación auto")
        giro = "girando páginas" if p.get("auto_rotate", True) else "sin girar"
        return (f"N-Up {p.get('cols', 2)}×{p.get('rows', 2)} en {p.get('size_name', 'A4')} {ori}"
                f" (espacio {'auto' if gap is None else f'{gap:g} mm'}, {giro})")
    if t == "adjust":
        pages = p.get("pages")
        donde = (" (página " if len(pages or []) == 1 else " (páginas ") + ", ".join(
            str(i + 1) for i in pages) + ")" if pages else ""
        if p.get("bw"):
            return (f"Ajuste{donde}: blanco y negro (brillo {p.get('brillo', 0):+.2f}, "
                    f"contraste {p.get('contraste', 1):.2f})")
        return (f"Ajuste{donde}: brillo {p.get('brillo', 0):+.2f}, contraste {p.get('contraste', 1):.2f}, "
                f"saturación {p.get('saturacion', 1):.2f}")
    if t == "find_replace":
        return f"Buscar {val('buscar')} → {val('reemplazar')}"
    if t == "censor":
        return f"Censurar {val('texto')}"
    if t == "metadata":
        shown = [f"{PROMPTABLE['metadata'][k].lower()} " + ("vacío" if k not in ask and not p[k] else val(k))
                 for k in PROMPTABLE["metadata"] if k in p]
        return "Metadatos: " + (", ".join(shown) if shown else "sin cambios")
    if t == "metadata_clear":
        return "Borrar todos los metadatos"
    return STEP_LABELS.get(t, t)


def summarize(steps: list[dict]) -> str:
    return "  →  ".join(describe(s) for s in steps)


def steps_key(steps: list[dict]) -> str:
    """Huella de los pasos (tipo + parámetros; 'preguntar' no cuenta)."""
    return json.dumps([[s["type"], s.get("params", {})] for s in steps],
                      sort_keys=True, ensure_ascii=False, default=str)


def find_duplicate(steps: list[dict], workflows: list[dict]) -> dict | None:
    key = steps_key(steps)
    return next((w for w in workflows if steps_key(w["steps"]) == key), None)


def prompt_fields(steps: list[dict]) -> list[tuple[int, str, str]]:
    """(índice de paso, parámetro, etiqueta) de todo lo que hay que preguntar."""
    fields = []
    for i, s in enumerate(steps):
        for name in s.get("ask", []):
            label = PROMPTABLE.get(s["type"], {}).get(name, name)
            fields.append((i, name, label))
    return fields


# ── Ejecución ─────────────────────────────────────────────────────────────
def _run_step(step: dict, path: str, values: dict) -> tuple[str | None, str | None]:
    """Devuelve (ruta_salida, aviso). Sin salida y con aviso = paso omitido
    (p.ej. el texto a reemplazar no está en ese archivo); sin ambos = error."""
    t = step["type"]
    p = dict(step.get("params", {}))
    p.update(values)
    if t == "resize":
        return be.resize_pdf(path, p.get("size_name", "A4"), p.get("fit_mode", "scale"),
                              p.get("custom_w_mm"), p.get("custom_h_mm")), None
    if t == "margins":
        return be.adjust_margins_pdf(path, p.get("top_mm", 0), p.get("bottom_mm", 0),
                                      p.get("left_mm", 0), p.get("right_mm", 0)), None
    if t == "nup":
        return be.n_up_pdf(path, p.get("cols", 2), p.get("rows", 2), p.get("size_name", "A4"),
                            p.get("custom_w_mm"), p.get("custom_h_mm"), p.get("gap_mm"),
                            p.get("orientation", "auto"), bool(p.get("auto_rotate", True))), None
    if t == "adjust":
        pages = p.get("pages")
        warn = None
        if pages:
            total = be.safe_page_count(path)
            valid = [i for i in pages if 0 <= i < total]
            if not valid:
                return None, f"el archivo solo tiene {total} página(s)"
            if len(valid) < len(pages):
                warn = f"el archivo solo tiene {total} página(s); ajusté las que existen"
            pages = valid
        out = be.apply_adjustment_to_pdf(path, p.get("brillo", 0.0), p.get("contraste", 1.0),
                                          p.get("saturacion", 1.0), bool(p.get("bw", False)),
                                          pages=pages or None)
        return out, warn
    if t == "find_replace":
        out = be.find_replace_in_pdf(path, p.get("buscar", ""), p.get("reemplazar", ""))
        if out:
            return out, None
        return None, f"no encontré {_q(p.get('buscar', ''))}"
    if t == "censor":
        out = be.censor_text_in_pdf(path, p.get("texto", ""))
        if out:
            return out, None
        return None, f"no encontré {_q(p.get('texto', ''))}"
    if t == "metadata":
        meta = {k: p[k] for k in PROMPTABLE["metadata"] if k in p}
        return be.write_metadata(path, meta), None
    if t == "metadata_clear":
        return be.clear_metadata(path), None
    return None, None


def _discard(path: str | None, created: set, originals: set):
    """Borra un intermedio que creamos nosotros (nunca un archivo original)."""
    if path and path in created and path not in originals:
        try:
            Path(path).unlink()
        except OSError:
            pass


def run_workflow(steps: list[dict], input_paths: list[str],
                 values: dict[int, dict] | None = None, progress=None) -> tuple[list[str], list[str]]:
    """Ejecuta los pasos sobre cada archivo (el paso 'merge' los une en uno).
    Devuelve (rutas finales, avisos). Solo se conservan los resultados
    finales: los PDF intermedios se borran."""
    values = values or {}
    originals = set(input_paths)
    created: set[str] = set()
    current: list[str | None] = list(input_paths)
    names = {p: Path(p).name for p in input_paths}
    warnings: list[str] = []
    total = len(steps)

    for si, step in enumerate(steps):
        label = describe(step)
        if progress:
            progress(si, total, label)
        if step["type"] == "merge":
            paths = [c for c in current if c]
            if len(paths) < 2:
                continue
            dest = str(be.DOWNLOADS / f"{Path(paths[0]).stem}_Merged.pdf")
            be.merge_pdfs(paths, dest)
            for c in paths:
                _discard(c, created, originals)
            created.add(dest)
            current = [dest]
            continue
        nxt: list[str | None] = []
        for c in current:
            if not c:
                nxt.append(None)
                continue
            out, warn = _run_step(step, c, values.get(si, {}))
            name = names.get(c, Path(c).name)
            if out:
                created.add(out)
                names[out] = name
                _discard(c, created, originals)
                nxt.append(out)
                if warn:
                    warnings.append(f"{name}: paso «{label}»: {warn}")
            elif warn:
                warnings.append(f"{name}: paso «{label}» omitido ({warn})")
                nxt.append(c)
            else:
                warnings.append(f"{name}: falló el paso «{label}»")
                _discard(c, created, originals)
                nxt.append(None)
        current = nxt
    if progress:
        progress(total, total, "Terminado")
    return [c for c in current if c], warnings


# ── Guardado (JSON en %APPDATA%\PDFManager) ───────────────────────────────
def storage_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "PDFManager" / "workflows.json"


def load_workflows(path: Path | None = None) -> list[dict]:
    path = path or storage_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [w for w in data if isinstance(w, dict) and w.get("steps")]
    except (OSError, ValueError):
        return []


def save_workflows(workflows: list[dict], path: Path | None = None) -> bool:
    path = path or storage_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(workflows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def new_workflow(name: str, steps: list[dict]) -> dict:
    return {"id": uuid.uuid4().hex, "name": name.strip(), "steps": steps}
