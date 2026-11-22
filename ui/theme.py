"""Unified Studio Slate theme tokens, QSS builders, 2x DPI vector icon engine, and GitHub Markdown renderer."""

import html
import math
import re
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication

from core.config import ALL_SLOT_LETTERS, DEFAULT_CUSTOM_THEME, load_settings

SLOT_ACCENTS = (
    "#8b5cf6", "#10b981", "#f59e0b", "#38bdf8", "#f43f5e",
    "#6366f1", "#14b8a6", "#fb7185", "#94a3b8",
)

_VECTOR_ICON_CACHE = {}
_INITIAL_OS_IS_DARK = None


def hex_rgba(hex_color: str, alpha: int) -> str:
    """Convert #RRGGBB string and 0-255 alpha into Qt CSS rgba(...) string."""
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {max(0, min(255, int(alpha)))})"


def _qcolor_alpha(color_or_hex, alpha: int) -> QColor:
    """Return a QColor with explicit 0-255 alpha safe for QPainter.setBrush()."""
    c = QColor(color_or_hex)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def darken_color(hex_color: str, factor: float = 0.8) -> str:
    """Scale RGB channels of a #RRGGBB color by factor."""
    c = QColor(hex_color)
    r = max(0, min(255, int(c.red() * factor)))
    g = max(0, min(255, int(c.green() * factor)))
    b = max(0, min(255, int(c.blue() * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def slot_text_color(accent: str, is_dark: bool) -> str:
    """Return high-contrast foreground/icon accent adjusted for dark or light surfaces."""
    if is_dark:
        return accent
    return darken_color(accent, 0.64)


def is_system_dark() -> bool:
    """Detect OS dark theme luminance reliably even after QApplication palette overrides."""
    global _INITIAL_OS_IS_DARK
    app = QApplication.instance()
    if app is None:
        return True
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    if _INITIAL_OS_IS_DARK is None:
        base = app.palette().window().color()
        brightness = base.red() * 0.299 + base.green() * 0.587 + base.blue() * 0.114
        _INITIAL_OS_IS_DARK = brightness < 128
    return _INITIAL_OS_IS_DARK


def apply_studio_palette(t: dict) -> None:
    """Synchronize QApplication QPalette with active Studio Slate tokens so native viewports never mismatch."""
    app = QApplication.instance()
    if app is None:
        return
    is_system_dark()  # Ensure initial OS scheme is cached before overriding palette
    pal = QPalette()
    win_col = QColor(t["win_bg"])
    surf_col = QColor(t["surface"])
    stage_col = QColor(t["stage_bg"])
    text_col = QColor(t["text"])
    muted_col = QColor(t["text_muted"])
    accent_col = QColor(t["accent"])
    white_col = QColor("#ffffff")

    pal.setColor(QPalette.Window, win_col)
    pal.setColor(QPalette.WindowText, text_col)
    pal.setColor(QPalette.Base, surf_col)
    pal.setColor(QPalette.AlternateBase, stage_col)
    pal.setColor(QPalette.Text, text_col)
    pal.setColor(QPalette.Button, surf_col)
    pal.setColor(QPalette.ButtonText, text_col)
    pal.setColor(QPalette.BrightText, white_col)
    pal.setColor(QPalette.Highlight, accent_col)
    pal.setColor(QPalette.HighlightedText, white_col)
    pal.setColor(QPalette.ToolTipBase, QColor(t["menu_bg"]))
    pal.setColor(QPalette.ToolTipText, text_col)
    pal.setColor(QPalette.PlaceholderText, muted_col)
    pal.setColor(QPalette.Disabled, QPalette.Text, muted_col)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, muted_col)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, muted_col)
    app.setPalette(pal)


def resolve_studio_tokens(owner=None) -> dict:
    """Single canonical Studio Slate design-token resolver across Dark, Light, System, and Custom themes."""
    theme_mode = getattr(owner, "theme_mode", None)
    if not theme_mode:
        theme_mode = load_settings().get("theme_mode", "system")

    if theme_mode == "custom":
        ct = getattr(owner, "custom_theme", None) or load_settings().get("custom_theme", DEFAULT_CUSTOM_THEME)
        bg = ct.get("bg_color", DEFAULT_CUSTOM_THEME["bg_color"])
        dark_custom = QColor(bg).lightness() < 128
        return {
            "is_dark": dark_custom,
            "win_bg": bg,
            "stage_bg": ct.get("label_bg", DEFAULT_CUSTOM_THEME["label_bg"]),
            "surface": ct.get("btn_bg", DEFAULT_CUSTOM_THEME["btn_bg"]),
            "surface_hover": ct.get("btn_hover", DEFAULT_CUSTOM_THEME["btn_hover"]),
            "surface_pressed": ct.get("btn_hover", "#2a3040"),
            "border": "#282e3d" if dark_custom else "#cfd6e3",
            "border_strong": ct.get("main_border_color", DEFAULT_CUSTOM_THEME["main_border_color"]),
            "next_border": ct.get("next_border_color", DEFAULT_CUSTOM_THEME["next_border_color"]),
            "text": ct.get("text_color", DEFAULT_CUSTOM_THEME["text_color"]),
            "text_muted": "#949cb0" if dark_custom else "#525a6b",
            "card_bg": ct.get("label_bg", "#151922"),
            "next_card_bg": ct.get("label_bg", "#151922"),
            "canvas_bg": "#0b0d12" if dark_custom else "#e6ebf2",
            "menu_bg": ct.get("menu_bg", DEFAULT_CUSTOM_THEME["menu_bg"]),
            "menu_text": ct.get("menu_text", DEFAULT_CUSTOM_THEME["menu_text"]),
            "accent": ct.get("main_border_color", DEFAULT_CUSTOM_THEME["main_border_color"]),
        }

    dark = theme_mode == "dark" or (theme_mode == "system" and is_system_dark())
    if dark:
        return {
            "is_dark": True,
            "win_bg": "#0e1015",
            "stage_bg": "#141821",
            "surface": "#1b202b",
            "surface_hover": "#242b3a",
            "surface_pressed": "#2d3548",
            "border": "#282e3d",
            "border_strong": "#3b4358",
            "next_border": "#2a3040",
            "text": "#f1f3f9",
            "text_muted": "#949cb0",
            "card_bg": "#151922",
            "next_card_bg": "#151922",
            "canvas_bg": "#0b0d12",
            "menu_bg": "#131720",
            "menu_text": "#f1f3f9",
            "accent": "#3b82f6",
        }
    return {
        "is_dark": False,
        "win_bg": "#f4f6fa",
        "stage_bg": "#eaeef5",
        "surface": "#ffffff",
        "surface_hover": "#eef2f8",
        "surface_pressed": "#e1e7f0",
        "border": "#cfd6e3",
        "border_strong": "#adb7c9",
        "next_border": "#c5cedd",
        "text": "#11141c",
        "text_muted": "#525a6b",
        "card_bg": "#ffffff",
        "next_card_bg": "#f9fafc",
        "canvas_bg": "#e6ebf2",
        "menu_bg": "#ffffff",
        "menu_text": "#11141c",
        "accent": "#2563eb",
    }


def build_studio_dialog_qss(t: dict) -> str:
    """Unified Studio Slate QSS stylesheet shared across all QDialog, QMessageBox, inputs, and scrollbars."""
    accent_hover = "#2563eb" if t["is_dark"] else "#1d4ed8"
    accent_press = "#1d4ed8" if t["is_dark"] else "#1e40af"
    danger_bg = hex_rgba("#ef4444", 34 if t["is_dark"] else 22)
    danger_border = hex_rgba("#ef4444", 110 if t["is_dark"] else 95)
    danger_hover = hex_rgba("#ef4444", 64 if t["is_dark"] else 42)
    danger_text = "#fca5a5" if t["is_dark"] else "#dc2626"
    return f"""
        QDialog, QMessageBox {{
            background-color: {t["win_bg"]};
            color: {t["text"]};
        }}
        QWidget {{
            color: {t["text"]};
        }}
        QLabel {{
            color: {t["text"]};
            background-color: transparent;
            border: none;
        }}
        QFrame#studioCard, QFrame#workflowBar {{
            background-color: {t["stage_bg"]};
            border: 1px solid {t["border"]};
            border-radius: 10px;
        }}
        QFrame#hairline {{
            background-color: {t["border"]};
            max-height: 1px;
            min-height: 1px;
            border: none;
        }}
        QLineEdit, QTextEdit, QTextBrowser {{
            background-color: {t["surface"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 7px 12px;
            font-size: 12px;
            selection-background-color: {t["accent"]};
            selection-color: #ffffff;
        }}
        QSpinBox {{
            background-color: {t["surface"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 6px 24px 6px 10px;
            font-size: 12px;
            font-weight: 600;
            selection-background-color: {t["accent"]};
            selection-color: #ffffff;
        }}
        QSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 22px;
            background: transparent;
            border: none;
        }}
        QSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 22px;
            background: transparent;
            border: none;
        }}
        QSpinBox::up-arrow, QSpinBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
            border: none;
        }}
        QLineEdit:focus, QSpinBox:focus, QTextEdit:focus {{
            border-color: {t["accent"]};
        }}
        QTextBrowser#releaseNotesView {{
            background-color: {t["stage_bg"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
            border-radius: 10px;
            padding: 10px 14px;
        }}
        QTextBrowser#releaseNotesView:focus {{
            border-color: {t["border_strong"]};
        }}
        QFrame#shortcutRow {{
            background-color: transparent;
            border: none;
            border-bottom: 1px solid {t["border"]};
        }}
        QPushButton {{
            background-color: {t["surface"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
            min-height: 26px;
        }}
        QPushButton:hover {{
            background-color: {t["surface_hover"]};
            border-color: {t["border_strong"]};
        }}
        QPushButton:pressed {{
            background-color: {t["surface_pressed"]};
        }}
        QPushButton:disabled {{
            color: {t["text_muted"]};
            background-color: {t["stage_bg"]};
            border-color: {t["border"]};
        }}
        QPushButton#primaryBtn, QPushButton#save_btn {{
            background-color: {t["accent"]};
            color: #ffffff;
            border: 1px solid {t["accent"]};
        }}
        QPushButton#primaryBtn:hover, QPushButton#save_btn:hover {{
            background-color: {accent_hover};
            border-color: {accent_hover};
        }}
        QPushButton#primaryBtn:pressed, QPushButton#save_btn:pressed {{
            background-color: {accent_press};
        }}
        QPushButton#primaryBtn:disabled {{
            background-color: {t["surface"]};
            color: {t["text_muted"]};
            border-color: {t["border"]};
        }}
        QPushButton#dangerBtn {{
            background-color: {danger_bg};
            color: {danger_text};
            border: 1px solid {danger_border};
        }}
        QPushButton#dangerBtn:hover {{
            background-color: {danger_hover};
            border-color: #ef4444;
        }}
        QSlider::groove:horizontal {{
            background: {t["border"]};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: {t["accent"]};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: #ffffff;
            border: 2px solid {t["accent"]};
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {t["accent"]};
        }}
        QScrollArea, QWidget#scrollBody, QWidget#scrollColumn, QWidget#qt_scrollarea_viewport {{
            background-color: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 2px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {t["border_strong"]};
            min-height: 24px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t["border_strong"]};
            min-width: 24px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QToolTip {{
            background-color: {t["menu_bg"]};
            color: {t["text"]};
            border: 1px solid {t["border_strong"]};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 11px;
        }}
    """


def make_vector_icon(kind: str, color: str = "#e4e6eb", size: int = 16) -> QIcon:
    """Build cached 2x DPI anti-aliased vector glyph icon."""
    key = (kind, color, int(size))
    cached = _VECTOR_ICON_CACHE.get(key)
    if cached is not None:
        return cached

    dpr = 2.0
    px_size = int(size * dpr)
    pix = QPixmap(px_size, px_size)
    pix.fill(Qt.transparent)
    pix.setDevicePixelRatio(dpr)

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    qcol = QColor(color)
    pen = QPen(qcol, 1.65, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    s = float(size)
    mid = s * 0.5

    if kind == "prev":
        p.drawPolyline(QPolygonF([QPointF(s * 0.64, s * 0.22), QPointF(s * 0.32, mid), QPointF(s * 0.64, s * 0.78)]))
    elif kind == "next":
        p.drawPolyline(QPolygonF([QPointF(s * 0.36, s * 0.22), QPointF(s * 0.68, mid), QPointF(s * 0.36, s * 0.78)]))
    elif kind == "undo":
        p.drawArc(QRectF(s * 0.26, s * 0.34, s * 0.54, s * 0.46), 280 * 16, 200 * 16)
        p.drawLine(QPointF(s * 0.26, s * 0.36), QPointF(s * 0.54, s * 0.36))
        p.drawPolyline(QPolygonF([QPointF(s * 0.36, s * 0.20), QPointF(s * 0.20, s * 0.36), QPointF(s * 0.36, s * 0.52)]))
    elif kind == "skip":
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(s * 0.22, s * 0.24), QPointF(s * 0.62, mid), QPointF(s * 0.22, s * 0.76)]))
        p.drawRoundedRect(QRectF(s * 0.68, s * 0.24, s * 0.14, s * 0.52), 1.0, 1.0)
    elif kind == "folder":
        path_pts = QPolygonF([
            QPointF(s * 0.14, s * 0.28),
            QPointF(s * 0.42, s * 0.28),
            QPointF(s * 0.50, s * 0.38),
            QPointF(s * 0.86, s * 0.38),
            QPointF(s * 0.86, s * 0.78),
            QPointF(s * 0.14, s * 0.78),
        ])
        p.setBrush(_qcolor_alpha(qcol, 42))
        p.drawPolygon(path_pts)
    elif kind == "play":
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(s * 0.30, s * 0.20), QPointF(s * 0.78, mid), QPointF(s * 0.30, s * 0.80)]))
    elif kind == "pause":
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        bw = max(2.2, s * 0.16)
        p.drawRoundedRect(QRectF(s * 0.26, s * 0.22, bw, s * 0.56), 1.0, 1.0)
        p.drawRoundedRect(QRectF(s * 0.58, s * 0.22, bw, s * 0.56), 1.0, 1.0)
    elif kind in ("sound_on", "sound_off"):
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        speaker = QPolygonF([
            QPointF(s * 0.16, s * 0.38),
            QPointF(s * 0.33, s * 0.38),
            QPointF(s * 0.54, s * 0.20),
            QPointF(s * 0.54, s * 0.80),
            QPointF(s * 0.33, s * 0.62),
            QPointF(s * 0.16, s * 0.62),
        ])
        p.drawPolygon(speaker)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(qcol, 1.45, Qt.SolidLine, Qt.RoundCap))
        if kind == "sound_on":
            p.drawArc(QRectF(s * 0.48, s * 0.32, s * 0.24, s * 0.36), -50 * 16, 100 * 16)
            p.drawArc(QRectF(s * 0.52, s * 0.20, s * 0.36, s * 0.60), -52 * 16, 104 * 16)
        else:
            p.drawLine(QPointF(s * 0.62, s * 0.34), QPointF(s * 0.86, s * 0.66))
            p.drawLine(QPointF(s * 0.86, s * 0.34), QPointF(s * 0.62, s * 0.66))
    elif kind == "step_prev":
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.24, s * 0.12, s * 0.52), 1.0, 1.0)
        p.drawPolygon(QPolygonF([QPointF(s * 0.76, s * 0.24), QPointF(s * 0.38, mid), QPointF(s * 0.76, s * 0.76)]))
    elif kind == "step_next":
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(s * 0.24, s * 0.24), QPointF(s * 0.62, mid), QPointF(s * 0.24, s * 0.76)]))
        p.drawRoundedRect(QRectF(s * 0.66, s * 0.24, s * 0.12, s * 0.52), 1.0, 1.0)
    elif kind == "folder_plus":
        path_pts = QPolygonF([
            QPointF(s * 0.12, s * 0.26),
            QPointF(s * 0.40, s * 0.26),
            QPointF(s * 0.48, s * 0.36),
            QPointF(s * 0.88, s * 0.36),
            QPointF(s * 0.88, s * 0.78),
            QPointF(s * 0.12, s * 0.78),
        ])
        p.setBrush(_qcolor_alpha(qcol, 36))
        p.drawPolygon(path_pts)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(mid, s * 0.46), QPointF(mid, s * 0.68))
        p.drawLine(QPointF(s * 0.39, s * 0.57), QPointF(s * 0.61, s * 0.57))
    elif kind == "folder_search":
        path_pts = QPolygonF([
            QPointF(s * 0.12, s * 0.26),
            QPointF(s * 0.40, s * 0.26),
            QPointF(s * 0.48, s * 0.36),
            QPointF(s * 0.88, s * 0.36),
            QPointF(s * 0.88, s * 0.78),
            QPointF(s * 0.12, s * 0.78),
        ])
        p.setBrush(_qcolor_alpha(qcol, 36))
        p.drawPolygon(path_pts)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(s * 0.48, s * 0.55), s * 0.11, s * 0.11)
        p.drawLine(QPointF(s * 0.56, s * 0.63), QPointF(s * 0.68, s * 0.73))
    elif kind == "trash":
        p.drawLine(QPointF(s * 0.20, s * 0.28), QPointF(s * 0.80, s * 0.28))
        p.drawRoundedRect(QRectF(s * 0.38, s * 0.16, s * 0.24, s * 0.12), 1.5, 1.5)
        p.drawRoundedRect(QRectF(s * 0.26, s * 0.28, s * 0.48, s * 0.56), 2.0, 2.0)
        p.drawLine(QPointF(s * 0.42, s * 0.42), QPointF(s * 0.42, s * 0.70))
        p.drawLine(QPointF(s * 0.58, s * 0.42), QPointF(s * 0.58, s * 0.70))
    elif kind == "file_text":
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.14, s * 0.56, s * 0.72), 2.0, 2.0)
        p.drawLine(QPointF(s * 0.34, s * 0.36), QPointF(s * 0.66, s * 0.36))
        p.drawLine(QPointF(s * 0.34, s * 0.52), QPointF(s * 0.66, s * 0.52))
        p.drawLine(QPointF(s * 0.34, s * 0.68), QPointF(s * 0.54, s * 0.68))
    elif kind == "clock":
        p.drawEllipse(QPointF(mid, mid), s * 0.36, s * 0.36)
        p.drawLine(QPointF(mid, s * 0.30), QPointF(mid, mid))
        p.drawLine(QPointF(mid, mid), QPointF(s * 0.66, s * 0.58))
    elif kind == "palette":
        p.drawEllipse(QPointF(mid, mid), s * 0.37, s * 0.34)
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        for cx, cy in ((0.36, 0.38), (0.52, 0.32), (0.64, 0.44), (0.40, 0.58)):
            p.drawEllipse(QPointF(s * cx, s * cy), s * 0.06, s * 0.06)
    elif kind == "sun":
        p.drawEllipse(QPointF(mid, mid), s * 0.18, s * 0.18)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
            p.drawLine(
                QPointF(mid + dx * s * 0.27, mid + dy * s * 0.27),
                QPointF(mid + dx * s * 0.38, mid + dy * s * 0.38),
            )
    elif kind == "moon":
        path = QPainterPath()
        path.addEllipse(QPointF(mid, mid), s * 0.33, s * 0.33)
        cut = QPainterPath()
        cut.addEllipse(QPointF(s * 0.63, s * 0.37), s * 0.27, s * 0.27)
        cres = path.subtracted(cut)
        p.setBrush(_qcolor_alpha(qcol, 48))
        p.drawPath(cres)
    elif kind == "monitor":
        p.drawRoundedRect(QRectF(s * 0.16, s * 0.18, s * 0.68, s * 0.48), 2.0, 2.0)
        p.drawLine(QPointF(mid, s * 0.66), QPointF(mid, s * 0.80))
        p.drawLine(QPointF(s * 0.32, s * 0.80), QPointF(s * 0.68, s * 0.80))
    elif kind == "eye_off":
        path = QPainterPath()
        path.moveTo(s * 0.14, mid)
        path.quadTo(mid, s * 0.20, s * 0.86, mid)
        path.quadTo(mid, s * 0.80, s * 0.14, mid)
        p.drawPath(path)
        p.drawEllipse(QPointF(mid, mid), s * 0.11, s * 0.11)
        p.drawLine(QPointF(s * 0.20, s * 0.80), QPointF(s * 0.80, s * 0.20))
    elif kind == "folder_tree":
        p.drawRoundedRect(QRectF(s * 0.14, s * 0.16, s * 0.30, s * 0.22), 1.5, 1.5)
        p.drawLine(QPointF(s * 0.26, s * 0.38), QPointF(s * 0.26, s * 0.74))
        p.drawLine(QPointF(s * 0.26, s * 0.54), QPointF(s * 0.50, s * 0.54))
        p.drawLine(QPointF(s * 0.26, s * 0.74), QPointF(s * 0.50, s * 0.74))
        p.drawRoundedRect(QRectF(s * 0.50, s * 0.44, s * 0.34, s * 0.18), 1.5, 1.5)
        p.drawRoundedRect(QRectF(s * 0.50, s * 0.66, s * 0.34, s * 0.18), 1.5, 1.5)
    elif kind == "duplicates":
        p.drawRoundedRect(QRectF(s * 0.16, s * 0.16, s * 0.46, s * 0.46), 2.0, 2.0)
        p.setBrush(_qcolor_alpha(qcol, 42))
        p.drawRoundedRect(QRectF(s * 0.38, s * 0.38, s * 0.46, s * 0.46), 2.0, 2.0)
    elif kind == "jump":
        p.drawLine(QPointF(s * 0.18, mid), QPointF(s * 0.68, mid))
        p.drawPolyline(QPolygonF([QPointF(s * 0.50, s * 0.30), QPointF(s * 0.70, mid), QPointF(s * 0.50, s * 0.70)]))
        p.drawLine(QPointF(s * 0.82, s * 0.26), QPointF(s * 0.82, s * 0.74))
    elif kind == "expand":
        p.drawPolyline(QPolygonF([QPointF(s * 0.18, s * 0.38), QPointF(s * 0.18, s * 0.18), QPointF(s * 0.38, s * 0.18)]))
        p.drawPolyline(QPolygonF([QPointF(s * 0.62, s * 0.18), QPointF(s * 0.82, s * 0.18), QPointF(s * 0.82, s * 0.38)]))
        p.drawPolyline(QPolygonF([QPointF(s * 0.82, s * 0.62), QPointF(s * 0.82, s * 0.82), QPointF(s * 0.62, s * 0.82)]))
        p.drawPolyline(QPolygonF([QPointF(s * 0.38, s * 0.82), QPointF(s * 0.18, s * 0.82), QPointF(s * 0.18, s * 0.62)]))
    elif kind == "sliders":
        for y_frac, cx in ((0.26, 0.38), (0.50, 0.64), (0.74, 0.44)):
            y = s * y_frac
            p.drawLine(QPointF(s * 0.16, y), QPointF(s * 0.84, y))
            p.setBrush(qcol)
            p.drawEllipse(QPointF(s * cx, y), s * 0.08, s * 0.08)
            p.setBrush(Qt.NoBrush)
    elif kind == "upload":
        p.drawLine(QPointF(mid, s * 0.64), QPointF(mid, s * 0.20))
        p.drawPolyline(QPolygonF([QPointF(s * 0.32, s * 0.38), QPointF(mid, s * 0.20), QPointF(s * 0.68, s * 0.38)]))
        p.drawPolyline(QPolygonF([
            QPointF(s * 0.20, s * 0.62),
            QPointF(s * 0.20, s * 0.80),
            QPointF(s * 0.80, s * 0.80),
            QPointF(s * 0.80, s * 0.62),
        ]))
    elif kind == "download":
        p.drawLine(QPointF(mid, s * 0.18), QPointF(mid, s * 0.62))
        p.drawPolyline(QPolygonF([QPointF(s * 0.32, s * 0.44), QPointF(mid, s * 0.62), QPointF(s * 0.68, s * 0.44)]))
        p.drawPolyline(QPolygonF([
            QPointF(s * 0.20, s * 0.62),
            QPointF(s * 0.20, s * 0.80),
            QPointF(s * 0.80, s * 0.80),
            QPointF(s * 0.80, s * 0.62),
        ]))
    elif kind == "bolt":
        bolt = QPolygonF([
            QPointF(s * 0.56, s * 0.14),
            QPointF(s * 0.26, s * 0.54),
            QPointF(s * 0.48, s * 0.54),
            QPointF(s * 0.42, s * 0.86),
            QPointF(s * 0.74, s * 0.46),
            QPointF(s * 0.52, s * 0.46),
        ])
        p.setBrush(_qcolor_alpha(qcol, 44))
        p.drawPolygon(bolt)
    elif kind == "chevron_down":
        p.drawPolyline(QPolygonF([QPointF(s * 0.24, s * 0.38), QPointF(mid, s * 0.64), QPointF(s * 0.76, s * 0.38)]))
    elif kind == "chevron_up":
        p.drawPolyline(QPolygonF([QPointF(s * 0.24, s * 0.62), QPointF(mid, s * 0.36), QPointF(s * 0.76, s * 0.62)]))
    elif kind in ("reset", "update"):
        p.drawArc(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 35 * 16, 290 * 16)
        p.drawPolyline(QPolygonF([QPointF(s * 0.60, s * 0.16), QPointF(s * 0.78, s * 0.28), QPointF(s * 0.60, s * 0.38)]))
    elif kind == "keyboard":
        p.drawRoundedRect(QRectF(s * 0.14, s * 0.26, s * 0.72, s * 0.48), 2.0, 2.0)
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        for rx in (0.26, 0.42, 0.58, 0.72):
            p.drawRect(QRectF(s * rx - 1.2, s * 0.38, 2.4, 2.4))
        p.drawRoundedRect(QRectF(s * 0.30, s * 0.58, s * 0.40, 2.2), 1.0, 1.0)
    elif kind == "info":
        p.drawEllipse(QPointF(mid, mid), s * 0.36, s * 0.36)
        p.drawLine(QPointF(mid, s * 0.46), QPointF(mid, s * 0.68))
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(mid, s * 0.32), 1.4, 1.4)
    elif kind == "check":
        p.drawPolyline(QPolygonF([QPointF(s * 0.22, s * 0.52), QPointF(s * 0.42, s * 0.72), QPointF(s * 0.78, s * 0.28)]))
    elif kind in ("star", "star_filled"):
        mid_x, mid_y = s * 0.5, s * 0.52
        r_out, r_in = s * 0.38, s * 0.17
        pts = []
        for i in range(10):
            r = r_out if i % 2 == 0 else r_in
            ang = -3.14159265 / 2.0 + i * (3.14159265 / 5.0)
            pts.append(QPointF(mid_x + r * math.cos(ang), mid_y + r * math.sin(ang)))
        star_poly = QPolygonF(pts)
        if kind == "star_filled":
            p.setBrush(qcol)
            p.setPen(Qt.NoPen)
            p.drawPolygon(star_poly)
        else:
            p.setBrush(_qcolor_alpha(qcol, 34))
            p.drawPolygon(star_poly)
    elif kind == "sort":
        p.drawLine(QPointF(s * 0.16, s * 0.26), QPointF(s * 0.84, s * 0.26))
        p.drawLine(QPointF(s * 0.16, s * 0.48), QPointF(s * 0.62, s * 0.48))
        p.drawLine(QPointF(s * 0.16, s * 0.70), QPointF(s * 0.42, s * 0.70))
        p.drawPolyline(QPolygonF([QPointF(s * 0.68, s * 0.58), QPointF(s * 0.78, s * 0.72), QPointF(s * 0.88, s * 0.58)]))
        p.drawLine(QPointF(s * 0.78, s * 0.40), QPointF(s * 0.78, s * 0.72))
    elif kind == "filmstrip":
        p.drawRoundedRect(QRectF(s * 0.14, s * 0.22, s * 0.72, s * 0.56), 2.0, 2.0)
        p.drawLine(QPointF(mid, s * 0.22), QPointF(mid, s * 0.78))
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        for xr in (0.22, 0.38, 0.62, 0.78):
            p.drawRect(QRectF(s * xr - 1.0, s * 0.26, 2.0, 2.0))
            p.drawRect(QRectF(s * xr - 1.0, s * 0.70, 2.0, 2.0))
    elif kind == "rename":
        p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.74, s * 0.26))
        p.drawPolyline(QPolygonF([
            QPointF(s * 0.62, s * 0.16),
            QPointF(s * 0.84, s * 0.38),
            QPointF(s * 0.74, s * 0.48),
            QPointF(s * 0.52, s * 0.26),
            QPointF(s * 0.62, s * 0.16),
        ]))
        p.drawPolyline(QPolygonF([
            QPointF(s * 0.18, s * 0.82),
            QPointF(s * 0.32, s * 0.80),
            QPointF(s * 0.20, s * 0.68),
            QPointF(s * 0.18, s * 0.82),
        ]))
    elif kind == "report":
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.14, s * 0.64, s * 0.72), 2.0, 2.0)
        p.setBrush(qcol)
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(s * 0.28, s * 0.56, s * 0.10, s * 0.20))
        p.drawRect(QRectF(s * 0.45, s * 0.42, s * 0.10, s * 0.34))
        p.drawRect(QRectF(s * 0.62, s * 0.30, s * 0.10, s * 0.46))

    p.end()
    icon = QIcon(pix)
    _VECTOR_ICON_CACHE[key] = icon
    return icon


