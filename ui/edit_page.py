# -*- coding: utf-8 -*-
"""Pantalla Editar: panel lateral y herramientas sobre la vista del editor."""
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, QPointF, Signal, QThread
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QDesktopServices, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QFrame,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QDialog,
    QMessageBox,
    QMenu,
    QInputDialog,
    QProgressBar,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

import backend as be
import icons as ic
import winfonts
import fontmanager as fm
import annot_tools as at
import signature_pad as sp
import form_tools as ft
import stamp_tool as st_
import pdf_tools as ptl
import layout_tools as lt
import draft as dr
from theme import TEXT, ACCENT
from flow_layout import FlowLayout
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import ICON_DARK, _LIST_SELECT_QSS, _btn, add_shadow, on_gui, run_bg
from ui.editor_parts import (
    ClickIconDialog,
    CopyDialog,
    FieldDialog,
    InsertPageDialog,
    LinkDialog,
    NoteDialog,
    SelectionBar,
    color_menu,
    opacity_menu,
)
from ui.editor_view import PageEditorView
from ui.widgets import BackHeader

# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: EDIT — editor visual + censurar / buscar y reemplazar
# ══════════════════════════════════════════════════════════════════════════
class _FontLookupWorker(QThread):
    """Busca en Google Fonts las familias que faltan (sin bloquear la ventana)."""
    found = Signal(str, object)         # familia, {"info": …, "substitute": …}
    failed = Signal(str)

    def __init__(self, groups):
        super().__init__()
        self.groups = groups

    def run(self):
        for g in self.groups:
            try:
                info = fm.find_on_google(g["candidates"])
                sub_info = None
                sub_name = fm.SUBSTITUTES.get(g["family"].lower())
                if info is None and sub_name:
                    sub_info = fm.google_lookup(sub_name)
                self.found.emit(g["family"], {"info": info, "substitute": sub_info, "sub_name": sub_name})
            except OSError as e:
                self.failed.emit(str(e))
                return


class _FontDownloadWorker(QThread):
    progress = Signal(str)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, jobs, to_windows):
        super().__init__()
        self.jobs, self.to_windows = jobs, to_windows

    def run(self):
        installed = []
        try:
            for family, info, styles in self.jobs:
                paths = fm.download_family(
                    info, styles, progress=lambda i, n, name, fam=family: self.progress.emit(
                        tr("Descargando «{fam}»: {name} ({i}/{n})", fam=fam, name=name, i=i + 1, n=n) if name
                        else tr("«{fam}» descargada", fam=fam)))
                if self.to_windows:
                    self.progress.emit(tr("Instalando «{family}» en Windows…", family=family))
                    fm.install_in_windows(paths)
                installed.append(info["family"])
            self.done.emit(installed)
        except OSError as e:
            self.failed.emit(str(e))


class FontDownloadDialog(QDialog):
    """Lista las fuentes del PDF que no están instaladas y deja descargarlas de Google Fonts,
    instalándolas solo en el programa o también en Windows."""
    def __init__(self, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Fuentes que faltan"))
        self.resize(640, 520)
        self.groups = groups
        self.rows: dict[str, dict] = {}
        self.installed: list[str] = []
        self._workers = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        title = QLabel(tr("Fuentes que faltan"))
        title.setStyleSheet(f"font-size:17px; font-weight:600; color:{TEXT};")
        lay.addWidget(title)
        info = QLabel(tr("Este PDF usa fuentes que no están en tu ordenador. Sin ellas, al editar se usa una "
                      "parecida y el texto puede verse algo distinto. Las que publica Google Fonts "
                      "(licencia libre) se pueden descargar aquí. Las de Microsoft, Adobe o de pago no."))
        info.setObjectName("Hint")
        info.setWordWrap(True)
        lay.addWidget(info)

        self.list = QListWidget()
        self.list.setStyleSheet(_LIST_SELECT_QSS)
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for g in groups:
            it = QListWidgetItem(tr("«{family}» — comprobando en Google Fonts…", family=g['family']))
            it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable)
            self.list.addItem(it)
            self.rows[g["family"]] = {"group": g, "item": it, "info": None, "substitute": None}
        lay.addWidget(self.list, 1)

        self.search_btn = _btn(tr("Buscar la seleccionada en Google Fonts"), None, "Flat", icon_color=TEXT)
        self.search_btn.clicked.connect(self._search_web)
        lay.addWidget(self.search_btn, 0, Qt.AlignLeft)

        self.opt_app = QRadioButton(tr("Instalar solo en este programa (recomendado: no cambia nada en Windows)"))
        self.opt_win = QRadioButton(tr("Instalar también en Windows (para todos tus programas; solo para tu "
                                    "usuario, sin permisos de administrador)"))
        self.opt_app.setChecked(True)
        lay.addWidget(self.opt_app)
        lay.addWidget(self.opt_win)

        self.status = QLabel("")
        self.status.setObjectName("Hint")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        lay.addWidget(self.bar)

        btns = QHBoxLayout()
        self.close_btn = _btn(tr("Cerrar"), None, "Secondary", icon_color=TEXT)
        self.go_btn = _btn(tr("Descargar e instalar"), "download", "Primary", icon_color=ICON_DARK)
        self.go_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        self.go_btn.clicked.connect(self._start_download)
        btns.addStretch(1)
        btns.addWidget(self.close_btn)
        btns.addWidget(self.go_btn)
        lay.addLayout(btns)

        w = _FontLookupWorker(groups)
        w.found.connect(self._on_found)
        w.failed.connect(self._on_lookup_failed)
        w.finished.connect(self._on_lookup_done)
        self._workers.append(w)
        w.start()

    def _on_found(self, family: str, data: dict):
        row = self.rows[family]
        it = row["item"]
        row["info"], row["substitute"] = data["info"], data["substitute"]
        n_styles = len(row["group"]["styles"])
        if data["info"]:
            it.setText(tr("«{family}» — disponible en Google Fonts ({n} estilos)",
                          family=family, n=len(data['info']['files'])))
        elif data["substitute"]:
            it.setText(tr("«{family}» — de Microsoft; «{sub}» (Google Fonts) tiene las mismas medidas",
                          family=family, sub=data['sub_name']))
            it.setToolTip(tr("«{family}» no se puede descargar (es de Microsoft). «{sub}» es una "
                          "fuente libre con medidas idénticas: el texto ocupa lo mismo y no se descoloca.",
                          family=family, sub=data['sub_name']))
        else:
            it.setText(tr("«{family}» — no está en Google Fonts: se usa «Arial» en su lugar. Si quieres usar «{family}», "
                       "instálala en Windows (doble clic en el archivo de la fuente → Instalar) y reabre la aplicación.",
                       family=family))
            it.setToolTip(tr("Suele ser una fuente de pago o del sistema, y no se puede descargar de aquí."))
            return
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked)

    def _on_lookup_failed(self, msg: str):
        self.status.setText(tr("No se pudo conectar con Google Fonts. Comprueba tu conexión a internet."))
        for family, row in self.rows.items():
            if row["info"] is None and row["substitute"] is None:
                row["item"].setText(tr("«{family}» — sin conexión", family=family))

    def _on_lookup_done(self):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.go_btn.setEnabled(any(r["info"] or r["substitute"] for r in self.rows.values()))

    def _search_web(self):
        it = self.list.currentItem() or (self.list.item(0) if self.list.count() else None)
        if it is None:
            return
        fam = next(k for k, r in self.rows.items() if r["item"] is it)
        QDesktopServices.openUrl(QUrl("https://fonts.google.com/?query=" + fam.replace(" ", "+")))

    def _start_download(self):
        jobs = []
        for fam, r in self.rows.items():
            if r["item"].flags() & Qt.ItemIsUserCheckable and r["item"].checkState() == Qt.Checked:
                jobs.append((fam, r["info"] or r["substitute"], set(r["group"]["styles"])))
        if not jobs:
            self.status.setText(tr("Marca al menos una fuente."))
            return
        self.go_btn.setEnabled(False)
        self.bar.setRange(0, 0)
        w = _FontDownloadWorker(jobs, self.opt_win.isChecked())
        w.progress.connect(self.status.setText)
        w.done.connect(self._on_downloaded)
        w.failed.connect(self._on_download_failed)
        self._workers.append(w)
        w.start()

    def _on_downloaded(self, names: list):
        self.installed = names
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.status.setText(tr("Listo: {names} instalada(s). Ya se usarán al editar este PDF.",
                               names=", ".join(f"«{n}»" for n in names)))
        self.close_btn.setText(tr("  Cerrar"))

    def _on_download_failed(self, msg: str):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.go_btn.setEnabled(True)
        self.status.setText(tr("No se pudo descargar: {msg}", msg=msg))


class EditPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.doc = None
        self.current_file: dict | None = None
        self.page_idx = 0
        self.dirty = False
        self._warned_fonts: set[str] = set()
        self._active_panel: str | None = None
        self._undo_stack: list[bytes] = []
        self._redo_stack: list[bytes] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(BackHeader(tr("Edit – Editor visual"), lambda: win.go_home()))

        root.addWidget(QLabel(tr("Archivo:")))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        root.addWidget(self.file_combo)

        hint = QLabel(tr("Clic sobre cualquier texto de la página para editarlo directamente, "
                       "sobre la propia página. Enter hace una línea nueva, Ctrl+Enter confirma y Esc cancela. Usa la fuente original del "
                       "PDF si la tienes instalada en Windows; si no, avisa y usa una de respaldo."))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Aviso de fuentes que faltan (solo aparece si el PDF usa alguna que no tienes)
        self.font_banner = QFrame()
        self.font_banner.setStyleSheet(
            f"QFrame {{ background:rgba(192,130,88,0.16); border:1px solid {ACCENT}; border-radius:10px; }}"
            f"QLabel {{ background:transparent; border:none; }}")
        fb = QHBoxLayout(self.font_banner)
        fb.setContentsMargins(14, 10, 14, 10)
        self.font_banner_lbl = QLabel()
        self.font_banner_lbl.setWordWrap(True)
        fb_get = _btn(tr("Descargar fuentes…"), "download", "Primary", icon_color=ICON_DARK)
        fb_get.clicked.connect(self._open_font_dialog)
        fb_skip = _btn(tr("Ignorar"), None, "Flat", icon_color=TEXT)
        fb_skip.clicked.connect(self._ignore_fonts)
        fb_restart = _btn(tr("Reiniciar con este documento"), "back", "Secondary", icon_color=TEXT)
        fb_restart.setToolTip(tr("Cierra y vuelve a abrir la aplicación con este mismo documento y sus cambios, para "
                              "que reconozca una fuente recién instalada"))
        fb_restart.clicked.connect(self._restart_with_doc)
        fb.addWidget(self.font_banner_lbl, 1)
        fb.addWidget(fb_restart)
        fb.addWidget(fb_get)
        self.font_get_btn = fb_get
        fb.addWidget(fb_skip)
        self.font_banner.hide()
        self._missing_fonts: list = []
        self._ignored_fonts: set = set()
        self._font_state: dict = {}              # familia -> "google" | "no" (según la búsqueda en Google Fonts)
        self._lookup_worker = None
        root.addWidget(self.font_banner)

        # ── Barra de herramientas superior ───────────────────────────────
        toolbar = QFrame(); toolbar.setObjectName("Toolbar")
        toolbar.setStyleSheet("QFrame#Toolbar QPushButton { padding-left:8px; padding-right:8px; font-size:12px; }")
        outer = QVBoxLayout(toolbar)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)
        tb = QHBoxLayout()           # fila 1: deshacer/rehacer, páginas y guardar
        tools_row = QWidget()        # fila 2: herramientas (salta de línea si la ventana es estrecha)
        tb2 = FlowLayout(tools_row, margin=0, hspacing=8, vspacing=6)
        outer.addLayout(tb)
        outer.addWidget(tools_row)
        self.undo_btn = _btn("", "back"); self.undo_btn.setFixedWidth(38)
        self.undo_btn.setToolTip(tr("Deshacer (Ctrl+Z)"))
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._do_undo)
        self.redo_btn = _btn("", "forward"); self.redo_btn.setFixedWidth(38)
        self.redo_btn.setToolTip(tr("Rehacer (Ctrl+Y)"))
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._do_redo)
        tb.addWidget(self.undo_btn)
        tb.addWidget(self.redo_btn)
        tb.addSpacing(10)
        self.censor_btn = _btn(tr("Censurar"), "lock", "Secondary", icon_color=TEXT)
        self.censor_btn.setToolTip(tr("Tapar texto con una barra negra"))
        self.censor_btn.setCheckable(True)
        self.censor_btn.clicked.connect(lambda: self._toggle_panel("censor"))
        self.fr_btn = _btn(tr("Reemplazar"), "swap", "Secondary", icon_color=TEXT)
        self.fr_btn.setToolTip(tr("Buscar y reemplazar texto"))
        self.fr_btn.setCheckable(True)
        self.fr_btn.clicked.connect(lambda: self._toggle_panel("find"))
        self.edit_btn = _btn(tr("Editar"), "pencil", "Secondary", icon_color=TEXT)
        self.edit_btn.setCheckable(True)
        self.edit_btn.setChecked(True)
        self.edit_btn.setToolTip(tr("Editar el texto existente: haz clic sobre un texto y cámbialo"))
        self.edit_btn.clicked.connect(self._go_edit_mode)
        self.hf_btn = _btn(tr("Configurar página"), "document", "Secondary", icon_color=TEXT)
        self.hf_btn.setToolTip(tr("Marca qué es cabecera y pie de página y cómo se repiten en páginas nuevas"))
        self.hf_btn.clicked.connect(lambda: self.editor_view.ask_header_footer(self.page_idx))
        self.text_btn = _btn(tr("Texto"), "text_add", "Secondary", icon_color=TEXT)
        self.text_btn.setCheckable(True)
        self.text_btn.setToolTip(tr("Añadir texto nuevo: haz clic en cualquier punto de la página y escribe"))
        self.text_btn.clicked.connect(self._toggle_text_mode)
        self.manual_btn = _btn(tr("Automático"), "bolt", "Secondary", icon_color=TEXT)
        self.manual_btn.setCheckable(True)
        self.manual_btn.setToolTip(
            tr("Automático: deduce párrafos, listas, cabecera, pie y numeración, y reparte el texto "
            "entre páginas.\nManual: cada línea se edita por separado y no se mueve nada más."))
        self.manual_btn.clicked.connect(self._toggle_manual)
        self.annot_btn = _btn(tr("Marcar"), "highlight", "Secondary", icon_color=TEXT)
        self.annot_btn.setCheckable(True)
        self.annot_btn.setToolTip(tr("Resaltar, subrayar o tachar texto arrastrando sobre él"))
        self.annot_menu = QMenu(self.annot_btn)
        self.annot_btn.setMenu(self.annot_menu)
        self.annot_menu.aboutToShow.connect(self._fill_annot_menu)
        self.shape_btn = _btn(tr("Dibujar"), "pen", "Secondary", icon_color=TEXT)
        self.shape_btn.setCheckable(True)
        self.shape_btn.setToolTip(tr("Dibujo libre (lápiz, rotulador), rectángulos, elipses, líneas y flechas"))
        self.shape_btn.clicked.connect(self._toggle_shape_panel)
        self.image_btn = _btn(tr("Imagen"), "image", "Secondary", icon_color=TEXT)
        self.image_btn.setCheckable(True)
        self.image_btn.setToolTip(tr("Insertar una imagen, o seleccionar, mover y borrar las que ya hay en el PDF"))
        self.image_menu = QMenu(self.image_btn)
        self.image_btn.setMenu(self.image_menu)
        self.image_menu.aboutToShow.connect(self._fill_image_menu)
        tb2.addWidget(self.edit_btn)
        tb2.addWidget(self.fr_btn)
        tb2.addWidget(self.annot_btn)
        tb2.addWidget(self.image_btn)
        tb2.addWidget(self.shape_btn)
        self.sign_btn = _btn(tr("Firma"), "signature", "Secondary", icon_color=TEXT)
        self.sign_btn.setToolTip(tr("Firmar: dibuja, escribe o usa una imagen; se guarda para volver a usarla"))
        self.sign_menu = QMenu(self.sign_btn)
        self.sign_btn.setMenu(self.sign_menu)
        self.sign_menu.aboutToShow.connect(self._fill_sign_menu)
        self.link_btn = _btn(tr("Enlace"), "link", "Secondary", icon_color=TEXT)
        self.link_btn.setCheckable(True)
        self.link_btn.setToolTip(tr("Convertir un texto, un área, una imagen o un dibujo en un enlace; clic en uno existente para editarlo"))
        self.link_btn.clicked.connect(self._toggle_link_mode)
        tb2.addWidget(self.sign_btn)
        tb2.addWidget(self.link_btn)
        tb2.addWidget(self.censor_btn)
        self.form_btn = _btn(tr("Formulario"), "form", "Secondary", icon_color=TEXT)
        self.form_btn.setCheckable(True)
        self.form_btn.setToolTip(tr("Rellenar los campos del PDF, crear campos nuevos o aplanar el formulario"))
        self.form_btn.clicked.connect(self._toggle_form_mode)
        tb2.addWidget(self.form_btn)
        self.notes_btn = _btn(tr("Notas"), "note", "Secondary", icon_color=TEXT)
        self.notes_btn.setCheckable(True)
        self.notes_btn.setToolTip(tr("Notas y comentarios, archivos adjuntos y ocultar las anotaciones"))
        self.notes_menu = QMenu(self.notes_btn)
        self.notes_btn.setMenu(self.notes_menu)
        self.notes_menu.aboutToShow.connect(self._fill_notes_menu)
        tb2.addWidget(self.notes_btn)
        self.copy_btn = _btn(tr("Copiar texto"), "text_t", "Secondary", icon_color=TEXT)
        self.copy_btn.setCheckable(True)
        self.copy_btn.setToolTip(tr("Copiar texto con sentido: arrastra una zona o haz clic en un párrafo o tabla. "
                                 "Entiende párrafos, columnas y tablas (también en escaneos)"))
        self.copy_btn.clicked.connect(self._toggle_copy_mode)
        tb2.addWidget(self.copy_btn)
        self.stamp_btn = _btn(tr("Sello"), "stamp", "Secondary", icon_color=TEXT)
        self.stamp_btn.setToolTip(tr("Sello de texto (APROBADO, RECIBIDO…) con fecha y autor"))
        self.stamp_btn.clicked.connect(self._new_stamp)
        tb2.addWidget(self.stamp_btn)
        tb2.addWidget(self.text_btn)
        self.manual_btn.hide()           # el modo Automático es el único: ya no se ofrece como opción
        tb2.addWidget(self.hf_btn)
        tb.addStretch(1)
        prev_btn = _btn("", "chevron_left"); prev_btn.setFixedWidth(38)
        next_btn = _btn("", "chevron_right"); next_btn.setFixedWidth(38)
        prev_btn.clicked.connect(self._prev_page)
        next_btn.clicked.connect(self._next_page)
        self.page_lbl = QLabel("—")
        self.page_lbl.setObjectName("Hint")
        self.page_lbl.setFixedWidth(84)
        self.page_lbl.setAlignment(Qt.AlignCenter)
        tb.addWidget(prev_btn)
        tb.addWidget(self.page_lbl)
        tb.addWidget(next_btn)
        tb.addSpacing(10)
        zo = _btn("−", None); zo.setFixedWidth(34); zo.setToolTip(tr("Alejar (Ctrl y −, o Ctrl + rueda)"))
        zi = _btn("+", None); zi.setFixedWidth(34); zi.setToolTip(tr("Acercar (Ctrl y +, o Ctrl + rueda)"))
        self.zoom_btn = _btn("120 %", None, "Secondary", icon_color=TEXT)
        self.zoom_btn.setFixedWidth(64)
        self.zoom_btn.setToolTip(tr("Ajustar al ancho de la ventana (Ctrl+0)"))
        zo.clicked.connect(lambda: self.editor_view.zoom_by(1 / 1.2))
        zi.clicked.connect(lambda: self.editor_view.zoom_by(1.2))
        self.zoom_btn.clicked.connect(lambda: self.editor_view.fit_width())
        tb.addWidget(zo)
        tb.addWidget(self.zoom_btn)
        tb.addWidget(zi)
        tb.addSpacing(10)
        save_btn = _btn(tr("Guardar"), "save", "Primary")
        save_btn.clicked.connect(self._save_changes)
        tb.addWidget(save_btn)
        root.addWidget(toolbar)

        # ── Panel colapsable: censurar / buscar y reemplazar ─────────────
        self.tools_panel = QFrame(); self.tools_panel.setObjectName("Card")
        add_shadow(self.tools_panel, blur=18, dy=4, alpha=70)
        panel_lay = QVBoxLayout(self.tools_panel)

        self.censor_content = QWidget()
        c1 = QVBoxLayout(self.censor_content)
        c1.setContentsMargins(0, 0, 0, 0)
        censor_title = QLabel(tr("Censurar"))
        censor_title.setObjectName("SectionTitle")
        c1.addWidget(censor_title)
        censor_hint = QLabel(tr("Con este panel abierto, clica sobre cualquier fragmento de texto "
                              "de la página para taparlo al instante, o clica y arrastra sobre "
                              "cualquier área (también fotos o firmas) para censurar justo esa "
                              "zona. También puedes buscar un texto exacto aquí abajo. "
                              "Esta acción no se puede deshacer."))
        censor_hint.setObjectName("Hint")
        censor_hint.setWordWrap(True)
        c1.addWidget(censor_hint)
        censor_row = QHBoxLayout()
        self.censor_field = QLineEdit()
        self.censor_field.setPlaceholderText(tr("O escribe aquí un texto exacto a censurar"))
        censor_go_btn = _btn(tr("Censurar texto"), "lock", "Primary")
        censor_go_btn.clicked.connect(self._do_censor)
        censor_row.addWidget(self.censor_field, 1)
        censor_row.addWidget(censor_go_btn)
        c1.addLayout(censor_row)
        panel_lay.addWidget(self.censor_content)

        self.find_content = QWidget()
        c2 = QVBoxLayout(self.find_content)
        c2.setContentsMargins(0, 0, 0, 0)
        fr_title = QLabel(tr("Buscar y reemplazar"))
        fr_title.setObjectName("SectionTitle")
        c2.addWidget(fr_title)
        fr_row = QHBoxLayout()
        self.buscar_field = QLineEdit()
        self.buscar_field.setPlaceholderText(tr("Buscar"))
        self.reemplazar_field = QLineEdit()
        self.reemplazar_field.setPlaceholderText(tr("Reemplazar por (vacío = eliminar)"))
        fr_go_btn = _btn(tr("Reemplazar"), "swap", "Primary")
        fr_go_btn.clicked.connect(self._do_find_replace)
        fr_row.addWidget(self.buscar_field, 1)
        fr_row.addWidget(self.reemplazar_field, 1)
        fr_row.addWidget(fr_go_btn)
        c2.addLayout(fr_row)
        fr_opts = QHBoxLayout()
        self.case_cb = QCheckBox(tr("Distinguir mayúsculas y minúsculas"))
        fr_hint = QLabel(tr("Reemplaza en todo el documento conservando la fuente, el tamaño y el color. Ctrl+Z lo deshace."))
        fr_hint.setObjectName("Hint")
        fr_opts.addWidget(self.case_cb)
        fr_opts.addWidget(fr_hint, 1)
        c2.addLayout(fr_opts)
        panel_lay.addWidget(self.find_content)

        self.tools_panel.hide()
        root.addWidget(self.tools_panel)
        self._build_shape_panel(root)
        self._build_form_panel(root)

        # ── Vista continua de todas las páginas ──────────────────────────
        self.editor_view = PageEditorView(on_dirty=self._mark_dirty,
                                           on_font_missing=self._warn_font_missing,
                                           on_page_visible=self._on_page_visible,
                                           on_before_mutate=self._before_mutate,
                                           on_notice=lambda m: self.win.snack(m, "info"))
        self.editor_view.mode_changed.connect(self._on_view_mode)
        self.editor_view.page_action.connect(self._on_page_action)
        self.editor_view.shape_kind_changed.connect(self._on_shape_kind_changed)
        self.editor_view.icon_picker_requested.connect(self._open_icon_picker)
        self.editor_view.save_signature_requested.connect(self._on_save_signature)
        self.editor_view.zoomed.connect(lambda z: self.zoom_btn.setText(f"{round(z / 1.3333 * 100)} %"))
        for seq, fn in ((QKeySequence.StandardKey.ZoomIn, lambda: self.editor_view.zoom_by(1.2)),
                        (QKeySequence.StandardKey.ZoomOut, lambda: self.editor_view.zoom_by(1 / 1.2)),
                        (QKeySequence("Ctrl+0"), lambda: self.editor_view.fit_width())):
            sc_ = QShortcut(seq, self)
            sc_.activated.connect(fn)
        self.editor_view.link_requested.connect(self._on_link_requested)
        self.editor_view.field_requested.connect(self._on_field_requested)
        self.editor_view._reload_cb = self._reload_doc_from_bytes
        self.editor_view.note_requested.connect(self._on_note_requested)
        self.editor_view.copy_requested.connect(self._on_copy_requested)
        self.editor_view.replace_requested.connect(self._on_replace_requested)
        self._copy_cache: dict = {}
        self.editor_view.attach_clicked.connect(self._on_attach_clicked)
        root.addWidget(self.editor_view, 1)

        undo_sc = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_sc.activated.connect(self._do_undo)
        redo_sc = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_sc.activated.connect(self._do_redo)

    # ── Ciclo de vida de la pestaña / sesión de edición ─────────────────
    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)
        if self.win.uploaded_files:
            self.file_combo.setCurrentIndex(0)
            self._load_file(self.win.uploaded_files[0])

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _on_file_changed(self, idx: int):
        if 0 <= idx < len(self.win.uploaded_files):
            self._maybe_prompt_save()
            self._load_file(self.win.uploaded_files[idx])

    def _load_file(self, f: dict):
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:
                pass
        self.current_file = f
        self.doc = be.open_edit_session(f["path"])
        self.page_idx = 0
        self.dirty = False
        dr.clear()
        self._warned_fonts.clear()
        self._copy_cache = {}
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()
        self.editor_view.hf = None
        self._ignored_fonts = set()
        self._font_state = {}
        if not self.doc:
            self.page_lbl.setText("—")
        self.editor_view.load_doc(self.doc)
        self._refresh_font_banner()
        if self.doc is not None and ft.has_fields(self.doc):
            self.win.snack(tr("Este PDF tiene campos de formulario: usa el botón Formulario para rellenarlos."), "info")

    def _before_mutate(self):
        """Llamado justo antes de cualquier cambio (editar texto, censurar)
        para poder deshacerlo luego."""
        if self.doc is None:
            return
        snap = be.snapshot_doc_bytes(self.doc)
        if snap:
            self._undo_stack.append(snap)
            self._redo_stack.clear()
            self._update_undo_redo_buttons()

    def _swap_doc(self, new_bytes: bytes):
        new_doc = be.doc_from_bytes(new_bytes)
        if new_doc is None:
            return False
        old_doc = self.doc
        self.doc = new_doc
        self._copy_cache = {}
        try:
            if old_doc is not None:
                old_doc.close()
        except Exception:
            pass
        vbar_val = self.editor_view.verticalScrollBar().value()
        self.editor_view.load_doc(self.doc)
        self.editor_view.verticalScrollBar().setValue(vbar_val)
        return True

    def _do_undo(self):
        if not self._undo_stack or self.editor_view._editor is not None:
            return
        cur = be.snapshot_doc_bytes(self.doc)
        prev_bytes = self._undo_stack.pop()
        if self._swap_doc(prev_bytes):
            if cur:
                self._redo_stack.append(cur)
            self.dirty = bool(self._undo_stack)
            self._schedule_draft()
            self._update_undo_redo_buttons()
            self.win.snack(tr("↩ Deshecho"), "info")

    def _do_redo(self):
        if not self._redo_stack or self.editor_view._editor is not None:
            return
        cur = be.snapshot_doc_bytes(self.doc)
        next_bytes = self._redo_stack.pop()
        if self._swap_doc(next_bytes):
            if cur:
                self._undo_stack.append(cur)
            self.dirty = True
            self._schedule_draft()
            self._update_undo_redo_buttons()
            self.win.snack(tr("↪ Rehecho"), "info")

    def _update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(bool(self._undo_stack))
        self.redo_btn.setEnabled(bool(self._redo_stack))

    def _on_page_visible(self, idx: int, total: int):
        self.page_idx = idx
        self.page_lbl.setText(tr("Pág. {n} / {total}", n=idx + 1, total=total) if total else "—")

    def _prev_page(self):
        if self.doc and self.page_idx > 0:
            self.editor_view.scroll_to_page(self.page_idx - 1)

    def _next_page(self):
        if self.doc and self.page_idx < len(self.doc) - 1:
            self.editor_view.scroll_to_page(self.page_idx + 1)

    def _close_panel(self):
        self._active_panel = None
        self.tools_panel.hide()
        self.censor_btn.setChecked(False)
        self.fr_btn.setChecked(False)
        self.editor_view.set_mode("edit")

    def _toggle_panel(self, which: str):
        if self._active_panel == which:
            self._close_panel()
            return
        self._active_panel = which
        self.tools_panel.show()
        if which == "censor":
            self.censor_content.show()
            self.find_content.hide()
            self.censor_btn.setChecked(True)
            self.fr_btn.setChecked(False)
            self.editor_view.set_mode("censor")
        else:
            self.find_content.show()
            self.censor_content.hide()
            self.fr_btn.setChecked(True)
            self.censor_btn.setChecked(False)
            self.editor_view.set_mode("edit")

    # ── Fuentes que faltan ──────────────────────────────────────────────
    def _font_banner_text(self) -> str:
        fb = self.editor_view._FALLBACK_FONT
        lines = []
        for g in self._missing_fonts:
            fam, st = g["family"], self._font_state.get(g["family"])
            if st == "google":
                lines.append(tr("La fuente «{fam}» no está instalada, pero está en Google Fonts: pulsa «Descargar "
                             "fuentes…» para instalarla. Mientras tanto se usa «{fb}».", fam=fam, fb=fb))
            elif st == "no":
                lines.append(tr("La fuente «{fam}» no está en Google Fonts (suele ser de pago o de otro programa): se está "
                             "usando «{fb}» en su lugar. Si quieres usar «{fam}», descárgala e instálala en Windows "
                             "(doble clic en el archivo de la fuente → Instalar) y pulsa «Reiniciar con este documento».",
                             fam=fam, fb=fb))
            else:
                lines.append(tr("La fuente «{fam}» no está instalada: se está usando «{fb}» en su lugar. Si quieres usar "
                             "«{fam}», instálala en Windows y reabre la aplicación (o mira si está en Google Fonts "
                             "con «Descargar fuentes…»).", fam=fam, fb=fb))
        return "\n".join(lines)

    def _refresh_font_banner(self):
        """Muestra el aviso si el PDF usa fuentes que no están instaladas, diciendo cuál se usa en su lugar."""
        missing = fm.missing_fonts(self.doc) if self.doc is not None else []
        self._missing_fonts = [g for g in missing if g["family"] not in self._ignored_fonts]
        if not self._missing_fonts:
            self.font_banner.hide()
            return
        self.font_banner_lbl.setText(self._font_banner_text())
        self._sync_font_buttons()
        self.font_banner.show()
        todo = [g for g in self._missing_fonts if g["family"] not in self._font_state]
        if todo and (self._lookup_worker is None or not self._lookup_worker.isRunning()):
            w = _FontLookupWorker(todo)
            w.found.connect(self._on_font_looked_up)
            self._lookup_worker = w
            w.start()

    def _on_font_looked_up(self, family: str, data: dict):
        self._font_state[family] = "google" if (data["info"] or data["substitute"]) else "no"
        if self._missing_fonts:
            self.font_banner_lbl.setText(self._font_banner_text())
            self._sync_font_buttons()

    def _sync_font_buttons(self):
        """«Descargar fuentes» solo tiene sentido si alguna está (o puede estar) en Google Fonts."""
        self.font_get_btn.setVisible(any(self._font_state.get(g["family"]) != "no" for g in self._missing_fonts))

    def _ignore_fonts(self):
        self._ignored_fonts |= {g["family"] for g in self._missing_fonts}
        self._refresh_font_banner()

    def _open_font_dialog(self):
        dlg = FontDownloadDialog(self._missing_fonts, self.window())
        dlg.exec()
        if dlg.installed:
            winfonts.refresh_installed_fonts()
            self._refresh_font_banner()
            self.editor_view.reload_preserving_scroll()
            self.win.snack(tr("Fuentes instaladas: {names}", names=", ".join(dlg.installed)), "success")

    # ── Páginas, texto libre y modo manual ──────────────────────────────

    def _add_page(self, at: int):
        if not self.doc:
            return
        ev = self.editor_view
        dlg = InsertPageDialog(ev, self.doc, at, self.window())
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.choice == "pdf":
            self._before_mutate()
            res = be.insert_pdf_pages(self.doc, at, dlg.pdf_path)
            if res["ok"]:
                self._mark_dirty()
                ev.reload_preserving_scroll()
                ev.scroll_to_page(at)
                self.win.snack(tr("{n} página{s} insertada{s}.", n=res['count'],
                                  s='s' if res['count'] != 1 else ''), "success")
            else:
                self.win.snack(tr("No se pudo insertar ese PDF (¿tiene contraseña?)."), "error")
            return
        self._insert_blank(at, dlg.settings)

    def _insert_blank(self, at: int, settings):
        ev = self.editor_view
        if (ev.manual or len(self.doc) < 2) and settings is None and ev.hf is None:
            # Con una sola página (o en modo manual) no se puede deducir cabecera, pie y numeración.
            if not ev.ask_header_footer(self.page_idx, tr("Marca la cabecera y el pie de página para "
                                        "copiarlos a la página nueva y decide cómo se numera.")):
                return
            settings = ev.hf
        self._before_mutate()
        res = be.insert_page(self.doc, at, settings=settings)
        if res["ok"]:
            self._mark_dirty()
            ev.reload_preserving_scroll()
            ev.scroll_to_page(at)
            self.win.snack(tr("Página añadida (ahora es la {n}).", n=at + 1), "success")
        else:
            self.win.snack(tr("No se pudo añadir la página."), "error")

    def _rotate(self, idxs: list, delta: int):
        if not self.doc:
            return
        self._before_mutate()
        if be.rotate_pages(self.doc, idxs, delta):
            self._mark_dirty()
            self.editor_view.reload_preserving_scroll()
            self.win.snack(tr("Página girada. Mientras esté girada no se puede editar su contenido; vuelve a girarla "
                           "a su posición para hacerlo.") if len(idxs) == 1 else tr("Páginas giradas."), "info")
        else:
            self.win.snack(tr("No se pudo girar."), "error")

    def _delete_page(self):
        if not self.doc:
            return
        if len(self.doc) < 2:
            self.win.snack(tr("No se puede borrar la única página del documento."), "error")
            return
        n = self.page_idx + 1
        if QMessageBox.question(
                self, tr("Borrar página"), tr("¿Borrar la página {n} con todo su contenido?\n"
                "Las siguientes se renumeran. Puedes deshacerlo con Ctrl+Z.", n=n),
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._before_mutate()
        res = be.delete_pages(self.doc, [self.page_idx], settings=self.editor_view.hf)
        if res["ok"]:
            self._mark_dirty()
            self.editor_view.reload_preserving_scroll()
            self.editor_view.scroll_to_page(min(self.page_idx, len(self.doc) - 1))
            self.win.snack(tr("Página {n} borrada.", n=n), "success")
        else:
            self.win.snack(tr("No se pudo borrar la página."), "error")

    def _toggle_text_mode(self, checked: bool):
        if checked:
            self._close_panel()
            self.text_btn.setChecked(True)
            self.editor_view.set_mode("text")
            self.win.snack(tr("Haz clic en la página donde quieras escribir."), "info")
        else:
            self.editor_view.set_mode("edit")

    def _on_page_action(self, action: str, idx: int):
        # se aplica fuera del clic: recargar la escena destruye el propio botón que se está pulsando
        QTimer.singleShot(0, lambda: self._do_page_action(action, idx))

    def _do_page_action(self, action: str, idx: int):
        if not self.doc:
            return
        self.page_idx = min(idx, len(self.doc) - 1)
        if action in ("zoomin", "zoomout"):
            self.editor_view.zoom_by(1.2 if action == "zoomin" else 1 / 1.2)
        elif action == "insert":
            self._add_page(idx)
        elif action == "delete":
            self._delete_page()
        elif action == "rotl":
            self._rotate([idx], -90)
        elif action == "rotr":
            self._rotate([idx], 90)

    def _go_edit_mode(self):
        self._close_panel()
        self.editor_view.set_mode("edit")
        self.edit_btn.setChecked(True)

    def _on_view_mode(self, mode: str):
        self.edit_btn.setChecked(mode == "edit")
        self.text_btn.setChecked(mode == "text")
        self.annot_btn.setChecked(mode == "markup")
        if mode != "markup":
            self.annot_btn.setText(tr("  Marcar"))
        self.shape_btn.setChecked(mode == "shape")
        self.shape_panel.setVisible(mode == "shape")
        if mode == "shape":
            self._sync_shape_panel()
        self.image_btn.setChecked(mode == "image")
        self.link_btn.setChecked(mode == "link")
        self.form_btn.setChecked(mode == "form")
        self.form_panel.setVisible(mode == "form")
        self.notes_btn.setChecked(mode in ("note", "attach"))
        self.copy_btn.setChecked(mode == "copy")
        if mode != "shape":
            self.shape_btn.setText(tr("  Dibujar"))

    # ── Enlaces ─────────────────────────────────────────────────────────
    # ── Sellos ──────────────────────────────────────────────────────────
    def _new_stamp(self):
        if self.doc is None:
            return
        self._close_panel()
        dlg = st_.StampDialog(self.window())
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            try:
                size = at.image_size(str(dlg.result_path))
            except Exception:
                self.win.snack(tr("No se pudo crear el sello."), "error")
                return
            self.begin_place_image(str(dlg.result_path), size, max_frac=0.28, what=tr("el sello"))

    # ── Copiar texto con sentido ────────────────────────────────────────
    def _toggle_copy_mode(self, checked: bool):
        if checked:
            self._close_panel()
            self.editor_view.set_mode("copy")
            self.win.snack(tr("Arrastra para copiar una zona, o haz clic en un párrafo o una tabla. Esc para salir."), "info")
        else:
            self.editor_view.set_mode("edit")

    def _ocr_langs_for_copy(self) -> list:
        tp = getattr(self.win, "tools_page", None)
        chosen = [c for c, cb in getattr(tp, "_ocr_checks", {}).items() if cb.isChecked()] if tp else []
        return chosen or ["spa", "por", "eng"][:1]

    def _page_layout(self, page_idx: int):
        key = (id(self.doc), page_idx)
        if key in self._copy_cache:
            return self._copy_cache[key]
        tp = getattr(self.win, "tools_page", None)
        engine = tp.ocr_engine.currentData() if tp is not None and hasattr(tp, "ocr_engine") else "tesseract"
        entry = ptl.page_layout(self.doc[page_idx], self._ocr_langs_for_copy(), engine=engine)
        self._copy_cache[key] = entry
        return entry

    def _on_copy_requested(self, page_idx: int, rect, pt):
        ev = self.editor_view
        if self.doc is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            entry = self._page_layout(page_idx)
        except ptl.ToolError as e:
            QApplication.restoreOverrideCursor()
            self.win.snack(str(e), "error")
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.win.snack(tr("No se pudo analizar la página: {e}", e=e), "error")
            return
        QApplication.restoreOverrideCursor()
        if not entry["words"]:
            self.win.snack(tr("No he encontrado texto en esa página."), "info")
            return
        if rect is not None:                                           # zona arrastrada
            d_rect = ptl.to_analysis_rect(entry, rect)
            res = lt.region_to_text(entry["words"], d_rect, True, entry["h_lines"], entry["v_lines"])
            blocks, shown = res["blocks"], rect
        else:                                                          # clic: el párrafo o la tabla que hay ahí
            d_pt = ptl.to_analysis_rect(entry, (pt[0], pt[1], pt[0], pt[1]))[:2]
            blk = lt.block_at(entry["blocks"], d_pt)
            if blk is None:
                self.win.snack(tr("Ahí no hay texto. Arrastra para elegir una zona."), "info")
                return
            blocks = [blk]
            shown = ptl.from_analysis_rect(entry, blk.bbox)
        if not blocks:
            self.win.snack(tr("Esa zona no contiene texto."), "info")
            return
        ev.show_copy_highlight(page_idx, shown)
        note = ""
        if entry["ocr"]:
            note = tr("Esta página es una imagen: el texto se ha reconocido ahora mismo (OCR, idioma: {langs}). "
                    "Para tenerlo siempre buscable y copiable en cualquier lector, usa Herramientas → OCR.",
                    langs=", ".join(ptl.LANG_NAMES.get(l, l) for l in entry.get("langs", [])))
        dlg = CopyDialog(self.window(), blocks, note)
        dlg.exec()
        ev.clear_copy_highlight()

    # ── Notas, adjuntos y ocultar anotaciones ───────────────────────────
    def _fill_notes_menu(self):
        m = self.notes_menu
        m.clear()
        ev = self.editor_view
        m.addAction(ic.icon("note", TEXT, 17), tr("Añadir nota"), self._enter_note)
        m.addAction(ic.icon("link", TEXT, 17), tr("Adjuntar archivo…"), self._pick_attachment)
        m.addSeparator()
        a = m.addAction(tr("Ocultar anotaciones (solo en pantalla)"))
        a.setCheckable(True)
        a.setChecked(ev.hide_annots)
        a.triggered.connect(lambda on: ev.set_hide_annots(bool(on)))
        if ev.mode in ("note", "attach"):
            m.addSeparator()
            m.addAction(tr("Terminar"), lambda: ev.set_mode("edit"))

    def _enter_note(self):
        if self.doc is None:
            return
        self._close_panel()
        self.editor_view.set_mode("note")
        self.win.snack(tr("Haz clic donde quieras la nota. Clic en una nota para editarla; arrástrala para moverla."), "info")

    def _on_note_requested(self, page_idx: int, pt, existing):
        author = os.environ.get("USERNAME", "")
        dlg = NoteDialog(self.window(), (existing or {}).get("text", ""), (existing or {}).get("author", "") or author,
                         existing is not None)
        if dlg.exec() != QDialog.Accepted:
            return
        text = dlg.edit.toPlainText().strip()
        if existing is None and not text:
            return
        if not self.editor_view.apply_note(page_idx, pt, existing, text, author, remove=dlg.remove):
            self.win.snack(tr("No se pudo guardar la nota."), "error")

    def _pick_attachment(self):
        if self.doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Elige el archivo que quieres adjuntar"), str(Path.home()))
        if not path:
            return
        if os.path.getsize(path) > at.MAX_ATTACH:
            self.win.snack(tr("Ese archivo pesa más de 25 MB; no se adjunta."), "error")
            return
        self._close_panel()
        self.editor_view.set_mode("attach")
        self.editor_view.pending_attach = path
        self.editor_view.viewport().setCursor(Qt.BlankCursor)             # en su lugar viaja el clip con el ratón
        self.win.snack(tr("Mueve el clip hasta donde quieras ponerlo y haz clic. Esc cancela."), "info")

    def _on_attach_clicked(self, page_idx: int, att: dict, gpos):
        m = QMenu(self)
        m.addAction(tr("Guardar una copia de «{name}»…", name=att['name']), lambda: self._save_attachment(page_idx, att))
        m.addAction(tr("Quitar adjunto"), lambda: self.editor_view.remove_attachment(page_idx, att["xref"]))
        m.exec(gpos)

    def _save_attachment(self, page_idx: int, att: dict):
        got = at.read_attachment(self.doc, page_idx, att["xref"])
        if not got:
            self.win.snack(tr("No se pudo leer el adjunto."), "error")
            return
        name, data = got
        dest, _ = QFileDialog.getSaveFileName(self, tr("Guardar adjunto"), str(Path.home() / "Downloads" / Path(name).name))
        if dest:
            Path(dest).write_bytes(data)
            self.win.snack(tr("Adjunto guardado: {name}. No se abre solo: ábrelo tú si te fías de su origen.",
                           name=Path(dest).name), "success")

    def _reload_doc_from_bytes(self):
        """Reabre el documento desde su estado actual en memoria (conserva deshacer y modo)."""
        snap = be.snapshot_doc_bytes(self.doc)
        if snap:
            self._swap_doc(snap)
            self.editor_view._fm_refresh()

    # ── Formularios ─────────────────────────────────────────────────────
    def _build_form_panel(self, root):
        """Barra del modo formulario: los campos del PDF se rellenan con solo entrar; aquí van las demás acciones."""
        self.form_panel = QFrame()
        self.form_panel.setObjectName("Card")
        self.form_panel.setStyleSheet("QFrame#Card QPushButton { padding:5px 9px; font-size:12px; }")
        fl = FlowLayout(self.form_panel, margin=8, hspacing=6, vspacing=6)
        hint = QLabel(tr("Haz clic en un campo (recuadro azul) para rellenarlo. Arrastra en un hueco para crear uno nuevo."))
        hint.setObjectName("Hint")
        fl.addWidget(hint)
        det = _btn(tr("Detectar campos automáticamente…"), "bolt", "Secondary", icon_color=TEXT)
        det.setToolTip(tr("Busca rayas, recuadros vacíos y casillas para convertirlos en campos"))
        det.clicked.connect(self._detect_fields)
        fl.addWidget(det)
        tab = _btn(tr("Orden de tabulación"), "swap", "Secondary", icon_color=TEXT)
        tab_menu = QMenu(tab)

        def fill_tab():
            tab_menu.clear()
            cur = ft.get_tab_order(self.doc) if self.doc is not None else None
            for key, label in ft.TAB_ORDERS.items():
                a = tab_menu.addAction(label)
                a.setCheckable(True)
                a.setChecked(cur == key)
                a.triggered.connect(lambda _=False, k=key: self._set_tab_order(k))
        tab_menu.aboutToShow.connect(fill_tab)
        tab.setMenu(tab_menu)
        fl.addWidget(tab)
        flat = _btn(tr("Aplanar formulario…"), "download", "Secondary", icon_color=TEXT)
        flat.setToolTip(tr("Convierte los campos rellenados en contenido fijo de la página"))
        flat.clicked.connect(self._flatten_form)
        fl.addWidget(flat)
        self.form_panel.hide()
        root.addWidget(self.form_panel)

    def _toggle_form_mode(self, checked: bool = False):
        if self.editor_view.mode == "form":
            self.editor_view.set_mode("edit")
        else:
            self._enter_form()

    def _enter_form(self):
        if self.doc is None:
            return
        self._close_panel()
        self.editor_view.set_mode("form")
        n = sum(len(v) for v in self.editor_view._fm_cache.values())
        msg = tr("Hay {n} campos (recuadros azules): haz clic en uno para rellenarlo. ", n=n) if n else \
            tr("Este PDF no tiene campos. ")
        self.win.snack(msg + tr("Arrastra un recuadro vacío para crear uno nuevo; clic derecho "
                       "sobre un campo para eliminarlo."), "info")

    def _detect_fields(self):
        if self.doc is None:
            return
        found = ft.detect_all(self.doc)
        total = sum(len(v) for v in found.values())
        if not total:
            self.win.snack(tr("No encontré rayas, recuadros vacíos ni casillas que convertir en campos."), "info")
            return
        self._close_panel()
        self.editor_view.set_mode("form")
        self.editor_view.show_candidates(found)
        first = min(found)
        self.editor_view.scroll_to_page(first)
        n_chk = sum(1 for v in found.values() for c in v if c["kind"] == "checkbox")
        resp = QMessageBox.question(
            self, tr("Detectar campos"),
            tr("He encontrado {total} posibles campos (marcados en verde): {n_text} de texto y {n_chk} casillas.\n\n"
            "Salen de rayas, recuadros vacíos y cuadritos de la página; revisa que no sobre ninguno (puedes borrar "
            "los que no quieras con clic derecho). ¿Crearlos?", total=total, n_text=total - n_chk, n_chk=n_chk),
            QMessageBox.Yes | QMessageBox.No)
        self.editor_view.show_candidates(None)
        if resp != QMessageBox.Yes:
            return
        self._before_mutate()
        n = ft.create_detected(self.doc, found)
        if n:
            self._mark_dirty()
            self.editor_view.reload_preserving_scroll()
            self.editor_view._fm_refresh()
            self.win.snack(tr("{n} campos creados. Haz clic en uno para rellenarlo.", n=n), "success")
        else:
            self.win.snack(tr("No se pudo crear ningún campo."), "error")

    def _set_tab_order(self, order: str):
        if self.doc is None:
            return
        if not ft.has_fields(self.doc):
            self.win.snack(tr("Este PDF no tiene campos de formulario."), "info")
            return
        self._before_mutate()
        n = ft.set_tab_order(self.doc, order)
        if n:
            self._mark_dirty()
            self.win.snack(tr("Orden de tabulación: {order} (en {n} página{s}).",
                           order=ft.TAB_ORDERS[order].lower(), n=n, s='s' if n != 1 else ''),
                           "success")

    def _on_field_requested(self, page_idx: int, rect):
        dlg = FieldDialog(self.window(), ft.unique_name(self.doc, "campo"))
        if dlg.exec() == QDialog.Accepted and dlg.spec:
            if self.editor_view.apply_new_field(page_idx, rect, dlg.spec):
                self.win.snack(tr("Campo creado."), "success")
            else:
                self.win.snack(tr("No se pudo crear el campo."), "error")

    def _flatten_form(self):
        if self.doc is None:
            return
        if not ft.has_fields(self.doc):
            self.win.snack(tr("Este PDF no tiene campos de formulario."), "info")
            return
        if QMessageBox.question(self, tr("Aplanar formulario"),
                                tr("Los campos pasarán a ser contenido fijo de la página, con lo que hayas rellenado: "
                                "ya no se podrán editar. Puedes deshacerlo con Ctrl+Z hasta que guardes.\n\n"
                                "¿Aplanar el formulario?"), QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._before_mutate()
        if ft.flatten(self.doc):
            self._mark_dirty()
            self.editor_view.set_mode("edit")
            self.editor_view.reload_preserving_scroll()
            self.win.snack(tr("Formulario aplanado."), "success")
        else:
            self.win.snack(tr("No se pudo aplanar el formulario."), "error")

    def _toggle_link_mode(self, checked: bool):
        if checked:
            self._close_panel()
            self.editor_view.set_mode("link")
            self.win.snack(tr("Arrastra sobre un texto o un área para crear un enlace. Haz clic en un recuadro azul "
                           "para editarlo o quitarlo."), "info")
        else:
            self.editor_view.set_mode("edit")

    def _on_link_requested(self, page_idx: int, boxes, existing):
        n_zones = len(at.group_of(self.doc, page_idx, existing)) if existing else len(boxes)
        from_obj = bool(getattr(self.editor_view, "_lk_from_object", False)) and existing is None
        dlg = LinkDialog(self.window(), len(self.doc), existing, n_zones, allow_underline=not from_obj)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.remove:
            if self.editor_view.apply_link(page_idx, boxes, existing, None):
                self.win.snack(tr("Enlace quitado."), "info")
            return
        if self.editor_view.apply_link(page_idx, boxes, existing, dlg.result_dest,
                                       underline=existing is None and dlg.underline_cb.isChecked(), obj=from_obj,
                                       color=dlg.link_color):
            self.win.snack(tr("Enlace guardado.") if existing else
                           tr("Enlace creado ({n} zona{s}).", n=len(boxes), s='s' if len(boxes) != 1 else ''), "success")
            if from_obj and len(boxes) == 1:
                dlg2 = ClickIconDialog(self.window())
                if dlg2.exec() == QDialog.Accepted and dlg2.kind:
                    self._add_click_icon(page_idx, boxes[0], dlg2.kind)
        else:
            self.win.snack(tr("No se pudo guardar el enlace."), "error")

    def _open_icon_picker(self):
        ev = self.editor_view
        if not (ev._img_sel and ev._img_sel.get("icon")):
            return
        old = getattr(self, "_icon_picker", None)
        if old is not None:
            try:
                old.close()
            except RuntimeError:
                pass
        dlg = ClickIconDialog(self.window(), live=ev.swap_selected_icon)
        dlg.setWindowFlag(Qt.Tool, True)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        self._icon_picker = dlg
        dlg.show()

    def _add_click_icon(self, page_idx: int, box, kind: str):
        """Pone el icono elegido («clic aquí») en la esquina inferior derecha de la imagen enlazada; queda
        seleccionado para moverlo o girarlo."""
        x0, y0, x1, y1 = box
        s = max(30.0, min(60.0, 0.5 * min(x1 - x0, y1 - y0)))
        rect = (x1 - s - 4, y1 - s - 4, x1 - 4, y1 - 4)
        self._before_mutate()
        xref = at.add_click_icon(self.doc, page_idx, rect, kind, 0.0)
        if not xref:
            self.win.snack(tr("No se pudo añadir el icono."), "error")
            return
        self._mark_dirty()
        ev = self.editor_view
        ev.refresh_page(page_idx)
        ev.set_mode("image")
        ev._img_select({"page": page_idx, "xref": xref, "rect": rect, "icon": (kind, 0.0)})
        self.win.snack(tr("Icono añadido. Arrástralo para moverlo; el punto de arriba lo gira (o las teclas [ y ])."),
                       "success")

    # ── Imagen ──────────────────────────────────────────────────────────
    def _fill_image_menu(self):
        m = self.image_menu
        m.clear()
        m.addAction(ic.icon("image", TEXT, 17), tr("Insertar una imagen…"), self._pick_image)
        m.addAction(ic.icon("select", TEXT, 17), tr("Seleccionar, mover o borrar imágenes"), self._image_select_mode)
        if self.editor_view.mode == "image":
            m.addSeparator()
            m.addAction(tr("Terminar"), lambda: self.editor_view.set_mode("edit"))

    def _image_select_mode(self):
        """Modo imagen sin insertar nada: clic en una imagen (del PDF o puesta aquí) para moverla, escalarla o borrarla."""
        if self.doc is None:
            return
        self._close_panel()
        self.editor_view._img_select(None)
        self.editor_view.set_mode("image")
        self.editor_view.viewport().setCursor(Qt.ArrowCursor)
        self.win.snack(tr("Haz clic en una imagen para seleccionarla: arrástrala para moverla, usa los puntos para cambiar "
                       "el tamaño y pulsa Supr para borrarla (en las imágenes del PDF, solo borrar). Esc para salir."),
                       "info")

    def _pick_image(self):
        if self.doc is None:
            self.image_btn.setChecked(False)
            return
        self._close_panel()                      # suelta lo que hubiera activo (Marcar, Dibujar…) antes de elegir
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Elige una imagen"), str(Path.home() / "Pictures"),
            tr("Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;Todos los archivos (*.*)"))
        if not path:
            self.image_btn.setChecked(self.editor_view.mode == "image")
            return
        try:
            size = at.image_size(path)
        except Exception:
            self.image_btn.setChecked(False)
            self.win.snack(tr("No se pudo leer esa imagen."), "error")
            return
        self.begin_place_image(path, size)

    def begin_place_image(self, source, size, max_frac: float = 0.45, what: str = None):
        if what is None:
            what = tr("la imagen")
        self._close_panel()
        self.editor_view.start_place_image(source, size, max_frac)
        self.win.snack(tr("Haz clic donde quieras {what} (o arrastra para dibujarle el tamaño). Después puedes "
                       "moverla, cambiarle el tamaño por las esquinas (Mayús = deformar) y borrarla con Supr.",
                       what=what), "info")

    # ── Firma ───────────────────────────────────────────────────────────
    def _sig_thumb(self, path) -> QIcon:
        pm = QPixmap(str(path))
        thumb = QPixmap(96, 34)
        thumb.fill(QColor("#FFFFFF"))
        if not pm.isNull():
            pa = QPainter(thumb)
            pa.setRenderHint(QPainter.SmoothPixmapTransform)
            scaled = pm.scaled(88, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pa.drawPixmap((96 - scaled.width()) // 2, (34 - scaled.height()) // 2, scaled)
            pa.end()
        return QIcon(thumb)

    def _fill_sign_menu(self):
        m = self.sign_menu
        m.clear()
        saved = sp.list_saved()
        for path in saved[:10]:
            act = m.addAction(self._sig_thumb(path), "  " + sp.display_name(path))
            act.triggered.connect(lambda _=False, p_=path: self._place_signature(p_))
        if saved:
            m.addSeparator()
        m.addAction(tr("Crear firma nueva…"), self._new_signature)
        if saved:
            dm = m.addMenu(tr("Gestionar mis firmas"))
            for path in saved[:10]:
                sm = dm.addMenu(self._sig_thumb(path), "  " + sp.display_name(path))
                sm.addAction(tr("Cambiar el nombre…"), lambda _=False, p_=path: self._rename_signature(p_))
                if sp.load_meta(path).get("type") in ("draw", "text"):
                    sm.addAction(tr("Editar…"), lambda _=False, p_=path: self._edit_signature(p_))
                sm.addAction(tr("Borrar"), lambda _=False, p_=path: self._delete_signature(p_))

    def _rename_signature(self, path):
        name, ok = QInputDialog.getText(self, tr("Nombre de la firma"), tr("Nombre:"), text=sp.display_name(path))
        if ok and name.strip():
            sp.rename(path, name)
            self.win.snack(tr("Firma renombrada."), "info")

    def _edit_signature(self, path):
        dlg = sp.SignatureDialog(self.window(), edit_path=path)
        if dlg.exec() == QDialog.Accepted:
            self.win.snack(tr("Firma actualizada. Se usará la nueva versión en los documentos siguientes."), "success")

    def _on_save_signature(self, desc: dict):
        """Clic derecho sobre un dibujo libre → guardarlo como firma reutilizable."""
        strokes = [[QPointF(x, y) for x, y in st] for st in desc.get("strokes", []) if len(st) > 1]
        rgb = desc.get("stroke") or (0.1, 0.1, 0.1)
        color = "#%02x%02x%02x" % tuple(int(c * 255) for c in rgb)
        width = max(1.0, float(desc.get("width", 2.0)) / (5 if desc.get("marker") else 1))
        img = sp.render_strokes(strokes, color, width, scale=5.0)
        if img is None:
            self.win.snack(tr("Ese dibujo no se puede guardar como firma."), "error")
            return
        name, ok = QInputDialog.getText(self, tr("Guardar como firma"), tr("Nombre de la firma:"), text=tr("Firma"))
        if not ok:
            return
        sp.save_png(img, keep=True, name=name, meta=sp.strokes_meta(strokes, color, width))
        self.win.snack(tr("Firma guardada: la tienes en el menú Firma."), "success")

    def _new_signature(self):
        if self.doc is None:
            return
        self._close_panel()
        dlg = sp.SignatureDialog(self.window())
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            self._place_signature(dlg.result_path)

    def _place_signature(self, path):
        try:
            size = at.image_size(str(path))
        except Exception:
            self.win.snack(tr("No se pudo abrir esa firma."), "error")
            return
        self.begin_place_image(str(path), size, max_frac=0.22, what=tr("la firma"))

    def _delete_signature(self, path):
        if QMessageBox.question(self, tr("Borrar firma"), tr("¿Borrar esta firma guardada?"),
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            sp.delete_saved(path)
            self.win.snack(tr("Firma borrada."), "info")

    # ── Formas: rectángulo, elipse, línea, flecha ───────────────────────
    # ── Barra de dibujo: formas + color, relleno y grosor ───────────────
    def _build_shape_panel(self, root):
        self.shape_panel = QFrame()
        self.shape_panel.setObjectName("Card")
        self.shape_panel.setStyleSheet(
            "QFrame#Card QPushButton { padding:5px 9px; font-size:12px; }")
        fl = FlowLayout(self.shape_panel, margin=8, hspacing=6, vspacing=6)
        self._shape_tool_btns = {}
        for kind, label in self._SHAPE_TOOLS:
            icon_name = {"select": "select", "pen": "pen", "marker": "highlight", "rect": "rect", "ellipse": "ellipse",
                         "line": "line", "arrow": "arrow"}[kind]
            b = _btn(tr(label), icon_name, "Secondary", icon_color=TEXT)
            b.setCheckable(True)
            b.setToolTip(tr(label))
            b.clicked.connect(lambda _=False, k=kind: self._enter_shape(kind=k))
            fl.addWidget(b)
            self._shape_tool_btns[kind] = b
        self.sh_stroke_btn = QPushButton(); self.sh_fill_btn = QPushButton()
        for b, tip in ((self.sh_stroke_btn, tr("Color del borde / trazo")), (self.sh_fill_btn, tr("Color de relleno (rectángulo y elipse)"))):
            b.setObjectName("Secondary")
            b.setToolTip(tip)
            fl.addWidget(b)
        self.sh_stroke_btn.clicked.connect(lambda: self._shape_color_menu(self.sh_stroke_btn, False))
        self.sh_fill_btn.clicked.connect(lambda: self._shape_color_menu(self.sh_fill_btn, True))
        self.sh_width_combo = QComboBox()
        for w, label in self._WIDTH_LABELS:
            self.sh_width_combo.addItem(tr("Grosor: {label}", label=tr(label)), w)
        self.sh_width_combo.setToolTip(tr("Grosor de la línea"))
        self.sh_width_combo.activated.connect(lambda i: self._enter_shape(width=self.sh_width_combo.itemData(i)))
        fl.addWidget(self.sh_width_combo)
        self.sh_op_btn = QPushButton()
        self.sh_op_btn.setObjectName("Secondary")
        self.sh_op_btn.setToolTip(tr("Opacidad: total por defecto 100 %; opcionalmente otra para el trazo o el relleno"))
        self.sh_op_btn.clicked.connect(self._shape_opacity_menu)
        fl.addWidget(self.sh_op_btn)
        self.sh_head_combo = QComboBox()
        for name, label in at.HEAD_LABELS:
            self.sh_head_combo.addItem(label, name)
        self.sh_head_combo.setToolTip(tr("Forma de la punta de las flechas"))
        self.sh_head_combo.activated.connect(lambda i: self._set_shape_head(self.sh_head_combo.itemData(i)))
        fl.addWidget(self.sh_head_combo)
        self.shape_panel.hide()
        root.addWidget(self.shape_panel)

    def _shape_color_menu(self, anchor, fill: bool):
        ap = (lambda v: self._enter_shape(fill=v)) if fill else (lambda v: self._enter_shape(color=v))
        m = color_menu(self, self.editor_view, fill, ap)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _shape_opacity_menu(self):
        ev = self.editor_view
        so = ev.shape_stroke_op if ev.shape_stroke_op is not None else ev.shape_opacity
        fo = ev.shape_fill_op if ev.shape_fill_op is not None else ev.shape_opacity
        m = opacity_menu(self, self._set_shape_opacity, has_fill=True, current=(so, fo))
        m.exec(self.sh_op_btn.mapToGlobal(self.sh_op_btn.rect().bottomLeft()))

    def _set_shape_opacity(self, part, v):
        ev = self.editor_view
        v = float(v)
        if part == "total":
            ev.shape_opacity, ev.shape_stroke_op, ev.shape_fill_op = v, None, None
        elif part == "stroke":
            ev.shape_stroke_op = v
        else:
            ev.shape_fill_op = v
        if ev._ss_sel and ev.mode == "shape":
            kw = {"total": "opacity", "stroke": "stroke_op", "fill": "fill_op"}[part]
            ev.restyle_selection(**{kw: v})
        self._sync_shape_panel()

    def _set_shape_head(self, name):
        ev = self.editor_view
        ev.shape_head = name
        if ev._ss_sel and ev.mode == "shape":
            ev.restyle_selection(head=name)

    def _sync_shape_panel(self):
        ev = self.editor_view
        for kind, b in self._shape_tool_btns.items():
            b.setChecked(kind == ev.shape_kind)
        self.sh_stroke_btn.setIcon(SelectionBar._swatch(at.rgb_of(ev.shape_color)))
        self.sh_stroke_btn.setText("  Borde")
        self.sh_fill_btn.setIcon(SelectionBar._swatch(at.rgb_of(ev.shape_fill) if ev.shape_fill else None))
        so = ev.shape_stroke_op if ev.shape_stroke_op is not None else ev.shape_opacity
        fo = ev.shape_fill_op if ev.shape_fill_op is not None else ev.shape_opacity
        self.sh_op_btn.setText("  Opacidad %d %%" % round(so * 100) if abs(so - fo) < 0.01
                               else "  Opacidad %d/%d %%" % (round(so * 100), round(fo * 100)))
        i = self.sh_head_combo.findData(ev.shape_head)
        if i >= 0:
            self.sh_head_combo.setCurrentIndex(i)
        self.sh_fill_btn.setText("  Relleno")
        i = self.sh_width_combo.findData(ev.shape_width)
        if i >= 0:
            self.sh_width_combo.setCurrentIndex(i)

    def _toggle_shape_panel(self, checked: bool = False):
        if self.editor_view.mode == "shape":
            self.editor_view.set_mode("edit")
            return
        if self.editor_view.shape_kind == "select":
            self.editor_view.shape_kind = "rect"
        self._enter_shape()

    def _on_shape_kind_changed(self, kind: str):
        self._sync_shape_panel()

    _SHAPE_TOOLS = (("select", "Seleccionar / mover"), ("pen", "Lápiz libre"), ("marker", "Rotulador libre"),
                    ("rect", "Rectángulo"),
                    ("ellipse", "Elipse"), ("line", "Línea"), ("arrow", "Flecha"))
    _WIDTH_LABELS = ((1.0, "Fino"), (2.0, "Normal"), (4.0, "Grueso"), (7.0, "Muy grueso"))

    def _enter_shape(self, kind=None, color=None, width=None, fill=None):
        ev = self.editor_view
        sel = ev._ss_sel if ev.mode == "shape" else None
        if kind:
            ev.shape_kind = kind
        if color:
            ev.shape_color = color
        if width:
            ev.shape_width = width
        if fill is not None:
            ev.shape_fill = fill or None
        self._close_panel()
        ev.set_mode("shape")
        ev.viewport().setCursor(Qt.ArrowCursor if ev.shape_kind == "select" else Qt.CrossCursor)
        self._sync_shape_panel()
        if sel and not kind and (color or width or fill is not None):
            ev._ss_select(sel["page"], sel["desc"])              # la selección sigue; cambia su estilo
            ev.restyle_selection(color, width, fill)
            return
        if ev.shape_kind == "select":
            self.win.snack(tr("Clic en una forma o trazo para seleccionarlo: arrastra para mover, puntos blancos para "
                           "cambiar el tamaño, Ctrl+D duplica, Supr borra."), "info")
            return
        if ev.shape_kind in ("pen", "marker"):
            self.win.snack(tr("Dibuja con el ratón. Para mover, escalar o duplicar un trazo: «Seleccionar / mover»."), "info")
        else:
            self.win.snack(tr("Arrastra para dibujar (Mayús para proporción exacta). Para mover, escalar o duplicar "
                           "una forma ya dibujada, elige «Seleccionar / mover» o haz clic en su borde."), "info")

    # ── Marcar texto: resaltar, subrayar, tachar ────────────────────────
    _MARK_TOOLS = (("highlight", "Resaltar", "highlight"), ("underline", "Subrayar", "underline"),
                   ("strike", "Tachar", "strike"), ("erase", "Quitar marca", "eraser"))

    def _fill_annot_menu(self):
        m = self.annot_menu
        m.clear()
        ev = self.editor_view
        active = ev.mode == "markup"
        for kind, label, icon_name in self._MARK_TOOLS:
            act = m.addAction(ic.icon(icon_name, TEXT, 17), tr(label))
            act.setCheckable(True)
            act.setChecked(active and ev.markup_kind == kind)
            act.triggered.connect(lambda _=False, k=kind: self._enter_markup(k))
        m.addSeparator()
        sub = m.addMenu(tr("Color"))
        cur = ev.markup_color or at.DEFAULT_COLOR.get(ev.markup_kind, "amarillo")
        for name, rgb in at.COLORS.items():
            pm = QPixmap(14, 14)
            pm.fill(QColor(*(int(c * 255) for c in rgb)))
            act = sub.addAction(QIcon(pm), name.capitalize())
            act.setCheckable(True)
            act.setChecked(name == cur)
            act.triggered.connect(lambda _=False, n=name: self._set_markup_color(n))
        if active:
            m.addSeparator()
            m.addAction(tr("Terminar de marcar"), lambda: ev.set_mode("edit"))

    def _enter_markup(self, kind: str):
        ev = self.editor_view
        if kind != ev.markup_kind:
            ev.markup_color = None             # cada herramienta vuelve a su color normal
        ev.markup_kind = kind
        self._close_panel()
        ev.set_mode("markup")
        label = {"highlight": "Resaltar", "underline": "Subrayar", "strike": "Tachar", "erase": "Quitar marca"}[kind]
        self.annot_btn.setText("  " + tr(label))
        self.win.snack(tr("Haz clic sobre una marca para quitarla.") if kind == "erase"
                       else tr("Arrastra sobre el texto (o haz clic en una palabra) para marcarlo."), "info")

    def _set_markup_color(self, name: str):
        ev = self.editor_view
        ev.markup_color = name
        if ev.markup_kind == "erase":
            ev.markup_kind = "highlight"
        self._enter_markup(ev.markup_kind)

    def _toggle_manual(self, checked: bool):
        ev = self.editor_view
        ev.manual = checked
        self.manual_btn.setText(tr("Manual") if checked else tr("Automático"))
        ev.reload_preserving_scroll()
        self.win.snack(tr("Modo manual: cada línea se edita por separado y no se mueve nada más.") if checked
                       else tr("Modo automático: párrafos, listas, cabecera, pie y numeración."), "info")

    def _mark_dirty(self):
        self.dirty = True
        self._schedule_draft()

    # ── Borrador automático (carpeta temporal) ─────────────────────────
    def _schedule_draft(self):
        t = getattr(self, "_draft_timer", None)
        if t is None:
            t = self._draft_timer = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(2500)
            t.timeout.connect(self._write_draft)
        t.start()

    def _write_draft(self):
        if self.doc is None:
            return
        if self.dirty:
            dr.save(self.doc, (self.current_file or {}).get("name", "documento.pdf"))
        else:
            dr.clear()

    def _restart_with_doc(self):
        """Reinicia la aplicación y reabre este mismo documento (con sus cambios sin guardar)."""
        if self.doc is None:
            return
        if self.editor_view._editor is not None:
            self.editor_view._close_inline_editor(commit=True)
        name = (self.current_file or {}).get("name", "documento.pdf")
        if not dr.save(self.doc, name, restart=True, dirty=self.dirty):
            self.win.snack(tr("No se pudo guardar el borrador para reiniciar."), "error")
            return
        from PySide6.QtCore import QProcess
        args = [os.path.abspath(sys.argv[0])] if not getattr(sys, "frozen", False) else []
        if QProcess.startDetached(sys.executable, args, os.getcwd()):
            self.win._force_quit = True
            self.win.close()
        else:
            self.win.snack(tr("No se pudo reiniciar la aplicación; ábrela tú y te preguntará si continúas."), "error")

    def _warn_font_missing(self, family: str):
        if family in self._warned_fonts:
            return
        self._warned_fonts.add(family)
        fb = self.editor_view._FALLBACK_FONT
        self.win.snack(
            tr("La fuente «{family}» no está instalada: se ha usado «{fb}» en su lugar. Si quieres usar «{family}», "
            "instálala en Windows (doble clic en su archivo → Instalar) y reabre la aplicación.",
            family=family, fb=fb), "info")

    def _maybe_prompt_save(self):
        if self.dirty and self.doc is not None:
            resp = QMessageBox.question(
                self, tr("Cambios sin guardar"),
                tr("Tienes cambios sin guardar en este PDF. ¿Guardarlos antes de cambiar de archivo?"),
                QMessageBox.Yes | QMessageBox.No)
            if resp == QMessageBox.Yes:
                self._save_changes()

    def _save_changes(self):
        if not self.doc or not self.current_file:
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        out = be.save_edit_session(self.doc, self.current_file["path"])
        if out:
            idx = self.file_combo.currentIndex()
            new_f = self.win.replace_file(self.current_file, out)
            self.current_file = new_f
            self.file_combo.blockSignals(True)
            self.file_combo.setItemText(idx, new_f["name"])
            self.file_combo.blockSignals(False)
            self.dirty = False
            dr.clear()
            self.win.snack(tr("✓ Guardado: {name} — "
                            "listo para guardar una copia o seguir con otra herramienta", name=Path(out).name), "success")
        else:
            self.win.snack(tr("No se pudo guardar"), "error")

    # ── Censurar texto (global, por búsqueda) ───────────────────────────
    def _do_censor(self):
        texto = self.censor_field.text().strip()
        if not texto:
            self.win.snack(tr("Escribe el texto a censurar"), "error"); return
        f = self._selected_file()
        if not f:
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        self.win.snack(tr("Censurando…"), "info")

        def _run():
            out = be.censor_text_in_pdf(f["path"], texto)

            def done():                                           # esto sí toca la pantalla: en su hilo
                if out:
                    self.win.record_step("censor", {"texto": texto})
                    self.win.replace_file(f, out)
                    self.win.snack(tr("✓ Censurado (sin vuelta atrás): {name} — "
                                    "listo para guardar o seguir con otra herramienta", name=Path(out).name), "success")
                    self.populate()
                    self._close_panel()
                else:
                    self.win.snack(tr("No se encontró ese texto en el PDF"), "error")
            on_gui(done)

        run_bg(_run)

    def _on_replace_requested(self, text: str):
        """«Reemplazar…» desde el clic derecho: abre el panel con el texto ya puesto, solo falta escribir el nuevo."""
        self.editor_view._close_inline_editor(commit=True)
        if self._active_panel != "find":
            self._toggle_panel("find")
        self.buscar_field.setText(text.strip())
        self.reemplazar_field.clear()
        self.reemplazar_field.setFocus()
        self.win.snack(tr("Escribe el texto nuevo y pulsa Reemplazar."), "info")

    def _do_find_replace(self):
        buscar = self.buscar_field.text().strip()
        reemplazar = self.reemplazar_field.text()
        if not buscar:
            self.win.snack(tr("Escribe el texto a buscar"), "error"); return
        if self.doc is None:
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        ev = self.editor_view
        ev._close_inline_editor(commit=True)

        def ask(page, para, new_runs):
            # Con una sola página no se pueden deducir cabecera y pie: si el cambio crea una página, se pregunta antes.
            if ev.hf is None and len(self.doc) < 2 and not ev.manual:
                added = be.paragraph_edit_adds_pages(self.doc, page, para, "".join(r["text"] for r in new_runs),
                                                     para["size"], para["color"], runs=[dict(r) for r in new_runs])
                if added and not ev.ask_header_footer(
                        page, tr("El texto nuevo no cabe y se creará una página. Marca la cabecera y el pie para no "
                              "tocarlos y decide cómo se repiten. Si cancelas, no se reemplaza nada más.")):
                    return False
            return True

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = be.replace_text_in_doc(self.doc, buscar, reemplazar, settings=ev.hf, manual=ev.manual,
                                         case=self.case_cb.isChecked(), before=self._before_mutate, ask_pages=ask)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.win.snack(tr("No se pudo reemplazar: {e}", e=e), "error")
            return
        QApplication.restoreOverrideCursor()
        if res["cancelled"]:
            if res["count"]:
                self._do_undo()                                  # no se deja a medias
            self.win.snack(tr("Cancelado: no se ha reemplazado nada."), "info")
            return
        if not res["count"]:
            self.win.snack(tr("No se encontró ese texto en el PDF."), "error")
            return
        self._mark_dirty()
        self.win.record_step("find_replace", {"buscar": buscar, "reemplazar": reemplazar})
        ev.reload_preserving_scroll()
        self.win.snack(tr("✓ {n} cambio{s1} en {np} página{s2}. Ctrl+Z lo deshace.",
                       n=res['count'], s1='s' if res['count'] != 1 else '',
                       np=len(res['pages']), s2='s' if len(res['pages']) != 1 else ''), "success")
