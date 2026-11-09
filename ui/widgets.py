# -*- coding: utf-8 -*-
"""Widgets reutilizables: lista de archivos, zona de soltar, cabecera con «Volver», deslizadores."""

from PySide6.QtCore import Qt, QSize, QRect, QTimer
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont, QFontMetrics, QPen
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QSpinBox,
    QSlider,
    QAbstractItemView,
    QMenu,
    QSizePolicy,
    QStyle,
    QStyleOptionSlider,
)

import backend as be
import icons as ic
from theme import BG, SURFACE_2, SURFACE_3, TEXT, TEXT_SOFT, ACCENT
from i18n import tr
from ui.common import FILE_COLORS, _btn, add_shadow


REMOVE_BTN_RECT = QRect(0, 0, 38, 84)   # zona clicable del aspa «quitar», en coordenadas de la tarjeta (margen generoso)


def render_file_card(name: str, pages: int, color: str, width: int = 620, height: int = 84,
                     path: str | None = None) -> QPixmap:
    """Pre-renderiza la tarjeta de un archivo como pixmap único: así el
    drag&drop interno de Qt mueve la tarjeta entera sin glitches. A la izquierda de la miniatura lleva un
    aspa para quitar el archivo sin menú contextual (su zona clicable es REMOVE_BTN_RECT, escalada a `height`)."""
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(SURFACE_2))
    p.drawRoundedRect(0, 0, width, height, 13, 13)

    p.setBrush(QColor(color))
    p.drawRoundedRect(0, 10, 5, height - 20, 2, 2)

    close_d = 22
    close_rect = QRect(10, (height - close_d) // 2, close_d, close_d)
    p.setBrush(QColor(SURFACE_3))
    p.drawEllipse(close_rect)
    close_icon = ic.icon("close", TEXT_SOFT, 12).pixmap(12, 12)
    p.drawPixmap(close_rect.x() + (close_d - 12) // 2, close_rect.y() + (close_d - 12) // 2, close_icon)

    box = QRect(40, 8, 56, height - 16)
    thumb = None
    png = be.get_page_thumbnail_png(path, 0, width=140) if path else None
    if png:
        t = QPixmap()
        if t.loadFromData(png):
            thumb = t.scaled(box.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if thumb:
        tx = box.x() + (box.width() - thumb.width()) // 2
        ty = box.y() + (box.height() - thumb.height()) // 2
        p.drawPixmap(tx, ty, thumb)
        p.setPen(QPen(QColor(243, 241, 228, 70), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(tx, ty, thumb.width() - 1, thumb.height() - 1)
        p.setPen(Qt.NoPen)
    else:
        doc_icon = ic.icon("document", TEXT, 22).pixmap(22, 22)
        p.drawPixmap(box.x() + (box.width() - 22) // 2, (height - 22) // 2, doc_icon)

    text_x = 112
    text_w = width - text_x - 60
    name_font = QFont("Segoe UI", 11, QFont.DemiBold)
    p.setFont(name_font)
    fm = QFontMetrics(name_font)
    elided = fm.elidedText(name, Qt.ElideRight, text_w)
    p.setPen(QColor(TEXT))
    p.drawText(QRect(text_x, 19, text_w, 24), Qt.AlignVCenter | Qt.AlignLeft, elided)

    pages_font = QFont("Segoe UI", 9)
    p.setFont(pages_font)
    p.setPen(QColor(TEXT_SOFT))
    p.drawText(QRect(text_x, 44, text_w, 20), Qt.AlignVCenter | Qt.AlignLeft,
               tr("{pages} pág.", pages=pages))

    hint_font = QFont("Segoe UI", 8)
    p.setFont(hint_font)
    p.setPen(QColor(TEXT_SOFT))
    p.drawText(QRect(0, 0, width - 16, height), Qt.AlignVCenter | Qt.AlignRight, "⠿⠿")

    p.end()
    return pix


# ══════════════════════════════════════════════════════════════════════════
#  LISTA DE ARCHIVOS (home) — drop nativo del SO + reordenado nativo de Qt
# ══════════════════════════════════════════════════════════════════════════
class FileListWidget(QListWidget):
    """
    Nota de robustez: el drag&drop interno de Qt mueve los QListWidgetItem
    serializando sus datos (QDataStream) para construir el MIME interno.
    Guardar un dict de Python directamente en Qt.UserRole depende de que esa
    serialización trate bien un objeto arbitrario, lo cual no está garantizado.
    Por eso aquí solo se guarda un id() (int, se serializa sin problemas) y se
    resuelve contra un diccionario propio — así el orden sobrevive al drop
    pase lo que pase con la serialización de Qt.
    """
    def __init__(self, on_files_dropped, on_order_changed, on_remove, on_open):
        super().__init__()
        self._on_files_dropped = on_files_dropped
        self._on_order_changed = on_order_changed
        self._on_remove = on_remove
        self._on_open = on_open
        self._id_map: dict[int, dict] = {}

        self.setViewMode(QListWidget.ListMode)
        self.setFlow(QListWidget.TopToBottom)
        self.setWrapping(False)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(6)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setIconSize(QSize(620, 84))
        self.setCursor(Qt.OpenHandCursor)
        self.itemDoubleClicked.connect(lambda item: self._on_open(self._resolve(item)))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            item = self.itemAt(e.pos())
            if item is not None:
                local = e.pos() - self.visualItemRect(item).topLeft()
                if REMOVE_BTN_RECT.contains(local):
                    self._on_remove(self._resolve(item))
                    return
        super().mousePressEvent(e)

    def set_items(self, files: list[dict]):
        vbar = self.verticalScrollBar()
        scroll_val = vbar.value()
        self.clear()
        self._id_map = {id(f): f for f in files}
        for i, f in enumerate(files):
            color = FILE_COLORS[i % len(FILE_COLORS)]
            pix = render_file_card(f["name"], f["pages"], color, path=f["path"])
            item = QListWidgetItem(QIcon(pix), "")
            item.setData(Qt.UserRole, id(f))
            item.setSizeHint(QSize(pix.width(), pix.height() + 6))
            self.addItem(item)
        vbar.setValue(scroll_val)
        QTimer.singleShot(0, lambda: vbar.setValue(scroll_val))

    def _resolve(self, item: QListWidgetItem):
        return self._id_map.get(item.data(Qt.UserRole))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
            e.acceptProposedAction()
            if paths:
                self._on_files_dropped(paths)
        else:
            super().dropEvent(e)
            self._on_order_changed(self._current_order())

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            item = self.currentItem()
            if item:
                self._on_remove(self._resolve(item))
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        item = self.itemAt(e.pos())
        if not item:
            return
        f = self._resolve(item)
        menu = QMenu(self)
        open_act = menu.addAction(tr("Abrir"))
        remove_act = menu.addAction(tr("Quitar archivo"))
        action = menu.exec(e.globalPos())
        if action == remove_act:
            self._on_remove(f)
        elif action == open_act:
            self._on_open(f)

    def _current_order(self):
        order = [self._resolve(self.item(r)) for r in range(self.count())]
        return [f for f in order if f is not None]


class DropArea(QFrame):
    """Zona grande que acepta soltar PDFs incluso cuando la lista está vacía."""
    def __init__(self, on_files_dropped):
        super().__init__()
        self._on_files_dropped = on_files_dropped
        self.setAcceptDrops(True)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        icon = QLabel(alignment=Qt.AlignCenter)
        icon.setPixmap(ic.icon("folder", TEXT_SOFT, 34).pixmap(34, 34))
        txt = QLabel(tr("Arrastra PDFs o fotos aquí (también texto, HTML, Word…)"), alignment=Qt.AlignCenter)
        txt.setObjectName("Hint")
        lay.addStretch(1)
        lay.addWidget(icon)
        lay.addWidget(txt)
        lay.addStretch(1)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
        if paths:
            self._on_files_dropped(paths)


class BackHeader(QWidget):
    def __init__(self, title: str, on_back):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        back_btn = _btn(tr("Volver"), "back", "Flat")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(on_back)
        lbl = QLabel(title)
        lbl.setObjectName("Header")
        self.title_lbl = lbl
        lay.addWidget(back_btn)
        lay.addSpacing(10)
        lay.addWidget(lbl)
        lay.addStretch(1)


# ══════════════════════════════════════════════════════════════════════════
#  AJUSTE B&N — diálogo con preview en vivo
# ══════════════════════════════════════════════════════════════════════════
class JumpSlider(QSlider):
    """Un clic sobre la barra salta directo a ese valor (Qt, por defecto,
    solo avanza un 'paso de página' hacia el clic) y sigue arrastrando."""
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.orientation() == Qt.Horizontal:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            style = self.style()
            groove = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
            handle = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            pos = e.position().toPoint()
            if not handle.contains(pos):
                span = max(1, groove.width() - handle.width())
                x = pos.x() - groove.x() - handle.width() // 2
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), x, span, opt.upsideDown))
        super().mousePressEvent(e)


def make_slider_row(label: str, lo: int, hi: int, val: int, on_change,
                    suffix: str = "") -> tuple[QWidget, QSlider]:
    """Fila 'etiqueta + barra + campo numérico' con ambos sincronizados."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label)
    lbl.setFixedWidth(90)
    lbl.setObjectName("Hint")
    sl = JumpSlider(Qt.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(val)
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    sp.setSuffix(suffix)
    sp.setKeyboardTracking(False)
    sp.setFixedWidth(92)
    sl.valueChanged.connect(sp.setValue)
    sp.valueChanged.connect(sl.setValue)
    sl.valueChanged.connect(on_change)
    lay.addWidget(lbl)
    lay.addWidget(sl, 1)
    lay.addWidget(sp)
    return w, sl


# ══════════════════════════════════════════════════════════════════════════
#  GRID DE PÁGINAS SELECCIONABLES (sin reordenar) — para elegir con el ratón
# ══════════════════════════════════════════════════════════════════════════
class SelectablePageGrid(QListWidget):
    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSpacing(10)
        self.setIconSize(QSize(148, 196))
        self.itemSelectionChanged.connect(self._refresh_icons)

    def _refresh_icons(self):
        for r in range(self.count()):
            item = self.item(r)
            pg = item.data(Qt.UserRole)
            pix = render_page_card(pg["png"], pg["label"], pg["color"],
                                    selected=item.isSelected())
            item.setIcon(QIcon(pix))


def render_page_card(png_bytes: bytes | None, label: str, color: str,
                      width: int = 148, height: int = 196, selected: bool = False) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    p.setBrush(QColor(ACCENT) if selected else QColor(SURFACE_2))
    pen = QPen(QColor(color)); pen.setWidth(3 if selected else 2)
    p.setPen(pen)
    p.drawRoundedRect(1, 1, width - 2, height - 2, 12, 12)

    thumb_area = QRect(10, 10, width - 20, height - 48)
    p.setPen(Qt.NoPen)
    if png_bytes:
        thumb = QPixmap()
        thumb.loadFromData(png_bytes)
        thumb = thumb.scaled(thumb_area.width(), thumb_area.height(),
                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = thumb_area.x() + (thumb_area.width() - thumb.width()) // 2
        y = thumb_area.y() + (thumb_area.height() - thumb.height()) // 2
        p.drawPixmap(x, y, thumb)
    else:
        fallback_icon = ic.icon("document", TEXT_SOFT, 28).pixmap(28, 28)
        p.drawPixmap(thumb_area.center().x() - 14, thumb_area.center().y() - 14, fallback_icon)

    chip = QRect(10, height - 32, width - 20, 22)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(chip, 7, 7)
    p.setPen(QColor("#1C1409"))
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.drawText(chip, Qt.AlignCenter, (f"✓ {label}" if selected else label))

    p.end()
    return pix


# ══════════════════════════════════════════════════════════════════════════
#  PANEL DE VISTA PREVIA (reutilizable: Tamaño/Márgenes y N-Up)
# ══════════════════════════════════════════════════════════════════════════
class PreviewPanel(QFrame):
    """Vista previa en vivo con navegación. render_fn(idx) -> bytes PNG | None.
    Los cambios de controles llaman a schedule(): se agrupan (debounce) para
    no re-renderizar a cada pulsación de flecha de un spinbox."""
    def __init__(self, render_fn, item_word: str = "Página"):
        super().__init__()
        self.setObjectName("Card")
        add_shadow(self, blur=18, dy=4, alpha=70)
        self._render_fn = render_fn
        self._item_word = item_word
        self._idx = 0
        self._total = 1
        self._orig: QPixmap | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(160)
        self._timer.timeout.connect(self._render)

        lay = QVBoxLayout(self)
        self.caption = QLabel(tr("Vista previa"))
        self.caption.setObjectName("SectionTitle")
        lay.addWidget(self.caption)

        self.img = QLabel(alignment=Qt.AlignCenter)
        self.img.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.img.setMinimumSize(240, 300)
        self.img.setStyleSheet(f"background:{BG}; border-radius:10px;")
        lay.addWidget(self.img, 1)

        nav = QHBoxLayout()
        self.prev_btn = _btn("", "chevron_left"); self.prev_btn.setFixedWidth(42)
        self.next_btn = _btn("", "chevron_right"); self.next_btn.setFixedWidth(42)
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))
        self.nav_lbl = QLabel()
        self.nav_lbl.setObjectName("Hint")
        nav.addStretch(1)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.nav_lbl)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        lay.addLayout(nav)
        self._update_nav()

    def set_caption(self, text: str):
        self.caption.setText(text)

    def set_total(self, total: int):
        self._total = max(1, total)
        self._idx = min(self._idx, self._total - 1)
        self._update_nav()

    def schedule(self):
        self._timer.start()

    def _step(self, delta: int):
        new = self._idx + delta
        if 0 <= new < self._total:
            self._idx = new
            self._update_nav()
            self._render()

    def _update_nav(self):
        self.nav_lbl.setText(f"{self._item_word} {self._idx + 1} / {self._total}")
        self.prev_btn.setEnabled(self._idx > 0)
        self.next_btn.setEnabled(self._idx < self._total - 1)

    def _render(self):
        png = self._render_fn(self._idx)
        if not png:
            self._orig = None
            self.img.setPixmap(QPixmap())
            self.img.setText(tr("No se pudo generar la vista previa"))
            return
        pix = QPixmap()
        pix.loadFromData(png)
        self._orig = pix
        self._fit()

    def _fit(self):
        if self._orig is None:
            return
        target = self.img.size() - QSize(16, 16)
        if target.width() > 0 and target.height() > 0:
            self.img.setPixmap(self._orig.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()
