# -*- coding: utf-8 -*-
"""
photo_fix.py — Corrige una foto de un documento: encuentra las cuatro esquinas del papel (o se las das tú),
estira la página para que quede plana y rectangular (corrige la perspectiva) y, si quieres, aclara el fondo y la
iluminación. Solo trabaja bien con papel plano: una hoja muy arrugada o curvada no se puede aplanar así.
Sin dependencias de interfaz (numpy, Pillow y PyMuPDF).
"""
import io
import math

import numpy as np
from PIL import Image, ImageFilter

import pdf_tools as pt

A4_RATIO = 297 / 210          # alto / ancho
LETTER_RATIO = 11 / 8.5


# ── geometría ────────────────────────────────────────────────────────────
def order_corners(pts) -> list:
    """Ordena cuatro puntos como [arriba-izq, arriba-der, abajo-der, abajo-izq]."""
    p = [tuple(map(float, q)) for q in pts]
    tl = min(p, key=lambda q: q[0] + q[1])
    br = max(p, key=lambda q: q[0] + q[1])
    tr = max(p, key=lambda q: q[0] - q[1])
    bl = min(p, key=lambda q: q[0] - q[1])
    return [tl, tr, br, bl]


def _area(pts) -> float:
    s = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


def is_convex(pts) -> bool:
    sign = 0
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) < 1e-6:
            continue
        s = 1 if cr > 0 else -1
        if sign and s != sign:
            return False
        sign = s
    return True


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def target_size(corners, snap: str = "auto", max_side: int = 3300) -> tuple:
    """Tamaño (ancho, alto) en píxeles de la página corregida. snap: 'auto' (ajusta a A4/Carta si se parece),
    'A4', 'Carta' o 'medido' (las proporciones medidas en la foto)."""
    tl, tr, br, bl = corners
    w = max(_dist(tl, tr), _dist(bl, br))
    h = max(_dist(tl, bl), _dist(tr, br))
    portrait = h >= w
    short, long = (w, h) if portrait else (h, w)
    r = long / max(short, 1.0)
    target = None
    if snap == "A4" or (snap == "auto" and abs(r - A4_RATIO) < 0.2):
        target = A4_RATIO
    elif snap == "Carta" or (snap == "auto" and abs(r - LETTER_RATIO) < 0.1):
        target = LETTER_RATIO
    if target:
        long = short * target
    ww, hh = (short, long) if portrait else (long, short)
    k = min(1.0, max_side / max(ww, hh))
    return max(int(ww * k), 50), max(int(hh * k), 50)


def perspective_coeffs(src: list, dst: list) -> list:
    """Coeficientes de PIL (salida → origen) que llevan los puntos `dst` a los puntos `src`."""
    a, b = [], []
    for (xd, yd), (xs, ys) in zip(dst, src):
        a.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd])
        a.append([0, 0, 0, xd, yd, 1, -ys * xd, -ys * yd])
        b += [xs, ys]
    return [float(v) for v in np.linalg.solve(np.array(a, dtype=np.float64), np.array(b, dtype=np.float64))]


def warp(img: Image.Image, corners: list, size: tuple) -> Image.Image:
    """Estira el cuadrilátero `corners` (de la imagen) a un rectángulo de `size`."""
    w, h = size
    coeffs = perspective_coeffs(corners, [(0, 0), (w, 0), (w, h), (0, h)])
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(255, 255, 255)
                         if img.mode == "RGB" else 255)


# ── detección de las esquinas ────────────────────────────────────────────
def _dilate(m):
    d = m.copy()
    d[1:] |= m[:-1]
    d[:-1] |= m[1:]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def _region_from(mask, seed):
    reach = np.zeros_like(mask)
    reach[seed] = True
    for _ in range(max(mask.shape) * 2):
        nxt = _dilate(reach) & mask
        if (nxt == reach).all():
            break
        reach = nxt
    return reach


def _boundary(reg):
    er = reg.copy()
    er[1:] &= reg[:-1]
    er[:-1] &= reg[1:]
    er[:, 1:] &= reg[:, :-1]
    er[:, :-1] &= reg[:, 1:]
    return reg & ~er


def _fit_line(points):
    """Recta de mínimos cuadrados totales por unos puntos: (punto medio, dirección unitaria)."""
    p = np.asarray(points, dtype=np.float64)
    c = p.mean(axis=0)
    _u, _s, vt = np.linalg.svd(p - c, full_matrices=False)
    return c, vt[0]


def _intersect(l1, l2):
    (c1, d1), (c2, d2) = l1, l2
    m = np.array([[d1[0], -d2[0]], [d1[1], -d2[1]]])
    if abs(np.linalg.det(m)) < 1e-9:
        return None
    s = np.linalg.solve(m, c2 - c1)
    return tuple(c1 + s[0] * d1)