def render_github_markdown_html(md_text: str, t: dict) -> str:
    """Render GitHub Release Markdown into clean GitHub-Preview HTML suited for QTextBrowser."""
    raw = (md_text or "").strip()
    if not raw:
        raw = "No release notes available."

    text_col = t["text"]
    muted_col = t["text_muted"]
    accent_col = t["accent"]
    border_col = t["border"]
    code_bg = "#1e2330" if t["is_dark"] else "#eef1f6"
    code_fg = "#e2e8f0" if t["is_dark"] else "#1e293b"

    def _fmt_inline(line_str: str) -> str:
        code_tokens = []
        link_tokens = []

        def _hold_code(m):
            idx = len(code_tokens)
            inner = html.escape(m.group(1))
            code_tokens.append(
                f"<code style='background-color:{code_bg}; color:{code_fg}; "
                f"font-family:Consolas,monospace; font-size:11px;'>&nbsp;{inner}&nbsp;</code>"
            )
            return f"\x00CODE{idx}\x00"

        def _hold_md_link(m):
            idx = len(link_tokens)
            label = html.escape(m.group(1))
            href = html.escape(m.group(2), quote=True)
            link_tokens.append(
                f"<a href='{href}' style='color:{accent_col}; text-decoration:none;'>{label}</a>"
            )
            return f"\x00LINK{idx}\x00"

        tmp = re.sub(r"`([^`]+)`", _hold_code, line_str)
        tmp = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", _hold_md_link, tmp)

        def _hold_bare_link(m):
            idx = len(link_tokens)
            url_txt = m.group(1)
            trailing = ""
            while url_txt and url_txt[-1] in ".,;:!?)":
                trailing = url_txt[-1] + trailing
                url_txt = url_txt[:-1]
            href = html.escape(url_txt, quote=True)
            disp = html.escape(url_txt)
            link_tokens.append(
                f"<a href='{href}' style='color:{accent_col}; text-decoration:none;'>{disp}</a>"
            )
            return f"\x00LINK{idx}\x00{trailing}"

        tmp = re.sub(r"(https?://[^\s<>\x00]+)", _hold_bare_link, tmp)
        s = html.escape(tmp)
        s = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<b><i>\1</i></b>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)

        for idx, val in enumerate(link_tokens):
            s = s.replace(f"\x00LINK{idx}\x00", val)
        for idx, val in enumerate(code_tokens):
            s = s.replace(f"\x00CODE{idx}\x00", val)
        return s

    lines = raw.splitlines()
    out = [
        f"<div style='font-family:\"Segoe UI\",\"Inter\",sans-serif; font-size:12.5px; color:{text_col};'>"
    ]
    list_stack = []
    in_code = False
    code_lines = []

    def _close_lists(target_level: int = 0):
        while list_stack and list_stack[-1][1] >= target_level:
            tag, _lvl = list_stack.pop()
            out.append(f"</{tag}>")

    for line in lines:
        expanded = line.replace("\t", "    ")
        leading = len(expanded) - len(expanded.lstrip(" "))
        stripped = expanded.strip()

        if stripped.startswith("```"):
            _close_lists(1)
            if not in_code:
                in_code = True
                code_lines = []
            else:
                in_code = False
                code_block = html.escape("\n".join(code_lines))
                out.append(
                    f"<pre style='background-color:{code_bg}; color:{code_fg}; border:1px solid {border_col}; "
                    f"padding:8px 10px; font-family:Consolas,monospace; font-size:11px; margin:6px 0;'>{code_block}</pre>"
                )
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            _close_lists(1)
            continue

        if re.match(r"^[-*_]{3,}$", stripped):
            _close_lists(1)
            out.append(f"<hr style='border:none; background-color:{border_col}; height:1px; margin:8px 0;'>")
            continue

        h_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if h_match:
            _close_lists(1)
            level = len(h_match.group(1))
            h_text = _fmt_inline(h_match.group(2).strip())
            if level == 1:
                out.append(
                    f"<p style='font-size:16px; font-weight:700; color:{text_col}; margin:8px 0 3px 0;'>{h_text}</p>"
                    f"<hr style='border:none; background-color:{border_col}; height:1px; margin:0 0 6px 0;'>"
                )
            elif level == 2:
                out.append(
                    f"<p style='font-size:14.5px; font-weight:700; color:{text_col}; margin:8px 0 3px 0;'>{h_text}</p>"
                    f"<hr style='border:none; background-color:{border_col}; height:1px; margin:0 0 5px 0;'>"
                )
            elif level == 3:
                out.append(
                    f"<p style='font-size:13px; font-weight:700; color:{accent_col}; margin:8px 0 3px 0;'>{h_text}</p>"
                )
            else:
                out.append(
                    f"<p style='font-size:12px; font-weight:700; color:{muted_col}; margin:6px 0 2px 0;'>{h_text}</p>"
                )
            continue

        ul_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ul_match or ol_match:
            req_tag = "ul" if ul_match else "ol"
            indent_lvl = 2 if leading >= 2 else 1
            while list_stack and (
                list_stack[-1][1] > indent_lvl
                or (list_stack[-1][1] == indent_lvl and list_stack[-1][0] != req_tag)
            ):
                tag, _lvl = list_stack.pop()
                out.append(f"</{tag}>")
            if not list_stack or list_stack[-1][1] < indent_lvl:
                out.append(
                    f"<{req_tag} style='margin:2px 0 6px 0; padding:0; -qt-list-indent:{indent_lvl};'>"
                )
                list_stack.append((req_tag, indent_lvl))
            item_body = (ul_match.group(1) if ul_match else ol_match.group(2)).strip()
            if item_body.startswith("[x] ") or item_body.startswith("[X] "):
                item_html = f"<span style='color:#10b981; font-weight:700;'>✓</span> {_fmt_inline(item_body[4:])}"
            elif item_body.startswith("[ ] "):
                item_html = f"<span style='color:{muted_col};'>○</span> {_fmt_inline(item_body[4:])}"
            else:
                item_html = _fmt_inline(item_body)
            out.append(f"<li style='margin:2px 0; line-height:135%; color:{text_col};'>{item_html}</li>")
            continue

        if stripped.startswith(">"):
            _close_lists(1)
            q_body = _fmt_inline(stripped.lstrip(">").strip())
            out.append(
                f"<table width='100%' cellspacing='0' cellpadding='0' style='margin:5px 0;'>"
                f"<tr>"
                f"<td width='3' style='background-color:{accent_col};'></td>"
                f"<td style='background-color:{code_bg}; color:{muted_col}; padding:5px 10px; line-height:135%;'>{q_body}</td>"
                f"</tr></table>"
            )
            continue

        _close_lists(1)
        out.append(f"<p style='margin:4px 0 6px 0; line-height:138%; color:{text_col};'>{_fmt_inline(stripped)}</p>")

    _close_lists(1)
    out.append("</div>")
    return "".join(out)


