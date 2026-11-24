"""Centralized application configuration, atomic JSON settings IO, paths, and logging."""

import copy
import json
import os
import sys
from datetime import datetime

APP_NAME = "ImageSorter"
APP_VERSION = "2.1.26-Stable"

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
    "hide_moved": False,
    "folder_names": list(DEFAULT_FOLDER_NAMES),
    "folder_paths": list(DEFAULT_FOLDER_PATHS),
    "recent_folders": [],
    "last_opened_folder": "",
    "theme_mode": "system",
    "rapid_move_interval": RAPID_MOVE_DEFAULT_MS,
    "video_muted": False,
    "video_volume": 0.85,
    "sort_by": "name",
    "sort_order": "asc",
    "show_filmstrip": True,
    "auto_rename_enabled": False,
    "auto_rename_pattern": "{folder}_{index:04d}",
    "flagged_files": [],
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


def read_recent_event_log(max_lines: int = 500) -> list:
    """Read up to max_lines recent activity entries from persistent event.log."""
    path = get_event_log_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\r\n") for ln in f if ln.strip()]
        return lines[-max_lines:]
    except OSError as e:
        debug_log(f"Error reading event.log: {e}")
        return []


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


def normalize_settings(raw: dict, first_run_default: bool = True) -> dict:
    """Validate, clamp, pad 9-slot lists, and deduplicate recent_folders in a settings dictionary."""
    merged = default_settings_copy(first_run=first_run_default)
    if not isinstance(raw, dict):
        return merged

    for key, value in raw.items():
        if key != "custom_theme":
            merged[key] = copy.deepcopy(value)

    merged["first_run"] = bool(raw.get("first_run", first_run_default))
    merged["folder_slot_count"] = clamp_folder_slots(raw.get("folder_slot_count", DEFAULT_FOLDER_SLOTS))
    merged["include_subfolders"] = bool(raw.get("include_subfolders", False))
    merged["hide_moved"] = bool(raw.get("hide_moved", False))

    raw_names = raw.get("folder_names")
    names = [str(x).strip() for x in raw_names] if isinstance(raw_names, list) else []
    padded_names = []
    for i in range(MAX_FOLDER_SLOTS):
        val = names[i] if i < len(names) and names[i] else DEFAULT_FOLDER_NAMES[i]
        padded_names.append(val)
    merged["folder_names"] = padded_names

    raw_paths = raw.get("folder_paths")
    paths = [str(x).strip() for x in raw_paths] if isinstance(raw_paths, list) else []
    padded_paths = []
    for i in range(MAX_FOLDER_SLOTS):
        val = paths[i] if i < len(paths) and paths[i] else DEFAULT_FOLDER_PATHS[i]
        padded_paths.append(val)
    merged["folder_paths"] = padded_paths

    raw_recent = raw.get("recent_folders")
    dedup_recent = []
    seen_recent = set()
    if isinstance(raw_recent, list):
        for item in raw_recent:
            if isinstance(item, str) and item.strip():
                norm_p = os.path.normpath(item.strip())
                key_p = os.path.normcase(os.path.abspath(norm_p))
                if key_p not in seen_recent:
                    seen_recent.add(key_p)
                    dedup_recent.append(norm_p)
    merged["recent_folders"] = dedup_recent[:10]

    last_folder = raw.get("last_opened_folder", "")
    if not isinstance(last_folder, str) or not last_folder.strip():
        last_folder = dedup_recent[0] if dedup_recent else ""
    else:
        last_folder = os.path.normpath(last_folder.strip())
    merged["last_opened_folder"] = last_folder

    theme_mode = raw.get("theme_mode", "system")
    merged["theme_mode"] = theme_mode if theme_mode in ("system", "dark", "light", "custom") else "system"

    interval_raw = raw.get("rapid_move_interval", raw.get("rapid_move_interval_ms", RAPID_MOVE_DEFAULT_MS))
    merged["rapid_move_interval"] = clamp_rapid_interval(interval_raw)
    merged.pop("rapid_move_interval_ms", None)

    merged["video_muted"] = bool(raw.get("video_muted", False))
    try:
        vol = float(raw.get("video_volume", 0.85))
    except (TypeError, ValueError):
        vol = 0.85
    merged["video_volume"] = max(0.0, min(1.0, vol))

    sort_by = str(raw.get("sort_by", "name")).lower().strip()
    merged["sort_by"] = sort_by if sort_by in ("name", "date", "size", "ext") else "name"

    sort_order = str(raw.get("sort_order", "asc")).lower().strip()
    merged["sort_order"] = sort_order if sort_order in ("asc", "desc") else "asc"

    merged["show_filmstrip"] = bool(raw.get("show_filmstrip", True))
    merged["auto_rename_enabled"] = bool(raw.get("auto_rename_enabled", False))

    arp = str(raw.get("auto_rename_pattern", "{folder}_{index:04d}")).strip()
    merged["auto_rename_pattern"] = arp if arp else "{folder}_{index:04d}"

    raw_flagged = raw.get("flagged_files")
    dedup_flagged = []
    seen_flagged = set()
    if isinstance(raw_flagged, list):
        for item in raw_flagged:
            if isinstance(item, str) and item.strip():
                norm_p = os.path.normpath(item.strip())
                key_p = os.path.normcase(os.path.abspath(norm_p))
                if key_p not in seen_flagged:
                    seen_flagged.add(key_p)
                    dedup_flagged.append(norm_p)
    merged["flagged_files"] = dedup_flagged

    ct = copy.deepcopy(DEFAULT_CUSTOM_THEME)
    raw_ct = raw.get("custom_theme")
    if isinstance(raw_ct, dict):
        for k, v in raw_ct.items():
            if isinstance(v, str) and v.strip():
                ct[k] = v.strip()
    merged["custom_theme"] = ct
    return merged


def load_settings() -> dict:
    """Load settings.json merged and normalized cleanly with canonical defaults."""
    config_path = get_config_path()
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                return normalize_settings(loaded, first_run_default=True)
    except (json.JSONDecodeError, IOError, OSError) as e:
        debug_log(f"Error loading settings: {e}")
    return default_settings_copy(first_run=True)


def save_settings(settings: dict) -> None:
    """Persist normalized settings.json atomically and record its signature to skip self hot-reloads."""
    global _LAST_INTERNAL_SETTINGS_SIG
    config_path = get_config_path()
    normalized = normalize_settings(settings, first_run_default=False)
    if isinstance(settings, dict) and "first_run" in settings:
        normalized["first_run"] = bool(settings["first_run"])
    try:
        atomic_json_write(config_path, normalized, indent=4, ensure_ascii=False)
        _LAST_INTERNAL_SETTINGS_SIG = file_signature(config_path)
    except (IOError, OSError) as e:
        debug_log(f"Error saving settings: {e}")