def _refine(reg, pts):
    """Afina las esquinas ajustando una recta a cada lado del contorno de la zona y cortando las rectas contiguas."""
    by, bx = np.nonzero(_boundary(reg))
    bp = np.stack([bx, by], axis=1).astype(np.float64)
    diag = math.hypot(*reg.shape)
    lines = []
    for i in range(4):
        p0, p1 = np.array(pts[i]), np.array(pts[(i + 1) % 4])
        d = p1 - p0
        L = np.linalg.norm(d)
        if L < 4:
            return pts
        u = d / L
        n = np.array([-u[1], u[0]])
        rel = bp - p0
        along, off = rel @ u, rel @ n
        sel = (along > 0.12 * L) & (along < 0.88 * L) & (np.abs(off) < 0.04 * diag + 2)
        if sel.sum() < 12:
            return pts
        lines.append(_fit_line(bp[sel]))
    new = []
    for i in range(4):
        q = _intersect(lines[i - 1], lines[i])
        if q is None or math.hypot(q[0] - pts[i][0], q[1] - pts[i][1]) > 0.08 * diag:
            return pts
        new.append(q)
    return new


def _edges_have_contrast(gray, pts, min_diff: float = 14.0) -> bool:
    """Comprueba que a lo largo de cada lado del cuadrilátero el papel (dentro) se distingue del fondo (fuera)."""
    h, w = gray.shape
    cx, cy = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])
    ok = 0
    for i in range(4):
        p0, p1 = np.array(pts[i]), np.array(pts[(i + 1) % 4])
        mid_x, mid_y = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        on_border = (min(mid_x, w - mid_x) < 0.03 * w) or (min(mid_y, h - mid_y) < 0.03 * h)
        d = p1 - p0
        L = np.linalg.norm(d)
        u = d / max(L, 1e-6)
        n = np.array([-u[1], u[0]])
        if (n[0] * (cx - mid_x) + n[1] * (cy - mid_y)) < 0:
            n = -n                                          # n apunta hacia dentro
        ins, outs = [], []
        for s in np.linspace(0.15, 0.85, 16):
            q = p0 + d * s
            for off, bucket in ((6, ins), (-6, outs)):
                x, y = int(round(q[0] + n[0] * off)), int(round(q[1] + n[1] * off))
                if 0 <= x < w and 0 <= y < h:
                    bucket.append(float(gray[y, x]))
        if on_border and not outs:
            ok += 1
            continue
        if ins and outs and abs(np.mean(ins) - np.mean(outs)) >= min_diff:
            ok += 1
    return ok >= 4 or (ok >= 3 and any(min(p[0], w - p[0]) < 0.03 * w or min(p[1], h - p[1]) < 0.03 * h for p in pts))


