# -*- coding: utf-8 -*-
"""Piezas del editor de páginas: barras, menús y diálogos (insertar, cabecera, notas, campos, enlaces)."""
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRectF, Signal
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QFileDialog,
    QFrame,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QSpinBox,
    QDialog,
    QMessageBox,
    QMenu,
    QTextEdit,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QColorDialog,
    QGridLayout,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

import backend as be
import icons as ic
import annot_tools as at
import pdf_tools as ptl
import layout_tools as lt
import click_icons as ci
from theme import SURFACE, SURFACE_2, SURFACE_3, TEXT, ACCENT, BORDER_STRONG, DANGER
from ui.common import ICON_DARK, _btn
from i18n import tr


# ══════════════════════════════════════════════════════════════════════════
#  EDITOR VISUAL — clic sobre el texto para editarlo
# ══════════════════════════════════════════════════════════════════════════
class SpanRectItem(QGraphicsRectItem):
    """Zona clicable invisible sobre un fragmento de texto de la página."""
    def __init__(self, rect: QRectF, span: dict, page_idx: int, on_click, mode_provider=None):
        super().__init__(rect)
        self.span = span
        self.page_idx = page_idx
        self._on_click = on_click
        self._mode_provider = mode_provider
        self.kind = "edit"
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(Qt.NoPen))
        self._normal = QBrush(QColor(0, 0, 0, 0))
        self._hover_edit = QBrush(QColor(192, 130, 88, 70))
        self._hover_censor = QBrush(QColor(212, 114, 104, 120))
        self.setBrush(self._normal)

    def _mode(self) -> str:
        return self._mode_provider() if self._mode_provider else "edit"

    def hoverEnterEvent(self, e):
        censor = self._mode() == "censor"
        self.setBrush(self._hover_censor if censor else self._hover_edit)
        self.setCursor(Qt.CrossCursor if censor else Qt.IBeamCursor)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.setBrush(self._normal)
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if self._mode() == "censor":
            e.ignore()   # deja que la vista gestione el clic/arrastre de censura
            return
        self._on_click(self)
        super().mousePressEvent(e)


def _toggle_icon(name: str, size: int = 18) -> QIcon:
    """Icono claro normal y oscuro cuando el botón está marcado (fondo de acento)."""
    icon = QIcon()
    icon.addPixmap(ic.icon(name, TEXT, size).pixmap(size, size), QIcon.Normal, QIcon.Off)
    icon.addPixmap(ic.icon(name, ICON_DARK, size).pixmap(size, size), QIcon.Normal, QIcon.On)
    return icon


class _ToolBar(QFrame):
    """Barra de formato flotante. Absorbe los clics: si no, los de las zonas que
    no son botón llegarían a la página de fondo y cerrarían el editor."""
    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        e.accept()

    def mouseDoubleClickEvent(self, e):
        e.accept()


class _Swatch(QPushButton):
    """Círculo de color dibujado con suavizado (los bordes redondeados de la
    hoja de estilo salen pixelados a este tamaño)."""
    def __init__(self, hexc: str, selected: bool):
        super().__init__()
        self.hexc, self.selected = hexc, selected
        self.setFixedSize(30, 30)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        disc = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.hexc))
        p.drawEllipse(disc)
        if self.selected or self.underMouse():
            pen = QPen(QColor(ACCENT if self.selected else TEXT))
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(disc.adjusted(-3, -3, 3, 3))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(disc)


class _ToolPopup(QFrame):
    """Panel flotante que se cierra al hacer clic fuera: sirve de menú
    desplegable de la barra de formato (tamaño, fuente, color)."""
    def __init__(self, parent):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        # Fondo sólido: la transparencia de las ventanas emergentes se pinta a medias en Windows.
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(SURFACE_2))
        self.setPalette(pal)
        self.setObjectName("ToolPopup")
        self.setStyleSheet(
            f"#ToolPopup {{ background:{SURFACE_2}; border:1px solid {BORDER_STRONG}; border-radius:4px; }}")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(8, 8, 8, 8)
        self.lay.setSpacing(6)


def _popup_list(width: int, height: int) -> QListWidget:
    lst = QListWidget()
    lst.setFixedSize(width, height)
    lst.setFocusPolicy(Qt.NoFocus)
    lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    lst.setStyleSheet(
        f"QListWidget {{ background:transparent; border:none; color:{TEXT}; outline:0; }}"
        f"QScrollBar:vertical {{ background:transparent; width:8px; margin:2px 0; border:none; }}"
        f"QScrollBar::handle:vertical {{ background:rgba(243,241,228,0.28); border-radius:4px; min-height:24px; }}"
        f"QScrollBar::handle:vertical:hover {{ background:rgba(243,241,228,0.45); }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}"
        f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}"
        f"QListWidget::item {{ padding:5px 8px; border-radius:6px; color:{TEXT}; }}"
        f"QListWidget::item:hover {{ background:rgba(243,241,228,0.10); }}"
        f"QListWidget::item:selected {{ background:{ACCENT}; color:{ICON_DARK}; }}")
    return lst


class _VirtualItem:
    """Lo que el editor necesita de un elemento que aún no existe en el PDF (texto libre nuevo)."""
    kind = "new"

    def __init__(self, page_idx: int, rect: QRectF, span: dict):
        self.page_idx, self._rect, self.span = page_idx, rect, span

    def rect(self) -> QRectF:
        return self._rect