def build_empty_state_html(t: dict, slot_count: int = 5, compact: bool = False) -> str:
    """Build clean Studio Slate HTML quick-start guide when no media is loaded."""
    max_key = max(3, int(slot_count or 5))
    max_let = ALL_SLOT_LETTERS[min(max_key - 1, len(ALL_SLOT_LETTERS) - 1)]
    tbl_w = 250 if compact else 325
    cell_pad = 4 if compact else 7
    font_sz = 11 if compact else 12
    title_sz = 15 if compact else 17
    key_col = t["accent"]
    desc_col = t["text"]
    sub_col = t["text_muted"]
    row_bg = "#1c212e" if t["is_dark"] else "#eef2f8"
    return (
        f"<div align='center'>"
        f"<p style='font-size:{title_sz}px; font-weight:700; color:{desc_col}; margin-bottom:4px;'>No Media Loaded</p>"
        f"<p style='font-size:{font_sz}px; color:{sub_col}; margin-top:0px; margin-bottom:{8 if compact else 14}px;'>"
        f"Drop a folder or press <font face='Consolas' color='{key_col}'><b>Ctrl+O</b></font>"
        f"</p>"
        f"<table align='center' width='{tbl_w}' cellspacing='3' cellpadding='{cell_pad}' style='font-size:{font_sz}px;'>"
        f"<tr bgcolor='{row_bg}'>"
        f"<td align='left' width='44%'><font face='Consolas' color='{key_col}'><b>[1] – [{max_key}]</b></font></td>"
        f"<td align='left'><font color='{desc_col}'>Move to Folder A–{max_let}</font></td>"
        f"</tr>"
        f"<tr bgcolor='{row_bg}'>"
        f"<td align='left'><font face='Consolas' color='{key_col}'><b>Hold [1]–[{max_key}]</b></font></td>"
        f"<td align='left'><font color='{desc_col}'>Rapid Move</font></td>"
        f"</tr>"
        f"<tr bgcolor='{row_bg}'>"
        f"<td align='left'><font face='Consolas' color='{key_col}'><b>←  /  →</b></font></td>"
        f"<td align='left'><font color='{desc_col}'>Previous / Next</font></td>"
        f"</tr>"
        f"<tr bgcolor='{row_bg}'>"
        f"<td align='left'><font face='Consolas' color='{key_col}'><b>Space / F</b></font></td>"
        f"<td align='left'><font color='{desc_col}'>Skip / Zoom preview</font></td>"
        f"</tr>"
        f"</table>"
        f"<p style='font-size:11px; color:{sub_col}; margin-top:{8 if compact else 12}px;'>"
        f"Press <font face='Consolas' color='{key_col}'><b>F1</b></font> for all shortcuts"
        f"</p>"
        f"</div>"
    )
