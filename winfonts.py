# -*- coding: utf-8 -*-
"""
winfonts.py — Localiza fuentes instaladas en Windows (registro del sistema)
y empareja el nombre PostScript de una fuente de un PDF (p.ej. "ArialMT",
"TimesNewRomanPS-BoldMT") con el archivo .ttf/.otf instalado más parecido,
para poder insertar texto nuevo respetando la fuente original del PDF.

No descarga ni instala nada: solo lee lo que ya está instalado.
"""
import os
import re
from functools import lru_cache
from pathlib import Path

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

def app_fonts_dir() -> Path:
    """Carpeta de fuentes del programa (descargadas desde él, sin tocar Windows)."""
    return Path(os.environ.get("APPDATA") or Path.home()) / "PDFManager" / "fonts"


# Fuente de Microsoft → sustituta libre (Google Fonts) con las mismas medidas.
SUBSTITUTES = {"calibri": "Carlito", "cambria": "Caladea", "arial": "Arimo", "helvetica": "Arimo",
               "times new roman": "Tinos", "courier new": "Cousine", "georgia": "Gelasio"}

FONTS_DIR = Path(r"C:\Windows\Fonts")
LOCAL_FONTS_DIR = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"


def _read_registry_fonts(hive, subkey: str) -> dict[str, str]:
    result = {}
    if not HAS_WINREG:
        return result
    try:
        with winreg.OpenKey(hive, subkey) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                clean = re.sub(r"\s*\((TrueType|OpenType)\)\s*$", "", name).strip()
                result[clean.lower()] = value
    except OSError:
        pass
    return result


def _font_keys(path: Path) -> set[str]:
    """Nombres con los que se puede pedir un archivo de fuente («open sans», «open sans bold»…)."""
    keys: set[str] = set()
    try:
        from fontTools.ttLib import TTFont
        n = TTFont(str(path), lazy=True, fontNumber=0)["name"]
        for fam, sub in ((n.getDebugName(16), n.getDebugName(17)), (n.getDebugName(1), n.getDebugName(2))):
            if not fam:
                continue
            sl = (sub or "").lower()
            style = "bold italic" if ("bold" in sl and "italic" in sl) else "bold" if "bold" in sl                 else "italic" if "italic" in sl else ""
            keys.add((fam + (" " + style if style else "")).lower())
            if sl and sl not in ("regular", "bold", "italic", "bold italic"):
                keys.add(f"{fam} {sub}".lower())          # «Open Sans SemiBold»
        if n.getDebugName(4):
            keys.add(n.getDebugName(4).lower())
    except Exception:
        pass
    if not keys:                                           # sin fontTools: por el nombre del archivo
        fam, _, style = path.stem.partition("-")
        fam = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", fam).lower()
        sl = style.lower()
        suffix = " bold italic" if ("bold" in sl and "italic" in sl) else " bold" if "bold" in sl             else " italic" if "italic" in sl else ""
        keys.add(fam + suffix)
    return keys


def _scan_app_fonts() -> dict[str, str]:
    out: dict[str, str] = {}
    root = app_fonts_dir()
    if root.is_dir():
        for p in sorted(root.rglob("*.ttf")):
            for k in _font_keys(p):
                out.setdefault(k, str(p))
    return out


