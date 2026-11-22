import sys
import os
import requests
import re
import time
from collections import deque
# Tambahkan direktori utils/ ke sys.path
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

utils_path = os.path.join(base_path, "utils")
if utils_path not in sys.path:
    sys.path.append(utils_path)

print(f"[DEBUG] Current working directory: {os.getcwd()}")
print(f"[DEBUG] assets/icons/app_icon.png exists: {os.path.exists(os.path.join(base_path, 'assets/icons/app_icon.png'))}")
try:
    from utils import resources
    print("[DEBUG] Successfully imported resources")
except ImportError as e:
    print(f"[ERROR] Failed to import resources: {e}")

import shutil
import json
import html
import subprocess
import ctypes
from ctypes import wintypes

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QWidget, QFileDialog,
    QMessageBox, QMenuBar, QSpacerItem, QSizePolicy, QDialog, QLineEdit,
    QColorDialog, QFrame, QComboBox, QGraphicsDropShadowEffect,
    QProgressBar, QStackedLayout, QScrollArea, QTextEdit, QTextBrowser,
    QSpinBox, QSlider, QGridLayout
)
from PySide6.QtGui import (
    QAction, QImageReader, QIcon, QShortcut, QKeySequence,
    QDesktopServices, QMovie, QPixmap, QPainter, QPainterPath, QPen, QColor,
    QPolygonF, QFontMetrics
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QTimer, QThread, QSize, Signal,
    QUrl, QEvent, QByteArray, QBuffer, QIODevice, QPointF, QRectF
)
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
    _HAS_QTMULTIMEDIA = True
except ImportError:
    QMediaPlayer = None
    QAudioOutput = None
    QVideoSink = None
    _HAS_QTMULTIMEDIA = False

from utils.image_utils import (
    PIL_FALLBACK_EXTENSIONS,
    VIDEO_EXTENSIONS,
    _HAS_CV2,
    _HAS_HEIF,
    _HAS_PIL,
    PixmapLRUCache,
    compute_dhash,
    decode_video_qimages,
    find_duplicate_groups,
    format_duration,
    format_file_size,
    hamming_distance,
    is_video_file,
    load_animation_frames,
    load_pixmap,
    read_image_metadata,
    read_video_metadata,
    resize_image,
    resize_next_preview,
)

_RESOLVED_CONFIG_DIR = None
_VECTOR_ICON_CACHE = {}


def _hex_rgba(hex_color: str, alpha: int) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {max(0, min(255, int(alpha)))})"


def make_vector_icon(kind: str, color: str = "#e4e6eb", size: int = 16) -> QIcon:
    """Bangun ikon vektor anti-aliased 2x DPI (cached) untuk menggantikan ikon raster lama."""
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
        p.setBrush(_hex_rgba(color, 36))
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
        p.setBrush(_hex_rgba(color, 28))
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
        p.setBrush(_hex_rgba(color, 28))
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
        p.setBrush(_hex_rgba(color, 42))
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
        p.setBrush(_hex_rgba(color, 34))
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
        p.setBrush(_hex_rgba(color, 38))
        p.drawPolygon(bolt)
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

    p.end()
    icon = QIcon(pix)
    _VECTOR_ICON_CACHE[key] = icon
    return icon


class _ClickSeekSlider(QSlider):
    """Slider horizontal yang mendukung klik langsung ke posisi waktu mana pun secara instan."""
    seek_clicked = Signal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            span = max(1, self.maximum() - self.minimum())
            ratio = max(0.0, min(1.0, event.position().x() / float(self.width())))
            val = self.minimum() + int(round(ratio * span))
            self.setValue(val)
            self.seek_clicked.emit(val)
            event.accept()
            return
        super().mousePressEvent(event)


