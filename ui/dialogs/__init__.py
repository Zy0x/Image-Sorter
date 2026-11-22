"""Studio Slate modal dialogs package."""

from ui.dialogs.info_dialogs import (
    AboutDialog,
    JumpToMediaDialog,
    ShortcutsGuideDialog,
    UpdateDialog,
    apply_studio_dialog_style,
    show_studio_message,
)
from ui.dialogs.preview_dialog import ImagePreviewDialog
from ui.dialogs.settings_dialogs import (
    CustomThemeDialog,
    FolderSettingsDialog,
    RapidMoveSettingsDialog,
)

__all__ = [
    "AboutDialog",
    "CustomThemeDialog",
    "FolderSettingsDialog",
    "ImagePreviewDialog",
    "JumpToMediaDialog",
    "RapidMoveSettingsDialog",
    "ShortcutsGuideDialog",
    "UpdateDialog",
    "apply_studio_dialog_style",
    "show_studio_message",
]
