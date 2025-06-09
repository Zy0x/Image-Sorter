import sys
import os
import requests
import re
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

from pathlib import Path
import shutil
import json

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QWidget, QFileDialog,
    QMessageBox, QMenuBar, QSpacerItem, QSizePolicy, QDialog, QLineEdit,
    QMenu, QColorDialog, QFrame, QStyleOption, QStyle, QComboBox, QGraphicsDropShadowEffect,
    QProgressBar, QStackedLayout, QScrollArea, QTextEdit  # Added QTextEdit for release notes
)
from PySide6.QtGui import QPixmap, QAction, QImageReader, QIcon, QFont, QShortcut, QKeySequence, QDesktopServices
from PySide6.QtCore import Qt, QSettings, QMimeData, QPropertyAnimation, QEasingCurve, QTimer, QThread, QSize, Property, Signal, QUrl
from glob import glob

# Import resize function from utils/image_utils.py
from utils.image_utils import resize_image, resize_next_preview

def get_config_path():
    """Get the path to settings.json, always relative to the application directory."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    config_dir = os.path.join(base_path, "config")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "settings.json")
    print(f"[DEBUG] Using config path: {config_path}")
    return config_path

def save_history(history):
    config_path = get_config_path()
    history_path = os.path.join(os.path.dirname(config_path), "history.json")
    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        print(f"[DEBUG] History saved to {history_path}")
    except IOError as e:
        print(f"[DEBUG] Error saving history: {e}")

def load_history():
    config_path = get_config_path()
    history_path = os.path.join(os.path.dirname(config_path), "history.json")
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                print(f"[DEBUG] Loaded history from {history_path}")
                return history
        else:
            print(f"[DEBUG] No history file found at {history_path}, returning empty list")
    except (json.JSONDecodeError, IOError) as e:
        print(f"[DEBUG] Error loading history: {e}")
    return []

def resource_path(relative_path):
    """Find the file path relative to the application directory."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    print(f"[DEBUG] Resource path for {relative_path}: {full_path}")
    return full_path

