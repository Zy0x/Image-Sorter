"""Background worker QThreads and semantic version comparison utility."""

import re
import requests
from PySide6.QtCore import QThread, Signal

from core.config import debug_log
from core.file_ops import scan_image_files
from media.duplicates import find_duplicate_groups

_VERSION_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)(?:-([a-zA-Z]+))?$")


def is_newer_version(current: str, latest: str) -> bool:
    """Compare semantic strings like '2.1.20-Stable' vs '2.2.0-Beta' cleanly."""
    try:
        current_match = _VERSION_RE.match((current or "").strip())
        if not current_match:
            debug_log(f"Invalid current version format: {current}")
            return False
        current_num = current_match.group(1)
        current_qual = current_match.group(2) or "Stable"

        latest_match = _VERSION_RE.match((latest or "").strip())
        if not latest_match:
            debug_log(f"Invalid latest version format: {latest}")
            return False
        latest_num = latest_match.group(1)
        latest_qual = latest_match.group(2) or "Stable"

        current_parts = [int(x) for x in current_num.split(".")]
        latest_parts = [int(x) for x in latest_num.split(".")]
        while len(current_parts) < 3:
            current_parts.append(0)
        while len(latest_parts) < 3:
            latest_parts.append(0)

        if latest_parts != current_parts:
            return latest_parts > current_parts

        qualifier_priority = {"Stable": 3, "Beta": 2, "Alpha": 1}
        return qualifier_priority.get(latest_qual, 0) > qualifier_priority.get(current_qual, 0)
    except (ValueError, AttributeError) as e:
        debug_log(f"Error comparing versions: {e}")
        return False


class UpdateCheckThread(QThread):
    """Fetch latest GitHub release metadata asynchronously without blocking the UI thread."""

    update_checked = Signal(str, str, str)
    error_occurred = Signal(str)

    def __init__(self, parent=None, manual: bool = False):
        super().__init__(parent)
        self.manual = manual
        self.api_url = "https://api.github.com/repos/Zy0x/Image-Sorter/releases/latest"

    def run(self):
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            release_info = response.json()
            latest_version = release_info.get("tag_name", "").lstrip("v")
            release_notes = release_info.get("body", "No release notes provided.")
            download_url = release_info.get("html_url", "")
            self.update_checked.emit(latest_version, release_notes or "", download_url)
        except (requests.RequestException, ValueError) as e:
            self.error_occurred.emit(str(e))


class FolderScanThread(QThread):
    """Iterate and natural-sort massive directories in a background QThread."""

    progress_updated = Signal(int)

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


class DuplicateScanThread(QThread):
    """Compute perceptual 64-bit dHash clusters asynchronously across active media paths."""

    progress_updated = Signal(int, int)

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
