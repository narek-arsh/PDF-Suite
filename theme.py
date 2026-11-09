# -*- coding: utf-8 -*-
"""Paleta de marca Provecto (modo oscuro y modo claro) y hoja de estilos QSS global."""
import json
import os
from pathlib import Path

FONT_FAMILY = "Segoe UI, Inter, Arial, sans-serif"

CONFIG_PATH = Path(os.environ.get("APPDATA") or Path.home()) / "PDFManager" / "config.json"

PALETTES = {
    "dark": dict(
        BG="#15170F", BG_GRAD_TOP="#181B10", BG_GRAD_BOTTOM="#0F110A",
        SURFACE="#262A1C", SURFACE_2="#333823", SURFACE_3="#454A30",
        GLASS_CARD="rgba(255,255,255,0.05)", GLASS_BORDER="rgba(255,255,255,0.12)",
        TEXT="#F6F3E7", TEXT_SOFT="#AEB38A",
        ACCENT="#E08A4F", ACCENT_HOV="#F39B5C", ACCENT_SOFT="rgba(224,138,79,0.18)",
        ACCENT2="#3FC1AC", ACCENT2_HOV="#55D4BE", ACCENT2_SOFT="rgba(63,193,172,0.18)",
        ACCENT3="#B870D6", ACCENT3_HOV="#C98AE3", ACCENT3_SOFT="rgba(184,112,214,0.18)",
        SECONDARY="#6E7355",
        BORDER="rgba(243,241,228,0.14)", BORDER_STRONG="rgba(243,241,228,0.24)",
        DANGER="#D47268", DANGER_HOV="#B85A50",
        ON_ACCENT="#1A0F06",
        ORB1=(224, 138, 79, 70), ORB2=(63, 193, 172, 55), ORB3=(184, 112, 214, 45),
    ),
    "light": dict(
        BG="#F3EFE2", BG_GRAD_TOP="#FBF8EF", BG_GRAD_BOTTOM="#F1ECDD",
        SURFACE="#FDFBF4", SURFACE_2="#F1ECDC", SURFACE_3="#E7E0CB",
        GLASS_CARD="rgba(255,255,255,0.60)", GLASS_BORDER="rgba(40,35,20,0.10)",
        TEXT="#2B2A1E", TEXT_SOFT="#6E7054",
        ACCENT="#C9703A", ACCENT_HOV="#B8602E", ACCENT_SOFT="rgba(201,112,58,0.14)",
        ACCENT2="#1C9A84", ACCENT2_HOV="#167A69", ACCENT2_SOFT="rgba(28,154,132,0.14)",
        ACCENT3="#9A4FC7", ACCENT3_HOV="#8540AD", ACCENT3_SOFT="rgba(154,79,199,0.14)",
        SECONDARY="#B8AE86",
        BORDER="rgba(40,35,20,0.12)", BORDER_STRONG="rgba(40,35,20,0.22)",
        DANGER="#C8564C", DANGER_HOV="#B04339",
        ON_ACCENT="#FFF8EE",
        ORB1=(224, 138, 79, 55), ORB2=(28, 154, 132, 42), ORB3=(154, 79, 199, 35),
    ),
}


def load_mode() -> str:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        mode = data.get("theme")
        if mode in PALETTES:
            return mode
    except Exception:
        pass
    return "dark"


def save_mode(mode: str) -> None:
    if mode not in PALETTES:
        return
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CONFIG_PATH.is_file():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["theme"] = mode
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def other_mode(mode: str) -> str:
    return "light" if mode == "dark" else "dark"


