# -*- coding: utf-8 -*-
"""
fontmanager.py — Detecta las fuentes de un PDF que no están instaladas y las descarga
de Google Fonts, instalándolas solo en el programa o también en Windows (solo para el
usuario actual: no hace falta ser administrador).

Solo se ofrecen fuentes que Google publica con licencia libre. Las de Microsoft, Adobe o
de pago (Arial, Calibri, Helvetica…) no se pueden descargar: ahí se usa la más parecida.
Sin dependencias de interfaz.
"""
import ctypes
import json
import os
import re
import shutil
from pathlib import Path

import requests

import winfonts

UA = {"User-Agent": "PDFManager/1.0 (descarga de fuentes pedida por el usuario)"}
LIST_URL = "https://fonts.google.com/download/list"
MAX_FILE_BYTES = 25 * 1024 * 1024            # tope por archivo de fuente
BASIC_STYLES = {"regular", "bold", "italic", "bolditalic"}

# Fuentes que todo lector de PDF trae (las 14 estándar) y fuentes de símbolos: no se descargan.
_BASE14 = re.compile(r"^(helvetica|times|courier)(-|,|$)|^(symbol|zapfdingbats)")
_SYMBOLS = ("symbol", "wingdings", "webdings", "zapfdingbats", "dingbats", "marlett")

# Fuentes de Microsoft que no se pueden descargar, con su sustituta libre de Google Fonts de
# MEDIDAS IDÉNTICAS: el texto ocupa lo mismo y no se descoloca.
SUBSTITUTES = winfonts.SUBSTITUTES


def strip_subset(ps_name: str) -> str:
    """«ABCDEE+Calibri» → «Calibri»."""
    name = ps_name or ""
    if "+" in name and len(name.split("+")[0]) == 6:
        name = name.split("+", 1)[1]
    return name


def _camel_split(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)).strip()


def family_candidates(ps_name: str) -> list[str]:
    """Nombres de familia posibles a partir del nombre PostScript («OpenSans-Bold» → «Open Sans»)."""
    base = strip_subset(ps_name)
    head = base.split("-")[0].split(",")[0]
    head = re.sub(r"(PSMT|MT|PS)$", "", head)
    out = []
    for cand in (_camel_split(head), winfonts.guess_family_from_ps_name(base), head):
        cand = cand.strip()
        if cand and "-" not in cand and cand not in out:
            out.append(cand)
    return out


def style_token(ps_name: str) -> str:
    """Parte de estilo del nombre PostScript («Montserrat-SemiBold» → «semibold»)."""
    base = strip_subset(ps_name)
    if "-" not in base:
        return "regular"
    tok = base.split("-", 1)[1].lower().replace(" ", "")
    return re.sub(r"(psmt|mt)$", "", tok) or "regular"


def is_text_font(ps_name: str) -> bool:
    low = strip_subset(ps_name).lower()
    return not (_BASE14.match(low) or any(low.startswith(s) for s in _SYMBOLS))


def document_fonts(doc) -> list[dict]:
    """Fuentes de texto que usa un PDF: {ps, family, style, embedded, installed}."""
    seen: dict[str, dict] = {}
    try:
        for i in range(doc.page_count):
            for _xref, ext, _typ, base, _ref, _enc in doc.get_page_fonts(i):
                name = strip_subset(base)
                if not name or name in seen or not is_text_font(name):
                    continue
                installed = winfonts.find_font_file(name)[0] is not None
                seen[name] = {"ps": name, "family": family_candidates(name)[0], "style": style_token(name),
                              "embedded": ext != "n/a", "installed": installed}
    except Exception:
        pass
    return list(seen.values())


def missing_fonts(doc) -> list[dict]:
    """Las fuentes de texto del PDF que no están instaladas, agrupadas por familia."""
    groups: dict[str, dict] = {}
    for f in document_fonts(doc):
        if f["installed"]:
            continue
        g = groups.setdefault(f["family"], {"family": f["family"], "candidates": family_candidates(f["ps"]),
                                            "styles": set(), "ps_names": [], "embedded": True})
        g["styles"].add(f["style"])
        g["ps_names"].append(f["ps"])
        g["embedded"] = g["embedded"] and f["embedded"]
    return list(groups.values())


