# -*- coding: utf-8 -*-
"""Vista del editor de páginas (lienzo con texto, anotaciones, formularios y firmas)."""

from PySide6.QtCore import Qt, QSize, QRectF, QTimer, QEvent, QPoint, QPointF, Signal
from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QPainter,
    QColor,
    QFont,
    QFontMetrics,
    QPen,
    QBrush,
    QCursor,
    QFontDatabase,
    QTextBlockFormat,
    QTextCursor,
    QTextCharFormat,
    QTextFormat,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QListWidgetItem,
    QFrame,
    QSpinBox,
    QDialog,
    QAbstractItemView,
    QGraphicsDropShadowEffect,
    QMenu,
    QTextEdit,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QColorDialog,
    QGridLayout,
)

import backend as be
import icons as ic
import winfonts
import annot_tools as at
import form_tools as ft
import click_icons as ci
from theme import SURFACE, SURFACE_2, SURFACE_3, TEXT, TEXT_SOFT, ACCENT, BORDER_STRONG
from i18n import tr
from ui.common import ICON_DARK
from ui.editor_parts import (
    HeaderFooterDialog,
    LINK_COLORS,
    SelectionBar,
    SpanRectItem,
    _FieldEditor,
    _PROP_FAMILY,
    _PROP_FONT,
    _PROP_SIZE,
    _Swatch,
    _ToolBar,
    _ToolPopup,
    _VirtualItem,
    _popup_list,
    _toggle_icon,
    fitz_rect,
)


class GutterPlusItem(QGraphicsItem):
    """Botón «+» entre dos páginas (vista general): inserta una página en ese hueco."""
    D = 24

    def __init__(self, at_idx: int, callback):
        super().__init__()
        self.at_idx, self.cb, self._hover = at_idx, callback, False
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("Insertar una página aquí"))

    def boundingRect(self):
        return QRectF(-1, -1, self.D + 2, self.D + 2)

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(ACCENT if self._hover else SURFACE_3))
        p.setPen(QPen(QColor(ACCENT), 1.5))
        p.drawEllipse(QRectF(0, 0, self.D, self.D))
        p.setPen(QPen(QColor(ICON_DARK if self._hover else TEXT), 2))
        c, a = self.D / 2, self.D * 0.27
        p.drawLine(QPointF(c - a, c), QPointF(c + a, c))
        p.drawLine(QPointF(c, c - a), QPointF(c, c + a))

    def hoverEnterEvent(self, e):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.cb("insert", self.at_idx)


