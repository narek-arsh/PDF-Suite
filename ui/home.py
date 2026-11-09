# -*- coding: utf-8 -*-
"""Portada: lista de archivos y barra lateral de herramientas."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
)

import backend as be
import icons as ic
from PySide6.QtWidgets import QScrollArea
import pdf_tools as ptl
import workflows as wf
import theme
from theme import SURFACE, TEXT, TEXT_SOFT, ACCENT, ACCENT2, ACCENT3, BORDER_STRONG, DANGER
import i18n
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import ICON_DARK, _btn, _save_btn, add_shadow, glow, on_gui, provecto_logo_pixmap, run_bg
from ui.feedback import FeedbackDialog
from ui.widgets import DropArea, FileListWidget


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: HOME
# ══════════════════════════════════════════════════════════════════════════
class HomePage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.side = QFrame()
        self.side.setObjectName("Card")
        self.side.setFixedWidth(256)
        self._build_sidebar()
        root.addWidget(self.side)

        main = QWidget()
        root.addWidget(main, 1)
        col = QVBoxLayout(main)
        col.setContentsMargins(24, 20, 24, 20)
        col.setSpacing(12)

        url_row = QHBoxLayout()
        self.url_field = QLineEdit()
        self.url_field.setPlaceholderText(tr("Pega un enlace a un PDF y pulsa Enter (o arrastra archivos aquí)"))
        self.url_field.returnPressed.connect(self._load_from_url)
        attach_btn = _btn(tr("Añadir archivos"), "clip")
        attach_btn.setToolTip(tr("Subir PDFs o fotos desde el ordenador"))
        attach_btn.clicked.connect(self._browse_files)
        url_row.addWidget(self.url_field, 1)
        url_row.addWidget(attach_btn)
        col.addLayout(url_row)

        self.hint = QLabel()
        self.hint.setObjectName("Hint")
        col.addWidget(self.hint)

        self.drop_area = DropArea(self._handle_files_dropped)
        self.file_list = FileListWidget(
            on_files_dropped=self._handle_files_dropped,
            on_order_changed=self.win.reorder_files,
            on_remove=self.win.remove_file_obj,
            on_open=self.win.open_in_viewer,
        )
        col.addWidget(self.drop_area, 1)
        col.addWidget(self.file_list, 1)

        self.steps_bar = QFrame()
        self.steps_bar.setObjectName("Card")
        sb = QHBoxLayout(self.steps_bar)
        sb.setContentsMargins(14, 8, 10, 8)
        self.steps_lbl = QLabel()
        self.steps_lbl.setObjectName("Hint")
        self.steps_lbl.setWordWrap(True)
        self.save_wf_btn = _btn(tr("Guardar como workflow"), "bolt", "Primary")
        save_wf_btn = self.save_wf_btn
        save_wf_btn.clicked.connect(self.win.save_session_as_workflow)
        self.append_wf_btn = _btn(tr("Añadir al workflow"), "bolt", "Primary")
        self.append_wf_btn.clicked.connect(self.win.append_session_to_saved)
        self.append_wf_btn.setVisible(False)
        reset_btn = _btn(tr("Descartar pasos"), None, "Flat")
        reset_btn.setToolTip(tr("Borra la lista de pasos anotados para empezar otro workflow "
                             "desde cero. No deshace nada en tus archivos."))
        reset_btn.clicked.connect(self.win.clear_steps)
        sb.addWidget(self.steps_lbl, 1)
        sb.addWidget(self.append_wf_btn)
        sb.addWidget(save_wf_btn)
        sb.addWidget(reset_btn)
        self.steps_bar.setVisible(False)
        col.addWidget(self.steps_bar)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("Card")
        add_shadow(self.action_bar)
        self._build_action_bar()
        col.addWidget(self.action_bar)

        self.refresh_file_list()

    def refresh_steps_bar(self):
        steps = self.win.session_steps
        self.steps_bar.setVisible(bool(steps))
        if not steps:
            return
        win = self.win
        saved = win.saved_upto == len(steps)
        pending = bool(win.saved_id) and len(steps) > win.saved_upto
        self.save_wf_btn.setVisible(not saved)
        self.save_wf_btn.setText(("  " + tr("Guardar como nuevo")) if pending else ("  " + tr("Guardar como workflow")))
        self.save_wf_btn.setObjectName("Secondary" if pending else "Primary")
        self.save_wf_btn.setIcon(ic.icon("bolt", ACCENT if pending else ICON_DARK, 17))
        self.save_wf_btn.style().unpolish(self.save_wf_btn)
        self.save_wf_btn.style().polish(self.save_wf_btn)
        self.append_wf_btn.setVisible(pending)
        if pending:
            name = win.saved_name if len(win.saved_name) <= 22 else win.saved_name[:21] + "…"
            self.append_wf_btn.setText(tr("  Añadir a «{name}»", name=name))
            self.steps_lbl.setText(f"«{win.saved_name}» " + tr("guardado  ·  pasos nuevos:  ")
                                   + wf.summarize(steps[win.saved_upto:]))
        elif saved:
            self.steps_lbl.setText(tr("✓ Guardado como «{name}»  ·  ", name=win.saved_name) + wf.summarize(steps))
        else:
            self.steps_lbl.setText(tr("Pasos aplicados:  ") + wf.summarize(steps))

    def _handle_files_dropped(self, paths: list[str]):
        self.win.add_files_any(paths)

    def _build_search_box(self, lay):
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText(tr("Buscar una función… (p. ej. «firmar», «formulario», «numerar»)"))
        self.search_field.textChanged.connect(self._do_search)
        lay.addWidget(self.search_field)
        self.search_results = QListWidget()
        self.search_results.setObjectName("SearchResults")
        self.search_results.setMaximumHeight(220)
        self.search_results.setVisible(False)
        self.search_results.itemClicked.connect(self._run_search_result)
        self.search_results.setStyleSheet(
            f"QListWidget#SearchResults {{ background:{SURFACE}; border:1px solid {BORDER_STRONG}; "
            f"border-radius:10px; padding:2px; }}"
            f"QListWidget#SearchResults::item {{ border-radius:7px; padding:7px 8px; color:{TEXT}; }}"
            f"QListWidget#SearchResults::item:hover {{ background: rgba(243,241,228,0.08); }}"
            f"QListWidget#SearchResults::item:selected {{ background: rgba(192,130,88,0.28); color:{TEXT}; }}")
        lay.addWidget(self.search_results)
        lay.addSpacing(8)

    def _do_search(self, text: str):
        text = text.strip().lower()
        self.search_results.clear()
        if not text:
            self.search_results.setVisible(False)
            self.nav.setVisible(True)
            return
        seen_labels = set()
        matches = []
        for label, icon_name, slot, haystack in self._search_entries:
            if text in haystack and label not in seen_labels:
                seen_labels.add(label)
                matches.append((label, icon_name, slot))
        self.nav.setVisible(False)
        self.search_results.setVisible(True)
        if not matches:
            it = QListWidgetItem(tr("Sin resultados."))
            it.setFlags(Qt.NoItemFlags)
            self.search_results.addItem(it)
            return
        for label, icon_name, slot in matches:
            it = QListWidgetItem(ic.icon(icon_name, TEXT, 17), label)
            it.setData(Qt.UserRole, slot)
            self.search_results.addItem(it)

    def _run_search_result(self, item: QListWidgetItem):
        slot = item.data(Qt.UserRole)
        if not slot:
            return
        self.search_field.blockSignals(True)
        self.search_field.clear()
        self.search_field.blockSignals(False)
        self.search_results.setVisible(False)
        self.nav.setVisible(True)
        slot()

    def _build_sidebar(self):
        lay = QVBoxLayout(self.side)
        lay.setContentsMargins(16, 18, 16, 16)
        lay.setSpacing(4)

        header = QHBoxLayout()
        badge = QLabel()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignCenter)
        logo_pix = provecto_logo_pixmap(36)
        if logo_pix is not None:
            badge.setPixmap(logo_pix)
        else:
            badge.setObjectName("Badge")
            badge.setText("P")
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("PDF Manager")
        title.setObjectName("Header")
        title.setStyleSheet("font-size:15px;")
        subtitle = QLabel('<a href="https://provecto.app" style="color:inherit; text-decoration:none;">by Provecto</a>')
        subtitle.setObjectName("SubHeader")
        subtitle.setOpenExternalLinks(True)
        subtitle.setCursor(Qt.PointingHandCursor)
        subtitle.setToolTip(tr("Abrir provecto.app"))
        glow(badge, ACCENT, blur=22, alpha=130)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addWidget(badge)
        header.addSpacing(10)
        header.addLayout(title_col, 1)
        lay.addLayout(header)
        lay.addSpacing(8)

        toolbar_row = QHBoxLayout()
        toolbar_row.addStretch(1)
        fb_btn = QPushButton()
        fb_btn.setObjectName("Flat")
        fb_btn.setFixedSize(28, 28)
        fb_btn.setStyleSheet("padding:0;")
        fb_btn.setIcon(ic.icon("info", TEXT_SOFT, 16))
        fb_btn.setToolTip(tr("Enviar comentarios"))
        fb_btn.clicked.connect(lambda: FeedbackDialog(self.win).exec())
        toolbar_row.addWidget(fb_btn)
        toolbar_row.addSpacing(4)
        lang_btn = QPushButton(i18n.LANG.upper())
        lang_btn.setObjectName("Flat")
        lang_btn.setFixedSize(32, 28)
        lang_btn.setStyleSheet("padding:0;font-size:11px;")
        lang_btn.setToolTip(tr("Idioma") + ": " + i18n.LANG_NAMES.get(i18n.LANG, i18n.LANG))
        lang_btn.clicked.connect(self.win.cycle_language)
        toolbar_row.addWidget(lang_btn)
        toolbar_row.addSpacing(4)
        theme_btn = QPushButton()
        theme_btn.setObjectName("Flat")
        theme_btn.setFixedSize(28, 28)
        theme_btn.setStyleSheet("padding:0;")
        theme_btn.setIcon(ic.icon("moon", TEXT_SOFT, 16))
        theme_btn.setToolTip(tr("Cambiar a modo claro") if theme.MODE == "dark" else tr("Cambiar a modo oscuro"))
        theme_btn.clicked.connect(self.win.toggle_theme)
        toolbar_row.addWidget(theme_btn)
        lay.addLayout(toolbar_row)
        lay.addSpacing(8)

        self._search_entries: list = []   # (etiqueta, iconos, slot, texto_para_buscar) de TODO lo buscable
        self._build_search_box(lay)

        self.nav = QWidget()
        nav = QVBoxLayout(self.nav)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(4)
        w = self.win

        GROUP_COLORS = {
            "Combinar y dividir": ACCENT, "Comparar": ACCENT2, "Editar": ACCENT,
            "Formato": ACCENT3, "Optimizar": ACCENT2, "Texto y conversión": ACCENT3,
            "Más": ACCENT,
        }

        def group(text, items):
            g = QLabel(tr(text).upper())
            g.setObjectName("Hint")
            g.setContentsMargins(6, 10, 0, 2)
            nav.addWidget(g)
            dot_color = GROUP_COLORS.get(text, ACCENT)
            for item in items:
                label_es, icon_name, slot = item[0], item[1], item[2]
                keywords = item[3] if len(item) > 3 else ""
                label = tr(label_es)
                b = _btn(label, icon_name, "Flat", icon_color=dot_color)
                b.setStyleSheet("text-align:left;padding:8px 10px;")
                b.clicked.connect(lambda _=False, s=slot: s())
                nav.addWidget(b)
                self._search_entries.append(
                    (label, icon_name, slot, (label_es + " " + label + " " + keywords).lower()))

        # Cosas que viven dentro del Editor, sin botón propio en el menú: solo se encuentran buscando.
        for label_es, icon_name, keywords in (
            ("Firmar", "signature", "firma firmar rúbrica sign"),
            ("Formulario", "form", "formulario rellenar campos form"),
            ("Sello", "stamp", "sello aprobado recibido confidencial stamp"),
            ("Resaltar texto", "highlight", "resaltar subrayar tachar marcar highlight"),
            ("Dibujar", "pen", "dibujar lápiz rotulador rectángulo elipse línea flecha"),
            ("Enlace", "link", "enlace link hipervínculo url"),
            ("Añadir texto", "text_add", "añadir texto nuevo escribir"),
            ("Censurar", "lock", "censurar tachar ocultar negro redact"),
            ("Reemplazar texto", "swap", "reemplazar buscar y reemplazar cambiar texto"),
            ("Copiar texto o tabla", "copy", "copiar extraer tabla excel"),
        ):
            label = tr(label_es)
            self._search_entries.append(
                (label, icon_name, w.open_edit_view, (label_es + " " + label + " " + keywords).lower()))

        group("Combinar y dividir", [("Unir", "link", w.do_merge_standalone, "combinar fusionar merge juntar"),
                                     ("Dividir", "scissors", w.open_split_view, "separar cortar split"),
                                     ("Organizar páginas", "grid", w.open_organize_view, "ordenar reordenar mover girar eliminar páginas")])
        group("Comparar", [("Comparar PDFs", "swap", w.open_compare_view, "diferencias diff versiones"),
                           ("Numerar páginas", "text_add", lambda: w.open_tool("Numerar páginas"), "numeración folio paginar"),
                           ("Analizar PDF", "info", lambda: w.open_tool("Analizar PDF"), "información propiedades versión fuentes"),
                           ("Verificar firmas", "signature", lambda: w.open_tool("Verificar firmas"), "firma digital certificado validar")])
        group("Editar", [("Editor", "pencil", w.open_edit_view, "editar texto imágenes páginas"),
                         ("Metadatos", "info", w.open_metadata_view, "título autor propiedades"),
                         ("Ajuste de imagen", "droplet", w.do_ajuste_standalone, "blanco y negro escanear contraste brillo")])
        group("Formato", [("Tamaño y márgenes", "resize", w.open_size_margins_view, "redimensionar a4 carta página márgenes"),
                          ("Varias por hoja", "nup", w.open_nup_view, "n-up imposición varias páginas por hoja")])
        group("Optimizar", [("Comprimir", "download", lambda: w.open_tool("Comprimir"), "reducir peso tamaño"),
                            ("Proteger", "lock", lambda: w.open_tool("Proteger"), "contraseña bloquear desbloquear cifrar password permisos"),
                            ("Marca de agua", "stamp", lambda: w.open_tool("Marca de agua"), "watermark filigrana"),
                            ("Invertir colores", "droplet", lambda: w.open_tool("Invertir colores"), "modo oscuro dark negativo"),
                            ("Aplanar y reparar", "wrench", lambda: w.open_tool("Aplanar y reparar"), "flatten repair dañado corrupto")])
        group("Texto y conversión", [("OCR", "pencil", lambda: w.open_tool("OCR"), "reconocer texto escaneado buscable"),
                                     ("Convertir a PDF", "document", lambda: w.open_tool("Convertir a PDF"), "word excel powerpoint imágenes html a pdf"),
                                     ("Convertir desde PDF", "download", lambda: w.open_tool("Convertir desde PDF"), "pdf a word excel imágenes texto html")])
        group("Más", [("Workflows", "bolt", w.open_workflows_view, "automatizar macro pasos plantilla")])
        sc = QScrollArea()                                       # con ventanas bajas, la lista de herramientas se desplaza
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        sc.setWidget(self.nav)
        lay.addWidget(sc, 1)

    def _build_action_bar(self):
        lay = QHBoxLayout(self.action_bar)
        lay.setContentsMargins(14, 10, 14, 10)
        clear_btn = _btn(tr("Limpiar todo"), "trash", "Danger", icon_color=DANGER)
        clear_btn.clicked.connect(self.win.clear_all)
        save_btn = _btn(tr("Guardar como…"), "download")
        save_btn.clicked.connect(self.win.do_save_as_copy)
        self.merge_btn = _save_btn(tr("Unir"), "link", "Primary")
        self.merge_btn.clicked.connect(self.win.do_merge_standalone)
        lay.addWidget(clear_btn)
        lay.addStretch(1)
        lay.addWidget(save_btn)
        lay.addWidget(self.merge_btn)

    def _browse_files(self):
        exts = " ".join("*" + e for e in sorted(ptl.accepted_extensions()))
        photos = " ".join("*" + e for e in sorted(ptl.IMAGE_EXT))
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("Elegir PDFs o fotos"), "",
            f"{tr('PDF y fotos ({exts})', exts=exts)};;PDF (*.pdf);;"
            f"{tr('Fotos ({photos})', photos=photos)};;{tr('Todos los archivos (*.*)')}")
        self.win.add_files_any(paths)

    def _load_from_url(self):
        url = self.url_field.text().strip()
        if not url:
            return
        self.win.snack(tr("Descargando PDF…"), "info")

        def _dl():
            p = be.download_pdf_from_url(url)
            fn = url.split("/")[-1].split("?")[0] or "descargado.pdf"
            if not fn.lower().endswith(".pdf"):
                fn += ".pdf"
            if p:
                on_gui(lambda: self.win.add_file(p, fn))
            else:
                on_gui(lambda: self.win.snack(tr("No se pudo descargar el PDF"), "error"))

        run_bg(_dl)
        self.url_field.clear()

    def refresh_file_list(self):
        files = self.win.uploaded_files
        self.file_list.set_items(files)
        has_files = len(files) >= 1
        self.action_bar.setEnabled(has_files)
        n = len(files)
        pages = sum(f.get("pages", 0) for f in files)
        word_file = tr("archivo")
        word_page = tr("página")
        self.hint.setText(
            (f"{n} {word_file}{'s' if n != 1 else ''} · {pages} {word_page}{'s' if pages != 1 else ''} · "
             + tr("arrastra las tarjetas para ordenarlas")) if has_files
            else tr("Arrastra archivos o pega un enlace para empezar"))
        self.merge_btn.setText(tr("  Unir los {n} archivos", n=n) if n > 1 else ("  " + tr("Unir")))
        self.merge_btn.setEnabled(n > 1)
        self.drop_area.setVisible(not has_files)
        self.file_list.setVisible(has_files)