# ── Google Fonts ──────────────────────────────────────────────────────────
def google_lookup(family: str) -> dict | None:
    """Archivos estáticos de una familia en Google Fonts, o None si no existe allí.
    Devuelve {family, files: [{name, url}]}. Lanza OSError si no hay conexión."""
    try:
        r = requests.get(LIST_URL, params={"family": family}, headers=UA, timeout=20)
    except requests.RequestException as e:
        raise OSError(str(e)) from e
    if r.status_code != 200:
        return None
    text = r.text
    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]
    try:
        refs = json.loads(text).get("manifest", {}).get("fileRefs", [])
    except ValueError:
        return None
    ttf = [x for x in refs if str(x.get("filename", "")).lower().endswith(".ttf") and x.get("url")]
    static = [x for x in ttf if x["filename"].startswith("static/")]
    chosen = static or ttf
    if not chosen:
        return None
    return {"family": family,
            "files": [{"name": os.path.basename(x["filename"]), "url": x["url"]} for x in chosen]}


def find_on_google(candidates: list[str]) -> dict | None:
    for cand in candidates:
        info = google_lookup(cand)
        if info:
            return info
    return None


def pick_files(info: dict, wanted_styles: set) -> list[dict]:
    """De todos los estilos de la familia, los cuatro básicos y los que pide el PDF. Se omiten las
    variantes de anchura («OpenSans_Condensed-Bold»)."""
    wanted = {s.lower() for s in wanted_styles} | BASIC_STYLES
    out = []
    for f in info["files"]:
        fam, _, style = f["name"][:-4].partition("-")
        if "_" in fam:
            continue
        if style.lower().replace(" ", "") in wanted:
            out.append(f)
    return out or info["files"][:4]


def _looks_like_font(data: bytes) -> bool:
    return data[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO", b"ttcf")


def download_family(info: dict, wanted_styles: set, progress=None, dest_root: Path | None = None) -> list[Path]:
    """Descarga los estilos necesarios a la carpeta de fuentes del programa y devuelve las rutas."""
    files = pick_files(info, wanted_styles)
    dest = (dest_root or winfonts.app_fonts_dir()) / re.sub(r"[^a-z0-9]+", "", info["family"].lower())
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, f in enumerate(files):
        if progress:
            progress(i, len(files), f["name"])
        try:
            r = requests.get(f["url"], headers=UA, timeout=60, stream=True)
            r.raise_for_status()
            data = b""
            for chunk in r.iter_content(65536):
                data += chunk
                if len(data) > MAX_FILE_BYTES:
                    raise OSError("el archivo es demasiado grande")
        except requests.RequestException as e:
            raise OSError(str(e)) from e
        if not _looks_like_font(data):
            raise OSError(f"«{f['name']}» no es un archivo de fuente válido")
        target = dest / f["name"]
        target.write_bytes(data)
        paths.append(target)
    if progress:
        progress(len(files), len(files), "")
    winfonts.refresh_installed_fonts()
    return paths


# ── Instalación en Windows (solo el usuario actual) ───────────────────────
def _full_name(path: Path) -> str:
    try:
        from fontTools.ttLib import TTFont
        name = TTFont(str(path), lazy=True)["name"].getDebugName(4)
        if name:
            return name
    except Exception:
        pass
    return path.stem


def install_in_windows(paths: list[Path], dest_dir: Path | None = None, key_path: str | None = None) -> int:
    """Copia las fuentes a la carpeta de fuentes del usuario y las registra para que Windows (y
    cualquier programa) las vea. No pide permisos de administrador. Devuelve cuántas instaló."""
    import winreg
    real = dest_dir is None and key_path is None
    dest = dest_dir or Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
    dest.mkdir(parents=True, exist_ok=True)
    key = key_path or r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
    n = 0
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
        for p in paths:
            target = dest / p.name
            shutil.copy2(p, target)
            winreg.SetValueEx(k, f"{_full_name(p)} (TrueType)", 0, winreg.REG_SZ, str(target))
            if real:
                ctypes.windll.gdi32.AddFontResourceW(str(target))
            n += 1
    if real:
        try:                                            # avisa a los programas abiertos (WM_FONTCHANGE)
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 2, 1000, None)
        except Exception:
            pass
    winfonts.refresh_installed_fonts()
    return n
