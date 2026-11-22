"""In-memory media queue, filter evaluator, valid-index navigation, and duplicate group model."""

from collections import deque
import os
from typing import Dict, List, Optional, Tuple

from core.history import HistoryStore
from media.formats import is_video_file

_ANIMATED_EXTS = (".gif", ".webp", ".apng", ".avif")


class MediaQueueModel:
    """Tracks loaded media list, active filter results, navigation cursor, and duplicate clusters."""

    def __init__(self, history_store: HistoryStore):
        self.history_store = history_store
        self.all_files: List[str] = []
        self.filtered_files: List[str] = []
        self.current_index: int = 0
        self.nav_history: deque = deque(maxlen=500)
        self.duplicate_norms: set = set()
        self.duplicate_groups: List[List[str]] = []
        self.duplicate_group_lookup: Dict[str, Tuple[int, int]] = {}

    @staticmethod
    def _norm(path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def clear_duplicates(self) -> None:
        self.duplicate_norms.clear()
        self.duplicate_groups.clear()
        self.duplicate_group_lookup.clear()

    def set_files(self, files: List[str]) -> None:
        self.all_files = list(files or [])
        self.filtered_files = []
        self.current_index = 0
        self.nav_history.clear()
        self.clear_duplicates()

    def resolve_duplicate_targets(self) -> List[Tuple[str, str]]:
        """Return (source_path, existing_actual_path) pairs for all active files."""
        targets = []
        for src in self.all_files:
            actual = self.history_store.resolve_actual_path(src)
            if os.path.exists(actual):
                targets.append((src, actual))
        return targets

    def populate_duplicate_results(self, groups_actual, actual_to_srcs) -> None:
        """Index detected duplicate/similar file clusters back to original source paths."""
        self.clear_duplicates()
        for g_idx, g_actuals in enumerate(groups_actual, start=1):
            src_group = []
            for act in g_actuals:
                norm_act = self._norm(act)
                for src in actual_to_srcs.get(norm_act, [act]):
                    src_group.append(src)
            if len(src_group) > 1:
                self.duplicate_groups.append(src_group)
                for s in src_group:
                    ns = self._norm(s)
                    self.duplicate_norms.add(ns)
                    self.duplicate_group_lookup[ns] = (g_idx, len(src_group))

    def apply_filter(self, selected_filter: str, hide_moved: bool, preserve_current: bool = True) -> None:
        """Rebuild filtered_files from all_files and update current_index cleanly."""
        previous_path = (
            self.filtered_files[self.current_index]
            if preserve_current and 0 <= self.current_index < len(self.filtered_files)
            else None
        )

        if selected_filter == "All Files":
            candidates = list(self.all_files)
        elif selected_filter == "All Videos":
            candidates = [p for p in self.all_files if is_video_file(p)]
        elif selected_filter == "All Images":
            candidates = [p for p in self.all_files if not is_video_file(p)]
        elif selected_filter == "Animated / GIF":
            candidates = [p for p in self.all_files if p.lower().endswith(_ANIMATED_EXTS)]
        elif selected_filter == "Duplicates Only":
            candidates = [p for p in self.all_files if self._norm(p) in self.duplicate_norms]
        else:
            wanted = selected_filter.lower()
            candidates = [p for p in self.all_files if p.lower().endswith(wanted)]

        if hide_moved and self.history_store.cache:
            self.filtered_files = [
                p for p in candidates if not self.history_store.is_moved(p)
            ]
        else:
            self.filtered_files = candidates

        if not preserve_current:
            return

        if previous_path and previous_path in self.filtered_files:
            self.current_index = self.filtered_files.index(previous_path)
        elif self.filtered_files:
            if self.current_index >= len(self.filtered_files):
                self.current_index = 0
            cur_actual = self.history_store.resolve_actual_path(self.filtered_files[self.current_index])
            if not os.path.exists(cur_actual):
                valid_idx = self.find_valid_next_index(-1)
                if valid_idx is not None:
                    self.current_index = valid_idx
        else:
            self.current_index = 0

    def find_valid_next_index(self, start_index: int, files=None) -> Optional[int]:
        items = self.filtered_files if files is None else files
        for i in range(start_index + 1, len(items)):
            actual = self.history_store.resolve_actual_path(items[i])
            if os.path.exists(actual):
                return i
        return None

    def find_valid_previous_index(self, start_index: int, files=None) -> Optional[int]:
        items = self.filtered_files if files is None else files
        for i in range(start_index - 1, -1, -1):
            p = items[i]
            if os.path.exists(p) or self.history_store.get_new_path(p):
                return i
        return None

    def find_next_unmoved_index(self, start_index: int, files=None) -> Optional[int]:
        items = self.filtered_files if files is None else files
        for i in range(start_index + 1, len(items)):
            p = items[i]
            if not self.history_store.is_moved(p) and os.path.exists(p):
                return i
        return None

    def current_paths(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.filtered_files or not (0 <= self.current_index < len(self.filtered_files)):
            return None, None
        src = self.filtered_files[self.current_index]
        actual = self.history_store.resolve_actual_path(src)
        return src, actual
