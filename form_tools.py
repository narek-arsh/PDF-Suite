# -*- coding: utf-8 -*-
"""
form_tools.py — Campos de formulario de un PDF abierto: listarlos, rellenarlos, crear campos nuevos
(texto, casilla, lista desplegable, lista de selección), borrarlos y aplanar el formulario.
Sin dependencias de interfaz. Coordenadas en puntos PDF.
"""
import re

import fitz

_KINDS = {
    fitz.PDF_WIDGET_TYPE_TEXT: "text",
    fitz.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
    fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
    fitz.PDF_WIDGET_TYPE_COMBOBOX: "combo",
    fitz.PDF_WIDGET_TYPE_LISTBOX: "list",
    fitz.PDF_WIDGET_TYPE_SIGNATURE: "signature",
    fitz.PDF_WIDGET_TYPE_BUTTON: "button",
}
KIND_LABELS = {"text": "Texto", "checkbox": "Casilla", "radio": "Botón de opción", "combo": "Lista desplegable",
               "list": "Lista de selección", "signature": "Firma", "button": "Botón"}
READONLY = 1                                   # bit 1 de los flags del campo


def _describe(w, doc=None) -> dict:
    kind = _KINDS.get(w.field_type, "other")
    d = {"xref": w.xref, "name": w.field_name or "", "kind": kind,
         "rect": (w.rect.x0, w.rect.y0, w.rect.x1, w.rect.y1), "value": w.field_value,
         "choices": [str(c) for c in (w.choice_values or [])] if kind in ("combo", "list") else [],
         "multiline": bool(kind == "text" and (w.field_flags or 0) & fitz.PDF_TX_FIELD_IS_MULTILINE),
         "readonly": bool((w.field_flags or 0) & READONLY), "fontsize": w.text_fontsize or 0}
    try:
        d["ours"] = bool(doc is not None and doc.xref_get_key(w.xref, "NM")[1] == "pdfm-field")   # creado desde el editor
    except Exception:
        d["ours"] = False
    if kind in ("checkbox", "radio"):
        try:
            d["on_state"] = w.on_state()
        except Exception:
            d["on_state"] = "Yes"
        d["checked"] = str(w.field_value) not in ("Off", "", "False", "None")
    return d


def widgets_of(doc, page_idx: int) -> list[dict]:
    try:
        page = doc[page_idx]
        return [_describe(w, doc) for w in (page.widgets() or [])]
    except Exception:
        return []


def widget_at(doc, page_idx: int, pt: tuple) -> dict | None:
    hit = None
    for d in widgets_of(doc, page_idx):
        r = d["rect"]
        if r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]:
            hit = d
    return hit


def has_fields(doc) -> bool:
    try:
        return any(True for i in range(len(doc)) for _ in (doc[i].widgets() or []))
    except Exception:
        return False


def set_widget_value(doc, page_idx: int, xref: int, value) -> bool:
    """Cambia el valor de un campo. En casillas, value es True/False; en botones de opción, True elige este
    y desmarca los del mismo grupo."""
    page = doc[page_idx]
    try:
        target = next((w for w in (page.widgets() or []) if w.xref == xref), None)
        if target is None:
            return False
        kind = _KINDS.get(target.field_type)
        if kind == "checkbox":
            target.field_value = target.on_state() if value else "Off"
            target.update()
        elif kind == "radio":
            if not _select_radio(doc, page, target):
                name = target.field_name
                for w in page.widgets():
                    if w.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON and w.field_name == name:
                        w.field_value = w.on_state() if w.xref == xref else "Off"
                        w.update()
        elif kind in ("text", "combo", "list"):
            if str(value) == "":
                # PyMuPDF ignora un valor vacío y deja el anterior: se pone un espacio (no se ve) para regenerar la
                # apariencia y después se deja el valor realmente vacío.
                target.field_value = " "
                target.update()
                doc.xref_set_key(xref, "V", "()")
            else:
                target.field_value = str(value)
                target.update()
        else:
            return False
        return True
    except Exception:
        return False


