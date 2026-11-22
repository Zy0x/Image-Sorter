"""Move history persistence and synchronized O(1) lookup store for sorting & Undo."""

import json
import os
from typing import Dict, List, Optional, Tuple

from core.config import atomic_json_write, debug_log, get_config_dir


def get_history_path() -> str:
    """Return full path to persistent history.json."""
    return os.path.join(get_config_dir(), "history.json")


def save_history(history) -> None:
    """Persist move history atomically via temp file + os.replace."""
    history_path = get_history_path()
    try:
        atomic_json_write(history_path, history, indent=None, ensure_ascii=False)
    except (IOError, OSError) as e:
        debug_log(f"Error saving history: {e}")


def load_history() -> Tuple[List[Tuple[str, str]], Dict[str, str]]:
    """Load move history list and build normalized source-to-destination cache."""
    history_path = get_history_path()
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            history = [(s, d) for s, d in raw]
            cache = {
                os.path.normcase(os.path.normpath(s)): d
                for s, d in history
            }
            return history, cache
    except (json.JSONDecodeError, IOError, TypeError, ValueError) as e:
        debug_log(f"Error loading history: {e}")
    return [], {}


class HistoryStore:
    """Single source of truth keeping ordered move history list & O(1) lookup cache in lockstep."""

    def __init__(self):
        self.records, self.cache = load_history()
        self.dirty = False

    @staticmethod
    def _norm(path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def record_move(self, src_path: str, dest_path: str) -> None:
        """Record a successful move and keep only the latest entry per source path."""
        norm_src = self._norm(src_path)
        if norm_src in self.cache:
            self.records = [(s, d) for s, d in self.records if self._norm(s) != norm_src]
        self.records.append((src_path, dest_path))
        self.cache[norm_src] = dest_path
        self.dirty = True

    def pop_last(self) -> Optional[Tuple[str, str]]:
        """Pop the most recent move from history (caller handles filesystem restore)."""
        if not self.records:
            return None
        pair = self.records.pop()
        self.dirty = True
        return pair

    def push_back(self, src_path: str, dest_path: str) -> None:
        """Re-insert a popped entry (e.g., when Undo fails) without losing cache state."""
        self.records.append((src_path, dest_path))
        self.cache[self._norm(src_path)] = dest_path
        self.dirty = True

    def remove_source(self, src_path: str) -> None:
        """Remove all entries matching src_path from both list and cache."""
        norm_src = self._norm(src_path)
        if norm_src in self.cache:
            del self.cache[norm_src]
            self.records = [(s, d) for s, d in self.records if self._norm(s) != norm_src]
            self.dirty = True

    def clear_cache_entry(self, src_path: str) -> None:
        """Remove src_path from lookup cache after successful Undo."""
        norm_src = self._norm(src_path)
        if norm_src in self.cache:
            del self.cache[norm_src]

    def get_new_path(self, src_path: str) -> Optional[str]:
        """Return current moved destination path for src_path, or None if unmoved."""
        return self.cache.get(self._norm(src_path), None)

    def is_moved(self, src_path: str) -> bool:
        """Return True if src_path has an active recorded move destination."""
        return self._norm(src_path) in self.cache

    def resolve_actual_path(self, src_path: str) -> str:
        """Return destination path if moved, otherwise original src_path."""
        return self.get_new_path(src_path) or src_path

    def get_folder_name(self, src_path: str, folder_names, folder_paths) -> Optional[str]:
        """Resolve friendly destination slot label for a moved file."""
        dest_path = self.get_new_path(src_path)
        if not dest_path:
            return None
        dest_folder = os.path.dirname(dest_path)
        norm_dest_folder = self._norm(dest_folder)
        for i, folder_path in enumerate(folder_paths):
            norm_fp = self._norm(folder_path)
            if norm_dest_folder.startswith(norm_fp):
                return folder_names[i]
        return os.path.basename(os.path.normpath(dest_folder))

    def validate(self) -> None:
        """Deduplicate records by normalized source path and rebuild lookup cache cleanly."""
        seen = set()
        valid = []
        new_cache = {}
        for src, dest in self.records:
            ns = self._norm(src)
            if ns not in seen:
                seen.add(ns)
                valid.append((src, dest))
                new_cache[ns] = dest
        self.records = valid
        self.cache = new_cache

    def flush(self) -> None:
        """Flush history to disk immediately if dirty."""
        if self.dirty:
            save_history(self.records)
            self.dirty = False
