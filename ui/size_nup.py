# -*- coding: utf-8 -*-
"""Pantallas Tamaño y márgenes y Varias por hoja (N-Up)."""
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QSpinBox,
    QDoubleSpinBox,
)

import backend as be
from i18n import tr
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pdf_qt import MainWindow
from ui.common import _save_btn, add_shadow, ask_scope
from ui.widgets import BackHeader, PreviewPanel


class SizeMarginsPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader(tr("Tamaño y márgenes"), lambda: win.go_home()))

        self.file_row = QWidget()
        fr = QHBoxLayout(self.file_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.addWidget(QLabel(tr("Archivo:")))
        self.file_combo = QComboBox()
        fr.addWidget(self.file_combo, 1)
        root.addWidget(self.file_row)

        self._mode = "size"
        self.preview = PreviewPanel(self._render_preview, tr("Página"))
        self.preview.set_caption(tr("Vista previa · tamaño"))
        self.file_combo.currentIndexChanged.connect(self.refresh_preview)
        body = QHBoxLayout(); body.setSpacing(16)
        left = QVBoxLayout()

        # ── Tamaño de página ──────────────────────────────────────────
        size_card = QFrame(); size_card.setObjectName("Card")
        add_shadow(size_card, blur=18, dy=4, alpha=70)
        sc = QVBoxLayout(size_card)
        title1 = QLabel(tr("Cambiar tamaño de página")); title1.setObjectName("SectionTitle")
        sc.addWidget(title1)

        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A5", "A3", "Carta (Letter)", "Legal", "Personalizado"])
        self.size_combo.currentTextChanged.connect(self._on_size_choice_changed)
        self.size_combo.currentTextChanged.connect(lambda *_: self._touch("size"))
        sc.addWidget(self.size_combo)

        self.custom_row_widget = QWidget()
        custom_row = QHBoxLayout(self.custom_row_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        self.custom_w = QDoubleSpinBox(); self.custom_w.setRange(10, 2000)
        self.custom_w.setValue(210); self.custom_w.setSuffix(" mm")
        self.custom_h = QDoubleSpinBox(); self.custom_h.setRange(10, 2000)
        self.custom_h.setValue(297); self.custom_h.setSuffix(" mm")
        custom_row.addWidget(QLabel(tr("Ancho:"))); custom_row.addWidget(self.custom_w)
        custom_row.addWidget(QLabel(tr("Alto:")));  custom_row.addWidget(self.custom_h)
        self.custom_row_widget.setVisible(False)
        self.custom_w.valueChanged.connect(lambda *_: self._touch("size"))
        self.custom_h.valueChanged.connect(lambda *_: self._touch("size"))
        sc.addWidget(self.custom_row_widget)

        fit_row = QHBoxLayout()
        self.fit_scale_radio  = QRadioButton(tr("Escalar contenido para llenar la hoja"))
        self.fit_center_radio = QRadioButton(tr("Mantener tamaño original y centrar"))
        self.fit_scale_radio.setChecked(True)
        fgroup = QButtonGroup(self)
        fgroup.addButton(self.fit_scale_radio); fgroup.addButton(self.fit_center_radio)
        fit_row.addWidget(self.fit_scale_radio); fit_row.addWidget(self.fit_center_radio)
        self.fit_scale_radio.toggled.connect(lambda *_: self._touch("size"))
        sc.addLayout(fit_row)

        resize_btn = _save_btn(tr("Aplicar tamaño"), "resize", "Primary")
        resize_btn.clicked.connect(self._do_resize)
        sc.addWidget(resize_btn)
        left.addWidget(size_card)

        # ── Márgenes ──────────────────────────────────────────────────
        margin_card = QFrame(); margin_card.setObjectName("Card")
        add_shadow(margin_card, blur=18, dy=4, alpha=70)
        mc = QVBoxLayout(margin_card)
        title2 = QLabel(tr("Cambiar márgenes")); title2.setObjectName("SectionTitle")
        mc.addWidget(title2)
        hint = QLabel(tr("Valores positivos añaden margen en blanco en ese borde; "
                       "valores negativos recortan ese borde de la página."))
        hint.setObjectName("Hint"); hint.setWordWrap(True)
        mc.addWidget(hint)

        grid_row = QHBoxLayout()
        self.margin_top    = self._mm_spin()
        self.margin_bottom = self._mm_spin()
        self.margin_left   = self._mm_spin()
        self.margin_right  = self._mm_spin()
        for label, field in ((tr("Arriba"), self.margin_top), (tr("Abajo"), self.margin_bottom),
                              (tr("Izquierda"), self.margin_left), (tr("Derecha"), self.margin_right)):
            col = QVBoxLayout()
            lbl = QLabel(label); lbl.setObjectName("Hint")
            col.addWidget(lbl)
            col.addWidget(field)
            grid_row.addLayout(col)
        mc.addLayout(grid_row)
        for sp in (self.margin_top, self.margin_bottom, self.margin_left, self.margin_right):
            sp.valueChanged.connect(lambda *_: self._touch("margins"))

        margin_btn = _save_btn(tr("Aplicar márgenes"), "crop", "Primary")
        margin_btn.clicked.connect(self._do_margins)
        mc.addWidget(margin_btn)
        left.addWidget(margin_card)
        left.addStretch(1)
        body.addLayout(left, 1)
        body.addWidget(self.preview, 1)
        root.addLayout(body, 1)

    def _touch(self, mode: str):
        self._mode = mode
        self.preview.set_caption(tr("Vista previa · tamaño") if mode == "size"
                                  else tr("Vista previa · márgenes"))
        self.preview.schedule()

    def refresh_preview(self, *_):
        f = self._selected_file()
        self.preview.set_total(f["pages"] if f else 1)
        self.preview.schedule()

    def _render_preview(self, idx: int):
        f = self._selected_file()
        if not f:
            return None
        if self._mode == "margins":
            return be.preview_margins_png(
                f["path"], idx, self.margin_top.value(), self.margin_bottom.value(),
                self.margin_left.value(), self.margin_right.value())
        fit_mode = "scale" if self.fit_scale_radio.isChecked() else "center"
        return be.preview_resize_png(
            f["path"], idx, self.size_combo.currentText(), fit_mode,
            custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value())

    def _mm_spin(self) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(-100.0, 100.0)
        sp.setValue(0.0)
        sp.setSuffix(" mm")
        sp.setSingleStep(5.0)
        return sp

    def _on_size_choice_changed(self, text: str):
        self.custom_row_widget.setVisible(text == "Personalizado")

    def populate(self):
        self.file_row.setVisible(len(self.win.uploaded_files) > 1)
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _targets(self, scope: str) -> list:
        if scope == "all":
            return list(self.win.uploaded_files)
        f = self._selected_file()
        return [f] if f else []

    def _batch(self, call, start_msg: str, ok_label: str):
        f = self._selected_file()
        if not f:
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        scope = ask_scope(self, self.win, f["name"])
        if not scope:
            return
        targets = self._targets(scope)
        oks, fails = [], []
        for t in targets:
            out = call(t)
            (oks if out else fails).append(t)
        self.populate()
        self.refresh_preview()
        if oks:
            msg = tr("✓ {ok_label} en {n} archivo{s}.", ok_label=ok_label, n=len(oks),
                     s=('s' if len(oks) != 1 else ''))
            if fails:
                msg += tr(" ({n} con error)", n=len(fails))
            self.win.snack(msg, "success" if not fails else "info")
        else:
            self.win.snack(tr("No se pudo: {label}.", label=ok_label.lower()), "error")

    def _do_resize(self):
        size_name = self.size_combo.currentText()
        fit_mode = "scale" if self.fit_scale_radio.isChecked() else "center"

        def call(f):
            out = be.resize_pdf(f["path"], size_name, fit_mode,
                                custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value())
            if out:
                self.win.record_step("resize", {
                    "size_name": size_name, "fit_mode": fit_mode,
                    "custom_w_mm": self.custom_w.value(), "custom_h_mm": self.custom_h.value()})
                self.win.replace_file(f, out)
            return out
        self._batch(call, tr("Cambiando tamaño…"), tr("Tamaño aplicado"))

    def _do_margins(self):
        top, bottom, left, right = (self.margin_top.value(), self.margin_bottom.value(),
                                    self.margin_left.value(), self.margin_right.value())

        def call(f):
            out = be.adjust_margins_pdf(f["path"], top_mm=top, bottom_mm=bottom, left_mm=left, right_mm=right)
            if out:
                self.win.record_step("margins", {"top_mm": top, "bottom_mm": bottom, "left_mm": left, "right_mm": right})
                self.win.replace_file(f, out)
            return out
        self._batch(call, tr("Aplicando márgenes…"), tr("Márgenes aplicados"))
        for sp in (self.margin_top, self.margin_bottom, self.margin_left, self.margin_right):
            sp.setValue(0.0)


# ══════════════════════════════════════════════════════════════════════════
#  PÁGINA: N-UP (varias páginas por hoja)
# ══════════════════════════════════════════════════════════════════════════
class NUpPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(BackHeader(tr("N-Up – Varias páginas por hoja"), lambda: win.go_home()))

        self.file_lbl = QLabel(tr("Archivo:"))
        root.addWidget(self.file_lbl)
        self.file_combo = QComboBox()
        root.addWidget(self.file_combo)
        self._merge_dir = tempfile.mkdtemp(prefix="pdfmgr_nup_")
        self._merge_key: tuple | None = None
        self._merge_info: dict | None = None

        self.preview = PreviewPanel(self._render_preview, tr("Hoja"))
        self.preview.set_caption(tr("Vista previa · hoja de salida"))
        self.file_combo.currentIndexChanged.connect(self.refresh_preview)
        body = QHBoxLayout(); body.setSpacing(16)
        left = QVBoxLayout()

        card = QFrame(); card.setObjectName("Card")
        add_shadow(card, blur=18, dy=4, alpha=70)
        c = QVBoxLayout(card)

        grid_row = QHBoxLayout()
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(1, 6); self.cols_spin.setValue(2)
        self.rows_spin = QSpinBox(); self.rows_spin.setRange(1, 6); self.rows_spin.setValue(2)
        self.cols_spin.valueChanged.connect(self._update_total_label)
        self.rows_spin.valueChanged.connect(self._update_total_label)
        self.cols_spin.valueChanged.connect(self.refresh_preview)
        self.rows_spin.valueChanged.connect(self.refresh_preview)
        grid_row.addWidget(QLabel(tr("Columnas:"))); grid_row.addWidget(self.cols_spin)
        grid_row.addWidget(QLabel(tr("Filas:")));    grid_row.addWidget(self.rows_spin)
        c.addLayout(grid_row)

        self.total_label = QLabel()
        self.total_label.setObjectName("Hint")
        c.addWidget(self.total_label)

        c.addWidget(QLabel(tr("Tamaño de la hoja de salida:")))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A5", "A3", "Carta (Letter)", "Legal", "Personalizado"])
        self.size_combo.currentTextChanged.connect(self._on_size_choice_changed)
        self.size_combo.currentTextChanged.connect(lambda *_: self.preview.schedule())
        c.addWidget(self.size_combo)

        self.custom_row_widget = QWidget()
        custom_row = QHBoxLayout(self.custom_row_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        self.custom_w = QDoubleSpinBox(); self.custom_w.setRange(10, 2000)
        self.custom_w.setValue(297); self.custom_w.setSuffix(" mm")
        self.custom_h = QDoubleSpinBox(); self.custom_h.setRange(10, 2000)
        self.custom_h.setValue(210); self.custom_h.setSuffix(" mm")
        custom_row.addWidget(QLabel(tr("Ancho:"))); custom_row.addWidget(self.custom_w)
        custom_row.addWidget(QLabel(tr("Alto:")));  custom_row.addWidget(self.custom_h)
        self.custom_row_widget.setVisible(False)
        self.custom_w.valueChanged.connect(lambda *_: self.preview.schedule())
        self.custom_h.valueChanged.connect(lambda *_: self.preview.schedule())
        c.addWidget(self.custom_row_widget)

        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel(tr("Orientación de la hoja:")))
        self.orient_combo = QComboBox()
        self.orient_combo.addItem(tr("Automática"), "auto")
        self.orient_combo.addItem(tr("Vertical"), "portrait")
        self.orient_combo.addItem(tr("Horizontal"), "landscape")
        self.orient_combo.setToolTip(tr("Automática: elige la orientación en la que las páginas salen más grandes"))
        self.orient_combo.currentIndexChanged.connect(lambda *_: self.preview.schedule())
        orient_row.addWidget(self.orient_combo, 1)
        c.addLayout(orient_row)

        self.rotate_check = QCheckBox(tr("Girar páginas para aprovechar mejor la hoja"))
        self.rotate_check.setChecked(True)
        self.rotate_check.setToolTip(tr("Si una página llena mejor su celda girada 90°, se gira "
                                     "(útil con documentos de páginas mezcladas)"))
        self.rotate_check.toggled.connect(lambda *_: self.preview.schedule())
        c.addWidget(self.rotate_check)

        gap_row = QHBoxLayout()
        gap_row.addWidget(QLabel(tr("Espacio entre páginas:")))
        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setDecimals(1)
        self.gap_spin.setSingleStep(0.5)
        self.gap_spin.setRange(-0.5, 30)
        self.gap_spin.setSuffix(" mm")
        self.gap_spin.setSpecialValueText(tr("Auto"))
        self.gap_spin.setValue(-0.5)
        gap_row.addWidget(self.gap_spin)
        self.gap_spin.valueChanged.connect(lambda *_: self.preview.schedule())
        c.addLayout(gap_row)

        left.addWidget(card)

        apply_btn = _save_btn(tr("Aplicar N-Up"), "nup", "Primary")
        apply_btn.clicked.connect(self._do_nup)
        left.addWidget(apply_btn)
        left.addStretch(1)
        body.addLayout(left, 1)
        body.addWidget(self.preview, 1)
        root.addLayout(body, 1)

        self._update_total_label()

    def _update_total_label(self, *_):
        n = self.cols_spin.value() * self.rows_spin.value()
        self.total_label.setText(tr("= {n} página(s) por hoja", n=n))

    def _gap_value(self) -> float | None:
        """None = 'Auto' (valor mínimo del campo, que se muestra como texto)."""
        v = self.gap_spin.value()
        return None if v <= self.gap_spin.minimum() else v

    def _orientation(self) -> str:
        return self.orient_combo.currentData() or "auto"

    def _update_gap_tooltip(self, orientation: str = "portrait"):
        v = be.auto_gap_mm(self.size_combo.currentText(), self.custom_w.value(),
                           self.custom_h.value(), self.cols_spin.value(), self.rows_spin.value(),
                           orientation)
        self.gap_spin.setToolTip(
            tr("Auto: ahora {v:.1f} mm (3 mm, reducido hasta 0 si la cuadrícula necesita el sitio)", v=v))

    def _source(self) -> dict | None:
        """Con varios archivos cargados, N-Up trabaja sobre su unión (en el
        orden de la lista); con uno solo, sobre el archivo elegido."""
        files = self.win.uploaded_files
        if not files:
            return None
        if len(files) == 1:
            return self._selected_file() or files[0]
        key = tuple(f["path"] for f in files)
        if self._merge_key != key:
            out = str(Path(self._merge_dir) / f"{Path(files[0]['name']).stem}_Merged.pdf")
            be.merge_pdfs([f["path"] for f in files], out)
            self._merge_key = key
            self._merge_info = {"name": Path(out).name, "path": out,
                                "pages": be.safe_page_count(out)}
        return self._merge_info

    def refresh_preview(self, *_):
        n_files = len(self.win.uploaded_files)
        multi = n_files > 1
        self.file_combo.setVisible(not multi)
        src = self._source()
        pages = src["pages"] if src else 1
        self.file_lbl.setText(
            tr("Se unirán {n_files} archivos en el orden de la lista ({pages} páginas) "
            "y después se aplicará N-Up", n_files=n_files, pages=pages) if multi else tr("Archivo:"))
        per_sheet = self.cols_spin.value() * self.rows_spin.value()
        self.preview.set_total(-(-pages // per_sheet))
        self.preview.schedule()

    def _render_preview(self, idx: int):
        f = self._source()
        if not f:
            return None
        ori = be.nup_resolved_orientation(
            f["path"], self.cols_spin.value(), self.rows_spin.value(),
            self.size_combo.currentText(), self.custom_w.value(), self.custom_h.value(),
            self._gap_value(), self._orientation(), self.rotate_check.isChecked())
        self._update_gap_tooltip(ori)
        self.preview.set_caption(
            tr("Vista previa · hoja {orient}",
               orient=tr("horizontal") if ori == "landscape" else tr("vertical")))
        return be.preview_nup_png(
            f["path"], idx, self.cols_spin.value(), self.rows_spin.value(),
            size_name=self.size_combo.currentText(),
            custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value(),
            gap_mm=self._gap_value(), orientation=self._orientation(),
            auto_rotate=self.rotate_check.isChecked())

    def _on_size_choice_changed(self, text: str):
        self.custom_row_widget.setVisible(text == "Personalizado")

    def populate(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in self.win.uploaded_files:
            self.file_combo.addItem(f["name"])
        self.file_combo.blockSignals(False)

    def _selected_file(self) -> dict | None:
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self.win.uploaded_files):
            return None
        return self.win.uploaded_files[idx]

    def _do_nup(self):
        f = self._source()
        if not f:
            self.win.snack(tr("Selecciona un archivo"), "error"); return
        multi = len(self.win.uploaded_files) > 1
        out = be.n_up_pdf(
            f["path"], cols=self.cols_spin.value(), rows=self.rows_spin.value(),
            size_name=self.size_combo.currentText(),
            custom_w_mm=self.custom_w.value(), custom_h_mm=self.custom_h.value(),
            gap_mm=self._gap_value(), orientation=self._orientation(),
            auto_rotate=self.rotate_check.isChecked())
        if out:
            if multi:
                self.win.record_step("merge")
            self.win.record_step("nup", {
                "cols": self.cols_spin.value(), "rows": self.rows_spin.value(),
                "size_name": self.size_combo.currentText(),
                "custom_w_mm": self.custom_w.value(), "custom_h_mm": self.custom_h.value(),
                "gap_mm": self._gap_value(), "orientation": self._orientation(),
                "auto_rotate": self.rotate_check.isChecked()})
        if out and multi:
            self.win.load_single_result(out)
        elif out:
            self.win.replace_file(f, out)
            self.populate()
            self.refresh_preview()
            self.win.snack(tr("✓ N-Up aplicado: {name}", name=Path(out).name))
        else:
            self.win.snack(tr("No se pudo aplicar N-Up"), "error")