@lru_cache(maxsize=1)
def list_installed_fonts() -> dict[str, str]:
    """nombre de familia en minúsculas -> ruta absoluta del archivo de fuente.
    Se cachea: el registro solo se lee una vez por sesión del programa
    ('precargar las fuentes de Windows')."""
    fonts: dict[str, str] = {}
    if not HAS_WINREG:
        return fonts

    sys_fonts = _read_registry_fonts(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
    for name, fname in sys_fonts.items():
        path = Path(fname)
        if not path.is_absolute():
            path = FONTS_DIR / fname
        if path.is_file():
            fonts[name] = str(path)

    for key, path in _scan_app_fonts().items():       # fuentes descargadas por el programa
        fonts.setdefault(key, path)

    user_fonts = _read_registry_fonts(
        winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
    for name, fname in user_fonts.items():
        path = Path(fname)
        if not path.is_absolute():
            path = LOCAL_FONTS_DIR / fname
        if path.is_file():
            fonts[name] = str(path)

    return fonts


def refresh_installed_fonts() -> dict[str, str]:
    """Fuerza releer el registro (por si el usuario acaba de instalar una fuente)."""
    list_installed_fonts.cache_clear()
    return list_installed_fonts()


_SUFFIXES = [
    "-BoldItalic", "-BoldOblique", "-Italic", "-Oblique", "-Bold", "-Regular",
    "BoldItalic", "BoldOblique", "Italic", "Oblique", "Bold", "Regular", "MT", "PS",
]


def guess_family_from_ps_name(ps_name: str) -> str:
    """'ArialMT' -> 'Arial'; 'TimesNewRomanPS-BoldMT' -> 'Times New Roman'."""
    name = ps_name or ""
    if "+" in name and len(name.split("+")[0]) == 6:
        name = name.split("+", 1)[1]   # quita el prefijo de subconjunto "ABCDEF+"
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if name.endswith(suf):
                name = name[: -len(suf)]
                changed = True
    name = re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip()   # CamelCase -> con espacios
    name = re.sub(r"\s+", " ", name)
    return name or ps_name


def style_from_ps_name(ps_name: str) -> tuple[bool, bool]:
    """(negrita, cursiva) deducidas del nombre PostScript de la fuente."""
    low = (ps_name or "").lower()
    return "bold" in low, ("italic" in low or "oblique" in low)


def find_styled_font(family: str, bold: bool = False, italic: bool = False,
                     installed: dict[str, str] | None = None) -> str | None:
    """Archivo de la familia con la negrita/cursiva pedidas; si esa variante no
    está instalada, devuelve la más cercana (p. ej. la normal)."""
    if installed is None:
        installed = list_installed_fonts()
    fam = (family or "").lower().strip()
    if not fam:
        return None
    sub_fam = SUBSTITUTES.get(fam)
    if sub_fam and not any(k == fam or k.startswith(fam + " ") for k in installed):
        fam = sub_fam.lower()                       # no está la original: se usa la sustituta
    wanted = [" bold italic"] if bold and italic else [" bold"] if bold else [" italic"] if italic else []
    if bold and italic:
        wanted += [" bold", " italic"]
    for suffix in wanted + [""]:
        if fam + suffix in installed:
            return installed[fam + suffix]
    for k, path in installed.items():
        if k.startswith(fam) and not any(w in k[len(fam):] for w in ("bold", "italic", "oblique")):
            return path
    return None


def find_font_file(ps_name: str, installed: dict[str, str] | None = None) -> tuple[str | None, str]:
    """
    Busca el archivo de fuente instalada que mejor coincide con ps_name
    (el nombre PostScript tal cual aparece en el PDF).
    Devuelve (ruta_al_archivo o None, nombre_de_familia_legible).
    """
    if installed is None:
        installed = list_installed_fonts()
    family = guess_family_from_ps_name(ps_name)
    key = family.lower()
    if key in installed:
        return installed[key], family
    sub_fam = SUBSTITUTES.get(key)
    if sub_fam and sub_fam.lower() in installed:             # p. ej. Calibri → Carlito
        return installed[sub_fam.lower()], family
    base = ps_name.split("+", 1)[1] if "+" in ps_name and len(ps_name.split("+")[0]) == 6 else ps_name
    if "-" in base:                                      # «OpenSans-SemiBold» → «open sans semibold»
        head, tail = base.split("-", 1)
        head = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", re.sub(r"(PSMT|MT|PS)$", "", head)).lower()
        tail = re.sub(r"(psmt|mt)$", "", tail.lower().replace(" ", ""))
        for cand in (f"{head} {tail}", f"{head} {re.sub(r'(?<=[a-z])(?=italic)', ' ', tail)}"):
            if cand in installed:
                return installed[cand], family
    for k, path in installed.items():
        if key and (key in k or k in key):
            return path, family
    return None, family