def _build_qss(p: dict) -> str:
    return f"""
* {{
    font-family: {FONT_FAMILY};
}}

QMainWindow {{
    background: transparent;
}}

QDialog, QWidget#RootView {{
    background-color: {p['BG']};
}}

QWidget {{
    color: {p['TEXT']};
}}

QLabel#Header {{
    font-size: 21px;
    font-weight: 800;
    color: {p['TEXT']};
    letter-spacing: 0.2px;
}}

QLabel#SubHeader {{
    font-size: 12px;
    font-weight: 700;
    color: {p['ACCENT']};
}}

QLabel#SectionTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {p['TEXT']};
    border-left: 3px solid {p['ACCENT']};
    padding-left: 9px;
}}

QLabel#Hint {{
    font-size: 11.5px;
    color: {p['TEXT_SOFT']};
}}

QLabel#Badge {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['ACCENT_HOV']}, stop:1 {p['ACCENT']});
    color: {p['ON_ACCENT']};
    border-radius: 11px;
    font-size: 17px;
    font-weight: 800;
}}

QLabel#Tag {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['ACCENT2_SOFT']}, stop:1 transparent);
    color: {p['ACCENT2']};
    border: 1px solid {p['ACCENT2']};
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}

QFrame#Card {{
    background-color: {p['GLASS_CARD']};
    border: 1px solid {p['GLASS_BORDER']};
    border-radius: 14px;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {p['SURFACE_2']};
    color: {p['TEXT']};
    border: 1px solid {p['BORDER_STRONG']};
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {p['ACCENT']};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {p['ACCENT']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p['SURFACE_2']};
    color: {p['TEXT']};
    selection-background-color: {p['ACCENT']};
    selection-color: {p['ON_ACCENT']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
}}

QPushButton {{
    background-color: {p['SURFACE_3']};
    color: {p['TEXT']};
    border: 1px solid {p['BORDER_STRONG']};
    border-bottom: 2px solid rgba(0,0,0,0.22);
    border-radius: 10px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton:hover {{
    border: 1px solid {p['ACCENT']};
    border-bottom: 2px solid {p['ACCENT']};
    background-color: {p['ACCENT_SOFT']};
    color: {p['TEXT']};
}}

QPushButton:pressed {{
    background-color: {p['BG']};
    border-bottom: 1px solid {p['ACCENT']};
}}

QPushButton:disabled {{
    color: {p['TEXT_SOFT']};
    border-bottom: 2px solid rgba(0,0,0,0.22);
    background-color: {p['SURFACE_2']};
}}

QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p['ACCENT_HOV']}, stop:1 {p['ACCENT']});
    color: {p['ON_ACCENT']};
    border: none;
    border-bottom: 2px solid rgba(0,0,0,0.28);
    font-weight: 700;
}}

QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p['ACCENT']}, stop:1 {p['ACCENT_HOV']});
    border-bottom: 2px solid rgba(0,0,0,0.28);
}}

QPushButton#Secondary {{
    background-color: transparent;
    color: {p['ACCENT']};
    border: 1.5px solid {p['ACCENT']};
    border-bottom: 1.5px solid {p['ACCENT']};
    font-weight: 700;
}}

QPushButton#Secondary:hover {{
    background-color: {p['ACCENT_SOFT']};
    color: {p['TEXT']};
}}

QPushButton#Secondary:checked {{
    background-color: {p['ACCENT']};
    color: {p['ON_ACCENT']};
}}

QPushButton#Danger {{
    background-color: transparent;
    color: {p['DANGER']};
    border: 1.5px solid {p['DANGER']};
    border-bottom: 1.5px solid {p['DANGER']};
}}

QPushButton#Danger:hover {{
    background-color: {p['DANGER']};
    color: {p['TEXT']};
}}

QPushButton#Flat {{
    background-color: transparent;
    border: none;
    color: {p['TEXT_SOFT']};
    padding: 6px 4px;
    font-weight: 600;
}}

QPushButton#Flat:hover {{
    color: {p['ACCENT']};
    background-color: transparent;
}}

QFrame#Toolbar {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
}}

QTabWidget::pane {{
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    background: {p['SURFACE']};
    top: -1px;
}}

QTabBar::tab {{
    background: {p['SURFACE_2']};
    color: {p['TEXT_SOFT']};
    padding: 8px 18px;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 12.5px;
}}

QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['ACCENT_HOV']}, stop:1 {p['ACCENT']});
    color: {p['ON_ACCENT']};
}}

QTabBar::tab:hover:!selected {{
    color: {p['TEXT']};
}}

QCheckBox, QRadioButton {{
    color: {p['TEXT_SOFT']};
    font-size: 12.5px;
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid {p['BORDER']};
    background-color: {p['SURFACE_2']};
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['ACCENT2_HOV']}, stop:1 {p['ACCENT2']});
    border: 1px solid {p['ACCENT2']};
}}

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QListWidget::item {{
    border: none;
}}

QListWidget::item:selected {{
    background-color: transparent;
}}

QMenu {{
    background-color: {p['SURFACE_2']};
    color: {p['TEXT']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 7px 18px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background-color: {p['ACCENT']};
    color: {p['ON_ACCENT']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {p['SECONDARY']};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {p['BORDER']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['ACCENT_HOV']}, stop:1 {p['ACCENT']});
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QProgressBar {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
    color: {p['TEXT']};
}}

QProgressBar::chunk {{
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['ACCENT2']}, stop:0.6 {p['ACCENT']}, stop:1 {p['ACCENT_HOV']});
}}

QToolTip {{
    background-color: {p['SURFACE_2']};
    color: {p['TEXT']};
    border: 1px solid {p['BORDER']};
    padding: 5px 8px;
    border-radius: 6px;
}}

QStatusBar {{
    background-color: {p['BG']};
    color: {p['TEXT_SOFT']};
    border-top: 1px solid {p['BORDER']};
    padding: 2px 6px;
}}
"""


MODE = load_mode()
_PAL = PALETTES[MODE]

BG = _PAL["BG"]
BG_GRAD_TOP = _PAL["BG_GRAD_TOP"]
BG_GRAD_BOTTOM = _PAL["BG_GRAD_BOTTOM"]
SURFACE = _PAL["SURFACE"]
SURFACE_2 = _PAL["SURFACE_2"]
SURFACE_3 = _PAL["SURFACE_3"]
GLASS_CARD = _PAL["GLASS_CARD"]
GLASS_BORDER = _PAL["GLASS_BORDER"]
TEXT = _PAL["TEXT"]
TEXT_SOFT = _PAL["TEXT_SOFT"]
ACCENT = _PAL["ACCENT"]
ACCENT_HOV = _PAL["ACCENT_HOV"]
ACCENT_SOFT = _PAL["ACCENT_SOFT"]
ACCENT2 = _PAL["ACCENT2"]
ACCENT2_HOV = _PAL["ACCENT2_HOV"]
ACCENT2_SOFT = _PAL["ACCENT2_SOFT"]
ACCENT3 = _PAL["ACCENT3"]
ACCENT3_HOV = _PAL["ACCENT3_HOV"]
ACCENT3_SOFT = _PAL["ACCENT3_SOFT"]
SECONDARY = _PAL["SECONDARY"]
BORDER = _PAL["BORDER"]
BORDER_STRONG = _PAL["BORDER_STRONG"]
DANGER = _PAL["DANGER"]
DANGER_HOV = _PAL["DANGER_HOV"]
ON_ACCENT = _PAL["ON_ACCENT"]
ORB1 = _PAL["ORB1"]
ORB2 = _PAL["ORB2"]
ORB3 = _PAL["ORB3"]

QSS = _build_qss(_PAL)
