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
import subprocess
import ctypes
from ctypes import wintypes

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QWidget, QFileDialog,
    QMessageBox, QMenuBar, QSpacerItem, QSizePolicy, QDialog, QLineEdit,
    QColorDialog, QFrame, QComboBox, QGraphicsDropShadowEffect,
    QProgressBar, QStackedLayout, QScrollArea, QTextEdit,
    QSpinBox, QSlider
)
from PySide6.QtGui import QAction, QImageReader, QIcon, QShortcut, QKeySequence, QDesktopServices, QMovie
from PySide6.QtCore import Qt, QPropertyAnimation, QTimer, QThread, QSize, Signal, QUrl, QEvent, QByteArray, QBuffer, QIODevice

from utils.image_utils import (
    format_file_size,
    load_pixmap,
    read_image_metadata,
    resize_image,
    resize_next_preview,
)

_RESOLVED_CONFIG_DIR = None


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

SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.jfif', '.gif', '.bmp', '.webp',
                              '.tiff', '.tif', '.ico', '.svg', '.heic', '.heif', '.raw', '.psd')
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
    """Ekstensi yang didukung aplikasi DAN bisa dibaca Qt di komputer ini.
    Dicek sekali per ekstensi (bukan sekali per file) agar import ribuan file tetap cepat."""
    global _READABLE_EXTENSIONS
    if _READABLE_EXTENSIONS is None:
        qt_formats = {bytes(f).decode("ascii", "ignore").lower() for f in QImageReader.supportedImageFormats()}
        aliases = {".jpg": "jpeg", ".jpeg": "jpeg", ".jfif": "jpeg", ".tiff": "tiff", ".tif": "tiff", ".heic": "heic", ".heif": "heif"}
        result = set()
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            name = ext.lstrip(".")
            if name in qt_formats or aliases.get(ext, name) in qt_formats:
                result.add(ext)
        _READABLE_EXTENSIONS = frozenset(result)
    return _READABLE_EXTENSIONS


_NATURAL_SPLIT = re.compile(r"(\d+)")


def natural_sort_key(path):
    """Urutan seperti Windows Explorer: IMG_2 sebelum IMG_10."""
    name = os.path.basename(path).lower()
    return [int(part) if part.isdigit() else part for part in _NATURAL_SPLIT.split(name)]


def scan_image_files(folder_path, extensions=None, should_cancel=None, on_progress=None):
    """Satu kali lintasan direktori dengan os.scandir (tanpa subfolder).
    Tidak memakai glob, jadi nama folder dengan [ ] * ? aman."""
    extensions = extensions or readable_image_extensions()
    files = []
    last_report = time.monotonic()
    with os.scandir(folder_path) as entries:
        for entry in entries:
            if should_cancel is not None and should_cancel():
                return None
            name = entry.name
            dot = name.rfind(".")
            if dot <= 0 or name[dot:].lower() not in extensions:
                continue
            try:
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
    files.sort(key=natural_sort_key)
    return files