def detect_corners(img: Image.Image) -> list | None:
    """Esquinas del papel en píxeles de la imagen ([TL, TR, BR, BL]), o None si no se distingue el papel del fondo
    (entonces hay que marcarlas a mano). Busca la zona clara (u oscura) que contiene el centro, toma sus extremos y
    los afina ajustando una recta a cada lado; después comprueba que el papel se distingue del fondo en los cuatro lados."""
    w0, h0 = img.size
    scale = 320.0 / max(w0, h0)
    small = img.convert("L").resize((max(8, int(w0 * scale)), max(8, int(h0 * scale))))
    small = small.filter(ImageFilter.GaussianBlur(2.0))
    a = np.asarray(small)
    thr = pt._otsu(a)
    h, w = a.shape
    best = None
    for bright in (True, False):
        mask = (a > thr) if bright else (a <= thr)
        cy, cx = h // 2, w // 2
        win = mask[cy - h // 10:cy + h // 10 + 1, cx - w // 10:cx + w // 10 + 1]
        if win.mean() < 0.5:                                  # el centro no pertenece a esta clase
            continue
        seed = (cy, cx) if mask[cy, cx] else tuple(np.argwhere(win)[0] + [cy - h // 10, cx - w // 10])
        reg = _region_from(mask, seed)
        frac = reg.mean()
        if 0.15 < frac < 0.97 and (best is None or frac > best[0]):
            best = (frac, reg)
    if best is None:
        return None
    reg = best[1]
    ys, xs = np.nonzero(reg)
    pts = order_corners([(xs[np.argmin(xs + ys)], ys[np.argmin(xs + ys)]), (xs[np.argmax(xs - ys)], ys[np.argmax(xs - ys)]),
                         (xs[np.argmax(xs + ys)], ys[np.argmax(xs + ys)]), (xs[np.argmin(xs - ys)], ys[np.argmin(xs - ys)])])
    pts = _refine(reg, pts)
    if not is_convex(pts) or _area(pts) < 0.12 * w * h:
        return None
    if not _edges_have_contrast(a.astype(np.float32), pts):
        return None
    return [(x / scale, y / scale) for x, y in pts]


# ── iluminación ──────────────────────────────────────────────────────────
def flatten_light(img: Image.Image) -> Image.Image:
    """Aclara el fondo y reparte la luz (quita sombras suaves): divide cada canal por su fondo desenfocado."""
    w, h = img.size
    k = max(1, int(max(w, h) / 600))
    small = img.resize((w // k, h // k), Image.BILINEAR)
    # el fondo es lo más claro de cada zona: se suaviza el máximo local para no «comerse» el texto
    bg = small.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(max(w, h) / (30.0 * k)))
    bg = bg.resize((w, h), Image.BILINEAR)
    a = np.asarray(img, dtype=np.float32)
    b = np.maximum(np.asarray(bg, dtype=np.float32), 30.0)
    out = np.clip(a / b * 245.0, 0, 255)
    return Image.fromarray(out.astype(np.uint8), img.mode)


# ── página del PDF ───────────────────────────────────────────────────────
def render_page(doc, page_idx: int, max_dpi: int = 300, max_px: int = 4200) -> Image.Image:
    """La página como imagen, a la resolución de su foto (sin pasarse)."""
    page = doc[page_idx]
    nat = pt.native_dpi(page) or 150
    dpi = int(min(max(nat, 72), max_dpi))
    k = dpi / 72.0
    if max(page.rect.width, page.rect.height) * k > max_px:
        dpi = int(max_px / max(page.rect.width, page.rect.height) * 72)
    pix = page.get_pixmap(dpi=max(dpi, 72), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _paper_fill(img: Image.Image) -> tuple:
    arr = np.asarray(img.convert("RGB")).reshape(-1, 3)
    return tuple(int(v) for v in np.percentile(arr, 85, axis=0))


def _line_slopes(gray: Image.Image, nwin: int = 7) -> list:
    """[(y centro, grados, confianza)] de la inclinación de las líneas de texto en franjas horizontales de la página."""
    h = gray.height
    wh = max(40, int(h * 0.27))
    out = []
    for k in range(nwin):
        c = h * (0.1 + 0.8 * k / (nwin - 1))
        y0, y1 = int(max(0, c - wh / 2)), int(min(h, c + wh / 2))
        if y1 - y0 < 30:
            continue
        ang, conf = pt._deskew_scan(gray.crop((0, y0, gray.width, y1)), 12.0)
        out.append(((y0 + y1) / 2.0, ang, conf))
    return out


def keystone_straighten(img: Image.Image, slope_of_y, bands: int = 48) -> Image.Image:
    """Endereza un texto cuya inclinación cambia de arriba a abajo (foto hecha con el móvil en ángulo): cada franja
    horizontal se corrige con su propia inclinación, de forma continua, y las líneas quedan todas horizontales."""
    w, h = img.size
    xc = w / 2.0
    mesh = []
    for i in range(bands):
        y0, y1 = int(round(h * i / bands)), int(round(h * (i + 1) / bands))
        if y1 <= y0:
            continue
        t0 = math.tan(math.radians(slope_of_y(y0)))
        t1 = math.tan(math.radians(slope_of_y(y1)))
        quad = (0, y0 + t0 * (0 - xc), 0, y1 + t1 * (0 - xc), w, y1 + t1 * (w - xc), w, y0 + t0 * (w - xc))
        mesh.append(((0, y0, w, y1), quad))
    return img.transform((w, h), Image.MESH, mesh, Image.BICUBIC, fillcolor=_paper_fill(img))


def straighten_text(img: Image.Image) -> tuple:
    """Deja horizontales las líneas de texto, tomando como guía la base de las letras. Mide la inclinación en varias
    franjas: si es la misma en toda la página, la gira; si cambia de arriba a abajo (foto con perspectiva), corrige cada
    franja con la suya. Devuelve (imagen, grados de la mayor corrección); si ya está recto, la imagen igual y 0."""
    gray = img.convert("L")
    pts = [(y, a, c) for y, a, c in _line_slopes(gray) if c >= 1.8]       # franjas con líneas de texto claras
    if len(pts) < 2:                                                      # poco texto: una sola medida en toda la página
        ang, conf = pt._deskew_scan(gray, 12.0)
        if abs(ang) < 0.25 or conf < 1.3:
            return img, 0.0
        return img.rotate(ang, resample=Image.BICUBIC, expand=False, fillcolor=_paper_fill(img)), float(ang)
    ys = np.array([p[0] for p in pts]); an = np.array([p[1] for p in pts]); wt = np.array([p[2] for p in pts])
    slope, icpt = np.polyfit(ys, an, 1, w=wt)                              # inclinación ≈ icpt + slope·y
    fit = icpt + slope * ys
    h = img.height
    span = abs(slope) * h
    resid = float(np.max(np.abs(an - fit)))
    if span >= 0.8 and resid <= 1.2:                                       # cambia de arriba a abajo: por franjas
        def f(y):
            return float(np.clip(icpt + slope * y, -12, 12))
        out = keystone_straighten(img, f)
        biggest = max((f(0), f(h)), key=abs)
        return out, float(biggest)
    ang = float(np.average(an, weights=wt))                                # igual en toda la página: un giro
    if abs(ang) < 0.25:
        return img, 0.0
    return img.rotate(ang, resample=Image.BICUBIC, expand=False, fillcolor=_paper_fill(img)), ang


def _fix_one(doc, page_idx: int, corners_frac, snap: str, flatten: bool, straighten: bool, force: bool):
    """Endereza UNA página del documento abierto: perspectiva (con las esquinas dadas, o buscadas solas si no se dan),
    líneas de texto horizontales y fondo aclarado, y la sustituye en `doc`. Devuelve {"size", "angle", "warped"} o None
    si no hacía falta tocarla (sin esquinas y con el texto ya recto), salvo con `force`."""
    img = render_page(doc, page_idx)
    corners = None
    if corners_frac:
        corners = order_corners([(x * img.width, y * img.height) for x, y in corners_frac])
        if not is_convex(corners) or _area(corners) < 0.02 * img.width * img.height:
            raise pt.ToolError("Las esquinas no forman un cuadrilátero válido: colócalas en las cuatro esquinas del papel.")
    elif corners_frac is None:
        corners = detect_corners(img)                          # si el papel no se distingue del fondo, se sigue sin esquinas
    size, flat, angle = img.size, img, 0.0
    if corners:
        size = target_size(corners, snap)
        flat = warp(img, corners, size)
    if straighten:                                             # después de la perspectiva: alinear las líneas de texto
        flat, angle = straighten_text(flat)
    if not force and not corners and abs(angle) < 0.25:
        return None
    if flatten:
        flat = flatten_light(flat)
    buf = io.BytesIO()
    flat.save(buf, "JPEG", quality=90, optimize=True)
    k = 841.89 / max(size)
    new = doc.new_page(pno=page_idx + 1, width=size[0] * k, height=size[1] * k)
    new.insert_image(new.rect, stream=buf.getvalue())
    doc.delete_page(page_idx)
    return {"size": size, "angle": float(angle), "warped": bool(corners)}


def straighten_pages(path: str, password: str = "", only_scanned: bool = True, flatten: bool = True,
                     manual: dict | None = None, progress=None) -> tuple:
    """Endereza las páginas de un PDF hecho con fotos o escaneos (esquinas buscadas solas, o las que se marcaron a mano
    en `manual` = {página: esquinas}) y guarda el resultado en una carpeta temporal con el mismo nombre. Las páginas
    que ya están rectas no se tocan. Devuelve (ruta, [(página, grados girados, ¿perspectiva?)])."""
    import tempfile
    from pathlib import Path
    manual = manual or {}
    doc = pt._open(path, password)
    changed = []
    try:
        pages = pt.ocr_needed_pages(doc) if only_scanned else list(range(len(doc)))
        for k, i in enumerate(pages):
            if progress:
                progress(k, len(pages) * 2)
            try:
                r = _fix_one(doc, i, manual.get(i), "auto", flatten, True, i in manual)
            except pt.ToolError:
                r = None
            if r:
                changed.append((i, r["angle"], r["warped"]))
        dest = Path(tempfile.mkdtemp(prefix="pdfm_str_")) / (Path(path).stem + ".pdf")
        doc.save(str(dest), garbage=3, deflate=True)
    finally:
        doc.close()
    return str(dest), changed


def ocr_straight(path: str, languages: list, dpi: int = 200, only_scanned: bool = True, password: str = "",
                 progress=None, enhance: bool = True, straighten: bool = True, flatten: bool = True,
                 manual: dict | None = None, precise: bool = False, engine: str = "tesseract",
                 review: bool = False) -> dict:
    """OCR con enderezado opcional en el mismo paso: primero se endereza cada página (perspectiva y líneas de texto) y
    después se reconoce el texto sobre la página ya recta."""
    if not straighten:
        return pt.ocr(path, languages, dpi, only_scanned, password, progress=progress, enhance=enhance, precise=precise,
                      engine=engine, review=review)
    tmp, changed = straighten_pages(path, password, only_scanned, flatten, manual, progress)
    try:
        res = pt.ocr(tmp, languages, dpi, only_scanned, "",
                     progress=(lambda i, n: progress(n + i, n * 2)) if progress else None, enhance=enhance,
                     precise=precise, engine=engine, review=review)
    except pt.ToolError:
        raise
    res["straightened"] = len(changed)
    res["angles"] = [round(a, 1) for _i, a, _w in changed]
    return res
