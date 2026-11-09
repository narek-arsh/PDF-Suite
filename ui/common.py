# -*- coding: utf-8 -*-
"""Utilidades compartidas de la interfaz: botones, hilos, sombras y logo."""
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRectF, Signal, QThread, QObject
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor
from PySide6.QtWidgets import QPushButton, QMessageBox, QGraphicsDropShadowEffect

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

import backend as be
import icons as ic
import pdf_tools as ptl
from theme import TEXT, ON_ACCENT
from i18n import tr


ICON_DARK = ON_ACCENT   # para iconos sobre fondo de acento (botones Primary); se adapta al modo claro/oscuro


def _btn(text: str, icon_name: str | None = None, object_name: str | None = None,
         icon_color: str | None = None, size: int = 17) -> QPushButton:
    """Crea un QPushButton con un icono vectorial propio (sin emoji)."""
    b = QPushButton(("  " + text) if (icon_name and text) else text)
    if object_name:
        b.setObjectName(object_name)
    if icon_name:
        color = icon_color or (ICON_DARK if object_name == "Primary" else TEXT)
        b.setIcon(ic.icon(icon_name, color, size))
        b.setIconSize(QSize(size, size))
    return b

FILE_COLORS = be.FILE_COLORS


# ── Helpers genéricos ───────────────────────────────────────────────────
def pil_to_qpixmap(img) -> QPixmap:
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


def run_bg(fn, *args, **kwargs):
    threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()


class _GuiBridge(QObject):
    """Deja que un hilo secundario pida que algo se ejecute en el hilo de la pantalla (Qt no admite tocar la
    interfaz desde otro hilo: da «Timers cannot be stopped from another thread» y cuelgues)."""
    run = Signal(object)

    def __init__(self):
        super().__init__()
        self.run.connect(lambda fn: fn())


_GUI_BRIDGE = None


def init_bridge():
    """Crea el puente al hilo de la pantalla (hay que llamarlo desde ese hilo)."""
    global _GUI_BRIDGE
    _GUI_BRIDGE = _GuiBridge()


def on_gui(fn):
    """Ejecuta fn() en el hilo de la pantalla; se puede llamar desde cualquier hilo."""
    if _GUI_BRIDGE is not None:
        _GUI_BRIDGE.run.emit(fn)
    else:
        fn()


_LOGO_CACHE: dict[int, QPixmap] = {}


def provecto_logo_pixmap(size: int = 40) -> QPixmap | None:
    """Renderiza el logo de Provecto (SVG) a un QPixmap cuadrado, cacheado."""
    if size in _LOGO_CACHE:
        return _LOGO_CACHE[size]
    svg_path = be.resource_path("provecto_logo.svg")
    pix = None
    if HAS_SVG and Path(svg_path).is_file():
        renderer = QSvgRenderer(svg_path)
        if renderer.isValid():
            img = QImage(size, size, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            renderer.render(p, QRectF(0, 0, size, size))
            p.end()
            pix = QPixmap.fromImage(img)
    _LOGO_CACHE[size] = pix
    return pix


def add_shadow(widget, blur=24, dy=6, alpha=90):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def glow(widget, color: str, blur: int = 36, alpha: int = 140):
    """Halo de color (sin desplazamiento) para dar relieve a logos y botones destacados."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    c = QColor(color)
    c.setAlpha(alpha)
    effect.setColor(c)
    widget.setGraphicsEffect(effect)
    return effect


class _ToolJob(QThread):
    """Ejecuta una operación pesada fuera del hilo de la ventana."""
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.finished_ok.emit(self._fn(lambda i, n: self.progress.emit(i, n)))
        except ptl.ToolError as e:
            self.failed.emit(str(e))
        except Exception as e:                                  # fallo inesperado: se cuenta, no se traga
            self.failed.emit(tr("Ha ocurrido un error inesperado: {e}", e=e))


def _human_size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def ask_scope(parent, win, current_name: str | None = None):
    """'all' | 'one' | None (cancelado). Solo pregunta si hay más de un archivo subido; con uno o ninguno,
    devuelve 'one' sin preguntar nada."""
    n = len(win.uploaded_files)
    if n <= 1:
        return "one"
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(tr("¿A qué archivos?"))
    box.setText(tr("Tienes {n} archivos subidos. ¿Aplicar esto a todos o solo al elegido ahora"
               "{current}?", n=n, current=(' (' + current_name + ')') if current_name else ''))
    all_btn = box.addButton(tr("A todos"), QMessageBox.AcceptRole)
    one_btn = box.addButton(tr("Solo a este"), QMessageBox.AcceptRole)
    box.addButton(tr("Cancelar"), QMessageBox.RejectRole)
    box.setDefaultButton(one_btn)
    box.exec()
    clicked = box.clickedButton()
    if clicked is all_btn:
        return "all"
    if clicked is one_btn:
        return "one"
    return None


# ══════════════════════════════════════════════════════════════════════════
#  WORKFLOWS (macros): guardar, editar, ejecutar
# ══════════════════════════════════════════════════════════════════════════
_LIST_SELECT_QSS = (
    f"QListWidget::item {{ border-radius: 8px; padding: 6px 8px; color: {TEXT}; }}"
    f"QListWidget::item:selected {{ background-color: rgba(192,130,88,0.28); color: {TEXT}; }}"
    f"QListWidget::item:hover {{ background-color: rgba(243,241,228,0.06); color: {TEXT}; }}")