_PROP_FONT = 0x100001      # propiedad de formato: fuente original del PDF
_PROP_FAMILY = 0x100002    # propiedad de formato: el usuario eligió otra fuente
_PROP_SIZE = 0x100003      # propiedad de formato: tamaño exacto en pt (el píxel del editor lo redondea)


class _HFBlock(QGraphicsRectItem):
    """Texto de la página que se puede marcar con un clic como cabecera o pie."""
    COLORS = {"header": QColor(80, 140, 210, 120), "footer": QColor(90, 170, 110, 120)}

    def __init__(self, rect: QRectF, bbox: tuple, on_click):
        super().__init__(rect)
        self.bbox, self._on_click, self.role = bbox, on_click, None
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self._paint()

    def set_role(self, role):
        self.role = role
        self._paint()

    def _paint(self, hover=False):
        self.setPen(QPen(QColor(192, 130, 88, 200 if hover else 90), 1))
        self.setBrush(QBrush(self.COLORS.get(self.role, QColor(192, 130, 88, 60 if hover else 0))))

    def hoverEnterEvent(self, e):
        self._paint(True)

    def hoverLeaveEvent(self, e):
        self._paint(False)

    def mousePressEvent(self, e):
        self._on_click(self)


class InsertPageDialog(QDialog):
    """¿Qué se inserta aquí? Una página en blanco (con o sin la cabecera y el pie detectados, con vista previa) o
    las páginas de otro PDF."""

    def __init__(self, view, doc, at: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Insertar página"))
        self.view, self.doc, self.at = view, doc, at
        self.choice = None                    # "blank" | "pdf"
        self.settings = None                  # ajustes de cabecera/pie para la hoja en blanco (None = detección automática)
        self.pdf_path = None
        self._cache = {}
        self.has_hf = be.has_header_footer(doc, at, view.hf)
        self.resize(640, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(self._title(tr("¿Qué quieres insertar aquí?")))
        row = QHBoxLayout()
        self.blank_rb = QRadioButton(tr("Una página en blanco"))
        self.pdf_rb = QRadioButton(tr("Páginas de otro documento (PDF)…"))
        self.blank_rb.setChecked(True)
        row.addWidget(self.blank_rb)
        row.addWidget(self.pdf_rb)
        row.addStretch(1)
        lay.addLayout(row)

        self.hf_box = QWidget()
        hl = QHBoxLayout(self.hf_box)
        hl.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        info = QLabel(tr("Se ha detectado cabecera, pie o fondo de página en este documento.") if view.hf is None
                      else tr("Este documento tiene la cabecera y el pie que configuraste."))
        info.setWordWrap(True)
        left.addWidget(info)
        self.keep_rb = QRadioButton(tr("Mantener cabecera, pie y fondo"))
        self.empty_rb = QRadioButton(tr("Hoja totalmente en blanco"))
        self.conf_rb = QRadioButton(tr("Configurar cabecera y pie…"))
        self.keep_rb.setChecked(True)
        for rb in (self.keep_rb, self.empty_rb, self.conf_rb):
            left.addWidget(rb)
            rb.toggled.connect(self._on_option)
        left.addStretch(1)
        hl.addLayout(left, 1)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(250, 330)
        self.preview.setStyleSheet("background:#FFFFFF; border:1px solid %s;" % BORDER_STRONG)
        hl.addWidget(self.preview)
        lay.addWidget(self.hf_box, 1)
        self.hf_box.setVisible(self.has_hf)

        self.pdf_lbl = QLabel("")
        self.pdf_lbl.setObjectName("Hint")
        lay.addWidget(self.pdf_lbl)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = _btn(tr("Cancelar"), None, "Secondary")
        self.ok_btn = _btn(tr("Insertar"), "plus", "Primary")
        cancel.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(self.ok_btn)
        lay.addLayout(btns)
        self.blank_rb.toggled.connect(self._on_kind)
        self._on_kind()
        self._refresh_preview()

    @staticmethod
    def _title(text):
        l = QLabel(text)
        l.setObjectName("SectionTitle")
        return l

    def _on_kind(self):
        blank = self.blank_rb.isChecked()
        self.hf_box.setVisible(blank and self.has_hf)
        self.pdf_lbl.setText("" if blank else tr("Al pulsar «Insertar» elegirás el PDF cuyas páginas se añaden aquí."))

    def _current_settings(self):
        if self.empty_rb.isChecked():
            return be.BLANK_HF
        return self.view.hf                      # None = detección automática

    def _on_option(self, checked):
        if not checked:
            return
        if self.conf_rb.isChecked():
            if self.view.ask_header_footer(max(0, min(self.at - 1, len(self.doc) - 1))):
                self._cache.clear()
            self.keep_rb.setChecked(True)
            return
        self._refresh_preview()

    def _refresh_preview(self):
        key = "empty" if self.empty_rb.isChecked() else "keep"
        if key not in self._cache:
            self._cache[key] = be.preview_inserted_page(self.doc, self.at, self._current_settings(), 250)
        png = self._cache[key]
        pm = QPixmap()
        if png:
            pm.loadFromData(png)
            self.preview.setPixmap(pm)
        else:
            self.preview.setText(tr("Sin vista previa"))

    def _accept(self):
        if self.pdf_rb.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, tr("Elige el PDF a insertar"), str(Path.home()),
                                                  tr("PDF (*.pdf);;Todos los archivos (*.*)"))
            if not path:
                return
            self.choice, self.pdf_path = "pdf", path
        else:
            self.choice = "blank"
            self.settings = self._current_settings() if self.has_hf else self.view.hf
        self.accept()


class ClickIconDialog(QDialog):
    """Elegir un icono de «haz clic aquí» para poner sobre el enlace de una imagen."""

    def __init__(self, parent=None, live=None):
        super().__init__(parent)
        self.live = live
        self.setWindowTitle(tr("Cambiar icono") if live else tr("Icono de «clic aquí»"))
        self.kind = None
        lay = QVBoxLayout(self)
        lbl = QLabel(tr("Pulsa un icono para cambiarlo al momento; puedes probar varios.") if live else
                     tr("El enlace está sobre una imagen. ¿Quieres insertar alguno de estos iconos para indicar a quien "
                     "lea el PDF que puede hacer clic? Después podrás moverlo y girarlo un poco para que no tape nada."))
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        grid = QGridLayout()
        entries = ci.builtin_kinds() + [(k, tr("Tu imagen")) for k in ci.list_custom()]
        for i, (key, label) in enumerate(entries):
            pm = QPixmap(84, 84)
            pm.fill(QColor("#FFFFFF"))
            pa = QPainter(pm)
            pa.setRenderHint(QPainter.SmoothPixmapTransform)
            pa.drawImage(QRectF(0, 0, 84, 84), ci.render_image(key, 0, 168))
            pa.end()
            b = QPushButton()
            b.setIcon(QIcon(pm))
            b.setIconSize(QSize(84, 84))
            b.setFixedSize(100, 100)
            b.setToolTip(label)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            grid.addWidget(b, i // 4, i % 4)
        lay.addLayout(grid)
        row = QHBoxLayout()
        own = _btn(tr("Usar mi propia imagen…"), "image", "Secondary")
        own.setToolTip(tr("Importa un PNG, JPG o SVG para usarlo como icono (queda guardado para otros documentos)"))
        own.clicked.connect(self._own)
        row.addWidget(own)
        row.addStretch(1)
        no = _btn(tr("Cerrar") if live else tr("No, gracias"), None, "Secondary")
        no.clicked.connect(self.reject)
        row.addWidget(no)
        lay.addLayout(row)

    def _own(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("Elige las imágenes de tus iconos"), str(Path.home() / "Pictures"),
            tr("Imágenes e ilustraciones (*.png *.jpg *.jpeg *.svg *.ai *.eps *.pdf *.webp *.gif *.bmp);;Todos (*.*)"))
        keys, errors = [], []
        for pth in paths:
            key, err = ci.import_custom(pth)
            if key:
                keys.append(key)
            else:
                errors.append(f"{Path(pth).name}: {err}")
        if errors:
            QMessageBox.warning(self, tr("Icono"), "\n".join(errors))
        if keys:
            self._pick(keys[0])                 # el primero se usa ya; los demás quedan guardados en la lista

    def _pick(self, key):
        self.kind = key
        if self.live is not None:
            self.live(key)                 # modo «jugar»: se aplica al momento y la ventana sigue abierta
            return
        self.accept()


class HeaderFooterDialog(QDialog):
    """Pregunta qué es cabecera y pie de página (clic sobre el texto) y cómo
    repetirlos en las páginas nuevas: igual en todas o distinto en pares e
    impares, y si se sigue la numeración."""
    def __init__(self, doc, page_idx: int, settings, parent=None, intro: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("Cabecera y pie de página"))
        self.doc, self.page_idx, self.settings = doc, page_idx, settings
        auto_h, auto_f = be.auto_header_footer(doc, page_idx)
        s = {**be.DEFAULT_HF, **(settings or {})}
        self.resize(900, 660)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)

        # ── Vista previa con los textos clicables ────────────────────────
        page = doc[page_idx]
        zoom = min(1.3, 560 / page.rect.height)
        png = be.render_doc_page_png(doc, page_idx, zoom=zoom)
        pm = QPixmap()
        if png:
            pm.loadFromData(png)
        scene = QGraphicsScene(self)
        scene.addPixmap(pm)
        self.items: list[_HFBlock] = []
        for b in page.get_text("blocks"):
            if b[6] != 0 or not b[4].strip():
                continue
            it = _HFBlock(QRectF(b[0] * zoom, b[1] * zoom, (b[2] - b[0]) * zoom, (b[3] - b[1]) * zoom),
                          tuple(b[:4]), self._clicked)
            if settings is not None:
                it.role = ("header" if any(abs(b[1] - h[1]) < 1.5 and abs(b[0] - h[0]) < 1.5 for h in s["header_boxes"])
                           else "footer" if any(abs(b[1] - f[1]) < 1.5 and abs(b[0] - f[0]) < 1.5 for f in s["footer_boxes"])
                           else None)
            else:
                it.role = ("header" if auto_h and b[3] <= auto_h + 2
                           else "footer" if auto_f and b[1] >= auto_f - 2 else None)
            it.set_role(it.role)
            scene.addItem(it)
            self.items.append(it)
        scene.setSceneRect(0, 0, pm.width(), pm.height())
        view = QGraphicsView(scene)
        view.setStyleSheet(f"background:{SURFACE}; border:none; border-radius:10px;")
        view.setFixedSize(pm.width() + 4, min(pm.height() + 4, 600))
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(view)

        # ── Opciones ─────────────────────────────────────────────────────
        side = QVBoxLayout()
        side.setSpacing(10)
        title = QLabel(tr("Cabecera y pie de página"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        side.addWidget(title)
        text = intro or (tr("Marca con un clic los textos que son cabecera o pie: no se moverán al "
                         "repartir el texto entre páginas y se podrán repetir en las páginas nuevas."))
        info = QLabel(text)
        info.setObjectName("Hint")
        info.setWordWrap(True)
        side.addWidget(info)

        side.addWidget(QLabel(tr("Cada clic marca el texto como:")))
        self.role_header = QRadioButton(tr("Cabecera (azul)"))
        self.role_footer = QRadioButton(tr("Pie de página (verde)"))
        self.role_header.setChecked(True)
        side.addWidget(self.role_header)
        side.addWidget(self.role_footer)
        self.rep_header = QCheckBox(tr("Repetir la cabecera en las páginas nuevas"))
        self.rep_header.setChecked(s["repeat_header"])
        self.rep_footer = QCheckBox(tr("Repetir el pie en las páginas nuevas"))
        self.rep_footer.setChecked(s["repeat_footer"])
        side.addSpacing(6)
        side.addWidget(self.rep_header)
        side.addWidget(self.rep_footer)

        side.addSpacing(6)
        side.addWidget(QLabel(tr("¿Son iguales en todas las páginas?")))
        self.same_all = QRadioButton(tr("Iguales en todas"))
        self.parity = QRadioButton(tr("Distintos en pares e impares"))
        (self.parity if s["parity"] else self.same_all).setChecked(True)
        par_hint = QLabel(tr("La página nueva copia la de dos antes, o la anterior si no hay."))
        par_hint.setObjectName("Hint")
        par_hint.setWordWrap(True)
        side.addWidget(self.same_all)
        side.addWidget(self.parity)
        side.addWidget(par_hint)

        side.addSpacing(6)
        self.numbering = QCheckBox(tr("Seguir la numeración de página"))
        self.numbering.setChecked(s["numbering"])
        self.num_info = QLabel()
        self.num_info.setObjectName("Hint")
        self.num_info.setWordWrap(True)
        side.addWidget(self.numbering)
        side.addWidget(self.num_info)
        side.addStretch(1)

        btns = QHBoxLayout()
        cancel = _btn(tr("Cancelar"), None, "Secondary", icon_color=TEXT)
        ok = _btn(tr("Continuar"), "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        side.addLayout(btns)
        wrap = QWidget()
        wrap.setLayout(side)
        wrap.setFixedWidth(320)
        root.addWidget(wrap)
        self._refresh_numbers()

    def _clicked(self, item: "_HFBlock"):
        role = "header" if self.role_header.isChecked() else "footer"
        item.set_role(None if item.role == role else role)
        self._refresh_numbers()

    def _bounds(self):
        hb = max((i.bbox[3] for i in self.items if i.role == "header"), default=None)
        fb = min((i.bbox[1] for i in self.items if i.role == "footer"), default=None)
        return hb, fb

    def _refresh_numbers(self):
        hb, fb = self._bounds()
        found = be.find_page_numbers(self.doc, self.page_idx, hb, fb)
        self.num_info.setText(
            tr("Número de página detectado: {nums}. En la página nueva subirá solo.",
               nums=", ".join(f"«{t}»" for t in found))
            if found else tr("No se ha detectado ningún número de página en lo marcado."))

    def _accept(self):
        self.settings = {
            "header_boxes": [i.bbox for i in self.items if i.role == "header"],
            "footer_boxes": [i.bbox for i in self.items if i.role == "footer"],
            "repeat_header": self.rep_header.isChecked(),
            "repeat_footer": self.rep_footer.isChecked(),
            "parity": self.parity.isChecked(),
            "numbering": self.numbering.isChecked(),
            "ref_h": self.doc[self.page_idx].rect.height,
        }
        self.accept()


def fitz_rect(x0, y0, x1, y1):
    return (x0, y0, x1, y1)


class CopyDialog(QDialog):
    """Texto de la zona elegida, con párrafos, columnas y tablas respetados. Se puede editar antes de copiar."""
    def __init__(self, parent, blocks: list, note: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("Copiar texto"))
        self.resize(640, 520)
        self.blocks = blocks
        self.xlsx_path = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        title = QLabel(tr("Texto de la zona"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.summary = QLabel("")
        self.summary.setObjectName("Hint")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        if note:
            n = QLabel(note)
            n.setObjectName("Hint")
            n.setWordWrap(True)
            lay.addWidget(n)
        self.reflow = QCheckBox(tr("Unir las líneas de cada párrafo (quita los saltos de línea del escaneo o de la maquetación)"))
        self.reflow.setChecked(True)
        self.reflow.toggled.connect(self._fill)
        lay.addWidget(self.reflow)
        self.edit = QTextEdit()
        self.edit.setAcceptRichText(False)
        self.edit.setLineWrapMode(QTextEdit.WidgetWidth)
        lay.addWidget(self.edit, 1)
        self.hint = QLabel("")
        self.hint.setObjectName("Hint")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        btns = QHBoxLayout()
        self.xlsx_btn = _btn(tr("Tablas a Excel…"), "download", "Secondary", icon_color=TEXT)
        self.xlsx_btn.clicked.connect(self._export)
        btns.addWidget(self.xlsx_btn)
        btns.addStretch(1)
        close = _btn(tr("Cerrar"), None, "Secondary", icon_color=TEXT)
        self.copy_btn = _btn(tr("Copiar"), "copy", "Primary", icon_color=ICON_DARK)
        close.clicked.connect(self.accept)
        self.copy_btn.clicked.connect(self._copy)
        btns.addWidget(close)
        btns.addWidget(self.copy_btn)
        lay.addLayout(btns)
        self._fill()

    def _fill(self, *_):
        text = lt.blocks_to_text(self.blocks, self.reflow.isChecked())
        self.edit.setPlainText(text)
        n_t = sum(1 for b in self.blocks if b.kind == "table")
        n_p = sum(len(b.paragraphs) for b in self.blocks if b.kind == "text")
        n_r = sum(1 for b in self.blocks if b.kind == "row")
        parts = []
        if n_p:
            parts.append(f"{n_p} " + tr("párrafo") + ('s' if n_p != 1 else ''))
        if n_t:
            parts.append(f"{n_t} " + tr("tabla") + ('s' if n_t != 1 else ''))
        if n_r:
            parts.append(f"{n_r} " + tr("fila") + ('s' if n_r != 1 else '') + " " + tr("suelta") + ('s' if n_r != 1 else ''))
        self.summary.setText(tr("Se ha reconocido: ") + (", ".join(parts) or tr("nada de texto")) + ".")
        self.xlsx_btn.setVisible(n_t > 0)
        self.hint.setText(tr("Las celdas de tablas y filas van separadas por tabuladores: al pegarlo en Excel o en una tabla "
                          "de Word cada una cae en su columna.") if (n_t or n_r) else "")
        self.copy_btn.setEnabled(bool(text.strip()))

    def _copy(self):
        QApplication.clipboard().setText(self.edit.toPlainText())
        self.hint.setText(tr("✓ Copiado al portapapeles."))

    def _export(self):
        tables = [b.rows for b in self.blocks if b.kind == "table"]
        dest, _ = QFileDialog.getSaveFileName(self, tr("Guardar tablas"), str(Path.home() / "Downloads" / "tablas.xlsx"),
                                              tr("Excel (*.xlsx)"))
        if not dest:
            return
        try:
            ptl.tables_to_xlsx(tables, dest)
            self.xlsx_path = dest
            self.hint.setText(tr("✓ Guardado: {name} ({n} hoja{s}).", name=Path(dest).name, n=len(tables),
                                 s='s' if len(tables) != 1 else ''))
        except Exception as e:
            self.hint.setText(tr("No se pudo guardar: {e}", e=e))


class NoteDialog(QDialog):
    def __init__(self, parent, text: str = "", author: str = "", existing: bool = False):
        super().__init__(parent)
        self.setWindowTitle(tr("Editar nota") if existing else tr("Nueva nota"))
        self.setMinimumWidth(420)
        self.remove = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel(tr("Editar nota") if existing else tr("Nueva nota"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        if author:
            a = QLabel(tr("Autor: {author}", author=author))
            a.setObjectName("Hint")
            lay.addWidget(a)
        self.edit = QTextEdit()
        self.edit.setAcceptRichText(False)
        self.edit.setPlainText(text)
        self.edit.setMinimumHeight(120)
        lay.addWidget(self.edit)
        btns = QHBoxLayout()
        if existing:
            rm = _btn(tr("Eliminar nota"), "trash", "Flat", icon_color=DANGER)
            rm.clicked.connect(self._remove)
            btns.addWidget(rm)
        btns.addStretch(1)
        cancel = _btn(tr("Cancelar"), None, "Secondary", icon_color=TEXT)
        ok = _btn(tr("Guardar"), "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.edit.setFocus()

    def _remove(self):
        self.remove = True
        self.accept()


class _FieldEditor(QTextEdit):
    """Caja para escribir en un campo de formulario, justo encima del campo. Intro (o Ctrl+Intro si el campo es
    de varias líneas) o salir de la caja confirma; Esc cancela."""
    committed = Signal(str)
    cancelled = Signal()
    tabbed = Signal(bool)                 # Tab (True) o Mayús+Tab (False): confirmar y pasar al campo siguiente o anterior

    def __init__(self, parent, text: str, multiline: bool, font_px: float):
        super().__init__(parent)
        self._multi, self._done = multiline, False
        self.setAcceptRichText(False)
        self.setPlainText(text)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff if not multiline else Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth if multiline else QTextEdit.NoWrap)
        f = self.font()
        f.setPixelSize(max(9, int(font_px)))
        self.setFont(f)
        self.document().setDocumentMargin(0)
        # sin caja ni fondo: se escribe directamente sobre el campo y solo se ve el cursor parpadeante
        self.setStyleSheet("QTextEdit { background:transparent; color:#000000; border:none; padding:0; }")
        self.setCursorWidth(max(2, round(font_px * 0.07)))
        pal = self.palette()
        pal.setColor(pal.ColorRole.Text, QColor("#000000"))
        self.setPalette(pal)

    def _finish(self, ok: bool):
        if self._done:
            return
        self._done = True
        (self.committed.emit(self.toPlainText()) if ok else self.cancelled.emit())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._finish(False)
            return
        if e.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            fwd = e.key() == Qt.Key_Tab and not (e.modifiers() & Qt.ShiftModifier)
            self._finish(True)
            self.tabbed.emit(fwd)
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and (not self._multi or e.modifiers() & Qt.ControlModifier):
            self._finish(True)
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        # Cambiar de ventana o abrir un menú no debe cerrar la caja; hacer clic en otro sitio, sí.
        if e.reason() in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason):
            return
        self._finish(True)


class FieldDialog(QDialog):
    """Datos de un campo de formulario nuevo."""
    TYPES = (("text", tr("Texto (una línea)")), ("multiline", tr("Texto (varias líneas)")), ("checkbox", tr("Casilla")),
             ("combo", tr("Lista desplegable")), ("list", tr("Lista de selección")),
             ("radio", tr("Botones de opción (elegir uno)")))

    def __init__(self, parent, default_name: str):
        super().__init__(parent)
        self.setWindowTitle(tr("Nuevo campo"))
        self.setMinimumWidth(420)
        self.spec = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel(tr("Nuevo campo de formulario"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.kind = QComboBox()
        for key, label in self.TYPES:
            self.kind.addItem(label, key)
        lay.addWidget(QLabel(tr("Tipo de campo")))
        lay.addWidget(self.kind)
        lay.addWidget(QLabel(tr("Nombre del campo (así se identifica al exportar los datos)")))
        self.name = QLineEdit(default_name)
        lay.addWidget(self.name)
        self.opts_lbl = QLabel(tr("Opciones (una por línea)"))
        self.opts = QTextEdit()
        self.opts.setAcceptRichText(False)
        self.opts.setFixedHeight(90)
        self.opts.setPlainText(tr("Opción 1\nOpción 2\nOpción 3"))
        lay.addWidget(self.opts_lbl)
        lay.addWidget(self.opts)
        self.val_lbl = QLabel(tr("Valor inicial (opcional)"))
        self.value = QLineEdit()
        lay.addWidget(self.val_lbl)
        lay.addWidget(self.value)
        self.kind.currentIndexChanged.connect(self._sync)
        self._sync()
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = _btn(tr("Cancelar"), None, "Secondary", icon_color=TEXT)
        ok = _btn(tr("Crear campo"), "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

    def _sync(self):
        k = self.kind.currentData()
        lists = k in ("combo", "list", "radio")
        self.opts_lbl.setVisible(lists)
        self.opts.setVisible(lists)
        self.opts_lbl.setText(tr("Opciones (una por línea, mínimo 2)") if k == "radio" else tr("Opciones (una por línea)"))
        self.val_lbl.setVisible(k not in ("checkbox", "radio"))

    def _ok(self):
        k = self.kind.currentData()
        self.spec = {"kind": k, "name": self.name.text().strip() or "campo", "value": self.value.text(),
                     "choices": [l.strip() for l in self.opts.toPlainText().splitlines() if l.strip()]}
        self.accept()


# Colores para el texto de un enlace; el primero es el azul de hipervínculo habitual
LINK_COLORS = ((tr("Azul de hipervínculo"), (5 / 255, 99 / 255, 193 / 255)), (tr("Azul oscuro"), (0.1, 0.2, 0.6)),
               (tr("Morado (visitado)"), (0.4, 0.2, 0.6)), (tr("Rojo"), (0.8, 0.1, 0.1)), (tr("Verde"), (0.1, 0.5, 0.2)),
               (tr("Naranja"), (0.9, 0.45, 0.05)), (tr("Negro"), (0.1, 0.1, 0.1)))


class LinkDialog(QDialog):
    """Elegir adónde lleva un enlace: una web, una página del documento o un correo."""
    def __init__(self, parent, n_pages: int, existing: dict | None = None, n_zones: int = 1,
                 allow_underline: bool = True):
        super().__init__(parent)
        self.setWindowTitle(tr("Editar enlace") if existing else tr("Nuevo enlace"))
        self.setMinimumWidth(460)
        self.result_dest = None
        self.remove = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel(tr("Editar enlace") if existing else tr("Nuevo enlace"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        self.r_web = QRadioButton(tr("Dirección web (o correo electrónico)"))
        self.url = QLineEdit()
        self.url.setPlaceholderText(tr("https://ejemplo.com  ·  nombre@correo.com"))
        self.r_page = QRadioButton(tr("Una página de este documento"))
        self.page = QSpinBox()
        self.page.setRange(1, max(n_pages, 1))
        self.page.setPrefix(tr("Página "))
        self.page.setSuffix(tr(" de {n}", n=n_pages))
        lay.addWidget(self.r_web)
        lay.addWidget(self.url)
        lay.addWidget(self.r_page)
        lay.addWidget(self.page)
        self.link_color = LINK_COLORS[0][1]
        style_row = QHBoxLayout()
        self.underline_cb = QCheckBox(tr("Poner el texto en azul y subrayarlo, como un hipervínculo"))
        self.underline_cb.setChecked(existing is None and allow_underline)
        self.color_btn = QPushButton()
        self.color_btn.setObjectName("Secondary")
        self.color_btn.setToolTip(tr("Color del texto y del subrayado"))
        self.color_btn.clicked.connect(self._color_menu)
        self._paint_color_btn()
        style_row.addWidget(self.underline_cb, 1)
        style_row.addWidget(self.color_btn)
        style_row.setContentsMargins(0, 0, 0, 0)
        self.style_box = QWidget()
        self.style_box.setLayout(style_row)
        self.style_box.setVisible(existing is None and allow_underline)
        lay.addWidget(self.style_box)
        self.note = QLabel(tr("Este enlace ocupa {n} zonas (líneas): se editan y se quitan juntas.", n=n_zones)
                           if n_zones > 1 else "")
        self.note.setObjectName("Hint")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        if existing and existing.get("kind") == 1:             # LINK_GOTO
            self.r_page.setChecked(True)
            self.page.setValue(existing.get("page", 0) + 1)
        else:
            self.r_web.setChecked(True)
            self.url.setText((existing or {}).get("uri", "") or "")
        self.url.textChanged.connect(lambda: self.r_web.setChecked(True))
        self.page.valueChanged.connect(lambda: self.r_page.setChecked(True))
        btns = QHBoxLayout()
        if existing:
            rm = _btn(tr("Quitar enlace"), "trash", "Flat", icon_color=DANGER)
            rm.clicked.connect(self._remove)
            btns.addWidget(rm)
        btns.addStretch(1)
        cancel = _btn(tr("Cancelar"), None, "Secondary", icon_color=TEXT)
        ok = _btn(tr("Guardar enlace"), "check", "Primary", icon_color=ICON_DARK)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.url.setFocus()

    def _paint_color_btn(self):
        pm = QPixmap(16, 16)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.5))
        pa.setBrush(QColor(*(int(c * 255) for c in self.link_color)))
        pa.drawEllipse(1, 1, 14, 14)
        pa.end()
        self.color_btn.setIcon(QIcon(pm))
        self.color_btn.setText("  " + tr("Color"))

    def _color_menu(self):
        m = QMenu(self)
        for name, rgb in LINK_COLORS:
            m.addAction(SelectionBar._swatch(rgb), name, lambda c=rgb: self._set_color(c))
        m.addSeparator()

        def other():
            c = QColorDialog.getColor(QColor(*(int(v * 255) for v in self.link_color)), self, tr("Color del enlace"))
            if c.isValid():
                self._set_color((c.redF(), c.greenF(), c.blueF()))
        m.addAction(tr("Otro color…"), other)
        m.exec(self.color_btn.mapToGlobal(self.color_btn.rect().bottomLeft()))

    def _set_color(self, rgb):
        self.link_color = tuple(rgb)
        self._paint_color_btn()

    def _remove(self):
        self.remove = True
        self.accept()

    def _ok(self):
        if self.r_page.isChecked():
            self.result_dest = {"kind": "goto", "page": self.page.value() - 1}
            self.accept()
            return
        uri = at.normalize_uri(self.url.text())
        if not uri:
            self.note.setText(tr("Esa dirección no es válida. Usa una web (https://…), un correo o un teléfono; "
                              "por seguridad no se admiten otros tipos de enlace."))
            return
        self.result_dest = {"kind": "uri", "uri": uri}
        self.accept()


def color_menu(parent, view, fill: bool, apply):
    """Menú de colores: paleta, «Otro color…» y cuentagotas. `apply` recibe un nombre, una tupla (r,g,b) o "" (sin relleno)."""
    m = QMenu(parent)
    sw = SelectionBar._swatch
    if fill:
        m.addAction(sw(None), tr("Sin relleno"), lambda: apply(""))
    for name, rgb in at.SHAPE_COLORS.items():
        m.addAction(sw(rgb), name.capitalize(), lambda n=name: apply(n))
    m.addSeparator()

    def other():
        c = QColorDialog.getColor(QColor(200, 60, 60), parent, tr("Elige un color"))
        if c.isValid():
            apply((c.redF(), c.greenF(), c.blueF()))
    m.addAction(tr("Otro color…"), other)
    m.addAction(tr("Cuentagotas (tomar de la página)"), lambda: view.start_eyedropper(apply))
    return m


OPACITIES = ((1.0, "100 %"), (0.75, "75 %"), (0.5, "50 %"), (0.25, "25 %"))


def opacity_menu(parent, apply, has_fill: bool = True, current=None):
    """Opacidad: total (trazo y relleno a la vez) y, opcionalmente, solo del trazo o solo del relleno.
    `apply(parte, valor)` con parte = "total" | "stroke" | "fill"."""
    m = QMenu(parent)
    tot = m.addMenu(tr("Opacidad total"))
    for v, label in OPACITIES:
        a = tot.addAction(label, lambda x=v: apply("total", x))
        a.setCheckable(True)
        a.setChecked(bool(current) and abs(current[0] - v) < 0.01 and abs(current[1] - v) < 0.01)
    st = m.addMenu(tr("Solo el trazo (opcional)"))
    for v, label in OPACITIES:
        st.addAction(label, lambda x=v: apply("stroke", x))
    if has_fill:
        fl = m.addMenu(tr("Solo el relleno (opcional)"))
        for v, label in OPACITIES:
            fl.addAction(label, lambda x=v: apply("fill", x))
    return m


class SelectionBar(QFrame):
    """Opciones sobre la forma seleccionada: color del borde, relleno, grosor, duplicar y borrar."""

    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self.setObjectName("SelBar")
        self.setStyleSheet(
            "QFrame#SelBar { background:%s; border:1px solid %s; border-radius:8px; }"
            "QPushButton { background:transparent; border:none; padding:4px 6px; border-radius:6px; color:%s; font-size:12px; }"
            "QPushButton:hover { background:%s; }" % (SURFACE, BORDER_STRONG, TEXT, SURFACE_3))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        self.stroke_btn = QPushButton(); self.stroke_btn.setToolTip(tr("Color del borde"))
        self.fill_btn = QPushButton(); self.fill_btn.setToolTip(tr("Color de relleno"))
        self.width_btn = QPushButton(); self.width_btn.setToolTip(tr("Grosor"))
        self.op_btn = QPushButton(); self.op_btn.setToolTip(tr("Opacidad del relleno"))
        self.head_btn = QPushButton(); self.head_btn.setToolTip(tr("Forma de la punta de la flecha"))
        self.dup_btn = _btn("", "copy", None, icon_color=TEXT, size=16); self.dup_btn.setToolTip(tr("Duplicar (Ctrl+D)"))
        self.del_btn = _btn("", "trash", None, icon_color=TEXT, size=16); self.del_btn.setToolTip(tr("Borrar (Supr)"))
        for b in (self.stroke_btn, self.fill_btn, self.op_btn, self.width_btn, self.head_btn, self.dup_btn, self.del_btn):
            lay.addWidget(b)
            b.setCursor(Qt.PointingHandCursor)
        self.stroke_btn.clicked.connect(lambda: self._color_menu(self.stroke_btn, False))
        self.fill_btn.clicked.connect(lambda: self._color_menu(self.fill_btn, True))
        self.width_btn.clicked.connect(self._width_menu)
        self.op_btn.clicked.connect(self._opacity_menu)
        self.head_btn.clicked.connect(self._head_menu)
        self.dup_btn.clicked.connect(lambda: self.view.duplicate_selection())
        self.del_btn.clicked.connect(lambda: self.view.delete_selection())
        self.hide()

    @staticmethod
    def _swatch(rgb, ring=True):
        pm = QPixmap(18, 18)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.5))
        pa.setBrush(QColor(*(int(c * 255) for c in rgb)) if rgb else QBrush(Qt.NoBrush))
        pa.drawEllipse(2, 2, 14, 14)
        if not rgb:
            pa.setPen(QPen(QColor("#E05050"), 1.5))
            pa.drawLine(4, 14, 14, 4)
        pa.end()
        return QIcon(pm)

    def _color_menu(self, anchor, fill: bool):
        ap = (lambda v: self.view.restyle_selection(fill=v)) if fill else (lambda v: self.view.restyle_selection(color=v))
        m = color_menu(self, self.view, fill, ap)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _opacity_menu(self):
        d = (self.view._ss_sel or {}).get("desc", {})
        s = d.get("opacity", 1.0)
        cur = (s, d.get("fill_opacity", s))

        def ap(part, v):
            kw = {"total": "opacity", "stroke": "stroke_op", "fill": "fill_op"}[part]
            self.view.restyle_selection(**{kw: v})
        m = opacity_menu(self, ap, has_fill=d.get("kind") in ("rect", "ellipse", "poly") and bool(d.get("fill")),
                         current=cur)
        m.exec(self.op_btn.mapToGlobal(self.op_btn.rect().bottomLeft()))

    def _head_menu(self):
        m = QMenu(self)
        for name, label in at.HEAD_LABELS:
            m.addAction(label, lambda n=name: self.view.restyle_selection(head=n))
        m.exec(self.head_btn.mapToGlobal(self.head_btn.rect().bottomLeft()))

    def _width_menu(self):
        m = QMenu(self)
        for w, label in ((1.0, tr("Fino")), (2.0, tr("Normal")), (4.0, tr("Grueso")), (7.0, tr("Muy grueso"))):
            m.addAction(label, lambda v=w: self.view.restyle_selection(width=v))
        m.exec(self.width_btn.mapToGlobal(self.width_btn.rect().bottomLeft()))

    def refresh(self, d: dict):
        self.stroke_btn.setIcon(self._swatch(d.get("stroke") or (0.1, 0.1, 0.1)))
        self.stroke_btn.setText(" " + tr("Borde"))
        can_fill = d["kind"] in ("rect", "ellipse", "poly")
        self.fill_btn.setVisible(can_fill)
        if can_fill:
            self.fill_btn.setIcon(self._swatch(d.get("fill")))
            self.fill_btn.setText(" " + tr("Relleno"))
        self.width_btn.setText(tr("Grosor"))
        s = d.get("opacity", 1.0) if d.get("opacity", 1.0) >= 0 else 1.0
        f = d.get("fill_opacity", s)
        self.op_btn.setVisible(True)
        self.op_btn.setText(tr("Opacidad {p} %", p=round(s * 100)) if (not (can_fill and d.get("fill")) or abs(s - f) < 0.01)
                            else tr("Opacidad {p1}/{p2} %", p1=round(s * 100), p2=round(f * 100)))
        self.op_btn.setToolTip(tr("Opacidad total; dentro puedes dar otra solo al trazo o solo al relleno"))
        self.head_btn.setVisible(d["kind"] == "arrow")
        self.head_btn.setText(tr("Punta"))
        self.adjustSize()
