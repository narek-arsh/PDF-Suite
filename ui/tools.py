# -*- coding: utf-8 -*-
"""Pantalla Herramientas: comprimir, proteger, marca de agua, reparar, convertir y OCR."""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon, QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QFrame,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QSpinBox,
    QDoubleSpinBox,
    QSlider,
    QDialog,
    QMessageBox,
    QAbstractItemView,
    QMenu,
    QSizePolicy,
    QTabWidget,
    QProgressDialog,
    QColorDialog,
    QProgressBar,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

from PySide6.QtWidgets import QPlainTextEdit, QScrollArea
import pdf_tools as ptl
import photo_fix as pf
from theme import TEXT, TEXT_SOFT
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import ICON_DARK, _ToolJob, _btn, _human_size, ask_scope
from ui.ocr import OcrPagesPanel, OcrReviewDialog
from ui.widgets import BackHeader


class ToolPreview(QFrame):
    """Vista previa de la página del archivo elegido, con ‹ › para recorrerlas. Una herramienta puede ponerle un
    «hook» que transforma la página antes de mostrarla (la marca de agua, por ejemplo)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self._path, self._pw, self._n, self._i = "", "", 0, 0
        self.hook = None                                      # hook(ruta de un PDF de 1 página, nº de página) -> ruta | None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._render)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        nav = QHBoxLayout()
        self.prev_b = _btn("‹", None, "Flat")
        self.prev_b.setFixedWidth(34)
        self.next_b = _btn("›", None, "Flat")
        self.next_b.setFixedWidth(34)
        self.prev_b.clicked.connect(lambda: self.goto(self._i - 1))
        self.next_b.clicked.connect(lambda: self.goto(self._i + 1))
        self.lbl = QLabel("")
        self.lbl.setObjectName("Hint")
        self.lbl.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.prev_b)
        nav.addWidget(self.lbl, 1)
        nav.addWidget(self.next_b)
        lay.addLayout(nav)
        self.view = QLabel("")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(240, 300)
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        lay.addWidget(self.view, 1)

    def set_file(self, f: dict | None, password: str = ""):
        self._pw = password
        if not f or f.get("locked") and not password:
            self._path, self._n, self._i = "", 0, 0
            self._clear(tr("Sin vista previa") if not f else tr("🔒 Protegido con contraseña"))
            return
        if f["path"] != self._path:
            self._i = 0
        self._path = f["path"]
        try:
            doc = ptl._open(self._path, self._pw)
            self._n = len(doc)
            doc.close()
        except Exception:
            self._n = 0
            self._clear(tr("No se puede mostrar este archivo"))
            return
        self._i = min(self._i, max(0, self._n - 1))
        self.refresh()

    def _clear(self, text: str):
        self.view.setPixmap(QPixmap())
        self.view.setText(text)
        self.lbl.setText("")
        self.prev_b.setEnabled(False)
        self.next_b.setEnabled(False)

    def goto(self, i: int):
        if 0 <= i < self._n:
            self._i = i
            self.refresh()

    def refresh(self, delay: int = 0):
        """Vuelve a dibujar la página (con un pequeño retraso se agrupan los cambios seguidos, p. ej. al escribir)."""
        self._timer.start(delay)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._path:
            self.refresh(120)

    def _render(self):
        if not self._path or self._n == 0 or not self.isVisible():
            return
        import fitz as _fz
        try:
            doc = ptl._open(self._path, self._pw)
            try:
                page_doc, k, tmp = doc, self._i, None
                if self.hook is not None:
                    import tempfile
                    one = _fz.open()
                    one.insert_pdf(doc, from_page=self._i, to_page=self._i)
                    tmp = os.path.join(tempfile.mkdtemp(prefix="pdfm_prev_"), "p.pdf")
                    one.save(tmp)
                    one.close()
                    out = self.hook(tmp, self._i)
                    if out:
                        page_doc, k = ptl._open(out, ""), 0
                    else:
                        page_doc, k = ptl._open(tmp, ""), 0
                page = page_doc[k]
                z = min((self.view.width() - 8) / max(page.rect.width, 1), (self.view.height() - 8) / max(page.rect.height, 1))
                z = max(0.2, min(z, 3.0))
                pix = page.get_pixmap(matrix=_fz.Matrix(z, z), alpha=False)
                qi = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                if page_doc is not doc:
                    page_doc.close()
            finally:
                doc.close()
        except Exception:
            self._clear(tr("No se puede mostrar la página"))
            return
        self.view.setText("")
        self.view.setPixmap(QPixmap.fromImage(qi))
        self.lbl.setText(tr("Página {i} de {n}", i=self._i + 1, n=self._n))
        self.prev_b.setEnabled(self._i > 0)
        self.next_b.setEnabled(self._i < self._n - 1)


class _ConvList(QListWidget):
    """Lista de archivos a convertir: acepta soltar archivos y muestra una ayuda mientras está vacía."""
    def __init__(self, on_paths):
        super().__init__()
        self._on_paths = on_paths
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setStyleSheet("QListWidget { border: 1px dashed #767A56; border-radius: 10px; }")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        self._on_paths([u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()])

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(TEXT_SOFT))
            p.drawText(self.viewport().rect(), Qt.AlignCenter, tr("Arrastra aquí los archivos a convertir\no pulsa «Añadir archivos…»"))


class ToolsPage(QWidget):
    """Herramientas de archivo completo: comprimir, proteger, marca de agua, aplanar, reparar, convertir y OCR."""
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self._job = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        self.back = BackHeader(tr("Herramientas"), lambda: win.go_home())
        root.addWidget(self.back)

        self.file_row = QWidget()
        row = QHBoxLayout(self.file_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.file_picker_w = QWidget()
        pr = QHBoxLayout(self.file_picker_w)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.addWidget(QLabel(tr("Archivo:")))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._file_changed)
        pr.addWidget(self.file_combo, 1)
        row.addWidget(self.file_picker_w, 1)
        row.addWidget(QLabel(tr("Contraseña del PDF:")))
        self.pw_field = QLineEdit()
        self.pw_field.setEchoMode(QLineEdit.Password)
        self.pw_field.setPlaceholderText(tr("solo si lo necesita"))
        self.pw_field.setFixedWidth(170)
        row.addWidget(self.pw_field)
        self.pw_field.editingFinished.connect(lambda: self.preview.set_file(self._file(), self.pw_field.text()))
        root.addWidget(self.file_row)
        self.info = QLabel("")
        self.info.setObjectName("Hint")
        root.addWidget(self.info)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()                              # cada herramienta se elige en la barra lateral
        body.addWidget(self.tabs, 3)
        self.preview = ToolPreview()
        body.addWidget(self.preview, 2)
        root.addLayout(body, 1)
        self._build_compress()
        self._build_protect()
        self._build_watermark()
        self._build_numbering()
        self._build_invert()
        self._build_fix()
        self._build_convert()
        self._build_export()
        self._build_inspect()
        self._build_verify_sig()
        self._build_ocr()
        self._wm_timer_widgets()
        self._pn_timer_widgets()
        self._inv_timer_widgets()

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        root.addWidget(self.bar)

    # ── comunes ─────────────────────────────────────────────────────────
    def _tab(self, title: str, hint: str):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)
        h = QLabel(hint)
        h.setObjectName("Hint")
        h.setWordWrap(True)
        lay.addWidget(h)
        self.tabs.addTab(w, title)
        return lay

    TOOLS = ("Comprimir", "Proteger", "Marca de agua", "Numerar páginas", "Invertir colores", "Aplanar y reparar",
             "Convertir a PDF", "Convertir desde PDF", "Analizar PDF", "Verificar firmas", "OCR")
    WITH_PREVIEW = ("Comprimir", "Proteger", "Marca de agua", "Numerar páginas", "Invertir colores", "Aplanar y reparar")

    def show_tool(self, name: str):
        """Muestra una sola herramienta: título, opciones y, si la tiene, la vista previa del archivo."""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == name:
                self.tabs.setCurrentIndex(i)
        self.back.title_lbl.setText(tr(name))
        self.file_row.setVisible(name != "Convertir a PDF")
        self.file_picker_w.setVisible(len(self.win.uploaded_files) > 1)
        self.info.setVisible(name != "Convertir a PDF")
        self.preview.setVisible(name in self.WITH_PREVIEW)
        self.preview.hook = {"Marca de agua": self._wm_hook, "Numerar páginas": self._pn_hook,
                            "Invertir colores": self._inv_hook}.get(name)
        self.populate()
        self.preview.refresh()

    def populate(self):
        self.file_picker_w.setVisible(len(self.win.uploaded_files) > 1)
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(("🔒 " if f.get("locked") else "") + f["name"])
        self.file_combo.blockSignals(False)
        self._file_changed()
        self._refresh_ocr_langs()
        self.status.setText("")

    def _file(self):
        i = self.file_combo.currentIndex()
        return self.win.uploaded_files[i] if 0 <= i < len(self.win.uploaded_files) else None

    def _file_changed(self, *_):
        f = self._file()
        if not f:
            self.info.setText(tr("Añade un PDF en la pantalla principal para usar esta herramienta."))
            self.preview.set_file(None)
            return
        try:
            size = _human_size(os.path.getsize(f["path"]))
        except OSError:
            size = "?"
        self.info.setText(f"{size}" + (tr(" · tiene contraseña de apertura") if f.get("locked") else tr(" · {pages} pág.", pages=f['pages'])))
        self.compress_now.setText(tr("Peso actual: {size}", size=size))
        self.preview.set_file(f, self.pw_field.text())
        self._load_ocr_panel()

    def _need_file(self):
        f = self._file()
        if not f:
            self._say(tr("Añade primero un PDF en la pantalla principal."), "error")
        return f

    def _say(self, msg: str, kind: str = "info"):
        col = {"ok": "#92976C", "error": "#D47268", "info": TEXT_SOFT}[kind]
        self.status.setStyleSheet(f"color:{col};")
        self.status.setText(msg)

    def _run(self, fn, on_done, start_msg: str, unit: str = "página"):
        if self._job is not None and self._job.isRunning():
            return
        self._say(start_msg, "info")
        self.bar.setRange(0, 0)
        job = _ToolJob(fn)
        job.finished_ok.connect(lambda res: (self._finish(), on_done(res)))
        job.failed.connect(lambda msg: (self._finish(), self._say(msg, "error"), self.win.snack(msg, "error")))
        job.progress.connect(lambda i, n: self._progress(i, n, unit))
        self._job = job
        job.start()

    def _progress(self, i: int, n: int, unit: str = "página"):
        if n > 0:
            self.bar.setRange(0, n)
            self.bar.setValue(i)
            self.status.setText(tr("Procesando {unit} {i} de {n}…", unit=tr(unit), i=min(i + 1, n), n=n))

    # ── Elegir uno o todos los archivos subidos ──────────────────────────
    def _ask_scope(self):
        cur = self._file()
        return ask_scope(self, self.win, cur["name"] if cur else None)

    def _targets(self, scope: str) -> list:
        return list(self.win.uploaded_files) if scope == "all" else ([self._file()] if self._file() else [])

    def _run_for_files(self, targets: list, call, on_each, start_msg: str, label_ok: str = "hecho"):
        """call(path, password) -> resultado (o lanza ptl.ToolError, que se cuenta como fallo de ese archivo).
        on_each(archivo, resultado) -> (True, None) si se adoptó bien, o (False, nota) para un aviso sin error."""
        pw = self.pw_field.text()

        def job(cb):
            out = []
            for i, f in enumerate(targets):
                cb(i, len(targets))
                try:
                    out.append((f, call(f["path"], pw), None))
                except ptl.ToolError as e:
                    out.append((f, None, str(e)))
            cb(len(targets), max(len(targets), 1))
            return out

        def done(results):
            oks, notes, errs = [], [], []
            for f, r, err in results:
                if err:
                    errs.append((f, err))
                    continue
                ok, note = on_each(f, r)
                (oks if ok else notes).append((f, note))
            self.populate()
            bits = []
            if oks:
                bits.append(f"{len(oks)} {label_ok}" + ("s" if len(oks) != 1 else ""))
            if notes:
                bits.append("; ".join(f"{f['name']}: {n}" for f, n in notes[:5]))
            if errs:
                bits.append(tr("{n} con error: ", n=len(errs)) + " · ".join(f"{f['name']}: {e}" for f, e in errs[:5]))
            kind = "ok" if oks and not errs and not notes else ("error" if not oks and not notes else "info")
            msg = ("✓ " if kind == "ok" else ("✗ " if kind == "error" else "⚠ ")) + (" — ".join(bits) or tr("Sin cambios."))
            self._say(msg, kind)
            self.win.snack(msg, {"ok": "success", "error": "error", "info": "info"}[kind])

        self._run(job, done, start_msg, unit="archivo")

    def _finish(self):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)

    def _adopt(self, out: str, f: dict | None, msg: str):
        """El resultado sustituye al archivo en la lista (como las demás herramientas) y se avisa dónde está."""
        if f is not None and out:
            new_f = self.win.replace_file(f, out)
            self.populate()
            self.file_combo.setCurrentIndex(max(0, self.win.uploaded_files.index(new_f)))
        self._say(f"✓ {msg}  " + tr("Guardado en Descargas: {name}", name=Path(out).name), "ok")
        self.win.snack(f"✓ {msg}", "success")

    # ── Comprimir ───────────────────────────────────────────────────────
    def _build_compress(self):
        lay = self._tab("Comprimir", tr("Reduce el peso del PDF reescalando las imágenes grandes y limpiando lo que sobra. "
                                     "El texto no cambia."))
        self.compress_now = QLabel("")
        lay.addWidget(self.compress_now)
        self.level_group = QButtonGroup(self)
        for key, (label, _p) in ptl.COMPRESS_LEVELS.items():
            rb = QRadioButton(tr(label))
            rb.setProperty("level", key)
            self.level_group.addButton(rb)
            lay.addWidget(rb)
            if key == "medium":
                rb.setChecked(True)
        b = _btn(tr("Comprimir"), "download", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_compress)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)

    def _do_compress(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        level = self.level_group.checkedButton().property("level")

        def each(f, r):
            if not r["ok"]:
                return False, r["reason"]
            self.win.replace_file(f, r["out"])
            return True, None

        self._run_for_files(self._targets(scope), lambda path, pw: ptl.compress(path, level, pw), each,
                            tr("Comprimiendo…"), tr("comprimido"))

    # ── Proteger ────────────────────────────────────────────────────────
    def _build_protect(self):
        lay = self._tab("Proteger", tr("Bloquea el PDF con contraseña (cifrado AES-256) o quita la protección de uno que "
                                    "ya tengas. Si olvidas la contraseña, nadie podrá recuperarla: guárdala."))
        card = QFrame(); card.setObjectName("Card")
        c = QVBoxLayout(card)
        t = QLabel(tr("Bloquear"))
        t.setObjectName("SectionTitle")
        c.addWidget(t)
        self.lock_pw = QLineEdit(); self.lock_pw.setEchoMode(QLineEdit.Password)
        self.lock_pw.setPlaceholderText(tr("Contraseña para abrirlo (déjala vacía para solo limitar permisos)"))
        self.lock_pw2 = QLineEdit(); self.lock_pw2.setEchoMode(QLineEdit.Password)
        self.lock_pw2.setPlaceholderText(tr("Repite la contraseña"))
        self.lock_owner = QLineEdit(); self.lock_owner.setEchoMode(QLineEdit.Password)
        self.lock_owner.setPlaceholderText(tr("Contraseña de propietario para cambiar permisos (opcional)"))
        for w in (self.lock_pw, self.lock_pw2, self.lock_owner):
            c.addWidget(w)
        c.addWidget(QLabel(tr("Permitir a quien lo abra:")))
        perms = QHBoxLayout()
        self.perm_print = QCheckBox(tr("Imprimir")); self.perm_print.setChecked(True)
        self.perm_copy = QCheckBox(tr("Copiar texto"))
        self.perm_edit = QCheckBox(tr("Modificar"))
        self.perm_annot = QCheckBox(tr("Anotar y rellenar"))
        for w in (self.perm_print, self.perm_copy, self.perm_edit, self.perm_annot):
            perms.addWidget(w)
        perms.addStretch(1)
        c.addLayout(perms)
        b = _btn(tr("Bloquear"), "lock", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_lock)
        c.addWidget(b, 0, Qt.AlignLeft)
        lay.addWidget(card)
        card2 = QFrame(); card2.setObjectName("Card")
        c2 = QVBoxLayout(card2)
        t2 = QLabel(tr("Desbloquear"))
        t2.setObjectName("SectionTitle")
        c2.addWidget(t2)
        h2 = QLabel(tr("Escribe arriba la «Contraseña del PDF» si hace falta para abrirlo. Úsalo solo con documentos que "
                    "sean tuyos o que tengas permiso para modificar."))
        h2.setObjectName("Hint"); h2.setWordWrap(True)
        c2.addWidget(h2)
        b2 = _btn(tr("Quitar protección"), "check", "Secondary", icon_color=TEXT)
        b2.clicked.connect(self._do_unlock)
        c2.addWidget(b2, 0, Qt.AlignLeft)
        lay.addWidget(card2)
        lay.addStretch(1)

    def _do_lock(self):
        if not self._need_file():
            return
        pw, pw2 = self.lock_pw.text(), self.lock_pw2.text()
        if pw != pw2:
            self._say(tr("Las dos contraseñas no coinciden."), "error")
            return
        if pw and len(pw) < 4:
            self._say(tr("Usa una contraseña de al menos 4 caracteres."), "error")
            return
        scope = self._ask_scope()
        if not scope:
            return
        targets = self._targets(scope)
        already = [f for f in targets if f.get("locked")]
        targets = [f for f in targets if not f.get("locked")]
        owner, ap, ac, ae, aa = (self.lock_owner.text(), self.perm_print.isChecked(), self.perm_copy.isChecked(),
                                 self.perm_edit.isChecked(), self.perm_annot.isChecked())

        def each(f, out):
            f["locked"] = bool(pw)
            self.win.replace_file(f, out)
            return True, None

        def call(path, password):
            return ptl.lock(path, user_pw=pw, owner_pw=owner, allow_print=ap, allow_copy=ac, allow_edit=ae,
                            allow_annot=aa, password=password)
        self.lock_pw.clear(); self.lock_pw2.clear(); self.lock_owner.clear()
        if not targets:
            self._say(tr("Ya tenía(n) contraseña: desbloquéalo(s) primero."), "error")
            return
        self._run_for_files(targets, call, each, tr("Protegiendo…"), tr("protegido"))
        if already:
            self.win.snack(tr("{n} ya tenía(n) contraseña: no se han tocado.", n=len(already)), "info")

    def _do_unlock(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return

        def each(f, r):
            f["locked"] = False
            self.win.replace_file(f, r["out"])
            return True, None

        self._run_for_files(self._targets(scope), lambda path, pw: ptl.unlock(path, pw), each,
                            tr("Quitando protección…"), tr("desprotegido"))

    # ── Marca de agua ───────────────────────────────────────────────────
    def _build_watermark(self):
        lay = self._tab("Marca de agua", tr("Añade un texto o una imagen detrás del contenido de las páginas, con "
                                         "transparencia. No tapa nada. Los cambios solo se ven en la vista previa: "
                                         "no se guarda nada hasta pulsar «Añadir marca de agua»."))
        self.wm_text_rb = QRadioButton(tr("Texto")); self.wm_text_rb.setChecked(True)
        self.wm_img_rb = QRadioButton(tr("Imagen"))
        g = QButtonGroup(self); g.addButton(self.wm_text_rb); g.addButton(self.wm_img_rb)
        r1 = QHBoxLayout()
        r1.addWidget(self.wm_text_rb)
        self.wm_text = QLineEdit(tr("CONFIDENCIAL"))
        r1.addWidget(self.wm_text, 1)
        lay.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(self.wm_img_rb)
        self.wm_img_path = QLineEdit(); self.wm_img_path.setReadOnly(True)
        self.wm_img_path.setPlaceholderText(tr("Elige una imagen (PNG con fondo transparente queda mejor)"))
        pick = _btn(tr("Elegir…"), None, "Secondary", icon_color=TEXT)
        pick.clicked.connect(self._wm_pick)
        r2.addWidget(self.wm_img_path, 1)
        r2.addWidget(pick)
        lay.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel(tr("Color")))
        self._wm_color_rgb = ptl.WM_COLORS["Gris"]
        self.wm_color_btn = _btn(tr("Gris"), None, "Secondary", icon_color=TEXT)
        self.wm_color_btn.clicked.connect(self._wm_color_menu)
        self._wm_paint_color_btn()
        r3.addWidget(self.wm_color_btn)
        r3.addWidget(QLabel(tr("Opacidad")))
        self.wm_opacity = QSlider(Qt.Horizontal)
        self.wm_opacity.setRange(5, 80); self.wm_opacity.setValue(25); self.wm_opacity.setFixedWidth(110)
        r3.addWidget(self.wm_opacity)
        self.wm_opacity_lbl = QLabel("25 %"); self.wm_opacity_lbl.setFixedWidth(40)
        r3.addWidget(self.wm_opacity_lbl)
        self.wm_opacity.valueChanged.connect(lambda v: self.wm_opacity_lbl.setText(f"{v} %"))
        self.wm_tile = QCheckBox(tr("Repetir (mosaico)"))
        r3.addWidget(self.wm_tile)
        r3.addStretch(1)
        lay.addLayout(r3)

        r3b = QHBoxLayout()
        r3b.addWidget(QLabel(tr("Giro del texto")))
        self.wm_angle = QSpinBox(); self.wm_angle.setRange(-90, 90); self.wm_angle.setValue(45); self.wm_angle.setSuffix("°")
        r3b.addWidget(self.wm_angle)
        r3b.addWidget(QLabel(tr("Tamaño del texto")))
        self.wm_size = QSpinBox(); self.wm_size.setRange(0, 300); self.wm_size.setValue(0)
        self.wm_size.setSpecialValueText(tr("Automático")); self.wm_size.setSuffix(" pt")
        r3b.addWidget(self.wm_size)
        r3b.addWidget(QLabel(tr("en mosaico")))
        self.wm_size_tile = QSpinBox(); self.wm_size_tile.setRange(0, 300); self.wm_size_tile.setValue(0)
        self.wm_size_tile.setSpecialValueText(tr("Automático")); self.wm_size_tile.setSuffix(" pt")
        r3b.addWidget(self.wm_size_tile)
        r3b.addStretch(1)
        lay.addLayout(r3b)
        self.wm_text_row = r3b

        r3c = QHBoxLayout()
        r3c.addWidget(QLabel(tr("Giro de la imagen")))
        self.wm_img_angle = QSpinBox(); self.wm_img_angle.setRange(-180, 180); self.wm_img_angle.setValue(0)
        self.wm_img_angle.setSuffix("°")
        r3c.addWidget(self.wm_img_angle)
        r3c.addStretch(1)
        lay.addLayout(r3c)
        self.wm_img_row = r3c

        r4 = QHBoxLayout()
        r4.addWidget(QLabel(tr("Páginas")))
        self.wm_pages = QLineEdit()
        self.wm_pages.setPlaceholderText(tr("todas  ·  ejemplos: 1-3, 5, 8-   ·   pares   ·   impares"))
        r4.addWidget(self.wm_pages, 1)
        lay.addLayout(r4)
        b = _btn(tr("Añadir marca de agua"), "stamp", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_wm)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)
        self._wm_mode_changed()
        self.wm_text_rb.toggled.connect(self._wm_mode_changed)
        self.wm_img_rb.toggled.connect(self._wm_mode_changed)

    def _wm_mode_changed(self):
        """Muestra el giro que toca según el modo (texto/mosaico con un ángulo, la imagen con otro, a 0° por defecto)."""
        use_img = self.wm_img_rb.isChecked()
        for i in range(self.wm_text_row.count()):
            w = self.wm_text_row.itemAt(i).widget()
            if w:
                w.setVisible(not use_img)
        for i in range(self.wm_img_row.count()):
            w = self.wm_img_row.itemAt(i).widget()
            if w:
                w.setVisible(use_img)
        if self.preview.hook is not None:
            self.preview.refresh(150)

    def _wm_paint_color_btn(self):
        pm = QPixmap(16, 16)
        pm.fill(Qt.transparent)
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.5))
        pa.setBrush(QColor(*(int(c * 255) for c in self._wm_color_rgb)))
        pa.drawEllipse(1, 1, 14, 14)
        pa.end()
        self.wm_color_btn.setIcon(QIcon(pm))

    def _wm_color_menu(self):
        m = QMenu(self)
        for name, rgb in ptl.WM_COLORS.items():
            pm = QPixmap(16, 16); pm.fill(Qt.transparent)
            pa = QPainter(pm); pa.setRenderHint(QPainter.Antialiasing)
            pa.setPen(QPen(QColor("#FFFFFF"), 1.5)); pa.setBrush(QColor(*(int(c * 255) for c in rgb)))
            pa.drawEllipse(1, 1, 14, 14); pa.end()
            m.addAction(QIcon(pm), tr(name), lambda n=tr(name), c=rgb: self._wm_set_color(n, c))
        m.addSeparator()

        def other():
            c = QColorDialog.getColor(QColor(*(int(v * 255) for v in self._wm_color_rgb)), self, tr("Color de la marca de agua"))
            if c.isValid():
                self._wm_set_color(c.name(), (c.redF(), c.greenF(), c.blueF()))
        m.addAction(tr("Otro color…"), other)
        m.exec(self.wm_color_btn.mapToGlobal(self.wm_color_btn.rect().bottomLeft()))

    def _wm_set_color(self, label: str, rgb):
        self._wm_color_rgb = tuple(rgb)
        self.wm_color_btn.setText(label)
        self._wm_paint_color_btn()
        if self.preview.hook is not None:
            self.preview.refresh(150)

    def _wm_kwargs(self) -> dict:
        use_img = self.wm_img_rb.isChecked()
        size = self.wm_size_tile.value() if self.wm_tile.isChecked() else self.wm_size.value()
        return dict(text="" if use_img else self.wm_text.text(), image=self.wm_img_path.text() if use_img else "",
                    opacity=self.wm_opacity.value() / 100,
                    angle=float(self.wm_img_angle.value()) if use_img else float(self.wm_angle.value()),
                    size=float(size), color=self._wm_color_rgb, pages=self.wm_pages.text(),
                    tile=self.wm_tile.isChecked(), password="")

    def _wm_hook(self, tmp_path: str, page_idx: int):
        """Pone la marca de agua en la página que se está viendo (si está entre las páginas elegidas). Solo dibuja
        sobre la copia temporal de la vista previa: nunca guarda nada en Descargas."""
        f = self._file()
        kw = self._wm_kwargs()
        if f and page_idx not in ptl.parse_pages(kw["pages"], f.get("pages", 1)):
            return None
        try:
            doc = ptl._open(tmp_path, "")
        except ptl.ToolError:
            return None
        try:
            ptl._apply_watermark(doc, text=kw["text"], image=kw["image"], opacity=kw["opacity"], angle=kw["angle"],
                                  size=kw["size"], color=kw["color"], tile=kw["tile"], pages="")
            out = os.path.join(os.path.dirname(tmp_path), "p_marca.pdf")
            doc.save(out)
            return out
        except ptl.ToolError:
            return None
        finally:
            doc.close()

    def _wm_timer_widgets(self):
        """Cualquier cambio en las opciones de la marca de agua redibuja la vista previa (nunca guarda nada)."""
        for w, sig in ((self.wm_text, "textChanged"), (self.wm_img_path, "textChanged"), (self.wm_pages, "textChanged"),
                       (self.wm_opacity, "valueChanged"), (self.wm_angle, "valueChanged"),
                       (self.wm_img_angle, "valueChanged"), (self.wm_size, "valueChanged"),
                       (self.wm_size_tile, "valueChanged"), (self.wm_tile, "toggled"), (self.wm_text_rb, "toggled")):
            getattr(w, sig).connect(lambda *_: self.preview.hook is not None and self.preview.refresh(250))

    def _wm_pick(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("Imagen de la marca de agua"), str(Path.home() / "Pictures"),
                                           tr("Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)"))
        if p:
            self.wm_img_path.setText(p)
            self.wm_img_rb.setChecked(True)

    def _do_wm(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        kw = self._wm_kwargs()
        del kw["password"]

        def each(f, out):
            self.win.replace_file(f, out)
            return True, None
        self._run_for_files(self._targets(scope), lambda path, pw: ptl.watermark(path, password=pw, **kw), each,
                            tr("Añadiendo marca de agua…"), tr("con marca de agua"))

    # ── Numerar páginas ───────────────────────────────────────────────────
    def _build_numbering(self):
        lay = self._tab("Numerar páginas", tr("Añade el número de página. Los cambios solo se ven en la vista previa: "
                                           "no se guarda nada hasta pulsar «Añadir numeración»."))
        r1 = QHBoxLayout()
        r1.addWidget(QLabel(tr("Posición")))
        self.pn_position = QComboBox()
        for p in ptl.PN_POSITIONS:
            self.pn_position.addItem(p)
        r1.addWidget(self.pn_position)
        r1.addWidget(QLabel(tr("Formato")))
        self.pn_format = QComboBox()
        self.pn_format.setEditable(True)
        for f in ptl.PN_FORMATS:
            self.pn_format.addItem(tr(f))
        self.pn_format.setToolTip(tr("{n} = número de página, {total} = último número. Puedes escribir tu propio formato."))
        r1.addWidget(self.pn_format, 1)
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel(tr("Empezar en")))
        self.pn_start = QSpinBox(); self.pn_start.setRange(0, 9999); self.pn_start.setValue(1)
        r2.addWidget(self.pn_start)
        r2.addWidget(QLabel(tr("Tamaño")))
        self.pn_size = QDoubleSpinBox(); self.pn_size.setRange(6, 72); self.pn_size.setValue(11); self.pn_size.setSuffix(" pt")
        r2.addWidget(self.pn_size)
        r2.addWidget(QLabel(tr("Margen")))
        self.pn_margin = QDoubleSpinBox(); self.pn_margin.setRange(4, 120); self.pn_margin.setValue(26); self.pn_margin.setSuffix(" pt")
        r2.addWidget(self.pn_margin)
        r2.addWidget(QLabel(tr("Color")))
        self._pn_color_rgb = ptl.WM_COLORS["Negro"]
        self.pn_color_btn = _btn(tr("Negro"), None, "Secondary", icon_color=TEXT)
        self.pn_color_btn.clicked.connect(self._pn_color_menu)
        self._pn_paint_color_btn()
        r2.addWidget(self.pn_color_btn)
        r2.addStretch(1)
        lay.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel(tr("Páginas")))
        self.pn_pages = QLineEdit()
        self.pn_pages.setPlaceholderText(tr("todas  ·  ejemplos: 2-   (deja la portada sin número)   ·   pares   ·   impares"))
        r3.addWidget(self.pn_pages, 1)
        lay.addLayout(r3)

        b = _btn(tr("Añadir numeración"), "text_add", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_numbering)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)

    def _pn_paint_color_btn(self):
        pm = QPixmap(16, 16); pm.fill(Qt.transparent)
        pa = QPainter(pm); pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(QPen(QColor("#FFFFFF"), 1.5)); pa.setBrush(QColor(*(int(c * 255) for c in self._pn_color_rgb)))
        pa.drawEllipse(1, 1, 14, 14); pa.end()
        self.pn_color_btn.setIcon(QIcon(pm))

    def _pn_color_menu(self):
        m = QMenu(self)
        for name, rgb in ptl.WM_COLORS.items():
            pm = QPixmap(16, 16); pm.fill(Qt.transparent)
            pa = QPainter(pm); pa.setRenderHint(QPainter.Antialiasing)
            pa.setPen(QPen(QColor("#FFFFFF"), 1.5)); pa.setBrush(QColor(*(int(c * 255) for c in rgb)))
            pa.drawEllipse(1, 1, 14, 14); pa.end()
            m.addAction(QIcon(pm), tr(name), lambda n=tr(name), c=rgb: self._pn_set_color(n, c))
        m.addSeparator()

        def other():
            c = QColorDialog.getColor(QColor(*(int(v * 255) for v in self._pn_color_rgb)), self, tr("Color de la numeración"))
            if c.isValid():
                self._pn_set_color(c.name(), (c.redF(), c.greenF(), c.blueF()))
        m.addAction(tr("Otro color…"), other)
        m.exec(self.pn_color_btn.mapToGlobal(self.pn_color_btn.rect().bottomLeft()))

    def _pn_set_color(self, label: str, rgb):
        self._pn_color_rgb = tuple(rgb)
        self.pn_color_btn.setText(label)
        self._pn_paint_color_btn()
        if self.preview.hook is not None:
            self.preview.refresh(150)

    def _pn_kwargs(self) -> dict:
        return dict(start=self.pn_start.value(), fmt=self.pn_format.currentText() or "{n}",
                    position=self.pn_position.currentText(), size=self.pn_size.value(),
                    color=self._pn_color_rgb, margin=self.pn_margin.value(), pages=self.pn_pages.text())

    def _pn_hook(self, tmp_path: str, page_idx: int):
        """Numera la página que se está viendo (si está entre las elegidas). Solo dibuja sobre la copia temporal
        de la vista previa: nunca guarda nada en Descargas."""
        f = self._file()
        kw = self._pn_kwargs()
        if f and page_idx not in ptl.parse_pages(kw["pages"], f.get("pages", 1)):
            return None
        try:
            doc = ptl._open(tmp_path, "")
        except ptl.ToolError:
            return None
        try:
            # el número que toca en esta página concreta, aunque la vista previa solo tenga esa única página
            idx_real = ptl.parse_pages(kw["pages"], f.get("pages", 1)) if f else [0]
            n = kw["start"] + (idx_real.index(page_idx) if page_idx in idx_real else 0)
            total_real = kw["start"] + len(idx_real) - 1
            fmt_resolved = kw["fmt"].replace("{total}", str(total_real))
            ptl._apply_page_numbers(doc, start=n, fmt=fmt_resolved, position=kw["position"], size=kw["size"],
                                    color=kw["color"], margin=kw["margin"], pages="todas")
            out = os.path.join(os.path.dirname(tmp_path), "p_numerado.pdf")
            doc.save(out)
            return out
        except ptl.ToolError:
            return None
        finally:
            doc.close()

    def _pn_timer_widgets(self):
        """Cualquier cambio en las opciones de numeración redibuja la vista previa (nunca guarda nada)."""
        for w, sig in ((self.pn_position, "currentIndexChanged"), (self.pn_format, "editTextChanged"),
                       (self.pn_start, "valueChanged"), (self.pn_size, "valueChanged"),
                       (self.pn_margin, "valueChanged"), (self.pn_pages, "textChanged")):
            getattr(w, sig).connect(lambda *_: self.preview.hook is not None and self.preview.refresh(250))

    def _do_numbering(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        kw = self._pn_kwargs()

        def each(f, r):
            self.win.replace_file(f, r["out"])
            return True, None
        self._run_for_files(self._targets(scope), lambda path, pw: ptl.number_pages(path, password=pw, **kw),
                            each, tr("Numerando páginas…"), tr("numerado"))

    # ── Invertir colores ──────────────────────────────────────────────────
    def _build_invert(self):
        lay = self._tab("Invertir colores", tr("Pasa el PDF a modo oscuro: fondo oscuro y colores más claros. El "
                                            "texto sigue siendo texto de verdad: se puede seguir buscando y "
                                            "copiando. Los cambios solo se ven en la vista previa: no se guarda "
                                            "nada hasta pulsar «Invertir colores»."))
        r1 = QHBoxLayout()
        r1.addWidget(QLabel(tr("Modo")))
        self.inv_mode = QComboBox()
        self.inv_mode.addItem(tr("Oscuro, conservar colores de las fotos"), "smart")
        self.inv_mode.addItem(tr("Invertir todos los colores (como un negativo)"), "full")
        r1.addWidget(self.inv_mode, 1)
        r1.addWidget(QLabel(tr("Fondo")))
        self.inv_bg = QComboBox()
        for name in ptl.INVERT_BACKGROUNDS:
            self.inv_bg.addItem(name)
        r1.addWidget(self.inv_bg)
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        self.inv_keep_dark = QCheckBox(tr("No tocar las páginas que ya son oscuras (diapositivas, fotos a página completa…)"))
        self.inv_keep_dark.setChecked(True)
        r2.addWidget(self.inv_keep_dark)
        r2.addStretch(1)
        lay.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel(tr("Páginas")))
        self.inv_pages = QLineEdit()
        self.inv_pages.setPlaceholderText(tr("todas  ·  ejemplos: 1-3, 5, 8-   ·   pares   ·   impares"))
        r3.addWidget(self.inv_pages, 1)
        lay.addLayout(r3)

        b = _btn(tr("Invertir colores"), "droplet", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_invert)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)

    def _inv_kwargs(self) -> dict:
        return dict(mode=self.inv_mode.currentData(), background=self.inv_bg.currentText(),
                    keep_dark_pages=self.inv_keep_dark.isChecked(), pages=self.inv_pages.text())

    def _inv_hook(self, tmp_path: str, page_idx: int):
        """Invierte la página que se está viendo (si está entre las elegidas). Solo dibuja sobre la copia temporal
        de la vista previa: nunca guarda nada en Descargas."""
        f = self._file()
        kw = self._inv_kwargs()
        if f and page_idx not in ptl.parse_pages(kw["pages"], f.get("pages", 1)):
            return None
        try:
            doc = ptl._open(tmp_path, "")
        except ptl.ToolError:
            return None
        try:
            ptl._apply_invert(doc, mode=kw["mode"], background=kw["background"],
                              keep_dark_pages=kw["keep_dark_pages"], pages="todas")
            out = os.path.join(os.path.dirname(tmp_path), "p_oscuro.pdf")
            doc.save(out)
            return out
        except ptl.ToolError:
            return None
        finally:
            doc.close()

    def _inv_timer_widgets(self):
        for w, sig in ((self.inv_mode, "currentIndexChanged"), (self.inv_bg, "currentIndexChanged"),
                       (self.inv_keep_dark, "toggled"), (self.inv_pages, "textChanged")):
            getattr(w, sig).connect(lambda *_: self.preview.hook is not None and self.preview.refresh(250))

    def _do_invert(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        kw = self._inv_kwargs()

        def each(f, out):
            self.win.replace_file(f, out)
            return True, None
        self._run_for_files(self._targets(scope), lambda path, pw: ptl.invert_colors(path, password=pw, **kw)["out"],
                            each, tr("Invirtiendo colores…"), tr("con modo oscuro"))

    # ── Aplanar y reparar ───────────────────────────────────────────────
    def _build_fix(self):
        lay = self._tab("Aplanar y reparar", tr("Aplanar convierte comentarios, dibujos y campos de formulario en contenido "
                                             "fijo (ya no se pueden editar). Reparar reconstruye un PDF dañado o que no "
                                             "se abre bien."))
        card = QFrame(); card.setObjectName("Card")
        c = QVBoxLayout(card)
        t = QLabel(tr("Aplanar")); t.setObjectName("SectionTitle"); c.addWidget(t)
        self.flat_annots = QCheckBox(tr("Anotaciones (resaltados, dibujos, notas, sellos…)")); self.flat_annots.setChecked(True)
        self.flat_widgets = QCheckBox(tr("Campos de formulario (con lo rellenado)")); self.flat_widgets.setChecked(True)
        c.addWidget(self.flat_annots); c.addWidget(self.flat_widgets)
        b = _btn(tr("Aplanar"), "document", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_flatten)
        c.addWidget(b, 0, Qt.AlignLeft)
        lay.addWidget(card)
        card2 = QFrame(); card2.setObjectName("Card")
        c2 = QVBoxLayout(card2)
        t2 = QLabel(tr("Reparar")); t2.setObjectName("SectionTitle"); c2.addWidget(t2)
        b2 = _btn(tr("Reparar PDF"), "bolt", "Secondary", icon_color=TEXT)
        b2.clicked.connect(self._do_repair)
        c2.addWidget(b2, 0, Qt.AlignLeft)
        lay.addWidget(card2)
        lay.addStretch(1)

    def _do_flatten(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        a, w = self.flat_annots.isChecked(), self.flat_widgets.isChecked()

        def each(f, r):
            self.win.replace_file(f, r["out"])
            return True, None
        self._run_for_files(self._targets(scope), lambda path, pw: ptl.flatten(path, a, w, pw), each,
                            tr("Aplanando…"), tr("aplanado"))

    def _do_repair(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return

        def each(f, r):
            self.win.replace_file(f, r["out"])
            return True, None
        self._run_for_files(self._targets(scope), lambda path, pw: ptl.repair(path, pw), each,
                            tr("Reparando…"), tr("revisado"))

    # ── Convertir a PDF ─────────────────────────────────────────────────
    def _build_convert(self):
        exts = " ".join(ptl.supported_extensions())
        lay = self._tab("Convertir a PDF", tr("Convierte imágenes, texto, Markdown, HTML y otros formatos a PDF. Word, "
                                           "Excel y PowerPoint necesitan Office o LibreOffice instalados. Formatos: {exts}", exts=exts))
        self.office_note = QFrame(); self.office_note.setObjectName("Card")
        nl = QHBoxLayout(self.office_note)
        txt = QLabel(tr("No encuentro Office ni LibreOffice: los archivos de Word, Excel o PowerPoint no se podrán "
                     "convertir hasta que instales uno de los dos. Las imágenes, el texto y el HTML sí funcionan igual."))
        txt.setObjectName("Hint"); txt.setWordWrap(True)
        nl.addWidget(txt, 1)
        inst_col = QVBoxLayout()
        inst = _btn(tr("Instalar LibreOffice…"), "download", "Secondary", icon_color=TEXT)
        inst.clicked.connect(self._offer_install_libreoffice)
        inst_col.addWidget(inst)
        check = _btn(tr("Ya lo instalé: comprobar"), None, "Flat", icon_color=TEXT)
        check.clicked.connect(lambda: self._refresh_office_note(say_if_missing=True))
        inst_col.addWidget(check)
        nl.addLayout(inst_col)
        lay.addWidget(self.office_note)
        self._refresh_office_note()
        self.conv_list = _ConvList(self._conv_add_paths)
        self.conv_list.setMinimumHeight(120)
        lay.addWidget(self.conv_list, 1)
        r = QHBoxLayout()
        add = _btn(tr("Añadir archivos…"), "clip", "Secondary", icon_color=TEXT)
        add.clicked.connect(self._conv_add)
        rm = _btn(tr("Quitar"), "trash", "Flat", icon_color=TEXT)
        rm.clicked.connect(lambda: [self.conv_list.takeItem(self.conv_list.row(i)) for i in self.conv_list.selectedItems()])
        r.addWidget(add); r.addWidget(rm); r.addStretch(1)
        r.addWidget(QLabel(tr("Imágenes en página:")))
        self.conv_size = QComboBox()
        for n in ("A4", "Carta", "Ajustar"):
            self.conv_size.addItem(n)
        r.addWidget(self.conv_size)
        lay.addLayout(r)
        b = _btn(tr("Convertir"), "play", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_convert)
        lay.addWidget(b, 0, Qt.AlignLeft)

    def _conv_add(self):
        flt = tr("Todos los compatibles ({exts})", exts=" ".join("*" + e for e in ptl.supported_extensions()))
        paths, _ = QFileDialog.getOpenFileNames(self, tr("Archivos a convertir"), str(Path.home()), flt)
        self._conv_add_paths(paths)

    def _conv_add_paths(self, paths: list):
        existing = {self.conv_list.item(i).data(Qt.UserRole) for i in range(self.conv_list.count())}
        for p in paths:
            if p not in existing:
                it = QListWidgetItem(Path(p).name)
                it.setData(Qt.UserRole, p)
                self.conv_list.addItem(it)

    def _do_convert(self):
        paths = [self.conv_list.item(i).data(Qt.UserRole) for i in range(self.conv_list.count())]
        if not paths:
            self._say(tr("Añade al menos un archivo."), "error")
            return
        size = self.conv_size.currentText()

        def done(results):
            ok = [r for r in results if r[1]]
            bad = [r for r in results if not r[1]]
            for _src, out, _e in ok:
                self.win.add_file(out, Path(out).name)
            self.conv_list.clear()
            self.populate()
            msg = "✓ " + tr("{n} PDF creado(s) (están en la lista y en Descargas).", n=len(ok))
            if bad:
                msg += "  " + tr("No se pudo: ") + " · ".join(f"{Path(s).name if os.path.exists(str(s)) else s}: {e}" for s, _o, e in bad)
            self._say(msg, "ok" if ok and not bad else "error" if not ok else "info")
        self._run(lambda cb: ptl.convert_to_pdf(paths, size), done, tr("Convirtiendo…"))

    def _refresh_office_note(self, say_if_missing: bool = False):
        """Vuelve a mirar si hay Office o LibreOffice y muestra u oculta el aviso."""
        eng = ptl.office_engines()
        found = bool(eng.get("word") or eng.get("excel") or eng.get("powerpoint") or eng.get("libreoffice"))
        self.office_note.setVisible(not found)
        if say_if_missing:
            self.win.snack(tr("Ya puedes convertir Word, Excel y PowerPoint.") if found else
                          tr("Sigo sin encontrar Office ni LibreOffice."), "success" if found else "error")

    def _offer_install_libreoffice(self):
        """Pide permiso, descarga el instalador oficial de LibreOffice y lo abre: la instalación la termina el
        usuario en la ventana del propio instalador (no se instala nada en silencio)."""
        if self._job is not None and self._job.isRunning():
            return
        try:
            info = ptl.libreoffice_installer_info()
        except ptl.ToolError as e:
            self.win.snack(str(e), "error")
            return
        size_mb = (info["size"] or 0) / (1024 * 1024)
        msg = tr("Se descargará el instalador oficial de LibreOffice {version} para Windows\n"
              "«{filename}», unos {size_mb:.0f} MB\n"
              "desde download.documentfoundation.org.\n\n"
              "Después se abrirá su propio instalador: tú decides si seguir, aceptas sus condiciones y lo "
              "instalas (con el permiso de Windows si lo pide). El programa no instala nada por su cuenta.",
              version=info['version'], filename=info['filename'], size_mb=size_mb)
        if QMessageBox.question(self, tr("Instalar LibreOffice"), msg,
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        dlg = QProgressDialog(tr("Descargando LibreOffice…"), tr("Cancelar"), 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setValue(0)

        def on_progress(done, total):
            if total:
                dlg.setMaximum(100)
                dlg.setValue(int(done * 100 / total))
            else:
                dlg.setMaximum(0)
            dlg.setLabelText(tr("Descargando LibreOffice… {done:.0f} / {total:.0f} MB",
                                 done=done / 1024 / 1024, total=total / 1024 / 1024)
                             if total else tr("Descargando LibreOffice…"))

        def on_done(path):
            dlg.close()
            try:
                ptl.run_installer(path)
            except Exception:
                self.win.snack(tr("Se descargó, pero no se pudo abrir el instalador. Ábrelo a mano."), "error")
                return
            QMessageBox.information(self, tr("Instalar LibreOffice"),
                                    tr("Se ha abierto el instalador de LibreOffice. Cuando termines, vuelve aquí y "
                                    "pulsa «Ya lo instalé: comprobar»."))

        def on_failed(msg):
            dlg.close()
            self.win.snack(msg, "error")

        job = _ToolJob(lambda cb: ptl.download_libreoffice_installer(info, progress=cb))
        job.progress.connect(on_progress)
        job.finished_ok.connect(on_done)
        job.failed.connect(on_failed)
        dlg.canceled.connect(job.terminate)
        self._job = job
        job.start()

    # ── Convertir desde PDF ───────────────────────────────────────────────
    def _build_export(self):
        lay = self._tab("Convertir desde PDF", tr("Exporta el PDF elegido a otro formato. El PDF original no se "
                                               "modifica; el resultado se guarda en Descargas."))
        r1 = QHBoxLayout()
        r1.addWidget(QLabel(tr("Formato de salida")))
        self.exp_format = QComboBox()
        for f in ptl.PDF_EXPORT_FORMATS:
            self.exp_format.addItem(f)
        self.exp_format.currentTextChanged.connect(self._exp_format_changed)
        r1.addWidget(self.exp_format, 1)
        r1.addWidget(QLabel(tr("Calidad")))
        self.exp_dpi = QComboBox()
        for label, dpi in ((tr("Normal (100 ppp)"), 100), (tr("Alta (150 ppp)"), 150), (tr("Muy alta (300 ppp)"), 300)):
            self.exp_dpi.addItem(label, dpi)
        self.exp_dpi.setCurrentIndex(1)
        r1.addWidget(self.exp_dpi)
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel(tr("Páginas")))
        self.exp_pages = QLineEdit()
        self.exp_pages.setPlaceholderText(tr("todas  ·  ejemplos: 1-3, 5, 8-   ·   pares   ·   impares"))
        r2.addWidget(self.exp_pages, 1)
        lay.addLayout(r2)

        self.exp_note = QLabel(); self.exp_note.setObjectName("Hint"); self.exp_note.setWordWrap(True)
        lay.addWidget(self.exp_note)

        b = _btn(tr("Convertir"), "download", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_export)
        lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)
        self._exp_format_changed()

    # NOTA: las claves de este diccionario son los valores de ptl.PDF_EXPORT_FORMATS (identificadores internos,
    # no se traducen); solo se traduce el texto de la nota al mostrarlo.
    _EXP_NOTES = {
        "Imágenes (PNG)": "Una imagen por página, con transparencia donde la hubiera.",
        "Imágenes (JPG)": "Una imagen por página, más ligeras pero sin transparencia.",
        "Texto (.txt)": "El texto que ya tiene el PDF. Si es un escaneo sin OCR previo, no saldrá nada: pásalo "
                        "antes por OCR.",
        "HTML": "El texto de cada página, colocado tal como está en el PDF.",
        "Word (.docx)": "Sale editable, pero no es una copia exacta: tablas, columnas y fuentes pueden no "
                        "coincidir del todo con el original.",
    }

    def _exp_format_changed(self):
        name = self.exp_format.currentText()
        self.exp_dpi.setVisible(name.startswith("Imágenes"))
        self.exp_note.setText(tr(self._EXP_NOTES.get(name, "")) if self._EXP_NOTES.get(name) else "")

    def _do_export(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        fmt = self.exp_format.currentText()
        dpi = self.exp_dpi.currentData() or 150
        pages = self.exp_pages.text()

        def each(f, r):
            return True, None
        self._run_for_files(self._targets(scope), lambda path, pw: ptl.convert_from_pdf(path, fmt, dpi, pages, pw),
                            each, tr("Convirtiendo…"), tr("convertido (en Descargas)"))

    # ── Analizar PDF ──────────────────────────────────────────────────────
    def _build_inspect(self):
        lay = self._tab("Analizar PDF", tr("Examina el PDF elegido: versión, páginas, metadatos, cifrado y permisos, "
                                        "fuentes, imágenes, formulario, marcadores y si tiene firma digital. No lo "
                                        "modifica ni lo guarda."))
        b = _btn(tr("Analizar"), "info", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_inspect)
        lay.addWidget(b, 0, Qt.AlignLeft)
        self.inspect_report = QPlainTextEdit()
        self.inspect_report.setReadOnly(True)
        self.inspect_report.setPlaceholderText(tr("Pulsa «Analizar» para ver la información del PDF elegido."))
        lay.addWidget(self.inspect_report, 1)

    def _do_inspect(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        targets = self._targets(scope)
        pw = self.pw_field.text()

        def job(cb):
            out = []
            for i, f in enumerate(targets):
                cb(i, len(targets))
                try:
                    out.append((f, ptl.inspect_pdf(f["path"], pw), None))
                except ptl.ToolError as e:
                    out.append((f, None, str(e)))
            cb(len(targets), max(len(targets), 1))
            return out

        def done(results):
            parts = []
            for f, info, err in results:
                if err:
                    parts.append(f"=== {f['name']} ===\n" + tr("No se ha podido analizar: {err}", err=err))
                else:
                    head = f"=== {f['name']} ===\n" if len(targets) > 1 else ""
                    parts.append(head + self._format_inspect(info))
            self.inspect_report.setPlainText("\n\n".join(parts))
            self._say("✓ " + tr("Analizado(s) {n} archivo(s).", n=len(targets)), "ok")
        self._run(job, done, tr("Analizando…"), unit="archivo")

    _META_LABELS = {"title": "Título", "author": "Autor", "subject": "Asunto", "keywords": "Palabras clave",
                    "creator": "Programa de creación", "producer": "Productor", "creationDate": "Creado",
                    "modDate": "Modificado"}

    def _format_inspect(self, info: dict) -> str:
        L = []
        L.append(tr("Archivo: {name}  ({size})", name=Path(info['path']).name, size=_human_size(info['size'])))
        L.append(tr("Versión: {v}", v=info['version']))
        L.append(tr("Páginas: {n}", n=info['pages']))
        for ps in info["page_sizes"]:
            L.append(tr("  • {n} página(s) de {w} × {h} pt ({orientation})",
                        n=ps['n'], w=ps['width'], h=ps['height'], orientation=ps['orientation']))
        L.append("")
        L.append(tr("Metadatos:"))
        any_meta = False
        for k, label in self._META_LABELS.items():
            v = info["metadata"].get(k)
            if v:
                L.append(f"  {tr(label)}: {v}")
                any_meta = True
        if not any_meta:
            L.append("  " + tr("(sin metadatos)"))
        L.append("")
        L.append(tr("Seguridad:"))
        L.append("  " + tr("Necesita contraseña para abrirse: {v}", v=tr("sí") if info['needs_password'] else tr("no")))
        L.append("  " + tr("Cifrado: {v}", v=tr("sí") if info['encrypted'] else tr("no")))
        if info["encrypted"]:
            L.append("  " + tr("Permite: {v}", v=(", ".join(info["permissions"]) if info["permissions"] else tr("nada"))))
        L.append("")
        L.append(tr("Firma digital: {v}", v=tr("sí tiene (usa «Verificar firmas» para comprobarla)") if info["signed"]
                                      else tr("no tiene")))
        L.append("")
        L.append(tr("Fuentes ({n}):", n=len(info['fonts'])))
        for fo in info["fonts"][:40]:
            L.append(f"  • {fo['name']} ({fo['type']}) — " + (tr("incrustada") if fo['embedded'] else tr("no incrustada")))
        L.append("")
        L.append(tr("Imágenes: {n}", n=info['n_images']))
        L.append("")
        L.append(tr("Formulario: {v}", v=tr("sí, con {n} campo(s)", n=info['n_form_fields']) if info["is_form"] else tr("no")))
        L.append("")
        L.append(tr("Marcadores: {n}", n=info['n_bookmarks']))
        for bm in info["bookmarks"][:20]:
            L.append(f"  • {bm}")
        return "\n".join(L)

    # ── Verificar firmas ──────────────────────────────────────────────────
    def _build_verify_sig(self):
        lay = self._tab("Verificar firmas", tr("Comprueba las firmas digitales del PDF elegido: quién firmó, cuándo "
                                            "y si el documento se modificó después de firmarlo. No comprueba si el "
                                            "certificado es de una entidad de confianza (no dice si la firma es "
                                            "«cualificada» en el sentido legal), solo si el documento está intacto."))
        b = _btn(tr("Comprobar firmas"), "signature", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_verify_sig)
        lay.addWidget(b, 0, Qt.AlignLeft)
        self.sig_report = QPlainTextEdit()
        self.sig_report.setReadOnly(True)
        self.sig_report.setPlaceholderText(tr("Pulsa «Comprobar firmas» para ver las firmas del PDF elegido."))
        lay.addWidget(self.sig_report, 1)

    def _do_verify_sig(self):
        if not self._need_file():
            return
        scope = self._ask_scope()
        if not scope:
            return
        targets = self._targets(scope)
        pw = self.pw_field.text()

        def job(cb):
            out = []
            for i, f in enumerate(targets):
                cb(i, len(targets))
                try:
                    out.append((f, ptl.verify_signatures(f["path"], pw), None))
                except ptl.ToolError as e:
                    out.append((f, None, str(e)))
            cb(len(targets), max(len(targets), 1))
            return out

        def done(results):
            parts, all_intact = [], True
            for f, info, err in results:
                head = f"=== {f['name']} ===\n" if len(targets) > 1 else ""
                if err:
                    parts.append(head + tr("No se ha podido comprobar: {err}", err=err))
                    continue
                parts.append(head + self._format_sig_report(info))
                if not all(s.get("intact", False) for s in info["signatures"] if not s.get("error")):
                    all_intact = False
            self.sig_report.setPlainText("\n\n".join(parts))
            self._say(("✓ " + tr("Firmas comprobadas.")) if all_intact else
                      ("⚠ " + tr("Alguna firma indica que un documento se modificó después.")), "ok" if all_intact else "error")
        self._run(job, done, tr("Comprobando firmas…"), unit="archivo")

    _MOD_LABELS = {"NONE": "ninguna (igual que cuando se firmó)", "FORM_FILLING": "se rellenaron campos de formulario",
                  "ANNOTATIONS": "se añadieron anotaciones", "OTHER": "sí, se modificó el contenido"}

    def _format_sig_report(self, info: dict) -> str:
        if info["n"] == 0:
            return tr("Este PDF no tiene ninguna firma digital.")
        L = [tr("{n} firma(s) encontrada(s):\n", n=info['n'])]
        for i, s in enumerate(info["signatures"], 1):
            L.append(tr("— Firma {i}: campo «{field}»", i=i, field=s['field']))
            if s.get("error"):
                L.append("   " + tr("No se ha podido comprobar: {err}", err=s['error']))
                L.append("")
                continue
            L.append("   " + tr("Firmante (según el certificado): {v}", v=s['signer']))
            L.append("   " + tr("Emitido por: {v}", v=s['issuer']))
            L.append("   " + tr("Fecha de firma: {v}", v=s['signing_time'] or tr("(no indicada)")))
            L.append("   " + tr("Firma íntegra (no se ha tocado desde que se firmó): {v}",
                                v=tr("sí") if s['intact'] else tr("NO — el documento se modificó después de esta firma")))
            if not s["entire_file"] and s["intact"]:
                L.append("   " + tr("Aviso: esta firma no cubre todo el archivo (hay contenido añadido después, p. ej. otra firma posterior)."))
            L.append("   " + tr("Qué cambió después: {v}", v=tr(self._MOD_LABELS.get(s['modified_after'], s['modified_after']))))
            L.append("")
        L.append(tr("Nota: esto comprueba que el documento no se ha tocado desde que se firmó, pero no comprueba si "
                 "el certificado pertenece de verdad a quien dice ser (para eso haría falta la lista de entidades "
                 "de confianza de la UE, que no está incluida). No es una comprobación de validez legal ni dice si "
                 "la firma es «cualificada»."))
        return "\n".join(L)

    # ── OCR ─────────────────────────────────────────────────────────────
    def _build_ocr(self):
        lay = self._tab("OCR", tr("Reconoce el texto de un PDF escaneado (o hecho de imágenes) y lo añade de forma invisible: "
                               "ya se puede buscar y copiar. Si la página es una foto torcida, puede enderezarla antes en "
                               "el mismo paso. Funciona sin internet; los idiomas son archivos pequeños que se "
                               "instalan una vez."))
        er = QHBoxLayout()
        er.addWidget(QLabel(tr("Motor")))
        self.ocr_engine = QComboBox()
        self.ocr_engine.addItem(tr("RapidOCR · recomendado"), "rapid")
        self.ocr_engine.addItem(tr("Tesseract · rápido"), "tesseract")
        if not ptl.rapid_available():
            self.ocr_engine.setCurrentIndex(1)
            self.ocr_engine.model().item(0).setEnabled(False)
            self.ocr_engine.setToolTip(tr("RapidOCR no está instalado: pip install rapidocr"))
        else:
            self.ocr_engine.setToolTip(tr("RapidOCR usa redes neuronales (sin internet, gratis) y lee mucho mejor las fotos "
                                       "borrosas o pequeñas. Tesseract es más rápido y va bien con escaneos limpios."))
        self.ocr_engine.currentIndexChanged.connect(self._ocr_engine_changed)
        er.addWidget(self.ocr_engine)
        er.addStretch(1)
        lay.addLayout(er)
        self.ocr_engine_note = QLabel()
        self.ocr_engine_note.setObjectName("Hint")
        self.ocr_engine_note.setWordWrap(True)
        lay.addWidget(self.ocr_engine_note)
        self.ocr_lang_panel = QWidget()
        lp = QVBoxLayout(self.ocr_lang_panel)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.addWidget(QLabel(tr("Idiomas del documento:")))
        self.ocr_langs_box = QHBoxLayout()
        wrap = QWidget(); wrap.setLayout(self.ocr_langs_box)
        lp.addWidget(wrap)
        self.ocr_missing_box = QHBoxLayout()
        wrap2 = QWidget(); wrap2.setLayout(self.ocr_missing_box)
        lp.addWidget(wrap2)
        lay.addWidget(self.ocr_lang_panel)
        r = QHBoxLayout()
        self.ocr_only = QCheckBox(tr("Solo las páginas sin texto")); self.ocr_only.setChecked(True)
        r.addWidget(self.ocr_only)
        self.ocr_precise = QCheckBox(tr("Máxima precisión"))
        self.ocr_precise.setToolTip(tr("Usa datos de idioma de alta precisión (tessdata_best, unos 15 MB por idioma, se "
                                    "descargan una vez). Más lento, pero lee mucho mejor el texto borroso o de baja "
                                    "resolución."))
        r.addWidget(self.ocr_precise)
        self.ocr_review = QCheckBox(tr("Revisar el texto antes de guardar"))
        self.ocr_review.setChecked(True)
        self.ocr_review.setToolTip(tr("Tras leer, se abre una vista para comparar el texto con la página y corregirlo. "
                                   "Desde ahí también puedes crear un PDF nuevo redibujado con el texto."))
        r.addWidget(self.ocr_review)
        # ── Enderezar (opcional, dentro del mismo OCR)
        self.ocr_straighten = QCheckBox(tr("Enderezar las páginas torcidas"))
        self.ocr_straighten.setChecked(True)
        self.ocr_straighten.setToolTip(tr("Busca solo el papel, corrige la perspectiva y gira la página hasta que las líneas "
                                       "de texto queden horizontales (se guía por la base de las letras). Las páginas que "
                                       "ya están rectas no se tocan. Sirve para papel plano: una hoja arrugada no se aplana."))
        r.addWidget(self.ocr_straighten)
        r.addStretch(1)
        lay.addLayout(r)
        self.ocr_panel = OcrPagesPanel(self)
        lay.addWidget(self.ocr_panel, 1)
        self.ocr_straighten.toggled.connect(self.ocr_panel.setVisible)
        self.ocr_only.toggled.connect(lambda _on: self.ocr_panel.refresh_all())
        self.tabs.currentChanged.connect(lambda _i: self._load_ocr_panel())
        b = _btn(tr("Reconocer texto"), "play", "Primary", icon_color=ICON_DARK)
        b.clicked.connect(self._do_ocr)
        lay.addWidget(b, 0, Qt.AlignLeft)
        self._ocr_checks: dict = {}
        self._ocr_engine_changed()
        page = lay.parentWidget()                               # la pestaña entera se desplaza si la ventana es baja
        idx = self.tabs.indexOf(page)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        sc.setWidget(page)
        self.tabs.removeTab(idx)
        self.tabs.insertTab(idx, sc, "OCR")

    def _refresh_ocr_langs(self):
        for box in (self.ocr_langs_box, self.ocr_missing_box):
            while box.count():
                w = box.takeAt(0).widget()
                if w:
                    w.deleteLater()
        prev = {k: c.isChecked() for k, c in self._ocr_checks.items()}
        self._ocr_checks = {}
        avail = ptl.available_languages()
        for code in sorted(avail, key=lambda c: (c not in ("spa", "por", "eng"), c)):
            cb = QCheckBox(tr(ptl.LANG_NAMES.get(code, code)))
            cb.setChecked(prev.get(code, code in ("spa", "por") or (code == "eng" and not ({"spa", "por"} & set(avail)))))
            self._ocr_checks[code] = cb
            self.ocr_langs_box.addWidget(cb)
        self.ocr_langs_box.addStretch(1)
        missing = sorted((c for c in ptl.LANG_NAMES if c not in avail), key=lambda c: ptl.LANG_NAMES[c])
        if missing:
            lbl = QLabel(tr("¿Otro idioma?"))
            lbl.setObjectName("Hint")
            self.ocr_missing_box.addWidget(lbl)
            combo = QComboBox()
            combo.setMinimumWidth(260)
            combo.addItem(tr("Descargar otro idioma…"), None)
            for code in missing:
                combo.addItem(f"{tr(ptl.LANG_NAMES[code])}  ({code})", code)
            combo.activated.connect(lambda i, c=combo: self._lang_picked(c))
            self.ocr_lang_combo = combo
            self.ocr_missing_box.addWidget(combo)
        self.ocr_missing_box.addStretch(1)
        self._ocr_engine_changed()

    def _lang_picked(self, combo: QComboBox):
        code = combo.currentData()
        combo.setCurrentIndex(0)
        if code:
            self._install_lang(code)

    def _install_lang(self, code: str):
        name = tr(ptl.LANG_NAMES.get(code, code))
        if QMessageBox.question(
                self, tr("Instalar idioma"),
                tr("Se descargará el idioma «{name}» ({code}.traineddata, unos 1–10 MB) del repositorio oficial de Tesseract "
                "(github.com/tesseract-ocr/tessdata_fast) y se guardará en tu carpeta de datos del programa.\n\n"
                "¿Descargarlo?", name=name, code=code), QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._run(lambda cb: ptl.download_language(code),
                  lambda _p: (self._refresh_ocr_langs(), self._say("✓ " + tr("Idioma «{name}» instalado.", name=name), "ok")),
                  tr("Descargando «{name}»…", name=name))

    def _ocr_engine_changed(self, *_):
        """Idiomas y «Máxima precisión» solo cuentan con Tesseract; RapidOCR reconoce los idiomas con alfabeto latino solo."""
        rapid = self.ocr_engine.currentData() == "rapid"
        self.ocr_precise.setVisible(not rapid)
        if rapid:
            self.ocr_precise.setChecked(False)
        self.ocr_lang_panel.setVisible(not rapid)
        self.ocr_engine_note.setText(tr(
            "Lee bien fotos, escaneos borrosos y papel torcido. Detecta solo el idioma (alfabeto latino): no hace falta "
            "elegirlo. Es algo más lento.") if rapid else tr(
            "Muy rápido y va bien con escaneos limpios y rectos. Elige abajo el idioma del documento; para fotos o "
            "texto borroso usa RapidOCR."))

    def _load_ocr_panel(self):
        """Las miniaturas y la detección de esquinas solo se calculan cuando se abre la pestaña OCR."""
        if self.tabs.tabText(self.tabs.currentIndex()) == "OCR":
            self.ocr_panel.load(self._file(), self.pw_field.text())

    def _do_ocr(self):
        f = self._need_file()
        if not f:
            return
        engine = self.ocr_engine.currentData()
        langs = [c for c, cb in self._ocr_checks.items() if cb.isChecked()]
        if not langs and engine != "rapid":
            self._say(tr("Marca al menos un idioma (o instala uno de la lista)."), "error")
            return
        dpi, only, pw = 300, self.ocr_only.isChecked(), self.pw_field.text()   # tope; cada página se lee a la resolución de su escaneo (ptl.render_dpi_for)
        enhance = True                      # siempre: quita ruido y líneas de tabla solo para leer mejor
        straighten, flatten = self.ocr_straighten.isChecked(), True
        manual = self.ocr_panel.manual() if straighten else {}
        precise = self.ocr_precise.isChecked()
        review = self.ocr_review.isChecked()
        missing_hq = [l for l in langs if not ptl.best_available(l)] if precise else []
        if missing_hq:
            names = ", ".join(f"{tr(ptl.LANG_NAMES.get(l, l))} ({l}.traineddata)" for l in missing_hq)
            if QMessageBox.question(
                    self, tr("Descargar datos de alta precisión"),
                    tr("Para la máxima precisión se descargará, una sola vez: {names}.\n\nOrigen: "
                    "github.com/tesseract-ocr/tessdata_best (repositorio oficial de Tesseract). Unos 15 MB por idioma "
                    "(el de inglés pesa 15 MB). Se guardan en tu carpeta de datos del programa.\n\n¿Descargarlos?", names=names),
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return

        def saved(r):
            outs = r.get("outs") or [r["out"]]
            more = tr(" También: {name}.", name=Path(outs[1]).name) if len(outs) > 1 else ""
            self._adopt(r["out"], f, tr("Texto guardado en {pages} página(s) ({words} palabras).",
                                        pages=r['pages'], words=r['words']) + more)

        def done(r):
            if r.get("review"):
                if not r["pages"]:                                  # nada que revisar (p. ej. solo páginas giradas)
                    self._job.wait()
                    self._run(lambda cb: ptl.ocr_apply(r, {}, True, False, progress=cb), saved, tr("Guardando…"))
                    return
                dlg = OcrReviewDialog(self.window(), r)
                if dlg.exec() != QDialog.Accepted:
                    self._say(tr("Revisión cancelada: no se ha guardado nada."), "info")
                    return
                texts, s, rd = dlg.texts(), dlg.searchable(), dlg.redrawn()
                self._job.wait()
                self._run(lambda cb: ptl.ocr_apply(r, texts, s, rd, progress=cb), saved, tr("Guardando el texto…"))
                return
            extra = tr(", {n} tabla(s)", n=r['tables']) if r.get("tables") else ""
            n_str = r.get("straightened", 0)
            tail = (tr(" {n} página(s) enderezada(s).", n=n_str)
                    if straighten and n_str else tr(" La página original no se ha tocado."))
            self._adopt(r["out"], f, tr("Texto reconocido en {pages} página(s) ({words} palabras{extra}).",
                                        pages=r['pages'], words=r['words'], extra=extra) + tail)
        def work(cb):
            for l in missing_hq:                                   # primero los datos de alta precisión que falten
                ptl.download_language(l, best=True)
            return pf.ocr_straight(f["path"], langs, dpi, only, pw, progress=cb, enhance=enhance,
                                   straighten=straighten, flatten=flatten, manual=manual, precise=precise,
                                   engine=engine, review=review)
        self._run(work, done,
                  tr("Enderezando y reconociendo texto…") if straighten else tr("Reconociendo texto…"))
