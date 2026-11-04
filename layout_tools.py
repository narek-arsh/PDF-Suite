# -*- coding: utf-8 -*-
"""
layout_tools.py — Entiende la maquetación de una página a partir de sus palabras con posición: líneas, columnas,
párrafos, tablas (con o sin líneas) y filas sueltas (valores a la misma altura aunque estén muy separados).
Sirve igual para PDFs normales que para el texto reconocido con OCR. Sin dependencias de interfaz.

Entrada: palabras como (x0, y0, x1, y1, texto) en puntos de página; opcionalmente las líneas horizontales y
verticales dibujadas (para tablas con rejilla). Salida: bloques en orden de lectura.
"""
import re
import statistics

_BULLET = re.compile(r"^\s*(?:[•·▪◦➢➤►●○■□\-–—*]|\(?[a-zA-Z0-9]{1,3}[.)])\s*$")


# ── utilidades geométricas ───────────────────────────────────────────────
def _h(w) -> float:
    return max(w[3] - w[1], 0.1)


def _vover(a0, a1, b0, b1) -> float:
    """Solape vertical relativo al más bajo de los dos."""
    inter = min(a1, b1) - max(a0, b0)
    return inter / max(min(a1 - a0, b1 - b0), 0.1)


class Line:
    def __init__(self, words: list):
        self.words = sorted(words, key=lambda w: w[0])
        self.x0 = min(w[0] for w in self.words)
        self.y0 = min(w[1] for w in self.words)
        self.x1 = max(w[2] for w in self.words)
        self.y1 = max(w[3] for w in self.words)

    @property
    def h(self) -> float:
        return max(self.y1 - self.y0, statistics.median(_h(w) for w in self.words))

    @property
    def text(self) -> str:
        return " ".join(w[4] for w in self.words)

    @property
    def baseline(self) -> float:
        """Línea donde se apoyan la mayoría de las letras (las palabras con rabo bajan más; no cuentan)."""
        b = sorted(w[3] for w in self.words)
        return b[len(b) // 4]

    @property
    def bbox(self):
        return (self.x0, self.y0, self.x1, self.y1)


class TableSeg:
    """Tabla con rejilla ya resuelta; se comporta como un segmento más para ordenar la página."""
    text = ""

    def __init__(self, bbox, rows, cell_words):
        self.x0, self.y0, self.x1, self.y1 = bbox
        self.rows, self.cell_words = rows, cell_words
        self.words = [w for r in cell_words for c in r for w in c]
        self.h = 10.0


class Block:
    """kind: 'text' (párrafos) | 'table' (filas × columnas) | 'row' (valores sueltos a la misma altura).
    `ordered` = todas sus palabras, en orden de lectura."""
    def __init__(self, kind: str, bbox: tuple, lines=None, paragraphs=None, rows=None, ordered=None):
        self.kind, self.bbox = kind, bbox
        self.lines = lines or []
        self.paragraphs = paragraphs or []      # list[list[Line]]
        self.rows = rows or []                  # list[list[str]]
        self.ordered = ordered or []


# ── 1. palabras → líneas → segmentos ─────────────────────────────────────
def group_lines(words: list) -> list:
    """Agrupa palabras en líneas por solape vertical (sin importar cuánto las separe en horizontal)."""
    words = [w for w in words if str(w[4]).strip()]
    words.sort(key=lambda w: (w[1] + w[3]) / 2)
    lines: list = []
    for w in words:
        placed = False
        for ln in reversed(lines[-6:]):
            if _vover(ln["y0"], ln["y1"], w[1], w[3]) > 0.55:
                ln["w"].append(w)
                ln["y0"], ln["y1"] = min(ln["y0"], w[1]), max(ln["y1"], w[3])
                placed = True
                break
        if not placed:
            lines.append({"w": [w], "y0": w[1], "y1": w[3]})
    return [Line(l["w"]) for l in lines]


def split_segments(line: Line, gap_factor: float = 1.0) -> list:
    """Parte una línea donde haya un hueco claramente mayor que un espacio normal (columna, celda, valor lejano)."""
    thr = gap_factor * line.h
    segs, cur = [], [line.words[0]]
    for prev, w in zip(line.words, line.words[1:]):
        if w[0] - prev[2] > thr:
            segs.append(Line(cur))
            cur = [w]
        else:
            cur.append(w)
    segs.append(Line(cur))
    return segs


# ── 2. corte XY (orden de lectura con columnas) ──────────────────────────
def _cuts(items: list, lo, hi, min_gap: float) -> list:
    """Posiciones medias de los huecos ≥ min_gap entre intervalos (lo(item), hi(item))."""
    spans = sorted((lo(i), hi(i)) for i in items)
    cuts, reach = [], spans[0][1]
    for a, b in spans[1:]:
        if a - reach >= min_gap:
            cuts.append((reach + a) / 2)
        reach = max(reach, b)
    return cuts


def _split(items: list, pos: list, key) -> list:
    groups = [[] for _ in range(len(pos) + 1)]
    for it in items:
        k = sum(1 for p in pos if key(it) > p)
        groups[k].append(it)
    return [g for g in groups if g]


def xy_cut(segs: list, med_h: float, depth: int = 0) -> list:
    """Divide en regiones: primero por huecos horizontales (bloques apilados) y, si no hay, por huecos verticales
    (columnas), salvo que la región sea una tabla (se lee por filas). Devuelve listas de segmentos en orden."""
    if len(segs) <= 1 or depth > 12:
        return [segs]
    hc = _cuts(segs, lambda s: s.y0, lambda s: s.y1, 0.9 * med_h)
    if hc:
        out = []
        for g in _split(segs, hc, lambda s: (s.y0 + s.y1) / 2):
            out += xy_cut(g, med_h, depth + 1)
        return out
    if not any(isinstance(s, TableSeg) for s in segs):
        rows = _lines_of(segs)
        if len(rows) >= 2 and _looks_like_table(rows):
            return [segs]                   # una tabla no se corta en columnas: se lee por filas
    vc = _cuts(segs, lambda s: s.x0, lambda s: s.x1, 1.5 * med_h)
    if vc:
        groups = _split(segs, vc, lambda s: (s.x0 + s.x1) / 2)
        if len(groups) > 1:
            out = []
            for g in groups:
                out += xy_cut(g, med_h, depth + 1)
            return out
    return [segs]


# ── 3. clasificación de cada región ──────────────────────────────────────
def _is_number(t: str) -> bool:
    return bool(re.fullmatch(r"[-+(]?[€$£]?\s?\d[\d.,\s]*\s?[%€$£)·]?", t.strip()))


def _lines_of(region: list) -> list:
    """Reagrupa los segmentos de una región en líneas (segmentos a la misma altura)."""
    rows: list = []
    for s in sorted(region, key=lambda s: (s.y0 + s.y1) / 2):
        for r in rows:
            if _vover(r[0].y0, r[0].y1, s.y0, s.y1) > 0.55:
                r.append(s)
                break
        else:
            rows.append([s])
    return [sorted(r, key=lambda s: s.x0) for r in rows]


def _looks_like_table(rows: list) -> bool:
    """Varias filas con celdas cortas y bien alineadas en columnas, sobre todo si hay cifras."""
    multi = [r for r in rows if len(r) >= 2]
    if len(multi) < 2 or len(multi) < 0.6 * len(rows):
        return False
    ncols = statistics.mode(len(r) for r in multi)
    if ncols < 2:
        return False
    cells = [s for r in multi for s in r]
    labels = [r[0].text.strip() for r in multi]
    if ncols == 2 and sum(1 for l in labels if l.endswith(":")) >= 0.5 * len(labels):
        return True                                        # lista «etiqueta: valor»
    short = sum(1 for s in cells if len(s.words) <= 3) / len(cells)
    numeric = sum(1 for s in cells if _is_number(s.text)) / len(cells)
    avg_words = sum(len(s.words) for s in cells) / len(cells)
    return (short >= 0.7 and (numeric >= 0.2 or ncols >= 3)) and avg_words <= 3.5


def _table_from_rows(rows: list):
    """Asigna las celdas de cada fila a columnas definidas por los huecos verticales comunes."""
    segs = [s for r in rows for s in r]
    med_h = statistics.median(s.h for s in segs)
    cuts = _cuts(segs, lambda s: s.x0, lambda s: s.x1, 0.6 * med_h)
    texts, cwords = [], []
    for r in rows:
        cells, cw = [""] * (len(cuts) + 1), [[] for _ in range(len(cuts) + 1)]
        for s in r:
            k = sum(1 for c in cuts if (s.x0 + s.x1) / 2 > c)
            cells[k] = (cells[k] + " " + s.text).strip()
            cw[k] += s.words
        texts.append(cells)
        cwords.append(cw)
    return texts, cwords


def _paragraphs(lines: list) -> list:
    """Agrupa líneas consecutivas en párrafos: un salto de línea mayor que el habitual del bloque, una sangría de
    primera línea o una viñeta empiezan un párrafo nuevo."""
    lines = sorted(lines, key=lambda l: l.y0)
    if not lines:
        return []
    bases = [l.baseline for l in lines]
    pitches = [b - a for a, b in zip(bases, bases[1:])]
    span_ref = max(l.y1 - l.y0 for l in lines)
    # distancia normal entre líneas: la mediana del propio bloque; con pocas líneas, por el tamaño de la letra
    limit = 1.35 * statistics.median(pitches) if len(pitches) >= 3 else 1.85 * span_ref
    h = statistics.median(l.h for l in lines)
    left = min(l.x0 for l in lines)
    paras, cur = [], [lines[0]]
    for prev, ln, pitch in zip(lines, lines[1:], pitches):
        new = pitch > limit
        if not new and ln.x0 - left > 0.5 * h and ln.x0 - prev.x0 > 0.5 * h:
            new = True                                     # sangría de primera línea
        if not new and _BULLET.match(ln.words[0][4]) and len(ln.words) > 1:
            new = True                                     # viñeta o numeración
        if new:
            paras.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    paras.append(cur)
    return paras


# ── 4. tablas con rejilla (líneas dibujadas) ─────────────────────────────
def _cluster(vals: list, tol: float) -> list:
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def grid_tables(words: list, h_lines: list, v_lines: list, min_cells: int = 2) -> tuple:
    """Tablas con rejilla. h_lines = [(y, x0, x1)], v_lines = [(x, y0, y1)]. Devuelve ([TableSeg], palabras sobrantes).
    Cada celda recoge las palabras que caen dentro, también si ocupan varias líneas o la celda está vacía."""
    if not h_lines or not v_lines:
        return [], list(words)
    items = [("h", l) for l in h_lines] + [("v", l) for l in v_lines]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    tol = 6.0
    for i, (ka, a) in enumerate(items):
        for j in range(i + 1, len(items)):
            kb, b = items[j]
            if ka == kb:
                continue
            h, v = (a, b) if ka == "h" else (b, a)
            if h[1] - tol <= v[0] <= h[2] + tol and v[1] - tol <= h[0] <= v[2] + tol:
                parent[find(i)] = find(j)
    comps: dict = {}
    for i, it in enumerate(items):
        comps.setdefault(find(i), []).append(it)
    tables, used = [], set()
    for comp in comps.values():
        hs = [l for k, l in comp if k == "h"]
        vs = [l for k, l in comp if k == "v"]
        ys, xs = _cluster([l[0] for l in hs], tol), _cluster([l[0] for l in vs], tol)
        if len(ys) < 2 or len(xs) < 2 or (len(ys) - 1) * (len(xs) - 1) < min_cells:
            continue
        bbox = (xs[0], ys[0], xs[-1], ys[-1])
        texts, cwords = [], []
        for r in range(len(ys) - 1):
            trow, wrow = [], []
            for c in range(len(xs) - 1):
                inside = [w for w in words if xs[c] <= (w[0] + w[2]) / 2 <= xs[c + 1]
                          and ys[r] <= (w[1] + w[3]) / 2 <= ys[r + 1]]
                for w in inside:
                    used.add(id(w))
                lines = group_lines(inside) if inside else []
                trow.append(" ".join(l.text for l in lines))
                wrow.append([w for l in lines for w in l.words])
            texts.append(trow)
            cwords.append(wrow)
        texts, cwords = _trim_empty_edges(texts, cwords)
        if not any(any(c.strip() for c in row) for row in texts):
            continue
        tables.append(TableSeg(bbox, texts, cwords))
    rest = [w for w in words if id(w) not in used]
    return tables, rest


def _trim_empty_edges(texts: list, cwords: list) -> tuple:
    """Quita filas y columnas vacías de los bordes (al seleccionar solo una parte de la tabla)."""
    def empty_row(r):
        return not any(c.strip() for c in texts[r])

    def empty_col(c):
        return not any(texts[r][c].strip() for r in range(len(texts)))
    while len(texts) > 1 and empty_row(0):
        texts, cwords = texts[1:], cwords[1:]
    while len(texts) > 1 and empty_row(len(texts) - 1):
        texts, cwords = texts[:-1], cwords[:-1]
    n = len(texts[0]) if texts else 0
    lo, hi = 0, n
    while hi - lo > 1 and empty_col(lo):
        lo += 1
    while hi - lo > 1 and empty_col(hi - 1):
        hi -= 1
    return [r[lo:hi] for r in texts], [r[lo:hi] for r in cwords]


# ── 5. análisis completo ─────────────────────────────────────────────────
def analyze(words: list, h_lines: list | None = None, v_lines: list | None = None) -> list:
    """Palabras → bloques en orden de lectura (texto en párrafos, tablas, filas sueltas)."""
    words = [w for w in words if str(w[4]).strip()]
    tseg, rest = grid_tables(words, h_lines or [], v_lines or [])
    lines = group_lines(list(rest))
    if not lines and not tseg:
        return []
    med_h = statistics.median(l.h for l in lines) if lines else 10.0
    segs = [s for l in lines for s in split_segments(l)] + tseg
    blocks: list = []
    for region in xy_cut(segs, med_h):
        ts = [s for s in region if isinstance(s, TableSeg)]
        others = [s for s in region if not isinstance(s, TableSeg)]
        parts = [("t", s.y0, s) for s in ts]
        if others:
            parts.append(("o", min(s.y0 for s in others), others))
        for kind, _y, obj in sorted(parts, key=lambda p: p[1]):
            if kind == "t":
                blocks.append(Block("table", (obj.x0, obj.y0, obj.x1, obj.y1), rows=obj.rows,
                                    ordered=[w for r in obj.cell_words for c in r for w in c]))
                continue
            rows = _lines_of(obj)
            bbox = (min(s.x0 for s in obj), min(s.y0 for s in obj), max(s.x1 for s in obj), max(s.y1 for s in obj))
            if len(rows) >= 2 and _looks_like_table(rows):
                texts, cwords = _table_from_rows(rows)
                blocks.append(Block("table", bbox, rows=texts, ordered=[w for r in cwords for c in r for w in c]))
            elif len(rows) == 1 and len(rows[0]) >= 2:
                blocks.append(Block("row", bbox, rows=[[s.text for s in rows[0]]],
                                    ordered=[w for s in rows[0] for w in s.words]))
            else:
                flat = [Line([w for s in r for w in s.words]) for r in rows]
                blocks.append(Block("text", bbox, lines=flat, paragraphs=_paragraphs(flat),
                                    ordered=[w for l in flat for w in l.words]))
    return _merge_same_row(blocks)


def _merge_same_row(blocks: list) -> list:
    """Dos bloques de una sola línea a la misma altura (p. ej. «Total:» y su importe lejano) van juntos en una fila."""
    out: list = []
    for b in blocks:
        single = (b.kind == "row") or (b.kind == "text" and len(b.lines) == 1)
        if out and single:
            p = out[-1]
            psingle = (p.kind == "row") or (p.kind == "text" and len(p.lines) == 1)
            if psingle and _vover(p.bbox[1], p.bbox[3], b.bbox[1], b.bbox[3]) > 0.55:
                cells = (p.rows[0] if p.kind == "row" else [p.lines[0].text]) + \
                        (b.rows[0] if b.kind == "row" else [b.lines[0].text])
                out[-1] = Block("row", (min(p.bbox[0], b.bbox[0]), min(p.bbox[1], b.bbox[1]),
                                        max(p.bbox[2], b.bbox[2]), max(p.bbox[3], b.bbox[3])), rows=[cells],
                                ordered=p.ordered + b.ordered)
                continue
        out.append(b)
    return out


# ── 6. salida ────────────────────────────────────────────────────────────
def paragraph_text(lines: list, reflow: bool = True) -> str:
    """Une las líneas de un párrafo (y las palabras partidas con guion al final de línea)."""
    if not reflow:
        return "\n".join(l.text for l in lines)
    out = ""
    for ln in lines:
        t = ln.text
        if out.endswith("-") and len(out) > 1 and out[-2].isalpha() and t[:1].islower():
            out = out[:-1] + t
        else:
            out = (out + " " + t) if out else t
    return out


def blocks_to_text(blocks: list, reflow: bool = True, tab: str = "\t") -> str:
    parts = []
    for b in blocks:
        if b.kind == "text":
            parts.append("\n".join(paragraph_text(p, reflow) for p in b.paragraphs))
        else:                                              # tabla o fila: celdas separadas por tabulador
            parts.append("\n".join(tab.join(c for c in row) for row in b.rows))
    return "\n\n".join(p for p in parts if p.strip())


def ordered_words(blocks: list) -> list:
    """Todas las palabras de la página en orden de lectura (para escribir una capa de texto bien ordenada)."""
    return [w for b in blocks for w in b.ordered]


def words_in_rect(words: list, rect: tuple) -> list:
    """Palabras cuyo centro cae dentro del rectángulo."""
    x0, y0, x1, y1 = rect
    return [w for w in words if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]


def region_to_text(words: list, rect: tuple, reflow: bool = True, h_lines=None, v_lines=None) -> dict:
    """Texto de una zona respetando párrafos, columnas y tablas. {"text", "blocks", "tables", "n_words"}."""
    inside = words_in_rect(words, rect)
    # líneas que tocan la zona (aunque la rejilla siga fuera de ella: las filas y columnas vacías de los bordes se recortan)
    hl = [l for l in (h_lines or []) if l[2] >= rect[0] - 3 and l[1] <= rect[2] + 3]
    vl = [l for l in (v_lines or []) if l[2] >= rect[1] - 3 and l[1] <= rect[3] + 3]
    blocks = analyze(inside, hl, vl)
    return {"text": blocks_to_text(blocks, reflow), "blocks": blocks, "n_words": len(inside),
            "tables": [b for b in blocks if b.kind == "table"]}


# ── 7. líneas dibujadas en un PDF normal (para tablas con rejilla) ───────
def lines_from_page(page, min_len: float = 20.0) -> tuple:
    """Líneas horizontales y verticales dibujadas en la página: ([(y, x0, x1)], [(x, y0, y1)]). Las celdas hechas con
    rectángulos aportan sus cuatro lados."""
    h, v = [], []
    try:
        drawings = page.get_drawings()
    except Exception:
        return [], []

    def add_h(y, a, b):
        if abs(b - a) >= min_len:
            h.append((y, min(a, b), max(a, b)))

    def add_v(x, a, b):
        if abs(b - a) >= min_len:
            v.append((x, min(a, b), max(a, b)))
    for d in drawings:
        for it in d.get("items", []):
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) < 1.5:
                    add_h((p1.y + p2.y) / 2, p1.x, p2.x)
                elif abs(p1.x - p2.x) < 1.5:
                    add_v((p1.x + p2.x) / 2, p1.y, p2.y)
            elif it[0] == "re":
                r = it[1]
                if r.height <= 1.8:
                    add_h((r.y0 + r.y1) / 2, r.x0, r.x1)
                elif r.width <= 1.8:
                    add_v((r.x0 + r.x1) / 2, r.y0, r.y1)
                elif r.width >= min_len and r.height >= 6:
                    add_h(r.y0, r.x0, r.x1); add_h(r.y1, r.x0, r.x1)
                    add_v(r.x0, r.y0, r.y1); add_v(r.x1, r.y0, r.y1)
    return h, v


def block_at(blocks: list, pt: tuple):
    """Bloque que contiene el punto (el más pequeño si hay varios), o el más cercano en vertical."""
    def near(b, m):
        return b.bbox[0] - m <= pt[0] <= b.bbox[2] + m and b.bbox[1] - m <= pt[1] <= b.bbox[3] + m
    for margin in (2, 8, 16):                          # primero un clic exacto, luego un clic «cerca»
        hit = [b for b in blocks if near(b, margin)]
        if hit:
            return min(hit, key=lambda b: (b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1]))
    return None