class _StageViewport(QWidget):
    """Kontainer viewport pratinjau responsif: bebas dari minimumSizeHint kaku dan memusatkan pratinjau."""
    resized = Signal()

    def __init__(self, child_widget: QWidget, min_w: int = 240, min_h: int = 180, parent=None):
        super().__init__(parent)
        self._min_sz = QSize(min_w, min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.child_widget = child_widget
        child_widget.setParent(self)

    def minimumSizeHint(self):
        return self._min_sz

    def sizeHint(self):
        return QSize(max(self._min_sz.width(), 320), max(self._min_sz.height(), 260))

    def center_child(self):
        if self.child_widget is None:
            return
        vw, vh = self.width(), self.height()
        cw, ch = self.child_widget.width(), self.child_widget.height()
        self.child_widget.move(max(0, (vw - cw) // 2), max(0, (vh - ch) // 2))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()
        self.center_child()


def _fit_pixmap_box(pixmap: QPixmap, max_w: int, max_h: int) -> QPixmap:
    """Skalakan pixmap agar selalu pas di dalam batas (max_w x max_h) tanpa merusak aspek rasio."""
    if pixmap.isNull():
        return pixmap
    mw = max(48, int(max_w))
    mh = max(48, int(max_h))
    return pixmap.scaled(mw, mh, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def get_config_path():
    """Kembalikan path settings.json.
    Gunakan folder 'config/' lokal jika bisa ditulis (atau mode --portable),
    dan otomatis beralih ke %LOCALAPPDATA%/ImageSorter/config jika diinstal
    di lokasi read-only seperti C:/Program Files."""
    global _RESOLVED_CONFIG_DIR
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    local_config_dir = os.path.join(base_path, "config")
    portable = "--portable" in sys.argv
    if _RESOLVED_CONFIG_DIR is None:
        chosen = local_config_dir
        try:
            os.makedirs(local_config_dir, exist_ok=True)
            probe = os.path.join(local_config_dir, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(probe)
        except OSError:
            if not portable:
                appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
                chosen = os.path.join(appdata, "ImageSorter", "config")
                os.makedirs(chosen, exist_ok=True)
        _RESOLVED_CONFIG_DIR = chosen
    else:
        os.makedirs(_RESOLVED_CONFIG_DIR, exist_ok=True)

    return os.path.join(_RESOLVED_CONFIG_DIR, "settings.json")


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def send_to_recycle_bin(file_path: str) -> bool:
    """Pindahkan file ke Windows Recycle Bin (FOF_ALLOWUNDO)."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return False
    op = _SHFILEOPSTRUCTW()
    op.wFunc = 3  # FO_DELETE
    op.pFrom = abs_path + "\0\0"
    op.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return rc == 0 and not op.fAnyOperationsAborted

def save_history(history):
    config_path = get_config_path()
    history_path = os.path.join(os.path.dirname(config_path), "history.json")
    tmp_path = history_path + ".tmp"
    try:
        # Tulis ke file sementara lalu ganti secara atomik: history.json tidak
        # pernah setengah tertulis walaupun aplikasi/PC mati saat menyimpan.
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False)
        os.replace(tmp_path, history_path)
    except (IOError, OSError) as e:
        print(f"[DEBUG] Error saving history: {e}")

def load_history():
    config_path = get_config_path()
    history_path = os.path.join(os.path.dirname(config_path), "history.json")
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                print(f"[DEBUG] Loaded history from {history_path}")
                # Populate history_cache
                history_cache = {}
                for src, dest in history:
                    norm_src = os.path.normcase(os.path.normpath(src))
                    history_cache[norm_src] = dest
                return history, history_cache
        else:
            print(f"[DEBUG] No history file found at {history_path}, returning empty list")
    except (json.JSONDecodeError, IOError) as e:
        print(f"[DEBUG] Error loading history: {e}")
    return [], {}

def resource_path(relative_path):
    """Find the file path relative to the application directory."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, relative_path)
    print(f"[DEBUG] Resource path for {relative_path}: {full_path}")
    return full_path

SUPPORTED_IMAGE_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.jfif', '.gif', '.bmp', '.webp',
    '.avif', '.heic', '.heif', '.apng',
    '.tiff', '.tif', '.ico', '.cur', '.icns', '.svg', '.svgz',
    '.tga', '.psd', '.pbm', '.pgm', '.ppm', '.xbm', '.xpm', '.wbmp',
    '.mp4', '.webm', '.mkv', '.mov', '.avi', '.m4v', '.wmv',
)
RAPID_MOVE_MIN_MS = 50
RAPID_MOVE_MAX_MS = 1000
RAPID_MOVE_DEFAULT_MS = 200


def clamp_rapid_interval(value):
    """Pastikan interval rapid move selalu angka valid dalam rentang 50-1000 ms."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return RAPID_MOVE_DEFAULT_MS
    return max(RAPID_MOVE_MIN_MS, min(RAPID_MOVE_MAX_MS, value))


_READABLE_EXTENSIONS = None


def readable_image_extensions():
    """Ekstensi gambar, animasi, dan video yang didukung aplikasi DAN bisa dibaca
    oleh Qt, Pillow/pillow-heif, atau OpenCV di komputer ini.
    Dicek sekali per ekstensi (bukan sekali per file) agar import ribuan file tetap cepat."""
    global _READABLE_EXTENSIONS
    if _READABLE_EXTENSIONS is None:
        qt_formats = {bytes(f).decode("ascii", "ignore").lower() for f in QImageReader.supportedImageFormats()}
        aliases = {
            ".jpg": "jpeg", ".jpeg": "jpeg", ".jfif": "jpeg",
            ".tiff": "tiff", ".tif": "tiff",
            ".heic": "heic", ".heif": "heif",
            ".apng": "png",
        }
        result = set()
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            name = ext.lstrip(".")
            if name in qt_formats or aliases.get(ext, name) in qt_formats:
                result.add(ext)
            elif ext in VIDEO_EXTENSIONS and _HAS_CV2:
                result.add(ext)
            elif ext in (".heic", ".heif") and (_HAS_HEIF or _HAS_PIL):
                result.add(ext)
            elif ext in PIL_FALLBACK_EXTENSIONS and _HAS_PIL:
                result.add(ext)
        _READABLE_EXTENSIONS = frozenset(result)
    return _READABLE_EXTENSIONS


_NATURAL_SPLIT = re.compile(r"(\d+)")


def natural_sort_key(path):
    """Urutan seperti Windows Explorer: IMG_2 sebelum IMG_10."""
    name = os.path.basename(path).lower()
    return [int(part) if part.isdigit() else part for part in _NATURAL_SPLIT.split(name)]


def scan_image_files(
    folder_path,
    extensions=None,
    should_cancel=None,
    on_progress=None,
    include_subfolders=False,
    excluded_dirs=None,
):
    """Satu kali lintasan direktori dengan os.scandir (mendukung rekursi subfolder opsional).
    Tidak memakai glob, jadi nama folder dengan [ ] * ? aman."""
    extensions = extensions or readable_image_extensions()
    files = []
    last_report = time.monotonic()
    excluded = set()
    if excluded_dirs:
        for ex in excluded_dirs:
            if ex:
                excluded.add(os.path.normcase(os.path.normpath(os.path.abspath(ex))))

    stack = [folder_path]
    visited_dirs = set()
    while stack:
        current_dir = stack.pop()
        if should_cancel is not None and should_cancel():
            return None
        norm_cur = os.path.normcase(os.path.normpath(os.path.abspath(current_dir)))
        if norm_cur in visited_dirs:
            continue
        visited_dirs.add(norm_cur)
        if norm_cur != os.path.normcase(os.path.normpath(os.path.abspath(folder_path))) and norm_cur in excluded:
            continue
        try:
            with os.scandir(current_dir) as entries:
                subdirs = []
                for entry in entries:
                    if should_cancel is not None and should_cancel():
                        return None
                    name = entry.name
                    try:
                        if include_subfolders and entry.is_dir(follow_symlinks=False):
                            if not name.startswith(".") and name not in ("__pycache__", "$RECYCLE.BIN", "System Volume Information"):
                                sub_norm = os.path.normcase(os.path.normpath(os.path.abspath(entry.path)))
                                if sub_norm not in excluded:
                                    subdirs.append(entry.path)
                            continue
                        dot = name.rfind(".")
                        if dot <= 0 or name[dot:].lower() not in extensions:
                            continue
                        if not entry.is_file():
                            continue
                    except OSError:
                        continue
                    files.append(entry.path)
                    if on_progress is not None and len(files) % 500 == 0:
                        now = time.monotonic()
                        if now - last_report >= 0.15:
                            last_report = now
                            on_progress(len(files))
                if subdirs:
                    subdirs.sort(key=natural_sort_key, reverse=True)
                    stack.extend(subdirs)
        except OSError:
            if current_dir == folder_path:
                raise
            continue
    files.sort(key=natural_sort_key)
    return files


MIN_FOLDER_SLOTS = 3
MAX_FOLDER_SLOTS = 9
DEFAULT_FOLDER_SLOTS = 5
ALL_SLOT_LETTERS = ("A", "B", "C", "D", "E", "F", "G", "H", "I")


def clamp_folder_slots(count) -> int:
    try:
        val = int(count)
    except (TypeError, ValueError):
        return DEFAULT_FOLDER_SLOTS
    return max(MIN_FOLDER_SLOTS, min(MAX_FOLDER_SLOTS, val))


def load_settings():
    """Load settings from settings.json or return default settings."""
    config_path = get_config_path()
    default_settings = {
        "first_run": True,
        "folder_slot_count": DEFAULT_FOLDER_SLOTS,
        "include_subfolders": False,
        "folder_names": ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"],
        "folder_paths": ["output/A", "output/B", "output/C", "output/D", "output/E"],
        "recent_folders": [],
        "theme_mode": "system",
        "rapid_move_interval": 200,
        "video_muted": False,
        "video_volume": 0.8,
        "custom_theme": {
            "bg_color": "#0e1015",
            "text_color": "#f0f2f5",
            "btn_bg": "#181b23",
            "btn_hover": "#212633",
            "label_bg": "#13161d",
            "menu_bg": "#12141b",
            "menu_text": "#f0f2f5",
            "main_border_color": "#3b82f6",
            "next_border_color": "#10b981",
            "main_shadow": "0 0 10px rgba(59, 130, 246, 0.55)",
            "next_shadow": "0 0 8px rgba(16, 185, 129, 0.45)"
        }
    }
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                print(f"[DEBUG] Loaded settings from {config_path}")
                return settings
        else:
            print(f"[DEBUG] No settings file found at {config_path}, using defaults")
    except (json.JSONDecodeError, IOError) as e:
        print(f"[DEBUG] Error loading settings: {e}")
    return default_settings

_LAST_INTERNAL_SETTINGS_SIG = None


def _file_sig(path):
    """Kembalikan (mtime_ns, size) untuk mendeteksi perubahan file di disk."""
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def save_settings(settings):
    """Save settings to settings.json."""
    global _LAST_INTERNAL_SETTINGS_SIG
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        _LAST_INTERNAL_SETTINGS_SIG = _file_sig(config_path)
        print(f"[DEBUG] Settings saved to {config_path}")
    except IOError as e:
        print(f"[DEBUG] Error saving settings: {e}")


SLOT_ACCENTS = (
    "#8b5cf6", "#10b981", "#f59e0b", "#38bdf8", "#f43f5e",
    "#6366f1", "#14b8a6", "#fb7185", "#94a3b8",
)


def resolve_studio_tokens(owner=None):
    """Kembalikan palet design-token Studio Slate terpadu untuk jendela utama, dialog, menu, dan overlay."""
    if owner is not None and hasattr(owner, "_get_ui_tokens"):
        return owner._get_ui_tokens()
    theme_mode = getattr(owner, "theme_mode", None)
    if not theme_mode:
        theme_mode = load_settings().get("theme_mode", "system")
    palette = QApplication.palette()
    base_color = palette.window().color()
    sys_dark = (base_color.red() * 0.299 + base_color.green() * 0.587 + base_color.blue() * 0.114) < 128
    is_dark = theme_mode == "dark" or (theme_mode == "system" and sys_dark)
    if theme_mode == "custom":
        ct = load_settings().get("custom_theme", {})
        bg = ct.get("bg_color", "#0e1015")
        dark_custom = QColor(bg).lightness() < 128
        return {
            "is_dark": dark_custom,
            "win_bg": bg,
            "stage_bg": ct.get("label_bg", "#13161d"),
            "surface": ct.get("btn_bg", "#181b23"),
            "surface_hover": ct.get("btn_hover", "#212633"),
            "surface_pressed": ct.get("btn_hover", "#2a3040"),
            "border": "#262a36" if dark_custom else "#d6dae3",
            "border_strong": ct.get("main_border_color", "#3b82f6"),
            "next_border": ct.get("next_border_color", "#10b981"),
            "text": ct.get("text_color", "#f0f2f5"),
            "text_muted": "#8b91a1" if dark_custom else "#646b7a",
            "card_bg": ct.get("label_bg", "#151820"),
            "next_card_bg": ct.get("label_bg", "#151820"),
            "menu_bg": ct.get("menu_bg", "#12141b"),
            "menu_text": ct.get("menu_text", "#f0f2f5"),
            "accent": ct.get("main_border_color", "#3b82f6"),
        }
    if is_dark:
        return {
            "is_dark": True,
            "win_bg": "#0e1015",
            "stage_bg": "#13161d",
            "surface": "#181b23",
            "surface_hover": "#212633",
            "surface_pressed": "#2a3040",
            "border": "#262a36",
            "border_strong": "#363c4d",
            "next_border": "#282c39",
            "text": "#f0f2f5",
            "text_muted": "#8b91a1",
            "card_bg": "#151820",
            "next_card_bg": "#151820",
            "menu_bg": "#12141b",
            "menu_text": "#f0f2f5",
            "accent": "#3b82f6",
        }
    return {
        "is_dark": False,
        "win_bg": "#f3f4f7",
        "stage_bg": "#e9ecf2",
        "surface": "#ffffff",
        "surface_hover": "#f0f2f6",
        "surface_pressed": "#e4e7ee",
        "border": "#d6dae3",
        "border_strong": "#bfc6d4",
        "next_border": "#d0d5e0",
        "text": "#16181d",
        "text_muted": "#646b7a",
        "card_bg": "#ffffff",
        "next_card_bg": "#f8f9fb",
        "menu_bg": "#ffffff",
        "menu_text": "#16181d",
        "accent": "#2563eb",
    }


def build_studio_dialog_qss(t: dict) -> str:
    """Bangun stylesheet terpadu untuk semua QDialog, QMessageBox, popup, input, slider, dan scrollbar."""
    accent_hover = "#2563eb" if t["is_dark"] else "#1d4ed8"
    accent_press = "#1d4ed8" if t["is_dark"] else "#1e40af"
    danger_bg = _hex_rgba("#ef4444", 34 if t["is_dark"] else 22)
    danger_border = _hex_rgba("#ef4444", 110 if t["is_dark"] else 95)
    danger_hover = _hex_rgba("#ef4444", 64 if t["is_dark"] else 42)
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
        QLineEdit, QSpinBox, QTextEdit, QTextBrowser {{
            background-color: {t["surface"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 12px;
            selection-background-color: {t["accent"]};
            selection-color: #ffffff;
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
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 18px;
            background: transparent;
            border: none;
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
        QScrollArea {{
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

def render_github_markdown_html(md_text: str, t: dict) -> str:
    """Render teks Markdown GitHub Release menjadi HTML bergaya GitHub Preview yang rapi di QTextBrowser."""
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

        # Lindungi inline code & Markdown link sebelum escaping + bare-URL matching
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
    list_stack = []  # stack of (tag, indent_level)
    in_code = False
    code_lines = []

    def _close_lists(target_level=0):
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
                    f"<p style='font-size:16px; font-weight:700; color:{text_col}; "
                    f"margin:8px 0 3px 0;'>{h_text}</p>"
                    f"<hr style='border:none; background-color:{border_col}; height:1px; margin:0 0 6px 0;'>"
                )
            elif level == 2:
                out.append(
                    f"<p style='font-size:14.5px; font-weight:700; color:{text_col}; "
                    f"margin:8px 0 3px 0;'>{h_text}</p>"
                    f"<hr style='border:none; background-color:{border_col}; height:1px; margin:0 0 5px 0;'>"
                )
            elif level == 3:
                out.append(
                    f"<p style='font-size:13px; font-weight:700; color:{accent_col}; "
                    f"margin:8px 0 3px 0;'>{h_text}</p>"
                )
            else:
                out.append(
                    f"<p style='font-size:12px; font-weight:700; color:{muted_col}; "
                    f"margin:6px 0 2px 0;'>{h_text}</p>"
                )
            continue

        ul_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ul_match or ol_match:
            req_tag = "ul" if ul_match else "ol"
            indent_lvl = 2 if leading >= 2 else 1
            while list_stack and (list_stack[-1][1] > indent_lvl or (list_stack[-1][1] == indent_lvl and list_stack[-1][0] != req_tag)):
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


class UpdateDialog(QDialog):
    def __init__(self, parent=None, current_version="2.0", latest_version=None, release_notes="", download_url=None):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setMinimumSize(490, 400)
        self.resize(550, 460)
        self.parent = parent
        self._tokens = resolve_studio_tokens(parent)
        self.apply_theme()

        t = self._tokens
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_label = QLabel("Software Update")
        title_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {t['text']};")
        header_row.addWidget(title_label)
        header_row.addStretch()

        has_newer = bool(latest_version and self.is_newer_version(current_version, latest_version))
        status_text = "Update Available" if has_newer else "Up to Date"
        status_col = "#f59e0b" if has_newer else "#10b981"
        status_bg = _hex_rgba(status_col, 32 if t["is_dark"] else 24)
        status_border = _hex_rgba(status_col, 110 if t["is_dark"] else 90)
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {status_col}; "
            f"background-color: {status_bg}; border: 1px solid {status_border}; "
            f"border-radius: 6px; padding: 3px 10px;"
        )
        header_row.addWidget(status_label)
        layout.addLayout(header_row)

        ver_card = QFrame()
        ver_card.setObjectName("studioCard")
        version_layout = QHBoxLayout(ver_card)
        version_layout.setContentsMargins(14, 10, 14, 10)
        version_layout.setSpacing(16)

        current_label = QLabel(
            f"<span style='color:{t['text_muted']}; font-size:11px;'>INSTALLED</span><br>"
            f"<b style='font-size:13px; color:{t['text']};'>{current_version}</b>"
        )
        version_layout.addWidget(current_label)
        version_layout.addStretch()

        latest_str = latest_version if latest_version else "Unknown"
        latest_label = QLabel(
            f"<span style='color:{t['text_muted']}; font-size:11px;'>LATEST RELEASE</span><br>"
            f"<b style='font-size:13px; color:{t['accent']};'>{latest_str}</b>"
        )
        latest_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        version_layout.addWidget(latest_label)
        layout.addWidget(ver_card)

        notes_label = QLabel("RELEASE NOTES")
        notes_label.setStyleSheet(
            f"font-size: 11px; font-weight: 700; letter-spacing: 0.8px; color: {t['text_muted']};"
        )
        layout.addWidget(notes_label)

        self.notes_text = QTextBrowser()
        self.notes_text.setObjectName("releaseNotesView")
        self.notes_text.setOpenExternalLinks(True)
        self.notes_text.setReadOnly(True)
        self.notes_text.document().setDocumentMargin(2)
        self.notes_text.document().setIndentWidth(15)
        self.notes_text.setHtml(render_github_markdown_html(release_notes, t))
        self.notes_text.setMinimumHeight(180)
        layout.addWidget(self.notes_text, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setMinimumWidth(96)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        self.download_btn = QPushButton("Download Update")
        self.download_btn.setObjectName("primaryBtn")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setIcon(make_vector_icon("download", "#ffffff" if has_newer else t["text_muted"], 14))
        self.download_btn.setIconSize(QSize(14, 14))
        self.download_btn.setEnabled(bool(download_url and has_newer))
        self.download_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
        btn_layout.addWidget(self.download_btn)

        if has_newer and download_url:
            self.download_btn.setDefault(True)
            self.download_btn.setFocus()
        else:
            close_btn.setDefault(True)
            close_btn.setFocus()

        layout.addLayout(btn_layout)

    def apply_theme(self):
        self._tokens = resolve_studio_tokens(self.parent)
        self.setStyleSheet(build_studio_dialog_qss(self._tokens))

    def is_newer_version(self, current, latest):
        try:
            version_pattern = r'^(\d+\.\d+(?:\.\d+)?)(?:-([a-zA-Z]+))?$'
            current_match = re.match(version_pattern, current)
            if not current_match:
                print(f"[DEBUG] Invalid current version format: {current}")
                return False
            current_num = current_match.group(1)  # e.g., '1.0' or '1.1.0'
            current_qual = current_match.group(2) or 'Stable'

            latest_match = re.match(version_pattern, latest)
            if not latest_match:
                print(f"[DEBUG] Invalid latest version format: {latest}")
                return False
            latest_num = latest_match.group(1)  # e.g., '1.2' or '1.2.0'
            latest_qual = latest_match.group(2) or 'Stable'

            # Split numeric parts, padding with zeros if needed
            current_parts = [int(x) for x in current_num.split('.')]
            latest_parts = [int(x) for x in latest_num.split('.')]
            # Ensure equal length for comparison
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(latest_parts) < 3:
                latest_parts.append(0)

            if latest_parts > current_parts:
                return True
            elif latest_parts < current_parts:
                return False

            qualifier_priority = {'Stable': 3, 'Beta': 2, 'Alpha': 1}
            current_priority = qualifier_priority.get(current_qual, 0)
            latest_priority = qualifier_priority.get(latest_qual, 0)
            return latest_priority > current_priority

        except (ValueError, AttributeError) as e:
            print(f"[DEBUG] Error comparing versions: {e}")
            return False

class UpdateCheckThread(QThread):
    update_checked = Signal(str, str, str)  # Signal untuk versi terbaru, catatan rilis, dan URL unduhan
    error_occurred = Signal(str)  # Signal untuk kesalahan

    def __init__(self, parent=None, manual=False):
        super().__init__(parent)
        self.manual = manual  # True = dipicu dari menu Help > Check for Updates
        self.api_url = "https://api.github.com/repos/Zy0x/Image-Sorter/releases/latest"

    def run(self):
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            release_info = response.json()
            latest_version = release_info.get("tag_name", "").lstrip("v")  # Menghapus 'v' dari tag
            release_notes = release_info.get("body", "No release notes provided.")
            download_url = release_info.get("html_url", "")
            self.update_checked.emit(latest_version, release_notes or "", download_url)
        except (requests.RequestException, ValueError) as e:
            self.error_occurred.emit(str(e))

class AboutDialog(QDialog):
    VERSION = "2.1.19-Stable"
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Image Sorter")
        self.setMinimumSize(500, 420)
        self.resize(520, 440)
        self.parent = parent
        self._tokens = resolve_studio_tokens(parent)
        self.apply_theme()

        t = self._tokens
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(14)
        self.logo_label = QLabel()
        self.logo_label.setPixmap(QIcon(resource_path("assets/icons/app_icon.png")).pixmap(52, 52))
        title_layout.addWidget(self.logo_label)

        title_info = QVBoxLayout()
        title_info.setSpacing(3)
        self.title_label = QLabel("Image Sorter")
        self.title_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t['text']};")
        self.version_label = QLabel(f"Version {self.VERSION}  ·  Studio Edition")
        self.version_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {t['accent']};"
        )
        title_info.addWidget(self.title_label)
        title_info.addWidget(self.version_label)
        title_layout.addLayout(title_info)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        desc_text = (
            "High-speed desktop media organization tool built for instant photo, GIF, and video "
            "sorting with zero file-lock playback, perceptual duplicate detection, and customizable 3–9 slot workflows."
        )
        self.desc_label = QLabel(desc_text)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(f"font-size: 13px; color: {t['text_muted']};")
        layout.addWidget(self.desc_label)

        feat_card = QFrame()
        feat_card.setObjectName("studioCard")
        feat_lay = QVBoxLayout(feat_card)
        feat_lay.setContentsMargins(16, 12, 16, 12)
        feat_lay.setSpacing(7)

        features_title = QLabel("CAPABILITIES")
        features_title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {t['text_muted']};"
        )
        feat_lay.addWidget(features_title)

        features_list = [
            "Instant 1–9 key & hold-to-Rapid-Move sorting across 3–9 custom folder slots",
            "Synchronized native-FPS video & audio playback with interactive timeline scrubbing",
            "Full-size inspection with cursor-anchored zoom, drag-to-pan, and frame stepping",
            "64-bit Perceptual dHash duplicate & visually similar media scanner",
            "Atomic Undo history & collision-safe auto-renaming (never overwrites files)",
        ]

        for feature in features_list:
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel("•")
            dot.setStyleSheet(f"color: {t['accent']}; font-size: 14px; font-weight: 700;")
            dot.setFixedWidth(10)
            item = QLabel(feature)
            item.setWordWrap(True)
            item.setStyleSheet(f"font-size: 12px; color: {t['text']};")
            row.addWidget(dot, 0, Qt.AlignTop)
            row.addWidget(item, 1)
            feat_lay.addLayout(row)

        layout.addWidget(feat_card)
        layout.addStretch()

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        telegram_btn = QPushButton("Telegram · Thea")
        telegram_btn.setIcon(QIcon(resource_path("assets/icons/telegram.png")))
        telegram_btn.setIconSize(QSize(16, 16))
        telegram_btn.setCursor(Qt.PointingHandCursor)
        telegram_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/ThuandMuda")))
        footer_layout.addWidget(telegram_btn)

        github_btn = QPushButton("GitHub · Zy0x")
        github_btn.setIcon(QIcon(resource_path("assets/icons/github.png")))
        github_btn.setIconSize(QSize(16, 16))
        github_btn.setCursor(Qt.PointingHandCursor)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Zy0x")))
        footer_layout.addWidget(github_btn)

        footer_layout.addStretch()

        ok_button = QPushButton("Close")
        ok_button.setObjectName("primaryBtn")
        ok_button.setCursor(Qt.PointingHandCursor)
        ok_button.setMinimumWidth(96)
        ok_button.clicked.connect(self.accept)
        footer_layout.addWidget(ok_button)
        layout.addLayout(footer_layout)

    def apply_theme(self):
        self._tokens = resolve_studio_tokens(self.parent)
        self.setStyleSheet(build_studio_dialog_qss(self._tokens))


class ShortcutsGuideDialog(QDialog):
    """Referensi shortcut bergaya Studio Slate dengan QScrollArea adaptif dan baris anti-terpotong."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts & Quick Guide")
        self.parent = parent
        t = resolve_studio_tokens(parent)

        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRectF(0, 0, 1280, 720).toRect()
        min_w = min(700, max(560, avail.width() - 40))
        min_h = min(460, max(360, avail.height() - 60))
        self.setMinimumSize(min_w, min_h)
        self.resize(min(760, max(min_w, int(avail.width() * 0.65))), min(610, max(min_h, int(avail.height() * 0.82))))

        key_bg = t["surface"]
        key_border = t["border_strong"]
        key_bottom = "#4b5369" if t["is_dark"] else "#adb5c7"

        base_qss = build_studio_dialog_qss(t)
        self.setStyleSheet(base_qss + f"""
            QLabel#catHeader {{
                color: {t["accent"]};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.9px;
            }}
            QLabel#actionLabel {{
                color: {t["text"]};
                font-size: 12px;
            }}
            QLabel#keyCap {{
                background-color: {key_bg};
                color: {t["text"]};
                border: 1px solid {key_border};
                border-bottom: 2px solid {key_bottom};
                border-radius: 5px;
                padding: 2px 8px;
                font-family: "Segoe UI", "Inter", sans-serif;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#keyJoin {{
                color: {t["text_muted"]};
                font-size: 11px;
                padding: 0 2px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        header_row = QHBoxLayout()
        title_lbl = QLabel("Keyboard Shortcuts & Quick Guide")
        title_lbl.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {t['text']};")
        header_row.addWidget(title_lbl)
        header_row.addStretch()
        esc_lbl = QLabel("F1  ·  Esc to close")
        esc_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {t['text_muted']}; "
            f"background-color: {t['stage_bg']}; border: 1px solid {t['border']}; "
            f"border-radius: 6px; padding: 3px 9px;"
        )
        header_row.addWidget(esc_lbl)
        root.addLayout(header_row)

        wf_bar = QFrame()
        wf_bar.setObjectName("workflowBar")
        wf_lay = QHBoxLayout(wf_bar)
        wf_lay.setContentsMargins(14, 9, 14, 9)
        wf_lay.setSpacing(8)
        wf_text = QLabel(
            f"<span style='color:{t['text_muted']}; font-weight:600;'>Quick Workflow:</span> &nbsp;"
            f"<b>1.</b> Configure 3–9 folder slots (<i>Settings → Folder Settings</i>) &nbsp;·&nbsp; "
            f"<b>2.</b> Import media (<b>Ctrl+O</b> or drag &amp; drop) &nbsp;·&nbsp; "
            f"<b>3.</b> Press or hold <b>1–9</b> to sort"
        )
        wf_text.setWordWrap(True)
        wf_text.setStyleSheet("font-size: 12px;")
        wf_lay.addWidget(wf_text)
        root.addWidget(wf_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        cols = QHBoxLayout(scroll_content)
        cols.setContentsMargins(2, 4, 10, 4)
        cols.setSpacing(24)

        left_sections = [
            ("SORTING", [
                ("Move to Folder 1–9", [("key", "1"), ("join", "–"), ("key", "9")]),
                ("Rapid Move (continuous)", [("join", "Hold"), ("key", "1"), ("join", "–"), ("key", "9")]),
                ("Undo last move", [("key", "Ctrl"), ("key", "Z")]),
            ]),
            ("NAVIGATION", [
                ("Previous / Next media", [("key", "←"), ("key", "→")]),
                ("Skip to next unmoved", [("key", "Space")]),
                ("First / Last media", [("key", "Home"), ("key", "End")]),
                ("Jump to media number", [("key", "Ctrl"), ("key", "G")]),
            ]),
        ]

        right_sections = [
            ("VIEW & PLAYBACK", [
                ("Full-size zoom preview", [("key", "F")]),
                ("Play / Pause video or GIF", [("key", "P")]),
                ("Mute / Unmute video sound", [("key", "M")]),
                ("Find duplicate / similar", [("key", "Ctrl"), ("key", "D")]),
                ("Include subfolders", [("key", "Ctrl"), ("key", "Shift"), ("key", "S")]),
                ("Hide moved media", [("key", "Ctrl"), ("key", "H")]),
                ("Shortcuts reference", [("key", "F1")]),
            ]),
            ("FILE & MOUSE", [
                ("Import folder", [("key", "Ctrl"), ("key", "O")]),
                ("Show in File Explorer", [("key", "Ctrl"), ("key", "E")]),
                ("Move to Recycle Bin", [("key", "Delete")]),
                ("Rapid Move with mouse", [("join", "Hold"), ("key", "Click 1–9")]),
                ("Zoom preview with mouse", [("key", "Double-Click")]),
            ]),
        ]

        cols.addLayout(self._build_column(left_sections), 1)
        cols.addLayout(self._build_column(right_sections), 1)
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        note = QLabel("Duplicate filenames in destination folders are auto-renamed — existing files are never overwritten.")
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: 11px; color: {t['text_muted']};")
        footer.addWidget(note, 1)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryBtn")
        close_btn.setMinimumWidth(92)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _build_column(self, sections):
        col = QVBoxLayout()
        col.setSpacing(3)
        for s_idx, (sec_title, rows) in enumerate(sections):
            if s_idx > 0:
                col.addSpacing(12)
            hdr = QLabel(sec_title)
            hdr.setObjectName("catHeader")
            col.addWidget(hdr)
            col.addSpacing(3)

            for label_text, tokens in rows:
                row_widget = QWidget()
                row_widget.setMinimumHeight(34)
                row_lay = QHBoxLayout(row_widget)
                row_lay.setContentsMargins(0, 4, 0, 4)
                row_lay.setSpacing(5)

                act_lbl = QLabel(label_text)
                act_lbl.setObjectName("actionLabel")
                act_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                row_lay.addWidget(act_lbl, 1)

                for kind, val in tokens:
                    t_lbl = QLabel(val)
                    if kind == "key":
                        t_lbl.setObjectName("keyCap")
                        t_lbl.setAlignment(Qt.AlignCenter)
                        t_lbl.setFixedHeight(24)
                        if len(val) == 1:
                            t_lbl.setMinimumWidth(26)
                    else:
                        t_lbl.setObjectName("keyJoin")
                        t_lbl.setAlignment(Qt.AlignCenter)
                    row_lay.addWidget(t_lbl, 0, Qt.AlignVCenter)

                col.addWidget(row_widget)
                div = QFrame()
                div.setObjectName("hairline")
                col.addWidget(div)

        col.addStretch()
        return col


def _dispose_qtmm_video_session(player, output, sink, buf):
    """Hentikan dan lepaskan resource QMediaPlayer/QAudioOutput/QVideoSink/QBuffer tanpa mengunci file disk."""
    if sink is not None:
        try:
            sink.videoFrameChanged.disconnect()
        except Exception:
            pass
        sink.deleteLater()
    if player is not None:
        try:
            player.stop()
            player.setVideoSink(None)
            player.setAudioOutput(None)
            player.setSource(QUrl())
        except Exception:
            pass
        player.deleteLater()
    if output is not None:
        output.deleteLater()
    if buf is not None:
        try:
            buf.close()
        except Exception:
            pass
        buf.deleteLater()


def _create_qtmm_video_session(owner, video_path: str, muted: bool, volume: float, on_frame, on_error=None):
    """Bangun QMediaPlayer + QAudioOutput + QVideoSink dari buffer memori (<=120 MB) untuk playback video+suara sinkron."""
    if not _HAS_QTMULTIMEDIA or not video_path or not os.path.exists(video_path):
        return None
    fsize = os.path.getsize(video_path)
    if fsize <= 0 or fsize > 120 * 1024 * 1024:
        return None
    with open(video_path, "rb") as f:
        raw = f.read()
    qbytes = QByteArray(raw)
    qbuf = QBuffer(owner)
    qbuf.setData(qbytes)
    qbuf.open(QIODevice.ReadOnly)
    output = QAudioOutput(owner)
    output.setVolume(max(0.0, min(1.0, float(volume))))
    output.setMuted(bool(muted))
    sink = QVideoSink(owner)
    if on_frame is not None:
        sink.videoFrameChanged.connect(on_frame)
    player = QMediaPlayer(owner)
    player.setAudioOutput(output)
    player.setVideoSink(sink)
    player.setLoops(QMediaPlayer.Infinite)
    if on_error is not None:
        player.errorOccurred.connect(on_error)
    player.setSourceDevice(qbuf, QUrl.fromLocalFile(video_path))
    return player, output, sink, qbuf, qbytes


class ImagePreviewDialog(QDialog):
    """Dialog pratinjau ukuran penuh dengan Smart Double-Click Zoom, Cursor-Anchored Wheel Zoom,
    Drag-to-Pan, serta Live Playback & Frame Stepping untuk GIF, Animated WebP/APNG/AVIF, dan Video."""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.parent = parent
        self.zoom_factor = 1.0
        self._fit_zoom = 1.0
        self._fit_mode = True
        self._pan_active = False
        self._pan_moved = False
        self._pan_start_pos = None
        self._pan_start_h = 0
        self._pan_start_v = 0
        self._scaled_frame_cache = {}
        self._scaled_cache_size = (0, 0)
        self._video_thread = None
        self._audio_player = None
        self._audio_output = None
        self._video_sink = None
        self._audio_buffer = None
        self._audio_bytes = None
        self._using_qtmm_video = False
        self._frame_step_mode = False
        self._seeking_preview = False
        self._video_duration_ms = 0
        self._audio_muted = bool(getattr(parent, "video_muted", False)) if parent else False

        is_vid = is_video_file(image_path)
        self._is_video = is_vid
        if is_vid:
            first_pix = load_pixmap(image_path, 1280, 960)
            self.anim_frames = [(first_pix, 40)] if not first_pix.isNull() else []
        else:
            self.anim_frames = load_animation_frames(image_path, 1600, 1200, max_frames=240)

        self._anim_index = 0
        self._anim_playing = len(self.anim_frames) > 1 or is_vid
        self._anim_timer = QTimer(self)
        self._anim_timer.setSingleShot(True)
        self._anim_timer.timeout.connect(self._advance_anim_frame)

        if self.anim_frames:
            self.base_pixmap = self.anim_frames[0][0]
        else:
            self.base_pixmap = load_pixmap(image_path)

        filename = os.path.basename(image_path)
        w = self.base_pixmap.width()
        h = self.base_pixmap.height()
        if is_vid:
            vw, vh, _vsz, _vfps, _vcnt, _vdur = read_video_metadata(image_path)
            if vw > 0 and vh > 0:
                w, h = vw, vh
            if _vdur > 0:
                self._video_duration_ms = int(round(_vdur * 1000))
        self._orig_w, self._orig_h = w, h
        self.setWindowTitle(f"Preview — {filename} ({w}×{h})")
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRectF(0, 0, 1280, 720).toRect()
        min_dlg_w = min(680, max(540, avail.width() - 32))
        min_dlg_h = min(460, max(380, avail.height() - 48))
        dlg_w = min(980, max(min_dlg_w, int(avail.width() * 0.84)))
        dlg_h = min(720, max(min_dlg_h, int(avail.height() * 0.84)))
        self.setMinimumSize(min_dlg_w, min_dlg_h)
        self.resize(dlg_w, dlg_h)

        is_dark = True
        if self.parent and hasattr(self.parent, "theme_mode"):
            is_dark = (
                self.parent.theme_mode in ("dark", "custom")
                or (self.parent.theme_mode == "system" and self.parent.is_system_dark())
            )
        bg = "#101218" if is_dark else "#f4f5f8"
        bar_bg = "#171a23" if is_dark else "#ffffff"
        canvas_bg = "#0c0e13" if is_dark else "#e9ecf2"
        text = "#eff1f5" if is_dark else "#16181d"
        muted = "#848b9c" if is_dark else "#666d7c"
        btn_bg = "#1e222d" if is_dark else "#f1f3f7"
        btn_hover = "#282d3b" if is_dark else "#e4e7ee"
        border = "#272b38" if is_dark else "#d4d8e2"
        thumb = "#3a4052" if is_dark else "#b8bec8"
        accent = "#3b82f6" if is_dark else "#2563eb"
        self._icon_ink = text

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {text}; }}
            QFrame#previewHeaderBar, QFrame#previewFooterBar {{
                background-color: {bar_bg};
                border: 1px solid {border};
                border-radius: 9px;
            }}
            QScrollArea {{
                background-color: {canvas_bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QLabel {{ color: {text}; background: transparent; border: none; }}
            QPushButton {{
                background-color: {btn_bg};
                color: {text};
                border: 1px solid {border};
                padding: 4px 11px;
                font-size: 12px;
                font-weight: 600;
                border-radius: 6px;
                min-height: 26px;
            }}
            QPushButton:hover {{ background-color: {btn_hover}; border-color: {accent}; }}
            QSlider::groove:horizontal {{
                background: {border};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {text};
                width: 11px;
                height: 11px;
                margin: -4px 0;
                border-radius: 5px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {thumb};
                min-height: 28px;
                border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {thumb};
                min-width: 28px;
                border-radius: 3px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # ---- Header Bar Rapi: Info File (kiri) + Kontrol Zoom & Close (kanan) ----
        header_frame = QFrame()
        header_frame.setObjectName("previewHeaderBar")
        toolbar = QHBoxLayout(header_frame)
        toolbar.setContentsMargins(12, 6, 8, 6)
        toolbar.setSpacing(6)

        self.info_label = QLabel(f"{filename}  ({w}×{h})")
        self.info_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.info_label.setToolTip(image_path)
        self.info_label.setMinimumWidth(160)
        toolbar.addWidget(self.info_label, stretch=1)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setToolTip("Zoom Out (−)")
        zoom_out_btn.setFixedWidth(32)
        zoom_out_btn.clicked.connect(lambda: self.adjust_zoom(0.8))
        fit_btn = QPushButton("Fit (0)")
        fit_btn.clicked.connect(self.fit_to_window)
        actual_btn = QPushButton("100% (1)")
        actual_btn.clicked.connect(self.reset_actual_size)
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom In (+)")
        zoom_in_btn.setFixedWidth(32)
        zoom_in_btn.clicked.connect(lambda: self.adjust_zoom(1.25))

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(18)
        sep.setStyleSheet(f"color: {border}; background: {border}; border: none;")

        close_btn = QPushButton("Close (Esc)")
        close_btn.clicked.connect(self.accept)

        for b in (zoom_out_btn, fit_btn, actual_btn, zoom_in_btn):
            b.setCursor(Qt.PointingHandCursor)
            toolbar.addWidget(b)
        toolbar.addWidget(sep)
        close_btn.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(close_btn)
        layout.addWidget(header_frame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(f"background-color: {canvas_bg};")
        self.scroll_area.setWidget(self.preview_label)
        layout.addWidget(self.scroll_area, stretch=1)

        # ---- Footer Bar: Kontrol Video/Animasi & Seekbar (kiri) + Hint Interaksi (kanan) ----
        footer_frame = QFrame()
        footer_frame.setObjectName("previewFooterBar")
        footer_lay = QHBoxLayout(footer_frame)
        footer_lay.setContentsMargins(10, 6, 12, 6)
        footer_lay.setSpacing(8)

        self.prev_frame_btn = None
        self.play_pause_btn = None
        self.next_frame_btn = None
        self.mute_btn = None
        self.seek_slider = None
        self.cur_time_lbl = None
        self.tot_time_lbl = None

        if len(self.anim_frames) > 1 or is_vid:
            self.prev_frame_btn = QPushButton("")
            self.prev_frame_btn.setIcon(make_vector_icon("step_prev", self._icon_ink, 13))
            self.prev_frame_btn.setIconSize(QSize(13, 13))
            self.prev_frame_btn.setFixedWidth(34)
            self.prev_frame_btn.setToolTip("Previous Frame ([)")
            self.prev_frame_btn.clicked.connect(lambda: self.step_frame(-1))

            self.play_pause_btn = QPushButton("Pause")
            self.play_pause_btn.setIcon(make_vector_icon("pause", self._icon_ink, 13))
            self.play_pause_btn.setIconSize(QSize(13, 13))
            self.play_pause_btn.setToolTip("Play / Pause (Space / P)")
            self.play_pause_btn.clicked.connect(self.toggle_animation)

            self.next_frame_btn = QPushButton("")
            self.next_frame_btn.setIcon(make_vector_icon("step_next", self._icon_ink, 13))
            self.next_frame_btn.setIconSize(QSize(13, 13))
            self.next_frame_btn.setFixedWidth(34)
            self.next_frame_btn.setToolTip("Next Frame (])")
            self.next_frame_btn.clicked.connect(lambda: self.step_frame(1))

            for ab in (self.prev_frame_btn, self.play_pause_btn, self.next_frame_btn):
                ab.setCursor(Qt.PointingHandCursor)
                ab.setFocusPolicy(Qt.NoFocus)
                footer_lay.addWidget(ab)

            if is_vid:
                self.cur_time_lbl = QLabel("0:00")
                self.cur_time_lbl.setStyleSheet(f"font-size: 11px; color: {text}; font-family: Consolas, monospace;")
                self.seek_slider = _ClickSeekSlider(Qt.Horizontal)
                self.seek_slider.setRange(0, max(100, self._video_duration_ms))
                self.seek_slider.setFocusPolicy(Qt.NoFocus)
                self.seek_slider.setMinimumWidth(140)
                self.seek_slider.sliderPressed.connect(lambda: setattr(self, "_seeking_preview", True))
                self.seek_slider.sliderMoved.connect(lambda v: self.cur_time_lbl.setText(format_duration(v / 1000.0)))
                self.seek_slider.sliderReleased.connect(self._on_preview_seek_released)
                self.seek_slider.seek_clicked.connect(self._on_preview_seek_clicked)
                tot_txt = format_duration(self._video_duration_ms / 1000.0) if self._video_duration_ms > 0 else "0:00"
                self.tot_time_lbl = QLabel(tot_txt)
                self.tot_time_lbl.setStyleSheet(f"font-size: 11px; color: {muted}; font-family: Consolas, monospace;")

                footer_lay.addWidget(self.cur_time_lbl)
                footer_lay.addWidget(self.seek_slider, stretch=1)
                footer_lay.addWidget(self.tot_time_lbl)

                mute_txt = "Muted" if self._audio_muted else "Sound"
                mute_icon = "sound_off" if self._audio_muted else "sound_on"
                self.mute_btn = QPushButton(mute_txt)
                self.mute_btn.setIcon(make_vector_icon(mute_icon, self._icon_ink, 14))
                self.mute_btn.setIconSize(QSize(14, 14))
                self.mute_btn.setToolTip("Toggle Video Sound Mute / Unmute (M)")
                self.mute_btn.setCursor(Qt.PointingHandCursor)
                self.mute_btn.setFocusPolicy(Qt.NoFocus)
                self.mute_btn.clicked.connect(self.toggle_audio_mute)
                footer_lay.addWidget(self.mute_btn)

        if self.seek_slider is None:
            footer_lay.addStretch(1)

        self.hint_label = QLabel("Double-Click: Zoom · Drag: Pan · Wheel: Zoom")
        self.hint_label.setStyleSheet(f"font-size: 11px; color: {muted};")
        self.hint_label.setVisible(self.width() >= 780)
        footer_lay.addWidget(self.hint_label)
        layout.addWidget(footer_frame)

        # Pasang eventFilter pada viewport dan label untuk Drag-to-Pan & Smart Double-Click Zoom
        self.scroll_area.viewport().installEventFilter(self)
        self.preview_label.installEventFilter(self)

        self.update_preview()
        if is_vid:
            self._start_preview_audio(image_path)
            self._received_video_chunks = False
            if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                raw_qimgs = decode_video_qimages(image_path, 1280, 960, max_frames=30)
                if raw_qimgs:
                    self._on_preview_video_chunk(image_path, raw_qimgs)
            else:
                vt = VideoDecodeThread(image_path, max_width=1280, max_height=960, max_frames=120, chunk_size=10, parent=self)
                vt.chunk_ready.connect(self._on_preview_video_chunk)
                self._video_thread = vt
                vt.start()
        elif self._anim_playing:
            self._schedule_next_anim_frame()

    def _start_preview_audio(self, video_path: str):
        self._stop_preview_audio()
        try:
            vol = float(getattr(self.parent, "video_volume", 0.8)) if self.parent else 0.8
            session = _create_qtmm_video_session(
                self,
                video_path,
                muted=self._audio_muted,
                volume=vol,
                on_frame=self._on_preview_video_frame,
                on_error=self._on_preview_media_error,
            )
            if session is None:
                self._using_qtmm_video = False
                return
            (
                self._audio_player,
                self._audio_output,
                self._video_sink,
                self._audio_buffer,
                self._audio_bytes,
            ) = session
            self._using_qtmm_video = True
            self._frame_step_mode = False
            self._audio_player.positionChanged.connect(self._on_preview_position_changed)
            self._audio_player.durationChanged.connect(self._on_preview_duration_changed)
            if self._anim_playing:
                self._audio_player.play()
        except Exception as e:
            print(f"[DEBUG] Preview media init warning: {e}")
            self._using_qtmm_video = False

    def _on_preview_position_changed(self, pos_ms: int):
        if self._seeking_preview:
            return
        if self.seek_slider is not None:
            self.seek_slider.setValue(int(pos_ms))
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))

    def _on_preview_duration_changed(self, dur_ms: int):
        if dur_ms > 0:
            self._video_duration_ms = int(dur_ms)
            if self.seek_slider is not None:
                self.seek_slider.setRange(0, int(dur_ms))
            if self.tot_time_lbl is not None:
                self.tot_time_lbl.setText(format_duration(dur_ms / 1000.0))

    def _on_preview_seek_released(self):
        self._seeking_preview = False
        if self._audio_player is not None and self.seek_slider is not None:
            self._audio_player.setPosition(int(self.seek_slider.value()))

    def _on_preview_seek_clicked(self, pos_ms: int):
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))
        if self._audio_player is not None:
            self._audio_player.setPosition(int(pos_ms))

    def _on_preview_media_error(self, error, error_string=""):
        print(f"[DEBUG] Preview QtMultimedia error ({error}): {error_string}")
        self._using_qtmm_video = False
        self._stop_preview_audio()
        if self._anim_playing and not self._anim_timer.isActive() and len(self.anim_frames) > 1:
            self._schedule_next_anim_frame()

    def _on_preview_video_frame(self, frame):
        if not self._using_qtmm_video or not self._anim_playing or self._frame_step_mode:
            return
        if not frame.isValid():
            return
        qimg = frame.toImage()
        if qimg.isNull():
            return
        pix = QPixmap.fromImage(qimg)
        self.base_pixmap = pix
        hbar = self.scroll_area.horizontalScrollBar()
        vbar = self.scroll_area.verticalScrollBar()
        old_h = hbar.value()
        old_v = vbar.value()
        if self._fit_mode:
            self._fit_zoom = self._compute_fit_zoom()
            self.zoom_factor = self._fit_zoom
        tw = max(16, int(round(pix.width() * self.zoom_factor)))
        th = max(16, int(round(pix.height() * self.zoom_factor)))
        mode = Qt.SmoothTransformation if pix.width() * pix.height() <= 1920 * 1080 else Qt.FastTransformation
        scaled = pix.scaled(tw, th, Qt.KeepAspectRatio, mode)
        if self._fit_mode:
            self.preview_label.setMinimumSize(1, 1)
        else:
            self.preview_label.setMinimumSize(scaled.size())
        self.preview_label.setPixmap(scaled)
        if not self._fit_mode:
            hbar.setValue(old_h)
            vbar.setValue(old_v)

    def _stop_preview_audio(self):
        self._using_qtmm_video = False
        _dispose_qtmm_video_session(
            self._audio_player,
            self._audio_output,
            self._video_sink,
            self._audio_buffer,
        )
        self._audio_player = None
        self._audio_output = None
        self._video_sink = None
        self._audio_buffer = None
        self._audio_bytes = None

    def toggle_audio_mute(self):
        self._audio_muted = not self._audio_muted
        if self._audio_output is not None:
            self._audio_output.setMuted(self._audio_muted)
        if self.mute_btn is not None:
            self.mute_btn.setText("Muted" if self._audio_muted else "Sound")
            self.mute_btn.setIcon(make_vector_icon("sound_off" if self._audio_muted else "sound_on", self._icon_ink, 14))
        if self.parent and hasattr(self.parent, "set_video_muted"):
            self.parent.set_video_muted(self._audio_muted, notify=False)

    def _on_preview_video_chunk(self, video_path: str, chunk: list):
        if not chunk:
            return
        new_pix_frames = [(QPixmap.fromImage(qimg), delay) for qimg, delay in chunk if not qimg.isNull()]
        if not new_pix_frames:
            return
        if not getattr(self, "_received_video_chunks", False):
            self._received_video_chunks = True
            self.anim_frames = new_pix_frames
            self._anim_index = 0
            if not self._using_qtmm_video:
                self.base_pixmap = self.anim_frames[0][0]
                self._scaled_frame_cache.clear()
                self._render_current_frame_preserve_scroll()
        else:
            self.anim_frames.extend(new_pix_frames)
            if not self._using_qtmm_video or self._frame_step_mode:
                self._update_info_label()
        if not self._using_qtmm_video and self._anim_playing and not self._anim_timer.isActive() and len(self.anim_frames) > 1:
            self._schedule_next_anim_frame()

    def _schedule_next_anim_frame(self):
        if self._using_qtmm_video and not self._frame_step_mode:
            return
        if not self._anim_playing or len(self.anim_frames) <= 1:
            return
        delay = self.anim_frames[self._anim_index][1]
        self._anim_timer.start(max(20, int(delay)))

    def _advance_anim_frame(self):
        if self._using_qtmm_video and not self._frame_step_mode:
            return
        if len(self.anim_frames) <= 1:
            return
        self._anim_index = (self._anim_index + 1) % len(self.anim_frames)
        self.base_pixmap = self.anim_frames[self._anim_index][0]
        self._render_current_frame_preserve_scroll()
        if self._anim_playing:
            self._schedule_next_anim_frame()

    def toggle_animation(self):
        if len(self.anim_frames) <= 1 and not self._is_video:
            return
        self._anim_playing = not self._anim_playing
        if self.play_pause_btn is not None:
            self.play_pause_btn.setText("Pause" if self._anim_playing else "Play")
            self.play_pause_btn.setIcon(make_vector_icon("pause" if self._anim_playing else "play", self._icon_ink, 13))
        if self._anim_playing:
            self._frame_step_mode = False
            if self._using_qtmm_video and self._audio_player is not None:
                self._anim_timer.stop()
                self._audio_player.play()
            else:
                self._schedule_next_anim_frame()
        else:
            if self._audio_player is not None:
                self._audio_player.pause()
            self._anim_timer.stop()
        self._update_info_label()

    def step_frame(self, delta: int):
        if len(self.anim_frames) <= 1:
            return
        self._anim_playing = False
        self._frame_step_mode = True
        self._anim_timer.stop()
        if self._audio_player is not None:
            self._audio_player.pause()
        if self.play_pause_btn is not None:
            self.play_pause_btn.setText("Play")
            self.play_pause_btn.setIcon(make_vector_icon("play", self._icon_ink, 13))
        self._anim_index = (self._anim_index + delta) % len(self.anim_frames)
        self.base_pixmap = self.anim_frames[self._anim_index][0]
        self._render_current_frame_preserve_scroll()

    def _compute_fit_zoom(self):
        if self.base_pixmap.isNull():
            return 1.0
        vp = self.scroll_area.viewport().size()
        tw = max(100, vp.width() - 8)
        th = max(100, vp.height() - 8)
        bw = max(1, self.base_pixmap.width())
        bh = max(1, self.base_pixmap.height())
        return min(tw / bw, th / bh)

    def _is_pannable(self):
        hbar = self.scroll_area.horizontalScrollBar()
        vbar = self.scroll_area.verticalScrollBar()
        return (hbar.maximum() > 0) or (vbar.maximum() > 0) or (not self._fit_mode and self.zoom_factor > self._fit_zoom * 1.02)

    def _update_cursor(self):
        if self._pan_active:
            self.scroll_area.viewport().setCursor(Qt.ClosedHandCursor)
        elif self._is_pannable():
            self.scroll_area.viewport().setCursor(Qt.OpenHandCursor)
        else:
            self.scroll_area.viewport().setCursor(Qt.ArrowCursor)

    def _zoom_to_at_pos(self, target_zoom, viewport_pos=None):
        """Ubah zoom_factor ke target_zoom dengan titik di bawah kursor (viewport_pos) tetap terkunci."""
        if self.base_pixmap.isNull():
            return
        vp = self.scroll_area.viewport()
        vp_w, vp_h = vp.width(), vp.height()
        if viewport_pos is None:
            vx, vy = vp_w / 2.0, vp_h / 2.0
        else:
            vx, vy = float(viewport_pos.x()), float(viewport_pos.y())

        hbar = self.scroll_area.horizontalScrollBar()
        vbar = self.scroll_area.verticalScrollBar()

        old_pix = self.preview_label.pixmap()
        if old_pix is not None and not old_pix.isNull():
            old_w, old_h = float(old_pix.width()), float(old_pix.height())
        else:
            old_w = max(1.0, self.base_pixmap.width() * self.zoom_factor)
            old_h = max(1.0, self.base_pixmap.height() * self.zoom_factor)

        offset_x = max(0.0, (vp_w - old_w) / 2.0)
        offset_y = max(0.0, (vp_h - old_h) / 2.0)
        img_x = hbar.value() + vx - offset_x
        img_y = vbar.value() + vy - offset_y
        fx = max(0.0, min(1.0, img_x / max(1.0, old_w)))
        fy = max(0.0, min(1.0, img_y / max(1.0, old_h)))

        self._fit_mode = False
        self.zoom_factor = max(0.1, min(8.0, float(target_zoom)))
        self.update_preview()

        new_w = self.base_pixmap.width() * self.zoom_factor
        new_h = self.base_pixmap.height() * self.zoom_factor
        new_offset_x = max(0.0, (vp_w - new_w) / 2.0)
        new_offset_y = max(0.0, (vp_h - new_h) / 2.0)
        hbar.setValue(int(round(fx * new_w + new_offset_x - vx)))
        vbar.setValue(int(round(fy * new_h + new_offset_y - vy)))
        self._update_cursor()

    def _smart_double_click_zoom(self, viewport_pos):
        """Double-click di titik mana pun:
        - Jika sedang Fit (atau zoom kecil): zoom in cerdas (2.2x dari Fit / minimal 100%) tepat ke titik yang diklik.
        - Jika sudah di-zoom in: kembali ke Fit-to-Window."""
        fit_z = self._compute_fit_zoom()
        self._fit_zoom = fit_z
        if self._fit_mode or self.zoom_factor <= fit_z * 1.05:
            target = max(1.0, fit_z * 2.25) if fit_z < 0.9 else min(4.0, fit_z * 2.25)
            self._zoom_to_at_pos(target, viewport_pos)
        else:
            self.fit_to_window()

    def adjust_zoom(self, multiplier, viewport_pos=None):
        self._zoom_to_at_pos(self.zoom_factor * multiplier, viewport_pos)

    def fit_to_window(self):
        self._fit_mode = True
        self.update_preview()
        self._update_cursor()

    def reset_actual_size(self):
        self._zoom_to_at_pos(1.0)

    def _update_info_label(self):
        pct = int(round(self.zoom_factor * 100))
        mode_tag = "Fit" if self._fit_mode else f"{pct}%"
        frame_tag = ""
        if self._using_qtmm_video and not self._frame_step_mode:
            frame_tag = " · Video" if self._anim_playing else " · Video · Paused"
        elif len(self.anim_frames) > 1:
            state_tag = "" if self._anim_playing else " · Paused"
            frame_tag = f" · Frame {self._anim_index + 1}/{len(self.anim_frames)}{state_tag}"
        suffix_info = f" ({self.base_pixmap.width()}×{self.base_pixmap.height()} · {mode_tag}{frame_tag})"
        f_calc = self.info_label.font()
        f_calc.setPixelSize(13)
        f_calc.setBold(True)
        fm = QFontMetrics(f_calc)
        # Hitung ruang tersisa langsung dari lebar dialog agar tidak tertinggal 1 frame saat resizeEvent
        avail_w = max(140, self.width() - 365)
        max_name_w = max(48, avail_w - fm.horizontalAdvance(suffix_info) - 16)
        elided_name = fm.elidedText(os.path.basename(self.image_path), Qt.ElideMiddle, max_name_w)
        self.info_label.setText(f"{elided_name}{suffix_info}")

    def _get_scaled_frame(self, frame_idx: int, tw: int, th: int) -> QPixmap:
        if (tw, th) != self._scaled_cache_size:
            self._scaled_frame_cache.clear()
            self._scaled_cache_size = (tw, th)
        if frame_idx in self._scaled_frame_cache:
            return self._scaled_frame_cache[frame_idx]
        transform_mode = Qt.FastTransformation if len(self.anim_frames) > 1 else Qt.SmoothTransformation
        scaled = self.base_pixmap.scaled(tw, th, Qt.KeepAspectRatio, transform_mode)
        if len(self.anim_frames) <= 180:
            self._scaled_frame_cache[frame_idx] = scaled
        return scaled

    def _render_current_frame_preserve_scroll(self):
        """Render frame animasi saat ini tanpa mereset posisi scroll/pan (dengan cache frame ter-scale)."""
        if self.base_pixmap.isNull():
            return
        hbar = self.scroll_area.horizontalScrollBar()
        vbar = self.scroll_area.verticalScrollBar()
        old_h = hbar.value()
        old_v = vbar.value()
        if self._fit_mode:
            self._fit_zoom = self._compute_fit_zoom()
            self.zoom_factor = self._fit_zoom
        tw = max(16, int(round(self.base_pixmap.width() * self.zoom_factor)))
        th = max(16, int(round(self.base_pixmap.height() * self.zoom_factor)))
        scaled = self._get_scaled_frame(self._anim_index, tw, th)
        if self._fit_mode:
            self.preview_label.setMinimumSize(1, 1)
        else:
            self.preview_label.setMinimumSize(scaled.size())
        self.preview_label.setPixmap(scaled)
        if not self._fit_mode:
            hbar.setValue(old_h)
            vbar.setValue(old_v)
        self._update_info_label()

    def update_preview(self):
        if self.base_pixmap.isNull():
            self.preview_label.setText("Failed to load image.")
            return
        if self._fit_mode:
            self._fit_zoom = self._compute_fit_zoom()
            self.zoom_factor = self._fit_zoom
        tw = max(16, int(round(self.base_pixmap.width() * self.zoom_factor)))
        th = max(16, int(round(self.base_pixmap.height() * self.zoom_factor)))
        self._scaled_frame_cache.clear()
        self._scaled_cache_size = (tw, th)
        scaled = self.base_pixmap.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._scaled_frame_cache[self._anim_index] = scaled
        if self._fit_mode:
            self.preview_label.setMinimumSize(1, 1)
        else:
            self.preview_label.setMinimumSize(scaled.size())
        self.preview_label.setPixmap(scaled)
        self.preview_label.resize(scaled.size())
        self._update_info_label()
        self._update_cursor()

    def _map_to_viewport(self, obj, pos):
        vp = self.scroll_area.viewport()
        if obj is vp:
            return pos
        return obj.mapTo(vp, pos)

    def eventFilter(self, obj, event):
        vp = self.scroll_area.viewport()
        if obj in (vp, self.preview_label):
            etype = event.type()
            if etype == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self._pan_active = False
                vp_pos = self._map_to_viewport(obj, event.position().toPoint())
                self._smart_double_click_zoom(vp_pos)
                return True
            if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if self._is_pannable():
                    self._pan_active = True
                    self._pan_moved = False
                    self._pan_start_pos = event.globalPosition().toPoint()
                    self._pan_start_h = self.scroll_area.horizontalScrollBar().value()
                    self._pan_start_v = self.scroll_area.verticalScrollBar().value()
                    self._update_cursor()
                    return True
            elif etype == QEvent.MouseMove and self._pan_active:
                delta = event.globalPosition().toPoint() - self._pan_start_pos
                if abs(delta.x()) > 2 or abs(delta.y()) > 2:
                    self._pan_moved = True
                self.scroll_area.horizontalScrollBar().setValue(self._pan_start_h - delta.x())
                self.scroll_area.verticalScrollBar().setValue(self._pan_start_v - delta.y())
                return True
            elif etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self._pan_active:
                    self._pan_active = False
                    self._update_cursor()
                    return True
            elif etype == QEvent.Wheel:
                delta = event.angleDelta().y()
                vp_pos = self._map_to_viewport(obj, event.position().toPoint())
                if delta > 0:
                    self.adjust_zoom(1.18, vp_pos)
                elif delta < 0:
                    self.adjust_zoom(1 / 1.18, vp_pos)
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.adjust_zoom(1.25)
            return
        if key == Qt.Key_Minus:
            self.adjust_zoom(0.8)
            return
        if key == Qt.Key_0:
            self.fit_to_window()
            return
        if key == Qt.Key_1:
            self.reset_actual_size()
            return
        if key in (Qt.Key_Space, Qt.Key_P) and (len(self.anim_frames) > 1 or self._is_video):
            self.toggle_animation()
            return
        if key == Qt.Key_M and self._is_video:
            self.toggle_audio_mute()
            return
        if key == Qt.Key_BracketLeft and len(self.anim_frames) > 1:
            self.step_frame(-1)
            return
        if key == Qt.Key_BracketRight and len(self.anim_frames) > 1:
            self.step_frame(1)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._anim_timer.stop()
        self._stop_preview_audio()
        if self._video_thread is not None and self._video_thread.isRunning():
            self._video_thread.cancel()
            self._video_thread.wait(1500)
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._fit_mode:
            self.update_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "hint_label"):
            self.hint_label.setVisible(self.width() >= 780)
        if self._fit_mode:
            self.update_preview()
        else:
            self._update_info_label()


class FolderScanThread(QThread):
    """Memindai folder di thread latar. UI tetap responsif berapa pun jumlah filenya."""
    progress_updated = Signal(int)  # jumlah gambar yang sudah ditemukan

    def __init__(self, folder_path, parent=None, include_subfolders=False, excluded_dirs=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.include_subfolders = bool(include_subfolders)
        self.excluded_dirs = excluded_dirs or []
        self.files = []
        self.error = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def run(self):
        try:
            result = scan_image_files(
                self.folder_path,
                should_cancel=self.is_cancelled,
                on_progress=self.progress_updated.emit,
                include_subfolders=self.include_subfolders,
                excluded_dirs=self.excluded_dirs,
            )
            self.files = result or []
        except OSError as e:
            self.error = str(e)
            self.files = []


class VideoDecodeThread(QThread):
    """Men-decode frame video di background thread (menggunakan QImage + cap.grab)
    dan mengirimkan batch frame secara streaming agar UI 0 ms lag."""
    chunk_ready = Signal(str, list)  # (video_path, [(QImage, delay_ms), ...])

    def __init__(self, video_path: str, max_width: int = 720, max_height: int = 500, max_frames: int = 60, chunk_size: int = 8, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.max_width = int(max_width)
        self.max_height = int(max_height)
        self.max_frames = int(max_frames)
        self.chunk_size = int(chunk_size)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def _emit_chunk(self, chunk):
        if not self._cancelled and chunk:
            self.chunk_ready.emit(self.video_path, chunk)

    def run(self):
        decode_video_qimages(
            self.video_path,
            max_width=self.max_width,
            max_height=self.max_height,
            max_frames=self.max_frames,
            should_cancel=self.is_cancelled,
            on_chunk=self._emit_chunk,
            chunk_size=self.chunk_size,
        )


class DuplicateScanThread(QThread):
    """Memindai kemiripan/duplikat gambar & video di thread latar menggunakan 64-bit dHash."""
    progress_updated = Signal(int, int)  # (processed, total)

    def __init__(self, paths, max_distance: int = 6, parent=None):
        super().__init__(parent)
        self.paths = list(paths)
        self.max_distance = int(max_distance)
        self.duplicate_norms = set()
        self.groups = []
        self.hash_map = {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def run(self):
        dup_norms, groups, hmap = find_duplicate_groups(
            self.paths,
            max_distance=self.max_distance,
            should_cancel=self.is_cancelled,
            on_progress=self.progress_updated.emit,
        )
        self.duplicate_norms = dup_norms
        self.groups = groups
        self.hash_map = hmap


class CustomThemeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Custom Theme Settings")
        self.setMinimumSize(420, 440)
        self.resize(450, 480)

        t = resolve_studio_tokens(parent)
        self._tokens = t
        self.setStyleSheet(build_studio_dialog_qss(t))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 18, 20, 18)

        hdr = QLabel("Custom Theme Palette")
        hdr.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {t['text']};")
        main_layout.addWidget(hdr)

        sub = QLabel("Customize surface, text, menu, and preview frame accent colors.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12px; color: {t['text_muted']};")
        main_layout.addWidget(sub)

        card = QFrame()
        card.setObjectName("studioCard")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(8, 8, 8, 8)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(8, 6, 8, 6)
        scroll_area.setWidget(scroll_content)
        card_lay.addWidget(scroll_area)
        main_layout.addWidget(card, stretch=1)

        settings = load_settings()
        self.default_colors = {
            "bg_color": "#0e1015",
            "text_color": "#f0f2f5",
            "btn_bg": "#181b23",
            "btn_hover": "#212633",
            "label_bg": "#13161d",
            "menu_bg": "#12141b",
            "menu_text": "#f0f2f5",
            "main_border_color": "#3b82f6",
            "next_border_color": "#10b981",
            "main_shadow": "0 0 10px rgba(59, 130, 246, 0.55)",
            "next_shadow": "0 0 8px rgba(16, 185, 129, 0.45)"
        }
        custom_theme = settings.get("custom_theme", self.default_colors)

        self.bg_color = custom_theme.get("bg_color", self.default_colors["bg_color"])
        self.text_color = custom_theme.get("text_color", self.default_colors["text_color"])
        self.btn_bg = custom_theme.get("btn_bg", self.default_colors["btn_bg"])
        self.btn_hover = custom_theme.get("btn_hover", self.default_colors["btn_hover"])
        self.label_bg = custom_theme.get("label_bg", self.default_colors["label_bg"])
        self.menu_bg = custom_theme.get("menu_bg", self.default_colors["menu_bg"])
        self.menu_text = custom_theme.get("menu_text", self.default_colors["menu_text"])
        self.main_border_color = custom_theme.get("main_border_color", self.default_colors["main_border_color"])
        self.next_border_color = custom_theme.get("next_border_color", self.default_colors["next_border_color"])
        self.main_shadow = custom_theme.get("main_shadow", self.default_colors["main_shadow"])
        self.next_shadow = custom_theme.get("next_shadow", self.default_colors["next_shadow"])

        color_fields = [
            ("Background Color", "bg", self.bg_color),
            ("Text Color", "text", self.text_color),
            ("Button Background", "btn_bg", self.btn_bg),
            ("Button Hover", "btn_hover", self.btn_hover),
            ("Stage / Card Surface", "label_bg", self.label_bg),
            ("Menu Bar Surface", "menu_bg", self.menu_bg),
            ("Menu Text Color", "menu_text", self.menu_text),
            ("Primary Frame Accent", "main_border", self.main_border_color),
            ("Up Next Frame Accent", "next_border", self.next_border_color),
        ]

        for label_text, target, current_color in color_fields:
            self.create_color_picker_button(scroll_layout, label_text, target, current_color)
        scroll_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setObjectName("dangerBtn")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setIcon(make_vector_icon("reset", "#fca5a5" if t["is_dark"] else "#dc2626", 14))
        self.reset_btn.setIconSize(QSize(14, 14))
        self.reset_btn.clicked.connect(self.reset_to_defaults)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Theme")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setIcon(make_vector_icon("check", "#ffffff", 14))
        self.save_btn.setIconSize(QSize(14, 14))
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save_and_close)

        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.save_btn)
        main_layout.addLayout(btn_layout)

    def _style_swatch_button(self, btn: QPushButton, hex_color: str):
        t = self._tokens
        qcol = QColor(hex_color)
        lum = qcol.red() * 0.299 + qcol.green() * 0.587 + qcol.blue() * 0.114
        fg = "#111318" if lum > 150 else "#f8fafc"
        btn.setText(hex_color.upper())
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_color};
                color: {fg};
                border: 1px solid {t["border_strong"]};
                border-radius: 7px;
                font-family: Consolas, monospace;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                border: 2px solid {t["accent"]};
            }}
        """)

    def create_color_picker_button(self, layout, label_text, target, current_color):
        container = QHBoxLayout()
        container.setSpacing(10)

        label = QLabel(label_text)
        label.setStyleSheet("font-weight: 600; font-size: 12px;")
        container.addWidget(label, 1)

        btn = QPushButton()
        btn.setObjectName(f"{target}_btn")
        btn.setCursor(Qt.PointingHandCursor)
        setattr(self, f"{target}_btn", btn)
        btn.setFixedSize(112, 30)
        self._style_swatch_button(btn, current_color)
        btn.clicked.connect(lambda _, t=target: self.pick_color(t))
        container.addWidget(btn)
        layout.addLayout(container)

    def pick_color(self, target):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            hex_color = color.name()
            btn = getattr(self, f"{target}_btn")
            self._style_swatch_button(btn, hex_color)

            if target == 'bg':
                self.bg_color = hex_color
            elif target == 'text':
                self.text_color = hex_color
            elif target == 'btn_bg':
                self.btn_bg = hex_color
            elif target == 'btn_hover':
                self.btn_hover = hex_color
            elif target == 'label_bg':
                self.label_bg = hex_color
            elif target == 'menu_bg':
                self.menu_bg = hex_color
            elif target == 'menu_text':
                self.menu_text = hex_color
            elif target == 'main_border':
                self.main_border_color = hex_color
                self.main_shadow = f"0 0 10px {hex_color}80"
            elif target == 'next_border':
                self.next_border_color = hex_color
                self.next_shadow = f"0 0 8px {hex_color}80"

    def reset_to_defaults(self):
        self.bg_color = self.default_colors["bg_color"]
        self.text_color = self.default_colors["text_color"]
        self.btn_bg = self.default_colors["btn_bg"]
        self.btn_hover = self.default_colors["btn_hover"]
        self.label_bg = self.default_colors["label_bg"]
        self.menu_bg = self.default_colors["menu_bg"]
        self.menu_text = self.default_colors["menu_text"]
        self.main_border_color = self.default_colors["main_border_color"]
        self.next_border_color = self.default_colors["next_border_color"]
        self.main_shadow = self.default_colors["main_shadow"]
        self.next_shadow = self.default_colors["next_shadow"]

        target_to_key = {
            "bg": "bg_color",
            "text": "text_color",
            "btn_bg": "btn_bg",
            "btn_hover": "btn_hover",
            "label_bg": "label_bg",
            "menu_bg": "menu_bg",
            "menu_text": "menu_text",
            "main_border": "main_border_color",
            "next_border": "next_border_color"
        }

        for target in target_to_key:
            btn = getattr(self, f"{target}_btn")
            color = self.default_colors[target_to_key[target]]
            self._style_swatch_button(btn, color)

    def save_and_close(self):
        settings = load_settings()
        settings["custom_theme"] = {
            "bg_color": self.bg_color,
            "text_color": self.text_color,
            "btn_bg": self.btn_bg,
            "btn_hover": self.btn_hover,
            "label_bg": self.label_bg,
            "menu_bg": self.menu_bg,
            "menu_text": self.menu_text,
            "main_border_color": self.main_border_color,
            "next_border_color": self.next_border_color,
            "main_shadow": self.main_shadow,
            "next_shadow": self.next_shadow
        }
        save_settings(settings)
        self.accept()

class FolderSettingsDialog(QDialog):
    DEFAULT_NAMES = [f"Folder {ch}" for ch in ALL_SLOT_LETTERS]
    DEFAULT_PATHS = [f"output/{ch}" for ch in ALL_SLOT_LETTERS]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Destination Folder Settings")
        self.setMinimumWidth(640)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 18, 22, 18)
        self.layout.setSpacing(12)
        self.inputs = []
        self.row_widgets = []

        t = resolve_studio_tokens(parent)
        self.setStyleSheet(build_studio_dialog_qss(t))

        settings = load_settings()
        saved_names = list(settings.get("folder_names", self.DEFAULT_NAMES[:DEFAULT_FOLDER_SLOTS]))
        saved_paths = list(settings.get("folder_paths", self.DEFAULT_PATHS[:DEFAULT_FOLDER_SLOTS]))
        initial_count = clamp_folder_slots(
            settings.get("folder_slot_count", len(saved_names) or DEFAULT_FOLDER_SLOTS)
        )

        top_card = QFrame()
        top_card.setObjectName("studioCard")
        slot_bar = QHBoxLayout(top_card)
        slot_bar.setContentsMargins(14, 10, 14, 10)
        slot_bar.setSpacing(12)
        slot_lbl = QLabel("Active Folder Slots (Keys 1–9):")
        slot_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(MIN_FOLDER_SLOTS, MAX_FOLDER_SLOTS)
        self.slot_spin.setValue(initial_count)
        self.slot_spin.setFixedWidth(76)
        self.slot_spin.valueChanged.connect(self._update_visible_rows)
        slot_hint = QLabel("Configure 3 to 9 custom sorting destinations")
        slot_hint.setStyleSheet(f"font-size: 12px; color: {t['text_muted']};")
        slot_bar.addWidget(slot_lbl)
        slot_bar.addWidget(self.slot_spin)
        slot_bar.addSpacing(6)
        slot_bar.addWidget(slot_hint)
        slot_bar.addStretch()
        self.layout.addWidget(top_card)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 0, 4, 0)
        header_layout.setSpacing(10)
        lbl_key = QLabel("KEY")
        lbl_key.setFixedWidth(44)
        lbl_key.setStyleSheet(f"font-size: 11px; font-weight: 700; letter-spacing: 0.8px; color: {t['text_muted']};")
        lbl_name = QLabel("FOLDER LABEL")
        lbl_name.setFixedWidth(150)
        lbl_name.setStyleSheet(f"font-size: 11px; font-weight: 700; letter-spacing: 0.8px; color: {t['text_muted']};")
        lbl_path = QLabel("DESTINATION PATH")
        lbl_path.setStyleSheet(f"font-size: 11px; font-weight: 700; letter-spacing: 0.8px; color: {t['text_muted']};")
        header_layout.addWidget(lbl_key)
        header_layout.addWidget(lbl_name)
        header_layout.addWidget(lbl_path, stretch=1)
        self.layout.addLayout(header_layout)

        for i in range(MAX_FOLDER_SLOTS):
            row_w = QWidget()
            h_layout = QHBoxLayout(row_w)
            h_layout.setContentsMargins(0, 1, 0, 1)
            h_layout.setSpacing(10)

            accent = SLOT_ACCENTS[i % len(SLOT_ACCENTS)]
            badge_bg = _hex_rgba(accent, 38 if t["is_dark"] else 26)
            badge_border = _hex_rgba(accent, 130 if t["is_dark"] else 110)
            key_badge = QLabel(f"[{i + 1}]")
            key_badge.setFixedSize(44, 30)
            key_badge.setAlignment(Qt.AlignCenter)
            key_badge.setStyleSheet(
                f"font-family: Consolas, monospace; font-size: 12px; font-weight: 700; "
                f"color: {t['text']}; background-color: {badge_bg}; "
                f"border: 1px solid {badge_border}; border-radius: 7px;"
            )

            name_val = saved_names[i] if i < len(saved_names) else self.DEFAULT_NAMES[i]
            path_val = saved_paths[i] if i < len(saved_paths) else self.DEFAULT_PATHS[i]
            name_input = QLineEdit(name_val)
            name_input.setFixedWidth(150)
            path_input = QLineEdit(path_val)
            btn_browse = QPushButton("Browse")
            btn_browse.setCursor(Qt.PointingHandCursor)
            btn_browse.setIcon(make_vector_icon("folder", accent, 14))
            btn_browse.setIconSize(QSize(14, 14))
            btn_browse.clicked.connect(lambda _, idx=i: self.select_folder(idx))
            h_layout.addWidget(key_badge)
            h_layout.addWidget(name_input)
            h_layout.addWidget(path_input, stretch=1)
            h_layout.addWidget(btn_browse)
            self.layout.addWidget(row_w)
            self.row_widgets.append(row_w)
            self.inputs.append((name_input, path_input))

        self._update_visible_rows(initial_count)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setMinimumWidth(96)
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setIcon(make_vector_icon("check", "#ffffff", 14))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.setMinimumWidth(124)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        self.layout.addLayout(btn_layout)

    def _update_visible_rows(self, count):
        count = clamp_folder_slots(count)
        for i, row_w in enumerate(self.row_widgets):
            row_w.setVisible(i < count)
        self.adjustSize()

    def select_folder(self, index):
        folder = QFileDialog.getExistingDirectory(self, f"Select Folder {index + 1}")
        if folder:
            self.inputs[index][1].setText(folder)

    def save_and_close(self):
        count = clamp_folder_slots(self.slot_spin.value())
        self.folder_names = [
            self.inputs[i][0].text().strip() or self.DEFAULT_NAMES[i]
            for i in range(count)
        ]
        self.folder_paths = [
            self.inputs[i][1].text().strip() or self.DEFAULT_PATHS[i]
            for i in range(count)
        ]
        settings = load_settings()
        settings["folder_slot_count"] = count
        settings["folder_names"] = self.folder_names
        settings["folder_paths"] = self.folder_paths
        save_settings(settings)
        self.accept()

    def get_folders(self):
        return self.folder_names, self.folder_paths

class RapidMoveSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rapid Move Speed")
        self.parent = parent
        self.setMinimumSize(440, 310)
        self.resize(460, 325)
        self.setModal(True)

        self._tokens = resolve_studio_tokens(parent)
        t = self._tokens
        self.setStyleSheet(build_studio_dialog_qss(t))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)

        title = QLabel("Rapid Move Interval")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {t['text']};")
        layout.addWidget(title)

        desc = QLabel(
            "Adjust how fast media files are moved while holding Folder 1–9 "
            "(mouse button or keyboard key 1–9). Lower interval = faster continuous sorting."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 12px; color: {t['text_muted']};")
        layout.addWidget(desc)

        status_card = QFrame()
        status_card.setObjectName("studioCard")
        card_lay = QVBoxLayout(status_card)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(12)

        self.current_label = QLabel()
        self.current_label.setAlignment(Qt.AlignCenter)
        card_lay.addWidget(self.current_label)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(14)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 1000)
        self.slider.setSingleStep(50)
        self.slider.setPageStep(100)
        self.slider.setCursor(Qt.PointingHandCursor)
        control_layout.addWidget(self.slider, stretch=1)

        self.spinbox = QSpinBox()
        self.spinbox.setRange(50, 1000)
        self.spinbox.setSingleStep(50)
        self.spinbox.setSuffix(" ms")
        self.spinbox.setFixedWidth(108)
        self.spinbox.setFixedHeight(34)
        control_layout.addWidget(self.spinbox)

        card_lay.addLayout(control_layout)

        hint_row = QHBoxLayout()
        lbl_fast = QLabel("50 ms (Fastest)")
        lbl_fast.setStyleSheet(f"font-size: 11px; color: {t['text_muted']};")
        lbl_slow = QLabel("1000 ms (Relaxed)")
        lbl_slow.setStyleSheet(f"font-size: 11px; color: {t['text_muted']};")
        hint_row.addWidget(lbl_fast)
        hint_row.addStretch()
        hint_row.addWidget(lbl_slow)
        card_lay.addLayout(hint_row)

        layout.addWidget(status_card)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setMinimumWidth(96)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Interval")
        save_btn.setObjectName("save_btn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setIcon(make_vector_icon("check", "#ffffff", 14))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.setMinimumWidth(120)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_and_close)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        initial_value = clamp_rapid_interval(parent.rapid_move_interval if parent else RAPID_MOVE_DEFAULT_MS)
        self.slider.setValue(initial_value)
        self.spinbox.setValue(initial_value)
        self.update_current_label(initial_value)

        self.slider.valueChanged.connect(self.spinbox.setValue)
        self.spinbox.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.update_current_label)
        self.spinbox.valueChanged.connect(self.update_current_label)

    def update_current_label(self, value):
        t = self._tokens
        if value <= 100:
            speed = "Ultra-Fast Burst"
            badge_col = "#f43f5e"
        elif value <= 200:
            speed = "High-Speed Studio (Recommended)"
            badge_col = t["accent"]
        elif value <= 400:
            speed = "Balanced Pace"
            badge_col = "#10b981"
        elif value <= 600:
            speed = "Moderate Cadence"
            badge_col = "#f59e0b"
        else:
            speed = "Relaxed Inspection"
            badge_col = t["text_muted"]

        fps_equiv = 1000.0 / max(50, int(value))
        self.current_label.setText(
            f"<span style='font-size: 20px; font-weight: 700; color: {t['text']};'>{value} ms</span> "
            f"<span style='font-size: 12px; color: {t['text_muted']};'>(~{fps_equiv:.1f} files/sec)</span><br>"
            f"<span style='font-size: 12px; font-weight: 600; color: {badge_col};'>{speed}</span>"
        )

    def save_and_close(self):
        new_interval = clamp_rapid_interval(self.spinbox.value())
        if self.parent:
            self.parent.rapid_move_interval = new_interval
            settings = load_settings()
            settings["rapid_move_interval"] = new_interval
            save_settings(settings)
            self.parent.show_notification(f"Rapid move interval set to {new_interval} ms")
        self.accept()

class ImageSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ImageSorter")
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRectF(0, 0, 1280, 720).toRect()
        init_w = min(960, max(780, int(avail.width() * 0.72)))
        init_h = min(680, max(580, int(avail.height() * 0.84)))
        self.setMinimumSize(min(780, max(680, avail.width() - 32)), min(580, max(500, avail.height() - 48)))
        self.resize(init_w, init_h)
        self.setAcceptDrops(True)
        self.image_files = []
        self.current_folder_path = ""
        self.current_index = 0
        self.nav_history = deque(maxlen=500)
        self.folder_names = []
        self.folder_paths = []
        self.log_buffer = []
        self.source_info = ""
        self.recent_folders = []
        self.theme_mode = "system"
        self.filtered_files = []
        self.history, self.history_cache = load_history()  # Updated to load history_cache
        # history.json disimpan dengan jeda singkat agar rapid move ribuan file tidak
        # menulis ulang seluruh file di setiap pemindahan.
        self._history_dirty = False
        self._history_save_timer = QTimer(self)
        self._history_save_timer.setSingleShot(True)
        self._history_save_timer.setInterval(400)
        self._history_save_timer.timeout.connect(self.flush_history)
        self.defer_ui_updates = False
        self.last_filter = "All Files"
        self.hide_moved = False
        self.current_movie = None
        self._movie_buffer = None
        self._movie_bytes = None
        self._main_anim_frames = []
        self._main_anim_index = 0
        self._main_anim_timer = QTimer(self)
        self._main_anim_timer.setSingleShot(True)
        self._main_anim_timer.timeout.connect(self._advance_main_anim_frame)
        self._video_decode_path = None
        self._video_decode_timer = QTimer(self)
        self._video_decode_timer.setSingleShot(True)
        self._video_decode_timer.setInterval(75)
        self._video_decode_timer.timeout.connect(self._start_deferred_video_anim)
        self._video_thread = None
        self._video_threads = set()
        self._raw_video_cache_frames = []
        # Rapid move variables
        self.is_rapid_moving = False
        self.rapid_folder_index = None
        self.rapid_source = None  # "mouse" atau "key"
        self.rapid_timer = QTimer(self)
        self.rapid_timer.timeout.connect(self.rapid_move)
        self.folder_buttons = []  # Untuk menyimpan referensi tombol folder
        settings = load_settings()
        self.rapid_move_interval = clamp_rapid_interval(settings.get("rapid_move_interval", RAPID_MOVE_DEFAULT_MS))
        self.include_subfolders = bool(settings.get("include_subfolders", False))
        self.video_muted = bool(settings.get("video_muted", False))
        try:
            self.video_volume = max(0.0, min(1.0, float(settings.get("video_volume", 0.8))))
        except (TypeError, ValueError):
            self.video_volume = 0.8
        self._main_audio_player = None
        self._main_audio_output = None
        self._main_video_sink = None
        self._main_audio_buffer = None
        self._main_audio_bytes = None
        self._main_video_target_size = QSize(720, 500)
        self._main_video_using_qtmm = False
        self._qtmm_first_frame_shown = False
        self._main_paused = False
        self._seeking_main_video = False
        self._video_duration_ms = 0
        self._video_controls = []
        self._play_pause_btn = None
        self._mute_btn = None
        self._video_seek_slider = None
        self._hud_cur_time = None
        self._hud_tot_time = None
        self._current_main_pixmap = None
        self._current_main_is_video = False
        self._current_next_pixmap = None
        self._current_file_meta = None
        self._last_folder_wrap_cols = None
        self._hud_is_video = False
        self.folder_slot_count = clamp_folder_slots(settings.get("folder_slot_count", DEFAULT_FOLDER_SLOTS))
        self.pixmap_cache = PixmapLRUCache(max_entries=36)
        self._prefetch_timer = QTimer(self)
        self._prefetch_timer.setSingleShot(True)
        self._prefetch_timer.setInterval(12)
        self._prefetch_timer.timeout.connect(self._prefetch_neighbor_images)
        self.duplicate_norms = set()
        self.duplicate_groups = []
        self.duplicate_group_lookup = {}
        self.dup_thread = None
        self.scan_thread = None
        self._scan_threads = set()  # semua thread pemindai yang masih hidup
        self.update_thread = None

        # Rest of __init__ remains unchanged
        self.loading_widget = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.loading_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.loading_label = QLabel("Loading folder...", self.loading_widget)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #f0f2f5;
            background-color: rgba(18, 20, 27, 238);
            border: 1px solid #363c4d;
            border-radius: 12px;
            padding: 18px 22px;
        """)
        layout = QVBoxLayout(self.loading_widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.loading_label)
        self.loading_widget.setLayout(layout)
        self.loading_widget.hide()
        self.loading_widget.setFixedSize(310, 96)
        self.start_update_check()
        self.init_ui()
        self.check_first_run()
        self.load_custom_folders()
        self.load_recent_folders()
        self.apply_theme()
        self.show_current_image(self.filtered_files)
        # Tangkap tombol 1-5 di level aplikasi agar rapid move keyboard tetap jalan
        # walaupun fokus sedang berada di tombol/combobox di jendela utama.
        QApplication.instance().installEventFilter(self)
        self.init_hot_reload()
        self.restore_hot_reload_state()

    def start_update_check(self, manual=False):
        """Mulai pengecekan pembaruan di thread terpisah (tidak memblokir UI)."""
        if not manual and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        if self.update_thread is not None and self.update_thread.isRunning():
            if manual:
                self.show_notification("Update check is already running...")
            return
        thread = UpdateCheckThread(self, manual=manual)
        thread.update_checked.connect(lambda v, n, u, t=thread: self.show_update_dialog(v, n, u, t.manual))
        thread.error_occurred.connect(lambda e, t=thread: self.show_update_error(e, t.manual))
        thread.finished.connect(lambda t=thread: self._on_update_thread_finished(t))
        self.update_thread = thread
        thread.start()

    def _on_update_thread_finished(self, thread):
        # Lepaskan referensi Python SEBELUM objek C++ dihapus agar tidak ada pointer basi.
        if self.update_thread is thread:
            self.update_thread = None
        thread.deleteLater()

    def show_update_dialog(self, latest_version, release_notes, download_url, manual=True):
        """Startup: dialog hanya muncul bila ada versi baru. Manual: selalu tampil."""
        current_version = AboutDialog.VERSION
        if not manual:
            checker = UpdateDialog.is_newer_version
            if not latest_version or not checker(None, current_version, latest_version):
                print(f"[DEBUG] Up to date ({current_version}), latest={latest_version}")
                return
        dialog = UpdateDialog(self, current_version, latest_version, release_notes, download_url)
        dialog.exec()

    def show_update_error(self, error_message, manual=True):
        """Startup: gagal cek update cukup dicatat (tanpa popup). Manual: tampilkan pesan."""
        print(f"[DEBUG] Update check failed: {error_message}")
        if not manual:
            return
        dialog = UpdateDialog(self, AboutDialog.VERSION, None,
                              "Failed to check for updates. Please check your internet connection.")
        dialog.exec()

    def schedule_history_save(self):
        self._history_dirty = True
        self._history_save_timer.start()

    def flush_history(self):
        """Tulis history.json sekarang juga jika ada perubahan yang belum tersimpan."""
        self._history_save_timer.stop()
        if self._history_dirty:
            save_history(self.history)
            self._history_dirty = False

    def stop_current_movie(self):
        """Hentikan animasi QMovie / QtMultimedia / timer frame aktif dan batalkan thread video aktif."""
        if getattr(self, "_video_decode_timer", None) is not None:
            self._video_decode_timer.stop()
        self._video_decode_path = None
        vthread = getattr(self, "_video_thread", None)
        if vthread is not None:
            vthread.cancel()
            self._video_thread = None
        for vt in list(getattr(self, "_video_threads", ())):
            vt.cancel()
        for vt in list(getattr(self, "_video_threads", ())):
            if vt.isRunning():
                vt.wait(250)
        self._raw_video_cache_frames = []
        self._main_paused = False
        self._main_video_using_qtmm = False
        self._qtmm_first_frame_shown = False
        self._stop_main_audio()
        self._clear_video_controls()
        if getattr(self, "_main_anim_timer", None) is not None:
            self._main_anim_timer.stop()
        self._main_anim_frames = []
        self._main_anim_index = 0
        if self.current_movie is not None:
            self.current_movie.stop()
            if hasattr(self, "image_label"):
                self.image_label.setMovie(None)
            self.current_movie.deleteLater()
            self.current_movie = None
        if self._movie_buffer is not None:
            self._movie_buffer.close()
            self._movie_buffer = None
        self._movie_bytes = None

    def _advance_main_anim_frame(self):
        """Putar frame berikutnya untuk APNG/AVIF atau fallback video (zero file lock)."""
        if not self._main_anim_frames or not hasattr(self, "image_label") or self._main_paused or self._main_video_using_qtmm:
            return
        self._main_anim_index = (self._main_anim_index + 1) % len(self._main_anim_frames)
        pix, delay = self._main_anim_frames[self._main_anim_index]
        tsize = getattr(self, "_main_video_target_size", None)
        if tsize is not None and not tsize.isEmpty() and pix.size() != tsize:
            pix = pix.scaled(tsize, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.image_label.setPixmap(pix)
        self._main_anim_timer.start(max(20, int(delay)))

    def _begin_main_anim(self):
        """Tampilkan frame pertama lalu mulai putar (atau tetap diam jika sedang di-pause)."""
        if len(self._main_anim_frames) <= 1 or self._main_video_using_qtmm:
            return
        self._main_anim_index = 0
        self.image_label.setPixmap(self._main_anim_frames[0][0])
        if self._main_paused:
            return
        self._main_anim_timer.start(max(20, int(self._main_anim_frames[0][1])))

    # ---------------- Pemutar Video + Suara Utama (QMediaPlayer + QVideoSink dari memori, tanpa kunci file) ----------------
    def _start_main_video_player(self, video_path: str):
        self._stop_main_audio()
        try:
            session = _create_qtmm_video_session(
                self,
                video_path,
                muted=self.video_muted,
                volume=self.video_volume,
                on_frame=self._on_main_video_frame,
                on_error=self._on_main_video_error,
            )
            if session is None:
                self._start_main_video_fallback(video_path)
                return
            (
                self._main_audio_player,
                self._main_audio_output,
                self._main_video_sink,
                self._main_audio_buffer,
                self._main_audio_bytes,
            ) = session
            self._main_video_using_qtmm = True
            self._qtmm_first_frame_shown = False
            self._main_audio_player.positionChanged.connect(self._on_main_player_position)
            self._main_audio_player.durationChanged.connect(self._on_main_player_duration)
            if self._main_paused:
                self._main_audio_player.pause()
            else:
                self._main_audio_player.play()
        except Exception as e:
            print(f"[DEBUG] Main QtMultimedia init warning: {e}")
            self._stop_main_audio()
            self._start_main_video_fallback(video_path)

    def _on_main_player_position(self, pos_ms: int):
        if getattr(self, "_seeking_main_video", False):
            return
        slider = getattr(self, "_video_seek_slider", None)
        if slider is not None:
            slider.setValue(int(pos_ms))
        cur_lbl = getattr(self, "_hud_cur_time", None)
        if cur_lbl is not None:
            cur_lbl.setText(format_duration(pos_ms / 1000.0))

    def _on_main_player_duration(self, dur_ms: int):
        if dur_ms > 0:
            self._video_duration_ms = int(dur_ms)
            slider = getattr(self, "_video_seek_slider", None)
            if slider is not None:
                slider.setRange(0, int(dur_ms))
            tot_lbl = getattr(self, "_hud_tot_time", None)
            if tot_lbl is not None:
                tot_lbl.setText(format_duration(dur_ms / 1000.0))

    def _on_main_seek_released(self):
        self._seeking_main_video = False
        slider = getattr(self, "_video_seek_slider", None)
        if self._main_audio_player is not None and slider is not None:
            self._main_audio_player.setPosition(int(slider.value()))

    def _on_main_seek_clicked(self, pos_ms: int):
        cur_lbl = getattr(self, "_hud_cur_time", None)
        if cur_lbl is not None:
            cur_lbl.setText(format_duration(pos_ms / 1000.0))
        if self._main_audio_player is not None:
            self._main_audio_player.setPosition(int(pos_ms))

    def _on_main_video_error(self, error, error_string=""):
        vpath = getattr(self, "_video_decode_path", None)
        print(f"[DEBUG] Main QtMultimedia error ({error}): {error_string}")
        self._stop_main_audio()
        if vpath and not self.is_rapid_moving and not self.defer_ui_updates and os.path.exists(vpath):
            self._start_main_video_fallback(vpath)

    def _on_main_video_frame(self, frame):
        if not getattr(self, "_main_video_using_qtmm", False) or self.is_rapid_moving or self.defer_ui_updates:
            return
        if self._main_paused and self._qtmm_first_frame_shown:
            return
        if not frame.isValid() or not hasattr(self, "image_label"):
            return
        qimg = frame.toImage()
        if qimg.isNull():
            return
        tsize = getattr(self, "_main_video_target_size", None)
        if tsize is not None and not tsize.isEmpty():
            mode = Qt.SmoothTransformation if qimg.width() * qimg.height() <= 1920 * 1080 else Qt.FastTransformation
            qimg = qimg.scaled(tsize, Qt.KeepAspectRatio, mode)
        self.image_label.setPixmap(QPixmap.fromImage(qimg))
        self._qtmm_first_frame_shown = True

    def _start_main_video_fallback(self, vpath: str):
        """Fallback OpenCV thread apabila QtMultimedia tidak tersedia / format >120 MB."""
        if self.pixmap_cache.has_animation_frames(vpath, 720, 500, max_frames=60):
            raw_frames = self.pixmap_cache.get_animation_frames(vpath, 720, 500, max_frames=60)
            if len(raw_frames) > 1:
                self._main_anim_frames = [
                    (resize_image(fpix), fdelay) for fpix, fdelay in raw_frames if not fpix.isNull()
                ]
                self._begin_main_anim()
            return
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            qimgs = decode_video_qimages(vpath, 720, 500, max_frames=60)
            self._raw_video_cache_frames = []
            self._on_main_video_chunk(vpath, qimgs)
            self._on_main_video_decode_finished(vpath)
            return
        vt = VideoDecodeThread(vpath, max_width=720, max_height=500, max_frames=60, chunk_size=8, parent=self)
        self._raw_video_cache_frames = []
        self._video_threads.add(vt)
        self._video_thread = vt
        vt.chunk_ready.connect(self._on_main_video_chunk)
        vt.finished.connect(lambda t=vt: self._cleanup_video_thread(t))
        vt.start()

    def _stop_main_audio(self):
        self._main_video_using_qtmm = False
        self._qtmm_first_frame_shown = False
        _dispose_qtmm_video_session(
            getattr(self, "_main_audio_player", None),
            getattr(self, "_main_audio_output", None),
            getattr(self, "_main_video_sink", None),
            getattr(self, "_main_audio_buffer", None),
        )
        self._main_audio_player = None
        self._main_audio_output = None
        self._main_video_sink = None
        self._main_audio_buffer = None
        self._main_audio_bytes = None

    # ---------------- HUD Kontrol Media + Seekbar Modern di atas pratinjau ----------------
    def _clear_video_controls(self):
        for w in getattr(self, "_video_controls", []):
            try:
                w.hide()
                w.deleteLater()
            except RuntimeError:
                pass
        self._video_controls = []
        self._play_pause_btn = None
        self._mute_btn = None
        self._video_seek_slider = None
        self._hud_cur_time = None
        self._hud_tot_time = None
        self._hud_is_video = False
        self._seeking_main_video = False

    def _build_video_controls(self, target_size, is_video: bool, duration_s: float = 0.0):
        """Bangun kapsul media frosted-glass terpadu: Seekbar + Timecode (video), Play/Pause (P), & Sound/Muted (M)."""
        self._clear_video_controls()
        w_lbl = max(120, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))

        hud = QFrame(self.image_label)
        hud.setObjectName("mainMediaHud")
        hud.setStyleSheet("""
            QFrame#mainMediaHud {
                background-color: rgba(14, 16, 22, 218);
                border: 1px solid rgba(255, 255, 255, 36);
                border-radius: 12px;
            }
            QLabel {
                color: #e6e8ee;
                background: transparent;
                border: none;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 20);
                color: #f0f2f5;
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
                padding: 0px 8px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 42);
                border-color: rgba(255, 255, 255, 68);
            }
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 45);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
        """)

        self._play_pause_btn = QPushButton("Pause")
        self._play_pause_btn.setCursor(Qt.PointingHandCursor)
        self._play_pause_btn.setFocusPolicy(Qt.NoFocus)
        self._play_pause_btn.setToolTip("Play / Pause (P)")
        self._play_pause_btn.clicked.connect(self.toggle_main_playback)

        if is_video:
            hud_w = min(360, max(84, w_lbl - 12))
            self._hud_compact_labels = hud_w < 190
            use_two_rows = hud_w >= 176 and h_lbl >= 120
            hud_h = 54 if use_two_rows else 32
            x = max(4, (w_lbl - hud_w) // 2)
            y = max(4, h_lbl - hud_h - 8)
            hud.setGeometry(x, y, hud_w, hud_h)

            outer = QVBoxLayout(hud)
            outer.setContentsMargins(8, 4 if use_two_rows else 3, 8, 4 if use_two_rows else 3)
            outer.setSpacing(3)

            dur_ms = int(round(duration_s * 1000)) if duration_s > 0 else self._video_duration_ms
            if use_two_rows:
                seek_row = QHBoxLayout()
                seek_row.setContentsMargins(0, 0, 0, 0)
                seek_row.setSpacing(5)
                self._hud_cur_time = QLabel("0:00")
                self._hud_cur_time.setFixedWidth(28)
                self._video_seek_slider = _ClickSeekSlider(Qt.Horizontal)
                self._video_seek_slider.setRange(0, max(100, dur_ms))
                self._video_seek_slider.setFocusPolicy(Qt.NoFocus)
                self._video_seek_slider.sliderPressed.connect(lambda: setattr(self, "_seeking_main_video", True))
                self._video_seek_slider.sliderMoved.connect(
                    lambda v: self._hud_cur_time.setText(format_duration(v / 1000.0)) if self._hud_cur_time else None
                )
                self._video_seek_slider.sliderReleased.connect(self._on_main_seek_released)
                self._video_seek_slider.seek_clicked.connect(self._on_main_seek_clicked)
                self._hud_tot_time = QLabel(format_duration(dur_ms / 1000.0) if dur_ms > 0 else "0:00")
                self._hud_tot_time.setFixedWidth(28)
                self._hud_tot_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                seek_row.addWidget(self._hud_cur_time)
                seek_row.addWidget(self._video_seek_slider, stretch=1)
                seek_row.addWidget(self._hud_tot_time)
                outer.addLayout(seek_row)

            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.setSpacing(6)
            btn_row.addStretch()
            self._play_pause_btn.setFixedHeight(22)
            btn_row.addWidget(self._play_pause_btn)

            self._mute_btn = QPushButton("Sound")
            self._mute_btn.setCursor(Qt.PointingHandCursor)
            self._mute_btn.setFocusPolicy(Qt.NoFocus)
            self._mute_btn.setToolTip("Mute / Unmute (M)")
            self._mute_btn.clicked.connect(self.toggle_main_mute)
            self._mute_btn.setFixedHeight(22)
            btn_row.addWidget(self._mute_btn)
            btn_row.addStretch()
            outer.addLayout(btn_row)
        else:
            self._hud_compact_labels = w_lbl < 140
            hud_w = min(112, max(60, w_lbl - 12))
            hud_h = 32
            x = max(4, (w_lbl - hud_w) // 2)
            y = max(4, h_lbl - hud_h - 8)
            hud.setGeometry(x, y, hud_w, hud_h)
            lay = QHBoxLayout(hud)
            lay.setContentsMargins(6, 4, 6, 4)
            self._play_pause_btn.setFixedHeight(22)
            lay.addWidget(self._play_pause_btn)

        hud.show()
        hud.raise_()
        self._hud_is_video = bool(is_video)
        self._video_controls.append(hud)
        self._refresh_video_controls()

    def _reposition_video_hud(self, target_size):
        """Sesuaikan posisi & lebar kapsul kontrol video/GIF secara real-time saat ukuran jendela berubah."""
        if not getattr(self, "_video_controls", None):
            return
        w_lbl = max(90, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))
        hud = self._video_controls[0]
        if self._hud_is_video:
            hud_w = min(360, max(84, w_lbl - 12))
            self._hud_compact_labels = hud_w < 190
            if self._video_seek_slider is not None:
                show_seek = hud_w >= 176
                self._video_seek_slider.setVisible(show_seek)
                if self._hud_cur_time is not None:
                    self._hud_cur_time.setVisible(show_seek)
                if self._hud_tot_time is not None:
                    self._hud_tot_time.setVisible(show_seek)
                hud_h = 54 if show_seek else 32
            else:
                hud_h = hud.height() or 32
        else:
            self._hud_compact_labels = w_lbl < 140
            hud_w = min(112, max(60, w_lbl - 12))
            hud_h = 32
        x = max(4, (w_lbl - hud_w) // 2)
        y = max(4, h_lbl - hud_h - 8)
        hud.setGeometry(x, y, hud_w, hud_h)
        self._refresh_video_controls()
        hud.raise_()

    def _refresh_video_controls(self):
        compact = getattr(self, "_hud_compact_labels", False)
        if self._play_pause_btn is not None:
            self._play_pause_btn.setText("" if compact else ("Play" if self._main_paused else "Pause"))
            self._play_pause_btn.setIcon(make_vector_icon("play" if self._main_paused else "pause", "#f0f2f5", 12))
            self._play_pause_btn.setIconSize(QSize(12, 12))
        if self._mute_btn is not None:
            self._mute_btn.setText("" if compact else ("Muted" if self.video_muted else "Sound"))
            self._mute_btn.setIcon(make_vector_icon("sound_off" if self.video_muted else "sound_on", "#f0f2f5", 12))
            self._mute_btn.setIconSize(QSize(12, 12))

    def toggle_main_playback(self):
        """Play/Pause video atau animasi yang sedang tampil di layar utama (tombol P)."""
        has_anim = len(self._main_anim_frames) > 1 or self.current_movie is not None
        has_video = self._main_audio_player is not None or bool(self._video_decode_path) or self._video_thread is not None
        if not has_anim and not has_video:
            return
        self._main_paused = not self._main_paused
        if self._main_paused:
            self._main_anim_timer.stop()
            if self.current_movie is not None:
                self.current_movie.setPaused(True)
            if self._main_audio_player is not None:
                self._main_audio_player.pause()
        else:
            if self.current_movie is not None:
                self.current_movie.setPaused(False)
            if self._main_audio_player is not None:
                self._main_audio_player.play()
            elif self._video_decode_path:
                if getattr(self, "_video_decode_timer", None) is not None:
                    self._video_decode_timer.stop()
                self._start_deferred_video_anim()
            elif len(self._main_anim_frames) > 1 and not self._main_video_using_qtmm:
                delay = self._main_anim_frames[self._main_anim_index][1]
                self._main_anim_timer.start(max(20, int(delay)))
        self._refresh_video_controls()

    def set_video_muted(self, muted: bool, notify: bool = True):
        self.video_muted = bool(muted)
        if self._main_audio_output is not None:
            self._main_audio_output.setMuted(self.video_muted)
        settings = load_settings()
        settings["video_muted"] = self.video_muted
        save_settings(settings)
        self._refresh_video_controls()
        if notify:
            self.show_notification("Video sound muted" if self.video_muted else "Video sound on")

    def toggle_main_mute(self):
        self.set_video_muted(not self.video_muted)

    def _start_deferred_video_anim(self):
        """Mulai pemutaran video+suara sinkron via QtMultimedia setelah idle 75ms (0 ms UI lag navigasi)."""
        if getattr(self, "_video_decode_timer", None) is not None:
            self._video_decode_timer.stop()
        vpath = getattr(self, "_video_decode_path", None)
        if not vpath or self.is_rapid_moving or self.defer_ui_updates or not os.path.exists(vpath):
            return
        _, cur_actual = self.get_current_actual_path()
        if not cur_actual or os.path.normcase(os.path.normpath(cur_actual)) != os.path.normcase(os.path.normpath(vpath)):
            return
        self._start_main_video_player(vpath)

    def _on_main_video_chunk(self, video_path: str, chunk: list):
        if self.is_rapid_moving or self.defer_ui_updates or not chunk or self._main_video_using_qtmm:
            return
        _, cur_actual = self.get_current_actual_path()
        if not cur_actual or os.path.normcase(os.path.normpath(cur_actual)) != os.path.normcase(os.path.normpath(video_path)):
            return
        for qimg, delay in chunk:
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                self._raw_video_cache_frames.append((pix, delay))
                self._main_anim_frames.append((resize_image(pix), delay))
        if len(self._main_anim_frames) > 1 and not self._main_anim_timer.isActive() and not self._main_paused:
            self._main_anim_index = 0
            self.image_label.setPixmap(self._main_anim_frames[0][0])
            self._main_anim_timer.start(max(20, int(self._main_anim_frames[0][1])))

    def _on_main_video_decode_finished(self, video_path: str):
        if len(self._raw_video_cache_frames) > 1:
            self.pixmap_cache.set_animation_frames(video_path, 720, 500, 60, self._raw_video_cache_frames)

    def _cleanup_video_thread(self, thread):
        self._video_threads.discard(thread)
        if not thread.is_cancelled():
            self._on_main_video_decode_finished(thread.video_path)
        if self._video_thread is thread:
            self._video_thread = None
        thread.deleteLater()

    def init_hot_reload(self):
        """Pantau perubahan pada main.py, utils/image_utils.py, dan config/settings.json.
        Jika file kode diedit, aplikasi otomatis memuat ulang tampilan terbaru di posisi
        dan sesi yang sama tanpa perlu tutup-buka manual."""
        self._hot_reload_timer = None
        if getattr(sys, "frozen", False) or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        app_dir = os.path.dirname(os.path.abspath(__file__))
        self._watched_code_files = [
            os.path.abspath(__file__),
            os.path.join(app_dir, "utils", "image_utils.py"),
        ]
        self._code_sigs = {p: _file_sig(p) for p in self._watched_code_files}
        self._pending_code_reload = False
        self._settings_watch_path = get_config_path()
        self._settings_sig = _file_sig(self._settings_watch_path)

        self._hot_reload_timer = QTimer(self)
        self._hot_reload_timer.setInterval(700)
        self._hot_reload_timer.timeout.connect(self._check_hot_reload)
        self._hot_reload_timer.start()

    def _check_hot_reload(self):
        if self.is_rapid_moving:
            return
        # 1. Cek apakah settings.json diubah dari luar aplikasi
        cur_settings_sig = _file_sig(self._settings_watch_path)
        if cur_settings_sig and cur_settings_sig != self._settings_sig:
            self._settings_sig = cur_settings_sig
            if cur_settings_sig != _LAST_INTERNAL_SETTINGS_SIG:
                self.reload_external_settings()

        # 2. Cek apakah file kode (main.py / image_utils.py) diubah
        changed = False
        for path in self._watched_code_files:
            sig = _file_sig(path)
            if sig and sig != self._code_sigs.get(path):
                self._code_sigs[path] = sig
                changed = True
        if changed:
            # Tunggu 1 siklus agar penulisan file oleh editor selesai 100%
            self._pending_code_reload = True
            return
        if self._pending_code_reload:
            self._pending_code_reload = False
            # Pastikan sintaks Python valid di memori sebelum me-reload proses
            for path in self._watched_code_files:
                try:
                    with open(path, "rb") as f:
                        source_bytes = f.read()
                    compile(source_bytes, path, "exec")
                except Exception as e:
                    print(f"[HOT-RELOAD] Waiting for valid syntax in {path}: {e}")
                    return
            self.trigger_hot_reload()

    def reload_external_settings(self):
        """Terapkan perubahan settings.json secara langsung tanpa restart jendela."""
        settings = load_settings()
        self.load_custom_folders()
        self.load_recent_folders()
        self.theme_mode = settings.get("theme_mode", "system")
        self.rapid_move_interval = clamp_rapid_interval(
            settings.get("rapid_move_interval", RAPID_MOVE_DEFAULT_MS)
        )
        self.video_muted = bool(settings.get("video_muted", False))
        try:
            self.video_volume = max(0.0, min(1.0, float(settings.get("video_volume", 0.8))))
        except (TypeError, ValueError):
            self.video_volume = 0.8
        if self._main_audio_output is not None:
            self._main_audio_output.setMuted(self.video_muted)
            self._main_audio_output.setVolume(self.video_volume)
        self._refresh_video_controls()
        self.sync_menu_theme_checkboxes()
        self.apply_theme()
        self.update_folder_buttons()
        self.show_current_image(self.filtered_files)
        self.show_notification("⚡ Settings reloaded automatically")

    def _hot_reload_state_path(self):
        return os.path.join(os.path.dirname(get_config_path()), ".hot_reload_state.json")

    def trigger_hot_reload(self):
        """Simpan state sesi saat ini, jalankan proses baru, dan tutup proses lama."""
        if self._hot_reload_timer is not None:
            self._hot_reload_timer.stop()
        modal = QApplication.activeModalWidget()
        active_dialog = type(modal).__name__ if modal is not None else None
        geom = self.geometry()
        state = {
            "timestamp": time.time(),
            "geometry": [geom.x(), geom.y(), geom.width(), geom.height()],
            "maximized": self.isMaximized(),
            "folder_path": self.current_folder_path,
            "current_index": self.current_index,
            "filter_text": self.filter_combo.currentText() if hasattr(self, "filter_combo") else "All Files",
            "hide_moved": self.hide_moved,
            "active_dialog": active_dialog,
        }
        try:
            with open(self._hot_reload_state_path(), "w", encoding="utf-8") as f:
                json.dump(state, f)
        except OSError:
            pass
        if modal is not None:
            modal.close()
        self.stop_rapid_move(silent=True)
        self.stop_current_movie()
        self.flush_history()
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
        except OSError as e:
            print(f"[HOT-RELOAD] Failed to spawn new instance: {e}")
            return
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def restore_hot_reload_state(self):
        """Pulihkan posisi jendela, folder, gambar aktif, dan dialog setelah hot-reload."""
        state_path = self._hot_reload_state_path()
        if not os.path.exists(state_path):
            return
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            state = None
        try:
            os.remove(state_path)
        except OSError:
            pass
        if not state or time.time() - state.get("timestamp", 0) > 20:
            return

        geom = state.get("geometry")
        if isinstance(geom, list) and len(geom) == 4:
            self.setGeometry(geom[0], geom[1], geom[2], geom[3])
        if state.get("maximized"):
            self.showMaximized()

        self.hide_moved = bool(state.get("hide_moved", False))
        if hasattr(self, "hide_moved_action"):
            self.hide_moved_action.setChecked(self.hide_moved)

        filter_text = state.get("filter_text", "All Files")
        if hasattr(self, "filter_combo"):
            idx = self.filter_combo.findText(filter_text)
            if idx >= 0:
                self.filter_combo.blockSignals(True)
                self.filter_combo.setCurrentIndex(idx)
                self.filter_combo.blockSignals(False)

        folder_path = state.get("folder_path") or ""
        if folder_path and os.path.isdir(folder_path):
            files = scan_image_files(
                folder_path,
                include_subfolders=self.include_subfolders,
                excluded_dirs=self.folder_paths,
            )
            if files:
                self.current_folder_path = folder_path
                self.image_files = files
                self.apply_filter()
                saved_idx = int(state.get("current_index", 0))
                if 0 <= saved_idx < len(self.filtered_files):
                    self.current_index = saved_idx
                    self.show_current_image(self.filtered_files)

        self.show_notification("⚡ Live Reloaded — displaying latest changes")
        active_dialog = state.get("active_dialog")
        if active_dialog == "ShortcutsGuideDialog":
            QTimer.singleShot(150, self.show_shortcuts_guide)
        elif active_dialog == "AboutDialog":
            QTimer.singleShot(150, self.show_about)

    def closeEvent(self, event):
        """Hentikan timer & thread latar dengan aman sebelum jendela ditutup."""
        if getattr(self, "_hot_reload_timer", None) is not None:
            self._hot_reload_timer.stop()
        self.stop_rapid_move(silent=True)
        self.stop_current_movie()
        self.flush_history()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if getattr(self, "_prefetch_timer", None) is not None:
            self._prefetch_timer.stop()
        if getattr(self, "dup_thread", None) is not None and self.dup_thread.isRunning():
            self.dup_thread.cancel()
            self.dup_thread.wait(3000)
        for vt in list(getattr(self, "_video_threads", ())):
            vt.cancel()
        for vt in list(getattr(self, "_video_threads", ())):
            vt.wait(1500)
        for thread in list(self._scan_threads):
            thread.cancel()
        for thread in list(self._scan_threads):
            thread.wait(3000)
        if self.update_thread is not None and self.update_thread.isRunning():
            self.update_thread.wait(6000)
        super().closeEvent(event)

    def check_first_run(self):
        settings = load_settings()
        first_run = settings.get("first_run", True)

        if first_run:
            self.set_default_settings()
            settings["first_run"] = False
            save_settings(settings)
            self.show_notification("Welcome to ImageSorter — organize your media in seconds.")
        else:
            # Muat pengaturan terakhir secara otomatis tanpa popup berisiko
            self.load_custom_folders()
            self.load_recent_folders()
            self.theme_mode = settings.get("theme_mode", "system")
            self.rapid_move_interval = clamp_rapid_interval(
                settings.get("rapid_move_interval", RAPID_MOVE_DEFAULT_MS)
            )
            self.sync_menu_theme_checkboxes()

        self.apply_theme()
        self.update_folder_buttons()
        self.show_current_image(self.filtered_files)

    def confirm_reset_default_settings(self):
        """Konfirmasi sebelum mereset pengaturan ke default (riwayat Undo tetap aman)."""
        msg = QMessageBox()
        msg.setWindowTitle("Reset Default Settings")
        msg.setText("Reset folder names, paths, and theme back to default settings?\n(Your Undo history will be preserved.)")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setIcon(QMessageBox.Question)
        self.apply_message_box_style(msg)
        if msg.exec() == QMessageBox.Yes:
            self.set_default_settings()
            self.apply_theme()
            self.update_folder_buttons()
            self.sync_menu_theme_checkboxes()
            self.show_notification("Default settings restored.")

    def set_default_settings(self):
        print("[DEBUG] Using JSON-based set_default_settings")
        settings = {
            "first_run": False,
            "folder_slot_count": DEFAULT_FOLDER_SLOTS,
            "include_subfolders": False,
            "folder_names": ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"],
            "folder_paths": ["output/A", "output/B", "output/C", "output/D", "output/E"],
            "recent_folders": [],
            "theme_mode": "system",
            "rapid_move_interval": RAPID_MOVE_DEFAULT_MS,
            "video_muted": False,
            "video_volume": 0.8,
            "custom_theme": {
                "bg_color": "#0e1015",
                "text_color": "#f0f2f5",
                "btn_bg": "#181b23",
                "btn_hover": "#212633",
                "label_bg": "#13161d",
                "menu_bg": "#12141b",
                "menu_text": "#f0f2f5",
                "main_border_color": "#3b82f6",
                "next_border_color": "#10b981",
                "main_shadow": "0 0 10px rgba(59, 130, 246, 0.55)",
                "next_shadow": "0 0 8px rgba(16, 185, 129, 0.45)"
            }
        }
        save_settings(settings)
        self.include_subfolders = False
        self.video_muted = False
        self.video_volume = 0.8
        if self._main_audio_output is not None:
            self._main_audio_output.setMuted(False)
            self._main_audio_output.setVolume(0.8)
        self._refresh_video_controls()
        if hasattr(self, "include_subfolders_action"):
            self.include_subfolders_action.setChecked(False)
        self.load_custom_folders()
        self.load_recent_folders()
        self.theme_mode = "system"
        self.rapid_move_interval = RAPID_MOVE_DEFAULT_MS
        self.current_index = 0
        self.filtered_files = []
        self.image_files = []
        self.nav_history.clear()
        # Riwayat pemindahan (Undo) sengaja TIDAK dihapus: itu satu-satunya jejak
        # untuk mengembalikan file. Mereset tampilan/pengaturan tidak boleh menghilangkannya.
        self.show_current_image(self.filtered_files)

    def open_custom_theme_editor(self):
        dialog = CustomThemeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # CustomThemeDialog.save_and_close() sudah menyimpan SELURUH key tema
            # (termasuk warna border & shadow); jangan ditimpa ulang dengan subset.
            self.set_theme_mode("custom")
        else:
            self.sync_menu_theme_checkboxes()

    def update_recent_folders(self, folder_path):
        if folder_path in self.recent_folders:
            self.recent_folders.remove(folder_path)
        self.recent_folders.insert(0, folder_path)
        if len(self.recent_folders) > 5:
            self.recent_folders.pop()
        self.save_recent_folders()
        self.update_recent_folders_menu()

    def save_recent_folders(self):
        settings = load_settings()
        settings["recent_folders"] = self.recent_folders
        save_settings(settings)
    
    def load_recent_folders(self):
        settings = load_settings()
        folders = settings.get("recent_folders", [])
        self.recent_folders = [f for f in folders if os.path.isdir(f)]
        self.update_recent_folders_menu()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if os.path.isdir(path):
            self.import_folder_common(path)
        elif os.path.isfile(path) and self.is_image_file(path):
            self.stop_rapid_move(silent=True)
            self.show_loading(True)
            source_folder = os.path.dirname(path)
            self.update_recent_folders(source_folder)
            self.cancel_running_scan()
            self.load_file_list(source_folder, [path])
        else:
            self.show_loading(False)
            msg = QMessageBox()
            msg.setWindowTitle("Invalid Drop")
            msg.setText("Only folders or image files are supported.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()

    def import_folder_common(self, folder_path):
        self.stop_rapid_move(silent=True)
        self.show_loading(True)
        self.position_stack.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.update_recent_folders(folder_path)
        # Selalu pindai ulang (tanpa cache daftar) agar file baru/terhapus langsung terlihat.
        self.start_scan(folder_path)

    def cancel_running_scan(self):
        if self.scan_thread is not None and self.scan_thread.isRunning():
            self.scan_thread.cancel()
        self.scan_thread = None

    def start_scan(self, folder_path):
        """Pindai folder di thread latar; hasil pemindaian lama (import yang digantikan) diabaikan."""
        self.cancel_running_scan()
        readable_image_extensions()  # isi cache format Qt di thread utama sebelum thread latar jalan
        self.progress_bar.setRange(0, 0)  # indikator sibuk: total belum diketahui
        sub_note = " (with subfolders)" if self.include_subfolders else ""
        self.loading_label.setText(f"Scanning folder{sub_note}...")
        thread = FolderScanThread(
            folder_path,
            self,
            include_subfolders=self.include_subfolders,
            excluded_dirs=self.folder_paths,
        )
        self._scan_threads.add(thread)
        thread.progress_updated.connect(
            lambda count, t=thread: self.on_scan_progress(t, count)
        )
        thread.finished.connect(lambda t=thread: self.on_scan_finished(t))
        self.scan_thread = thread
        thread.start()

    def on_scan_progress(self, thread, count):
        if thread is self.scan_thread:
            self.loading_label.setText(f"Scanning folder...\n{count:,} images found")

    def on_scan_finished(self, thread):
        self._scan_threads.discard(thread)
        if thread is not self.scan_thread:
            thread.deleteLater()  # hasil import lama, abaikan
            return
        self.scan_thread = None
        files, error, folder_path = thread.files, thread.error, thread.folder_path
        thread.deleteLater()
        self.progress_bar.setRange(0, 100)
        self.loading_label.setText("Loading folder...")
        if error:
            self.show_loading(False)
            self.position_stack.setCurrentIndex(0)
            msg = QMessageBox()
            msg.setWindowTitle("Import Error")
            msg.setText(f"Could not read this folder:\n{error}")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return
        self.load_file_list(folder_path, files)

    def is_image_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        return ext in SUPPORTED_IMAGE_EXTENSIONS

    def _get_ui_tokens(self):
        """Kembalikan palet design-token terpadu untuk tema Dark, Light, dan Custom."""
        is_dark = self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark())
        if self.theme_mode == "custom":
            ct = load_settings().get("custom_theme", {})
            bg = ct.get("bg_color", "#111318")
            dark_custom = QColor(bg).lightness() < 128
            return {
                "is_dark": dark_custom,
                "win_bg": bg,
                "stage_bg": ct.get("label_bg", "#151821"),
                "surface": ct.get("btn_bg", "#1c1f29"),
                "surface_hover": ct.get("btn_hover", "#262a37"),
                "surface_pressed": ct.get("btn_hover", "#2f3444"),
                "border": "#303545" if dark_custom else "#cfd5e2",
                "border_strong": ct.get("main_border_color", "#3b82f6"),
                "next_border": ct.get("next_border_color", "#10b981"),
                "text": ct.get("text_color", "#f0f2f5"),
                "text_muted": "#9aa1b2" if dark_custom else "#5f6675",
                "card_bg": ct.get("label_bg", "#161922"),
                "next_card_bg": ct.get("label_bg", "#14171f"),
                "menu_bg": ct.get("menu_bg", "#13161e"),
                "menu_text": ct.get("menu_text", "#f0f2f5"),
                "accent": ct.get("main_border_color", "#3b82f6"),
            }
        if is_dark:
            return {
                "is_dark": True,
                "win_bg": "#0e1015",
                "stage_bg": "#13161d",
                "surface": "#181b23",
                "surface_hover": "#212633",
                "surface_pressed": "#2a3040",
                "border": "#262a36",
                "border_strong": "#363c4d",
                "next_border": "#282c39",
                "text": "#f0f2f5",
                "text_muted": "#8b91a1",
                "card_bg": "#151820",
                "next_card_bg": "#151820",
                "menu_bg": "#12141b",
                "menu_text": "#f0f2f5",
                "accent": "#3b82f6",
            }
        return {
            "is_dark": False,
            "win_bg": "#f3f4f7",
            "stage_bg": "#e9ecf2",
            "surface": "#ffffff",
            "surface_hover": "#f0f2f6",
            "surface_pressed": "#e4e7ee",
            "border": "#d6dae3",
            "border_strong": "#bfc6d4",
            "next_border": "#d0d5e0",
            "text": "#16181d",
            "text_muted": "#646b7a",
            "card_bg": "#ffffff",
            "next_card_bg": "#f8f9fb",
            "menu_bg": "#ffffff",
            "menu_text": "#16181d",
            "accent": "#2563eb",
        }

    def apply_theme(self):
        t = self._get_ui_tokens()
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {t["win_bg"]}; }}
            QWidget {{ color: {t["text"]}; }}
            QFrame#studioStage {{
                background-color: {t["stage_bg"]};
                border: 1px solid {t["border"]};
                border-radius: 14px;
            }}
            QLabel {{
                color: {t["text"]};
                background-color: transparent;
                border: none;
            }}
            QLabel#headerFileBar, QLabel#headerCounterBar {{
                background-color: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: 9px;
                padding: 0px 12px;
                font-size: 12px;
            }}
            QLabel#headerCounterBar {{
                font-weight: 700;
                font-family: Consolas, monospace;
            }}
            QLabel#nextEyebrowLabel {{
                color: {t["text_muted"]};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }}
            QPushButton {{
                background-color: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                padding: 6px 14px;
                font-weight: 600;
                border-radius: 9px;
                min-height: 26px;
            }}
            QPushButton:hover {{
                background-color: {t["surface_hover"]};
                border-color: {t["border_strong"]};
            }}
            QPushButton:pressed {{ background-color: {t["surface_pressed"]}; }}
            QMenuBar {{
                background-color: {t["menu_bg"]};
                color: {t["menu_text"]};
                border-bottom: 1px solid {t["border"]};
                padding: 2px 6px;
            }}
            QMenuBar::item {{
                padding: 5px 10px;
                border-radius: 5px;
                background: transparent;
            }}
            QMenuBar::item:selected {{ background-color: {t["surface_hover"]}; }}
            QMenu {{
                background-color: {t["menu_bg"]};
                color: {t["menu_text"]};
                border: 1px solid {t["border"]};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 18px 6px 10px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{ background-color: {t["surface_hover"]}; }}
            QMenu::icon {{
                padding-left: 8px;
            }}
            QMenu::separator {{
                height: 1px;
                background: {t["border"]};
                margin: 4px 8px;
            }}
            QToolTip {{
                background-color: {t["menu_bg"]};
                color: {t["text"]};
                border: 1px solid {t["border_strong"]};
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
            }}
        """)

        self.update_progress_bar_style()
        self.update_label_styles()
        self.update_button_styles()
        self.update_menu_icons()
        self.update_folder_buttons()
        self.show_current_image()

    def sync_menu_theme_checkboxes(self):
        self.light_action.setChecked(self.theme_mode == "light")
        self.dark_action.setChecked(self.theme_mode == "dark")
        self.system_action.setChecked(self.theme_mode == "system")
        self.custom_action.setChecked(self.theme_mode == "custom")

    def update_label_styles(self):
        t = self._get_ui_tokens()
        main_bwidth = "2px" if self.theme_mode == "custom" else "1px"
        next_bwidth = "2px dashed" if self.theme_mode == "custom" else "1px solid"

        self.image_label.setStyleSheet(f"""
            QLabel {{
                color: {t["text"]};
                background-color: {t["card_bg"]};
                border: {main_bwidth} solid {t["border_strong"]};
                border-radius: 10px;
                padding: 0px;
            }}
        """)

        self.next_image_label.setStyleSheet(f"""
            QLabel {{
                color: {t["text_muted"]};
                background-color: {t["next_card_bg"]};
                border: {next_bwidth} {t["next_border"]};
                border-radius: 10px;
                padding: 0px;
                font-size: 12px;
            }}
        """)

        if hasattr(self, "_main_shadow_effect") and self._main_shadow_effect is not None:
            self._main_shadow_effect.setColor(QColor(0, 0, 0, 115) if t["is_dark"] else QColor(15, 23, 42, 36))
            self._main_shadow_effect.setBlurRadius(28)
            self._main_shadow_effect.setOffset(0, 8)
        if hasattr(self, "_next_shadow_effect") and self._next_shadow_effect is not None:
            self._next_shadow_effect.setColor(QColor(0, 0, 0, 70) if t["is_dark"] else QColor(15, 23, 42, 24))
            self._next_shadow_effect.setBlurRadius(16)
            self._next_shadow_effect.setOffset(0, 4)

        self.image_label.setMouseTracking(True)
        self.next_image_label.setMouseTracking(True)

    def is_system_dark(self):
        palette = QApplication.palette()
        base_color = palette.window().color()
        brightness = base_color.red() * 0.299 + base_color.green() * 0.587 + base_color.blue() * 0.114
        return brightness < 128

    def update_button_styles(self):
        t = self._get_ui_tokens()
        for btn in [self.undo_btn, self.skip_btn, self.prev_btn, self.next_btn, self.filter_combo]:
            self.set_modern_button_style(btn)
        self.prev_btn.setIcon(make_vector_icon("prev", t["text"], 15))
        self.prev_btn.setIconSize(QSize(15, 15))
        self.next_btn.setIcon(make_vector_icon("next", t["text"], 15))
        self.next_btn.setIconSize(QSize(15, 15))
        self.undo_btn.setIcon(make_vector_icon("undo", t["text"], 15))
        self.undo_btn.setIconSize(QSize(15, 15))
        self.skip_btn.setIcon(make_vector_icon("skip", t["text"], 15))
        self.skip_btn.setIconSize(QSize(15, 15))

    def show_notification(self, text):
        if hasattr(self, 'fade_in') and self.fade_in.state() == QPropertyAnimation.Running:
            self.fade_in.stop()
        if hasattr(self, 'fade_out') and self.fade_out.state() == QPropertyAnimation.Running:
            self.fade_out.stop()

        self.notification_label.setText(text)

        t = self._get_ui_tokens()
        bg_rgba = "rgba(22, 25, 34, 232)" if t["is_dark"] else "rgba(255, 255, 255, 240)"
        self.notification_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            padding: 8px 16px;
            border-radius: 10px;
            color: {t["text"]};
            background-color: {bg_rgba};
            border: 1px solid {t["border_strong"]};
            text-align: center;
        """)

        self.notification_label.setWordWrap(True)
        self.notification_label.setAlignment(Qt.AlignCenter)

        font_metrics = self.notification_label.fontMetrics()
        self._notification_text_width = font_metrics.horizontalAdvance(text) + 36
        self.position_notification()

        self.notification_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.notification_label.setWindowOpacity(0.0)
        self.notification_label.show()
        self.notification_label.raise_()

        self.fade_in = QPropertyAnimation(self.notification_label, b"windowOpacity")
        self.fade_in.setDuration(180)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

        self.fade_out = QPropertyAnimation(self.notification_label, b"windowOpacity")
        self.fade_out.setDuration(220)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)

        self.fade_in.finished.connect(lambda: QTimer.singleShot(2100, self.fade_out.start))
        self.fade_out.finished.connect(self.notification_label.hide)

        self.fade_in.start()

    def position_notification(self):
        """Letakkan notifikasi mengambang di bawah panggung media tanpa menutupi tombol kontrol."""
        available = max(140, self.width() - 40)
        text_width = getattr(self, "_notification_text_width", 280)
        label_width = min(available, max(260, min(680, text_width)))
        label_height = 42
        x = max(20, (self.width() - label_width) // 2)
        y = max(56, self.height() - 220)
        self.notification_label.setGeometry(x, y, label_width, label_height)

    def update_menu_icons(self):
        """Perbarui seluruh ikon QMenuBar menggunakan ikon vektor Studio Slate agar seragam & tajam di semua tema."""
        t = self._get_ui_tokens()
        col = t["menu_text"]
        accent = t["accent"]
        danger = "#f87171" if t["is_dark"] else "#dc2626"
        action_specs = [
            ("import_action", "folder_plus", accent),
            ("reveal_action", "folder_search", col),
            ("recycle_action", "trash", danger),
            ("export_action", "file_text", col),
            ("custom_action", "palette", "#a855f7" if t["is_dark"] else "#7e22ce"),
            ("light_action", "sun", "#f59e0b"),
            ("dark_action", "moon", "#38bdf8" if t["is_dark"] else "#0284c7"),
            ("system_action", "monitor", col),
            ("hide_moved_action", "eye_off", col),
            ("include_subfolders_action", "folder_tree", col),
            ("dup_action", "duplicates", accent),
            ("jump_action", "jump", col),
            ("preview_action", "expand", col),
            ("settings_action", "sliders", accent),
            ("export_settings_action", "upload", col),
            ("import_settings_action", "download", col),
            ("rapid_move_action", "bolt", "#f59e0b"),
            ("reset_settings_action", "reset", danger),
            ("shortcuts_action", "keyboard", accent),
            ("about_action", "info", col),
            ("update_action", "update", "#10b981"),
        ]
        for attr_name, icon_kind, icon_col in action_specs:
            act = getattr(self, attr_name, None)
            if act is not None:
                act.setIcon(make_vector_icon(icon_kind, icon_col, 15))
        if hasattr(self, "recent_folders_menu") and self.recent_folders_menu is not None:
            self.recent_folders_menu.setIcon(make_vector_icon("clock", col, 15))
            self.update_recent_folders_menu()

    def update_recent_folders_menu(self):
        if not hasattr(self, 'recent_folders_menu') or self.recent_folders_menu is None:
            return

        t = self._get_ui_tokens()
        for action in self.recent_folders_menu.actions():
            self.recent_folders_menu.removeAction(action)

        for folder in self.recent_folders:
            action = QAction(folder, self)
            action.setIcon(make_vector_icon("folder", t["accent"], 14))
            action.triggered.connect(lambda _, path=folder: self.import_folder_from_path(path))
            self.recent_folders_menu.addAction(action)

        if self.recent_folders:
            self.recent_folders_menu.addSeparator()

        clear_action = QAction("Clear Recent", self)
        clear_action.setIcon(make_vector_icon("trash", "#f87171" if t["is_dark"] else "#dc2626", 14))
        clear_action.triggered.connect(self.clear_recent_folders)
        self.recent_folders_menu.addAction(clear_action)

    def import_folder_from_path(self, folder_path):
        if not os.path.isdir(folder_path):
            self.show_notification("Folder is invalid or not found.")
            return

        self.import_folder_common(folder_path)

    def load_file_list(self, folder_path, files):
        """Pasang daftar file hasil pemindaian ke tampilan."""
        self.current_folder_path = folder_path if files else ""
        self.image_files = files
        self.filtered_files = []
        self.current_index = 0
        self.nav_history.clear()
        self.pixmap_cache.clear()
        self.duplicate_norms.clear()
        self.duplicate_groups.clear()
        self.duplicate_group_lookup.clear()
        if not self.image_files:
            self.show_current_image(self.filtered_files)
            self.show_loading(False)
            self.position_stack.setCurrentIndex(0)
            msg = QMessageBox()
            msg.setWindowTitle("No Images")
            msg.setText("No valid images found in this folder.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        count = len(self.image_files)
        self.source_info = f"{count:,} image{'s' if count != 1 else ''} imported from: {folder_path}"
        self.apply_filter()
        self.show_notification(self.source_info)
        self.show_loading(False)
        self.position_stack.setCurrentIndex(0)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 8, 14, 10)
        main_layout.setSpacing(8)

        self.image_label = QLabel("Current Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self._main_shadow_effect = QGraphicsDropShadowEffect(self)
        self._main_shadow_effect.setBlurRadius(24)
        self._main_shadow_effect.setColor(QColor(0, 0, 0, 115))
        self._main_shadow_effect.setOffset(0, 6)
        self.image_label.setGraphicsEffect(self._main_shadow_effect)

        self.next_image_label = QLabel("No upcoming\nmedia")
        self.next_image_label.setAlignment(Qt.AlignCenter)
        self.next_image_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._next_shadow_effect = QGraphicsDropShadowEffect(self)
        self._next_shadow_effect.setBlurRadius(14)
        self._next_shadow_effect.setColor(QColor(0, 0, 0, 70))
        self._next_shadow_effect.setOffset(0, 4)
        self.next_image_label.setGraphicsEffect(self._next_shadow_effect)
        self.update_label_styles()

        self.stage_frame = QFrame()
        self.stage_frame.setObjectName("studioStage")
        self.stage_frame.setMinimumHeight(200)
        preview_layout = QHBoxLayout(self.stage_frame)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(16)

        self.main_viewport = _StageViewport(self.image_label, min_w=260, min_h=180)
        self.main_viewport.resized.connect(self._on_stage_viewport_resized)

        self.next_stage_box = QWidget()
        next_stage_lay = QVBoxLayout(self.next_stage_box)
        next_stage_lay.setContentsMargins(0, 0, 0, 0)
        next_stage_lay.setSpacing(6)
        self.next_eyebrow = QLabel("UP NEXT")
        self.next_eyebrow.setObjectName("nextEyebrowLabel")
        self.next_eyebrow.setAlignment(Qt.AlignCenter)
        self.next_viewport = _StageViewport(self.next_image_label, min_w=130, min_h=140)
        next_stage_lay.addWidget(self.next_eyebrow, 0, Qt.AlignCenter)
        next_stage_lay.addWidget(self.next_viewport, stretch=1)

        preview_layout.addWidget(self.main_viewport, stretch=3)
        preview_layout.addWidget(self.next_stage_box, stretch=1)

        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)

        self.file_info_label = QLabel("No image loaded.")
        self.file_info_label.setObjectName("headerFileBar")
        self.file_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.file_info_label.setFixedHeight(34)
        self.file_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.position_container = QWidget()
        self.position_stack = QStackedLayout(self.position_container)
        self.position_container.setFixedHeight(34)
        self.position_container.setMinimumWidth(88)
        self.position_stack.setContentsMargins(0, 0, 0, 0)

        self.position_info_label = QLabel("0 / 0")
        self.position_info_label.setObjectName("headerCounterBar")
        self.position_info_label.setAlignment(Qt.AlignCenter)
        self.position_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.update_progress_bar_style()
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.progress_bar.setFixedHeight(34)

        self.position_stack.addWidget(self.position_info_label)
        self.position_stack.addWidget(self.progress_bar)
        self.position_stack.setCurrentIndex(0)

        info_layout.addWidget(self.file_info_label, stretch=1)
        info_layout.addWidget(self.position_container)

        main_layout.addLayout(info_layout)
        main_layout.addWidget(self.stage_frame, stretch=1)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setToolTip("Go to previous media (Left Arrow ←)")
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.set_modern_button_style(self.prev_btn)
        self.prev_btn.clicked.connect(self.show_previous)
        self.prev_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setToolTip("Go to next media (Right Arrow →)")
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.set_modern_button_style(self.next_btn)
        self.next_btn.clicked.connect(self.show_next)
        self.next_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout.addWidget(self.next_btn)

        nav_layout.setStretch(0, 1)
        nav_layout.setStretch(1, 1)

        self.folder_layout = QGridLayout()
        self.folder_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_layout.setSpacing(8)
        self.update_folder_buttons()

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        self.filter_combo = QComboBox()
        self.filter_combo.setToolTip("Select file extension or media type to filter")
        self.filter_combo.setCursor(Qt.PointingHandCursor)
        self.filter_combo.setMaxVisibleItems(10)
        self.filter_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.filter_combo.addItem("All Files")
        self.filter_combo.addItem("All Images")
        self.filter_combo.addItem("All Videos")
        self.filter_combo.addItem("Animated / GIF")
        self.filter_combo.addItem("Duplicates Only")
        readable_exts = readable_image_extensions()
        self.filter_combo.addItems([ext for ext in SUPPORTED_IMAGE_EXTENSIONS if ext in readable_exts])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        self.set_modern_button_style(self.filter_combo)
        action_layout.addWidget(self.filter_combo, stretch=2)
        self.filter_combo.setCurrentIndex(0)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setToolTip("Undo the last move (Ctrl+Z)")
        self.undo_btn.setCursor(Qt.PointingHandCursor)
        self.set_modern_button_style(self.undo_btn)
        self.undo_btn.clicked.connect(self.undo_action)
        action_layout.addWidget(self.undo_btn, stretch=5)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setToolTip("Skip to next unmoved media (Space)")
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.set_modern_button_style(self.skip_btn)
        self.skip_btn.clicked.connect(self.skip_image)
        action_layout.addWidget(self.skip_btn, stretch=5)

        self.setWindowIcon(QIcon(resource_path("assets/icons/app_icon.png")))
        self.update_button_styles()
        self.update_button_widths()

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addLayout(nav_layout)
        button_layout.addLayout(self.folder_layout)
        button_layout.addLayout(action_layout)

        main_layout.addWidget(button_container)

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        file_menu = menu_bar.addMenu("File")
        self.import_action = QAction("Import Folder", self)
        self.import_action.setShortcut(QKeySequence("Ctrl+O"))
        self.import_action.setToolTip("Import images from folder (Ctrl+O)")
        self.import_action.triggered.connect(self.import_folder)
        file_menu.addAction(self.import_action)

        self.reveal_action = QAction("Show in File Explorer", self)
        self.reveal_action.setShortcut(QKeySequence("Ctrl+E"))
        self.reveal_action.setToolTip("Reveal current image in File Explorer (Ctrl+E)")
        self.reveal_action.triggered.connect(self.reveal_in_explorer)
        file_menu.addAction(self.reveal_action)

        self.recycle_action = QAction("Move to Recycle Bin", self)
        self.recycle_action.setShortcut(QKeySequence("Delete"))
        self.recycle_action.setToolTip("Move current image to Windows Recycle Bin (Delete)")
        self.recycle_action.triggered.connect(self.delete_current_to_recycle_bin)
        file_menu.addAction(self.recycle_action)

        self.export_action = QAction("Export Log", self)
        self.export_action.setToolTip("Export activity log to text file")
        self.export_action.triggered.connect(self.export_log)
        file_menu.addAction(self.export_action)

        self.recent_folders_menu = file_menu.addMenu("Recent Folders")
        self.update_recent_folders_menu()

        view_menu = menu_bar.addMenu("View")
        self.light_action = QAction("Light Mode", self)
        self.dark_action = QAction("Dark Mode", self)
        self.system_action = QAction("System Default", self)
        self.custom_action = QAction("Custom Theme", self)
        self.custom_action.setCheckable(True)
        self.custom_action.setChecked(self.theme_mode == "custom")
        self.custom_action.triggered.connect(lambda: self.open_custom_theme_editor())
        view_menu.addAction(self.custom_action)

        self.light_action.setCheckable(True)
        self.dark_action.setCheckable(True)
        self.system_action.setCheckable(True)

        self.light_action.setChecked(self.theme_mode == "light")
        self.dark_action.setChecked(self.theme_mode == "dark")
        self.system_action.setChecked(self.theme_mode == "system")

        self.light_action.triggered.connect(lambda: self.set_theme_mode("light"))
        self.dark_action.triggered.connect(lambda: self.set_theme_mode("dark"))
        self.system_action.triggered.connect(lambda: self.set_theme_mode("system"))

        view_menu.addAction(self.light_action)
        view_menu.addAction(self.dark_action)
        view_menu.addAction(self.system_action)
        view_menu.addSeparator()

        self.hide_moved_action = QAction("Hide Moved Images", self)
        self.hide_moved_action.setCheckable(True)
        self.hide_moved_action.setChecked(self.hide_moved)
        self.hide_moved_action.setShortcut(QKeySequence("Ctrl+H"))
        self.hide_moved_action.triggered.connect(self.toggle_hide_moved)
        view_menu.addAction(self.hide_moved_action)

        self.include_subfolders_action = QAction("Include Subfolders", self)
        self.include_subfolders_action.setCheckable(True)
        self.include_subfolders_action.setChecked(self.include_subfolders)
        self.include_subfolders_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.include_subfolders_action.triggered.connect(self.toggle_include_subfolders)
        view_menu.addAction(self.include_subfolders_action)

        self.dup_action = QAction("Find Duplicate / Similar Images", self)
        self.dup_action.setShortcut(QKeySequence("Ctrl+D"))
        self.dup_action.triggered.connect(self.scan_duplicates)
        view_menu.addAction(self.dup_action)

        self.jump_action = QAction("Jump to Image...", self)
        self.jump_action.setShortcut(QKeySequence("Ctrl+G"))
        self.jump_action.triggered.connect(self.jump_to_image_dialog)
        view_menu.addAction(self.jump_action)

        self.preview_action = QAction("Full-Size Preview", self)
        self.preview_action.setShortcut(QKeySequence("F"))
        self.preview_action.triggered.connect(self.open_full_preview)
        view_menu.addAction(self.preview_action)

        settings_menu = menu_bar.addMenu("Settings")
        self.settings_action = QAction("Folder Settings", self)
        self.export_settings_action = QAction("Export Settings", self)
        self.import_settings_action = QAction("Import Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.export_settings_action.triggered.connect(self.export_settings)
        self.import_settings_action.triggered.connect(self.import_settings)
        self.rapid_move_action = QAction("Rapid Move Speed", self)
        self.rapid_move_action.triggered.connect(self.open_rapid_move_settings)
        self.reset_settings_action = QAction("Reset Default Settings", self)
        self.reset_settings_action.triggered.connect(self.confirm_reset_default_settings)

        settings_menu.addAction(self.settings_action)
        settings_menu.addAction(self.export_settings_action)
        settings_menu.addAction(self.import_settings_action)
        settings_menu.addAction(self.rapid_move_action)
        settings_menu.addSeparator()
        settings_menu.addAction(self.reset_settings_action)

        help_menu = menu_bar.addMenu("Help")
        self.shortcuts_action = QAction("Keyboard Shortcuts && Guide", self)
        self.shortcuts_action.setShortcut(QKeySequence("F1"))
        self.shortcuts_action.setToolTip("View all keyboard shortcuts and usage tutorial (F1)")
        self.shortcuts_action.triggered.connect(self.show_shortcuts_guide)
        help_menu.addAction(self.shortcuts_action)
        help_menu.addSeparator()

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)
        help_menu.addAction(self.about_action)

        self.update_action = QAction("Check for Updates", self)
        self.update_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(self.update_action)
        self.update_menu_icons()

        central_widget.setLayout(main_layout)

        self.notification_label = QLabel(self)
        self.notification_label.setWordWrap(True)
        self.notification_label.setAlignment(Qt.AlignCenter)
        self.notification_label.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
            padding: 10px;
            border-radius: 8px;
            color: white;
            background-color: rgba(50, 50, 50, 220);
        """)
        self.notification_label.hide()

        # Tombol 1-5 ditangani secara seragam oleh eventFilter (tekan = pindah 1 gambar, tahan = rapid move).
        home_shortcut = QShortcut(QKeySequence("Home"), self)
        home_shortcut.activated.connect(self.show_first_image)
        end_shortcut = QShortcut(QKeySequence("End"), self)
        end_shortcut.activated.connect(self.show_last_image)
        next_shortcut = QShortcut(QKeySequence("Right"), self)
        next_shortcut.activated.connect(self.show_next)
        prev_shortcut = QShortcut(QKeySequence("Left"), self)
        prev_shortcut.activated.connect(self.show_previous)
        undo_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), self)
        undo_shortcut.activated.connect(self.undo_action)
        skip_shortcut = QShortcut(QKeySequence("Space"), self)
        skip_shortcut.activated.connect(self.skip_image)
        play_pause_shortcut = QShortcut(QKeySequence("P"), self)
        play_pause_shortcut.activated.connect(self.toggle_main_playback)
        mute_shortcut = QShortcut(QKeySequence("M"), self)
        mute_shortcut.activated.connect(self.toggle_main_mute)

    def check_for_updates(self):
        """Cek update manual dari menu, tanpa membekukan UI."""
        self.show_notification("Checking for updates...")
        self.start_update_check(manual=True)

    def update_progress_bar_style(self):
        t = self._get_ui_tokens()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: 9px;
                text-align: center;
                font-size: 12px;
                font-weight: 600;
                padding: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {t["accent"]};
                border-radius: 7px;
            }}
        """)

    def set_theme_mode(self, mode):
        valid_modes = ["light", "dark", "system", "custom"]
        if mode not in valid_modes:
            return
        self.theme_mode = mode
        settings = load_settings()
        settings["theme_mode"] = self.theme_mode
        save_settings(settings)

        for action in [self.light_action, self.dark_action, self.system_action, self.custom_action]:
            action.setChecked(action.text().lower().startswith(mode))

        self.apply_theme()
        self.update_folder_buttons()
        self.show_current_image()

    def show_info_dialog(self, title, message):
        info_dialog = QMessageBox(self)
        info_dialog.setWindowTitle(title)
        info_dialog.setText(message)
        info_dialog.setIcon(QMessageBox.Information)
        self.apply_message_box_style(info_dialog)
        info_dialog.exec()

    def apply_message_box_style(self, message_box):
        t = self._get_ui_tokens()
        message_box.setStyleSheet(build_studio_dialog_qss(t) + """
            QMessageBox QLabel {
                font-size: 13px;
                padding: 4px 2px;
            }
            QMessageBox QPushButton {
                min-width: 84px;
                min-height: 28px;
            }
        """)

    def write_log_to_file(self):
        config_path = get_config_path()
        log_path = os.path.join(os.path.dirname(config_path), "event.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                for line in self.log_buffer:
                    f.write(line + "\n")
            self.log_buffer.clear()
            print(f"[DEBUG] Log written to {log_path}")
        except IOError as e:
            print(f"[DEBUG] Error writing to event.log: {e}")

    def log_message(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self.log_buffer.append(full_message)
        print(full_message)
        self.write_log_to_file()

    def load_custom_folders(self):
        settings = load_settings()
        self.include_subfolders = bool(settings.get("include_subfolders", False))
        if hasattr(self, "include_subfolders_action"):
            self.include_subfolders_action.setChecked(self.include_subfolders)
        raw_names = list(settings.get("folder_names", FolderSettingsDialog.DEFAULT_NAMES[:DEFAULT_FOLDER_SLOTS]))
        raw_paths = list(settings.get("folder_paths", FolderSettingsDialog.DEFAULT_PATHS[:DEFAULT_FOLDER_SLOTS]))
        slot_count = clamp_folder_slots(settings.get("folder_slot_count", len(raw_names) or DEFAULT_FOLDER_SLOTS))
        self.folder_slot_count = slot_count
        self.folder_names = [
            (raw_names[i] if i < len(raw_names) and raw_names[i] else FolderSettingsDialog.DEFAULT_NAMES[i])
            for i in range(slot_count)
        ]
        self.folder_paths = [
            (raw_paths[i] if i < len(raw_paths) and raw_paths[i] else FolderSettingsDialog.DEFAULT_PATHS[i])
            for i in range(slot_count)
        ]
        print(f"[DEBUG] Loaded folder_names ({slot_count} slots): {self.folder_names}")
        print(f"[DEBUG] Loaded folder_paths ({slot_count} slots): {self.folder_paths}")

    def clear_recent_folders(self):
        self.recent_folders.clear()
        self.save_recent_folders()
        self.update_recent_folders_menu()

    def update_folder_buttons(self):
        while self.folder_layout.count():
            item = self.folder_layout.takeAt(0)
            w_btn = item.widget()
            if w_btn:
                w_btn.hide()
                w_btn.deleteLater()

        self.folder_buttons = []
        self._last_folder_wrap_cols = None
        t = self._get_ui_tokens()

        slot_accents = [
            "#8b5cf6", "#10b981", "#f59e0b", "#38bdf8", "#f43f5e",
            "#6366f1", "#14b8a6", "#fb7185", "#94a3b8",
        ]

        slot_count = len(self.folder_names)
        compact_h = self.height() < 620
        pad_h = 6 if slot_count >= 7 else 12
        font_sz = "11px" if slot_count >= 8 else "12px"
        icon_sz = 14 if slot_count >= 7 else 15
        min_btn_h = 34 if compact_h else 42

        for i, (label, path) in enumerate(zip(self.folder_names, self.folder_paths)):
            key_num = i + 1
            accent = slot_accents[i % len(slot_accents)]
            icon_col = accent if t["is_dark"] else self.darken_color(accent, factor=0.72)

            btn = QPushButton(f"[{key_num}] {label}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(make_vector_icon("folder", icon_col, icon_sz))
            btn.setIconSize(QSize(icon_sz, icon_sz))
            btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            btn.setMinimumWidth(52)
            btn.setToolTip(
                f"Move to {label} ({path})\n"
                f"Shortcut: Press {key_num} • Hold click or key {key_num} for Rapid Move"
            )

            if t["is_dark"]:
                bg_rgba = _hex_rgba(accent, 34)
                hover_rgba = _hex_rgba(accent, 62)
                press_rgba = _hex_rgba(accent, 88)
                border_rgba = _hex_rgba(accent, 98)
                border_hover = _hex_rgba(accent, 185)
            else:
                bg_rgba = _hex_rgba(accent, 22)
                hover_rgba = _hex_rgba(accent, 44)
                press_rgba = _hex_rgba(accent, 64)
                border_rgba = _hex_rgba(accent, 95)
                border_hover = _hex_rgba(accent, 175)

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_rgba};
                    color: {t["text"]};
                    border: 1px solid {border_rgba};
                    padding: 6px {pad_h}px;
                    font-size: {font_sz};
                    font-weight: 600;
                    border-radius: 10px;
                    min-height: {min_btn_h}px;
                }}
                QPushButton:hover {{
                    background-color: {hover_rgba};
                    border-color: {border_hover};
                }}
                QPushButton:pressed {{
                    background-color: {press_rgba};
                }}
            """)
            btn.clicked.connect(lambda _, p=path: self.move_to_custom_folder(p))
            self.folder_buttons.append(btn)

        self._relayout_folder_grid(force=True)
        self._sync_minimum_window_size()
        for btn in self.folder_buttons:
            btn.installEventFilter(self)
        if hasattr(self, "image_label"):
            self.image_label.installEventFilter(self)

    def _sync_minimum_window_size(self):
        """Jaga batas minimum jendela agar seluruh komponen selalu utuh, terbaca, dan tidak tumpang tindih."""
        if not hasattr(self, "folder_buttons"):
            return
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRectF(0, 0, 1280, 720).toRect()
        slot_count = len(self.folder_buttons) or 5
        rows = 2 if slot_count >= 6 and self.width() < 980 else 1
        req_min_w = 780 if slot_count <= 5 else 800
        req_min_h = 580 if rows == 1 else 620
        min_w = min(req_min_w, max(680, avail.width() - 32))
        min_h = min(req_min_h, max(500, avail.height() - 48))
        if self.minimumWidth() != min_w or self.minimumHeight() != min_h:
            self.setMinimumSize(min_w, min_h)

    def _target_folder_columns(self, count: int) -> int:
        if count <= 0:
            return 1
        w = max(680, self.width())
        if (count >= 8 and w < 980) or (count >= 6 and w < 860):
            return (count + 1) // 2
        return count

    def _relayout_folder_grid(self, force: bool = False):
        btns = getattr(self, "folder_buttons", None)
        if not btns:
            return
        cols = self._target_folder_columns(len(btns))
        if not force and cols == getattr(self, "_last_folder_wrap_cols", None):
            return
        self._last_folder_wrap_cols = cols
        while self.folder_layout.count():
            self.folder_layout.takeAt(0)
        for idx, btn in enumerate(btns):
            row = idx // cols
            col = idx % cols
            self.folder_layout.addWidget(btn, row, col)
        for c in range(10):
            self.folder_layout.setColumnStretch(c, 1 if c < cols else 0)

    def darken_color(self, hex_color, factor=0.8):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _stage_budgets(self):
        """Hitung ruang maks (w, h) viewport utama & preview berikutnya agar presisi di ukuran layar apa pun."""
        next_visible = True
        if hasattr(self, "main_viewport") and self.main_viewport.width() > 60 and self.main_viewport.height() > 60:
            vp_w = max(240, self.main_viewport.width() - 16)
            vp_h = max(200, self.main_viewport.height() - 18)
        else:
            vp_w = max(260, int((self.width() - 60) * 0.68))
            vp_h = max(220, self.height() - 250)

        if hasattr(self, "next_viewport") and self.next_viewport.width() > 40 and self.next_viewport.height() > 40:
            nvp_w = max(120, self.next_viewport.width() - 12)
            nvp_h = max(130, self.next_viewport.height() - 14)
        else:
            nvp_w = max(130, min(200, int((self.width() - 60) * 0.24)))
            nvp_h = max(140, min(260, int((self.height() - 250) * 0.65)))
        return vp_w, vp_h, nvp_w, nvp_h, next_visible

    def _update_file_info_bar(self):
        meta = getattr(self, "_current_file_meta", None)
        if not meta:
            return
        filename, meta_plain, moved_folder, new_path = meta
        t = self._get_ui_tokens()
        f_calc = self.file_info_label.font()
        f_calc.setPixelSize(12)
        f_calc.setBold(True)
        fm = QFontMetrics(f_calc)
        # Hitung lebar bar info langsung dari lebar jendela agar selalu presisi saat resize live
        bar_w = max(280, self.width() - 28 - 8 - 88 - 6)
        suffix_plain = f" ({meta_plain})" if meta_plain else ""
        moved_plain = f" · moved to {moved_folder}" if moved_folder is not None else ""
        reserved_w = fm.horizontalAdvance(suffix_plain + moved_plain) + 46
        max_name_w = max(80, bar_w - reserved_w)
        display_name = fm.elidedText(filename, Qt.ElideMiddle, max_name_w)
        meta_html = (
            f" <span style='color: {t['text_muted']};'>({meta_plain})</span>"
            if meta_plain else ""
        )
        moved_html = (
            f" <span style='color: #10b981; font-weight: 600;'>· moved to {moved_folder}</span>"
            if moved_folder is not None else ""
        )
        self.file_info_label.setText(f"<b>{display_name}</b>{meta_html}{moved_html}")
        self.file_info_label.setToolTip(f"{filename}\n{new_path}")

    def _relayout_stage_previews(self):
        """Sesuaikan ukuran kartu preview utama, UP NEXT, & kapsul media saat jendela diubah ukurannya."""
        if not hasattr(self, "main_viewport"):
            return
        vp_w, vp_h, nvp_w, nvp_h, next_visible = self._stage_budgets()
        if hasattr(self, "next_stage_box"):
            self.next_stage_box.setVisible(next_visible)

        main_pix = getattr(self, "_current_main_pixmap", None)
        if main_pix is not None and not main_pix.isNull():
            fitted = _fit_pixmap_box(main_pix, min(720, vp_w), min(560, vp_h))
            target_size = fitted.size()
            self._main_video_target_size = target_size
            self.image_label.setFixedSize(target_size)
            if self.current_movie is not None:
                self.current_movie.setScaledSize(target_size)
            elif len(self._main_anim_frames) > 1 and not self._main_video_using_qtmm:
                cur_pix = self._main_anim_frames[self._main_anim_index][0]
                if not cur_pix.isNull():
                    self.image_label.setPixmap(cur_pix.scaled(target_size, Qt.KeepAspectRatio, Qt.FastTransformation))
            elif not self._main_video_using_qtmm:
                self.image_label.setPixmap(fitted)
            self._reposition_video_hud(target_size)
        else:
            empty_w = max(240, min(460, vp_w))
            empty_h = max(175, min(460, vp_h))
            self.image_label.setFixedSize(empty_w, empty_h)
            if not self.image_files and not self.filtered_files:
                self.image_label.setText(self.get_empty_state_text(compact=(empty_h < 350 or empty_w < 340)))
        self.main_viewport.center_child()

        if next_visible:
            next_pix = getattr(self, "_current_next_pixmap", None)
            if next_pix is not None and not next_pix.isNull():
                resized_next = resize_next_preview(next_pix, max_width=min(200, nvp_w), max_height=min(260, nvp_h))
                self.next_image_label.setPixmap(resized_next)
                self.next_image_label.setFixedSize(resized_next.size())
            else:
                self.next_image_label.setFixedSize(min(210, nvp_w), min(260, nvp_h))
            self.next_viewport.center_child()

    def _on_stage_viewport_resized(self):
        self._relayout_stage_previews()

    def update_button_widths(self):
        """Pertahankan proporsi minimum Filter/Undo/Skip agar sejajar sempurna di setiap resolusi."""
        window_width = max(560, self.width())
        filter_min = max(100, min(200, int(window_width * 0.16)))
        self.filter_combo.setMinimumWidth(filter_min)
        self.filter_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for btn in [self.undo_btn, self.skip_btn]:
            btn.setMinimumWidth(90)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        self.update_button_widths()
        self._relayout_folder_grid()
        self._sync_minimum_window_size()
        self._update_file_info_bar()
        self._relayout_stage_previews()
        if hasattr(self, 'notification_label') and self.notification_label.isVisible():
            self.position_notification()

    def set_modern_button_style(self, button):
        t = self._get_ui_tokens()
        if isinstance(button, QComboBox):
            button.setMaxVisibleItems(10)
            button.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            button.setStyleSheet(f"""
                QComboBox {{
                    background-color: {t["surface"]};
                    color: {t["text"]};
                    border: 1px solid {t["border"]};
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 9px;
                    min-height: 26px;
                    combobox-popup: 0;
                }}
                QComboBox:hover {{
                    background-color: {t["surface_hover"]};
                    border-color: {t["border_strong"]};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 24px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {t["menu_bg"]};
                    color: {t["text"]};
                    border: 1px solid {t["border_strong"]};
                    border-radius: 8px;
                    selection-background-color: {t["surface_hover"]};
                    selection-color: {t["text"]};
                    padding: 4px;
                    outline: 0;
                }}
                QComboBox QAbstractItemView::item {{
                    min-height: 26px;
                    padding: 4px 10px;
                    border-radius: 5px;
                }}
                QComboBox QScrollBar:vertical {{
                    background: transparent;
                    width: 8px;
                    margin: 2px 0;
                }}
                QComboBox QScrollBar::handle:vertical {{
                    background: {t["border_strong"]};
                    min-height: 24px;
                    border-radius: 4px;
                }}
                QComboBox QScrollBar::add-line:vertical, QComboBox QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)
            return

        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
                border-radius: 9px;
                min-height: 26px;
            }}
            QPushButton:hover {{
                background-color: {t["surface_hover"]};
                border-color: {t["border_strong"]};
            }}
            QPushButton:pressed {{ background-color: {t["surface_pressed"]}; }}
        """)

    def open_settings(self):
        dialog = FolderSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.load_custom_folders()
            self.update_folder_buttons()
            self.show_current_image()

    def open_rapid_move_settings(self):
        dialog = RapidMoveSettingsDialog(self)
        dialog.exec()
        
    def import_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path:
            return

        self.import_folder_common(folder_path)

    def show_loading(self, show=True):
        if show:
            t = self._get_ui_tokens()
            bg_rgba = "rgba(18, 20, 27, 238)" if t["is_dark"] else "rgba(255, 255, 255, 244)"
            self.loading_label.setAlignment(Qt.AlignCenter)
            self.loading_label.setStyleSheet(f"""
                font-size: 13px;
                font-weight: 700;
                color: {t["text"]};
                background-color: {bg_rgba};
                border: 1px solid {t["border_strong"]};
                border-radius: 12px;
                padding: 18px 22px;
            """)
            window_rect = self.geometry()
            x = window_rect.x() + (window_rect.width() - self.loading_widget.width()) // 2
            y = window_rect.y() + (window_rect.height() - self.loading_widget.height()) // 2
            self.loading_widget.move(x, y)
            self.loading_widget.show()
            self.loading_widget.raise_()
            QApplication.processEvents()
        else:
            self.loading_widget.hide()

    def get_new_path_from_history(self, path):
        normalized_path = os.path.normcase(os.path.normpath(path))
        return self.history_cache.get(normalized_path, None)

    def show_current_image(self, files=None):
        if self.defer_ui_updates:
            return  # Skip UI update during rapid operations

        self.position_stack.setCurrentIndex(0)
        if files is None:
            files = self.filtered_files
        self.stop_current_movie()
        vp_w, vp_h, nvp_w, nvp_h, next_visible = self._stage_budgets()
        if hasattr(self, "next_stage_box"):
            self.next_stage_box.setVisible(next_visible)

        if not files:
            for child in self.image_label.findChildren(QLabel):
                child.deleteLater()
            self._current_main_pixmap = None
            self._current_next_pixmap = None
            self._current_file_meta = None
            empty_w = max(240, min(460, vp_w))
            empty_h = max(175, min(460, vp_h))
            if self.image_files:
                self.image_label.setText("No images match the filter.")
            else:
                self.image_label.setText(self.get_empty_state_text(compact=(empty_h < 350 or empty_w < 340)))
            self.next_image_label.setText("No upcoming\nmedia")
            self.file_info_label.setText("No image loaded.")
            self.position_info_label.setText("0 / 0")
            self.image_label.setFixedSize(empty_w, empty_h)
            self.next_image_label.setFixedSize(min(210, nvp_w), min(260, nvp_h))
            self.main_viewport.center_child()
            if next_visible:
                self.next_viewport.center_child()
            return

        if self.current_index >= len(files):
            self.current_index = 0
            if not files:
                return

        path = files[self.current_index]
        filename = os.path.basename(path)
        folder_name = self.get_folder_name_from_history(path)
        new_path = self.get_new_path_from_history(path) or path
        is_moved = folder_name is not None

        parts = []
        orig_w, orig_h, file_size, fmt_bytes, frame_count = 0, 0, 0, b"", 1
        video_duration = 0.0
        is_video = is_video_file(new_path)
        file_exists = os.path.exists(new_path)
        if file_exists:
            if is_video:
                orig_w, orig_h, file_size, _fps, frame_count, video_duration = self.pixmap_cache.get_video_metadata(new_path)
                fmt_bytes = os.path.splitext(new_path)[1].lstrip(".").lower().encode("ascii", "ignore")
            else:
                orig_w, orig_h, file_size, fmt_bytes, frame_count = self.pixmap_cache.get_metadata(new_path)
            if orig_w > 0 and orig_h > 0:
                parts.append(f"{orig_w}×{orig_h}")
            if is_video and video_duration > 0:
                parts.append(f"VIDEO {format_duration(video_duration)}")
            elif frame_count and frame_count > 1:
                parts.append(f"{frame_count} frames")
            if file_size > 0:
                parts.append(format_file_size(file_size))
            norm_src_cur = os.path.normcase(os.path.normpath(path))
            if norm_src_cur in self.duplicate_group_lookup:
                g_idx, g_size = self.duplicate_group_lookup[norm_src_cur]
                parts.append(f"DUP #{g_idx} ({g_size} similar)")

        meta_plain = " • ".join(parts) if parts else ""
        self._current_file_meta = (filename, meta_plain, folder_name, new_path)
        self._update_file_info_bar()

        current_pos = self.current_index + 1
        total_files = len(files)
        self.position_info_label.setText(f"{current_pos} / {total_files}")

        for child in self.image_label.findChildren(QLabel):
            child.deleteLater()

        self._current_main_pixmap = None
        if file_exists:
            pixmap = self.pixmap_cache.get_pixmap(new_path, 720, 500)
            if not pixmap.isNull():
                self._current_main_pixmap = pixmap
                resized_pixmap = _fit_pixmap_box(pixmap, min(720, vp_w), min(560, vp_h))
                target_size = resized_pixmap.size()
                self._main_video_target_size = target_size
                self.image_label.setFixedSize(target_size)
                # Putar animasi GIF/WebP/APNG/AVIF atau Video dari buffer/frame memori agar tidak mengunci file di Windows.
                # Saat Rapid Move berlangsung, lewati ekstraksi multi-frame & audio agar kecepatan pemindahan maksimal.
                started_anim = False
                if not self.is_rapid_moving:
                    if is_video:
                        # Keyframe pertama sudah siap; tunda start QMediaPlayer+QAudioOutput+QVideoSink 75ms
                        self._video_decode_path = new_path
                        self._video_decode_timer.start()
                    elif frame_count and frame_count > 1 and file_size <= 50 * 1024 * 1024:
                        if fmt_bytes in (b"gif", b"webp"):
                            try:
                                with open(new_path, "rb") as f:
                                    raw_bytes = f.read()
                                self._movie_bytes = QByteArray(raw_bytes)
                                self._movie_buffer = QBuffer()
                                self._movie_buffer.setData(self._movie_bytes)
                                self._movie_buffer.open(QIODevice.ReadOnly)
                                movie = QMovie(self._movie_buffer, QByteArray(fmt_bytes), self)
                                movie.setScaledSize(target_size)
                                if movie.isValid():
                                    self.current_movie = movie
                                    self.image_label.setMovie(movie)
                                    movie.start()
                                    started_anim = True
                                else:
                                    self.stop_current_movie()
                            except OSError:
                                self.stop_current_movie()
                        if not started_anim:
                            raw_frames = self.pixmap_cache.get_animation_frames(new_path, 720, 500, max_frames=60)
                            if len(raw_frames) > 1:
                                self._main_anim_frames = [
                                    (fpix, fdelay) for fpix, fdelay in raw_frames if not fpix.isNull()
                                ]
                                if len(self._main_anim_frames) > 1:
                                    self._main_anim_index = 0
                                    self.image_label.setPixmap(_fit_pixmap_box(self._main_anim_frames[0][0], target_size.width(), target_size.height()))
                                    self._main_anim_timer.start(max(20, int(self._main_anim_frames[0][1])))
                                    started_anim = True
                if not started_anim:
                    self.image_label.setPixmap(resized_pixmap)
                if is_video and self.is_rapid_moving:
                    vbadge = QLabel(self.image_label)
                    dur_str = format_duration(video_duration) if video_duration > 0 else "VIDEO"
                    vbadge.setText(f"▶ {dur_str}")
                    vbadge.setStyleSheet("""
                        background-color: rgba(14, 16, 22, 205);
                        color: #f0f2f5;
                        border: 1px solid rgba(255, 255, 255, 40);
                        font-weight: 600;
                        font-size: 11px;
                        padding: 4px 8px;
                        border-radius: 6px;
                    """)
                    vbadge.setAlignment(Qt.AlignCenter)
                    vbadge.adjustSize()
                    bw = max(64, vbadge.width() + 10)
                    bh = 24
                    vbadge.setGeometry(target_size.width() - bw - 10, target_size.height() - bh - 10, bw, bh)
                    vbadge.show()
                    vbadge.raise_()
                if not self.is_rapid_moving and (is_video or started_anim):
                    self._build_video_controls(target_size, is_video=is_video, duration_s=video_duration)
                if is_moved:
                    watermark = QLabel(self.image_label)
                    watermark.setText("MOVED")
                    watermark.setStyleSheet("""
                        background-color: rgba(220, 38, 38, 210);
                        color: #ffffff;
                        border: 1px solid rgba(255, 255, 255, 55);
                        font-weight: 700;
                        font-size: 11px;
                        letter-spacing: 1px;
                        padding: 4px 10px;
                        border-radius: 7px;
                    """)
                    watermark.setAlignment(Qt.AlignCenter)
                    watermark.setGeometry(10, 10, 88, 28)
                    watermark.show()
                    watermark.raise_()
            else:
                self.image_label.setText(
                    "<div style='padding:16px; color:#f59e0b; font-weight:600;'>Failed to load media.</div>"
                )
                self.image_label.setAlignment(Qt.AlignCenter)
                self.image_label.setFixedSize(max(240, min(460, vp_w)), max(175, min(460, vp_h)))
        else:
            msg = (
                f"<div style='padding:16px;'>File moved to:<br>"
                f"<span style='color:#10b981; font-weight:700;'>{folder_name}</span></div>"
                if folder_name else "<div style='padding:16px; color:#9aa1b2;'>File not found</div>"
            )
            self.image_label.setText(msg)
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setFixedSize(max(240, min(460, vp_w)), max(175, min(460, vp_h)))
        self.main_viewport.center_child()

        self._current_next_pixmap = None
        next_index = self.find_valid_next_index(self.current_index, files)
        if next_index is not None:
            next_path = files[next_index]
            new_next_path = self.get_new_path_from_history(next_path) or next_path
            if os.path.exists(new_next_path):
                next_pixmap = self.pixmap_cache.get_pixmap(new_next_path, 200, 260)
                if not next_pixmap.isNull():
                    self._current_next_pixmap = next_pixmap
                    resized_next = resize_next_preview(next_pixmap, max_width=min(200, nvp_w), max_height=min(260, nvp_h))
                    self.next_image_label.setPixmap(resized_next)
                    self.next_image_label.setFixedSize(resized_next.size())
                else:
                    self.next_image_label.setText("No upcoming\nmedia")
                    self.next_image_label.setFixedSize(min(210, nvp_w), min(260, nvp_h))
            else:
                self.next_image_label.setText("No upcoming\nmedia")
                self.next_image_label.setFixedSize(min(210, nvp_w), min(260, nvp_h))
        else:
            self.next_image_label.setText("No upcoming\nmedia")
            self.next_image_label.setFixedSize(min(210, nvp_w), min(260, nvp_h))
        if next_visible:
            self.next_viewport.center_child()

        # Jadwalkan pre-fetch cerdas di waktu idle (12ms) untuk gambar sekitar (prev, next, next+1)
        if hasattr(self, "_prefetch_timer"):
            self._prefetch_timer.start()

    def _prefetch_neighbor_images(self):
        """Pre-decode gambar & video tetangga ke dalam LRU cache saat idle agar navigasi <- / -> & Rapid Move 0 ms."""
        files = self.filtered_files
        if not files or self.defer_ui_updates:
            return
        total = len(files)
        cur = self.current_index
        # Prioritas: next (+1), next (+2), prev (-1), next (+3)
        for offset in (1, 2, -1, 3):
            idx = cur + offset
            if 0 <= idx < total:
                p = files[idx]
                actual = self.get_new_path_from_history(p) or p
                if os.path.exists(actual):
                    if is_video_file(actual):
                        self.pixmap_cache.get_video_metadata(actual)
                    else:
                        self.pixmap_cache.get_metadata(actual)
                    self.pixmap_cache.get_pixmap(actual, 720, 500)
                    if offset in (1, 2):
                        self.pixmap_cache.get_pixmap(actual, 200, 260)

    def apply_info_style(self, label):
        t = self._get_ui_tokens()
        label.setStyleSheet(f"""
            background-color: {t["card_bg"]};
            border: 1px solid {t["border_strong"]};
            border-radius: 10px;
            color: {t["text"]};
            padding: 12px;
        """)

    def get_folder_name_from_history(self, path):
        normalized_path = os.path.normcase(os.path.normpath(path))
        dest_path = self.history_cache.get(normalized_path)
        if not dest_path:
            return None
        dest_folder = os.path.dirname(dest_path)
        norm_dest_folder = os.path.normcase(os.path.normpath(dest_folder))
        for i, folder_path in enumerate(self.folder_paths):
            norm_folder_path = os.path.normcase(os.path.normpath(folder_path))
            if norm_dest_folder.startswith(norm_folder_path):
                return self.folder_names[i]
        return os.path.basename(os.path.normpath(dest_folder))

    def find_valid_next_index(self, start_index, files=None):
        if files is None:
            files = self.filtered_files
        for i in range(start_index + 1, len(files)):
            path = files[i]
            new_path = self.get_new_path_from_history(path) or path
            if os.path.exists(new_path):
                return i
        return None

    def find_valid_previous_index(self, start_index, files=None):
        if files is None:
            files = self.filtered_files
        for i in range(start_index - 1, -1, -1):
            path = files[i]
            # Check if file exists in original or new location
            if os.path.exists(path) or self.get_new_path_from_history(path):
                return i
        return None

    def show_previous(self):
        valid_index = self.find_valid_previous_index(self.current_index, self.filtered_files)
        if valid_index is not None:
            self.nav_history.append(self.current_index)
            self.current_index = valid_index
            self.show_current_image(self.filtered_files)
        else:
            self.show_notification("No valid previous image.")

    def show_next(self):
        valid_index = self.find_valid_next_index(self.current_index, self.filtered_files)
        if valid_index is not None:
            self.nav_history.append(self.current_index)
            self.current_index = valid_index
            self.show_current_image(self.filtered_files)
        else:
            self.show_notification("No valid next image.")

    def show_first_image(self):
        if not self.filtered_files:
            return
        idx = self.find_valid_next_index(-1, self.filtered_files)
        if idx is not None and idx != self.current_index:
            self.nav_history.append(self.current_index)
            self.current_index = idx
            self.show_current_image(self.filtered_files)

    def show_last_image(self):
        if not self.filtered_files:
            return
        idx = self.find_valid_previous_index(len(self.filtered_files), self.filtered_files)
        if idx is not None and idx != self.current_index:
            self.nav_history.append(self.current_index)
            self.current_index = idx
            self.show_current_image(self.filtered_files)

    def jump_to_image_dialog(self):
        if not self.filtered_files:
            self.show_notification("No images loaded.")
            return
        t = self._get_ui_tokens()
        dlg = QDialog(self)
        dlg.setWindowTitle("Jump to Image")
        dlg.setMinimumWidth(330)
        dlg.setStyleSheet(build_studio_dialog_qss(t))
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        hdr = QLabel("Jump to Media Index")
        hdr.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {t['text']};")
        lay.addWidget(hdr)
        lbl = QLabel(f"Enter media number (1 – {len(self.filtered_files):,}):")
        lbl.setStyleSheet(f"font-size: 12px; color: {t['text_muted']};")
        lay.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(1, len(self.filtered_files))
        spin.setValue(self.current_index + 1)
        spin.setFixedHeight(34)
        lay.addWidget(spin)
        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dlg.reject)
        go_btn = QPushButton("Jump")
        go_btn.setObjectName("primaryBtn")
        go_btn.setCursor(Qt.PointingHandCursor)
        go_btn.setIcon(make_vector_icon("jump", "#ffffff", 14))
        go_btn.setIconSize(QSize(14, 14))
        go_btn.setDefault(True)
        go_btn.clicked.connect(dlg.accept)
        btns.addWidget(cancel_btn)
        btns.addWidget(go_btn)
        lay.addLayout(btns)
        if dlg.exec() == QDialog.Accepted:
            target_idx = spin.value() - 1
            if 0 <= target_idx < len(self.filtered_files):
                self.nav_history.append(self.current_index)
                self.current_index = target_idx
                self.show_current_image(self.filtered_files)

    def toggle_hide_moved(self, checked=None):
        if checked is None:
            self.hide_moved = not self.hide_moved
        else:
            self.hide_moved = bool(checked)
        if hasattr(self, "hide_moved_action"):
            self.hide_moved_action.setChecked(self.hide_moved)
        self.apply_filter()
        state = "hidden" if self.hide_moved else "visible"
        self.show_notification(f"Moved images are now {state}.")

    def toggle_include_subfolders(self, checked=None):
        if checked is None:
            self.include_subfolders = not self.include_subfolders
        else:
            self.include_subfolders = bool(checked)
        if hasattr(self, "include_subfolders_action"):
            self.include_subfolders_action.setChecked(self.include_subfolders)
        settings = load_settings()
        settings["include_subfolders"] = self.include_subfolders
        save_settings(settings)
        mode_str = "enabled" if self.include_subfolders else "disabled"
        if self.current_folder_path and os.path.isdir(self.current_folder_path):
            self.import_folder_common(self.current_folder_path)
            self.show_notification(f"Include Subfolders {mode_str} — rescanning folder...")
        else:
            self.show_notification(f"Include Subfolders {mode_str}.")

    def _resolve_duplicate_scan_targets(self):
        """Kembalikan pasangan (src_path, actual_path) untuk seluruh file aktif."""
        targets = []
        for src in self.image_files:
            actual = self.get_new_path_from_history(src) or src
            if os.path.exists(actual):
                targets.append((src, actual))
        return targets

    def _populate_duplicate_results(self, groups_actual, actual_to_srcs):
        self.duplicate_norms.clear()
        self.duplicate_groups.clear()
        self.duplicate_group_lookup.clear()
        for g_idx, g_actuals in enumerate(groups_actual, start=1):
            src_group = []
            for act in g_actuals:
                norm_act = os.path.normcase(os.path.normpath(act))
                for src in actual_to_srcs.get(norm_act, [act]):
                    src_group.append(src)
            if len(src_group) > 1:
                self.duplicate_groups.append(src_group)
                for s in src_group:
                    ns = os.path.normcase(os.path.normpath(s))
                    self.duplicate_norms.add(ns)
                    self.duplicate_group_lookup[ns] = (g_idx, len(src_group))

    def scan_duplicates(self, max_distance: int = 6, synchronous: bool = False):
        """Pindai gambar/video duplikat atau mirip menggunakan 64-bit Perceptual dHash."""
        self.stop_rapid_move(silent=True)
        if not self.image_files:
            self.show_notification("Import a folder first before scanning for duplicates.")
            return 0
        targets = self._resolve_duplicate_scan_targets()
        if len(targets) < 2:
            self.show_notification("Need at least 2 files to compare duplicates.")
            return 0

        actual_paths = [act for _src, act in targets]
        actual_to_srcs = {}
        for src, act in targets:
            norm_act = os.path.normcase(os.path.normpath(act))
            actual_to_srcs.setdefault(norm_act, []).append(src)

        if synchronous or len(actual_paths) <= 120 or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            _dup_norms, groups, _hmap = find_duplicate_groups(actual_paths, max_distance=max_distance)
            self._populate_duplicate_results(groups, actual_to_srcs)
            dup_count = len(self.duplicate_norms)
            group_count = len(self.duplicate_groups)
            if dup_count > 0:
                idx = self.filter_combo.findText("Duplicates Only")
                if idx >= 0:
                    self.filter_combo.setCurrentIndex(idx)
                self.apply_filter()
                self.show_notification(
                    f"Found {dup_count} duplicate/similar files across {group_count} group{'s' if group_count != 1 else ''}."
                )
            else:
                self.show_notification("No duplicate or visually similar files found.")
            return dup_count

        if self.dup_thread is not None and self.dup_thread.isRunning():
            self.dup_thread.cancel()
            self.dup_thread.wait(1000)

        self.show_loading(True)
        self.loading_label.setText(f"Scanning duplicates...\n0 / {len(actual_paths):,}")
        thread = DuplicateScanThread(actual_paths, max_distance=max_distance, parent=self)
        self._actual_to_srcs_pending = actual_to_srcs
        thread.progress_updated.connect(
            lambda done, tot: self.loading_label.setText(f"Scanning duplicates...\n{done:,} / {tot:,}")
        )
        thread.finished.connect(lambda t=thread: self._on_duplicate_scan_finished(t))
        self.dup_thread = thread
        thread.start()
        return 0

    def _on_duplicate_scan_finished(self, thread):
        if thread is not self.dup_thread:
            thread.deleteLater()
            return
        self.dup_thread = None
        groups = thread.groups
        thread.deleteLater()
        self.show_loading(False)
        actual_to_srcs = getattr(self, "_actual_to_srcs_pending", {})
        self._populate_duplicate_results(groups, actual_to_srcs)
        dup_count = len(self.duplicate_norms)
        group_count = len(self.duplicate_groups)
        if dup_count > 0:
            idx = self.filter_combo.findText("Duplicates Only")
            if idx >= 0:
                self.filter_combo.setCurrentIndex(idx)
            self.apply_filter()
            self.show_notification(
                f"Found {dup_count} duplicate/similar files across {group_count} group{'s' if group_count != 1 else ''}."
            )
        else:
            self.show_notification("No duplicate or visually similar files found.")

    def get_current_actual_path(self):
        if not self.filtered_files or not (0 <= self.current_index < len(self.filtered_files)):
            return None, None
        src_path = self.filtered_files[self.current_index]
        actual_path = self.get_new_path_from_history(src_path) or src_path
        return src_path, actual_path

    def reveal_in_explorer(self):
        _, actual_path = self.get_current_actual_path()
        if not actual_path or not os.path.exists(actual_path):
            self.show_notification("No valid image file to reveal.")
            return
        norm = os.path.normpath(actual_path)
        try:
            subprocess.Popen(["explorer", f"/select,{norm}"])
        except OSError:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(norm)))

    def delete_current_to_recycle_bin(self):
        self.stop_rapid_move(silent=True)
        src_path, actual_path = self.get_current_actual_path()
        if not actual_path or not os.path.exists(actual_path):
            self.show_notification("No image to delete.")
            return
        filename = os.path.basename(actual_path)
        msg = QMessageBox()
        msg.setWindowTitle("Move to Recycle Bin")
        msg.setText(f"Move '{filename}' to the Windows Recycle Bin?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        msg.setIcon(QMessageBox.Question)
        self.apply_message_box_style(msg)
        if msg.exec() != QMessageBox.Yes:
            return
        self.stop_current_movie()
        if not send_to_recycle_bin(actual_path):
            self.show_move_error("Error", f"Could not move '{filename}' to the Recycle Bin.")
            return
        norm_src = os.path.normcase(os.path.normpath(src_path))
        if norm_src in self.history_cache:
            del self.history_cache[norm_src]
            self.history = [(s, d) for s, d in self.history if os.path.normcase(os.path.normpath(s)) != norm_src]
            self.schedule_history_save()
        self.log_message(f"Recycle Bin: {actual_path}")
        if src_path in self.image_files:
            self.image_files.remove(src_path)
        if 0 <= self.current_index < len(self.filtered_files) and self.filtered_files[self.current_index] == src_path:
            self.filtered_files.pop(self.current_index)
        if self.current_index >= len(self.filtered_files):
            self.current_index = max(0, len(self.filtered_files) - 1)
        self.show_current_image(self.filtered_files)
        self.show_notification(f"'{filename}' moved to Recycle Bin.")

    def open_full_preview(self):
        _, actual_path = self.get_current_actual_path()
        if not actual_path or not os.path.exists(actual_path):
            self.show_notification("No image to preview.")
            return
        was_playing = not self._main_paused
        if self._main_audio_player is not None:
            self._main_audio_player.pause()
        if self.current_movie is not None:
            self.current_movie.setPaused(True)
        if self._main_anim_timer.isActive():
            self._main_anim_timer.stop()
        dlg = ImagePreviewDialog(actual_path, self)
        dlg.exec()
        self._refresh_video_controls()
        if was_playing and not self._main_paused:
            if self._main_audio_player is not None:
                self._main_audio_player.play()
            if self.current_movie is not None:
                self.current_movie.setPaused(False)
            if len(self._main_anim_frames) > 1 and not self._main_video_using_qtmm:
                delay = self._main_anim_frames[self._main_anim_index][1]
                self._main_anim_timer.start(max(20, int(delay)))

    def validate_history(self):
        valid_history = []
        seen_src = set()
        for src, dest in self.history:
            norm_src = os.path.normcase(os.path.normpath(src))
            if norm_src not in seen_src:
                valid_history.append((src, dest))
                seen_src.add(norm_src)
        self.history = valid_history
        print(f"[DEBUG] Validated history: {self.history}")

    DEFAULT_FOLDER_PATHS = [f"output/{ch}" for ch in ALL_SLOT_LETTERS]

    @staticmethod
    def _norm_path(path):
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    def is_default_folder_path(self, folder_path):
        """True jika path masih berupa path bawaan (output/A..E) yang belum diatur pengguna."""
        norm = os.path.normcase(os.path.normpath(folder_path))
        return norm in [os.path.normcase(os.path.normpath(p)) for p in self.DEFAULT_FOLDER_PATHS]

    def get_folder_display_name(self, folder_path):
        norm = os.path.normcase(os.path.normpath(folder_path))
        for name, path in zip(self.folder_names, self.folder_paths):
            if os.path.normcase(os.path.normpath(path)) == norm:
                return name
        return os.path.basename(os.path.normpath(folder_path))

    @staticmethod
    def get_unique_destination(dest_folder, filename):
        """Kembalikan path tujuan yang belum dipakai. File yang sudah ada TIDAK PERNAH ditimpa:
        'foto.jpg' -> 'foto (1).jpg' -> 'foto (2).jpg', dst."""
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(dest_folder, filename)
        counter = 1
        while os.path.lexists(candidate):
            candidate = os.path.join(dest_folder, f"{base} ({counter}){ext}")
            counter += 1
        return candidate

    def show_move_error(self, title, text):
        """Hentikan rapid move SEBELUM menampilkan dialog modal agar timer tidak terus berjalan
        dan dialog tidak menumpuk."""
        self.stop_rapid_move(silent=True)
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Critical if title.startswith("Error") else QMessageBox.Warning)
        self.apply_message_box_style(msg)
        msg.exec()

    def move_to_custom_folder(self, folder_path):
        """Pindahkan gambar yang SEDANG DITAMPILKAN ke folder tujuan.
        Mengembalikan True jika file benar-benar dipindahkan, False jika tidak."""
        files = self.filtered_files
        if not files or not (0 <= self.current_index < len(files)):
            self.show_notification("No image to move.")
            return False

        # Sumber selalu diambil dari daftar yang sama dengan yang ditampilkan (filtered_files)
        src_path = files[self.current_index]
        current_dest = self.get_new_path_from_history(src_path)
        if not os.path.exists(src_path) and not (current_dest and os.path.exists(current_dest)):
            self.stop_rapid_move(silent=True)
            self.show_notification("Source file not found.")
            self.show_next()
            return False

        # Folder tujuan masih default -> minta pengguna mengatur folder terlebih dahulu
        if self.is_default_folder_path(folder_path):
            self.stop_rapid_move(silent=True)
            norm_requested = os.path.normcase(os.path.normpath(folder_path))
            folder_index = next(
                (i for i, p in enumerate(self.folder_paths)
                 if os.path.normcase(os.path.normpath(p)) == norm_requested),
                None
            )
            dialog = FolderSettingsDialog(self)
            if dialog.exec() != QDialog.Accepted:
                self.show_notification("Move cancelled. Please set destination folder.")
                return False

            self.load_custom_folders()
            self.update_folder_buttons()

            if folder_index is None or folder_index >= len(self.folder_paths):
                self.show_notification("Destination folder invalid after settings.")
                return False
            # Gunakan path BARU pada slot folder yang sama (bukan path default lama)
            folder_path = self.folder_paths[folder_index]

        dest_folder = (folder_path or "").strip()
        if not dest_folder:
            self.show_move_error("Error", "Destination folder not selected.")
            return False

        folder_name = self.get_folder_display_name(dest_folder)
        source_to_move = current_dest if current_dest and os.path.exists(current_dest) else src_path

        # Sudah berada di folder tujuan -> tidak perlu dipindah
        if self._norm_path(os.path.dirname(source_to_move)) == self._norm_path(dest_folder):
            self.show_notification(f"File already in {folder_name}.")
            return False

        self.defer_ui_updates = True
        try:
            self.stop_current_movie()
            os.makedirs(dest_folder, exist_ok=True)
            filename = os.path.basename(src_path)
            dest_path = self.get_unique_destination(dest_folder, filename)
            renamed = os.path.basename(dest_path) != filename

            shutil.move(source_to_move, dest_path)

            # Update history and cache
            norm_src_path = os.path.normcase(os.path.normpath(src_path))
            if norm_src_path in self.history_cache:
                # Hanya saat file yang sama dipindah lagi: buang entri lamanya (jarang terjadi)
                self.history = [(s, d) for s, d in self.history
                                if os.path.normcase(os.path.normpath(s)) != norm_src_path]
            self.history.append((src_path, dest_path))
            self.history_cache[norm_src_path] = dest_path
            self.schedule_history_save()

            self.log_message(f"Moved: {source_to_move} → {dest_path}")

            current_index_before_move = self.current_index
            if self.hide_moved:
                if 0 <= current_index_before_move < len(self.filtered_files):
                    self.filtered_files.pop(current_index_before_move)
                has_next = len(self.filtered_files) > 0 and current_index_before_move < len(self.filtered_files)
                self.current_index = min(current_index_before_move, len(self.filtered_files) - 1) if self.filtered_files else 0
            else:
                next_index = self.find_valid_next_index(current_index_before_move, self.filtered_files)
                has_next = next_index is not None
                if has_next:
                    self.current_index = next_index
                else:
                    self.current_index = min(current_index_before_move, len(self.filtered_files) - 1) if self.filtered_files else 0

            self.defer_ui_updates = False
            self.nav_history.append(current_index_before_move)
            self.show_current_image(self.filtered_files)

            if renamed:
                self.show_notification(
                    f"Image moved to {folder_name} as \"{os.path.basename(dest_path)}\" (a file with the same name already existed)."
                )
            else:
                self.show_notification(f"Image successfully moved to {folder_name}")

            # Tidak ada gambar berikutnya -> rapid move berhenti otomatis
            if not has_next:
                self.stop_rapid_move(silent=True)
            return True

        except Exception as e:
            self.defer_ui_updates = False
            self.show_move_error("Error", f"Could not move file:\n{str(e)}")
            return False

    def start_rapid_move(self, folder_index, source="mouse"):
        """Mulai mode pindah cepat ke folder tertentu (index 0-3 = A-D)."""
        if self.is_rapid_moving or not self.filtered_files:
            return
        if not (0 <= folder_index < len(self.folder_paths)):
            return

        folder_path = self.folder_paths[folder_index]
        # Folder belum diatur: hanya satu pemindahan (dialog pengaturan akan muncul), TANPA timer.
        if self.is_default_folder_path(folder_path):
            self.move_to_custom_folder(folder_path)
            return

        self.is_rapid_moving = True
        self.rapid_folder_index = folder_index
        self.rapid_source = source
        # Pindahkan gambar pertama segera
        moved = self.move_to_custom_folder(folder_path)
        if not moved or not self.is_rapid_moving:
            self.stop_rapid_move(silent=True)
            return
        self.rapid_timer.start(clamp_rapid_interval(self.rapid_move_interval))

    def rapid_move(self):
        """Dipanggil oleh timer untuk memindahkan gambar berikutnya."""
        if not self.is_rapid_moving or self.rapid_folder_index is None:
            self.stop_rapid_move(silent=True)
            return
        # Pengaman: jika tombol mouse sudah tidak ditekan (event release hilang), hentikan.
        if self.rapid_source == "mouse" and not (QApplication.mouseButtons() & Qt.LeftButton):
            self.stop_rapid_move()
            return
        # Pengaman keyboard: jendela kehilangan fokus (key release tidak akan diterima)
        if self.rapid_source == "key" and not self.isActiveWindow():
            self.stop_rapid_move()
            return
        if not self.filtered_files or self.current_index >= len(self.filtered_files):
            self.stop_rapid_move()
            return
        if not self.move_to_custom_folder(self.folder_paths[self.rapid_folder_index]):
            self.stop_rapid_move(silent=True)

    def stop_rapid_move(self, silent=False):
        """Hentikan mode pindah cepat dan lanjutkan pemutaran animasi/video pada file saat ini."""
        self.rapid_timer.stop()
        if self.is_rapid_moving:
            self.is_rapid_moving = False
            self.rapid_folder_index = None
            self.rapid_source = None
            if not self.defer_ui_updates and self.filtered_files:
                self.show_current_image(self.filtered_files)
            if not silent:
                self.show_notification("Rapid move stopped")

    RAPID_KEYS = (
        Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5,
        Qt.Key_6, Qt.Key_7, Qt.Key_8, Qt.Key_9,
    )

    def _is_rapid_key_event(self, obj, event):
        """Key 1-9 (sesuai jumlah slot aktif) tanpa Ctrl/Alt/Meta, ditujukan ke jendela utama."""
        if event.key() not in self.RAPID_KEYS:
            return False
        idx = event.key() - Qt.Key_1
        if not (0 <= idx < len(self.folder_paths)):
            return False
        blocked = Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier
        if event.modifiers() & blocked:
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        if not (hasattr(obj, "isWidgetType") and obj.isWidgetType()):
            return False
        return obj.window() is self

    def eventFilter(self, obj, event):
        """Tangani tombol keyboard 1-4 dan hold mouse pada tombol folder A-D."""
        etype = event.type()
        if etype in (QEvent.KeyPress, QEvent.KeyRelease) and self._is_rapid_key_event(obj, event):
            if event.isAutoRepeat():
                return True  # abaikan auto-repeat OS; kecepatan diatur timer rapid move
            index = event.key() - Qt.Key_1
            if etype == QEvent.KeyPress:
                self.start_rapid_move(index, source="key")
            else:
                self.stop_rapid_move(silent=True)
            return True
        if etype == QEvent.WindowDeactivate and obj is self:
            self.stop_rapid_move(silent=True)
        if hasattr(self, "image_label") and obj is self.image_label:
            if etype == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                if self.filtered_files:
                    self.open_full_preview()
                    return True
        if obj in self.folder_buttons:
            if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                index = self.folder_buttons.index(obj)
                self.start_rapid_move(index, source="mouse")
                return True
            elif etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.stop_rapid_move()
                return True
        return super().eventFilter(obj, event)

    def undo_action(self):
        if not self.history:
            msg = QMessageBox()
            msg.setWindowTitle("Undo Info")
            msg.setText("No action to undo.")
            msg.setIcon(QMessageBox.Information)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        self.defer_ui_updates = True  # Defer UI updates during undo

        src_path, dest_path = self.history.pop()
        self.schedule_history_save()

        try:
            if not os.path.exists(dest_path):
                raise FileNotFoundError(f"Destination file {dest_path} not found.")
            # Jangan pernah menimpa file lain yang kini berada di lokasi asal
            if os.path.lexists(src_path):
                raise FileExistsError(
                    f"A file already exists at the original location:\n{src_path}\n"
                    "Rename or move it first, then try Undo again."
                )

            os.makedirs(os.path.dirname(src_path) or ".", exist_ok=True)
            shutil.move(dest_path, src_path)
            self.log_message(f"Undo: {dest_path} → {src_path}")

            # Update caches
            norm_src_path = os.path.normcase(os.path.normpath(src_path))
            if norm_src_path in self.history_cache:
                del self.history_cache[norm_src_path]
            if self.hide_moved:
                self.apply_filter()

            # Cari posisi file yang dikembalikan (pencarian string cepat dulu, lalu fallback ternormalisasi)
            try:
                self.current_index = self.filtered_files.index(src_path)
            except ValueError:
                for i, path in enumerate(self.filtered_files):
                    if os.path.normcase(os.path.normpath(path)) == norm_src_path:
                        self.current_index = i
                        break
                else:
                    self.current_index = min(self.current_index, len(self.filtered_files) - 1) if self.filtered_files else 0

            filename = os.path.basename(src_path)

            # Re-enable UI updates and refresh
            self.defer_ui_updates = False
            self.show_current_image(self.filtered_files)
            self.show_notification(f'"{filename}" has been restored to its original location.')
        except Exception as e:
            self.log_message(f"Undo Error: Failed to restore file: {str(e)}")
            msg = QMessageBox()
            msg.setWindowTitle("Undo Error")
            msg.setText(f"Failed to restore file: {str(e)}")
            msg.setIcon(QMessageBox.Critical)
            self.apply_message_box_style(msg)
            msg.exec()
            self.history.append((src_path, dest_path))
            self.schedule_history_save()
            self.defer_ui_updates = False

    def find_next_unmoved_index(self, start_index, files=None):
        """Cari indeks gambar berikutnya yang BELUM dipindahkan (unmoved)."""
        if files is None:
            files = self.filtered_files
        for i in range(start_index + 1, len(files)):
            path = files[i]
            norm_path = os.path.normcase(os.path.normpath(path))
            if norm_path not in self.history_cache and os.path.exists(path):
                return i
        return None

    def skip_image(self):
        """Lompat langsung ke gambar berikutnya yang belum dipindahkan (unmoved)."""
        if not self.filtered_files:
            self.show_notification("No image loaded.")
            return
        next_unmoved = self.find_next_unmoved_index(self.current_index, self.filtered_files)
        if next_unmoved is not None:
            self.nav_history.append(self.current_index)
            self.current_index = next_unmoved
            self.show_current_image(self.filtered_files)
        else:
            self.show_notification("No unmoved images remaining ahead.")

    def export_log(self):
        if self.log_buffer:
            self.write_log_to_file()
        log_path = os.path.join(os.path.dirname(get_config_path()), "event.log")
        log_content = ""
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_content = f.read()
            except IOError:
                log_content = ""
        if not log_content.strip():
            msg = QMessageBox()
            msg.setWindowTitle("Export Log")
            msg.setText("No log to export.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log As",
            "sorter_log.txt",
            "Text Files (*.txt);;All Files (*)",
            options=options
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(log_content)
            msg = QMessageBox()
            msg.setWindowTitle("Export Log")
            msg.setText(f"Log successfully saved as '{file_path}'")
            msg.setIcon(QMessageBox.Information)
            self.apply_message_box_style(msg)
            msg.exec()
        except Exception as e:
            msg = QMessageBox()
            msg.setWindowTitle("Export Log Error")
            msg.setText(f"Failed to save log: {str(e)}")
            msg.setIcon(QMessageBox.Critical)
            self.apply_message_box_style(msg)
            msg.exec()

    def get_empty_state_text(self, compact: bool = False):
        """Teks panduan singkat bergaya Studio Slate saat belum ada media yang dimuat."""
        t = self._get_ui_tokens()
        title_col = t["text"]
        sub_col = t["text_muted"]
        key_col = t["accent"]
        desc_col = t["text"]
        row_bg = t["surface"]

        max_key = max(3, len(self.folder_names)) if getattr(self, "folder_names", None) else 5
        max_let = ALL_SLOT_LETTERS[min(max_key - 1, len(ALL_SLOT_LETTERS) - 1)]
        tbl_w = 240 if compact else 310
        cell_pad = 3 if compact else 6
        font_sz = 11 if compact else 12
        title_sz = 15 if compact else 17
        return (
            f"<div align='center'>"
            f"<p style='font-size:{title_sz}px; font-weight:700; color:{title_col}; margin-bottom:3px;'>No Media Loaded</p>"
            f"<p style='font-size:{font_sz}px; color:{sub_col}; margin-top:0px; margin-bottom:{8 if compact else 14}px;'>"
            f"Drop a folder or press <font face='Consolas' color='{key_col}'><b>Ctrl+O</b></font>"
            f"</p>"
            f"<table align='center' width='{tbl_w}' cellspacing='2' cellpadding='{cell_pad}' style='font-size:{font_sz}px;'>"
            f"<tr bgcolor='{row_bg}'>"
            f"<td align='left' width='42%'><font face='Consolas' color='{key_col}'><b>[1] – [{max_key}]</b></font></td>"
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

    def show_shortcuts_guide(self):
        dialog = ShortcutsGuideDialog(self)
        dialog.exec()

    def show_about(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def export_settings(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Settings",
            "settings_export.json",
            "JSON Files (*.json);;All Files (*)",
            options=options
        )
        if not file_path:
            return

        try:
            settings = load_settings()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            msg = QMessageBox()
            msg.setWindowTitle("Export Settings")
            msg.setText(f"Settings successfully exported to '{file_path}'")
            msg.setIcon(QMessageBox.Information)
            self.apply_message_box_style(msg)
            msg.exec()
        except Exception as e:
            msg = QMessageBox()
            msg.setWindowTitle("Export Settings Error")
            msg.setText(f"Failed to export settings: {str(e)}")
            msg.setIcon(QMessageBox.Critical)
            self.apply_message_box_style(msg)
            msg.exec()

    def import_settings(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Settings",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_settings = json.load(f)

            # Validate data
            required_keys = ["folder_names", "folder_paths", "theme_mode", "recent_folders", "custom_theme"]
            if not all(key in imported_settings for key in required_keys):
                msg = QMessageBox()
                msg.setWindowTitle("Error")
                msg.setText("Settings file is invalid or incomplete.")
                msg.setIcon(QMessageBox.Warning)
                self.apply_message_box_style(msg)
                msg.exec()
                return

            # Save to settings.json
            save_settings(imported_settings)

            # Update UI
            self.load_custom_folders()
            self.load_recent_folders()
            self.theme_mode = imported_settings["theme_mode"]
            self.update_folder_buttons()
            self.update_recent_folders_menu()
            self.apply_theme()
            self.show_current_image()

            msg = QMessageBox()
            msg.setWindowTitle("Import Settings")
            msg.setText("Settings successfully imported.")
            msg.setIcon(QMessageBox.Information)
            self.apply_message_box_style(msg)
            msg.exec()
        except Exception as e:
            msg = QMessageBox()
            msg.setWindowTitle("Import Settings Error")
            msg.setText(f"Failed to import settings: {str(e)}")
            msg.setIcon(QMessageBox.Critical)
            self.apply_message_box_style(msg)
            msg.exec()

    def apply_filter(self):
        selected_ext = self.filter_combo.currentText()
        previous_path = (
            self.filtered_files[self.current_index]
            if not self.defer_ui_updates and 0 <= self.current_index < len(self.filtered_files)
            else None
        )
        self.last_filter = selected_ext

        # Selalu bangun ulang filtered_files dari image_files agar tidak basi saat ganti folder
        if selected_ext == "All Files":
            candidates = list(self.image_files)
        elif selected_ext == "All Videos":
            candidates = [path for path in self.image_files if is_video_file(path)]
        elif selected_ext == "All Images":
            candidates = [path for path in self.image_files if not is_video_file(path)]
        elif selected_ext == "Animated / GIF":
            anim_exts = (".gif", ".webp", ".apng", ".avif")
            candidates = [path for path in self.image_files if path.lower().endswith(anim_exts)]
        elif selected_ext == "Duplicates Only":
            if not self.duplicate_norms and self.image_files and not self.defer_ui_updates:
                targets = self._resolve_duplicate_scan_targets()
                if len(targets) >= 2:
                    actual_paths = [act for _src, act in targets]
                    actual_to_srcs = {}
                    for src, act in targets:
                        norm_act = os.path.normcase(os.path.normpath(act))
                        actual_to_srcs.setdefault(norm_act, []).append(src)
                    _dn, groups, _hm = find_duplicate_groups(actual_paths, max_distance=6)
                    self._populate_duplicate_results(groups, actual_to_srcs)
            candidates = [
                path for path in self.image_files
                if os.path.normcase(os.path.normpath(path)) in self.duplicate_norms
            ]
        else:
            wanted = selected_ext.lower()
            candidates = [path for path in self.image_files if path.lower().endswith(wanted)]

        if self.hide_moved and self.history_cache:
            self.filtered_files = [
                path for path in candidates
                if os.path.normcase(os.path.normpath(path)) not in self.history_cache
            ]
        else:
            self.filtered_files = candidates

        print(f"[DEBUG] filtered_files: {len(self.filtered_files)} items")

        if self.defer_ui_updates:
            return

        if previous_path and previous_path in self.filtered_files:
            self.current_index = self.filtered_files.index(previous_path)
        elif self.filtered_files:
            if self.current_index >= len(self.filtered_files):
                self.current_index = 0
            cur_path = self.filtered_files[self.current_index]
            cur_actual = self.get_new_path_from_history(cur_path) or cur_path
            if not os.path.exists(cur_actual):
                valid_index = self.find_valid_next_index(-1, self.filtered_files)
                if valid_index is not None:
                    self.current_index = valid_index
        else:
            self.current_index = 0

        self.show_current_image(self.filtered_files)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ImageSorterApp()
    window.show()
    sys.exit(app.exec())