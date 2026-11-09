# -*- coding: utf-8 -*-
"""
PDF Manager by Provecto (PySide6)
Ventana principal y arranque. Las pantallas viven en el paquete ui/; la lógica de PDF, en backend.py y pdf_tools.py.
"""
import copy
import shutil
import time
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QUrl, QTimer, Signal
from PySide6.QtGui import QIcon, QPainter, QColor, QDesktopServices, QBrush, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QStackedWidget,
    QDialog,
    QMessageBox,
    QStatusBar,
    QInputDialog,
    QProgressDialog,
)

import backend as be
import pdf_tools as ptl
import workflows as wf
import draft as dr
import theme
from theme import QSS, BG_GRAD_TOP, BG_GRAD_BOTTOM, ORB1, ORB2, ORB3
import i18n
from i18n import tr
from ui.ajuste import AjusteDialog, AjusteMultiDialog
from ui.common import init_bridge, run_bg
from ui.compare import ComparePage
from ui.edit_page import EditPage
from ui.home import HomePage
from ui.metadata import MetadataPage
from ui.organize import OrganizePage
from ui.pick import PickFilePage
from ui.size_nup import NUpPage, SizeMarginsPage
from ui.split import SplitPage
from ui.tools import ToolsPage
from ui.workflows_ui import AskValuesDialog, WorkflowEditorDialog, WorkflowsPage


