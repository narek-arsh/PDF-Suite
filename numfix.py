# -*- coding: utf-8 -*-
"""Separadores de miles y decimales en lo que lee el OCR.

Con poca calidad, el OCR confunde «.» y «,». Aquí se deduce cuál es cuál por su POSICIÓN: los miles se agrupan de tres
en tres (1.234.567) y los decimales van al final y no suelen ser tres; el último separador de un importe como
1.234,56 es el decimal y los demás son de miles. Con eso se sabe el papel de cada símbolo aunque se haya leído mal; el
carácter que debe llevar cada papel se toma de los números claros del propio documento (o del idioma elegido).

Solo se corrige donde la estructura lo demuestra; lo dudoso se marca para que lo mire una persona. Las fechas
(14.11.2026), teléfonos, códigos y horas no se tocan: no tienen forma de cantidad."""
from __future__ import annotations

import re

_SEP = re.compile(r"[.,]")
# prefijo y sufijo permitidos alrededor de la cantidad (moneda, signo, %, paréntesis y puntuación de frase)
_AFFIX_OK = re.compile(r"^[\s€$£¥%+\-−–()\[\]«»\"'.,;:!?]*$")
_PARSE = re.compile(r"^(?P<pre>[^\d]*)(?P<core>\d[\d.,]*\d)(?P<post>[^\d]*)$")

# idiomas (códigos de Tesseract) y su separador decimal habitual
_DECIMAL_COMMA = {"spa", "por", "fra", "ita", "deu", "nld", "cat", "glg", "eus", "rus", "pol", "swe", "dan", "nor", "fin"}
_DECIMAL_DOT = {"eng"}


def parse(core: str):
    """Estructura de una cantidad con separadores: (roles, certeza) o None si no tiene forma de cantidad.
    `roles` lleva «th» (miles) o «dec» (decimal) por cada separador, en orden; None en el papel de un separador único
    que puede ser cualquiera de los dos (p. ej. 1.234). `certeza`: «alta» si la estructura lo demuestra."""
    seps = _SEP.findall(core)
    groups = _SEP.split(core)
    if not seps or any(g == "" for g in groups):
        return None
    n, last = len(groups), len(groups[-1])
    if n == 2:
        if last != 3:
            return ["dec"], ("alta" if last == 2 else "media")
        # un solo separador y tres dígitos detrás: 1.234 (miles) o 0,125 / 1234,567 (decimal)
        if len(groups[0]) > 3 or groups[0].startswith("0"):
            return ["dec"], "media"
        return [None], "ambigua"
    # varios separadores: el primer grupo tiene 1-3 dígitos y los intermedios exactamente 3
    if not 1 <= len(groups[0]) <= 3 or groups[0].startswith("0"):
        return None
    if any(len(g) != 3 for g in groups[1:-1]):
        return None
    if last == 3 and len(set(seps)) == 1:
        return ["th"] * len(seps), "alta"                 # 1.234.567: todo miles
    return ["th"] * (len(seps) - 1) + ["dec"], "alta"


class NumberFixer:
    """Aprende el separador decimal del documento y corrige las cantidades mal leídas. Se usa página a página:
    `learn` con las palabras de la página y después `fix`."""

    def __init__(self, languages=None):
        self.votes = {",": 0, ".": 0}                    # carácter que hace de separador DECIMAL
        langs = set(languages or [])
        if langs and langs <= _DECIMAL_COMMA:
            self.hint = ","
        elif langs and langs <= _DECIMAL_DOT:
            self.hint = "."
        else:
            self.hint = None

    # ── convención del documento ───────────────────────────────────────
    @staticmethod
    def _split(text: str):
        m = _PARSE.match(text.strip())
        if not m or not _AFFIX_OK.match(m.group("pre")) or not _AFFIX_OK.match(m.group("post")):
            return None
        return m.group("pre"), m.group("core"), m.group("post")

    def learn(self, words) -> None:
        for w in words:
            parts = self._split(str(w[4]))
            if not parts:
                continue
            core = parts[1]
            info = parse(core)
            if not info:
                continue
            roles, certainty = info
            seps = _SEP.findall(core)
            if certainty == "alta" and "dec" in roles and len(set(seps)) == 2:
                self.votes[seps[-1]] += 3                # 1.234,56: aquí los dos símbolos están bien leídos
            elif "dec" in roles and len(roles) == 1 and certainty in ("alta", "media"):
                self.votes[seps[0]] += 1                 # 12,50
            elif roles and set(roles) == {"th"} and len(set(seps)) == 1:
                self.votes["." if seps[0] == "," else ","] += 2    # 1.234.567: ese símbolo es el de miles

    def decimal_char(self):
        """(carácter decimal, ¿es firme?): por votos de los números claros; si no, por el idioma."""
        tot = sum(self.votes.values())
        if tot >= 2:
            top = max(self.votes, key=self.votes.get)
            if self.votes[top] / tot >= 0.7:
                return top, tot >= 4 and self.votes[top] / tot >= 0.8
        return self.hint, False

    # ── corrección ─────────────────────────────────────────────────────
    def fix(self, words):
        """(palabras corregidas, info) con info = {(x0, y0, x1, y1): ("fixed", original) | ("flag", motivo)}."""
        dec, firm = self.decimal_char()
        th = None if dec is None else ("." if dec == "," else ",")
        out, info = [], {}
        for w in words:
            text = str(w[4])
            parts = self._split(text)
            res = parse(parts[1]) if parts else None
            if not res:
                out.append(w)
                continue
            pre, core, post = parts
            roles, certainty = res
            seps = _SEP.findall(core)
            key = tuple(round(float(v), 2) for v in w[:4])
            if certainty == "ambigua":
                info[key] = ("flag", "¿miles o decimales? Con tres dígitos tras el separador no se puede saber")
                out.append(w)
                continue
            if dec is None:
                out.append(w)
                continue
            want = [dec if r == "dec" else th for r in roles]
            if want == seps:
                out.append(w)
                continue
            # certeza alta (varios separadores): la estructura prueba los papeles; con uno solo hace falta que el
            # documento tenga una convención firme y que sea un importe de dos decimales
            if certainty == "alta" and (len(seps) > 1 or firm):
                chars = iter(want)
                new_core = "".join(next(chars) if c in ".," else c for c in core)
                out.append((*w[:4], pre + new_core + post))
                info[key] = ("fixed", text)
            else:
                info[key] = ("flag", f"Posible separador mal leído: en este documento el decimal es «{dec}»")
                out.append(w)
        return out, info
