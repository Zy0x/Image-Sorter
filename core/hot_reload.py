"""Multi-module recursive live Hot-Reload watcher across all Python packages and settings.json."""

import json
import os
import subprocess
import sys
import time
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, QTimer

from core.config import (
    file_signature,
    get_app_base_dir,
    get_config_dir,
    get_config_path,
    get_last_internal_settings_sig,
)

_WATCHED_SUBDIRS = ("core", "media", "ui", "utils")


def discover_watched_python_files() -> List[str]:
    """Discover all Python source files in main.py and modular packages for live reload."""
    root = get_app_base_dir()
    files = []
    entry = os.path.join(root, "main.py")
    if os.path.isfile(entry):
        files.append(entry)
    for sub in _WATCHED_SUBDIRS:
        sub_dir = os.path.join(root, sub)
        if not os.path.isdir(sub_dir):
            continue
        for cur, dirs, filenames in os.walk(sub_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
            for fn in filenames:
                if fn.endswith(".py"):
                    files.append(os.path.join(cur, fn))
    return sorted(files)


class HotReloadWatcher(QObject):
    """Watches every .py file across the modular tree and settings.json without broken mid-save reloads."""

    def __init__(
        self,
        parent=None,
        can_reload: Optional[Callable[[], bool]] = None,
        on_external_settings: Optional[Callable[[], None]] = None,
        on_trigger_reload: Optional[Callable[[], None]] = None,
        interval_ms: int = 700,
    ):
        super().__init__(parent)
        self._can_reload = can_reload or (lambda: True)
        self._on_external_settings = on_external_settings
        self._on_trigger_reload = on_trigger_reload
        self._watched_files = discover_watched_python_files()
        self._code_sigs = {p: file_signature(p) for p in self._watched_files}
        self._pending_reload = False
        self._settings_path = get_config_path()
        self._settings_sig = file_signature(self._settings_path)
        self._timer = None

        if not getattr(sys, "frozen", False) and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self._timer = QTimer(self)
            self._timer.setInterval(interval_ms)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    @staticmethod
    def state_file_path() -> str:
        return os.path.join(get_config_dir(), ".hot_reload_state.json")

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _tick(self) -> None:
        if not self._can_reload():
            return

        cur_settings_sig = file_signature(self._settings_path)
        if cur_settings_sig and cur_settings_sig != self._settings_sig:
            self._settings_sig = cur_settings_sig
            if cur_settings_sig != get_last_internal_settings_sig() and self._on_external_settings:
                self._on_external_settings()

        current_files = discover_watched_python_files()
        if set(current_files) != set(self._watched_files):
            self._watched_files = current_files
            for p in current_files:
                self._code_sigs.setdefault(p, None)

        changed = False
        for path in self._watched_files:
            sig = file_signature(path)
            if sig and sig != self._code_sigs.get(path):
                self._code_sigs[path] = sig
                changed = True

        if changed:
            self._pending_reload = True
            return

        if self._pending_reload:
            self._pending_reload = False
            for path in self._watched_files:
                try:
                    with open(path, "rb") as f:
                        compile(f.read(), path, "exec")
                except Exception as e:
                    print(f"[HOT-RELOAD] Waiting for valid syntax in {path}: {e}")
                    return
            if self._on_trigger_reload:
                self._on_trigger_reload()

    @classmethod
    def write_state_and_spawn(cls, state: dict) -> bool:
        """Persist session snapshot and launch replacement process at project main.py."""
        try:
            with open(cls.state_file_path(), "w", encoding="utf-8") as f:
                json.dump(state, f)
        except OSError:
            pass
        entry_py = os.path.join(get_app_base_dir(), "main.py")
        try:
            subprocess.Popen([sys.executable, entry_py, *sys.argv[1:]])
            return True
        except OSError as e:
            print(f"[HOT-RELOAD] Failed to spawn new instance: {e}")
            return False

    @classmethod
    def pop_recent_state(cls, max_age_s: float = 20.0) -> Optional[dict]:
        """Read and immediately delete persisted hot-reload state if still fresh."""
        path = cls.state_file_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            state = None
        try:
            os.remove(path)
        except OSError:
            pass
        if not state or time.time() - state.get("timestamp", 0) > max_age_s:
            return None
        return state
