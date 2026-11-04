# -*- coding: utf-8 -*-
"""Paleta de marca Provecto (modo oscuro) y hoja de estilos QSS global."""

BG         = "#1C1E13"
SURFACE    = "#2E3220"
SURFACE_2  = "#3B3F2A"
SURFACE_3  = "#4B5038"
TEXT       = "#F3F1E4"
TEXT_SOFT  = "#A7AC80"
ACCENT     = "#C08258"
ACCENT_HOV = "#D4935F"
ACCENT_SOFT = "rgba(192, 130, 88, 0.18)"
SECONDARY  = "#767A56"
BORDER     = "rgba(243, 241, 228, 0.14)"
BORDER_STRONG = "rgba(243, 241, 228, 0.24)"
DANGER     = "#D47268"
DANGER_HOV = "#B85A50"

FONT_FAMILY = "Segoe UI, Inter, Arial, sans-serif"

QSS = f"""
* {{
    font-family: {FONT_FAMILY};
}}

QMainWindow, QDialog, QWidget#RootView {{
    background-color: {BG};
}}

QWidget {{
    color: {TEXT};
}}

QLabel#Header {{
    font-size: 21px;
    font-weight: 700;
    color: {TEXT};
    letter-spacing: 0.2px;
}}

QLabel#SubHeader {{
    font-size: 12px;
    color: {TEXT_SOFT};
}}

QLabel#SectionTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
    border-left: 3px solid {ACCENT};
    padding-left: 9px;
}}

QLabel#Hint {{
    font-size: 11.5px;
    color: {TEXT_SOFT};
}}

QLabel#Badge {{
    background-color: {ACCENT};
    color: {BG};
    border-radius: 11px;
    font-size: 17px;
    font-weight: 700;
}}

QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 14px;
}}

QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    color: {TEXT};
    selection-background-color: {ACCENT};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QPushButton {{
    background-color: {SURFACE_3};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-bottom: 2px solid rgba(0,0,0,0.22);
    border-radius: 10px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton:hover {{
    border: 1px solid {ACCENT};
    border-bottom: 2px solid {ACCENT};
    background-color: {ACCENT_SOFT};
    color: {TEXT};
}}

QPushButton:pressed {{
    background-color: {BG};
    border-bottom: 1px solid {ACCENT};
}}

QPushButton:disabled {{
    color: {TEXT_SOFT};
    border-bottom: 2px solid rgba(0,0,0,0.22);
    background-color: {SURFACE_2};
}}

QPushButton#Primary {{
    background-color: {ACCENT};
    color: #1C1409;
    border: none;
    border-bottom: 2px solid rgba(0,0,0,0.28);
    font-weight: 700;
}}

QPushButton#Primary:hover {{
    background-color: {ACCENT_HOV};
    border-bottom: 2px solid rgba(0,0,0,0.28);
}}

QPushButton#Secondary {{
    background-color: transparent;
    color: {ACCENT};
    border: 1.5px solid {ACCENT};
    border-bottom: 1.5px solid {ACCENT};
    font-weight: 700;
}}

QPushButton#Secondary:hover {{
    background-color: {ACCENT_SOFT};
    color: {TEXT};
}}

QPushButton#Secondary:checked {{
    background-color: {ACCENT};
    color: #1C1409;
}}

QPushButton#Danger {{
    background-color: transparent;
    color: {DANGER};
    border: 1.5px solid {DANGER};
    border-bottom: 1.5px solid {DANGER};
}}

QPushButton#Danger:hover {{
    background-color: {DANGER};
    color: {TEXT};
}}

QPushButton#Flat {{
    background-color: transparent;
    border: none;
    color: {TEXT_SOFT};
    padding: 6px 4px;
    font-weight: 600;
}}

QPushButton#Flat:hover {{
    color: {ACCENT};
    background-color: transparent;
}}

QFrame#Toolbar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {SURFACE};
    top: -1px;
}}

QTabBar::tab {{
    background: {SURFACE_2};
    color: {TEXT_SOFT};
    padding: 8px 18px;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 12.5px;
}}

QTabBar::tab:selected {{
    background: {ACCENT};
    color: #1C1409;
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

QCheckBox, QRadioButton {{
    color: {TEXT_SOFT};
    font-size: 12.5px;
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background-color: {SURFACE_2};
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
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
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 7px 18px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background-color: {ACCENT};
    color: {BG};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {SECONDARY};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QProgressBar {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
    color: {TEXT};
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

QToolTip {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px 8px;
    border-radius: 6px;
}}

QStatusBar {{
    background-color: {BG};
    color: {TEXT_SOFT};
    border-top: 1px solid {BORDER};
    padding: 2px 6px;
}}
"""