# ══════════════════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    steps_changed = Signal()
    workflow_done = Signal(object, object)   # (rutas de salida, avisos)
    workflow_progress = Signal(str)
    file_ready = Signal(str, str)            # (ruta, nombre): un archivo ya convertido, listo para la lista
    notice = Signal(str, str)                # (mensaje, tipo): avisos desde hilos secundarios

    def __init__(self):
        super().__init__()
        init_bridge()                        # se crea aquí: en el hilo de la pantalla
        self.file_ready.connect(self.add_file)
        self.notice.connect(self.snack)
        self.session_steps: list[dict] = []
        self.saved_upto = 0          # cuántos pasos de la sesión ya están guardados
        self.saved_name = ""
        self.saved_id = ""           # workflow al que se pueden añadir los pasos nuevos
        self.setWindowTitle("PDF Manager by Provecto")
        self.setMinimumSize(480, 480)
        self.resize(1080, 820)
        icon_path = be.resource_path("provecto_icon.ico")
        if Path(icon_path).is_file():
            self.setWindowIcon(QIcon(icon_path))

        self.uploaded_files: list[dict] = []
        self._pending = None                 # (título, acción, mínimo de archivos) a la espera de que se suban PDFs
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.timeout.connect(self._run_pending)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_page = HomePage(self)
        self.organize_page = OrganizePage(self)
        self.edit_page = EditPage(self)
        self.metadata_page = MetadataPage(self)
        self.split_page = SplitPage(self)
        self.size_margins_page = SizeMarginsPage(self)
        self.nup_page = NUpPage(self)
        self.workflows_page = WorkflowsPage(self)
        self.tools_page = ToolsPage(self)
        self.pick_page = PickFilePage(self)
        self.compare_page = ComparePage(self)

        for p in (self.home_page, self.organize_page,
                  self.edit_page, self.metadata_page, self.split_page,
                  self.size_margins_page, self.nup_page, self.workflows_page, self.tools_page,
                  self.pick_page, self.compare_page):
            self.stack.addWidget(p)
        self.stack.setCurrentWidget(self.home_page)
        self.stack.currentChanged.connect(lambda _i: self.cancel_save_as())

        self._wf_progress: QProgressDialog | None = None
        self.steps_changed.connect(self.home_page.refresh_steps_bar)
        self.workflow_done.connect(self._on_workflow_done)
        self.workflow_progress.connect(self._on_workflow_progress)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def paintEvent(self, event):
        """Fondo con degradado y manchas de color difuminadas (da profundidad a toda la app,
        ya que las pantallas viven dentro del mismo QStackedWidget sin fondo propio)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0, QColor(BG_GRAD_TOP))
        base.setColorAt(1, QColor(BG_GRAD_BOTTOM))
        p.fillRect(self.rect(), QBrush(base))
        for cx, cy, r, rgba in (
            (w * 0.06, h * 0.04, max(w, h) * 0.42, ORB1),
            (w * 0.98, h * 0.14, max(w, h) * 0.46, ORB2),
            (w * 0.55, h * 1.05, max(w, h) * 0.52, ORB3),
        ):
            g = QRadialGradient(cx, cy, r)
            color = QColor(*rgba)
            g.setColorAt(0.0, color)
            transparent = QColor(color)
            transparent.setAlpha(0)
            g.setColorAt(1.0, transparent)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        p.end()
        super().paintEvent(event)

    def restart_app(self):
        """Relanza el programa (necesario tras cambiar de modo claro/oscuro, porque la paleta
        se fija al arrancar)."""
        QApplication.quit()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def toggle_theme(self):
        new_mode = theme.other_mode(theme.MODE)
        label = "claro" if new_mode == "light" else "oscuro"
        resp = QMessageBox.question(
            self, "Cambiar de modo",
            f"Se reiniciará la aplicación para aplicar el modo {label}. ¿Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if resp == QMessageBox.Yes:
            theme.save_mode(new_mode)
            self.restart_app()

    def cycle_language(self):
        new_lang = i18n.next_lang(i18n.LANG)
        name = i18n.LANG_NAMES.get(new_lang, new_lang)
        resp = QMessageBox.question(
            self, "Change language" if i18n.LANG == "en" else "Mudar idioma" if i18n.LANG == "pt" else "Cambiar idioma",
            f"The app will restart in {name}. Continue?" if i18n.LANG == "en"
            else f"O aplicativo será reiniciado em {name}. Continuar?" if i18n.LANG == "pt"
            else f"Se reiniciará la aplicación en {name}. ¿Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if resp == QMessageBox.Yes:
            i18n.save_lang(new_lang)
            self.restart_app()

    # ── Utilidades ──────────────────────────────────────────────────────
    def snack(self, msg: str, kind: str = "success"):
        colors = {"success": "#92976C", "error": "#D47268", "info": "#C08258"}
        self.status.setStyleSheet(f"color:{colors.get(kind, '#92976C')};")
        self.status.showMessage(msg, 4000)

    def ensure_files(self, title: str, action, minimum: int = 1) -> bool:
        """True si ya hay los PDFs que hacen falta. Si no, abre la pantalla de subida y, cuando estén cargados, ejecuta
        `action` sola (así se puede pulsar primero la herramienta y subir el archivo después)."""
        if len(self.uploaded_files) >= minimum:
            return True
        self._pending = (title, action, minimum)
        self.pick_page.show_for(title, minimum)
        self.stack.setCurrentWidget(self.pick_page)
        return False

    def cancel_pending(self):
        self._pending = None
        self._pending_timer.stop()

    def _run_pending(self):
        p = self._pending
        if p and len(self.uploaded_files) >= p[2]:
            self._pending = None
            p[1]()

    def go_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def add_files_any(self, paths: list):
        """Añade PDFs tal cual y convierte a PDF lo demás (fotos, texto, HTML, Word…). Las fotos se convierten una
        a una (cada una su PDF, con su tamaño) para poder ordenarlas o unirlas después. Lo que no se reconoce se avisa."""
        accepted = ptl.accepted_extensions()
        convert, unknown = [], []
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext == ".pdf":
                self.add_file(p, Path(p).name)
            elif ext in accepted:
                convert.append(p)
            elif p:
                unknown.append(Path(p).name)
        unknown_msg = ""
        if unknown:
            shown = ", ".join(unknown[:3]) + ("…" if len(unknown) > 3 else "")
            unknown_msg = tr(
                "No sé abrir: {shown}. Aceptados: PDF, fotos (JPG, PNG, TIFF, BMP, WEBP, GIF), texto, "
                "Markdown, HTML y, con LibreOffice, Word/Excel/PowerPoint.", shown=shown)
        if not convert:
            if unknown_msg:
                self.snack(unknown_msg, "error")
            return
        word_file = tr("archivo")
        self.snack(tr("Convirtiendo {n} {word_file}{s} a PDF…",
                       n=len(convert), word_file=word_file, s="s" if len(convert) != 1 else ""), "info")

        def work():
            fails = []
            for p in convert:
                try:
                    out = ptl.convert_one(p)
                    self.file_ready.emit(out, Path(out).name)
                except ptl.ToolError as e:
                    fails.append(f"{Path(p).name}: {e}")
                except Exception as e:
                    fails.append(f"{Path(p).name}: error inesperado ({e})")
            if fails or unknown_msg:
                self.notice.emit(" · ".join(fails + ([unknown_msg] if unknown_msg else []))[:500], "error")
        run_bg(work)

    def add_file(self, path: str, name: str):
        if not path or not Path(path).exists():
            self.snack(tr("No se pudo cargar: {name}", name=name), "error"); return
        pages = be.safe_page_count(path)
        locked = False
        if pages == 0:
            locked = ptl.is_locked(path)
            if locked:
                pages = 1
            else:
                self.snack(tr("PDF inválido: {name}", name=name), "error"); return
        self.uploaded_files.append({"name": name, "path": path, "pages": pages, "locked": locked})
        self.home_page.refresh_file_list()
        if self._pending:
            self.pick_page.show_for(self._pending[0], self._pending[2])
            self._pending_timer.start(500)
        if locked:
            self.snack(tr("🔒 {name} tiene contraseña: desbloquéalo en Proteger antes de usarlo.", name=name), "info")
        else:
            self.snack(tr("✓ {name} ({pages} pág.)", name=name, pages=pages))

    def remove_file_obj(self, f: dict):
        if f in self.uploaded_files:
            self.uploaded_files.remove(f)
            self.home_page.refresh_file_list()

    def reorder_files(self, new_order: list[dict]):
        self.uploaded_files = list(new_order)

    def closeEvent(self, e):
        ep = getattr(self, "edit_page", None)
        if not getattr(self, "_force_quit", False) and ep is not None and ep.dirty and ep.doc is not None:
            r = QMessageBox.question(self, tr("Cambios sin guardar"),
                                     tr("Tienes cambios sin guardar en el editor. ¿Guardarlos antes de salir?"),
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if r == QMessageBox.Cancel:
                e.ignore()
                return
            if r == QMessageBox.Save:
                ep._save_changes()
            dr.clear()
        elif not getattr(self, "_force_quit", False):
            dr.clear()
        super().closeEvent(e)

    def check_draft(self):
        """Al arrancar: si quedó un borrador (cierre brusco o reinicio pedido), lo recupera."""
        d = dr.load()
        if not d:
            return
        if not d.get("restart"):
            when = time.strftime("%d/%m/%Y %H:%M", time.localtime(d.get("time", 0)))
            r = QMessageBox.question(
                self, tr("Recuperar trabajo anterior"),
                tr("La aplicación se cerró sin guardar «{name}» (borrador del {when}).\n"
                   "¿Quieres continuar con el trabajo anterior?",
                   name=d.get('name', 'documento.pdf'), when=when),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if r != QMessageBox.Yes:
                dr.clear()
                return
        name = d.get("name") or "documento.pdf"
        dest = Path(tempfile.mkdtemp(prefix="recuperado_")) / name
        try:
            shutil.copy(d["path"], dest)
        except Exception:
            self.snack(tr("No se pudo recuperar el borrador."), "error")
            return
        self.uploaded_files.clear()
        self.add_file(str(dest), name)
        self.open_edit_view()
        ep = self.edit_page
        if ep.doc is not None:
            ep.dirty = bool(d.get("dirty", True))
            if ep.dirty:
                ep._write_draft()
            else:
                dr.clear()
            self.snack(tr("Documento reabierto") + (tr(" con tus cambios sin guardar.") if ep.dirty else "."), "success")

    def open_in_viewer(self, f: dict):
        QDesktopServices.openUrl(QUrl.fromLocalFile(f["path"]))

    def clear_all(self):
        self.uploaded_files.clear()
        self.home_page.refresh_file_list()
        self.clear_steps()

    def record_step(self, step_type: str, params: dict | None = None):
        """Registra en silencio cada herramienta aplicada, para poder
        guardar la secuencia como workflow. Seguro desde hilos (señal)."""
        self.session_steps.append(wf.new_step(step_type, params))
        self.steps_changed.emit()

    def clear_steps(self):
        self.session_steps.clear()
        self.saved_upto = 0
        self.saved_name = ""
        self.saved_id = ""
        self.steps_changed.emit()

    # ── «Guardar como…» (en vez de Descargas) ───────────────────────────────
    def request_save_as(self):
        self._save_as_pending = True

    def cancel_save_as(self):
        self._save_as_pending = False

    def relocate_output(self, path: str) -> str:
        """Si el usuario eligió «Guardar como…», mueve el resultado (ya creado en Descargas) adonde quiera. Con
        varios archivos seguidos, pregunta una vez y deja los demás en la misma carpeta."""
        folder = getattr(self, "_save_as_folder", None)
        if folder is None and not getattr(self, "_save_as_pending", False):
            return path
        src = Path(path)
        if folder is None:
            self._save_as_pending = False
            start_dir = getattr(self, "_last_save_dir", None) or Path.home() / "Documents"
            if not Path(start_dir).is_dir():
                start_dir = Path.home()
            ext = src.suffix
            dest, _ = QFileDialog.getSaveFileName(
                self, tr("Guardar como"), str(Path(start_dir) / src.name), f"{ext.lstrip('.').upper()} (*{ext})")
            if not dest:
                self.snack(tr("Se ha dejado en Descargas."), "info")
                return path
            dest = Path(dest)
            if dest.suffix.lower() != ext.lower():
                dest = dest.with_name(dest.name + ext)
            self._save_as_folder = dest.parent
            QTimer.singleShot(0, lambda: setattr(self, "_save_as_folder", None))
        else:
            dest = folder / src.name
            n = 2
            while dest.exists() and dest != src:
                dest = folder / f"{src.stem} ({n}){src.suffix}"
                n += 1
        self._last_save_dir = dest.parent
        if dest.resolve() != src.resolve():
            try:
                os.replace(src, dest)
            except OSError:
                shutil.copy2(src, dest)
                os.remove(src)
        return str(dest)

    def load_single_result(self, out_path: str):
        """Tras procesar: el resultado pasa a ser el único archivo cargado,
        listo para guardarlo o encadenar otra herramienta de la suite."""
        out_path = self.relocate_output(out_path)
        pages = be.safe_page_count(out_path)
        self.uploaded_files = [{"name": Path(out_path).name, "path": out_path, "pages": pages}]
        self.home_page.refresh_file_list()
        self.go_home()
        if Path(out_path).parent.resolve() == Path(be.DOWNLOADS).resolve():
            self.snack(tr("✓ {name} — guardado en Descargas. "
                          "Puedes guardarlo como o seguir con otra herramienta.", name=Path(out_path).name))
        else:
            self.snack(tr("✓ Guardado: {name}", name=str(out_path)))

    def replace_file(self, old_f: dict, new_path: str):
        """Sustituye un archivo concreto (p.ej. tras Edit/Metadata) por su
        versión procesada, sin tocar el resto de archivos cargados."""
        new_path = self.relocate_output(new_path)
        pages = be.safe_page_count(new_path)
        new_f = {"name": Path(new_path).name, "path": new_path, "pages": pages}
        if old_f in self.uploaded_files:
            self.uploaded_files[self.uploaded_files.index(old_f)] = new_f
        else:
            self.uploaded_files.append(new_f)
        self.home_page.refresh_file_list()
        return new_f

    def do_save_as_copy(self):
        if not self.uploaded_files:
            self.snack(tr("Añade al menos un PDF"), "error"); return
        src = self.uploaded_files[0]["path"]
        dest, _ = QFileDialog.getSaveFileName(
            self, tr("Guardar como"), self.uploaded_files[0]["name"], "PDF (*.pdf)")
        if not dest:
            return
        import shutil
        shutil.copy2(src, dest)
        self.snack(tr("✓ Guardado: {name}", name=Path(dest).name))

    def after_save(self, out_path: str):
        """Tras Merge/Organize: el resultado pasa a ser el archivo cargado."""
        self.load_single_result(out_path)

    # ── Acciones de la barra principal ──────────────────────────────────
    def do_merge_standalone(self):
        if not self.ensure_files("Unir", self.do_merge_standalone, 2):
            return
        paths = [f["path"] for f in self.uploaded_files]
        first = Path(self.uploaded_files[0]["name"]).stem
        out_name = f"{first}_Merged.pdf"
        dest = str(be.DOWNLOADS / out_name)
        be.merge_pdfs(paths, dest)
        self.record_step("merge")
        self.after_save(dest)

    def do_ajuste_standalone(self):
        if not self.ensure_files("Ajuste de imagen", self.do_ajuste_standalone, 1):
            return

        if len(self.uploaded_files) == 1:
            self._open_ajuste_for_file(self.uploaded_files[0], single=True)
            return

        opt_all = tr("Todos los archivos juntos (navegar como en un merge)")
        choice, ok = QInputDialog.getItem(
            self, tr("Ajuste de imagen"), tr("¿Qué quieres ajustar?"),
            [opt_all, tr("Solo un archivo suelto")],
            0, False)
        if not ok:
            return

        if choice == opt_all:
            dlg = AjusteMultiDialog(self.uploaded_files, self)
            if dlg.exec() == QDialog.Accepted and dlg.results:
                for fi, out in dlg.results.items():
                    self.snack(tr("✓ Ajuste: {name}", name=Path(out).name))
                    self.replace_file(self.uploaded_files[fi], out)
                if dlg.applied_params:
                    self.record_step("adjust", dlg.applied_params)
        else:
            names = [f["name"] for f in self.uploaded_files]
            name, ok2 = QInputDialog.getItem(
                self, tr("Elegir archivo"), tr("¿Qué PDF quieres ajustar?"), names, 0, False)
            if not ok2:
                return
            f = next((f for f in self.uploaded_files if f["name"] == name), None)
            if f:
                self._open_ajuste_for_file(f, single=False)

    def _open_ajuste_for_file(self, f: dict, single: bool):
        dlg = AjusteDialog(f["path"], self)
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            self.snack(tr("✓ Ajuste: {name}", name=Path(dlg.result_path).name))
            if dlg.applied_params:
                self.record_step("adjust", dlg.applied_params)
            if single:
                self.load_single_result(dlg.result_path)
            else:
                self.replace_file(f, dlg.result_path)

    # ── Navegación a vistas ──────────────────────────────────────────────
    def _locked_file(self):
        """Primer PDF cargado que aún tiene contraseña de apertura (las demás pantallas no pueden abrirlo)."""
        for f in self.uploaded_files:
            if f.get("locked"):
                return f
        return None

    def open_tool(self, name: str):
        """Abre una herramienta de archivo (Comprimir, Proteger, Marca de agua, Aplanar y reparar, Convertir a PDF u
        OCR). Salvo Convertir, necesita un PDF: si no hay, lo pide primero y la abre sola al subirlo."""
        if name != "Convertir a PDF" and not self.ensure_files(name, lambda: self.open_tool(name)):
            return
        self.tools_page.show_tool(name)
        self.stack.setCurrentWidget(self.tools_page)

    def open_organize_view(self):
        if not self.ensure_files("Organizar páginas", self.open_organize_view, 1):
            return
        lf = self._locked_file()
        if lf:
            self.snack(tr("«{name}» tiene contraseña: desbloquéalo en Proteger.", name=lf['name']), "error"); return
        self.organize_page.populate()
        self.stack.setCurrentWidget(self.organize_page)

    def open_compare_view(self):
        if not self.ensure_files("Comparar PDFs", self.open_compare_view, 1):
            return
        self.compare_page.populate()
        self.stack.setCurrentWidget(self.compare_page)

    def open_edit_view(self):
        if not self.ensure_files("Editor", self.open_edit_view, 1):
            return
        lf = self._locked_file()
        if lf:
            self.snack(tr("«{name}» tiene contraseña: desbloquéalo en Proteger.", name=lf['name']), "error"); return
        if not be.HAS_FITZ:
            self.snack(tr("PyMuPDF (fitz) no está instalado"), "error"); return
        self.edit_page.populate()
        self.stack.setCurrentWidget(self.edit_page)

    def open_metadata_view(self):
        if not self.ensure_files("Metadatos", self.open_metadata_view, 1):
            return
        lf = self._locked_file()
        if lf:
            self.snack(tr("«{name}» tiene contraseña: desbloquéalo en Proteger.", name=lf['name']), "error"); return
        if not be.HAS_FITZ:
            self.snack(tr("PyMuPDF (fitz) no está instalado"), "error"); return
        self.metadata_page.populate()
        self.stack.setCurrentWidget(self.metadata_page)

    def open_split_view(self):
        if not self.ensure_files("Dividir", self.open_split_view, 1):
            return
        lf = self._locked_file()
        if lf:
            self.snack(tr("«{name}» tiene contraseña: desbloquéalo en Proteger.", name=lf['name']), "error"); return
        self.split_page.populate()
        self.stack.setCurrentWidget(self.split_page)

    def open_size_margins_view(self):
        if not self.ensure_files("Tamaño y márgenes", self.open_size_margins_view, 1):
            return
        lf = self._locked_file()
        if lf:
            self.snack(tr("«{name}» tiene contraseña: desbloquéalo en Proteger.", name=lf['name']), "error"); return
        if not be.HAS_FITZ:
            self.snack(tr("PyMuPDF (fitz) no está instalado"), "error"); return
        self.size_margins_page.populate()
        self.size_margins_page.refresh_preview()
        self.stack.setCurrentWidget(self.size_margins_page)

    # ── Workflows ────────────────────────────────────────────────────────
    def open_workflows_view(self):
        self.workflows_page.populate()
        self.stack.setCurrentWidget(self.workflows_page)

    def save_session_as_workflow(self):
        if not self.session_steps:
            self.snack(tr("Aún no has aplicado ninguna herramienta"), "error"); return
        workflows = wf.load_workflows()
        dup = wf.find_duplicate(self.session_steps, workflows)
        if dup:
            self.saved_upto = len(self.session_steps)
            self.saved_name = dup["name"]
            self.saved_id = dup["id"]
            self.steps_changed.emit()
            QMessageBox.information(
                self, tr("Ya está guardado"),
                tr("Ya tienes el workflow «{name}» con exactamente estos pasos.", name=dup['name']))
            return
        dlg = WorkflowEditorDialog(self.session_steps, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_wf = wf.new_workflow(dlg.name, dlg.steps)
        workflows.append(new_wf)
        if wf.save_workflows(workflows):
            self.saved_upto = len(self.session_steps)
            self.saved_name = dlg.name
            self.saved_id = new_wf["id"]
            self.steps_changed.emit()
            self.snack(tr("✓ Workflow «{name}» guardado — lo tienes en Workflows", name=dlg.name))
        else:
            self.snack(tr("No se pudo guardar el workflow"), "error")

    def append_session_to_saved(self):
        """Añade al workflow ya guardado solo los pasos aplicados después."""
        workflows = wf.load_workflows()
        target = next((w for w in workflows if w["id"] == self.saved_id), None)
        new_steps = self.session_steps[self.saved_upto:]
        if target is None:
            self.snack(tr("Ese workflow ya no existe: guárdalo como nuevo"), "error")
            self.saved_id = ""
            self.steps_changed.emit()
            return
        if not new_steps:
            return
        dlg = WorkflowEditorDialog(new_steps, target["name"], self,
                                   title=tr("Añadir pasos a «{name}»", name=target['name']))
        if dlg.exec() != QDialog.Accepted:
            return
        target["steps"].extend(dlg.steps)
        target["name"] = dlg.name
        if wf.save_workflows(workflows):
            self.saved_upto = len(self.session_steps)
            self.saved_name = target["name"]
            self.steps_changed.emit()
            self.snack(tr("✓ {n} paso(s) añadidos a «{name}»", n=len(dlg.steps), name=target['name']))
        else:
            self.snack(tr("No se pudo guardar el workflow"), "error")

    def run_workflow(self, w: dict):
        files = [f["path"] for f in self.uploaded_files]
        if not files:
            files, _ = QFileDialog.getOpenFileNames(
                self, tr("Archivos para «{name}»", name=w['name']), "", "PDF (*.pdf)")
            if not files:
                return
        fields = wf.prompt_fields(w["steps"])
        values: dict[int, dict] = {}
        if fields:
            dlg = AskValuesDialog(w, fields, self)
            if dlg.exec() != QDialog.Accepted:
                return
            values = dlg.values
        prog = QProgressDialog(tr("Ejecutando «{name}»…", name=w['name']), None, 0, 0, self)
        prog.setWindowTitle("Workflow")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setCancelButton(None)
        prog.show()
        self._wf_progress = prog
        steps = copy.deepcopy(w["steps"])

        def _job():
            try:
                outs, warns = wf.run_workflow(
                    steps, files, values,
                    progress=lambda i, n, label: self.workflow_progress.emit(
                        tr("Paso {i} de {n}: {label}", i=min(i + 1, n), n=n, label=label)))
            except Exception as e:
                outs, warns = [], [tr("Error inesperado: {e}", e=e)]
            self.workflow_done.emit(outs, warns)

        run_bg(_job)

    def _on_workflow_progress(self, text: str):
        if self._wf_progress is not None:
            self._wf_progress.setLabelText(text)

    def _on_workflow_done(self, outs: list, warns: list):
        if self._wf_progress is not None:
            self._wf_progress.close()
            self._wf_progress = None
        if outs:
            self.uploaded_files = [
                {"name": Path(o).name, "path": o, "pages": be.safe_page_count(o)} for o in outs]
            self.home_page.refresh_file_list()
            self.go_home()
            self.snack(tr("✓ Workflow terminado: {n} archivo(s) en Descargas", n=len(outs)))
        else:
            self.snack(tr("El workflow no generó ningún archivo"), "error")
        if warns:
            QMessageBox.information(self, tr("Avisos del workflow"), "\n".join(f"• {w}" for w in warns))

    def open_nup_view(self):
        if not self.ensure_files("Varias por hoja", self.open_nup_view, 1):
            return
        lf = self._locked_file()
        if lf:
            self.snack(tr("«{name}» tiene contraseña: desbloquéalo en Proteger.", name=lf['name']), "error"); return
        if not be.HAS_FITZ:
            self.snack(tr("PyMuPDF (fitz) no está instalado"), "error"); return
        self.nup_page.populate()
        self.nup_page.refresh_preview()
        self.stack.setCurrentWidget(self.nup_page)


def main():
    if sys.platform == "win32":
        # Sin esto, Windows agrupa la ventana bajo el icono de python.exe en
        # la barra de tareas en vez de usar el nuestro (setWindowIcon).
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Provecto.PDFManager.1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    if i18n.LANG != "en":                         # menús y botones estándar de Qt (Cortar, Copiar, Pegar…) en el idioma elegido
        try:
            from PySide6.QtCore import QTranslator, QLibraryInfo
            _tr = QTranslator()
            qt_lang = {"es": "qtbase_es", "pt": "qtbase_pt"}.get(i18n.LANG)
            if qt_lang and _tr.load(qt_lang, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
                app.installTranslator(_tr)
                app._qt_translator = _tr
        except Exception:
            pass
    icon_path = be.resource_path("provecto_icon.ico")
    if Path(icon_path).is_file():
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    QTimer.singleShot(500, win.check_draft)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
