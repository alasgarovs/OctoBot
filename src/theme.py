"""Colors, fonts, icons and the application stylesheet."""

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

BG = "#0B0E13"
SIDE = "#0F1319"
PANEL = "#12161D"
LINE = "#1D232D"
LINE2 = "#2A3240"
TEXT = "#E8ECF2"
SOFT = "#A6B0BF"
MUTED = "#8F9AAB"
ACCENT = "#00D4FF"
ACCENT_INK = "#04222B"
OK = "#34D399"
WARN = "#FBBF24"
BAD = "#F87171"

UI_FAMILIES = ["Plus Jakarta Sans", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "sans-serif"]
MONO_FAMILIES = ["JetBrains Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "monospace"]

ICONS = {
    "dashboard": "M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 8h6V4h-6z",
    "users": "M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM20 20v-1.5a3.5 3.5 0 0 0-2.5-3.35M15.5 4.2a3.5 3.5 0 0 1 0 6.6",
    "download": "M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19h14",
    "upload": "M12 15V4M7.5 8.5 12 4l4.5 4.5M5 19h14",
    "trash": "M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13",
    "search": "M11 17.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM16 16l4 4",
    "check": "m5 12 5 5 9-9",
    "logout": "M9 4H5v16h4M16 8l4 4-4 4M20 12H9",
    "message": "M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z",
    "plus": "M12 5v14M5 12h14",
    "shield": "M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6zM9 12l2 2 4-4",
    "left": "m15 6-6 6 6 6",
    "settings": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z",
    "right": "m9 6 6 6-6 6",
}
FILLED = {
    "play": "M7 4.5v15l12-7.5z",
    "stop": "M6 6h12v12H6z",
}


def ui_font(pixel_size=14, weight=QFont.Weight.Medium):
    font = QFont()
    font.setFamilies(UI_FAMILIES)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def mono_font(pixel_size=14, weight=QFont.Weight.DemiBold):
    font = QFont()
    font.setFamilies(MONO_FAMILIES)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def _pixmap(svg, size, ratio=2):
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def _svg(name, color):
    if name in FILLED:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}">'
                f'<path d="{FILLED[name]}"/></svg>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="{ICONS[name]}"/></svg>')


