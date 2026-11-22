"""Centralized application configuration, atomic JSON settings IO, paths, and logging."""

import copy
import json
import os
import sys
from datetime import datetime

APP_NAME = "ImageSorter"
APP_VERSION = "2.1.21-Stable"

MIN_FOLDER_SLOTS = 3
MAX_FOLDER_SLOTS = 9
DEFAULT_FOLDER_SLOTS = 5
ALL_SLOT_LETTERS = ("A", "B", "C", "D", "E", "F", "G", "H", "I")
DEFAULT_FOLDER_NAMES = [f"Folder {ch}" for ch in ALL_SLOT_LETTERS]
DEFAULT_FOLDER_PATHS = [f"output/{ch}" for ch in ALL_SLOT_LETTERS]

RAPID_MOVE_MIN_MS = 50
RAPID_MOVE_MAX_MS = 1000
RAPID_MOVE_DEFAULT_MS = 200

DEFAULT_CUSTOM_THEME = {
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
    "next_shadow": "0 0 8px rgba(16, 185, 129, 0.45)",
}

DEFAULT_SETTINGS = {
    "first_run": True,
    "folder_slot_count": DEFAULT_FOLDER_SLOTS,
    "include_subfolders": False,
    "folder_names": DEFAULT_FOLDER_NAMES[:DEFAULT_FOLDER_SLOTS],
    "folder_paths": DEFAULT_FOLDER_PATHS[:DEFAULT_FOLDER_SLOTS],
    "recent_folders": [],
    "theme_mode": "system",
    "rapid_move_interval": RAPID_MOVE_DEFAULT_MS,
    "video_muted": False,
    "video_volume": 0.8,
    "custom_theme": copy.deepcopy(DEFAULT_CUSTOM_THEME),
}

_RESOLVED_CONFIG_DIR = None
_LAST_INTERNAL_SETTINGS_SIG = None
_DEBUG_ENABLED = "--debug" in sys.argv


def debug_log(message: str) -> None:
    """Emit structured debug output cleanly when --debug or offscreen diagnostics are active."""
    if _DEBUG_ENABLED:
        print(f"[DEBUG] {message}")


def default_settings_copy(first_run: bool = True) -> dict:
    """Return a deep copy of canonical default settings without mutating global constants."""
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    cfg["first_run"] = bool(first_run)
    return cfg


def get_app_base_dir() -> str:
    """Resolve repository/executable root directory (independent of current working directory)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path: str) -> str:
    """Resolve an asset file path safely across source runs and PyInstaller bundles."""
    base_dir = get_app_base_dir()
    candidate = os.path.join(base_dir, relative_path)
    if os.path.exists(candidate):
        return candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, relative_path)
        if os.path.exists(bundled):
            return bundled
    return candidate


def get_config_dir() -> str:
    """Resolve writable configuration directory ('config/' locally or %LOCALAPPDATA%/ImageSorter/config)."""
    global _RESOLVED_CONFIG_DIR
    if _RESOLVED_CONFIG_DIR is not None:
        os.makedirs(_RESOLVED_CONFIG_DIR, exist_ok=True)
        return _RESOLVED_CONFIG_DIR

    base_path = get_app_base_dir()
    local_config_dir = os.path.join(base_path, "config")
    portable = "--portable" in sys.argv
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
            chosen = os.path.join(appdata, APP_NAME, "config")
            os.makedirs(chosen, exist_ok=True)
    _RESOLVED_CONFIG_DIR = chosen
    return chosen


def get_config_path() -> str:
    """Return full path to settings.json."""
    return os.path.join(get_config_dir(), "settings.json")


def get_event_log_path() -> str:
    """Return full path to persistent activity event.log."""
    return os.path.join(get_config_dir(), "event.log")


def append_event_log(lines) -> None:
    """Append buffered log lines directly to event.log."""
    if not lines:
        return
    try:
        with open(get_event_log_path(), "a", encoding="utf-8") as f:
            for line in lines:
                f.write(f"{line}\n")
    except IOError as e:
        debug_log(f"Error writing to event.log: {e}")


def format_log_entry(message: str) -> str:
    """Format a timestamped activity entry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"


def file_signature(path: str):
    """Return (mtime_ns, size) tuple to detect external file modifications on disk."""
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def get_last_internal_settings_sig():
    """Return the file signature written by the last internal save_settings() call."""
    return _LAST_INTERNAL_SETTINGS_SIG


def clamp_rapid_interval(value) -> int:
    """Clamp rapid move interval into valid 50-1000 ms range."""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return RAPID_MOVE_DEFAULT_MS
    return max(RAPID_MOVE_MIN_MS, min(RAPID_MOVE_MAX_MS, numeric))


def clamp_folder_slots(count) -> int:
    """Clamp configured folder slot count into 3-9 range."""
    try:
        val = int(count)
    except (TypeError, ValueError):
        return DEFAULT_FOLDER_SLOTS
    return max(MIN_FOLDER_SLOTS, min(MAX_FOLDER_SLOTS, val))


def atomic_json_write(target_path: str, payload, indent=None, ensure_ascii: bool = True) -> None:
    """Write JSON atomically via .tmp + os.replace so crashes never corrupt state files."""
    tmp_path = f"{target_path}.tmp"
    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent, ensure_ascii=ensure_ascii)
    os.replace(tmp_path, target_path)


def load_settings() -> dict:
    """Load settings.json merged cleanly with canonical defaults."""
    config_path = get_config_path()
    defaults = default_settings_copy(first_run=True)
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key, value in defaults.items():
                    if key not in loaded:
                        loaded[key] = copy.deepcopy(value)
                ct_loaded = loaded.get("custom_theme")
                if not isinstance(ct_loaded, dict):
                    loaded["custom_theme"] = copy.deepcopy(DEFAULT_CUSTOM_THEME)
                else:
                    for ck, cv in DEFAULT_CUSTOM_THEME.items():
                        ct_loaded.setdefault(ck, cv)
                return loaded
    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"Error loading settings: {e}")
    return defaults


def save_settings(settings: dict) -> None:
    """Persist settings.json atomically and record its signature to skip self hot-reloads."""
    global _LAST_INTERNAL_SETTINGS_SIG
    config_path = get_config_path()
    try:
        atomic_json_write(config_path, settings, indent=4, ensure_ascii=True)
        _LAST_INTERNAL_SETTINGS_SIG = file_signature(config_path)
    except (IOError, OSError) as e:
        debug_log(f"Error saving settings: {e}")