class PageBarItem(QGraphicsItem):
    """Barra de acciones de una página (borrar, acercar, alejar, girar, insertar). Se dibuja y atiende los clics ella
    misma, sin widgets incrustados (esos daban cierres bruscos al recargar la escena)."""
    H = 26

    def __init__(self, idx: int, last: bool, callback, compact: bool = False):
        super().__init__()
        self.idx, self.last, self.cb, self.compact = idx, last, callback, compact
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = None
        self._btns = []          # (rect, acción, texto, icono, ayuda)
        x = 0.0
        bw = 28 if compact else 38
        if not last:
            x = 24.0 if compact else 34.0             # sitio para el número de página
            acts = [("delete", "", "trash", tr("Borrar esta página"))]
            if not compact:
                acts += [("zoomin", "+", None, tr("Acercar")), ("zoomout", "−", None, tr("Alejar"))]
            acts += [("rotl", "", "rot_left", tr("Girar a la izquierda")), ("rotr", "", "rot_right", tr("Girar a la derecha"))]
            for act, txt, icon, tip in acts:
                self._btns.append((QRectF(x, 0, bw, self.H), act, txt, icon, tip))
                x += bw
            x += 6 if compact else 14
        if compact:
            self.width_ = x - 6                          # en la vista general «insertar» va entre páginas
        else:
            self._btns.append((QRectF(x, 0, 150, self.H), "insert", tr("Insertar página aquí"), "plus",
                               tr("Insertar una página aquí")))
            self.width_ = x + 150

    def boundingRect(self):
        return QRectF(-1, -1, self.width_ + 2, self.H + 2)

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.Antialiasing, False)
        if not self.last:
            p.setPen(QColor(ACCENT))
            f = p.font(); f.setPixelSize(14 if self.compact else 20); p.setFont(f)
            p.drawText(QRectF(0, 0, 26, self.H), Qt.AlignVCenter | Qt.AlignLeft, str(self.idx + 1))
        f = p.font(); f.setPixelSize(12); p.setFont(f)
        for i, (r, act, txt, icon, tip) in enumerate(self._btns):
            p.setBrush(QColor(SURFACE_3 if self._hover == i else SURFACE))
            p.setPen(QColor(BORDER_STRONG))
            p.drawRect(r)
            p.setPen(QColor(TEXT))
            if icon:
                isz = 19 if icon in ("rot_left", "rot_right") else 15
                pm = ic.icon(icon, TEXT, isz).pixmap(isz, isz)
                if txt:
                    p.drawPixmap(int(r.left() + 10), int(r.center().y() - 7), pm)
                    p.drawText(r.adjusted(30, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, txt)
                else:
                    p.drawPixmap(int(r.center().x() - pm.width() / 2), int(r.center().y() - pm.height() / 2), pm)
            else:
                f2 = p.font(); f2.setPixelSize(16); p.setFont(f2)
                p.drawText(r, Qt.AlignCenter, txt)
                p.setFont(f)

    def _at(self, pos):
        for i, b in enumerate(self._btns):
            if b[0].contains(pos):
                return i
        return None

    def hoverMoveEvent(self, e):
        i = self._at(e.pos())
        if i != self._hover:
            self._hover = i
            self.setToolTip(self._btns[i][4] if i is not None else "")
            self.update()

    def hoverLeaveEvent(self, e):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        i = self._at(e.pos())
        if i is not None and e.button() == Qt.LeftButton:
            self.cb(self._btns[i][1], self.idx)


class PageEditorView(QGraphicsView):
    """Muestra TODAS las páginas apiladas verticalmente (scroll continuo),
    con cada fragmento de texto clicable; al clicar, abre un QLineEdit
    flotando justo encima para editarlo in situ."""
    mode_changed = Signal(str)
    page_action = Signal(str, int)
    shape_kind_changed = Signal(str)
    icon_picker_requested = Signal()                  # clic sobre un icono de «clic aquí» ya seleccionado
    save_signature_requested = Signal(object)         # descripción del dibujo libre que se guarda como firma
    replace_requested = Signal(str)                   # texto sobre el que se pidió «Reemplazar…» con el clic derecho
    link_requested = Signal(int, object, object)      # página, cajas (puntos PDF) o None, enlace existente o None
    field_requested = Signal(int, object)             # página y caja (puntos PDF) donde crear un campo nuevo
    copy_requested = Signal(int, object, object)      # página, caja (puntos PDF) o None, punto del clic o None
    zoomed = Signal(float)
    note_requested = Signal(int, object, object)      # página, punto PDF, nota existente o None
    attach_clicked = Signal(int, object, object)      # página, adjunto, posición global del clic
    ZOOM_MIN, ZOOM_MAX = 0.2, 4.0

    def __init__(self, on_dirty, on_font_missing, on_page_visible=None, on_before_mutate=None,
                 on_notice=None):
        super().__init__()
        # Atributos primero: setStyleSheet/setScene ya pueden disparar
        # eventos que pasan por nuestro eventFilter antes de seguir aquí.
        self._on_notice = on_notice
        self.hf = None          # ajustes de cabecera/pie de este documento (None = detección automática)
        self.manual = False     # True: cada línea es una unidad y no se deduce ni se mueve nada
        self._text0 = ""
        self._on_dirty = on_dirty
        self._on_font_missing = on_font_missing
        self._on_page_visible = on_page_visible
        self._on_before_mutate = on_before_mutate
        self.doc = None
        self.zoom = 1.6
        self._editor: QTextEdit | None = None
        self._editing_item: SpanRectItem | None = None
        self._toolbar: QFrame | None = None
        self._dialog_open = False
        self._page_items: list = []
        self._page_span_items: list[list] = []
        self._page_tops: list[float] = []
        self._current_page = 0
        self._page_gap = 52
        self._cols = 1                      # páginas por fila (más de 1 con el zoom muy alejado)
        self._bar_press = False
        self._bar_h = 34
        self.mode = "edit"                 # "edit" | "censor"
        self._censor_drag_start: QPointF | None = None
        self._censor_rect_item = None
        self.markup_kind = "highlight"     # highlight | underline | strike | erase
        self.markup_color = None           # nombre en annot_tools.COLORS (None = el de la herramienta)
        self._mk_page = None               # página donde empezó el arrastre
        self._mk_start = None              # punto PDF inicial
        self._mk_words: list = []
        self._mk_preview: list = []
        self.shape_kind = "rect"           # rect | ellipse | line | arrow
        self.shape_color = "rojo"
        self.shape_width = 2.0
        self.shape_fill = None             # None = sin relleno
        self.shape_opacity = 1.0           # opacidad total (1 = sólido)
        self.shape_stroke_op = None        # opacidad solo del trazo (None = la total)
        self.shape_fill_op = None          # opacidad solo del relleno (None = la total)
        self.shape_head = "closed"         # forma de la punta de las flechas
        self._pressure = None              # presión del lápiz óptico (None = ratón)
        self._sh_pressures: list = []
        self._eraser_hit = None
        self._eyedrop = None               # función a llamar con el color tomado de la página (cuentagotas)
        self._sh_page = None
        self._sh_start = None              # punto PDF donde empezó el arrastre
        self._sh_move = None               # forma existente que se está moviendo
        self._sh_preview: list = []
        self._sh_stroke: list = []         # puntos del trazo libre en curso (lápiz / rotulador)
        self._ss_sel = None                # forma/trazo seleccionado: {"page", "desc"}
        self._ss_drag = None               # arrastre en curso sobre la selección
        self._lk_items: list = []          # recuadros de los enlaces existentes (modo enlaces)
        self._fm_items: list = []          # recuadros de los campos de formulario (modo formulario)
        self._fm_cache: dict = {}          # página -> campos
        self._fm_editor = None             # caja de texto abierta sobre un campo
        self._fm_down = None               # clic en curso
        self._fm_rubber = None
        self._cp_down = None               # clic o arrastre en curso del modo «copiar»
        self._cp_rubber = None
        self._fm_sel = None                # campo propio seleccionado: {"page","xref","rect","kind"}
        self._reload_cb = None             # la pantalla recarga el documento (hace falta al crear botones de opción)
        self.hide_annots = False           # ver el PDF sin sus anotaciones (solo la vista; no cambia el archivo)
        self.pending_attach = None         # ruta del archivo a adjuntar con el próximo clic
        self._nt_down = None
        self.pending_image = None          # imagen (ruta o bytes) a colocar con el próximo clic
        self._pending_frac = 0.45          # ancho máximo inicial, como fracción del ancho de la página
        self._img_size = (1, 1)
        self._img_sel = None               # {"page", "xref", "rect"} del sello seleccionado (puntos PDF)
        self._img_items: list = []         # marco y tiradores de la selección
        self._img_drag = None              # {"op": "move"|"place"|nw|ne|sw|se, "start", "rect0"}

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setStyleSheet(f"background:{SURFACE}; border:none; border-radius:10px;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._zoom_pending = None
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.timeout.connect(lambda: self.set_zoom(self._zoom_pending))
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.verticalScrollBar().valueChanged.connect(self._update_current_page)
        self._sel_bar = SelectionBar(self)
        self.verticalScrollBar().valueChanged.connect(lambda _=0: self._update_sel_bar())
        self.horizontalScrollBar().valueChanged.connect(lambda _=0: self._update_sel_bar())

    def page_count(self) -> int:
        return len(self._page_items)

    def set_mode(self, mode: str):
        self.mode = mode
        self.viewport().setCursor({"censor": Qt.CrossCursor, "text": Qt.IBeamCursor, "markup": Qt.IBeamCursor,
                                   "shape": Qt.CrossCursor, "link": Qt.IBeamCursor, "note": Qt.CrossCursor, "copy": Qt.CrossCursor,
                                   "attach": Qt.CrossCursor}.get(mode, Qt.ArrowCursor))
        for page_items in self._page_span_items:
            for item in page_items:
                item.setVisible(item.kind == mode)
        self._mk_clear_preview()
        self._attach_ghost_clear()
        self._sh_clear()
        self._ss_sel, self._ss_drag = None, None
        self._update_sel_bar()
        self._fm_sel = None
        if mode != "image":
            self.pending_image = None
            self._img_select(None)
        self._lk_refresh()
        self._fm_close(False)
        self._fm_refresh()
        if mode != "attach":
            self.pending_attach = None
        if self.hide_annots and mode != "edit":              # al usar una herramienta, las anotaciones vuelven a verse
            self.hide_annots = False
            QTimer.singleShot(0, self.reload_preserving_scroll)
        self.mode_changed.emit(mode)

    # ── Notas y adjuntos ──
    def _nt_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        hit = at.note_at(self.doc, page_idx, pt) if self.mode == "note" else None
        att = None if hit else at.attachment_at(self.doc, page_idx, pt)       # un clip se puede coger desde ambos modos
        self._nt_down = {"page": page_idx, "pt": pt, "hit": hit, "att": att, "moved": False}

    def _clip_pixmap(self) -> QPixmap:
        """El clip tal como quedará, dibujado al tamaño actual del zoom."""
        s = int(round(at.CLIP_SIZE * self.zoom))
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        k = s / at.CLIP_SIZE
        pa.scale(k, k)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.0))
        pa.setBrush(QColor("#212121"))
        pa.drawEllipse(QRectF(0.5, 0.5, 21.0, 21.0))
        pen = QPen(QColor("#FFFFFF"), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        pa.setPen(pen)
        pa.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(8.4, 15.6))                         # mismo dibujo que la apariencia del PDF (y invertida)
        path.lineTo(8.4, 7.8)
        path.cubicTo(8.4, 5.4, 13.2, 5.4, 13.2, 7.8)
        path.lineTo(13.2, 14.8)
        path.cubicTo(13.2, 16.6, 10.2, 16.6, 10.2, 14.8)
        path.lineTo(10.2, 9.0)
        pa.drawPath(path)
        pa.end()
        return pm

    def _attach_ghost_move(self, scene_pos: QPointF):
        """Mientras se coloca un adjunto: el clip (semitransparente) viaja con el ratón, centrado donde se colocará."""
        if self.mode != "attach" or not self.pending_attach or self._page_at_y(scene_pos.y(), quiet=True) is None:
            self._attach_ghost_clear()
            return
        g = getattr(self, "_attach_ghost", None)
        if g is None:
            g = self.scene_.addPixmap(self._clip_pixmap())
            g.setOpacity(0.55)
            g.setZValue(70)
            g.setAcceptedMouseButtons(Qt.NoButton)
            self._attach_ghost = g
        w = g.pixmap().width()
        g.setPos(scene_pos.x() - w / 2, scene_pos.y() - w / 2)
        self.viewport().setCursor(Qt.BlankCursor)

    def _attach_ghost_clear(self):
        g, self._attach_ghost = getattr(self, "_attach_ghost", None), None
        if g is not None:
            try:
                self.scene_.removeItem(g)
            except RuntimeError:
                pass

    def leaveEvent(self, e):
        self._attach_ghost_clear()
        super().leaveEvent(e)

    def _nt_move(self, scene_pos: QPointF):
        self._attach_ghost_move(scene_pos)
        d = self._nt_down
        if d and (d["hit"] or d.get("att")):
            pt = self._mk_pdf_point(scene_pos, d["page"])
            if abs(pt[0] - d["pt"][0]) > 4 or abs(pt[1] - d["pt"][1]) > 4:
                d["moved"] = True
                self.viewport().setCursor(Qt.SizeAllCursor)

    def _nt_release(self, scene_pos: QPointF, global_pos):
        d, self._nt_down = self._nt_down, None
        if not d:
            return
        page_idx = d["page"]
        pt = self._mk_pdf_point(scene_pos, page_idx)
        self.viewport().setCursor(Qt.BlankCursor if (self.mode == "attach" and self.pending_attach) else Qt.CrossCursor)
        if d.get("att"):
            if d["moved"]:                                          # arrastrar el clip: cambia de sitio
                if self._on_before_mutate:
                    self._on_before_mutate()
                if at.move_attachment(self.doc, page_idx, d["att"]["xref"], pt[0] - d["pt"][0], pt[1] - d["pt"][1]):
                    self._on_dirty()
                    self.refresh_page(page_idx)
            else:                                                   # clic: guardar copia o quitar
                self.attach_clicked.emit(page_idx, d["att"], global_pos)
            return
        if self.mode == "note":
            if d["hit"] and d["moved"]:
                if self._on_before_mutate:
                    self._on_before_mutate()
                nx, ny = d["hit"]["pos"][0] + pt[0] - d["pt"][0], d["hit"]["pos"][1] + pt[1] - d["pt"][1]
                if at.move_note(self.doc, page_idx, d["hit"]["xref"], (nx, ny)):
                    self._on_dirty()
                    self.refresh_page(page_idx)
            else:
                self.note_requested.emit(page_idx, pt, d["hit"])
            return
        # modo adjuntar
        att = at.attachment_at(self.doc, page_idx, pt)
        if att:
            self.attach_clicked.emit(page_idx, att, global_pos)
        elif self.pending_attach:
            if self._on_before_mutate:
                self._on_before_mutate()
            if at.add_attachment(self.doc, page_idx, pt, self.pending_attach):
                self._on_dirty()
                self.refresh_page(page_idx)
                self.pending_attach = None
                self._attach_ghost_clear()
                self.set_mode("edit")
                if self._on_notice:
                    self._on_notice(tr("Archivo adjuntado (el clip). Clic en el clip para guardar una copia o quitarlo."))
        elif self._on_notice:
            self._on_notice(tr("Elige antes el archivo: Notas → Adjuntar archivo…"))

    def apply_note(self, page_idx: int, pt, existing, text: str, author: str, remove: bool = False) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        if existing is not None:
            ok = (at.delete_annot_by_xref(self.doc, page_idx, existing["xref"]) if remove
                  else at.update_note(self.doc, page_idx, existing["xref"], text))
        else:
            ok = at.add_note(self.doc, page_idx, pt, text, author)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
        return ok

    def remove_attachment(self, page_idx: int, xref: int) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = at.delete_annot_by_xref(self.doc, page_idx, xref)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
        return ok

    def set_hide_annots(self, hide: bool):
        if self.hide_annots != hide:
            self.hide_annots = hide
            self.reload_preserving_scroll()

    # ── Modo copiar: arrastrar una zona, o hacer clic en un párrafo o tabla ──
    def _cp_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        self._cp_down = {"page": page_idx, "pt": self._mk_pdf_point(scene_pos, page_idx), "moved": False}

    def _cp_move(self, scene_pos: QPointF):
        d = self._cp_down
        if not d:
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if abs(pt[0] - d["pt"][0]) > 4 or abs(pt[1] - d["pt"][1]) > 4:
            d["moved"] = True
        if not d["moved"]:
            return
        if self._cp_rubber is not None:
            self.scene_.removeItem(self._cp_rubber)
        box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
        self._cp_rubber = self.scene_.addRect(self._img_scene_rect(d["page"], box), QPen(QColor(ACCENT), 1.5, Qt.DashLine),
                                              QBrush(QColor(192, 130, 88, 60)))
        self._cp_rubber.setZValue(50)

    def _cp_release(self, scene_pos: QPointF):
        d, self._cp_down = self._cp_down, None
        if self._cp_rubber is not None:
            self.scene_.removeItem(self._cp_rubber)
            self._cp_rubber = None
        if not d:
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if d["moved"]:
            box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
            self.copy_requested.emit(d["page"], box, None)
        else:
            self.copy_requested.emit(d["page"], None, d["pt"])

    def show_copy_highlight(self, page_idx: int, rect):
        """Marca en pantalla la zona que se está copiando (se quita al terminar)."""
        self.clear_copy_highlight()
        if rect is None:
            return
        it = self.scene_.addRect(self._img_scene_rect(page_idx, rect), QPen(QColor(ACCENT), 1.5),
                                 QBrush(QColor(192, 130, 88, 55)))
        it.setZValue(48)
        self._cp_rubber = it

    def clear_copy_highlight(self):
        if self._cp_rubber is not None:
            try:
                self.scene_.removeItem(self._cp_rubber)
            except RuntimeError:
                pass
            self._cp_rubber = None

    # ── Modo formulario: rellenar campos, crear campos nuevos, borrarlos ──
    def _fm_refresh(self):
        for it in self._fm_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._fm_items, self._fm_cache = [], {}
        if self.mode != "form" or not self.doc or self._cols > 1:
            return
        for pi in range(len(self._page_tops)):
            ws = ft.widgets_of(self.doc, pi)
            self._fm_cache[pi] = ws
            for w in ws:
                it = self.scene_.addRect(self._img_scene_rect(pi, w["rect"]), QPen(QColor(70, 140, 255), 1.2, Qt.DashLine),
                                         QBrush(QColor(70, 140, 255, 28)))
                it.setZValue(40)
                it.setToolTip(f"{ft.KIND_LABELS.get(w['kind'], tr('Campo'))}: {w['name']}")
                self._fm_items.append(it)

    def _fm_hit(self, page_idx: int, pt: tuple):
        hit = None
        for w in self._fm_cache.get(page_idx, []):
            r = w["rect"]
            if r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]:
                hit = w
        return hit

    def _fm_close(self, commit: bool):
        ed = self._fm_editor
        if ed is not None:
            ed._finish(commit)

    def _fm_done(self, ed, info, text):
        if self._fm_editor is ed:
            self._fm_editor = None
        ed.hide()
        ed.deleteLater()
        cover, self._fm_cover = getattr(self, "_fm_cover", None), None
        if cover is not None:
            try:
                self.scene_.removeItem(cover)
            except RuntimeError:
                pass
        if info is not None:
            self._fm_set(info["page"], info["xref"], text)

    def _fm_open_editor(self, page_idx: int, w: dict):
        self._fm_close(True)
        vr = self.mapFromScene(self._img_scene_rect(page_idx, w["rect"])).boundingRect()
        # tamaño de letra: el del campo, pero sin pasar de lo que cabe en su altura (si no, el texto se corta y no se ve)
        fs = float(w["fontsize"] or 0) * self.zoom
        if w["multiline"]:
            px = fs if fs > 0 else 14.0 * self.zoom / 1.6
        else:
            fit = max(9.0, (vr.height() - 8) * 0.78)
            px = min(fs, fit) if fs > 0 else min(fit, 15.0)
        ed = _FieldEditor(self.viewport(), str(w["value"] or ""), w["multiline"], px)
        geo = vr.adjusted(-1, -1, 1, 1)
        need = QFontMetrics(ed.font()).height() + 10          # alto mínimo para que se vea la línea entera
        if not w["multiline"] and geo.height() < need:
            geo.setTop(geo.center().y() - need // 2)
            geo.setHeight(need)
        ed.setGeometry(geo)
        if not w["multiline"]:                                  # texto centrado en vertical dentro del campo
            ed.setViewportMargins(3, max(0, (geo.height() - QFontMetrics(ed.font()).height()) // 2), 3, 0)
        else:
            ed.setViewportMargins(3, 2, 3, 2)
        # tapa el valor que ya tenía el campo (con el color de fondo del propio campo) para que no se duplique
        r = self._img_scene_rect(page_idx, w["rect"]).adjusted(2, 2, -2, -2)
        if r.width() > 2 and r.height() > 2 and page_idx < len(self._page_items):
            it = self._page_items[page_idx]
            col = it.pixmap().toImage().pixelColor(max(0, int(r.x() + 1 - it.x())), max(0, int(r.y() + 1 - it.y())))
            cov = self.scene_.addRect(r, QPen(Qt.NoPen), QBrush(col))
            cov.setZValue(44)
            self._fm_cover = cov
        ed.show()
        ed.setFocus()
        ed.selectAll()
        info = {"page": page_idx, "xref": w["xref"]}
        ed.committed.connect(lambda txt, i=info, e=ed: self._fm_done(e, i, txt))
        ed.cancelled.connect(lambda e=ed: self._fm_done(e, None, None))
        ed.tabbed.connect(lambda fwd, i=info: QTimer.singleShot(0, lambda: self._fm_tab(i, fwd)))
        self._fm_editor = ed

    def _fm_tab(self, info: dict, forward: bool):
        """Tab / Mayús+Tab: ya confirmado el campo actual, abre el siguiente (o el anterior) campo de texto, siguiendo el
        orden de tabulación del documento (por filas por defecto, o por columnas)."""
        order = ft.get_tab_order(self.doc) if self.doc is not None else "R"
        items = [(pi, w) for pi, ws in sorted(self._fm_cache.items()) for w in ws
                 if w["kind"] == "text" and not w["readonly"]]
        if not items:
            return
        if order == "C":
            items.sort(key=lambda it: (it[0], round(it[1]["rect"][0] / 10), it[1]["rect"][1]))
        else:
            items.sort(key=lambda it: (it[0], round((it[1]["rect"][1] + it[1]["rect"][3]) / 2 / 6), it[1]["rect"][0]))
        idx = next((i for i, (pi, w) in enumerate(items) if w["xref"] == info["xref"]), None)
        if idx is None:
            return
        pi, w = items[(idx + (1 if forward else -1)) % len(items)]
        self.ensureVisible(self._img_scene_rect(pi, w["rect"]), 60, 90)
        self._fm_open_editor(pi, w)

    def _fm_set(self, page_idx: int, xref: int, value):
        cur = next((w for w in self._fm_cache.get(page_idx, []) if w["xref"] == xref), None)
        if cur is not None and cur["kind"] in ("text", "combo", "list") and str(cur["value"] or "") == str(value):
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        if ft.set_widget_value(self.doc, page_idx, xref, value):
            self._on_dirty()
            self.refresh_page(page_idx)
            self._fm_refresh()

    def _fm_activate(self, page_idx: int, w: dict, scene_pos: QPointF):
        if w["readonly"]:
            if self._on_notice:
                self._on_notice(tr("Este campo es de solo lectura."))
            return
        k = w["kind"]
        if k == "text":
            self._fm_open_editor(page_idx, w)
        elif k == "checkbox":
            self._fm_set(page_idx, w["xref"], not w["checked"])
        elif k == "radio":
            if not w["checked"]:
                self._fm_set(page_idx, w["xref"], True)
        elif k in ("combo", "list"):
            m = QMenu(self)
            for c in w["choices"]:
                act = m.addAction(c)
                act.setCheckable(True)
                act.setChecked(c == str(w["value"]))
                act.triggered.connect(lambda _=False, v=c: self._fm_set(page_idx, w["xref"], v))
            m.exec(self.viewport().mapToGlobal(self.mapFromScene(scene_pos)))
        elif k == "signature" and self._on_notice:
            self._on_notice(tr("Para firmar, usa el botón Firma."))
        elif self._on_notice:
            self._on_notice(tr("Este botón no se puede rellenar."))

    def _fm_handle_at(self, scene_pos: QPointF):
        sel = self._fm_sel
        if not sel:
            return None
        r = self._img_scene_rect(sel["page"], sel["rect"])
        tol = self._HANDLE + 4
        for name, pt in (("nw", r.topLeft()), ("ne", r.topRight()), ("sw", r.bottomLeft()), ("se", r.bottomRight())):
            if abs(scene_pos.x() - pt.x()) <= tol and abs(scene_pos.y() - pt.y()) <= tol:
                return name
        return None

    def _fm_select(self, page_idx, w):
        """Selecciona un campo creado aquí (marco y tiradores) o quita la selección (w=None)."""
        self._img_select(None)
        self._fm_sel = None if w is None else {"page": page_idx, "xref": w["xref"], "rect": tuple(w["rect"]),
                                               "kind": w["kind"]}
        if w is not None:
            self._img_draw(page_idx, w["rect"])

    def _fm_press(self, scene_pos: QPointF):
        self._fm_close(True)
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        op = self._fm_handle_at(scene_pos) if self._fm_sel and self._fm_sel["page"] == page_idx else None
        self._fm_down = {"page": page_idx, "pt": pt, "hit": self._fm_hit(page_idx, pt), "scene": scene_pos,
                         "moved": False, "op": op, "newrect": None}

    def _fm_new_rect(self, d, pt):
        sel = self._fm_sel
        x0, y0, x1, y1 = sel["rect"] if d["op"] else d["hit"]["rect"]
        if not d["op"]:                                           # mover
            dx, dy = pt[0] - d["pt"][0], pt[1] - d["pt"][1]
            return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        anchor = {"nw": (x1, y1), "ne": (x0, y1), "sw": (x1, y0), "se": (x0, y0)}[d["op"]]
        if sel["kind"] in ("checkbox", "radio"):
            return self._img_aspect_rect(anchor, pt, 1.0)
        nb = (min(anchor[0], pt[0]), min(anchor[1], pt[1]), max(anchor[0], pt[0]), max(anchor[1], pt[1]))
        return (nb[0], nb[1], max(nb[2], nb[0] + 14), max(nb[3], nb[1] + 10))

    def _fm_move(self, scene_pos: QPointF):
        d = self._fm_down
        if not d:
            h = self._fm_handle_at(scene_pos)
            if h:
                self.viewport().setCursor(Qt.SizeFDiagCursor if h in ("nw", "se") else Qt.SizeBDiagCursor)
                return
            page_idx = self._page_at_y(scene_pos.y(), quiet=True)
            over = page_idx is not None and self._fm_hit(page_idx, self._mk_pdf_point(scene_pos, page_idx))
            self.viewport().setCursor(Qt.PointingHandCursor if over else Qt.CrossCursor)
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if abs(pt[0] - d["pt"][0]) > 3 or abs(pt[1] - d["pt"][1]) > 3:
            d["moved"] = True
        if not d["moved"]:
            return
        movable = d["op"] or (d["hit"] and d["hit"].get("ours"))
        if movable:
            if not d["op"]:
                self._fm_select(d["page"], d["hit"])
            d["newrect"] = self._fm_new_rect(d, pt)
            self._img_draw(d["page"], d["newrect"])
            return
        if not d["hit"]:
            if self._fm_rubber is not None:
                self.scene_.removeItem(self._fm_rubber)
            box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
            self._fm_rubber = self.scene_.addRect(self._img_scene_rect(d["page"], box),
                                                  QPen(QColor(70, 140, 255), 1.5, Qt.DashLine),
                                                  QBrush(QColor(70, 140, 255, 50)))
            self._fm_rubber.setZValue(50)

    def _fm_release(self, scene_pos: QPointF):
        d, self._fm_down = self._fm_down, None
        if self._fm_rubber is not None:
            self.scene_.removeItem(self._fm_rubber)
            self._fm_rubber = None
        if not d:
            return
        if d.get("newrect") and self._fm_sel:
            sel = self._fm_sel
            if self._on_before_mutate:
                self._on_before_mutate()
            if ft.set_field_rect(self.doc, sel["page"], sel["xref"], d["newrect"]):
                self._on_dirty()
                self.refresh_page(sel["page"])
                self._fm_refresh()
                nw = next((w for w in self._fm_cache.get(sel["page"], []) if w["xref"] == sel["xref"]), None)
                self._fm_select(sel["page"], nw)
            return
        if d["hit"] and not d["moved"]:
            self._fm_select(d["page"], d["hit"] if d["hit"].get("ours") else None)
            self._fm_activate(d["page"], d["hit"], scene_pos)
            return
        if not d["hit"] and d["moved"]:
            pt = self._mk_pdf_point(scene_pos, d["page"])
            box = (min(d["pt"][0], pt[0]), min(d["pt"][1], pt[1]), max(d["pt"][0], pt[0]), max(d["pt"][1], pt[1]))
            if box[2] - box[0] >= 10 and box[3] - box[1] >= 8:
                self.field_requested.emit(d["page"], box)
            elif self._on_notice:
                self._on_notice(tr("Arrastra un recuadro más grande para crear el campo."))
        elif not d["hit"]:
            self._fm_select(None, None)
            if self._on_notice:
                self._on_notice(tr("Haz clic en un campo para rellenarlo, o arrastra un recuadro para crear uno nuevo."))

    def show_candidates(self, found):
        """Marca en verde los campos que se podrían crear (o los quita con None)."""
        for it in getattr(self, "_fm_cand", []):
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._fm_cand = []
        for pi, items in (found or {}).items():
            for c in items:
                it = self.scene_.addRect(self._img_scene_rect(pi, c["rect"]), QPen(QColor(40, 170, 90), 1.6, Qt.DashLine),
                                         QBrush(QColor(40, 170, 90, 55)))
                it.setZValue(45)
                self._fm_cand.append(it)

    def apply_new_field(self, page_idx: int, rect, spec: dict) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = ft.add_field(self.doc, page_idx, rect, spec)
        if ok and spec.get("kind") == "radio" and self._reload_cb:
            self._on_dirty()
            self._reload_cb()                       # PyMuPDF no ve los botones nuevos hasta reabrir el documento
            return True
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._fm_refresh()
        return ok

    def delete_field(self, page_idx: int, xref: int) -> bool:
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = ft.delete_field(self.doc, page_idx, xref)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._fm_refresh()
        return ok

    # ── Modo enlaces: crear sobre texto o área, y editar o quitar los existentes ──
    def _lk_refresh(self):
        """Dibuja un recuadro azul sobre cada enlace de todas las páginas (solo en modo enlaces)."""
        for it in self._lk_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._lk_items = []
        self._lk_hover_clear()
        self._lk_words_cache = None
        if self.mode != "link" or not self.doc or self._cols > 1:
            return
        for pi in range(len(self._page_tops)):
            for l in at.list_links(self.doc, pi):
                it = self.scene_.addRect(self._img_scene_rect(pi, l["rect"]), QPen(QColor(70, 140, 255), 1.2),
                                         QBrush(QColor(70, 140, 255, 45)))
                it.setZValue(40)
                it.setToolTip(at.describe_link(l))
                self._lk_items.append(it)

    def _lk_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        self._mk_page, self._mk_start = page_idx, pt
        self._mk_words = at.page_words(self.doc, page_idx)

    def _lk_boxes(self, scene_pos: QPointF):
        """Cajas del enlace en curso: las líneas de texto seleccionadas o, si no hay texto, el área arrastrada."""
        pt = self._mk_pdf_point(scene_pos, self._mk_page)
        idx = at.select_words(self._mk_words, self._mk_start, pt)
        moved = abs(pt[0] - self._mk_start[0]) > 6 or abs(pt[1] - self._mk_start[1]) > 6
        if idx and moved:
            return at.line_rects(self._mk_words, idx)
        if moved:
            return [fitz_rect(min(self._mk_start[0], pt[0]), min(self._mk_start[1], pt[1]),
                              max(self._mk_start[0], pt[0]), max(self._mk_start[1], pt[1]))]
        return at.line_rects(self._mk_words, idx) if idx else []

    def _lk_hover_clear(self):
        for it in getattr(self, "_lk_hover_items", []):
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._lk_hover_items = []
        self._lk_hover_key = None

    def _lk_hover(self, scene_pos: QPointF):
        """Sin pulsar: marca el área que se convertiría en enlace si haces clic aquí (palabra, imagen o dibujo), o el
        enlace ya existente (en otro color) si lo hay."""
        page_idx = self._page_at_y(scene_pos.y(), quiet=True)
        if page_idx is None or not self.doc or self._cols > 1:
            self._lk_hover_clear()
            self.viewport().setCursor(Qt.IBeamCursor)
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        rects, existing = [], False
        link = at.link_at(self.doc, page_idx, pt)
        if link:
            rects = [tuple(l["rect"]) for l in at.group_of(self.doc, page_idx, link)]
            existing = True
        else:
            cache = getattr(self, "_lk_words_cache", None)
            if cache is None or cache[0] != (id(self.doc), page_idx):
                cache = ((id(self.doc), page_idx), at.page_words(self.doc, page_idx))
                self._lk_words_cache = cache
            idx = at.select_words(cache[1], pt, pt, 4.0)
            if idx:
                rects = [tuple(r) for r in at.line_rects(cache[1], idx)]
            else:
                obj = self._lk_object_box(page_idx, pt)
                if obj:
                    rects = [obj]
        key = (page_idx, tuple(rects), existing)
        if key == getattr(self, "_lk_hover_key", None):
            return
        self._lk_hover_clear()
        self._lk_hover_key = key
        if rects:
            col = QColor(255, 150, 60) if existing else QColor(70, 140, 255)
            for r in rects:
                it = self.scene_.addRect(self._img_scene_rect(page_idx, r), QPen(col, 1.5),
                                         QBrush(QColor(col.red(), col.green(), col.blue(), 60)))
                it.setZValue(49)
                self._lk_hover_items.append(it)
        self.viewport().setCursor(Qt.PointingHandCursor if rects else Qt.IBeamCursor)

    def _lk_move(self, scene_pos: QPointF):
        if self._mk_start is None:
            self._lk_hover(scene_pos)
            return
        self._lk_hover_clear()
        for it in self._mk_preview:
            self.scene_.removeItem(it)
        self._mk_preview = []
        for r in self._lk_boxes(scene_pos):
            it = self.scene_.addRect(self._img_scene_rect(self._mk_page, (r[0], r[1], r[2], r[3])),
                                     QPen(QColor(70, 140, 255), 1.5, Qt.DashLine), QBrush(QColor(70, 140, 255, 70)))
            it.setZValue(50)
            self._mk_preview.append(it)

    def _lk_object_box(self, page_idx: int, pt: tuple):
        """Caja de la imagen (o del dibujo hecho en el editor) que hay bajo el punto, la más pequeña si hay varias."""
        best = None
        try:
            page = self.doc[page_idx]
            for info in page.get_image_info():
                x0, y0, x1, y1 = info["bbox"]
                if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1:
                    area = (x1 - x0) * (y1 - y0)
                    if best is None or area < best[0]:
                        best = (area, (x0, y0, x1, y1))
        except Exception:
            pass
        if best is None:
            hit = at.editable_at(self.doc, page_idx, pt)
            if hit:
                return tuple(hit["bbox"])
        return best[1] if best else None

    def _lk_release(self, scene_pos: QPointF):
        if self._mk_start is None:
            return
        page_idx, start = self._mk_page, self._mk_start
        pt = self._mk_pdf_point(scene_pos, page_idx)
        moved = abs(pt[0] - start[0]) > 6 or abs(pt[1] - start[1]) > 6
        self._lk_from_object = False
        existing = None if moved else at.link_at(self.doc, page_idx, pt)
        boxes = None if existing else [tuple(b) for b in self._lk_boxes(scene_pos)]
        if existing is None and not boxes and not moved:
            obj = self._lk_object_box(page_idx, pt)          # clic sobre una imagen o dibujo: el enlace cubre todo el objeto
            if obj:
                boxes = [obj]
                self._lk_from_object = True
        self._mk_clear_preview()
        if existing is None and not boxes:
            if self._on_notice:
                self._on_notice(tr("Arrastra sobre el texto o el área, o haz clic sobre una imagen o dibujo, para convertirlo en enlace."))
            return
        self.link_requested.emit(page_idx, boxes, existing)

    def apply_link(self, page_idx: int, boxes, existing, dest, underline: bool = False, obj: bool = False,
                   color=None):
        """Crea el enlace en cada caja, o cambia / quita el existente (dest=None quita)."""
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = False
        if existing is not None:
            members = at.group_of(self.doc, page_idx, existing)      # todas las zonas del mismo enlace
            ok = at.delete_group(self.doc, page_idx, members) if dest is None else at.replace_group(
                self.doc, page_idx, members, dest)
        else:
            col = tuple(color) if color else LINK_COLORS[0][1]
            if underline and not obj:                                # texto: se pone en el color del enlace
                be.recolor_text_in_boxes(self.doc, page_idx, [tuple(b) for b in boxes], col)
            gid = at.new_group_id() if len(boxes) > 1 else None      # las zonas de un enlace van juntas
            for i, b in enumerate(boxes):
                ok = at.add_link(self.doc, page_idx, b, dest, group=gid, index=i) or ok
            if ok and underline:                                   # que se note: subrayado azul
                at.add_markup(self.doc, page_idx, [tuple(b) for b in boxes], "underline", col)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._lk_refresh()
        return ok

    # ── Modo imagen: colocar, seleccionar, mover, escalar y borrar imágenes y firmas ──
    _HANDLE = 9.0

    def start_place_image(self, source, size: tuple, max_frac: float = 0.45):
        """Deja lista una imagen para colocarla con el siguiente clic (o arrastre) sobre la página."""
        self._img_select(None)
        self.set_mode("image")
        self.pending_image, self._img_size, self._pending_frac = source, size, max_frac
        self.viewport().setCursor(Qt.CrossCursor)

    def _img_select(self, sel):
        for it in self._img_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._img_items = []
        self._img_sel = sel
        if not sel:
            return
        self._img_draw(sel["page"], sel["rect"], handles=not sel.get("pdf"), rot=bool(sel.get("icon")))

    def _img_scene_rect(self, page_idx, rect):
        top, z = self._page_tops[page_idx], self.zoom
        return QRectF(rect[0] * z, top + rect[1] * z, (rect[2] - rect[0]) * z, (rect[3] - rect[1]) * z)

    _ROT_OFFSET = 26.0

    def _img_draw(self, page_idx, rect, handles: bool = True, rot: bool = False):
        for it in self._img_items:
            self.scene_.removeItem(it)
        self._img_items = []
        r = self._img_scene_rect(page_idx, rect)
        pen = QPen(QColor(ACCENT), 1.5, Qt.DashLine)
        frame = self.scene_.addRect(r, pen, QBrush(Qt.NoBrush))
        frame.setZValue(60)
        self._img_items.append(frame)
        if rot:                                           # tirador de giro (solo en los iconos de «clic aquí»)
            c = QPointF(r.center().x(), r.top() - self._ROT_OFFSET)
            cord = self.scene_.addLine(r.center().x(), r.top(), c.x(), c.y(), QPen(QColor(ACCENT), 1.2))
            cord.setZValue(60)
            hd = self.scene_.addEllipse(QRectF(c.x() - 5.5, c.y() - 5.5, 11, 11), QPen(QColor(ACCENT), 1.5),
                                        QBrush(QColor("#FFFFFF")))
            hd.setZValue(61)
            self._img_items += [cord, hd]
        h = self._HANDLE
        for pt in ((r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()) if handles else ()):
            hd = self.scene_.addRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h), QPen(QColor(ACCENT)),
                                     QBrush(QColor("#FFFFFF")))
            hd.setZValue(61)
            self._img_items.append(hd)

    def _img_handle_at(self, scene_pos: QPointF):
        if not self._img_sel or self._img_sel.get("pdf"):
            return None
        r = self._img_scene_rect(self._img_sel["page"], self._img_sel["rect"])
        h = self._HANDLE + 4
        handles = [("nw", r.topLeft()), ("ne", r.topRight()), ("sw", r.bottomLeft()), ("se", r.bottomRight())]
        if self._img_sel.get("icon"):
            handles.append(("rot", QPointF(r.center().x(), r.top() - self._ROT_OFFSET)))
        for name, pt in handles:
            if abs(scene_pos.x() - pt.x()) <= h and abs(scene_pos.y() - pt.y()) <= h:
                return name
        return None

    def _img_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        if self.pending_image is not None:
            self._img_drag = {"op": "place", "start": pt, "page": page_idx, "rect": None}
            return
        handle = self._img_handle_at(scene_pos)
        if handle:
            self._img_drag = {"op": handle, "start": pt, "page": self._img_sel["page"],
                              "rect0": tuple(self._img_sel["rect"]), "rect": None}
            if handle == "rot":
                self._img_drag["angle0"] = (self._img_sel.get("icon") or ("", 0.0))[1]
            return
        hit = at.stamp_at(self.doc, page_idx, pt)
        if hit:
            again = bool(self._img_sel and self._img_sel.get("xref") == hit["xref"] and self._img_sel.get("icon"))
            self._img_select({"page": page_idx, "xref": hit["xref"], "rect": hit["rect"],
                              "icon": ci.parse_subject(hit.get("subject", ""))})
            self._img_drag = {"op": "move", "start": pt, "page": page_idx, "rect0": tuple(hit["rect"]), "rect": None,
                              "reclick": again}
            self.viewport().setCursor(Qt.SizeAllCursor)
        else:
            pimg = at.pdf_image_at(self.doc, page_idx, pt)       # imagen del propio PDF: se puede borrar
            if pimg:
                self._img_select({"page": page_idx, "xref": None, "rect": pimg["bbox"], "pdf": True})
                if self._on_notice:
                    self._on_notice(tr("Imagen del PDF seleccionada: pulsa Supr para quitarla de esta página."))
            else:
                self._img_select(None)

    def _img_aspect_rect(self, anchor, pt, aspect):
        """Caja con una esquina en `anchor` y la opuesta lo más cerca posible de `pt`, manteniendo la proporción."""
        dx, dy = pt[0] - anchor[0], pt[1] - anchor[1]
        w = max(abs(dx), abs(dy) * aspect, 12.0)
        h = w / aspect
        x1 = anchor[0] + (w if dx >= 0 else -w)
        y1 = anchor[1] + (h if dy >= 0 else -h)
        return (min(anchor[0], x1), min(anchor[1], y1), max(anchor[0], x1), max(anchor[1], y1))

    def _img_compute(self, drag, pt, shift=False):
        op = drag["op"]
        if op == "move":
            dx, dy = pt[0] - drag["start"][0], pt[1] - drag["start"][1]
            x0, y0, x1, y1 = drag["rect0"]
            return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        if op == "place":
            aspect = self._img_size[0] / max(self._img_size[1], 1)
            return self._img_aspect_rect(drag["start"], pt, aspect)
        x0, y0, x1, y1 = drag["rect0"]
        if op == "rot":
            return drag["rect0"]
        anchor = {"nw": (x1, y1), "ne": (x0, y1), "sw": (x1, y0), "se": (x0, y0)}[op]
        if shift:                                   # con Mayús, deformar libremente
            return (min(anchor[0], pt[0]), min(anchor[1], pt[1]), max(anchor[0], pt[0]), max(anchor[1], pt[1]))
        return self._img_aspect_rect(anchor, pt, (x1 - x0) / max(y1 - y0, 1e-3))

    def _img_ghost_begin(self, d) -> None:
        """Al empezar a arrastrar o girar un sello/icono: se guarda su imagen y se oculta el original, para que lo que
        se ve moverse sea la propia imagen y no solo su marco."""
        if d.get("ghost_pm") is not None or d.get("op") == "place":
            return
        sel = self._img_sel
        if not sel or sel.get("pdf") or not sel.get("xref"):
            return
        png = at.stamp_png(self.doc, d["page"], sel["xref"])
        if not png:
            return
        pm = QPixmap()
        pm.loadFromData(png)
        d["ghost_pm"] = pm
        if at.set_stamp_hidden(self.doc, d["page"], sel["xref"], True):
            d["hidden"] = True
            img = be.render_doc_page_png(self.doc, d["page"], zoom=self.zoom, annots=not self.hide_annots)
            if img:
                page_pm = QPixmap()
                page_pm.loadFromData(img)
                self._page_items[d["page"]].setPixmap(page_pm)

    def _img_ghost_draw(self, d, rect) -> None:
        pm = d.get("ghost_pm")
        if pm is None:
            return
        r = self._img_scene_rect(d["page"], rect)
        item = self.scene_.addPixmap(pm.scaled(max(1, int(r.width())), max(1, int(r.height())),
                                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        item.setPos(r.topLeft())
        item.setZValue(59)
        self._img_items.append(item)

    def _img_move(self, scene_pos: QPointF, shift: bool):
        d = self._img_drag
        if not d:
            h = self._img_handle_at(scene_pos)
            self.viewport().setCursor({"nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor, "ne": Qt.SizeBDiagCursor,
                                       "sw": Qt.SizeBDiagCursor}.get(h, Qt.CrossCursor if self.pending_image is not None
                                                                     else Qt.ArrowCursor))
            return
        pt = self._mk_pdf_point(scene_pos, d["page"])
        if d["op"] == "place" and abs(pt[0] - d["start"][0]) < 3 and abs(pt[1] - d["start"][1]) < 3:
            return
        if d["op"] == "rot":
            import math
            x0, y0, x1, y1 = d["rect0"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            a0 = math.atan2(d["start"][1] - cy, d["start"][0] - cx)
            a1 = math.atan2(pt[1] - cy, pt[0] - cx)
            step = 15.0 if shift else 5.0
            d["angle"] = round((d["angle0"] + math.degrees(a1 - a0)) / step) * step
            self._img_ghost_begin(d)
            d["rect"] = d["rect0"]
            self._img_draw(d["page"], d["rect0"], handles=False, rot=True)
            key = (self._img_sel.get("icon") or ("arrow", 0))[0]
            pm = QPixmap.fromImage(ci.render_image(key, d["angle"], 192))
            item = self.scene_.addPixmap(pm.scaled(int(self._img_scene_rect(d["page"], d["rect0"]).width()),
                                                   int(self._img_scene_rect(d["page"], d["rect0"]).height()),
                                                   Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            item.setPos(self._img_scene_rect(d["page"], d["rect0"]).topLeft())
            item.setZValue(59)
            self._img_items.append(item)
            return
        self._img_ghost_begin(d)
        d["rect"] = self._img_compute(d, pt, shift)
        self._img_draw(d["page"], d["rect"], rot=False)
        self._img_ghost_draw(d, d["rect"])

    def _img_release(self, scene_pos: QPointF, shift: bool):
        d, self._img_drag = self._img_drag, None
        if not d:
            return
        page_idx = d["page"]
        if d.get("hidden") and self._img_sel:
            at.set_stamp_hidden(self.doc, page_idx, self._img_sel["xref"], False)
            d["hidden"] = False
        pt = self._mk_pdf_point(scene_pos, page_idx)
        moved = abs(pt[0] - d["start"][0]) >= 3 or abs(pt[1] - d["start"][1]) >= 3
        if d["op"] == "place":
            src = self.pending_image
            if moved:
                rect = self._img_compute(d, pt)
            else:
                page_rect = self.doc[page_idx].rect
                rect = tuple(at.default_image_rect(page_rect, self._img_size[0], self._img_size[1],
                                                   center=d["start"], max_frac=self._pending_frac))
            if self._on_before_mutate:
                self._on_before_mutate()
            xref = at.add_image(self.doc, page_idx, rect, src)
            self.pending_image = None
            if xref:
                self._on_dirty()
                self.refresh_page(page_idx)
                self._img_select({"page": page_idx, "xref": xref, "rect": rect})
            self.viewport().setCursor(Qt.ArrowCursor)
            return
        if not moved or not self._img_sel:
            self.viewport().setCursor(Qt.ArrowCursor)
            if d.get("ghost_pm") is not None:
                self.refresh_page(page_idx)
            self._img_select(self._img_sel)
            if d.get("reclick") and not moved:
                self.icon_picker_requested.emit()
            return
        if d["op"] == "rot":
            self.viewport().setCursor(Qt.ArrowCursor)
            self.rotate_selected_icon(d.get("angle", d["angle0"]) - d["angle0"])
            return
        rect = self._img_compute(d, pt, shift)
        if self._on_before_mutate:
            self._on_before_mutate()
        if at.set_stamp_rect(self.doc, page_idx, self._img_sel["xref"], rect):
            xref = self._img_sel["xref"]
            icon = self._img_sel.get("icon")
            self._on_dirty()
            self.refresh_page(page_idx)
            self._img_select({"page": page_idx, "xref": xref, "rect": rect, "icon": icon})
        self.viewport().setCursor(Qt.ArrowCursor)

    def swap_selected_icon(self, key: str) -> bool:
        """Cambia el dibujo del icono seleccionado por otro, conservando su sitio, tamaño y giro."""
        sel = self._img_sel
        if not sel or not sel.get("icon") or not self.doc:
            return False
        old_key, ang = sel["icon"]
        if key == old_key:
            return True
        if self._on_before_mutate:
            self._on_before_mutate()
        res = at.rotate_click_icon(self.doc, sel["page"], sel["xref"], ang, key=key)
        if not res:
            return False
        self._on_dirty()
        self.refresh_page(sel["page"])
        self._img_select({"page": sel["page"], "xref": res[0], "rect": res[1], "icon": (key, ang)})
        return True

    def rotate_selected_icon(self, delta: float) -> bool:
        """Gira el icono de «clic aquí» seleccionado `delta` grados."""
        sel = self._img_sel
        if not sel or not sel.get("icon") or not self.doc:
            return False
        key, ang = sel["icon"]
        new_ang = (ang + delta) % 360
        if self._on_before_mutate:
            self._on_before_mutate()
        res = at.rotate_click_icon(self.doc, sel["page"], sel["xref"], new_ang)
        if not res:
            return False
        self._on_dirty()
        self.refresh_page(sel["page"])
        self._img_select({"page": sel["page"], "xref": res[0], "rect": res[1], "icon": (key, new_ang)})
        return True

    def duplicate_selected_image(self) -> bool:
        sel = self._img_sel
        if not sel or not self.doc or sel.get("pdf"):
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        res = at.duplicate_stamp(self.doc, sel["page"], sel["xref"])
        if not res:
            return False
        self._on_dirty()
        self.refresh_page(sel["page"])
        self._img_select({"page": sel["page"], "xref": res[0], "rect": res[1], "icon": sel.get("icon")})
        return True

    def delete_selected_image(self) -> bool:
        sel = self._img_sel
        if not sel or not self.doc:
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = (at.delete_pdf_image(self.doc, sel["page"], sel["rect"]) if sel.get("pdf")
              else at.delete_stamp(self.doc, sel["page"], sel["xref"]))
        self._img_select(None)
        if ok:
            self._on_dirty()
            self.refresh_page(sel["page"])
        return ok

    def contextMenuEvent(self, e):
        if self.doc is not None and self._cols == 1 and self._editor is None and self.mode in ("edit", "shape"):
            sp_ = self.mapToScene(e.pos())
            pi = self._page_at_y(sp_.y(), quiet=True)
            hit = at.editable_at(self.doc, pi, self._mk_pdf_point(sp_, pi)) if pi is not None else None
            if hit and hit["kind"] == "ink":
                menu = QMenu(self)
                menu.addAction(ic.icon("signature", TEXT, 16), tr("Guardar como firma…"),
                               lambda: self.save_signature_requested.emit(hit))
                menu.addAction(ic.icon("trash", TEXT, 16), tr("Eliminar este dibujo"),
                               lambda: (self._ss_select(pi, hit), self.delete_selection()))
                menu.exec(e.globalPos())
                e.accept()
                return
        if self.mode == "edit" and self._editor is None and self.doc is not None:
            sp0 = self.mapToScene(e.pos())
            item = next((it for it in self.scene_.items(sp0) if isinstance(it, SpanRectItem) and it.kind == "edit"), None)
            if item is not None:
                pt = self._mk_pdf_point(sp0, item.page_idx)
                word = self._word_at(item.page_idx, pt)
                whole = " ".join(str(item.span.get("text", "")).split())
                menu = QMenu(self)
                a_edit = menu.addAction(ic.icon("pencil", TEXT, 16), tr("Editar este texto"))
                a_edit.triggered.connect(lambda _=False, it=item: self._open_inline_editor(it))
                menu.addSeparator()
                if word:
                    menu.addAction(ic.icon("swap", TEXT, 16), tr("Reemplazar «{w}»…", w=word)).triggered.connect(
                        lambda _=False, w=word: self.replace_requested.emit(w))
                if whole and whole != word:
                    shown = whole if len(whole) <= 36 else whole[:34] + "…"
                    menu.addAction(ic.icon("swap", TEXT, 16), tr("Reemplazar «{w}»…", w=shown)).triggered.connect(
                        lambda _=False, w=whole: self.replace_requested.emit(w))
                menu.exec(e.globalPos())
                e.accept()
                return
        if self.mode == "form":
            sp_ = self.mapToScene(e.pos())
            pi = self._page_at_y(sp_.y())
            w = self._fm_hit(pi, self._mk_pdf_point(sp_, pi)) if pi is not None else None
            if w:
                m = QMenu(self)
                m.addAction(tr("Rellenar / cambiar"), lambda: self._fm_activate(pi, w, sp_))
                m.addAction(tr("Eliminar campo «{n}»", n=w["name"]), lambda: self.delete_field(pi, w["xref"]))
                m.exec(e.globalPos())
            e.accept()
            return
        if self.mode == "image" and self._img_sel:
            m = QMenu(self)
            if self._img_sel.get("icon"):
                m.addAction(tr("Cambiar de icono…"), self.icon_picker_requested.emit)
                m.addAction(tr("Girar 15° a la izquierda") + "\t[", lambda: self.rotate_selected_icon(-15))
                m.addAction(tr("Girar 15° a la derecha") + "\t]", lambda: self.rotate_selected_icon(15))
                m.addSeparator()
            m.addAction(tr("Duplicar") + "	Ctrl+D", self.duplicate_selected_image)
            m.addAction(tr("Eliminar") + "	Supr", self.delete_selected_image)
            m.exec(e.globalPos())
            e.accept()
            return
        if self.mode == "shape" and self._ss_sel:
            m = QMenu(self)
            m.addAction(tr("Duplicar") + "\tCtrl+D", self.duplicate_selection)
            m.addAction(tr("Eliminar") + "\tSupr", self.delete_selection)
            m.exec(e.globalPos())
            e.accept()
            return
        super().contextMenuEvent(e)

    def keyPressEvent(self, e):
        if self.mode == "shape":
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._ss_sel:
                self.delete_selection()
                e.accept()
                return
            if e.key() == Qt.Key_D and (e.modifiers() & Qt.ControlModifier) and self._ss_sel:
                self.duplicate_selection()
                e.accept()
                return
            if e.key() == Qt.Key_Escape:
                if self._ss_sel:
                    self._ss_select(None, None)
                else:
                    self.set_mode("edit")
                e.accept()
                return
        if self.mode in ("note", "attach", "copy") and e.key() == Qt.Key_Escape:
            self.set_mode("edit")
            e.accept()
            return
        if self.mode == "form" and e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._fm_sel \
                and self._fm_editor is None:
            sel, self._fm_sel = self._fm_sel, None
            self.delete_field(sel["page"], sel["xref"])
            e.accept()
            return
        if self.mode == "form" and e.key() == Qt.Key_Escape:
            self.set_mode("edit")
            e.accept()
            return
        if self.mode == "image" and self._img_sel and self._img_sel.get("icon") and e.key() in (Qt.Key_BracketLeft,
                                                                                               Qt.Key_BracketRight):
            self.rotate_selected_icon(-15 if e.key() == Qt.Key_BracketLeft else 15)
            e.accept()
            return
        if self.mode == "link" and e.key() == Qt.Key_Escape:
            self.set_mode("edit")
            e.accept()
            return
        if self.mode == "image":
            if e.key() == Qt.Key_D and (e.modifiers() & Qt.ControlModifier) and self._img_sel:
                self.duplicate_selected_image()
                e.accept()
                return
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._img_sel:
                self.delete_selected_image()
                e.accept()
                return
            if e.key() == Qt.Key_Escape:
                if self.pending_image is not None or self._img_sel:
                    self.pending_image = None
                    self._img_select(None)
                else:
                    self.set_mode("edit")
                e.accept()
                return
        super().keyPressEvent(e)

    # ── Seleccionar, mover, escalar, duplicar y borrar lo dibujado desde el editor ──
    def _ss_select(self, page_idx, desc):
        self._img_select(None)                    # quita marco y tiradores anteriores
        self._ss_sel = None if desc is None else {"page": page_idx, "desc": desc}
        if desc is not None:
            self._ss_draw(page_idx, desc)
        self._update_sel_bar()

    def _update_sel_bar(self):
        """Coloca las opciones justo encima de la forma seleccionada (o las oculta)."""
        bar = getattr(self, "_sel_bar", None)
        if bar is None:
            return
        sel = self._ss_sel
        if not sel or self.mode != "shape" or self._ss_drag is not None:
            bar.hide()
            return
        d, page_idx = sel["desc"], sel["page"]
        z, top = self.zoom, self._page_tops[page_idx]
        if d["kind"] in ("line", "arrow"):
            xs = [d["p0"][0], d["p1"][0]]; ys = [d["p0"][1], d["p1"][1]]
            x0, x1, y0 = min(xs), max(xs), min(ys)
        else:
            x0, y0, x1, _y1 = d["bbox"]
        bar.refresh(d)
        cx = (x0 + x1) / 2 * z
        pt = self.mapFromScene(QPointF(cx, top + y0 * z))
        x = int(pt.x() - bar.width() / 2)
        y = int(pt.y() - bar.height() - 34)          # por encima del tirador de giro
        if y < 2:
            y = int(self.mapFromScene(QPointF(cx, top + (d["bbox"][3] if "bbox" in d else y0) * z)).y() + 14)
        x = max(4, min(x, self.viewport().width() - bar.width() - 4))
        bar.move(x, max(2, y))
        bar.show()
        bar.raise_()

    def _ss_draw(self, page_idx, d):
        for it in self._img_items:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._img_items = []
        z, top = self.zoom, self._page_tops[page_idx]
        pen = QPen(QColor(ACCENT), 1.5, Qt.DashLine)
        hs = self._HANDLE
        if d["kind"] in ("line", "arrow"):
            a, b = d["p0"], d["p1"]
            fr = self.scene_.addLine(a[0] * z, top + a[1] * z, b[0] * z, top + b[1] * z, pen)
        else:
            x0, y0, x1, y1 = d["bbox"]
            fr = self.scene_.addRect(QRectF(x0 * z, top + y0 * z, (x1 - x0) * z, (y1 - y0) * z), pen, QBrush(Qt.NoBrush))
        fr.setZValue(60)
        self._img_items.append(fr)
        for name, (hx, hy) in at.handles_of(d).items():
            if name == "rot":
                x0, y0, x1, y1 = d["bbox"]
                cord = self.scene_.addLine((x0 + x1) / 2 * z, top + y0 * z, hx * z, top + hy * z, QPen(QColor(ACCENT), 1.2))
                cord.setZValue(60)
                self._img_items.append(cord)
                hd = self.scene_.addEllipse(QRectF(hx * z - hs / 2 - 1, top + hy * z - hs / 2 - 1, hs + 2, hs + 2),
                                            QPen(QColor(ACCENT), 1.5), QBrush(QColor("#FFFFFF")))
            else:
                hd = self.scene_.addRect(QRectF(hx * z - hs / 2, top + hy * z - hs / 2, hs, hs), QPen(QColor(ACCENT)),
                                         QBrush(QColor("#FFFFFF")))
            hd.setZValue(61)
            self._img_items.append(hd)

    def _ss_handle_at(self, scene_pos: QPointF):
        if not self._ss_sel:
            return None
        z, top = self.zoom, self._page_tops[self._ss_sel["page"]]
        tol = self._HANDLE + 4
        for name, (hx, hy) in at.handles_of(self._ss_sel["desc"]).items():
            if abs(scene_pos.x() - hx * z) <= tol and abs(scene_pos.y() - (top + hy * z)) <= tol:
                return name
        return None

    def _ss_press(self, scene_pos: QPointF, page_idx: int, pt: tuple, allow_pick: bool) -> bool:
        """True si el clic se ha usado para seleccionar / mover / escalar algo ya dibujado."""
        sel = self._ss_sel
        if sel and sel["page"] == page_idx:
            h = self._ss_handle_at(scene_pos)
            if h:
                self._ss_drag = {"op": h, "start": pt, "page": page_idx, "desc": sel["desc"], "geom": None}
                return True
        if sel and sel["page"] == page_idx and sel["desc"]["kind"] == "ink":
            x0, y0, x1, y1 = sel["desc"]["bbox"]                  # un trazo fino se agarra desde todo su recuadro
            if x0 - 6 <= pt[0] <= x1 + 6 and y0 - 6 <= pt[1] <= y1 + 6:
                self._ss_drag = {"op": "move", "start": pt, "page": page_idx, "desc": sel["desc"], "geom": None}
                self.viewport().setCursor(Qt.SizeAllCursor)
                return True
        if allow_pick:
            hit = at.editable_at(self.doc, page_idx, pt, edge_only=self.shape_kind != "select")
            if hit:
                self._ss_select(page_idx, hit)
                self._ss_drag = {"op": "move", "start": pt, "page": page_idx, "desc": hit, "geom": None}
                self.viewport().setCursor(Qt.SizeAllCursor)
                return True
            self._ss_select(None, None)
        return self.shape_kind == "select"

    def _ss_compute(self, drag, pt, shift):
        d, op = drag["desc"], drag["op"]
        if op == "move":
            return at.shifted_geom(d, pt[0] - drag["start"][0], pt[1] - drag["start"][1])
        if op == "rot":
            import math
            cx, cy = at.center_of(d)
            a0 = math.atan2(drag["start"][1] - cy, drag["start"][0] - cx)
            a1 = math.atan2(pt[1] - cy, pt[0] - cx)
            delta = math.degrees(a1 - a0)
            if shift:
                delta = round(delta / 15.0) * 15.0
            return at.rotate_geom(d, delta, (cx, cy))
        if d["kind"] in ("line", "arrow"):
            other = d["p1"] if op == "a" else d["p0"]
            np_ = at.snap_points(other, pt, "line") if shift else pt
            return {"p0": np_, "p1": other} if op == "a" else {"p0": other, "p1": np_}
        x0, y0, x1, y1 = d["bbox"]
        anchor = {"nw": (x1, y1), "ne": (x0, y1), "sw": (x1, y0), "se": (x0, y0)}[op]
        if shift:
            nb = self._img_aspect_rect(anchor, pt, (x1 - x0) / max(y1 - y0, 1e-3))
        else:
            nb = (min(anchor[0], pt[0]), min(anchor[1], pt[1]), max(anchor[0], pt[0]), max(anchor[1], pt[1]))
            if nb[2] - nb[0] < 4:
                nb = (nb[0], nb[1], nb[0] + 4, nb[3])
            if nb[3] - nb[1] < 4 and d["kind"] != "ink":
                nb = (nb[0], nb[1], nb[2], nb[1] + 4)
        return at.scaled_geom(d, nb)

    def _ss_ghost(self, page_idx, d, geom):
        """Vista previa mientras se arrastra: la forma en su nueva posición y el marco con tiradores."""
        tmp = at.with_geom(d, geom)
        self._sh_page = page_idx
        z, top = self.zoom, self._page_tops[page_idx]
        cname = self._sh_color_name(d["stroke"])
        if tmp["kind"] == "poly":
            for it in self._sh_preview:
                self.scene_.removeItem(it)
            self._sh_preview = []
            r, g, b = (int(c * 255) for c in (d["stroke"] or at.rgb_of(cname)))
            path = QPainterPath(QPointF(tmp["pts"][0][0] * z, top + tmp["pts"][0][1] * z))
            for x, y in tmp["pts"][1:]:
                path.lineTo(x * z, top + y * z)
            path.closeSubpath()
            fillc = d.get("fill")
            brush = QBrush(QColor(*(int(c * 255) for c in fillc), 120)) if fillc else QBrush(Qt.NoBrush)
            it = self.scene_.addPath(path, QPen(QColor(r, g, b), max(1.0, d["width"] * z)), brush)
            it.setZValue(50)
            self._sh_preview.append(it)
        elif tmp["kind"] == "ink":
            for it in self._sh_preview:
                self.scene_.removeItem(it)
            self._sh_preview = []
            r, g, b = (int(c * 255) for c in (d["stroke"] or at.rgb_of(cname)))
            pen = QPen(QColor(r, g, b, 100 if d.get("marker") else 255), max(1.0, d["width"] * z))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            for st in tmp["strokes"]:
                if len(st) < 2:
                    continue
                path = QPainterPath(QPointF(st[0][0] * z, top + st[0][1] * z))
                for x, y in st[1:]:
                    path.lineTo(x * z, top + y * z)
                it = self.scene_.addPath(path, pen)
                it.setZValue(50)
                self._sh_preview.append(it)
        else:
            fill = self._sh_color_name(d["fill"]) if d.get("fill") and tmp["kind"] in ("rect", "ellipse") else None
            self._sh_draw_preview(tmp["kind"], tmp["p0"], tmp["p1"], cname, d["width"], fill)
        self._ss_draw(page_idx, tmp)

    def _ss_move_evt(self, scene_pos: QPointF, shift: bool):
        drag = self._ss_drag
        if not drag:
            h = self._ss_handle_at(scene_pos)
            cur = {"nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor, "ne": Qt.SizeBDiagCursor,
                   "sw": Qt.SizeBDiagCursor, "a": Qt.CrossCursor, "b": Qt.CrossCursor, "rot": Qt.PointingHandCursor}.get(h)
            self.viewport().setCursor(cur or (Qt.ArrowCursor if self.shape_kind == "select" else Qt.CrossCursor))
            return False
        pt = self._mk_pdf_point(scene_pos, drag["page"])
        if abs(pt[0] - drag["start"][0]) < 1.5 and abs(pt[1] - drag["start"][1]) < 1.5 and drag["geom"] is None:
            return True
        drag["geom"] = self._ss_compute(drag, pt, shift)
        self._sel_bar.hide()
        self._ss_ghost(drag["page"], drag["desc"], drag["geom"])
        return True

    def _ss_release(self, scene_pos: QPointF, shift: bool):
        drag, self._ss_drag = self._ss_drag, None
        page_idx, d = drag["page"], drag["desc"]
        pt = self._mk_pdf_point(scene_pos, page_idx)
        self._sh_clear()
        self.viewport().setCursor(Qt.ArrowCursor if self.shape_kind == "select" else Qt.CrossCursor)
        if drag["geom"] is None:
            self._ss_select(page_idx, d)
            return
        geom = self._ss_compute(drag, pt, shift)
        if self._on_before_mutate:
            self._on_before_mutate()
        new = at.rebuild(self.doc, page_idx, d, geom)
        if new:
            self._on_dirty()
            self.refresh_page(page_idx)
        self._ss_select(page_idx, new or d)

    def duplicate_selection(self):
        sel = self._ss_sel
        if not sel or not self.doc:
            return False
        d, page_idx = sel["desc"], sel["page"]
        if self._on_before_mutate:
            self._on_before_mutate()
        new = at.rebuild(self.doc, page_idx, d, at.shifted_geom(d, 14, 14), delete_old=False)
        if new:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._ss_select(page_idx, new)
        return bool(new)

    def delete_selection(self):
        sel = self._ss_sel
        if not sel or not self.doc:
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = at.delete_editable(self.doc, sel["page"], sel["desc"]["xref"])
        self._ss_select(None, None)
        if ok:
            self._on_dirty()
            self.refresh_page(sel["page"])
        return ok

    def restyle_selection(self, color=None, width=None, fill=None, opacity=None, head=None,
                          stroke_op=None, fill_op=None):
        """Cambia color, grosor, relleno, opacidad del relleno o punta de lo seleccionado (fill=\"\" quita el relleno)."""
        sel = self._ss_sel
        if not sel or not self.doc:
            return False
        d, page_idx = sel["desc"], sel["page"]
        style = {}
        if color:
            style["stroke"] = at.rgb_of(color)
            if d["kind"] == "arrow":
                style["fill"] = at.rgb_of(color)
        if width:
            style["width"] = width * (5 if d.get("marker") else 1)
        if fill is not None and d["kind"] in ("rect", "ellipse", "poly"):
            style["fill"] = at.rgb_of(fill) if fill else None
        if opacity is not None or stroke_op is not None or fill_op is not None:
            s_cur = d.get("opacity", 1.0)
            f_cur = d.get("fill_opacity", s_cur)
            s_new, f_new = s_cur, f_cur
            if opacity is not None:                       # total: trazo y relleno
                s_new = f_new = float(opacity)
            if stroke_op is not None:
                s_new = float(stroke_op)
            if fill_op is not None:
                f_new = float(fill_op)
            style["opacity"], style["fill_opacity"] = s_new, f_new
        if head and d["kind"] == "arrow":
            style["head"] = head
        if not style:
            return False
        if self._on_before_mutate:
            self._on_before_mutate()
        new = at.rebuild(self.doc, page_idx, d, at.geom_of(d), style=style)
        if new:
            self._on_dirty()
            self.refresh_page(page_idx)
            self._ss_select(page_idx, new)
        return bool(new)

    # ── Modo formas: rectángulo, elipse, línea, flecha (y mover las ya dibujadas) ──
    def _sh_clear(self):
        for it in self._sh_preview:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._sh_preview = []
        self._sh_start = self._sh_page = self._sh_move = None
        self._sh_stroke = []

    def _sh_draw_preview(self, kind, p0, p1, color, width, fill):
        for it in self._sh_preview:
            self.scene_.removeItem(it)
        self._sh_preview = []
        top = self._page_tops[self._sh_page]
        z = self.zoom
        r, g, b = (int(c * 255) for c in (at.rgb_of(color) or at.SHAPE_COLORS["rojo"]))
        pen = QPen(QColor(r, g, b), max(1.0, width * z))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        if kind in ("pen", "marker"):
            pts = self._sh_stroke
            path = QPainterPath(QPointF(pts[0][0] * z, top + pts[0][1] * z))
            for x, y in pts[1:]:
                path.lineTo(x * z, top + y * z)
            if kind == "marker":
                pen.setWidthF(max(1.0, width * 5 * z))
                pen.setColor(QColor(r, g, b, 100))
            it = self.scene_.addPath(path, pen)
            it.setZValue(50)
            self._sh_preview.append(it)
            return
        a = QPointF(p0[0] * z, top + p0[1] * z)
        c = QPointF(p1[0] * z, top + p1[1] * z)
        if kind in ("rect", "ellipse"):
            brush = QBrush(QColor(*(int(v * 255) for v in at.rgb_of(fill)), int(255 * (self.shape_fill_op if self.shape_fill_op is not None else self.shape_opacity)))) if fill else QBrush(Qt.NoBrush)
            box = QRectF(a, c).normalized()
            it = (self.scene_.addRect(box, pen, brush) if kind == "rect" else self.scene_.addEllipse(box, pen, brush))
            self._sh_preview.append(it)
        else:
            self._sh_preview.append(self.scene_.addLine(a.x(), a.y(), c.x(), c.y(), pen))
            if kind == "arrow":
                import math
                ang = math.atan2(c.y() - a.y(), c.x() - a.x())
                size = max(10.0, width * z * 4)
                for da in (2.6, -2.6):
                    self._sh_preview.append(self.scene_.addLine(
                        c.x(), c.y(), c.x() + size * math.cos(ang + da), c.y() + size * math.sin(ang + da), pen))
        for it in self._sh_preview:
            it.setZValue(50)

    def _sh_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        if self._ss_press(scene_pos, page_idx, pt, allow_pick=self.shape_kind not in ("pen", "marker")):
            return
        self._sh_page, self._sh_start = page_idx, pt
        if self.shape_kind in ("pen", "marker"):
            self._sh_stroke = [pt]
            self._sh_pressures = [self._pressure] if self._pressure else []
            return

    def _sh_current(self, scene_pos: QPointF, shift: bool):
        pt = self._mk_pdf_point(scene_pos, self._sh_page)
        if self._sh_move is None and shift:
            pt = at.snap_points(self._sh_start, pt, self.shape_kind)
        return pt

    def _sh_move_evt(self, scene_pos: QPointF, shift: bool):
        if self._sh_start is None:
            return
        if self.shape_kind in ("pen", "marker"):
            pt = self._mk_pdf_point(scene_pos, self._sh_page)
            last = self._sh_stroke[-1]
            if (pt[0] - last[0]) ** 2 + (pt[1] - last[1]) ** 2 >= 0.6:
                self._sh_stroke.append(pt)
                if self._pressure:
                    self._sh_pressures.append(self._pressure)
                self._sh_draw_preview(self.shape_kind, None, None, self.shape_color, self.shape_width, None)
            return
        pt = self._sh_current(scene_pos, shift)
        if self._sh_move:
            d = self._sh_move
            dx, dy = pt[0] - self._sh_start[0], pt[1] - self._sh_start[1]
            self._sh_draw_preview(d["kind"], (d["p0"][0] + dx, d["p0"][1] + dy), (d["p1"][0] + dx, d["p1"][1] + dy),
                                  self._sh_color_name(d["stroke"]), d["width"], None)
        else:
            self._sh_draw_preview(self.shape_kind, self._sh_start, pt, self.shape_color, self.shape_width,
                                  self.shape_fill)

    @staticmethod
    def _sh_color_name(rgb):
        return tuple(rgb) if rgb else "negro"

    def _sh_release(self, scene_pos: QPointF, shift: bool):
        if self._sh_start is None:
            return
        page_idx, start, moving = self._sh_page, self._sh_start, self._sh_move
        if self.shape_kind in ("pen", "marker"):
            stroke = list(self._sh_stroke)
            self._sh_clear()
            if len(stroke) >= 2:
                if self._on_before_mutate:
                    self._on_before_mutate()
                width = self.shape_width
                if self._sh_pressures:                     # lápiz óptico: la presión media da el grosor (0,5x a 1,5x)
                    width *= 0.5 + sum(self._sh_pressures) / len(self._sh_pressures)
                self._sh_pressures = []
                if at.add_ink(self.doc, page_idx, stroke, self.shape_color, width,
                              marker=self.shape_kind == "marker"):
                    self._on_dirty()
                    self.refresh_page(page_idx)
            return
        pt = self._sh_current(scene_pos, shift)
        self._sh_clear()
        self.viewport().setCursor(Qt.CrossCursor)
        dx, dy = pt[0] - start[0], pt[1] - start[1]
        if abs(dx) < 2 and abs(dy) < 2:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        if moving:
            ok = at.move_shape(self.doc, page_idx, moving, dx, dy)
        else:
            ok = at.add_shape(self.doc, page_idx, self.shape_kind, start, pt, self.shape_color,
                              self.shape_width, self.shape_fill, self.shape_opacity, self.shape_head,
                              self.shape_stroke_op, self.shape_fill_op)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)
            if not moving:
                # una forma por vez: se acaba el dibujo y queda seleccionada, con sus opciones encima
                self.shape_kind = "select"
                self.shape_kind_changed.emit("select")
                self.viewport().setCursor(Qt.ArrowCursor)
                self._ss_select(page_idx, at.last_editable(self.doc, page_idx))

    # ── Modo marcar: resaltar, subrayar, tachar, quitar marca ───────────
    def _mk_clear_preview(self):
        for it in self._mk_preview:
            try:
                self.scene_.removeItem(it)
            except RuntimeError:
                pass
        self._mk_preview = []
        self._mk_start = None
        self._mk_page = None

    def _mk_pdf_point(self, scene_pos: QPointF, page_idx: int) -> tuple:
        return (scene_pos.x() / self.zoom, (scene_pos.y() - self._page_tops[page_idx]) / self.zoom)

    def _mk_color_rgb(self):
        name = self.markup_color or at.DEFAULT_COLOR.get(self.markup_kind, "amarillo")
        return at.COLORS.get(name, at.COLORS["amarillo"])

    def _mk_press(self, scene_pos: QPointF):
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None or not self.doc:
            return
        pt = self._mk_pdf_point(scene_pos, page_idx)
        if self.markup_kind == "erase":
            if not at.remove_markup_at(self.doc, page_idx, pt, dry=True):
                if self._on_notice:
                    self._on_notice(tr("No hay ninguna marca ahí."))
                return
            if self._on_before_mutate:
                self._on_before_mutate()
            at.remove_markup_at(self.doc, page_idx, pt)
            self._on_dirty()
            self.refresh_page(page_idx)
            return
        self._mk_page, self._mk_start = page_idx, pt
        self._mk_words = at.page_words(self.doc, page_idx)

    def _mk_selection(self, scene_pos: QPointF):
        pt = self._mk_pdf_point(scene_pos, self._mk_page)
        idx = at.select_words(self._mk_words, self._mk_start, pt)
        return at.line_rects(self._mk_words, idx)

    def _mk_move(self, scene_pos: QPointF):
        if self._mk_start is None:
            return
        for it in self._mk_preview:
            self.scene_.removeItem(it)
        self._mk_preview = []
        r, g, b = (int(c * 255) for c in self._mk_color_rgb())
        top = self._page_tops[self._mk_page]
        for rect in self._mk_selection(scene_pos):
            qr = QRectF(rect.x0 * self.zoom, top + rect.y0 * self.zoom,
                        (rect.x1 - rect.x0) * self.zoom, (rect.y1 - rect.y0) * self.zoom)
            if self.markup_kind == "highlight":
                it = self.scene_.addRect(qr, QPen(Qt.NoPen), QBrush(QColor(r, g, b, 110)))
            else:
                y = qr.bottom() - 2 if self.markup_kind == "underline" else qr.center().y()
                it = self.scene_.addLine(qr.left(), y, qr.right(), y, QPen(QColor(r, g, b), 2))
            it.setZValue(50)
            self._mk_preview.append(it)

    def _mk_release(self, scene_pos: QPointF):
        if self._mk_start is None:
            return
        page_idx = self._mk_page
        rects = self._mk_selection(scene_pos)
        self._mk_clear_preview()
        if not rects:
            if self._on_notice:
                self._on_notice(tr("Arrastra sobre el texto que quieras marcar."))
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        if at.add_markup(self.doc, page_idx, rects, self.markup_kind, self.markup_color):
            self._on_dirty()
            self.refresh_page(page_idx)

    def load_doc(self, doc):
        """Renderiza el documento entero, una página debajo de otra."""
        self._close_inline_editor(commit=False)
        self.doc = doc
        self.scene_.clear()
        self._page_items = []
        self._page_span_items = []
        self._page_tops = []
        self._img_items, self._img_sel, self._img_drag = [], None, None      # la escena se vació
        self._edit_cover = None
        self._ss_sel, self._ss_drag = None, None
        self._sel_bar.hide()
        self._sh_preview, self._mk_preview, self._lk_items = [], [], []
        self._fm_items, self._fm_cache, self._fm_editor, self._fm_down, self._fm_rubber = [], {}, None, None, None
        self._fm_sel = None
        self._cp_down, self._cp_rubber = None, None
        if not doc:
            return
        cols = self._calc_cols()
        self._cols = cols
        gap_x = 24.0
        cell_w = max(doc[i].rect.width for i in range(len(doc))) * self.zoom
        x0 = max(0.0, (self.viewport().width() - (cols * (cell_w + gap_x) - gap_x)) / 2) if cols > 1 else 0.0
        y = float(self._page_gap - 8)
        max_w = 0.0
        row_h = 0.0
        pending_bars = []
        for page_idx in range(len(doc)):
            png = be.render_doc_page_png(doc, page_idx, zoom=self.zoom, annots=not self.hide_annots)
            if not png:
                continue
            pix = QPixmap()
            pix.loadFromData(png)
            col = page_idx % cols
            if col == 0 and page_idx > 0:
                y += row_h + self._page_gap
                row_h = 0.0
            px = x0 + col * (cell_w + gap_x) + ((cell_w - pix.width()) / 2 if cols > 1 else 0.0)
            pending_bars.append((page_idx, y, pix.width(), px))
            pm_item = self.scene_.addPixmap(pix)
            pm_item.setPos(px, y)
            self._page_items.append(pm_item)
            self._page_tops.append(y)
            row_h = max(row_h, float(pix.height()))
            max_w = max(max_w, px + pix.width())
            self._page_span_items.append(self._build_spans(doc, page_idx, y))
        end_y = y + row_h + 8
        for page_idx, top, w, px in pending_bars:
            self._add_page_bar(page_idx, top, w, max_w, px=px)
        if cols > 1:                                   # «+» en los huecos entre páginas
            cb = lambda a, i: self.page_action.emit(a, i)
            for k, (page_idx, top, w, px) in enumerate(pending_bars):
                h = self._page_items[k].pixmap().height()
                if k == 0:
                    g = GutterPlusItem(0, cb)
                    g.setPos(px - 12 - GutterPlusItem.D / 2 - 6, top + h / 2 - GutterPlusItem.D / 2)
                    g.setZValue(60); self.scene_.addItem(g)
                g = GutterPlusItem(page_idx + 1, cb)
                g.setPos(px + w + 12 - GutterPlusItem.D / 2 + (6 if (page_idx % cols) == cols - 1 else 0),
                         top + h / 2 - GutterPlusItem.D / 2)
                g.setZValue(60); self.scene_.addItem(g)
        else:
            self._add_page_bar(len(doc), end_y + 10 + self._bar_h + 6, 0, max_w, last=True)
        self.scene_.setSceneRect(0, 0, max_w, end_y + 10 + self._bar_h + 24)
        self._current_page = 0
        self._lk_refresh()
        self._fm_refresh()
        if self._on_page_visible:
            self._on_page_visible(0, len(self._page_items))

    def _calc_cols(self) -> int:
        """Páginas por fila: con mucho zoom una; si se aleja tanto que caben varias, se reparten en filas."""
        if not self.doc or len(self.doc) < 2:
            return 1
        cell = max(self.doc[i].rect.width for i in range(len(self.doc))) * self.zoom + 24.0
        avail = self.viewport().width() - 12 - 2 * 30          # hueco a los lados para los «+»
        return max(1, min(len(self.doc), int((avail + 24.0) // cell)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.doc is not None and self._page_items and self._calc_cols() != self._cols:
            QTimer.singleShot(0, self._relayout_if_needed)

    def _relayout_if_needed(self):
        if self.doc is not None and self._calc_cols() != self._cols:
            self.reload_preserving_scroll()

    def _overview_click(self, scene_pos: QPointF):
        """Con varias páginas por fila (vista general): un clic en una página la acerca para trabajar en ella."""
        for i, it in enumerate(self._page_items):
            if it.sceneBoundingRect().contains(scene_pos):
                self.fit_width()
                self.scroll_to_page(i)
                if self._on_notice:
                    self._on_notice(tr("Vista general: has acercado la página {n} para poder editarla.", n=i + 1))
                return

    def _add_page_bar(self, idx: int, top: float, page_w: float, max_w: float, last: bool = False, px: float = 0.0):
        """Barra encima de cada página (y una al final) para borrar, girar, acercar o insertar una página."""
        w = page_w if page_w else max_w
        item = PageBarItem(idx, last, lambda a, i: self.page_action.emit(a, i), compact=self._cols > 1)
        if last and self._cols > 1:
            px = 0.0
        item.setPos(px + max(0.0, (w - item.width_) / 2), top - self._bar_h - 6)
        item.setZValue(60)
        self.scene_.addItem(item)

    def _build_spans(self, doc, page_idx: int, y_offset: float) -> list:
        """Zonas clicables: un párrafo entero para editar y, para censurar,
        cada fragmento de texto por separado (solo se ve la de su modo)."""
        items = []
        if self._is_rotated(page_idx) or self._cols > 1:
            return items
        for kind, source in (("edit", be.get_page_paragraphs(doc, page_idx, manual=self.manual)),
                             ("censor", be.get_page_text_spans(doc, page_idx))):
            for span in source:
                x0, y0, x1, y1 = span["bbox"]
                rect = QRectF(x0 * self.zoom, y_offset + y0 * self.zoom,
                               (x1 - x0) * self.zoom, (y1 - y0) * self.zoom)
                item = SpanRectItem(rect, span, page_idx, self._open_inline_editor,
                                     mode_provider=lambda: self.mode)
                item.kind = kind
                item.setVisible(kind == self.mode)
                self.scene_.addItem(item)
                items.append(item)
        return items

    def reload_preserving_scroll(self):
        vbar = self.verticalScrollBar()
        val = vbar.value()
        self.load_doc(self.doc)
        vbar.setValue(val)

    def refresh_page(self, page_idx: int):
        """Vuelve a renderizar SOLO la página indicada (tras una edición o
        censura), sin tocar el resto del documento: mucho más rápido que
        recargarlo entero en PDFs de muchas páginas."""
        if not self.doc or not (0 <= page_idx < len(self._page_items)):
            self.reload_preserving_scroll()
            return
        png = be.render_doc_page_png(self.doc, page_idx, zoom=self.zoom, annots=not self.hide_annots)
        if not png:
            return
        pix = QPixmap()
        pix.loadFromData(png)
        self._page_items[page_idx].setPixmap(pix)
        for item in self._page_span_items[page_idx]:
            self.scene_.removeItem(item)
        self._page_span_items[page_idx] = self._build_spans(
            self.doc, page_idx, self._page_tops[page_idx])

    def scroll_to_page(self, idx: int):
        if not self._page_items:
            return
        idx = max(0, min(idx, len(self._page_items) - 1))
        top = self._page_tops[idx]
        self.verticalScrollBar().setValue(max(0, int(top - self._bar_h - 8)))

    def _update_current_page(self, _value=None):
        if not self._page_tops:
            return
        top_y = self.mapToScene(0, 4).y()
        idx = 0
        for i, t in enumerate(self._page_tops):
            if t - self._bar_h - 8 <= top_y + 2:
                idx = i
            else:
                break
        if idx != self._current_page:
            self._current_page = idx
            if self._on_page_visible:
                self._on_page_visible(idx, len(self._page_items))

    # ── Modo censurar: clic o clic-y-arrastre sobre el área a tapar ─────
    def tabletEvent(self, e):
        """Lápiz óptico: guarda la presión (grosor del trazo) y usa el extremo borrador para borrar dibujos libres.
        El resto sigue como ratón (Qt genera los eventos de ratón si aquí no se acepta)."""
        from PySide6.QtGui import QPointingDevice
        ptype = e.pointerType()
        if ptype == QPointingDevice.PointerType.Eraser:
            if (self.doc is not None and self._cols == 1 and self.mode in ("edit", "shape")
                    and self._editor is None and e.pressure() > 0):
                sp_ = self.mapToScene(e.position().toPoint())
                pi = self._page_at_y(sp_.y(), quiet=True)
                hit = at.editable_at(self.doc, pi, self._mk_pdf_point(sp_, pi)) if pi is not None else None
                if hit and hit["kind"] == "ink":
                    self._ss_sel = {"page": pi, "desc": hit}
                    self.delete_selection()
            e.accept()
            return
        self._pressure = e.pressure() if (ptype == QPointingDevice.PointerType.Pen and e.pressure() > 0) else None
        e.ignore()

    def start_eyedropper(self, callback):
        """El siguiente clic sobre una página toma ese color (se pasa a `callback` como (r, g, b) en 0..1)."""
        self._eyedrop = callback
        self.viewport().setCursor(Qt.CrossCursor)
        if self._on_notice:
            self._on_notice(tr("Cuentagotas: haz clic en cualquier punto de la página para tomar su color."))

    def _eyedrop_pick(self, e):
        cb, self._eyedrop = self._eyedrop, None
        self.viewport().setCursor(Qt.ArrowCursor if self.mode in ("edit", "shape") else Qt.CrossCursor)
        sp0 = self.mapToScene(e.pos())
        for it in self._page_items:
            if it.sceneBoundingRect().contains(sp0):
                img = it.pixmap().toImage()
                c = img.pixelColor(int(sp0.x() - it.x()), int(sp0.y() - it.y()))
                cb((c.redF(), c.greenF(), c.blueF()))
                return

    def mousePressEvent(self, e):
        if self._eyedrop is not None and e.button() == Qt.LeftButton:
            self._eyedrop_pick(e)
            e.accept()
            return
        if isinstance(self.itemAt(e.pos()), (PageBarItem, GutterPlusItem)):
            self._bar_press = True
            super().mousePressEvent(e)
            return
        if self._cols > 1:
            if e.button() == Qt.LeftButton:
                self._overview_click(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "markup" and e.button() == Qt.LeftButton:
            self._mk_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "shape" and e.button() == Qt.LeftButton:
            self.setFocus()
            self._sh_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "image" and e.button() == Qt.LeftButton:
            self.setFocus()
            self._img_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "link" and e.button() == Qt.LeftButton:
            self._lk_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "form" and e.button() == Qt.LeftButton:
            self._fm_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode in ("note", "attach") and e.button() == Qt.LeftButton:
            self._nt_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "copy" and e.button() == Qt.LeftButton:
            self._cp_press(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "text" and e.button() == Qt.LeftButton:
            self._open_new_text(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "censor" and e.button() == Qt.LeftButton:
            self._censor_drag_start = self.mapToScene(e.pos())
            self._censor_rect_item = self.scene_.addRect(
                QRectF(self._censor_drag_start, self._censor_drag_start),
                QPen(Qt.NoPen), QBrush(QColor(20, 18, 12, 190)))
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._cols > 1 or self._bar_press:
            super().mouseMoveEvent(e)
            return
        if self.mode == "markup":
            self._mk_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "shape":
            if not self._ss_move_evt(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier)):
                self._sh_move_evt(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "image":
            self._img_move(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "link":
            self._lk_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "form":
            self._fm_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode in ("note", "attach"):
            self._nt_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "copy":
            self._cp_move(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "censor" and self._censor_drag_start is not None:
            cur = self.mapToScene(e.pos())
            self._censor_rect_item.setRect(QRectF(self._censor_drag_start, cur).normalized())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._bar_press or self._cols > 1:
            self._bar_press = False
            super().mouseReleaseEvent(e)
            return
        if self.mode == "markup" and e.button() == Qt.LeftButton:
            self._mk_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "shape" and e.button() == Qt.LeftButton:
            if self._ss_drag:
                self._ss_release(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            else:
                self._sh_release(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "image" and e.button() == Qt.LeftButton:
            self._img_release(self.mapToScene(e.pos()), bool(e.modifiers() & Qt.ShiftModifier))
            e.accept()
            return
        if self.mode == "link" and e.button() == Qt.LeftButton:
            self._lk_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "form" and e.button() == Qt.LeftButton:
            self._fm_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode in ("note", "attach") and e.button() == Qt.LeftButton:
            self._nt_release(self.mapToScene(e.pos()), e.globalPosition().toPoint())
            e.accept()
            return
        if self.mode == "copy" and e.button() == Qt.LeftButton:
            self._cp_release(self.mapToScene(e.pos()))
            e.accept()
            return
        if self.mode == "censor" and self._censor_drag_start is not None:
            start = self._censor_drag_start
            cur = self.mapToScene(e.pos())
            self._censor_drag_start = None
            if self._censor_rect_item is not None:
                self.scene_.removeItem(self._censor_rect_item)
                self._censor_rect_item = None
            rect = QRectF(start, cur).normalized()
            if rect.width() < 4 and rect.height() < 4:
                item = self.scene_.itemAt(cur, self.transform())
                if isinstance(item, SpanRectItem):
                    self._censor_pdf_rect(item.page_idx, item.span["bbox"])
                else:
                    half_w, half_h = 55.0, 11.0
                    self._censor_scene_rect(QRectF(cur.x() - half_w, cur.y() - half_h,
                                                    half_w * 2, half_h * 2))
            else:
                self._censor_scene_rect(rect)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def _page_index(self, y: float):
        if not self._page_tops:
            return None
        idx = 0
        for i, t in enumerate(self._page_tops):
            if t <= y:
                idx = i
            else:
                break
        return idx

    def _is_rotated(self, idx) -> bool:
        try:
            return idx is not None and bool(self.doc) and self.doc[idx].rotation % 360 != 0
        except Exception:
            return False

    def _page_at_y(self, y: float, quiet: bool = False):
        """Página bajo una coordenada, para las herramientas de edición. En páginas giradas devuelve None
        (las coordenadas de edición no coinciden con lo que se ve): hay que volver a girarlas antes."""
        idx = self._page_index(y)
        if self._is_rotated(idx):
            if not quiet and self._on_notice:
                self._on_notice(tr("Esta página está girada: para editarla, vuelve a girarla a su posición original "
                                "(botones de giro sobre la página)."))
            return None
        return idx

    # ── Zoom ────────────────────────────────────────────────────────────
    def set_zoom(self, z):
        if z is None or not self.doc:
            return
        z = max(self.ZOOM_MIN, min(self.ZOOM_MAX, float(z)))
        self._zoom_pending = None
        if abs(z - self.zoom) < 0.005:
            self.zoomed.emit(self.zoom)
            return
        self._close_inline_editor(commit=True)
        self._fm_close(True)
        top_y = self.mapToScene(0, 0).y()
        pi = self._page_index(top_y) or 0
        off = (top_y - self._page_tops[pi]) / self.zoom if self._page_tops else 0.0
        hx = self.horizontalScrollBar().value() / self.zoom
        self.zoom = z
        self.load_doc(self.doc)
        if self._page_tops:
            self.verticalScrollBar().setValue(int(self._page_tops[min(pi, len(self._page_tops) - 1)] + off * z))
        self.horizontalScrollBar().setValue(int(hx * z))
        self.zoomed.emit(z)

    def zoom_by(self, factor: float):
        self.set_zoom(self.zoom * factor)

    def fit_width(self):
        if not self.doc or not len(self.doc):
            return
        pw = max(self.doc[i].rect.width for i in range(len(self.doc)))
        self.set_zoom((self.viewport().width() - 6) / max(pw, 1.0))

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            base_z = self._zoom_pending or self.zoom
            self._zoom_pending = max(self.ZOOM_MIN, min(self.ZOOM_MAX, base_z * (1.12 ** (e.angleDelta().y() / 120))))
            self._zoom_timer.start(140)
            e.accept()
            return
        super().wheelEvent(e)

    def _censor_scene_rect(self, rect: QRectF):
        """Clic-sin-span o arrastre: usa censura 'inteligente' por palabras,
        que solo tapa el texto real dentro del área (si lo hay)."""
        page_idx = self._page_at_y(rect.center().y())
        if page_idx is None:
            return
        y_off = self._page_tops[page_idx]
        bbox = (rect.x() / self.zoom, (rect.y() - y_off) / self.zoom,
                (rect.x() + rect.width()) / self.zoom, (rect.y() + rect.height() - y_off) / self.zoom)
        if not self.doc:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = be.censor_area_in_doc(self.doc, page_idx, bbox)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)

    def _censor_pdf_rect(self, page_idx: int, bbox: tuple):
        """Clic directo sobre un fragmento ya localizado: tapa exactamente
        esa caja, sin necesidad de volver a buscar texto."""
        if not self.doc:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        ok = be.censor_rect_in_doc(self.doc, page_idx, bbox)
        if ok:
            self._on_dirty()
            self.refresh_page(page_idx)

    def _open_inline_editor(self, item: SpanRectItem):
        self._close_inline_editor(commit=True)   # confirma cualquier edición pendiente
        view_rect = self.mapFromScene(item.rect()).boundingRect()
        editor = QTextEdit(self.viewport())
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.WidgetWidth)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setFrameShape(QFrame.NoFrame)
        editor.document().setDocumentMargin(0)
        editor.viewport().setAutoFillBackground(False)
        editor.setContextMenuPolicy(Qt.CustomContextMenu)
        editor.customContextMenuRequested.connect(self._editor_menu)
        self._view_rect = view_rect
        self._editor = editor
        self._editing_item = item
        self._deleting = False
        para = item.span
        # El texto se muestra con el estilo de cada tramo (negrita, color, tamaño, fuente).
        runs = para.get("runs") or [{"text": para["text"], "font": para["font"], "family": None,
                                     "bold": winfonts.style_from_ps_name(para["font"])[0],
                                     "italic": winfonts.style_from_ps_name(para["font"])[1],
                                     "size": para["size"], "color": para["color"]}]
        cur = QTextCursor(editor.document())
        for r in runs:
            fmt = self._char_format(r)
            for i, part in enumerate(r["text"].split("\n")):
                if i:
                    cur.insertBlock(QTextBlockFormat(), fmt)
                cur.insertText(part, fmt)
        editor.setCurrentCharFormat(self._char_format(runs[-1]))      # lo que se escriba lleva este estilo
        self._apply_editor_style()
        self._cover_original_text(item)
        editor.document().setModified(False)
        self._text0 = editor.toPlainText()
        editor.show()
        editor.setFocus()
        self._fit_editor()                      # ya con el ancho real, para que la altura sea exacta
        # Cursor parpadeando justo donde se hizo clic (sin seleccionar todo).
        editor.setTextCursor(editor.cursorForPosition(
            editor.viewport().mapFromGlobal(QCursor.pos())))
        editor.textChanged.connect(self._fit_editor)
        editor.cursorPositionChanged.connect(self._refresh_toolbar)
        editor.installEventFilter(self)
        self._build_toolbar()

    def _cover_original_text(self, item):
        """Tapa el texto original con la misma zona de la página SIN ese texto (fondo, dibujos e imágenes intactos):
        así el editor se ve directamente sobre la página, sin recuadro ni parches de color."""
        self._remove_cover()
        para = item.span
        if para.get("new") or not self.doc:
            return
        wrap = para["wrap_w"]
        if para["align"] == "center":
            left = (para["bbox"][0] + para["bbox"][2]) / 2 - wrap / 2
        else:
            left = para.get("body_x", para["bbox"][0])
        rect = (left, para["bbox"][1], left + wrap + 2, para["bbox"][3] + 1)
        png = be.render_text_free_clip(self.doc, item.page_idx, rect, self.zoom)
        if not png:
            return
        pm = QPixmap()
        pm.loadFromData(png)
        cover = self.scene_.addPixmap(pm)
        cover.setPos(rect[0] * self.zoom, self._page_tops[item.page_idx] + rect[1] * self.zoom)
        cover.setZValue(45)
        self._edit_cover = cover

    def _remove_cover(self):
        cover = getattr(self, "_edit_cover", None)
        self._edit_cover = None
        if cover is not None:
            try:
                self.scene_.removeItem(cover)
            except RuntimeError:
                pass

    def _word_at(self, page_idx: int, pt: tuple) -> str:
        """Palabra del PDF que hay bajo el punto (sin signos de puntuación en los extremos)."""
        try:
            words = self.doc[page_idx].get_text("words")
        except Exception:
            return ""
        best, best_d = "", 1e9
        for w in words:
            dx = max(w[0] - pt[0], 0, pt[0] - w[2])
            dy = max(w[1] - pt[1], 0, pt[1] - w[3])
            d = (dx * dx + dy * dy) ** 0.5
            if d < best_d:
                best, best_d = w[4], d
        return best.strip(" \t.,;:()[]{}«»\"'¿?¡!") if best_d < 6 else ""

    def _editor_menu(self, pos):
        """Clic derecho dentro del editor: el menú normal más «Reemplazar…» con el texto elegido ya puesto."""
        ed = self._editor
        if ed is None:
            return
        menu = ed.createStandardContextMenu()
        cur = ed.textCursor()
        sel = cur.selectedText().replace("\u2029", "\n").replace("\u2028", "\n")
        if not sel.strip():
            c2 = ed.cursorForPosition(pos)
            c2.select(QTextCursor.WordUnderCursor)
            sel = c2.selectedText()
        sel = sel.strip()
        if sel:
            menu.addSeparator()
            shown = sel if len(sel) <= 32 else sel[:30] + "…"
            act = menu.addAction(ic.icon("swap", TEXT, 16), tr("Reemplazar «{w}»…", w=shown))
            act.triggered.connect(lambda _=False, s=sel: self.replace_requested.emit(s))
        menu.exec(ed.mapToGlobal(pos))

    # ── Formato de los tramos de texto ──────────────────────────────────
    _FALLBACK_FONT = "Arial"

    def _font_installed(self, ps_name: str, family: str) -> bool:
        cache = self.__dict__.setdefault("_font_ok", {})
        if ps_name not in cache:
            cache[ps_name] = (winfonts.find_font_file(ps_name)[0] is not None) or QFontDatabase.hasFamily(family)
        return cache[ps_name]

    def _ps_family(self, ps_name: str) -> str:
        fam = winfonts.guess_family_from_ps_name(ps_name)
        if fam.lower() in ("helvetica", "helv"):
            return "Arial"                                  # Windows no tiene Helvetica
        # Si la fuente no está instalada se muestra (y se guarda) con la misma de respaldo: lo que ves es lo que sale.
        return fam if self._font_installed(ps_name, fam) else self._FALLBACK_FONT

    def _char_format(self, run: dict) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamilies([run.get("family") or self._ps_family(run["font"])])
        fmt.setFontWeight(700 if run["bold"] else 400)
        fmt.setFontItalic(bool(run["italic"]))
        fmt.setProperty(QTextFormat.Property.FontPixelSize, max(6, int(round(run["size"] * self.zoom))))
        fmt.setForeground(QBrush(QColor.fromRgb(int(run["color"]) & 0xFFFFFF)))
        fmt.setProperty(_PROP_FONT, run["font"])             # fuente original del PDF
        fmt.setProperty(_PROP_SIZE, float(run["size"]))
        if run.get("family"):
            fmt.setProperty(_PROP_FAMILY, True)              # el usuario eligió otra fuente
        return fmt

    def _style_of(self, fmt: QTextCharFormat) -> dict:
        para = self._editing_item.span
        px = fmt.intProperty(QTextFormat.Property.FontPixelSize)
        fams = fmt.fontFamilies()
        fam = fams[0] if fams else self._ps_family(para["font"])
        brush = fmt.foreground()
        color = (brush.color().rgb() & 0xFFFFFF) if brush.style() != Qt.NoBrush else int(para["color"])
        ps = fmt.property(_PROP_FONT)
        exact = fmt.property(_PROP_SIZE)
        return {"font": ps if isinstance(ps, str) and ps else para["font"],
                "family": fam if fmt.property(_PROP_FAMILY) else None, "display_family": fam,
                "bold": fmt.fontWeight() >= 600, "italic": fmt.fontItalic(),
                "size": (float(exact) if isinstance(exact, (int, float)) and exact > 0
                         else round(px / self.zoom, 1) if px > 0 else para["size"]), "color": color}

    def _current_style(self) -> dict:
        return self._style_of(self._editor.currentCharFormat())

    def _collect_runs(self) -> list[dict]:
        """Texto del editor como tramos con su estilo, para guardarlo en el PDF."""
        runs: list[dict] = []

        def add(text: str, st: dict):
            if not text:
                return
            st = {k: st[k] for k in ("font", "family", "bold", "italic", "size", "color")}
            if runs and all(runs[-1][k] == st[k] for k in st):
                runs[-1]["text"] += text
            else:
                runs.append({"text": text, **st})

        blk = self._editor.document().begin()
        first, last = True, None
        while blk.isValid():
            if not first and last is not None:
                add("\n", last)
            first = False
            it = blk.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    last = self._style_of(frag.charFormat())
                    add(frag.text().replace("\u2028", "\n"), last)
                it += 1
            blk = blk.next()
        return runs

    # ── Barra flotante de formato (negrita, cursiva, tamaño, fuente, color) ─
    def _apply_editor_style(self):
        """Aspecto del editor (fondo de papel, borde) y su interlineado, ancho y posición."""
        ed = self._editor
        para = self._editing_item.span
        col = int(para["color"]) & 0xFFFFFF
        # Sin caja, sin borde y sin fondo: solo el texto y el cursor (el texto original se tapa con el propio fondo
        # de la página, ver _cover_original_text). La selección se pinta suave para que el texto siga leyéndose.
        ed.setStyleSheet(
            f"QTextEdit {{ background:transparent; color:#{col:06x}; border:none; padding:0px; "
            f"selection-background-color:rgba(192,130,88,0.38); selection-color:#{col:06x}; }}")
        pal = ed.palette()
        pal.setColor(pal.ColorRole.Text, QColor.fromRgb(col))               # el cursor toma el color del texto
        ed.setPalette(pal)
        ed.setCursorWidth(max(2, int(round(para["size"] * self.zoom * 0.07))))
        # Interlineado del PDF: así el editor ocupa la altura que tendrá el párrafo.
        base = QFont(self._ps_family(para["font"]))
        base.setPixelSize(max(6, int(round(para["size"] * self.zoom))))
        natural = max(QFontMetrics(base).lineSpacing(), 1)
        block = QTextBlockFormat()
        block.setLineHeight(max(100.0, para["pitch"] * self.zoom / natural * 100),
                            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block.setAlignment({"center": Qt.AlignHCenter, "justify": Qt.AlignJustify}.get(
            para["align"], Qt.AlignLeft))
        cur = QTextCursor(ed.document())
        cur.select(QTextCursor.Document)
        cur.mergeBlockFormat(block)
        r = self._view_rect
        pad = 0
        wrap_px = para["wrap_w"] * self.zoom
        if para["align"] == "center":
            left = r.center().x() - wrap_px / 2
        else:                                   # con etiqueta («h)», viñeta) el texto empieza a su derecha
            left = r.x() + (para.get("body_x", para["bbox"][0]) - para["bbox"][0]) * self.zoom
        self._min_h = r.height()
        ed.setGeometry(int(left - pad), int(r.y() - pad), int(wrap_px + pad * 2 + 4), int(self._min_h))
        self._fit_editor()
        self._refresh_toolbar()

    def _fit_editor(self, *_):
        """Ajusta la altura del editor al texto (el ancho es el margen de la página)."""
        ed = self._editor
        if ed is None:
            return
        ed.document().setTextWidth(ed.viewport().width())
        height = int(ed.document().size().height()) + 1
        ed.setFixedHeight(max(height, int(self._min_h)))
        self._place_toolbar()

    def _build_toolbar(self):
        tb = _ToolBar(self.viewport())
        tb.setObjectName("EditToolbar")
        # Un clic en la barra (o en un botón sin foco) le da el foco al primer
        # ancestro que lo acepte; con el editor de proxy, el foco se queda en el texto.
        tb.setFocusPolicy(Qt.ClickFocus)
        tb.setFocusProxy(self._editor)
        tb.setStyleSheet(
            f"#EditToolbar {{ background:{SURFACE_2}; border:1px solid {BORDER_STRONG}; border-radius:10px; }}"
            f"#EditToolbar QPushButton {{ background:transparent; border:none; border-radius:7px;"
            f" color:{TEXT}; min-height:30px; max-height:30px; padding:0 8px; font-size:13px; }}"
            f"#EditToolbar QPushButton:hover {{ background:rgba(243,241,228,0.10); }}"
            f"#EditToolbar QPushButton:checked {{ background:{ACCENT}; }}"
            f"#EditToolbar QFrame#Sep {{ background:{BORDER_STRONG}; }}")
        shadow = QGraphicsDropShadowEffect(tb)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 120))
        tb.setGraphicsEffect(shadow)
        lay = QHBoxLayout(tb)
        lay.setContentsMargins(5, 4, 5, 4)
        lay.setSpacing(2)

        def button(tip, icon_name=None, checkable=False, width=None):
            b = QPushButton()
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.NoFocus)          # el cursor sigue en el texto
            b.setCursor(Qt.PointingHandCursor)
            if icon_name:
                b.setIcon(_toggle_icon(icon_name))
                b.setIconSize(QSize(18, 18))
            if width:
                b.setFixedWidth(width)
            return b

        def dropdown(b):
            b.setLayoutDirection(Qt.RightToLeft)   # la flecha a la derecha del texto
            b.setIcon(ic.icon("chevron_down", TEXT_SOFT, 12))
            b.setIconSize(QSize(11, 11))
            return b

        def sep():
            s = QFrame()
            s.setObjectName("Sep")
            s.setFixedSize(1, 20)
            return s

        self._tb_font = dropdown(button(tr("Fuente"), width=134))
        self._tb_font.clicked.connect(self._open_font_popup)
        self._tb_size = dropdown(button(tr("Tamaño del texto"), width=58))
        self._tb_size.clicked.connect(self._open_size_popup)
        self._tb_bold = button(tr("Negrita"), "bold", True, 32)
        self._tb_bold.toggled.connect(lambda on: self._set_fmt("bold", on))
        self._tb_italic = button(tr("Cursiva"), "italic", True, 32)
        self._tb_italic.toggled.connect(lambda on: self._set_fmt("italic", on))
        self._tb_color = button(tr("Color del texto"), width=52)
        self._tb_color.setIconSize(QSize(34, 16))
        self._tb_color.clicked.connect(self._open_color_popup)
        trash = button(tr("Borrar este texto"), "trash", width=32)
        trash.clicked.connect(self._delete_text)
        plus = button(tr("Añadir un elemento debajo (con su etiqueta o viñeta, y renumera los siguientes)"),
                      "clip", width=32)
        plus.clicked.connect(self._insert_below)
        plus.setVisible(not self.manual and not self._editing_item.span.get("new"))

        for w in (self._tb_font, self._tb_size, sep(), self._tb_bold, self._tb_italic,
                  self._tb_color, sep(), plus, trash):
            lay.addWidget(w)
        tb.adjustSize()
        self._toolbar = tb
        self._refresh_toolbar()
        tb.show()
        self._place_toolbar()

    def _refresh_toolbar(self):
        """Pone en la barra el formato del texto bajo el cursor (o de la selección)."""
        if getattr(self, "_toolbar", None) is None or self._editor is None:
            return
        st = self._current_style()
        self._tb_font.setText(QFontMetrics(self._tb_font.font()).elidedText(
            st["display_family"], Qt.ElideRight, 100))
        self._tb_size.setText(f"{round(st['size'], 1):g}")
        for btn, key in ((self._tb_bold, "bold"), (self._tb_italic, "italic")):
            btn.blockSignals(True)
            btn.setChecked(st[key])
            btn.blockSignals(False)
        pm = QPixmap(34, 16)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 110), 1))
        p.setBrush(QColor.fromRgb(st["color"]))
        p.drawEllipse(1, 1, 14, 14)
        p.drawPixmap(20, 2, ic.icon("chevron_down", TEXT_SOFT, 12).pixmap(12, 12))
        p.end()
        self._tb_color.setIcon(QIcon(pm))

    def _popup_below(self, button, build) -> "_ToolPopup":
        pop = _ToolPopup(self.viewport())
        build(pop)
        pop.adjustSize()
        pop.move(button.mapToGlobal(QPoint(0, button.height() + 6)))
        pop.show()
        return pop

    def _choose(self, pop, key, value):
        pop.close()
        self._set_fmt(key, value)

    def _open_size_popup(self):
        size = self._current_style()["size"]

        def build(pop):
            spin = QSpinBox()
            spin.setRange(4, 300)
            spin.setSuffix(" pt")
            spin.setValue(int(round(size)))
            spin.editingFinished.connect(lambda: self._choose(pop, "size", float(spin.value())))
            lst = _popup_list(96, 230)
            current = None
            for s in (6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72, 96):
                it = QListWidgetItem(f"{s}")
                it.setData(Qt.UserRole, s)
                lst.addItem(it)
                if abs(size - s) < 0.5:
                    current = it
            if current:
                lst.setCurrentItem(current)
            lst.itemClicked.connect(lambda it: self._choose(pop, "size", float(it.data(Qt.UserRole))))
            pop.lay.addWidget(spin)
            pop.lay.addWidget(lst)
        self._popup_below(self._tb_size, build)

    def _open_font_popup(self):
        cur_family = self._current_style()["display_family"]

        def build(pop):
            search = QLineEdit()
            search.setPlaceholderText(tr("Buscar fuente…"))
            lst = _popup_list(250, 300)
            families = QFontDatabase.families()
            for fam in families:
                it = QListWidgetItem(fam)
                it.setFont(QFont(fam, 11))        # cada nombre con su propia fuente
                lst.addItem(it)
            for i in range(lst.count()):
                if lst.item(i).text() == cur_family:
                    lst.setCurrentRow(i)
                    lst.scrollToItem(lst.item(i), QAbstractItemView.PositionAtCenter)
                    break

            def filt(text):
                t = text.lower()
                for i in range(lst.count()):
                    lst.item(i).setHidden(t not in lst.item(i).text().lower())
            search.textChanged.connect(filt)
            lst.itemClicked.connect(lambda it: self._choose(pop, "family", it.text()))
            pop.lay.addWidget(search)
            pop.lay.addWidget(lst)
        self._popup_below(self._tb_font, build)

    def _open_color_popup(self):
        palette = ["#000000", "#434343", "#666666", "#999999", "#cccccc", "#ffffff",
                   "#c0392b", "#e67e22", "#f1c40f", "#27ae60", "#16a085", "#2980b9",
                   "#8e44ad", "#d81b60", "#795548", "#1f8033", "#0b5394", "#7f6000"]
        current = self._current_style()["color"]
        original = int(self._editing_item.span["color"]) & 0xFFFFFF

        def build(pop):
            grid = QGridLayout()
            grid.setSpacing(6)
            colors = [f"#{original:06x}"] + palette
            for i, hexc in enumerate(colors):
                b = _Swatch(hexc, QColor(hexc).rgb() & 0xFFFFFF == current)
                b.setToolTip(tr("Color original") if i == 0 else hexc)
                b.clicked.connect(lambda _=False, h=hexc: self._choose(
                    pop, "color", QColor(h).rgb() & 0xFFFFFF))
                grid.addWidget(b, i // 6, i % 6)
            more = QPushButton(tr("Otro color…"))
            more.setFocusPolicy(Qt.NoFocus)
            more.clicked.connect(lambda: (pop.close(), self._pick_color()))
            pop.lay.addLayout(grid)
            pop.lay.addWidget(more)
        self._popup_below(self._tb_color, build)

    def _place_toolbar(self):
        tb = getattr(self, "_toolbar", None)
        if tb is None or self._editor is None:
            return
        ed = self._editor.geometry()
        x = max(4, min(ed.x(), self.viewport().width() - tb.width() - 4))
        y = ed.y() - tb.height() - 6
        if y < 2:
            y = ed.bottom() + 6
        tb.move(x, y)
        tb.raise_()

    def _set_fmt(self, key, value):
        """Aplica un formato a la selección; sin selección, a todo el párrafo."""
        if self._editor is None:
            return
        ed = self._editor
        fmt = QTextCharFormat()
        if key == "bold":
            fmt.setFontWeight(700 if value else 400)
        elif key == "italic":
            fmt.setFontItalic(bool(value))
        elif key == "size":
            fmt.setProperty(QTextFormat.Property.FontPixelSize, max(6, int(round(float(value) * self.zoom))))
            fmt.setProperty(_PROP_SIZE, float(value))
        elif key == "family":
            fmt.setFontFamilies([value])
            fmt.setProperty(_PROP_FAMILY, True)
        elif key == "color":
            fmt.setForeground(QBrush(QColor.fromRgb(int(value) & 0xFFFFFF)))
        cur = ed.textCursor()
        target = QTextCursor(cur)
        if not cur.hasSelection():
            target.select(QTextCursor.Document)
            ed.mergeCurrentCharFormat(fmt)          # y lo que se escriba a continuación
        target.mergeCharFormat(fmt)
        ed.setFocus()
        self._fit_editor()
        self._refresh_toolbar()

    def _pick_color(self):
        if self._editor is None:
            return
        self._dialog_open = True
        col = QColorDialog.getColor(QColor.fromRgb(self._current_style()["color"]), self, tr("Color del texto"))
        self._dialog_open = False
        if self._editor is None:
            return
        if col.isValid():
            self._set_fmt("color", col.rgb() & 0xFFFFFF)
        self._editor.setFocus()

    def _open_new_text(self, scene_pos: QPointF):
        """Modo texto libre: un clic en la página abre un editor vacío justo ahí."""
        if not self.doc:
            return
        page_idx = self._page_at_y(scene_pos.y())
        if page_idx is None:
            return
        y_off = self._page_tops[page_idx]
        x, y = scene_pos.x() / self.zoom, (scene_pos.y() - y_off) / self.zoom
        page_w = self.doc[page_idx].rect.width
        near = min((it for it in self._page_span_items[page_idx] if it.kind == "edit"),
                   key=lambda it: abs((it.span["bbox"][1] + it.span["bbox"][3]) / 2 - y), default=None)
        base = near.span if near else {"font": "ArialMT", "size": 11.0, "color": 0}
        size = float(base["size"])
        right = max(page_w - be._doc_geometry(self.doc)["left"], x + 80)
        span = {"text": "", "runs": [], "bbox": (x, y, x + 10, y + size * 1.25), "size": size,
                "color": base["color"], "font": base["font"], "pitch": size * 1.2, "n_lines": 0,
                "origin_y": y + size * 0.9, "x_first": x, "x_cont": x, "body_x": x, "align": "left",
                "label": None, "wrap_w": right - x, "wrap_first": right - x, "wrap_cont": right - x,
                "wrap_right": right, "shift_x0": 0.0, "shift_x1": page_w, "new": True}
        rect = QRectF(x * self.zoom, y_off + y * self.zoom, (right - x) * self.zoom, size * 1.25 * self.zoom)
        self.set_mode("edit")
        self.mode_changed.emit("edit")
        self._open_inline_editor(_VirtualItem(page_idx, rect, span))

    def _edit_at(self, page_idx: int, y_top: float):
        """Abre el editor en el elemento que empieza en y_top (tras insertarlo)."""
        for it in self._page_span_items[page_idx] if page_idx < len(self._page_span_items) else []:
            if it.kind == "edit" and abs(it.span["bbox"][1] - y_top) < 8:
                self._open_inline_editor(it)
                self._editor.selectAll()
                return

    def _insert_below(self):
        """Botón «+»: añade debajo del elemento en edición otro igual (con su etiqueta)."""
        item = self._editing_item
        if self._editor is None or item is None or item.span.get("new") or self.manual:
            return
        page_idx, y0, x0 = item.page_idx, item.span["bbox"][1], item.span["bbox"][0]
        self._close_inline_editor(commit=True)               # confirma lo escrito
        cand = [p for p in be.get_page_paragraphs(self.doc, page_idx)
                if abs(p["bbox"][1] - y0) < 3 and abs(p["bbox"][0] - x0) < 3]
        if not cand:
            return
        if self._on_before_mutate:
            self._on_before_mutate()
        pages_before = len(self.doc)
        res = be.insert_item_below(self.doc, page_idx, cand[0], tr("Novo elemento"), settings=self.hf)
        if not res["ok"]:
            if self._on_notice:
                self._on_notice(tr("No se pudo añadir el elemento."))
            return
        self._on_dirty()
        if len(self.doc) != pages_before:
            self.reload_preserving_scroll()
        else:
            for p in res["pages"]:
                self.refresh_page(p)
        QTimer.singleShot(0, lambda: self._edit_at(res["page"], res["y"]))

    def _delete_text(self):
        if self._editor is not None:
            self._editor.setPlainText("")
            self._deleting = True
            self._close_inline_editor(commit=True)

    def ask_header_footer(self, page_idx: int, intro: str = "") -> bool:
        """Abre el diálogo de cabecera y pie; guarda los ajustes si se acepta."""
        if not self.doc:
            return False
        dlg = HeaderFooterDialog(self.doc, page_idx, self.hf, self.window(), intro)
        if dlg.exec() == QDialog.Accepted:
            self.hf = dlg.settings
            return True
        return False

    def _maybe_close_editor(self, source=None):
        """Cerrar al perder el foco, salvo que sea por usar la barra de formato. `source` es el
        editor que lo provocó: si ya se cerró y hay otro abierto, no se toca el nuevo."""
        if self._editor is None or getattr(self, "_dialog_open", False):
            return
        if source is not None and source is not self._editor:
            return
        fw = QApplication.focusWidget()
        tb = getattr(self, "_toolbar", None)
        if QApplication.activePopupWidget() is not None or fw is self._editor \
                or (tb is not None and fw is not None and tb.isAncestorOf(fw)):
            return
        self._close_inline_editor(commit=True)

    def eventFilter(self, obj, e):
        if obj is self._editor:
            if e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key_Escape:
                self._close_inline_editor(commit=False)
                return True
            if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key_Return, Qt.Key_Enter) \
                    and e.modifiers() & Qt.ControlModifier:
                self._close_inline_editor(commit=True)      # Ctrl+Enter confirma; Enter = línea nueva
                return True
            if e.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(0, lambda ed=obj: self._maybe_close_editor(ed))
        return super().eventFilter(obj, e)

    def _close_inline_editor(self, commit: bool):
        if self._editor is None:
            return
        editor, item = self._editor, self._editing_item
        self._remove_cover()
        runs = self._collect_runs()
        changed = editor.document().isModified() or editor.toPlainText() != self._text0
        toolbar = getattr(self, "_toolbar", None)
        self._editor, self._editing_item, self._toolbar = None, None, None
        editor.removeEventFilter(self)
        editor.hide()
        editor.deleteLater()
        if toolbar is not None:
            toolbar.hide()
            toolbar.deleteLater()
        if commit and item is not None and changed:
            para = item.span
            new_text = "".join(r["text"] for r in runs)
            if para.get("new"):                                   # texto libre nuevo
                if new_text.strip():
                    if self._on_before_mutate:
                        self._on_before_mutate()
                    res = be.add_text_box(self.doc, item.page_idx, para["x_first"], para["bbox"][1],
                                          [dict(r) for r in runs], settings=self.hf)
                    if res["ok"]:
                        self._on_dirty()
                        self.refresh_page(item.page_idx)
                return
            # Con una sola página no se pueden deducir cabecera y pie (hay que ver qué
            # se repite): si la edición crea una página nueva, se pregunta antes.
            if self.hf is None and len(self.doc) < 2 and not self.manual:
                added = be.paragraph_edit_adds_pages(
                    self.doc, item.page_idx, para, new_text, para["size"], para["color"],
                    runs=[dict(r) for r in runs])
                if added and not self.ask_header_footer(
                        item.page_idx, tr("Este texto no cabe en la página y se creará una nueva. "
                        "Marca la cabecera y el pie para no tocarlos y decide cómo se repiten. "
                        "Si cancelas, el cambio se descarta.")):
                    return
            if self._on_before_mutate:
                self._on_before_mutate()
            pages_before = len(self.doc)
            res = be.replace_paragraph_in_doc(
                self.doc, item.page_idx, para, new_text, para["size"], para["color"],
                settings=self.hf, runs=[dict(r) for r in runs], shift=not self.manual)
            if res["ok"]:
                self._on_dirty()
                if not res["font_found"] and res["family"]:
                    self._on_font_missing(res["family"])
                spilled = [p + 1 for p in res["pages"] if p != item.page_idx]
                if spilled and self._on_notice:
                    self._on_notice(tr("El texto que no cabía pasó a la página {pages}.",
                                        pages=", ".join(str(p) for p in spilled)))
                if len(self.doc) != pages_before:
                    self.reload_preserving_scroll()          # se añadió alguna página
                else:
                    for p in res["pages"]:
                        self.refresh_page(p)