def _select_radio(doc, page, target) -> bool:
    """Marca un botón de opción y desmarca los demás de su grupo escribiendo directamente los objetos del PDF
    (PyMuPDF puede dejar dos marcados). False si el botón no tiene campo padre con hijos."""
    try:
        pk = doc.xref_get_key(target.xref, "Parent")
        if pk[0] != "xref":
            return False
        parent = int(pk[1].split()[0])
        kk = doc.xref_get_key(parent, "Kids")
        if kk[0] != "array":
            return False
        kids = [int(x) for x in re.findall(r"(\d+)\s+0\s+R", kk[1])]
        state = target.on_state()
        for k in kids:
            doc.xref_set_key(k, "AS", "/" + state if k == target.xref else "/Off")
        doc.xref_set_key(parent, "V", "/" + state)
        return True
    except Exception:
        return False


def unique_name(doc, base: str = "campo") -> str:
    base = re.sub(r"\s+", "_", (base or "campo").strip()) or "campo"
    used = set()
    for i in range(len(doc)):
        for w in (doc[i].widgets() or []):
            used.add(w.field_name)
    if base not in used:
        return base
    n = 2
    while f"{base}{n}" in used:
        n += 1
    return f"{base}{n}"


def add_field(doc, page_idx: int, rect, spec: dict) -> bool:
    """Crea un campo. spec = {"kind": text|multiline|checkbox|combo|list, "name", "choices", "value", "fontsize"}."""
    page = doc[page_idx]
    kind = spec["kind"]
    r = fitz.Rect(rect)
    if kind == "radio":
        n = max(len([c for c in (spec.get("choices") or []) if c.strip()]), 2)
        spacing = max(20.0, min(34.0, r.height / n)) if r.height > 0 else 22.0
        return add_radio_group(doc, page_idx, spec.get("name") or "opcion", spec.get("choices") or [],
                               (r.x0, r.y0), spacing=spacing)
    if kind == "checkbox":
        side = max(10.0, min(r.width, r.height))
        r = fitz.Rect(r.x0, r.y0, r.x0 + side, r.y0 + side)
    elif spec.get("box"):
        r = fitz.Rect(r)                              # cajita ya dibujada: el campo ocupa exactamente la caja
    else:
        r = fitz.Rect(r.x0, r.y0, r.x1, max(r.y1, r.y0 + 16))
    try:
        w = fitz.Widget()
        w.rect = r
        w.field_name = unique_name(doc, spec.get("name") or "campo")
        w.border_color = (0.35, 0.35, 0.35)
        w.border_width = 1
        w.fill_color = (0.93, 0.96, 1.0)
        w.text_color = (0, 0, 0)
        if kind in ("text", "multiline"):
            w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
            w.text_fontsize = float(spec.get("fontsize") or (min(11.0, max(6.0, r.height * 0.7)) if spec.get("box") else 11))
            w.field_value = spec.get("value") or ""
            if kind == "multiline":
                w.field_flags = (w.field_flags or 0) | fitz.PDF_TX_FIELD_IS_MULTILINE
        elif kind == "checkbox":
            w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
        elif kind in ("combo", "list"):
            w.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX if kind == "combo" else fitz.PDF_WIDGET_TYPE_LISTBOX
            w.choice_values = [c for c in (spec.get("choices") or []) if c.strip()] or ["Opción 1", "Opción 2"]
            w.text_fontsize = float(spec.get("fontsize") or 11)
            if spec.get("value") in w.choice_values:
                w.field_value = spec["value"]
        else:
            return False
        before = {x[0] for x in page.annot_xrefs()}
        page.add_widget(w)
        try:
            for x in page.annot_xrefs():
                if x[0] not in before:
                    doc.xref_set_key(x[0], "NM", "(pdfm-field)")        # marca: lo creó el editor (se puede mover)
                    if spec.get("box"):
                        doc.xref_set_key(x[0], "Q", "1")                # texto centrado en la cajita
        except Exception:
            pass
        return True
    except Exception:
        return False


