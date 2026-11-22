"""Thin application entrypoint and public module facade for ImageSorter."""

import os
import sys

from PySide6.QtWidgets import QApplication

import core.config as _cfg
from core.config import (
    ALL_SLOT_LETTERS,
    APP_NAME,
    APP_VERSION,
    DEFAULT_CUSTOM_THEME,
    DEFAULT_FOLDER_NAMES,
    DEFAULT_FOLDER_PATHS,
    DEFAULT_SETTINGS,
    load_settings,
    resource_path,
    save_settings,
)
from core.file_ops import (
    get_unique_destination,
    natural_sort_key,
    reveal_in_file_explorer,
    scan_image_files,
    send_to_recycle_bin,
)
from core.history import HistoryStore, load_history, save_history
from core.workers import DuplicateScanThread, FolderScanThread, UpdateCheckThread, is_newer_version
from ui.dialogs import (
    AboutDialog,
    CustomThemeDialog,
    FolderSettingsDialog,
    ImagePreviewDialog,
    JumpToMediaDialog,
    RapidMoveSettingsDialog,
    ShortcutsGuideDialog,
    UpdateDialog,
)
from ui.main_window import ImageSorterApp
from ui.widgets import LoadingOverlay, MediaHudOverlay, ToastNotification


def main() -> int:
    """Parse CLI args, configure Qt runtime, and launch ImageSorterApp."""
    if "--debug" in sys.argv:
        _cfg._DEBUG_ENABLED = True

    initial_folder = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and os.path.isdir(arg):
            initial_folder = os.path.abspath(arg)
            break

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")

    window = ImageSorterApp(initial_folder=initial_folder)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