def icon(name, color=SOFT, size=20, color_on=None):
    result = QIcon()
    result.addPixmap(_pixmap(_svg(name, color), size), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(_pixmap(_svg(name, color_on or color), size), QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(_pixmap(_svg(name, MUTED), size), QIcon.Mode.Disabled, QIcon.State.Off)
    return result


def logo_pixmap(size=26, color=ACCENT):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M5 12a7 7 0 0 1 14 0v1H5z"/>'
        f'<path d="M6.5 14c0 3-1.5 4-2.5 5M10 14v5M14 14v5M17.5 14c0 3 1.5 4 2.5 5"/>'
        f'<circle cx="9.5" cy="10.5" r="0.8" fill="{color}"/><circle cx="14.5" cy="10.5" r="0.8" fill="{color}"/></svg>'
    )
    return _pixmap(svg, size)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def qcolor(value, alpha=None):
    color = QColor(value)
    if alpha is not None:
        color.setAlphaF(alpha)
    return color


STYLESHEET = f"""
QWidget {{ color: {TEXT}; }}
QWidget#Root, QMainWindow {{ background: {BG}; }}
QWidget#Sidebar {{ background: {SIDE}; border-right: 1px solid {LINE}; }}
QWidget#Page {{ background: {BG}; }}
QStackedWidget {{ background: {BG}; }}

QFrame#Card {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 16px; }}
QFrame#Inset {{ background: {BG}; border: 1px solid {LINE}; border-radius: 12px; }}
QFrame#Bubble {{ background: #0F4C43; border-radius: 12px; }}
QFrame#ConnCard {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#QrFrame {{ background: #FFFFFF; border-radius: 20px; }}
QFrame#Segment {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; }}
QFrame#TableCard {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 16px; }}
QFrame#TableFoot {{ background: transparent; border: none; border-top: 1px solid {LINE}; }}

QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 26px; font-weight: 800; }}
QLabel[role="hero"] {{ font-size: 46px; font-weight: 800; }}
QLabel[role="h2"] {{ font-size: 15px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="small"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="soft"] {{ color: {SOFT}; }}
QLabel[role="bubble"] {{ color: #E6F5F2; font-size: 13px; }}
QLabel[role="bubbletime"] {{ color: #8FB8B1; font-size: 11px; }}
QLabel[role="step"] {{ color: {ACCENT}; background: rgba(0,212,255,0.08); border: 1px solid #2A4A55; border-radius: 18px; }}

QLabel[pill="true"] {{ border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: 700; }}
QLabel[pill="true"][tone="ok"] {{ background: rgba(52,211,153,0.12); color: {OK}; }}
QLabel[pill="true"][tone="warn"] {{ background: rgba(251,191,36,0.12); color: {WARN}; }}
QLabel[pill="true"][tone="bad"] {{ background: rgba(248,113,113,0.12); color: {BAD}; }}
QLabel[pill="true"][tone="idle"] {{ background: #1B2330; color: {SOFT}; }}
QLabel[pill="true"][tone="chip"] {{ background: {PANEL}; border: 1px solid {LINE}; color: {MUTED}; font-weight: 600; font-size: 13px; padding: 6px 14px; border-radius: 20px; }}

QPushButton {{
    background: {PANEL}; border: 1px solid {LINE2}; border-radius: 12px;
    padding: 0 18px; min-height: 42px; font-weight: 700; color: {TEXT};
}}
QPushButton:hover {{ border-color: #3C4A60; background: #171C25; }}
QPushButton:pressed {{ background: #0F1319; }}
QPushButton:disabled {{ color: #5A6270; border-color: #1D232D; background: #0F1319; }}
QPushButton[kind="primary"] {{ background: {ACCENT}; border: none; color: {ACCENT_INK}; font-weight: 800; padding: 0 22px; }}
QPushButton[kind="primary"]:hover {{ background: #33DCFF; }}
QPushButton[kind="primary"]:pressed {{ background: #00B8DD; }}
QPushButton[kind="primary"]:disabled {{ background: #123842; color: #4C7480; }}
QPushButton[kind="danger"] {{ color: {BAD}; border-color: #3A2A2E; }}
QPushButton[kind="danger"]:disabled {{ color: #6B4A4E; border-color: #2A2024; background: #0F1319; }}
QPushButton[kind="danger"]:hover {{ background: #1E1518; border-color: #5A343A; }}
QPushButton[kind="small"] {{ min-height: 30px; padding: 0 12px; font-size: 12px; border-radius: 8px; }}
QPushButton[kind="icon"] {{ min-height: 36px; min-width: 36px; max-width: 36px; padding: 0; border-radius: 9px; }}

QPushButton[nav="true"] {{
    text-align: left; border: none; background: transparent; color: {SOFT};
    min-height: 44px; padding: 0 12px; border-radius: 10px; font-size: 14px;
}}
QPushButton[nav="true"]:hover {{ background: #151A21; }}
QPushButton[nav="true"]:checked {{ background: rgba(0,212,255,0.10); color: {ACCENT}; }}

QPushButton[lang="true"] {{
    border: none; background: transparent; color: {MUTED}; min-height: 32px; padding: 0; border-radius: 7px; font-size: 12px;
}}
QPushButton[lang="true"]:checked {{ background: #222A36; color: {TEXT}; }}

QPushButton[filter="true"] {{ background: {PANEL}; border: 1px solid {LINE}; color: {SOFT}; font-size: 13px; padding: 0 14px; }}
QPushButton[filter="true"]:checked {{ background: #1B2330; border-color: #33405A; color: {TEXT}; }}

QPushButton[row="true"] {{
    text-align: left; background: {PANEL}; border: 1px solid {LINE}; border-radius: 12px;
    min-height: 56px; padding: 0 12px;
}}
QPushButton[row="true"]:hover {{ border-color: #3C4A60; background: #171C25; }}
QPushButton[row="true"]:checked {{ background: #1B2330; border-color: #33405A; }}

QScrollArea {{ background: transparent; border: none; }}
QWidget#RowsHolder {{ background: {PANEL}; }}

QPlainTextEdit, QTextEdit, QLineEdit, QSpinBox {{
    background: {BG}; border: 1px solid {LINE}; border-radius: 12px; padding: 8px 12px;
    selection-background-color: #0E4A59;
}}
QPlainTextEdit:focus, QLineEdit:focus, QSpinBox:focus {{ border-color: #2A6F80; }}
QPlainTextEdit:read-only {{ color: #C9D1DD; }}
QTextEdit#Log {{ background: transparent; border: none; padding: 0; font-size: 13px; }}
QLineEdit#Search {{ background: {PANEL}; min-height: 28px; padding-left: 38px; border-radius: 12px; }}
QSpinBox {{ min-height: 24px; padding: 4px 8px; border-radius: 8px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

QTableWidget {{ background: transparent; border: none; gridline-color: transparent; outline: none; }}
QTableWidget::item {{ border-bottom: 1px solid #1A202A; padding-left: 8px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {LINE};
    padding: 0 8px; min-height: 46px; font-size: 12px; font-weight: 700;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2A3240; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3C4A60; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QMessageBox, QDialog {{ background: {PANEL}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QToolTip {{ background: #171C25; color: {TEXT}; border: 1px solid {LINE2}; padding: 4px 8px; }}
"""