def load_settings():
    """Load settings from settings.json or return default settings."""
    config_path = get_config_path()
    default_settings = {
        "first_run": True,
        "folder_names": ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"],
        "folder_paths": ["output/A", "output/B", "output/C", "output/D", "output/E"],
        "recent_folders": [],
        "theme_mode": "system",
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
    def __init__(self, parent=None, current_version="1.0", latest_version=None, release_notes="", download_url=None):
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_url = "https://api.github.com/repos/Zy0x/Image-Sorter/releases/latest"

    def run(self):
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            release_info = response.json()
            latest_version = release_info.get("tag_name", "").lstrip("v")  # Menghapus 'v' dari tag
            release_notes = release_info.get("body", "No release notes provided.")
            download_url = release_info.get("html_url", "")
            self.update_checked.emit(latest_version, release_notes, download_url)
        except requests.RequestException as e:
            self.error_occurred.emit(str(e))

class AboutDialog(QDialog):
    VERSION = "1.0-Stable"
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

class ImageValidationThread(QThread):
    progress_updated = Signal(int)

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files
        self.valid_images = []

    def run(self):
        supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.heic', '.heif', '.raw', '.psd')
        total_files = len(self.files)
        for i, file in enumerate(self.files):
            if file.lower().endswith(supported_formats):
                try:
                    img = QImageReader(file)
                    if img.canRead():
                        self.valid_images.append(file)
                except Exception:
                    pass
            progress = int((i + 1) / total_files * 100)
            self.progress_updated.emit(progress)

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Destination Folders")
        self.layout = QVBoxLayout(self)
        self.inputs = []
        settings = load_settings()
        self.folder_names = settings.get("folder_names", ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"])
        self.folder_paths = settings.get("folder_paths", ["output/A", "output/B", "output/C", "output/D", "output/E"])
        for i in range(5):
            h_layout = QHBoxLayout()
            name_input = QLineEdit(self.folder_names[i])
            path_input = QLineEdit(self.folder_paths[i])
            btn_browse = QPushButton("Browse")
            btn_browse.clicked.connect(lambda _, idx=i: self.select_folder(idx))
            h_layout.addWidget(name_input)
            h_layout.addWidget(path_input)
            h_layout.addWidget(btn_browse)
            self.layout.addLayout(h_layout)
            self.inputs.append((name_input, path_input))
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_and_close)
        self.layout.addWidget(save_btn)

    def select_folder(self, index):
        folder = QFileDialog.getExistingDirectory(self, f"Select Folder {index + 1}")
        if folder:
            self.inputs[index][1].setText(folder)

    def save_and_close(self):
        self.folder_names = [inp[0].text() for inp in self.inputs]
        self.folder_paths = [inp[1].text() for inp in self.inputs]
        settings = load_settings()
        settings["folder_names"] = self.folder_names
        settings["folder_paths"] = self.folder_paths
        save_settings(settings)
        self.accept()

    def get_folders(self):
        return self.folder_names, self.folder_paths

class ImageSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ImageSorter")
        self.resize(900, 700)
        self.setAcceptDrops(True)
        self.image_cache = {}
        self.image_files = []
        self.current_index = 0
        self.nav_history = []
        self.folder_names = []
        self.folder_paths = []
        self.log_buffer = []
        self.source_info = ""
        self.recent_folders = []
        self.theme_mode = "system"
        self.filtered_files = []
        self.history = load_history()

        self.loading_widget = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.loading_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.loading_label = QLabel("Loading folder...", self.loading_widget)
        self.loading_label.setAlignment(Qt.AlignCenter)
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

    def start_update_check(self):
        """Mulai pengecekan pembaruan di thread terpisah."""
        self.update_thread = UpdateCheckThread(self)
        self.update_thread.update_checked.connect(self.show_update_dialog)
        self.update_thread.error_occurred.connect(self.show_update_error)
        self.update_thread.start()

    def show_update_dialog(self, latest_version, release_notes, download_url):
        """Tampilkan dialog pembaruan dengan informasi dari thread."""
        current_version = AboutDialog.VERSION
        dialog = UpdateDialog(self, current_version, latest_version, release_notes, download_url)
        dialog.exec_()

    def show_update_error(self, error_message):
        """Tampilkan dialog kesalahan jika pengecekan pembaruan gagal."""
        dialog = UpdateDialog(self, AboutDialog.VERSION, None, f"Failed to check for updates: {error_message}")
        dialog.exec_()

    def check_first_run(self):
        settings = load_settings()
        first_run = settings.get("first_run", True)

        if first_run:
            self.set_default_settings()
            settings["first_run"] = False
            save_settings(settings)
            self.show_notification("Welcome to ImageSorter! Organize your photos in seconds 😊")
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Load Settings")
            msg.setText("Would you like to load last settings?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            msg.setIcon(QMessageBox.Question)
            self.apply_message_box_style(msg)
            result = msg.exec()

            if result == QMessageBox.Yes:
                self.load_custom_folders()
                self.load_recent_folders()
                self.theme_mode = settings.get("theme_mode", "system")
                self.show_notification("Settings loaded from application directory.")
            else:
                self.set_default_settings()
                self.show_notification("Default settings applied.")

        self.apply_theme()
        self.update_folder_buttons()
        self.show_current_image(self.filtered_files)

    def set_default_settings(self):
        print("[DEBUG] Using JSON-based set_default_settings")
        settings = {
            "first_run": False,
            "folder_names": ["Folder A", "Folder B", "Folder C", "Folder D", "Folder E"],
            "folder_paths": ["output/A", "output/B", "output/C", "output/D", "output/E"],
            "recent_folders": [],
            "theme_mode": "system",
            "custom_theme": {
                "bg_color": "#121212",
                "text_color": "#FFFFFF",
                "btn_bg": "#2e2e2e",
                "btn_hover": "#444444",
                "label_bg": "#1a1a1a",
                "menu_bg": "#1a1a1a",
                "menu_text": "#FFFFFF"
            }
        }
        save_settings(settings)
        self.load_custom_folders()
        self.load_recent_folders()
        self.theme_mode = "system"
        self.current_index = 0
        self.filtered_files = []
        self.image_files = []
        self.nav_history = []
        self.history = []
        save_history(self.history)
        self.show_current_image(self.filtered_files)

    def open_custom_theme_editor(self):
        dialog = CustomThemeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            settings = load_settings()
            settings["custom_theme"] = {
                "bg_color": dialog.bg_color,
                "text_color": dialog.text_color,
                "btn_bg": dialog.btn_bg,
                "btn_hover": dialog.btn_hover,
                "label_bg": dialog.label_bg,
                "menu_bg": dialog.menu_bg,
                "menu_text": dialog.menu_text
            }
            save_settings(settings)
            self.set_theme_mode("custom")

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
            self.show_loading(True)
            source_folder = os.path.dirname(path)
            self.update_recent_folders(source_folder)
            self.image_files = [path]
            self.thread = ImageValidationThread(self.image_files)
            self.thread.finished.connect(lambda: self.process_valid_images_and_update_ui(source_folder))
            self.thread.start()
        else:
            self.show_loading(False)
            msg = QMessageBox()
            msg.setWindowTitle("Invalid Drop")
            msg.setText("Only folders or image files are supported.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()

    def import_folder_common(self, folder_path):
        self.show_loading(True)
        self.position_stack.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.update_recent_folders(folder_path)
        if folder_path in self.image_cache:
            self.image_files = self.image_cache[folder_path]
            self.current_index = 0
            self.nav_history = []
            self.source_info = f"Files successfully imported from: {folder_path}"
            self.apply_filter()
            self.show_notification(self.source_info)
            self.show_current_image(self.filtered_files)
            self.show_loading(False)
            self.position_stack.setCurrentIndex(0)
            return
        supported_formats = ('*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.webp',
                            '*.tiff', '*.heic', '*.heif', '*.raw', '*.psd')
        all_files = []
        for ext in supported_formats:
            all_files.extend(glob(os.path.join(folder_path, ext)))
        if not all_files:
            self.show_loading(False)
            self.position_stack.setCurrentIndex(0)
            msg = QMessageBox()
            msg.setWindowTitle("No Images")
            msg.setText("No valid images found in this folder.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return
        self.image_files = all_files
        self.thread = ImageValidationThread(all_files)
        self.thread.progress_updated.connect(self.progress_bar.setValue)
        self.thread.finished.connect(lambda: self.process_valid_images_and_update_ui(folder_path))
        self.thread.start()

    def process_valid_images(self):
        self.image_files = self.thread.valid_images
        if len(self.image_files) == 0:
            msg = QMessageBox()
            msg.setWindowTitle("No Images")
            msg.setText("No valid images found in this folder.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        self.current_index = 0
        self.show_current_image()

    def get_images_from_folder(self, folder):
        supported_formats = ('*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.webp', '*.tiff', '*.heic', '*.heif', '*.raw', '*.psd')
        all_files = []
        for ext in supported_formats:
            all_files.extend(glob(os.path.join(folder, ext)))
        return all_files

    def is_image_file(self, path):
        supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.heic', '.heif', '.raw', '.psd')
        ext = os.path.splitext(path)[1].lower()
        return ext in supported_formats

    def apply_theme(self):
        settings = load_settings()
        palette = QApplication.palette()
        base_color = palette.window().color()
        brightness = base_color.red() * 0.299 + base_color.green() * 0.587 + base_color.blue() * 0.114
        is_system_dark = brightness < 128

        use_dark = False
        if self.theme_mode == "dark":
            use_dark = True
        elif self.theme_mode == "light":
            use_dark = False
        elif self.theme_mode == "system":
            use_dark = is_system_dark
        elif self.theme_mode == "custom":
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
        else:
            use_dark = self.is_system_dark()

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
            main_border_color = custom_theme.get("main_border_color", "#00FFFF")
            next_border_color = custom_theme.get("next_border_color", "#FF00FF")
        else:
            bg_color = "#1e1e1e" if is_dark else "#ffffff"
            text_color = "white" if is_dark else "black"
            main_border_color = "#00FFFF" if is_dark else "#FF4500"
            next_border_color = "#FF00FF" if is_dark else "#9932CC"
            next_shadow = "0 0 12px rgba(255, 0, 255, 0.7)" if is_dark else "0 0 12px rgba(153, 50, 204, 0.7)"

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
        text_width = font_metrics.horizontalAdvance(text) + 20
        min_width = 300
        max_width = 800
        label_width = max(min_width, min(max_width, text_width))

        label_height = 60
        x = (self.width() - label_width) // 2
        y = self.height() - 150
        self.notification_label.setGeometry(x, y, label_width, label_height)

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

    def process_valid_images_and_update_ui(self, folder_path):
        self.image_files = self.thread.valid_images
        if not self.image_files:
            self.show_loading(False)
            self.position_stack.setCurrentIndex(0)
            msg = QMessageBox()
            msg.setWindowTitle("No Images")
            msg.setText("No valid images found in this folder.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        self.image_cache[folder_path] = self.image_files.copy()
        
        self.current_index = 0
        self.nav_history = []
        self.source_info = f"Files successfully imported from: {folder_path}"
        self.apply_filter()
        self.show_notification(self.source_info)
        self.show_current_image(self.filtered_files)
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
        self.filter_combo.addItems([".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".heic", ".heif", ".raw", ".psd"])
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
        import_action.setToolTip("Import images from folder")
        import_action.triggered.connect(self.import_folder)
        file_menu.addAction(import_action)
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
        settings_menu.addAction(settings_action)
        settings_menu.addAction(export_settings_action)
        settings_menu.addAction(import_settings_action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.setIcon(QIcon(resource_path("assets/icons/about.png")))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        update_action = QAction("Check for Updates", self)
        update_action.setIcon(QIcon(resource_path("assets/icons/update.png")))
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

        for i in range(5):
            shortcut = QShortcut(QKeySequence(str(i + 1)), self)
            shortcut.activated.connect(lambda idx=i: self.move_to_custom_folder(self.folder_paths[idx]))
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
        current_version = AboutDialog.VERSION  # Use version from AboutDialog
        api_url = "https://api.github.com/repos/Zy0x/Image-Sorter/releases/latest"
        try:
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            release_info = response.json()
            latest_version = release_info.get("tag_name", "").lstrip("v")  # Remove 'v' prefix, e.g., 'v1.1-Stable' -> '1.1-Stable'
            release_notes = release_info.get("body", "No release notes provided.")
            download_url = release_info.get("html_url", "")
            
            dialog = UpdateDialog(self, current_version, latest_version, release_notes, download_url)
            dialog.exec_()
            
        except requests.RequestException as e:
            print(f"[DEBUG] Error checking for updates: {e}")
            dialog = UpdateDialog(self, current_version, None, "Failed to check for updates. Please check your internet connection.")
            dialog.exec_()

    def load_images_from_folder(self, folder_path):
        if not os.path.isdir(folder_path):
            return

        self.show_loading(True)

        supported_formats = ('*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.webp',
                            '*.tiff', '*.heic', '*.heif', '*.raw', '*.psd')
        all_files = []
        for ext in supported_formats:
            all_files.extend(glob(os.path.join(folder_path, ext)))

        if not all_files:
            self.show_loading(False)
            msg = QMessageBox()
            msg.setWindowTitle("No Images")
            msg.setText("No valid images found in this folder.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        self.thread = ImageValidationThread(all_files)
        self.thread.finished.connect(lambda: self.process_valid_images_and_update_ui(folder_path))
        self.thread.start()
        self.image_files = all_files
        self.apply_filter()

        self.update_recent_folders(folder_path)

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

    def toggle_dark_mode(self, enable):
        self.dark_mode = enable
        settings.setValue("theme_mode", self.theme_mode)
        self.apply_theme()

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
        info_dialog.exec_()

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

        light_colors = ["#FFD1DC", "#C1E1C1", "#FFE082", "#B3CDE0", "#F8C8DC"]
        dark_colors = ["#4A2C5A", "#3A5F3A", "#6B5A2C", "#3A4B5D", "#6B3F4D"]

        for i, (label, path) in enumerate(zip(self.folder_names, self.folder_paths)):
            btn = QPushButton(f"{label}")
            btn.setIcon(QIcon(resource_path("assets/icons/folder.png")))
            btn.setIconSize(QSize(16, 16))
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
            label_width = 800
            label_height = 60
            x = (self.width() - label_width) // 2
            # Keep notification below the fixed info area (30px height)
            y = 30 + 10  # 30px for info area + 10px margin
            self.notification_label.setGeometry(x, y, label_width, label_height)

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

    def import_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path:
            return

        self.import_folder_common(folder_path)

    def process_valid_images_and_hide_loading(self):
        self.process_valid_images()
        self.show_loading(False)

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
        print(f"[DEBUG] Checking history for path: {normalized_path}, history: {self.history}")
        for src, dest in reversed(self.history):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_dest = os.path.normcase(os.path.normpath(dest))
            if normalized_path == norm_src:
                print(f"[DEBUG] Found new path for {path}: {dest} (matched src)")
                return dest
            elif normalized_path == norm_dest:
                print(f"[DEBUG] Found new path for {path}: {dest} (matched dest)")
                return dest
        print(f"[DEBUG] No new path for {path}")
        return None

    def show_current_image(self, files=None):
        self.position_stack.setCurrentIndex(0)
        if files is None:
            files = self.filtered_files or self.image_files
        if not files:
            self.image_label.setText("No Image Loaded")
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

        moved_status = f" <span style='color: red; font-weight: bold;'>(moved to {folder_name})</span>" if is_moved else ""
        self.file_info_label.setText(f"{filename}{moved_status}")
        self.file_info_label.setToolTip(self.file_info_label.text())

        current_pos = self.current_index + 1
        total_files = len(files)
        self.position_info_label.setText(f"{current_pos}/{total_files}")

        for child in self.image_label.findChildren(QLabel):
            child.deleteLater()

        if os.path.exists(new_path):
            pixmap = QPixmap(new_path)
            if not pixmap.isNull():
                resized_pixmap = resize_image(pixmap)
                self.image_label.setPixmap(resized_pixmap)
                self.image_label.setFixedSize(resized_pixmap.size())
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
                next_pixmap = QPixmap(new_next_path)
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
        print(f"[DEBUG] Checking folder for path: {normalized_path}")
        for src, dest in reversed(self.history):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_dest = os.path.normcase(os.path.normpath(dest))
            dest_folder = os.path.dirname(dest)
            print(f"[DEBUG] Comparing with src: {norm_src}, dest: {norm_dest}")
            if normalized_path in (norm_src, norm_dest):
                for i, folder_path in enumerate(self.folder_paths):
                    norm_folder_path = os.path.normcase(os.path.normpath(folder_path))
                    if os.path.normcase(os.path.normpath(dest_folder)).startswith(norm_folder_path):
                        print(f"[DEBUG] Matched folder: {self.folder_names[i]}")
                        return self.folder_names[i]
                print(f"[DEBUG] Using basename: {os.path.basename(os.path.normpath(dest_folder))}")
                return os.path.basename(os.path.normpath(dest_folder))
        print(f"[DEBUG] No folder found for path: {normalized_path}")
        return None

    def find_valid_next_index(self, start_index, files=None):
        if files is None:
            files = self.filtered_files or self.image_files
        for i in range(start_index + 1, len(files)):
            path = files[i]
            new_path = self.get_new_path_from_history(path) or path
            if os.path.exists(new_path):
                return i
        return None

    def find_valid_previous_index(self, start_index, files=None):
        if files is None:
            files = self.filtered_files or self.image_files
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
            # Bersihkan nav_history dari indeks yang tidak valid
            self.nav_history = [i for i in self.nav_history if i < len(self.filtered_files)]
            self.current_index = valid_index
            self.show_current_image(self.filtered_files)
        else:
            self.show_notification("No valid next image.")

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

    def move_to_custom_folder(self, folder_path):
        if not self.image_files or self.current_index >= len(self.filtered_files):
            self.show_notification("No image to move.")
            return

        src_path = self.image_files[self.current_index]
        if not os.path.exists(src_path) and not self.get_new_path_from_history(src_path):
            self.show_notification("Source file not found.")
            self.show_next()
            return

        # Default paths
        default_paths = ["output/A", "output/B", "output/C", "output/D", "output/E"]
        norm_folder_path = os.path.normcase(os.path.normpath(folder_path))

        # Check if folder is default
        is_default = norm_folder_path in [os.path.normcase(os.path.normpath(p)) for p in default_paths]

        if is_default:
            dialog = FolderSettingsDialog(self)
            if dialog.exec() != QDialog.Accepted:
                self.show_notification("Move cancelled. Please set destination folder.")
                return

            self.load_custom_folders()
            self.update_folder_buttons()

            for i, path in enumerate(self.folder_paths):
                if os.path.normcase(os.path.normpath(path)) == norm_folder_path:
                    folder_path = self.folder_paths[i]
                    break
            else:
                self.show_notification("Destination folder invalid after settings.")
                return

        dest_folder = folder_path
        if not dest_folder:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Destination folder not selected.")
            msg.setIcon(QMessageBox.Warning)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        current_dest = self.get_new_path_from_history(src_path)
        norm_dest_folder = os.path.normcase(os.path.normpath(dest_folder))

        if current_dest:
            current_dest_folder = os.path.normcase(os.path.normpath(os.path.dirname(current_dest)))
            if norm_dest_folder == current_dest_folder:
                folder_name = os.path.basename(os.path.normpath(dest_folder))
                for name, path in zip(self.folder_names, self.folder_paths):
                    if os.path.normcase(os.path.normpath(path)) == norm_dest_folder:
                        folder_name = name
                        break
                self.show_notification(f"File already in {folder_name}.")
                return

        os.makedirs(dest_folder, exist_ok=True)
        filename = os.path.basename(src_path)
        dest_path = os.path.join(dest_folder, filename)

        try:
            source_to_move = current_dest if current_dest and os.path.exists(current_dest) else src_path
            if not os.path.exists(source_to_move):
                raise FileNotFoundError(f"File {source_to_move} not found.")

            shutil.move(source_to_move, dest_path)

            # Update history
            self.history = [(s, d) for s, d in self.history if os.path.normcase(os.path.normpath(s)) != os.path.normcase(os.path.normpath(src_path))]
            self.history.append((src_path, dest_path))
            save_history(self.history)  # Save history

            self.log_message(f"Moved: {source_to_move} → {dest_path}")

            # Simpan indeks saat ini sebelum apply_filter
            current_index_before_move = self.current_index

            self.apply_filter()

            # Pulihkan current_index ke indeks berikutnya yang valid
            self.current_index = self.find_valid_next_index(current_index_before_move, self.filtered_files)
            if self.current_index is None:
                self.current_index = min(current_index_before_move, len(self.filtered_files) - 1) if self.filtered_files else 0

            folder_name = os.path.basename(os.path.normpath(folder_path))
            for name, path in zip(self.folder_names, self.folder_paths):
                if os.path.normcase(os.path.normpath(path)) == norm_dest_folder:
                    folder_name = name
                    break

            is_second_move = current_dest is not None

            # Perbarui UI dengan gambar berikutnya
            self.nav_history.append(current_index_before_move)
            self.show_current_image(self.filtered_files)

            if is_second_move:
                self.show_notification(f"Image successfully moved to {folder_name}")
            else:
                self.show_notification(f"Image successfully moved to {folder_name}")

        except Exception as e:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Could not move file:\n{str(e)}")
            msg.setIcon(QMessageBox.Critical)
            self.apply_message_box_style(msg)
            msg.exec()

    def undo_action(self):
        if not self.history:
            msg = QMessageBox()
            msg.setWindowTitle("Undo Info")
            msg.setText("No action to undo.")
            msg.setIcon(QMessageBox.Information)
            self.apply_message_box_style(msg)
            msg.exec()
            return

        src_path, dest_path = self.history.pop()
        self.validate_history()
        save_history(self.history)  # Save history after undo
        
        try:
            if not os.path.exists(dest_path):
                raise FileNotFoundError(f"Destination file {dest_path} not found.")
            
            shutil.move(dest_path, src_path)
            self.log_message(f"Undo: {dest_path} → {src_path}")
            
            # No need to update image_files since src_path remains
            # Update filtered_files by reapplying filter
            self.apply_filter()
            
            # Find index of undone file in filtered_files
            for i, path in enumerate(self.filtered_files):
                if os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(src_path)):
                    self.current_index = i
                    break
            else:
                # If file not in filtered_files, use closest valid index
                self.current_index = min(self.current_index, len(self.filtered_files) - 1) if self.filtered_files else 0
            
            # Clean nav_history for invalid indices
            self.nav_history = [i for i in self.nav_history if i < len(self.filtered_files)]
            filename = os.path.basename(src_path)
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
            # Re-add to history if failed
            self.history.append((src_path, dest_path))
        self.validate_history()

    def skip_image(self):
        self.nav_history.append(self.current_index)
        self.show_next()

    def export_log(self):
        if not self.log_buffer:
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
                for line in self.log_buffer:
                    f.write(line + "\n")
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

    def show_about(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec_()

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
        current_path = None
        if self.filtered_files and 0 <= self.current_index < len(self.filtered_files):
            current_path = self.filtered_files[self.current_index]
        
        self.filtered_files = [
            path for path in self.image_files
            if selected_ext == "All Files" or path.lower().endswith(selected_ext.lower())
        ]
        
        print(f"[DEBUG] filtered_files: {len(self.filtered_files)} items")
        
        # Coba pertahankan gambar saat ini jika masih ada dalam filtered_files
        if current_path and current_path in self.filtered_files:
            self.current_index = self.filtered_files.index(current_path)
        else:
            # Jika gambar saat ini tidak ada, cari indeks berikutnya yang valid
            self.current_index = 0
            if self.filtered_files:
                valid_index = self.find_valid_next_index(-1, self.filtered_files)
                if valid_index is not None:
                    self.current_index = valid_index
                else:
                    # Jika tidak ada indeks valid, cari file yang ada
                    for i, path in enumerate(self.filtered_files):
                        if os.path.exists(path) or self.get_new_path_from_history(path):
                            self.current_index = i
                            break
        self.position_stack.setCurrentIndex(0)  # Show position label
        if not self.filtered_files:
            self.image_label.setText("No images match the filter.")
            self.next_image_label.setText("Next: None")
            self.file_info_label.setText("No image loaded.")
            self.position_info_label.setText("")
        else:
            self.show_current_image(self.filtered_files)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ImageSorterApp()
    window.show()
    sys.exit(app.exec())