def set_field_rect(doc, page_idx: int, xref: int, rect) -> bool:
    """Mueve o cambia de tamaño un campo."""
    page = doc[page_idx]
    try:
        for w in (page.widgets() or []):
            if w.xref == xref:
                w.rect = fitz.Rect(rect)
                w.update()
                return True
    except Exception:
        pass
    return False


def delete_field(doc, page_idx: int, xref: int) -> bool:
    page = doc[page_idx]
    try:
        for w in (page.widgets() or []):
            if w.xref == xref:
                page.delete_widget(w)
                return True
    except Exception:
        pass
    return False


def flatten(doc) -> bool:
    """Convierte los campos en contenido fijo de la página (ya no se pueden editar)."""
    try:
        doc.bake(annots=False, widgets=True)
        return True
    except Exception:
        return False


# ── Detección automática de campos en un PDF "plano" ──────────────────────
def _iou_like(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1.0
    return inter / area


def _merge_collinear(items: list, gap: float) -> list:
    """Une trozos de una misma línea. items = [(posición, inicio, fin)] (p. ej. y, x0, x1 de trozos horizontales); los que
    están a menos de 1 pt de posición forman una línea y se unen si entre ellos hay como mucho `gap` pt.
    Devuelve [(posición, inicio, fin, nº de trozos)]."""
    out: list = []
    items = sorted(items)
    i = 0
    while i < len(items):
        j = i + 1
        while j < len(items) and items[j][0] - items[j - 1][0] <= 1.0:
            j += 1
        cluster = sorted(items[i:j], key=lambda s: s[1])
        pos = sum(s[0] for s in cluster) / len(cluster)
        cur = [pos, cluster[0][1], cluster[0][2], 1]
        for s in cluster[1:]:
            if s[1] <= cur[2] + gap:
                cur[2] = max(cur[2], s[2])
                cur[3] += 1
            else:
                out.append(tuple(cur))
                cur = [pos, s[1], s[2], 1]
        out.append(tuple(cur))
        i = j
    return out


def detect_fields(doc, page_idx: int) -> list[dict]:
    """Posibles campos de una página que no los tiene: líneas y rayas para rellenar (texto), recuadros vacíos
    (texto, o varias líneas si son altos) y casillas pequeñas. Devuelve [{"kind", "rect"}]."""
    page = doc[page_idx]
    pr = page.rect
    words = page.get_text("words")
    existing = [tuple(d["rect"]) for d in widgets_of(doc, page_idx)]
    cands: list[dict] = []

    def word_cover(r) -> float:
        """Fracción del recuadro tapada por palabras."""
        area = (r[2] - r[0]) * (r[3] - r[1]) or 1.0
        cov = 0.0
        for w in words:
            ix = max(0.0, min(r[2], w[2]) - max(r[0], w[0]))
            iy = max(0.0, min(r[3], w[3]) - max(r[1], w[1]))
            cov += ix * iy
        return cov / area

    # 1) rayas hechas con texto: «______», «.......», «- - - -», «…»; las partidas en varias palabras seguidas se unen
    leader = set("_.-–—…·•")
    rows: dict = {}
    for w in words:
        s = w[4]
        if len(s) >= 3 and set(s) <= leader and (len(s) >= 4 or set(s) <= {"_", "…"}):
            rows.setdefault((w[5], w[6]), []).append(w)
    for ws in rows.values():
        ws.sort(key=lambda w: w[0])
        group = [ws[0]]
        for w in ws[1:] + [None]:
            if w is not None and w[0] - group[-1][2] <= 8.0:
                group.append(w)
                continue
            x0, x1 = group[0][0], group[-1][2]
            if x1 - x0 >= 18:
                cands.append({"kind": "text", "rect": (x0, min(g[1] for g in group) - 1.5, x1,
                                                        max(g[3] for g in group) + 1.0)})
            group = [w] if w is not None else []
    # 2) dibujos vectoriales
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    segs: list = []                                  # trozos horizontales (x0, x1, y): líneas, rectángulos finos…
    vsegs: list = []                                 # trozos verticales (x, y0, y1): lados de casillas dibujadas a trozos
    for d in drawings:
        visible = d.get("color") is not None or d.get("fill") is not None
        for it in d.get("items", []):
            op = it[0]
            if op == "l":
                p1, p2 = it[1], it[2]
                if visible and abs(p1.y - p2.y) < 1.0 and abs(p1.x - p2.x) >= 0.8:
                    segs.append((min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2))
                elif visible and abs(p1.x - p2.x) < 1.0 and abs(p1.y - p2.y) >= 3.0:
                    vsegs.append(((p1.x + p2.x) / 2, min(p1.y, p2.y), max(p1.y, p2.y)))
            elif op in ("re", "qu"):
                rc = it[1] if op == "re" else it[1].rect
                w_, h_ = rc.width, rc.height
                if h_ < 1.6 and w_ >= 0.8 and visible:                        # línea dibujada como rectángulo fino
                    segs.append((rc.x0, rc.x1, rc.y0 + h_ / 2))
                elif w_ < 1.6 and h_ >= 3.0 and visible:                      # lado vertical dibujado como rectángulo fino
                    vsegs.append((rc.x0 + w_ / 2, rc.y0, rc.y1))
                elif op != "re":
                    continue
                elif 6 <= w_ <= 26 and 6 <= h_ <= 26 and abs(w_ - h_) <= 8.0 and d.get("color") is not None:
                    r = (rc.x0, rc.y0, rc.x1, rc.y1)
                    if word_cover(r) < 0.1:
                        cands.append({"kind": "checkbox", "rect": r})
                elif 40 <= w_ <= pr.width * 0.9 and 11 <= h_ <= 140 and d.get("color") is not None:
                    fill = d.get("fill")
                    if fill is None or all(c > 0.92 for c in fill):
                        r = (rc.x0, rc.y0, rc.x1, rc.y1)
                        if word_cover(r) < 0.05:
                            cands.append({"kind": "multiline" if h_ >= 36 else "text", "rect": r})
    # líneas que el PDF trae como imágenes finísimas (formularios escaneados o generados con rayas de puntos en bitmap)
    try:
        for im in page.get_image_info():
            ix0, iy0, ix1, iy1 = im["bbox"]
            if (iy1 - iy0) <= 4.5 and (ix1 - ix0) >= 1.0:
                segs.append((ix0, ix1, (iy0 + iy1) / 2))
    except Exception:
        pass
    # casillas escritas como símbolo de texto (□ ☐ ❏): se convierten en casillas de verdad
    for w in words:
        if w[4] and w[4][0] in "□☐❏❑◻" and len(w[4]) <= 2:
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            cands.append({"kind": "checkbox", "rect": (cx - 5.5, cy - 5.5, cx + 5.5, cy + 5.5)})
    # unir los trozos de una misma línea (rayas de puntos o guiones dibujadas a trozos) y quedarse con las de 18 pt o más
    merged: list = [(a0, a1, pos, n) for pos, a0, a1, n in _merge_collinear([(s[2], s[0], s[1]) for s in segs], 7.0)]
    # cajitas pequeñas dibujadas con cuatro lados (H, M, S, C, V…): se convierten en casillas de TEXTO, para poder
    # escribir en ellas una X (o lo que haga falta) en vez de ser solo de marcar
    vmerged: list = [(pos, a0, a1) for pos, a0, a1, _n in _merge_collinear(vsegs, 3.0)]
    small = [m for m in merged if 6.0 <= m[1] - m[0] <= 30.0]
    for i, a in enumerate(small):
        for b in small[i + 1:]:
            dy = b[2] - a[2]
            if 6.0 <= dy <= 30.0 and abs(a[0] - b[0]) <= 1.5 and abs(a[1] - b[1]) <= 1.5:
                def side(x):
                    return any(abs(v[0] - x) <= 1.5 and v[1] <= a[2] + 1.5 and v[2] >= b[2] - 1.5 for v in vmerged)
                if side(a[0]) and side(a[1]):
                    r = (a[0], a[2], a[1], b[2])
                    if word_cover(r) < 0.1:
                        cands.append({"kind": "text", "rect": r, "box": True})
    for x0, x1, y, _n in merged:
        if x1 - x0 >= pr.width * 0.95:
            continue
        # una línea que pasa por debajo de etiquetas («Provincia», «NIF/NIE»…) se parte alrededor de ellas
        cuts = sorted((w[0] - 1.0, w[2] + 1.0) for w in words
                      if y - 13.0 <= (w[1] + w[3]) / 2 <= y + 2.0 and w[2] > x0 and w[0] < x1 and not set(w[4]) <= leader)
        pieces, cur = [], x0
        for c0, c1 in cuts:
            if c0 - cur >= 1.0:
                pieces.append((cur, min(c0, x1)))
            cur = max(cur, c1)
        if x1 - cur >= 1.0:
            pieces.append((cur, x1))
        for a, b in pieces:
            r = (a, y - 15.0, b, y + 0.5)
            if b - a >= 24 and word_cover(r) < 0.25:
                cands.append({"kind": "text", "rect": r})
    # filtrar: nada sobre campos existentes, sin duplicados
    out: list[dict] = []
    for c in cands:
        r = c["rect"]
        if any(_iou_like(r, e) > 0.3 for e in existing):
            continue
        if any(_iou_like(r, o["rect"]) > 0.6 for o in out):
            continue
        out.append(c)
    out.sort(key=lambda c: (round(c["rect"][1] / 6), c["rect"][0]))
    return out[:150]


def detect_all(doc) -> dict:
    """{página: [candidatos]} de todo el documento."""
    res = {}
    for i in range(len(doc)):
        c = detect_fields(doc, i)
        if c:
            res[i] = c
    return res


def create_detected(doc, found: dict) -> int:
    n = 0
    for pi, items in found.items():
        for c in items:
            base = {"text": "texto", "multiline": "notas", "checkbox": "casilla"}.get(c["kind"], "campo")
            if add_field(doc, pi, c["rect"], {"kind": c["kind"], "name": base, "box": c.get("box", False)}):
                n += 1
    return n


# ── Orden de tabulación ───────────────────────────────────────────────────
TAB_ORDERS = {"R": "Por filas (de izquierda a derecha y de arriba abajo)", "C": "Por columnas",
              "S": "Según la estructura del documento"}


def set_tab_order(doc, order: str) -> int:
    """Orden en que el Tabulador recorre los campos de cada página (R filas, C columnas, S estructura)."""
    if order not in TAB_ORDERS:
        return 0
    n = 0
    for i in range(len(doc)):
        page = doc[i]
        if any(True for _ in (page.widgets() or [])):
            doc.xref_set_key(page.xref, "Tabs", "/" + order)
            n += 1
    return n


def get_tab_order(doc) -> str | None:
    for i in range(len(doc)):
        page = doc[i]
        if any(True for _ in (page.widgets() or [])):
            kind, val = doc.xref_get_key(page.xref, "Tabs")
            return val.lstrip("/") if kind != "null" else None
    return None


# ── Grupos de botones de opción (PyMuPDF no sabe crearlos: se construyen a mano) ──
def _circle_ops(cx: float, cy: float, r: float) -> str:
    k = 0.5523 * r
    return (f"{cx + r:.2f} {cy:.2f} m {cx + r:.2f} {cy + k:.2f} {cx + k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c "
            f"{cx - k:.2f} {cy + r:.2f} {cx - r:.2f} {cy + k:.2f} {cx - r:.2f} {cy:.2f} c "
            f"{cx - r:.2f} {cy - k:.2f} {cx - k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
            f"{cx + k:.2f} {cy - r:.2f} {cx + r:.2f} {cy - k:.2f} {cx + r:.2f} {cy:.2f} c h ")


def _form_stream(doc, w: float, h: float, ops: str) -> int:
    x = doc.get_new_xref()
    doc.update_object(x, f"<< /Type /XObject /Subtype /Form /BBox [0 0 {w:.2f} {h:.2f}] /Resources << >> >>")
    doc.update_stream(x, ops.encode())
    return x


def add_radio_group(doc, page_idx: int, name: str, options: list, origin: tuple, spacing: float = 22.0,
                    size: float = 14.0, font_size: float = 11.0) -> bool:
    """Grupo de botones de opción en vertical a partir de `origin` (esquina superior izquierda del primero),
    con su texto a la derecha. Solo se puede elegir uno."""
    options = [o.strip() for o in options if o and o.strip()]
    if len(options) < 2:
        return False
    page = doc[page_idx]
    try:
        inv = ~page.transformation_matrix
        parent = doc.get_new_xref()
        doc.update_object(parent, "<< >>")
        kids = []
        for i, label in enumerate(options):
            top = origin[1] + i * spacing
            r_pdf = fitz.Rect(origin[0], top, origin[0] + size, top + size) * inv
            r_pdf.normalize()
            w, h = r_pdf.width, r_pdf.height
            cx, cy, rad = w / 2, h / 2, min(w, h) / 2 - 1
            base = "q 0.93 0.96 1 rg 0.35 G 1 w " + _circle_ops(cx, cy, rad) + " B "
            off = _form_stream(doc, w, h, base + "Q")
            on = _form_stream(doc, w, h, base + "0.1 g " + _circle_ops(cx, cy, rad * 0.5) + " f Q")
            kid = doc.get_new_xref()
            doc.update_object(kid, f"<< /Type /Annot /Subtype /Widget /Rect [{r_pdf.x0:.2f} {r_pdf.y0:.2f} {r_pdf.x1:.2f} "
                                   f"{r_pdf.y1:.2f}] /F 4 /NM (pdfm-field) /Parent {parent} 0 R /P {page.xref} 0 R "
                                   f"/MK << /BC [0.35 0.35 0.35] /BG [0.93 0.96 1] >> /AS /Off "
                                   f"/AP << /N << /Op{i + 1} {on} 0 R /Off {off} 0 R >> >> >>")
            kids.append(kid)
        safe = re.sub(r"[()\\]", "", unique_name(doc, name))
        doc.update_object(parent, f"<< /FT /Btn /Ff 49152 /T ({safe}) /V /Off /Kids [" +
                          " ".join(f"{k} 0 R" for k in kids) + "] >>")
        items = " ".join(f"{k} 0 R" for k in kids)
        ann = doc.xref_get_key(page.xref, "Annots")
        if ann[0] == "array":
            doc.xref_set_key(page.xref, "Annots", ann[1][:-1] + " " + items + "]")
        elif ann[0] == "xref":
            ax = int(ann[1].split()[0])
            cur = doc.xref_object(ax)
            doc.update_object(ax, cur[:cur.rindex("]")] + " " + items + "]")
        else:
            doc.xref_set_key(page.xref, "Annots", "[" + items + "]")
        cat = doc.pdf_catalog()
        af = doc.xref_get_key(cat, "AcroForm")
        if af[0] == "null":
            axf = doc.get_new_xref()
            doc.update_object(axf, f"<< /Fields [{parent} 0 R] >>")
            doc.xref_set_key(cat, "AcroForm", f"{axf} 0 R")
        elif af[0] == "xref":
            axf = int(af[1].split()[0])
            fl = doc.xref_get_key(axf, "Fields")
            if fl[0] == "array":
                doc.xref_set_key(axf, "Fields", fl[1][:-1] + f" {parent} 0 R]")
            else:
                doc.xref_set_key(axf, "Fields", f"[{parent} 0 R]")
        else:                                                      # AcroForm escrito dentro del catálogo
            fl = doc.xref_get_key(cat, "AcroForm/Fields")
            if fl[0] == "array":
                doc.xref_set_key(cat, "AcroForm/Fields", fl[1][:-1] + f" {parent} 0 R]")
            else:
                doc.xref_set_key(cat, "AcroForm/Fields", f"[{parent} 0 R]")
        page = doc[page_idx]                                      # recarga la página con lo nuevo
        for i, label in enumerate(options):
            top = origin[1] + i * spacing
            page.insert_text((origin[0] + size + 8, top + size - 2.5), label, fontsize=font_size)
        return True
    except Exception:
        return False