def load_settings():
    """Load settings from settings.json or return default settings."""
    config_path = get_config_path()
    default_settings = {
        "first_run": True,
        "folder_names": ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"],
        "folder_paths": ["output/A", "output/B", "output/C", "output/D", "output/E"],
        "recent_folders": [],
        "theme_mode": "system",
        "rapid_move_interval": 200,
        "custom_theme": {
            "bg_color": "#121212",
            "text_color": "#FFFFFF",
            "btn_bg": "#2e2e2e",
            "btn_hover": "#444444",
            "label_bg": "#1a1a1a",
            "menu_bg": "#1a1a1a",
            "menu_text": "#FFFFFF",
            "main_border_color": "#00BFFF",
            "next_border_color": "#32CD32",
            "main_shadow": "0 0 10px rgba(0, 191, 255, 0.7)",
            "next_shadow": "0 0 8px rgba(50, 205, 50, 0.5)"
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

def save_settings(settings):
    """Save settings to settings.json."""
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        print(f"[DEBUG] Settings saved to {config_path}")
    except IOError as e:
        print(f"[DEBUG] Error saving settings: {e}")

class UpdateDialog(QDialog):
    def __init__(self, parent=None, current_version="2.0", latest_version=None, release_notes="", download_url=None):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setMinimumWidth(400)
        self.setMaximumHeight(500)
        self.parent = parent

        # Apply theme from parent
        self.apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("Image Sorter Update")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; background-color: transparent;")
        layout.addWidget(title_label)

        # Version Info
        version_layout = QHBoxLayout()
        current_label = QLabel(f"Current Version: {current_version}")
        current_label.setStyleSheet("font-size: 14px; background-color: transparent;")
        version_layout.addWidget(current_label)
        
        latest_label = QLabel(f"Latest Version: {latest_version if latest_version else 'Unknown'}")
        latest_label.setStyleSheet("font-size: 14px; background-color: transparent;")
        version_layout.addWidget(latest_label)
        layout.addLayout(version_layout)

        # Status
        status_text = "You are up to date!" if not latest_version or not self.is_newer_version(current_version, latest_version) else "A new version is available!"
        status_label = QLabel(status_text)
        status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;" if status_text == "You are up to date!" else "font-size: 14px; font-weight: bold; color: #F44336;")
        layout.addWidget(status_label)

        # Release Notes
        notes_label = QLabel("Release Notes:")
        notes_label.setStyleSheet("font-size: 14px; font-weight: bold; background-color: transparent;")
        layout.addWidget(notes_label)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setText(release_notes if release_notes else "No release notes available.")
        self.notes_text.setStyleSheet("font-size: 12px; background-color: #2e2e2e; color: white; border: 1px solid #444;" if self.parent.theme_mode == "dark" else "font-size: 12px; background-color: #f0f0f0; color: black; border: 1px solid #ccc;")
        self.notes_text.setFixedHeight(150)
        layout.addWidget(self.notes_text)

        # Buttons
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download Update")
        self.download_btn.setEnabled(bool(download_url and self.is_newer_version(current_version, latest_version)))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #666;
                color: #aaa;
            }
        """)
        self.download_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
        btn_layout.addWidget(self.download_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def apply_theme(self):
        if self.parent and hasattr(self.parent, 'theme_mode'):
            use_dark = self.parent.theme_mode == "dark" or (self.parent.theme_mode == "system" and self.parent.is_system_dark())
            if use_dark:
                self.setStyleSheet("""
                    QDialog { background-color: #1e1e1e; color: white; }
                    QLabel { color: white; background-color: transparent; border: none; }
                    QPushButton { background-color: #2e2e2e; color: white; }
                    QPushButton:hover { background-color: #444444; }
                """)
            else:
                self.setStyleSheet("""
                    QDialog { background-color: #f9f9f9; color: black; }
                    QLabel { color: black; background-color: transparent; border: none; }
                    QPushButton { background-color: #e0e0e0; color: black; }
                    QPushButton:hover { background-color: #d0d0d0; }
                """)

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
    VERSION = "2.1.2-Stable"
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Image Sorter")
        self.setMinimumWidth(500)
        self.setMaximumHeight(600)
        self.parent = parent

        self.apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title_layout = QHBoxLayout()
        self.logo_label = QLabel()
        self.logo_label.setPixmap(QIcon(resource_path("assets/icons/app_icon.png")).pixmap(64, 64))
        self.logo_label.setStyleSheet("background-color: transparent;")
        title_layout.addWidget(self.logo_label)

        self.title_label = QLabel("Image Sorter")
        self.title_label.setStyleSheet("font-size: 26px; font-weight: bold; margin-left: 10px; background-color: transparent;")
        self.version_label = QLabel(f"Version {self.VERSION}")
        self.version_label.setStyleSheet("font-size: 14px; margin-left: 10px; color: #aaa; background-color: transparent;")

        title_info = QVBoxLayout()
        title_info.addWidget(self.title_label)
        title_info.addWidget(self.version_label)
        title_layout.addLayout(title_info)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        desc_text = (
            "Image Sorter is a sleek and intuitive application designed to help you organize your images effortlessly into custom folders with a modern interface."
        )
        self.desc_label = QLabel(desc_text)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("""
            font-size: 14px;
            margin-top: 10px;
            background-color: transparent;
            border: none;
            text-align: justify;
        """)
        layout.addWidget(self.desc_label)

        features_title = QLabel("Key Features:")
        features_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 15px; background-color: transparent;")
        layout.addWidget(features_title)

        features_list = [
            "Effortless image sorting into custom folders",
            "Undo functionality for easy corrections",
            "Responsive image previews with smooth transitions",
            "Customizable themes for a personalized experience",
            "Recent folders history for quick access"
        ]

        for feature in features_list:
            item = QLabel(f"• {feature}")
            item.setStyleSheet("""
                font-size: 14px;
                color: #aaa;
                padding-left: 10px;
                background-color: transparent;
                border: none;
            """)
            layout.addWidget(item)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #555; margin: 15px 0;")
        layout.addWidget(separator)

        social_layout = QHBoxLayout()
        social_layout.setSpacing(15)
        social_layout.setAlignment(Qt.AlignCenter)

        telegram_btn = QPushButton()
        telegram_btn.setIcon(QIcon(resource_path("assets/icons/telegram.png")))
        telegram_btn.setIconSize(QSize(32, 32))
        telegram_btn.setText("Thea")
        telegram_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00BFFF;
                font-size: 14px;
                font-weight: bold;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(0, 191, 255, 0.1);
                color: #40C4FF;
                transform: scale(1.05);
            }
        """)
        telegram_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/ThuandMuda")))
        telegram_btn.setCursor(Qt.PointingHandCursor)
        social_layout.addWidget(telegram_btn)

        github_btn = QPushButton()
        github_btn.setIcon(QIcon(resource_path("assets/icons/github.png")))
        github_btn.setIconSize(QSize(32, 32))
        github_btn.setText("Zy0x")
        github_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #32CD32;
                font-size: 14px;
                font-weight: bold;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(50, 205, 50, 0.1);
                color: #66FF66;
                transform: scale(1.05);
            }
        """)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Zy0x")))
        github_btn.setCursor(Qt.PointingHandCursor)
        social_layout.addWidget(github_btn)

        social_layout.addStretch()
        layout.addLayout(social_layout)

        btn_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setFixedHeight(36)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 8px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        ok_button.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_button)
        layout.addLayout(btn_layout)

    def apply_theme(self):
        if self.parent and hasattr(self.parent, 'theme_mode'):
            use_dark = self.parent.theme_mode == "dark" or (self.parent.theme_mode == "system" and self.parent.is_system_dark())
            if use_dark:
                self.setStyleSheet("""
                    QDialog { background-color: #1e1e1e; color: white; }
                    QLabel { color: white; background-color: transparent; border: none; }
                    QPushButton { background-color: #2e2e2e; color: white; }
                    QPushButton:hover { background-color: #444444; }
                    QFrame { background-color: #555; }
                """)
            else:
                self.setStyleSheet("""
                    QDialog { background-color: #f9f9f9; color: black; }
                    QLabel { color: black; background-color: transparent; border: none; }
                    QPushButton { background-color: #e0e0e0; color: black; }
                    QPushButton:hover { background-color: #d0d0d0; }
                    QFrame { background-color: #ccc; }
                """)


class ShortcutsGuideDialog(QDialog):
    """Dialog panduan penggunaan & daftar lengkap shortcut keyboard/mouse."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts & Quick Guide")
        self.setMinimumSize(540, 520)
        self.parent = parent

        is_dark = False
        if self.parent and hasattr(self.parent, "theme_mode"):
            is_dark = (
                self.parent.theme_mode in ("dark", "custom")
                or (self.parent.theme_mode == "system" and self.parent.is_system_dark())
            )

        bg = "#1e1e1e" if is_dark else "#ffffff"
        card_bg = "#282828" if is_dark else "#f4f6f8"
        text = "#ffffff" if is_dark else "#1f2328"
        muted = "#b0b8c1" if is_dark else "#57606a"
        accent = "#00BFFF" if is_dark else "#0969da"
        border = "#3a3a3a" if is_dark else "#d8dee4"
        key_bg = "#121212" if is_dark else "#eaeef2"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {text}; }}
            QLabel {{ color: {text}; background: transparent; border: none; }}
            QScrollArea {{ background-color: {bg}; border: none; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        header = QLabel("⌨️ Keyboard Shortcuts & Quick Guide")
        header.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {text};")
        main_layout.addWidget(header)

        subtitle = QLabel("Everything you need to sort images quickly with keyboard or mouse.")
        subtitle.setStyleSheet(f"font-size: 13px; color: {muted}; margin-bottom: 4px;")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setStyleSheet(f"background-color: {bg};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(12)

        guide_html = f"""
        <div style="font-size:13px; line-height:1.55; color:{text};">
          <div style="background-color:{card_bg}; border:1px solid {border}; border-radius:10px; padding:12px 14px; margin-bottom:10px;">
            <div style="font-size:15px; font-weight:bold; color:{accent}; margin-bottom:6px;">🚀 Quick Workflow (3 Steps)</div>
            <ol style="margin:4px 0 0 18px; padding:0;">
              <li><b>Set Destination Folders:</b> Open <i>Settings → Folder Settings</i> (or click any folder button on first use) to set paths for Folders A–E.</li>
              <li><b>Import Images:</b> Drag &amp; drop a folder or image onto the window, or press <span style="background:{key_bg}; padding:2px 6px; border-radius:4px; font-family:Consolas,monospace;">Ctrl+O</span>.</li>
              <li><b>Sort Fast:</b> Press <span style="background:{key_bg}; padding:2px 6px; border-radius:4px; font-family:Consolas,monospace;">1</span>–<span style="background:{key_bg}; padding:2px 6px; border-radius:4px; font-family:Consolas,monospace;">5</span> to move 1 image, or hold <span style="background:{key_bg}; padding:2px 6px; border-radius:4px; font-family:Consolas,monospace;">1</span>–<span style="background:{key_bg}; padding:2px 6px; border-radius:4px; font-family:Consolas,monospace;">5</span> for Rapid Move.</li>
            </ol>
          </div>

          <div style="background-color:{card_bg}; border:1px solid {border}; border-radius:10px; padding:12px 14px; margin-bottom:10px;">
            <div style="font-size:15px; font-weight:bold; color:{accent}; margin-bottom:8px;">⌨️ Keyboard Shortcuts</div>
            <table width="100%" cellspacing="0" cellpadding="5" style="font-size:13px;">
              <tr><td width="38%"><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">1</span> – <span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">5</span> (Press)</b></td><td>Move current image to Folder A – E</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">1</span> – <span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">5</span> (Hold)</b></td><td><b>Rapid Move</b> continuously to Folder A – E</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">←</span> or <span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">A</span></b></td><td>Previous image</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">→</span> or <span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">D</span></b></td><td>Next image</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Home</span> / <span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">End</span></b></td><td>Jump to first / last image</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Ctrl+G</span></b></td><td>Jump to specific image number</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Ctrl+H</span></b></td><td>Toggle Hide Moved Images</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">F</span></b></td><td>Open Full-Size / Zoom Preview</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Space</span></b></td><td>Skip current image</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Ctrl+Z</span></b></td><td>Undo last move (restores file safely)</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Ctrl+E</span></b></td><td>Reveal current image in File Explorer</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Delete</span></b></td><td>Move current image to Windows Recycle Bin</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">Ctrl+O</span></b></td><td>Import folder</td></tr>
              <tr><td><b><span style="background:{key_bg}; padding:2px 7px; border-radius:4px; font-family:Consolas,monospace;">F1</span></b></td><td>Open this Keyboard Shortcuts &amp; Guide dialog</td></tr>
            </table>
          </div>

          <div style="background-color:{card_bg}; border:1px solid {border}; border-radius:10px; padding:12px 14px;">
            <div style="font-size:15px; font-weight:bold; color:{accent}; margin-bottom:6px;">🖱️ Mouse &amp; Safety Tips</div>
            <ul style="margin:4px 0 0 18px; padding:0;">
              <li><b>Click Folder A–E:</b> Move 1 image to that folder.</li>
              <li><b>Hold Left-Click on Folder A–E:</b> Rapid Move images continuously at your chosen interval (adjust in <i>Settings → Rapid Move Speed</i>).</li>
              <li><b>Double-Click Main Image:</b> Open Full-Size Zoom Preview.</li>
              <li><b>Drag &amp; Drop:</b> Drop any folder or image file directly onto the window.</li>
              <li><b>Zero Overwrite Protection:</b> Duplicate filenames are automatically renamed (e.g. <i>photo (1).jpg</i>) so existing files are never overwritten.</li>
            </ul>
          </div>
        </div>
        """

        body = QLabel(guide_html)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_layout.addWidget(body)
        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Got It")
        close_btn.setFixedHeight(36)
        close_btn.setMinimumWidth(110)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)




class ImagePreviewDialog(QDialog):
    """Dialog pratinjau ukuran penuh dengan kontrol Zoom (+, -, Fit, 100%, roda mouse)."""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.parent = parent
        self.zoom_factor = 1.0
        self._fit_mode = True
        self.base_pixmap = load_pixmap(image_path)

        filename = os.path.basename(image_path)
        w = self.base_pixmap.width()
        h = self.base_pixmap.height()
        self.setWindowTitle(f"Preview — {filename} ({w}×{h})")
        self.resize(960, 720)
        self.setMinimumSize(480, 360)

        is_dark = True
        if self.parent and hasattr(self.parent, "theme_mode"):
            is_dark = (
                self.parent.theme_mode in ("dark", "custom")
                or (self.parent.theme_mode == "system" and self.parent.is_system_dark())
            )
        bg = "#141414" if is_dark else "#f5f5f5"
        text = "#ffffff" if is_dark else "#1f2328"
        btn_bg = "#2a2a2a" if is_dark else "#e0e0e0"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {text}; }}
            QScrollArea {{ background-color: {bg}; border: 1px solid #333; border-radius: 8px; }}
            QLabel {{ color: {text}; background: transparent; border: none; }}
            QPushButton {{
                background-color: {btn_bg}; color: {text}; border: none;
                padding: 6px 14px; font-weight: bold; border-radius: 6px; min-height: 28px;
            }}
            QPushButton:hover {{ background-color: #00BFFF; color: white; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.info_label = QLabel(f"{filename}  ({w}×{h})")
        self.info_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        toolbar.addWidget(self.info_label)
        toolbar.addStretch()

        zoom_out_btn = QPushButton("− Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self.adjust_zoom(0.8))
        zoom_in_btn = QPushButton("+ Zoom In")
        zoom_in_btn.clicked.connect(lambda: self.adjust_zoom(1.25))
        fit_btn = QPushButton("Fit")
        fit_btn.clicked.connect(self.fit_to_window)
        actual_btn = QPushButton("100%")
        actual_btn.clicked.connect(self.reset_actual_size)
        close_btn = QPushButton("Close (Esc)")
        close_btn.clicked.connect(self.accept)

        for b in (zoom_out_btn, zoom_in_btn, fit_btn, actual_btn, close_btn):
            toolbar.addWidget(b)
        layout.addLayout(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.preview_label)
        layout.addWidget(self.scroll_area, stretch=1)

        self.update_preview()

    def adjust_zoom(self, multiplier):
        self._fit_mode = False
        self.zoom_factor = max(0.1, min(8.0, self.zoom_factor * multiplier))
        self.update_preview()

    def fit_to_window(self):
        self._fit_mode = True
        self.update_preview()

    def reset_actual_size(self):
        self._fit_mode = False
        self.zoom_factor = 1.0
        self.update_preview()

    def update_preview(self):
        if self.base_pixmap.isNull():
            self.preview_label.setText("Failed to load image.")
            return
        if self._fit_mode:
            vp = self.scroll_area.viewport().size()
            tw = max(200, vp.width() - 16)
            th = max(200, vp.height() - 16)
            scaled = self.base_pixmap.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.zoom_factor = scaled.width() / max(1, self.base_pixmap.width())
        else:
            tw = max(16, int(self.base_pixmap.width() * self.zoom_factor))
            th = max(16, int(self.base_pixmap.height() * self.zoom_factor))
            scaled = self.base_pixmap.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        pct = int(round(self.zoom_factor * 100))
        self.info_label.setText(
            f"{os.path.basename(self.image_path)}  ({self.base_pixmap.width()}×{self.base_pixmap.height()} • {pct}%)"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self.update_preview()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.adjust_zoom(1.15)
        elif delta < 0:
            self.adjust_zoom(1 / 1.15)


class FolderScanThread(QThread):
    """Memindai folder di thread latar. UI tetap responsif berapa pun jumlah filenya."""
    progress_updated = Signal(int)  # jumlah gambar yang sudah ditemukan

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
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
            )
            self.files = result or []
        except OSError as e:
            self.error = str(e)
            self.files = []


class CustomThemeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Custom Theme Settings")
        self.setMinimumWidth(300)
        self.setMaximumHeight(300)
        self.setFixedWidth(300)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(6)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        settings = load_settings()
        self.default_colors = {
            "bg_color": "#121212",
            "text_color": "#FFFFFF",
            "btn_bg": "#2e2e2e",
            "btn_hover": "#444444",
            "label_bg": "#1a1a1a",
            "menu_bg": "#1a1a1a",
            "menu_text": "#FFFFFF",
            "main_border_color": "#00BFFF",
            "next_border_color": "#32CD32",
            "main_shadow": "0 0 10px rgba(0, 191, 255, 0.7)",
            "next_shadow": "0 0 8px rgba(50, 205, 50, 0.5)"
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
            ("Label Background", "label_bg", self.label_bg),
            ("Menu Background", "menu_bg", self.menu_bg),
            ("Menu Text Color", "menu_text", self.menu_text),
            ("Main Image Border", "main_border", self.main_border_color),
            ("Next Preview Border", "next_border", self.next_border_color),
        ]

        for label_text, target, current_color in color_fields:
            self.create_color_picker_button(scroll_layout, label_text, target, current_color)

        btn_layout = QHBoxLayout()
        self.reset_btn = QPushButton("🔄 Reset to Defaults")
        self.save_btn = QPushButton("✅ Save")

        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                border-radius: 6px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_to_defaults)

        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                border-radius: 6px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.save_btn.clicked.connect(self.save_and_close)

        btn_layout.addWidget(self.reset_btn)
        btn_layout.addWidget(self.save_btn)
        main_layout.addLayout(btn_layout)

        if parent and hasattr(parent, 'theme_mode'):
            use_dark = parent.theme_mode == "dark" or (parent.theme_mode == "system" and parent.is_system_dark())
            if use_dark:
                self.setStyleSheet("""
                    QDialog { background-color: #1e1e1e; color: white; }
                    QScrollArea { background-color: #1e1e1e; border: none; }
                    QLabel { color: white; background-color: transparent; border: none; }
                    QPushButton { background-color: #2e2e2e; color: white; }
                    QPushButton:hover { background-color: #444444; }
                """)
            else:
                self.setStyleSheet("""
                    QDialog { background-color: #f9f9f9; color: black; }
                    QScrollArea { background-color: #f9f9f9; border: none; }
                    QLabel { color: black; background-color: transparent; border: none; }
                    QPushButton { background-color: #e0e0e0; color: black; }
                    QPushButton:hover { background-color: #d0d0d0; }
                """)

    def create_color_picker_button(self, layout, label_text, target, current_color):
        container = QHBoxLayout()
        container.setSpacing(6)

        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        label.setFixedWidth(150)
        container.addWidget(label)

        btn = QPushButton("")
        btn.setObjectName(f"{target}_btn")
        setattr(self, f"{target}_btn", btn)
        btn.setFixedSize(80, 30)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {current_color};
                border: 2px solid #ccc;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: #888;
            }}
        """)
        btn.clicked.connect(lambda _, t=target: self.pick_color(t))
        container.addWidget(btn)
        container.addStretch()
        layout.addLayout(container)

    def pick_color(self, target):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            btn = getattr(self, f"{target}_btn")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_color};
                    border: 2px solid #ccc;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border-color: #888;
                }}
            """)

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
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: 2px solid #ccc;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border-color: #888;
                }}
            """)

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
    DEFAULT_NAMES = ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Set Destination Folders")
        self.setMinimumWidth(560)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(10)
        self.inputs = []

        is_dark = False
        if self.parent and hasattr(self.parent, "theme_mode"):
            is_dark = (
                self.parent.theme_mode in ("dark", "custom")
                or (self.parent.theme_mode == "system" and self.parent.is_system_dark())
            )
        bg = "#1e1e1e" if is_dark else "#ffffff"
        surface = "#2b2b2b" if is_dark else "#f4f6f8"
        text = "#ffffff" if is_dark else "#1f2328"
        border = "#404040" if is_dark else "#d0d7de"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {text}; }}
            QLabel {{ color: {text}; background: transparent; border: none; }}
            QLineEdit {{
                background-color: {surface}; color: {text};
                border: 1px solid {border}; border-radius: 6px; padding: 6px 8px;
            }}
            QPushButton {{
                background-color: {surface}; color: {text};
                border: 1px solid {border}; border-radius: 6px;
                padding: 6px 14px; font-weight: bold; min-height: 28px;
            }}
            QPushButton:hover {{ border-color: #00BFFF; }}
        """)

        header_layout = QHBoxLayout()
        lbl_key = QLabel("Key")
        lbl_key.setFixedWidth(36)
        lbl_key.setStyleSheet("font-weight: bold;")
        lbl_name = QLabel("Folder Name")
        lbl_name.setFixedWidth(140)
        lbl_name.setStyleSheet("font-weight: bold;")
        lbl_path = QLabel("Destination Path")
        lbl_path.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(lbl_key)
        header_layout.addWidget(lbl_name)
        header_layout.addWidget(lbl_path, stretch=1)
        self.layout.addLayout(header_layout)

        settings = load_settings()
        self.folder_names = settings.get("folder_names", list(self.DEFAULT_NAMES))
        self.folder_paths = settings.get("folder_paths", ["output/A", "output/B", "output/C", "output/D", "output/E"])
        for i in range(5):
            h_layout = QHBoxLayout()
            key_badge = QLabel(f"[{i + 1}]")
            key_badge.setFixedWidth(36)
            key_badge.setStyleSheet("font-weight: bold;")
            name_input = QLineEdit(self.folder_names[i] if i < len(self.folder_names) else self.DEFAULT_NAMES[i])
            name_input.setFixedWidth(140)
            path_input = QLineEdit(self.folder_paths[i] if i < len(self.folder_paths) else f"output/{chr(65 + i)}")
            btn_browse = QPushButton("Browse...")
            btn_browse.clicked.connect(lambda _, idx=i: self.select_folder(idx))
            h_layout.addWidget(key_badge)
            h_layout.addWidget(name_input)
            h_layout.addWidget(path_input, stretch=1)
            h_layout.addWidget(btn_browse)
            self.layout.addLayout(h_layout)
            self.inputs.append((name_input, path_input))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; border: none; padding: 6px 18px; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        self.layout.addLayout(btn_layout)

    def select_folder(self, index):
        folder = QFileDialog.getExistingDirectory(self, f"Select Folder {index + 1}")
        if folder:
            self.inputs[index][1].setText(folder)

    def save_and_close(self):
        self.folder_names = [
            inp[0].text().strip() or self.DEFAULT_NAMES[i]
            for i, inp in enumerate(self.inputs)
        ]
        self.folder_paths = [inp[1].text().strip() for inp in self.inputs]
        settings = load_settings()
        settings["folder_names"] = self.folder_names
        settings["folder_paths"] = self.folder_paths
        save_settings(settings)
        self.accept()

    def get_folders(self):
        return self.folder_names, self.folder_paths

class RapidMoveSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Rapid Move Speed")
        self.parent = parent
        self.setMinimumSize(420, 300)
        self.setModal(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Title
        title = QLabel("Rapid Move Interval")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 600; margin-bottom: 8px; border: none; background-color: transparent;")
        layout.addWidget(title)

        # Description
        desc = QLabel("Adjust how fast images are moved while holding Folder A–E\n(mouse button or keyboard key 1–5). Lower value = faster movement.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; line-height: 1.5;")
        layout.addWidget(desc)

        layout.addSpacing(20)

        # Current speed indicator
        self.current_label = QLabel()
        self.current_label.setAlignment(Qt.AlignCenter)
        self.current_label.setStyleSheet("font-size: 18px; font-weight: 600; padding: 16px;")
        self.current_label.setMinimumHeight(60)
        layout.addWidget(self.current_label)

        # Slider + Value layout
        control_layout = QHBoxLayout()
        control_layout.setSpacing(24)

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 1000)
        self.slider.setSingleStep(50)
        self.slider.setPageStep(100)
        control_layout.addWidget(self.slider, stretch=1)

        # SpinBox
        self.spinbox = QSpinBox()
        self.spinbox.setRange(50, 1000)
        self.spinbox.setSingleStep(50)
        self.spinbox.setSuffix(" ms")
        self.spinbox.setFixedWidth(130)
        self.spinbox.setFixedHeight(44)
        self.spinbox.setStyleSheet("font-size: 15px;")
        control_layout.addWidget(self.spinbox)

        layout.addLayout(control_layout)

        # Direction hint
        hint = QLabel("Faster ← → Slower")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 13px; font-style: italic; margin-top: 8px;")
        layout.addWidget(hint)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(44)
        cancel_btn.setMinimumWidth(110)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(44)
        save_btn.setMinimumWidth(110)
        save_btn.setObjectName("save_btn")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_and_close)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addSpacing(16)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # Initial value
        initial_value = clamp_rapid_interval(parent.rapid_move_interval if parent else RAPID_MOVE_DEFAULT_MS)
        self.slider.setValue(initial_value)
        self.spinbox.setValue(initial_value)
        self.update_current_label(initial_value)

        # Sync controls
        self.slider.valueChanged.connect(self.spinbox.setValue)
        self.spinbox.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.update_current_label)
        self.spinbox.valueChanged.connect(self.update_current_label)

        # Apply modern theme
        self.apply_modern_theme()

    def apply_modern_theme(self):
        if self.parent and hasattr(self.parent, 'theme_mode'):
            is_dark = (
                self.parent.theme_mode == "dark" or
                (self.parent.theme_mode == "system" and self.parent.is_system_dark()) or
                self.parent.theme_mode == "custom"
            )
        else:
            is_dark = False

        # Colors
        bg_color = "#1e1e1e" if is_dark else "#ffffff"
        surface_color = "#2d2d2d" if is_dark else "#f8f9fa"
        text_color = "#ffffff" if is_dark else "#212529"
        text_secondary = "#b0b0b0" if is_dark else "#6c757d"
        accent_color = "#00BFFF"
        border_color = "#404040" if is_dark else "#dee2e6"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 20px;
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                background: {border_color};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent_color};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {accent_color};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 5px;
                border: 2px solid {bg_color};
            }}
            QSlider::handle:horizontal:hover {{
                background: #00d4ff;
            }}
            QSpinBox {{
                background-color: {surface_color};
                border: 2px solid {border_color};
                border-radius: 10px;
                padding: 8px 12px;
                color: {text_color};
                font-size: 15px;
            }}
            QSpinBox:focus {{
                border-color: {accent_color};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                background: transparent;
            }}
            QPushButton {{
                background-color: {surface_color};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 12px;
                padding: 0 24px;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {border_color};
            }}
            QPushButton:pressed {{
                background-color: {accent_color}40;
            }}
            QPushButton#save_btn {{
                background-color: {accent_color};
                color: white;
                border: none;
            }}
            QPushButton#save_btn:hover {{
                background-color: #00a8e6;
            }}
            QPushButton#save_btn:pressed {{
                background-color: #0098d4;
            }}
        """)

        # Update secondary text colors
        for widget in self.findChildren(QLabel):
            if widget.text() in ["Faster ← → Slower", 
                                "Adjust how fast images are moved while holding Folder A–E\n(mouse button or keyboard key 1–5). Lower value = faster movement."]:
                widget.setStyleSheet(f"color: {text_secondary}; font-size: 14px; border: none; background: transparent;")

        # Current label emphasis
        self.current_label.setStyleSheet(f"""
            background-color: {surface_color};
            color: {text_color};
            border-radius: 16px;
            padding: 20px;
            font-size: 18px;
            font-weight: 600;
        """)

    def update_current_label(self, value):
        if value <= 100:
            speed = "Lightning Fast ⚡⚡⚡"
        elif value <= 200:
            speed = "Very Fast ⚡⚡"
        elif value <= 400:
            speed = "Fast ⚡"
        elif value <= 600:
            speed = "Medium ⏱️"
        else:
            speed = "Relaxed 🐌"

        self.current_label.setText(f"{value} ms\n{speed}")

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
        self.resize(900, 700)
        self.setAcceptDrops(True)
        self.image_files = []
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
        # Rapid move variables
        self.is_rapid_moving = False
        self.rapid_folder_index = None
        self.rapid_source = None  # "mouse" atau "key"
        self.rapid_timer = QTimer(self)
        self.rapid_timer.timeout.connect(self.rapid_move)
        self.folder_buttons = []  # Untuk menyimpan referensi tombol folder
        settings = load_settings()
        self.rapid_move_interval = clamp_rapid_interval(settings.get("rapid_move_interval", RAPID_MOVE_DEFAULT_MS))
        self.scan_thread = None
        self._scan_threads = set()  # semua thread pemindai yang masih hidup
        self.update_thread = None

        # Rest of __init__ remains unchanged
        self.loading_widget = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.loading_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.loading_label = QLabel("Loading folder...", self.loading_widget)
        self.loading_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: white;
            background-color: rgba(0, 0, 0, 180);
            border-radius: 10px;
            padding: 20px;
        """)
        layout = QVBoxLayout(self.loading_widget)
        layout.addWidget(self.loading_label)
        self.loading_widget.setLayout(layout)
        self.loading_widget.hide()
        self.loading_widget.setFixedSize(300, 100)
        self.start_update_check()
        self.init_ui()
        self.check_first_run()
        self.load_custom_folders()
        self.load_recent_folders()
        self.apply_theme()
        self.show_current_image(self.filtered_files)
        # Tangkap tombol 1-4 di level aplikasi agar rapid move keyboard tetap jalan
        # walaupun fokus sedang berada di tombol/combobox di jendela utama.
        QApplication.instance().installEventFilter(self)

    def start_update_check(self, manual=False):
        """Mulai pengecekan pembaruan di thread terpisah (tidak memblokir UI)."""
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
        """Hentikan animasi QMovie aktif dan lepaskan buffer memori."""
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

    def closeEvent(self, event):
        """Hentikan timer & thread latar dengan aman sebelum jendela ditutup."""
        self.stop_rapid_move(silent=True)
        self.stop_current_movie()
        self.flush_history()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
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
            self.show_notification("Welcome to ImageSorter! Organize your photos in seconds 😊")
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
            "folder_names": ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"],
            "folder_paths": ["output/A", "output/B", "output/C", "output/D", "output/E"],
            "recent_folders": [],
            "theme_mode": "system",
            "rapid_move_interval": RAPID_MOVE_DEFAULT_MS,
            "custom_theme": {
                "bg_color": "#121212",
                "text_color": "#FFFFFF",
                "btn_bg": "#2e2e2e",
                "btn_hover": "#444444",
                "label_bg": "#1a1a1a",
                "menu_bg": "#1a1a1a",
                "menu_text": "#FFFFFF",
                "main_border_color": "#00BFFF",
                "next_border_color": "#32CD32",
                "main_shadow": "0 0 10px rgba(0, 191, 255, 0.7)",
                "next_shadow": "0 0 8px rgba(50, 205, 50, 0.5)"
            }
        }
        save_settings(settings)
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
        self.loading_label.setText("Scanning folder...")
        thread = FolderScanThread(folder_path, self)
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

    def apply_theme(self):
        settings = load_settings()
        if self.theme_mode == "custom":
            custom_theme = settings.get("custom_theme", {})
            bg_color = custom_theme.get("bg_color", "#121212")
            text_color = custom_theme.get("text_color", "#FFFFFF")
            btn_bg = custom_theme.get("btn_bg", "#2e2e2e")
            btn_hover = custom_theme.get("btn_hover", "#444444")
            label_bg = custom_theme.get("label_bg", "#1a1a1a")
            menu_bg = custom_theme.get("menu_bg", "#1a1a1a")
            menu_text = custom_theme.get("menu_text", "#FFFFFF")
            main_border_color = custom_theme.get("main_border_color", "#00BFFF")
            next_border_color = custom_theme.get("next_border_color", "#32CD32")
            main_shadow = custom_theme.get("main_shadow", "0 0 15px rgba(0, 191, 255, 0.6)")
            next_shadow = custom_theme.get("next_shadow", "0 0 10px rgba(50, 205, 50, 0.4)")

            main_bg_gradient = f"qradialgradient(cx:0.5, cy:0.5, radius:0.5, stop:0 {main_border_color}32, stop:1 transparent)"
            next_bg_gradient = f"qradialgradient(cx:0.5, cy:0.5, radius:0.5, stop:0 {next_border_color}1E, stop:1 transparent)"

            self.setStyleSheet(f"""
                QMainWindow {{ background-color: {bg_color}; }}
                QLabel {{
                    color: {text_color};
                    background-color: {label_bg};
                    border: 1px solid #333;
                }}
                QPushButton {{
                    background-color: {btn_bg};
                    color: {text_color};
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 8px;
                    min-height: 26px;
                }}
                QPushButton:hover {{ background-color: {btn_hover}; }}
                QPushButton:pressed {{ background-color: {btn_hover}; }}
                QMenuBar {{
                    background-color: {menu_bg};
                    color: {menu_text};
                }}
                QMenuBar::item:selected {{ background-color: #333333; }}
                QMenu {{
                    background-color: {menu_bg};
                    color: {menu_text};
                    border: 1px solid #333;
                }}
                QMenu::item:selected {{ background-color: #333333; }}
            """)
            self.image_label.setStyleSheet(f"""
                QLabel {{
                    color: {text_color};
                    background: {main_bg_gradient};
                    border: 3px solid {main_border_color};
                    border-radius: 12px;
                    box-shadow: {main_shadow};
                    padding: 8px;
                    transition: all 0.3s ease;
                }}
                QLabel:hover {{
                    transform: scale(1.02);
                    box-shadow: 0 0 25px {main_border_color}CC;
                    border: 4px solid {main_border_color};
                }}
            """)
            self.next_image_label.setStyleSheet(f"""
                QLabel {{
                    color: {text_color};
                    background: {next_bg_gradient};
                    border: 2px dashed {next_border_color};
                    border-radius: 10px;
                    box-shadow: {next_shadow};
                    padding: 6px;
                    transition: all 0.3s ease;
                }}
                QLabel:hover {{
                    transform: scale(1.01);
                    box-shadow: 0 0 15px {next_border_color}99;
                    opacity: 0.9;
                }}
            """)
            self.image_label.setMouseTracking(True)
            self.next_image_label.setMouseTracking(True)
            
            self.update_button_styles()
            self.update_folder_buttons()
            return

        if self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark()):
            self.setStyleSheet("""
                QMainWindow { background-color: #000000; }
                QLabel {
                    color: white;
                    background-color: #000000;
                    border: 1px solid #222;
                }
                QPushButton {
                    background-color: #111111;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 8px;
                    min-height: 26px;
                }
                QPushButton:hover { background-color: #222222; }
                QPushButton:pressed { background-color: #333333; }
                QMenuBar {
                    background-color: #000000;
                    color: white;
                }
                QMenuBar::item:selected { background-color: #111111; }
                QMenu {
                    background-color: #000000;
                    color: white;
                    border: 1px solid #222;
                }
                QMenu::item:selected { background-color: #111111; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #ffffff; }
                QLabel {
                    color: black;
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: black;
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 8px;
                    min-height: 26px;
                }
                QPushButton:hover { background-color: #d0d0d0; }
                QPushButton:pressed { background-color: #c0c0c0; }
                QMenuBar {
                    background-color: #f0f0f0;
                    color: black;
                }
                QMenuBar::item:selected { background-color: #dcdcdc; }
                QMenu {
                    background-color: #ffffff;
                    color: black;
                    border: 1px solid #ccc;
                }
                QMenu::item:selected { background-color: #eaeaea; }
            """)

        self.update_progress_bar_style()
        self.update_label_styles()
        self.update_button_styles()
        self.update_folder_buttons()
        self.show_current_image()

    def sync_menu_theme_checkboxes(self):
        self.light_action.setChecked(self.theme_mode == "light")
        self.dark_action.setChecked(self.theme_mode == "dark")
        self.system_action.setChecked(self.theme_mode == "system")
        self.custom_action.setChecked(self.theme_mode == "custom")

    def update_label_styles(self):
        settings = load_settings()
        is_dark = self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark())
        
        if self.theme_mode == "custom":
            custom_theme = settings.get("custom_theme", {})
            bg_color = custom_theme.get("label_bg", "#1e1e1e" if is_dark else "#ffffff")
            text_color = custom_theme.get("text_color", "#FFFFFF" if is_dark else "#000000")
        else:
            bg_color = "#1e1e1e" if is_dark else "#ffffff"
            text_color = "white" if is_dark else "black"

        self.image_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                background: {bg_color};
                border: 6px solid transparent;
                border-radius: 20px;
                padding: 10px;
            }}
            QLabel:hover {{
                border-width: 8px;
            }}
        """ if is_dark else f"""
            QLabel {{
                color: {text_color};
                background: {bg_color};
                border: 6px solid transparent;
                border-radius: 20px;
                padding: 10px;
            }}
            QLabel:hover {{
                border-width: 8px;
            }}
        """)

        self.next_image_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                background: {bg_color};
                border: 5px dashed transparent;
                border-radius: 15px;
                padding: 8px;
            }}
            QLabel:hover {{
                border-width: 6px;
                opacity: 1.0;
            }}
        """ if is_dark else f"""
            QLabel {{
                color: {text_color};
                background: {bg_color};
                border: 5px dashed transparent;
                border-radius: 15px;
                padding: 8px;
            }}
            QLabel:hover {{
                border-width: 6px;
                opacity: 1.0;
            }}
        """)

        self.image_label.setMouseTracking(True)
        self.next_image_label.setMouseTracking(True)

    def is_system_dark(self):
        palette = QApplication.palette()
        base_color = palette.window().color()
        brightness = base_color.red() * 0.299 + base_color.green() * 0.587 + base_color.blue() * 0.114
        return brightness < 128

    def update_button_styles(self):
        for btn in [self.undo_btn, self.skip_btn, self.prev_btn, self.next_btn]:
            self.set_modern_button_style(btn)

    def show_notification(self, text):
        if hasattr(self, 'fade_in') and self.fade_in.state() == QPropertyAnimation.Running:
            self.fade_in.stop()
        if hasattr(self, 'fade_out') and self.fade_out.state() == QPropertyAnimation.Running:
            self.fade_out.stop()

        self.notification_label.setText(text)

        if self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark()):
            self.notification_label.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
                color: white;
                background-color: rgba(30, 30, 30, 220);
                text-align: center;
            """)
        else:
            self.notification_label.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
                color: black;
                background-color: rgba(255, 255, 255, 220);
                border: 1px solid #ccc;
                text-align: center;
            """)

        self.notification_label.setWordWrap(True)
        self.notification_label.setAlignment(Qt.AlignCenter)

        font_metrics = self.notification_label.fontMetrics()
        self._notification_text_width = font_metrics.horizontalAdvance(text) + 20
        self.position_notification()

        self.notification_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.notification_label.setWindowOpacity(0.0)
        self.notification_label.show()

        self.fade_in = QPropertyAnimation(self.notification_label, b"windowOpacity")
        self.fade_in.setDuration(500)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

        self.fade_out = QPropertyAnimation(self.notification_label, b"windowOpacity")
        self.fade_out.setDuration(500)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)

        self.fade_in.finished.connect(lambda: QTimer.singleShot(2500, self.fade_out.start))
        self.fade_out.finished.connect(self.notification_label.hide)

        self.fade_in.start()

    def position_notification(self):
        """Letakkan notifikasi di tengah-bawah dan selalu muat di dalam jendela."""
        available = max(120, self.width() - 20)
        text_width = getattr(self, "_notification_text_width", 300)
        label_width = min(available, max(300, min(800, text_width)))
        label_height = 60
        x = max(10, (self.width() - label_width) // 2)
        y = max(40, self.height() - 150)
        self.notification_label.setGeometry(x, y, label_width, label_height)

    def update_recent_folders_menu(self):
        if not hasattr(self, 'recent_folders_menu') or self.recent_folders_menu is None:
            return

        for action in self.recent_folders_menu.actions():
            self.recent_folders_menu.removeAction(action)

        for folder in self.recent_folders:
            action = QAction(folder, self)
            action.triggered.connect(lambda _, path=folder: self.import_folder_from_path(path))
            self.recent_folders_menu.addAction(action)

        if self.recent_folders:
            self.recent_folders_menu.addSeparator()

        clear_action = QAction("Clear Recent", self)
        clear_action.setIcon(QIcon(resource_path("assets/icons/clear_recent.png")))
        clear_action.triggered.connect(self.clear_recent_folders)
        self.recent_folders_menu.addAction(clear_action)

    def import_folder_from_path(self, folder_path):
        if not os.path.isdir(folder_path):
            self.show_notification("Folder is invalid or not found.")
            return

        self.import_folder_common(folder_path)

    def load_file_list(self, folder_path, files):
        """Pasang daftar file hasil pemindaian ke tampilan."""
        self.image_files = files
        self.filtered_files = []
        self.current_index = 0
        self.nav_history.clear()
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

        self.image_label = QLabel("Current Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(450, 500)
        main_shadow_effect = QGraphicsDropShadowEffect(self)
        main_shadow_effect.setBlurRadius(40)
        main_shadow_effect.setColor(Qt.blue if self.theme_mode == "dark" else Qt.red)
        main_shadow_effect.setOffset(0, 0)
        self.image_label.setGraphicsEffect(main_shadow_effect)

        self.next_image_label = QLabel("Next Image")
        self.next_image_label.setAlignment(Qt.AlignCenter)
        self.next_image_label.setMinimumSize(300, 360)
        self.next_image_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        next_shadow_effect = QGraphicsDropShadowEffect(self)
        next_shadow_effect.setBlurRadius(10)
        next_shadow_effect.setColor(Qt.green if self.theme_mode == "dark" else Qt.magenta)
        next_shadow_effect.setOffset(0, 0)
        self.next_image_label.setGraphicsEffect(next_shadow_effect)
        self.update_label_styles()

        preview_layout = QHBoxLayout()
        preview_layout.addWidget(self.image_label)
        preview_layout.addWidget(self.next_image_label)

        info_layout = QHBoxLayout()

        self.file_info_label = QLabel("No image loaded.")
        self.file_info_label.setStyleSheet("font-size: 12px; padding: 5px;")
        self.file_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.file_info_label.setFixedHeight(30)
        self.file_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.position_container = QWidget()
        self.position_stack = QStackedLayout(self.position_container)
        self.position_container.setFixedHeight(30)
        self.position_stack.setContentsMargins(0, 0, 0, 0)

        self.position_info_label = QLabel("")
        self.position_info_label.setStyleSheet("font-size: 12px; padding: 5px;")
        self.position_info_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.file_info_label.setFixedHeight(30)
        self.position_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.update_progress_bar_style()
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.progress_bar.setFixedHeight(30)

        self.position_stack.addWidget(self.position_info_label)
        self.position_stack.addWidget(self.progress_bar)
        self.position_stack.setCurrentIndex(0)

        info_layout.addWidget(self.file_info_label)
        info_layout.addWidget(self.position_container)

        info_layout.setStretch(0, 8)
        info_layout.setStretch(1, 1)

        main_layout.addLayout(info_layout)
        main_layout.addLayout(preview_layout)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setToolTip("Go to previous image (Left Arrow / A)")
        self.set_modern_button_style(self.prev_btn)
        self.prev_btn.clicked.connect(self.show_previous)
        self.prev_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setToolTip("Go to next image (Right Arrow / D)")
        self.set_modern_button_style(self.next_btn)
        self.next_btn.clicked.connect(self.show_next)
        self.next_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout.addWidget(self.next_btn)

        nav_layout.setStretch(0, 1)
        nav_layout.setStretch(1, 1)

        self.folder_layout = QHBoxLayout()
        self.folder_layout.setSpacing(10)
        self.update_folder_buttons()

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        self.filter_combo = QComboBox()
        self.filter_combo.setToolTip("Select file extension to filter")
        self.filter_combo.addItem("All Files")
        readable_exts = readable_image_extensions()
        self.filter_combo.addItems([ext for ext in SUPPORTED_IMAGE_EXTENSIONS if ext in readable_exts])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        action_layout.addWidget(self.filter_combo)
        self.filter_combo.setCurrentIndex(0)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setToolTip("Undo the last move (Ctrl+Z)")
        self.set_modern_button_style(self.undo_btn)
        self.undo_btn.clicked.connect(self.undo_action)
        action_layout.addWidget(self.undo_btn)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setToolTip("Skip current image (Space)")
        self.set_modern_button_style(self.skip_btn)
        self.skip_btn.clicked.connect(self.skip_image)
        action_layout.addWidget(self.skip_btn)
        action_layout.addStretch()

        self.setWindowIcon(QIcon(resource_path("assets/icons/app_icon.png")))
        self.prev_btn.setIcon(QIcon(resource_path("assets/icons/prev.png")))
        self.next_btn.setIcon(QIcon(resource_path("assets/icons/next.png")))
        self.undo_btn.setIcon(QIcon(resource_path("assets/icons/undo.png")))
        self.skip_btn.setIcon(QIcon(resource_path("assets/icons/skip.png")))

        large_icon_size = QSize(48, 48)
        small_icon_size = QSize(20, 20)
        self.prev_btn.setIconSize(large_icon_size)
        self.next_btn.setIconSize(large_icon_size)
        self.undo_btn.setIconSize(small_icon_size)
        self.skip_btn.setIconSize(large_icon_size)

        self.update_button_widths()

        button_container = QWidget()
        button_container.setFixedHeight(150)
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addLayout(nav_layout)
        button_layout.addLayout(self.folder_layout)
        button_layout.addLayout(action_layout)

        main_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        main_layout.addWidget(button_container)

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        file_menu = menu_bar.addMenu("File")
        import_action = QAction("Import Folder", self)
        import_action.setIcon(QIcon(resource_path("assets/icons/folder.png")))
        import_action.setShortcut(QKeySequence("Ctrl+O"))
        import_action.setToolTip("Import images from folder (Ctrl+O)")
        import_action.triggered.connect(self.import_folder)
        file_menu.addAction(import_action)
        reveal_action = QAction("Show in File Explorer", self)
        reveal_action.setIcon(QIcon(resource_path("assets/icons/folder.png")))
        reveal_action.setShortcut(QKeySequence("Ctrl+E"))
        reveal_action.setToolTip("Reveal current image in File Explorer (Ctrl+E)")
        reveal_action.triggered.connect(self.reveal_in_explorer)
        file_menu.addAction(reveal_action)

        recycle_action = QAction("Move to Recycle Bin", self)
        recycle_action.setIcon(QIcon(resource_path("assets/icons/clear_recent.png")))
        recycle_action.setShortcut(QKeySequence("Delete"))
        recycle_action.setToolTip("Move current image to Windows Recycle Bin (Delete)")
        recycle_action.triggered.connect(self.delete_current_to_recycle_bin)
        file_menu.addAction(recycle_action)

        export_action = QAction("Export Log", self)
        export_action.setIcon(QIcon(resource_path("assets/icons/export_log.png")))
        export_action.setToolTip("Export activity log to text file")
        export_action.triggered.connect(self.export_log)
        file_menu.addAction(export_action)
        self.recent_folders_menu = file_menu.addMenu("Recent Folders")
        self.recent_folders_menu.setIcon(QIcon(resource_path("assets/icons/recent_folder.png")))
        self.update_recent_folders_menu()

        view_menu = menu_bar.addMenu("View")
        self.light_action = QAction("Light Mode", self)
        self.light_action.setIcon(QIcon(resource_path("assets/icons/light.png")))
        self.dark_action = QAction("Dark Mode", self)
        self.dark_action.setIcon(QIcon(resource_path("assets/icons/dark.png")))
        self.system_action = QAction("System Default", self)
        self.system_action.setIcon(QIcon(resource_path("assets/icons/system_default.png")))
        self.custom_action = QAction("Custom Theme", self)
        self.custom_action.setIcon(QIcon(resource_path("assets/icons/theme.png")))
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

        jump_action = QAction("Jump to Image...", self)
        jump_action.setShortcut(QKeySequence("Ctrl+G"))
        jump_action.triggered.connect(self.jump_to_image_dialog)
        view_menu.addAction(jump_action)

        preview_action = QAction("Full-Size Preview", self)
        preview_action.setShortcut(QKeySequence("F"))
        preview_action.triggered.connect(self.open_full_preview)
        view_menu.addAction(preview_action)

        settings_menu = menu_bar.addMenu("Settings")
        settings_action = QAction("Folder Settings", self)
        settings_action.setIcon(QIcon(resource_path("assets/icons/folder.png")))
        export_settings_action = QAction("Export Settings", self)
        export_settings_action.setIcon(QIcon(resource_path("assets/icons/export.png")))
        import_settings_action = QAction("Import Settings", self)
        import_settings_action.setIcon(QIcon(resource_path("assets/icons/import.png")))
        settings_action.triggered.connect(self.open_settings)
        export_settings_action.triggered.connect(self.export_settings)
        import_settings_action.triggered.connect(self.import_settings)
        rapid_move_action = QAction("Rapid Move Speed", self)
        rapid_move_action.setIcon(QIcon(resource_path("assets/icons/skip.png")))
        rapid_move_action.triggered.connect(self.open_rapid_move_settings)
        reset_settings_action = QAction("Reset Default Settings", self)
        reset_settings_action.setIcon(QIcon(resource_path("assets/icons/clear_recent.png")))
        reset_settings_action.triggered.connect(self.confirm_reset_default_settings)

        settings_menu.addAction(settings_action)
        settings_menu.addAction(export_settings_action)
        settings_menu.addAction(import_settings_action)
        settings_menu.addAction(rapid_move_action)
        settings_menu.addSeparator()
        settings_menu.addAction(reset_settings_action)

        help_menu = menu_bar.addMenu("Help")
        shortcuts_action = QAction("Keyboard Shortcuts && Guide", self)
        shortcuts_action.setIcon(QIcon(resource_path("assets/icons/about.png")))
        shortcuts_action.setShortcut(QKeySequence("F1"))
        shortcuts_action.setToolTip("View all keyboard shortcuts and usage tutorial (F1)")
        shortcuts_action.triggered.connect(self.show_shortcuts_guide)
        help_menu.addAction(shortcuts_action)
        help_menu.addSeparator()

        about_action = QAction("About", self)
        about_action.setIcon(QIcon(resource_path("assets/icons/about.png")))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        update_action = QAction("Check for Updates", self)
        update_action.setIcon(QIcon(resource_path("assets/icons/down_arrow.png")))
        update_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(update_action)

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
        next_shortcut_d = QShortcut(QKeySequence("D"), self)
        next_shortcut_d.activated.connect(self.show_next)
        prev_shortcut = QShortcut(QKeySequence("Left"), self)
        prev_shortcut.activated.connect(self.show_previous)
        prev_shortcut_a = QShortcut(QKeySequence("A"), self)
        prev_shortcut_a.activated.connect(self.show_previous)
        undo_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), self)
        undo_shortcut.activated.connect(self.undo_action)
        skip_shortcut = QShortcut(QKeySequence("Space"), self)
        skip_shortcut.activated.connect(self.skip_image)

    def check_for_updates(self):
        """Cek update manual dari menu, tanpa membekukan UI."""
        self.show_notification("Checking for updates...")
        self.start_update_check(manual=True)

    def update_progress_bar_style(self):
        is_dark = self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark())
        if self.theme_mode == "custom":
            settings = load_settings()
            custom_theme = settings.get("custom_theme", {})
            bg_color = custom_theme.get("bg_color", "#121212")
            text_color = custom_theme.get("text_color", "#FFFFFF")
            bar_color = custom_theme.get("main_border_color", "#8700C6DF")
        else:
            bg_color = "#1e1e1e" if is_dark else "#f0f0f0"
            text_color = "white" if is_dark else "black"
            bar_color = "#8700C6DF" if is_dark else "#FF4500"

        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {text_color};
                border-radius: 5px;
                text-align: center;
                font-size: 12px;
                padding: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 4px;
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
        info_dialog = QMessageBox()
        info_dialog.setWindowTitle(title)
        info_dialog.setText(message)
        info_dialog.setIcon(QMessageBox.Information)
        info_dialog.setWindowFlags(Qt.FramelessWindowHint)
        info_dialog.setAttribute(Qt.WA_TranslucentBackground)
        self.apply_message_box_style(info_dialog)
        info_dialog.exec()

    def apply_message_box_style(self, message_box):
        print(f"Theme Mode: {self.theme_mode}")
        is_dark = self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark())
        print(f"Is Dark: {is_dark}")

        bg_color = "#1e1e1e" if is_dark else "#f9f9f9"
        text_color = "white" if is_dark else "black"
        btn_bg = "#2e2e2e" if is_dark else "#d0d0d0"
        btn_hover = "#444444" if is_dark else "#b0b0b0"

        message_box.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 10px;
                padding: 10px;
            }}
            QMessageBox {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 10px;
                padding: 10px;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
                font-size: 14px;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: none;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 6px;
                min-width: 90px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
            QPushButton:pressed {{
                background-color: {btn_bg};
            }}
            QFrame {{
                background-color: transparent;
                border: none;
            }}
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
        self.folder_names = settings.get("folder_names", ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"])
        self.folder_paths = settings.get("folder_paths", ["output/A", "output/B", "output/C", "output/D", "output/E"])
        print(f"[DEBUG] Loaded folder_names: {self.folder_names}")
        print(f"[DEBUG] Loaded folder_paths: {self.folder_paths}") 

    def clear_recent_folders(self):
        self.recent_folders.clear()
        self.save_recent_folders()
        self.update_recent_folders_menu()

    def update_folder_buttons(self):
        # Remove all existing folder buttons
        while self.folder_layout.count():
            item = self.folder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.folder_buttons = []  # Reset list

        light_colors = ["#FFD1DC", "#C1E1C1", "#FFE082", "#B3CDE0", "#F8C8DC"]
        dark_colors = ["#4A2C5A", "#3A5F3A", "#6B5A2C", "#3A4B5D", "#6B3F4D"]

        for i, (label, path) in enumerate(zip(self.folder_names, self.folder_paths)):
            key_num = i + 1
            btn = QPushButton(f"[{key_num}] {label}")
            btn.setIcon(QIcon(resource_path("assets/icons/folder.png")))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(
                f"Move to {label} ({path})\n"
                f"Shortcut: Press {key_num} • Hold click or key {key_num} for Rapid Move"
            )
            if self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark()):
                color = dark_colors[i % len(dark_colors)]
                hover_color = self.darken_color(color, factor=0.75)
                text_color = "white"
            else:
                color = light_colors[i % len(light_colors)]
                hover_color = self.darken_color(color, factor=0.9)
                text_color = "black"
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: {text_color};
                    border: none;
                    padding: 10px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    min-height: 34px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
            """)
            btn.clicked.connect(lambda _, p=path: self.move_to_custom_folder(p))
            self.folder_layout.addWidget(btn)
            self.folder_buttons.append(btn)

        # Pasang event filter pada kelima tombol folder (A-E)
        for btn in self.folder_buttons:
            btn.installEventFilter(self)
        if hasattr(self, "image_label"):
            self.image_label.installEventFilter(self)

    def darken_color(self, hex_color, factor=0.8):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def update_button_widths(self):
        """Adjust widths for Filter, Undo, and Skip buttons dynamically."""
        window_width = self.width()
        # Filter button takes 15% of window width, with a minimum of 100px
        filter_width = max(int(window_width * 0.15), 100)
        # Remaining space is divided equally between Undo and Skip
        remaining_width = window_width - filter_width - 40  # Account for spacing (10px each side, assuming 4 spacings)
        button_width = max(int(remaining_width / 2), 80)  # Divide remaining space, min 80px

        self.filter_combo.setMinimumWidth(filter_width)
        self.filter_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        for btn in [self.undo_btn, self.skip_btn]:
            btn.setMinimumWidth(button_width)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        print(f"[DEBUG] Window width: {window_width}, Filter width: {filter_width}, Button width (undo/skip): {button_width}")

    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        self.update_button_widths()
        if hasattr(self, 'notification_label') and self.notification_label.isVisible():
            self.position_notification()

    def set_modern_button_style(self, button):
        if self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark()):
            bg_color = "#111111"
            hover_color = "#222222"
            text_color = "white"
        else:
            bg_color = "#e0e0e0"
            hover_color = "#d0d0d0"
            text_color = "black"

        # Use a smaller min-height for Filter, Undo, and Skip buttons
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                padding: 6px 12px;
                font-weight: bold;
                border-radius: 8px;
                min-height: 24px;  /* Smaller height than folder buttons (34px) */
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:pressed {{ background-color: {hover_color}; }}
        """)
        if isinstance(button, QComboBox):
            button.setStyleSheet(f"""
                QComboBox {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 8px;
                    min-height: 24px;  /* Match button height */
                }}
                QComboBox:hover {{ background-color: {hover_color}; }}
                QComboBox::drop-down {{ border: none; }}
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
            # Sinkronkan gaya dengan tema
            is_dark = self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark())
            if is_dark:
                self.loading_label.setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: white;
                    background-color: rgba(0, 0, 0, 180);
                    border-radius: 10px;
                    padding: 20px;
                """)
            else:
                self.loading_label.setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: black;
                    background-color: rgba(255, 255, 255, 180);
                    border-radius: 10px;
                    padding: 20px;
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
        if not files:
            for child in self.image_label.findChildren(QLabel):
                child.deleteLater()
            if self.image_files:
                self.image_label.setText("No images match the filter.")
            else:
                self.image_label.setText(self.get_empty_state_text())
            self.next_image_label.setText("Next: None")
            self.file_info_label.setText("No image loaded.")
            self.position_info_label.setText("")
            self.image_label.setFixedSize(450, 500)
            self.next_image_label.setFixedSize(250, 310)
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

        meta_text = ""
        orig_w, orig_h, file_size, fmt_bytes, frame_count = 0, 0, 0, b"", 1
        file_exists = os.path.exists(new_path)
        if file_exists:
            orig_w, orig_h, file_size, fmt_bytes, frame_count = read_image_metadata(new_path)
            parts = []
            if orig_w > 0 and orig_h > 0:
                parts.append(f"{orig_w}×{orig_h}")
            if file_size > 0:
                parts.append(format_file_size(file_size))
            if parts:
                meta_text = f" <span style='color: #888888;'>({' • '.join(parts)})</span>"

        moved_status = f" <span style='color: red; font-weight: bold;'>(moved to {folder_name})</span>" if is_moved else ""
        self.file_info_label.setText(f"{filename}{meta_text}{moved_status}")
        self.file_info_label.setToolTip(f"{filename} ({new_path})")

        current_pos = self.current_index + 1
        total_files = len(files)
        self.position_info_label.setText(f"{current_pos}/{total_files}")

        for child in self.image_label.findChildren(QLabel):
            child.deleteLater()

        if file_exists:
            pixmap = load_pixmap(new_path, 720, 500)
            if not pixmap.isNull():
                resized_pixmap = resize_image(pixmap)
                target_size = resized_pixmap.size()
                self.image_label.setFixedSize(target_size)
                # Putar animasi GIF/WebP dari buffer memori agar tidak mengunci file di Windows
                if frame_count and frame_count > 1 and file_size <= 30 * 1024 * 1024:
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
                        else:
                            self.stop_current_movie()
                            self.image_label.setPixmap(resized_pixmap)
                    except OSError:
                        self.stop_current_movie()
                        self.image_label.setPixmap(resized_pixmap)
                else:
                    self.image_label.setPixmap(resized_pixmap)
                if is_moved:
                    watermark = QLabel(self.image_label)
                    watermark.setText("MOVED")
                    watermark.setStyleSheet("""
                        background-color: rgba(255, 0, 0, 150);
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        padding: 10px;
                        border-radius: 5px;
                    """)
                    watermark.setAlignment(Qt.AlignCenter)
                    watermark.setGeometry(10, 10, 120, 40)
                    watermark.show()
            else:
                self.image_label.setText("Failed to load image.")
                self.apply_info_style(self.image_label)
                self.image_label.setAlignment(Qt.AlignCenter)
                self.image_label.setFixedSize(450, 500)
        else:
            msg = f"File has been moved to:<br><span style='color: red; font-weight: bold;'>{folder_name}</span>" if folder_name else "File not found"
            self.image_label.setText(msg)
            self.apply_info_style(self.image_label)
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setFixedSize(450, 500)

        next_index = self.find_valid_next_index(self.current_index, files)
        if next_index is not None:
            next_path = files[next_index]
            new_next_path = self.get_new_path_from_history(next_path) or next_path
            if os.path.exists(new_next_path):
                next_pixmap = load_pixmap(new_next_path, 200, 260)
                if not next_pixmap.isNull():
                    resized_next = resize_next_preview(next_pixmap)
                    self.next_image_label.setPixmap(resized_next)
                    self.next_image_label.setFixedSize(resized_next.size())
                else:
                    self.next_image_label.setText("Next\nImage")
                    self.next_image_label.setFixedSize(250, 310)
            else:
                self.next_image_label.setText("Next\nImage")
                self.next_image_label.setFixedSize(250, 310)
        else:
            self.next_image_label.setText("Next\nImage")
            self.next_image_label.setFixedSize(250, 310)

    def apply_info_style(self, label):
        if self.theme_mode == "dark" or (self.theme_mode == "system" and self.is_system_dark()):
            label.setStyleSheet("""
                background-color: #444;
                border: 1px solid #666;
                color: #FFD700;
                padding: 10px;
            """)
        else:
            label.setStyleSheet("""
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                color: #CC7700;
                padding: 10px;
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
        dlg = QDialog(self)
        dlg.setWindowTitle("Jump to Image")
        dlg.setMinimumWidth(300)
        self.apply_message_box_style(dlg)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        lbl = QLabel(f"Enter image number (1 – {len(self.filtered_files)}):")
        lay.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(1, len(self.filtered_files))
        spin.setValue(self.current_index + 1)
        spin.setFixedHeight(34)
        lay.addWidget(spin)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        go_btn = QPushButton("Go")
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
        dlg = ImagePreviewDialog(actual_path, self)
        dlg.exec()

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

    DEFAULT_FOLDER_PATHS = ["output/A", "output/B", "output/C", "output/D", "output/E"]

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
        """Hentikan mode pindah cepat."""
        self.rapid_timer.stop()
        if self.is_rapid_moving:
            self.is_rapid_moving = False
            self.rapid_folder_index = None
            self.rapid_source = None
            if not silent:
                self.show_notification("Rapid move stopped")

    RAPID_KEYS = (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5)

    def _is_rapid_key_event(self, obj, event):
        """Key 1-5 tanpa Ctrl/Alt/Meta, ditujukan ke jendela utama, dan tidak ada dialog modal."""
        if event.key() not in self.RAPID_KEYS:
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

    def skip_image(self):
        self.nav_history.append(self.current_index)
        self.show_next()

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

    def get_empty_state_text(self):
        """Teks panduan singkat pada area preview saat belum ada gambar yang dimuat."""
        return (
            "<div style='text-align:center; line-height:1.55;'>"
            "<div style='font-size:18px; font-weight:bold; margin-bottom:8px;'>No Image Loaded</div>"
            "<div style='font-size:13px; margin-bottom:14px;'>"
            "Drag &amp; drop a folder/image here, or press <b>Ctrl+O</b> (<i>File → Import Folder</i>)"
            "</div>"
            "<div style='font-size:12px;'>"
            "<b>[1]–[5]</b> Move to Folder A–E &nbsp;•&nbsp; "
            "<b>Hold [1]–[5] / Button A–E</b> Rapid Move<br>"
            "<b>← / A</b> Previous &nbsp;•&nbsp; <b>→ / D</b> Next &nbsp;•&nbsp; "
            "<b>Space</b> Skip &nbsp;•&nbsp; <b>Ctrl+Z</b> Undo<br>"
            "Press <b>F1</b> (<i>Help → Keyboard Shortcuts &amp; Guide</i>) for full tutorial"
            "</div>"
            "</div>"
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