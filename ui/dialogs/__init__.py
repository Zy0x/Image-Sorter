"""Studio Slate modal dialogs package."""

from ui.dialogs.info_dialogs import (
    AboutDialog,
    JumpToMediaDialog,
    SessionSummaryDialog,
    ShortcutsGuideDialog,
    UpdateDialog,
    apply_studio_dialog_style,
    show_studio_message,
)
from ui.dialogs.preview_dialog import ImagePreviewDialog
from ui.dialogs.settings_dialogs import (
    AutoRenameSettingsDialog,
    CustomThemeDialog,
    FolderSettingsDialog,
    RapidMoveSettingsDialog,
)

__all__ = [
    "AboutDialog",
    "AutoRenameSettingsDialog",
    "CustomThemeDialog",
    "FolderSettingsDialog",
    "ImagePreviewDialog",
    "JumpToMediaDialog",
    "RapidMoveSettingsDialog",
    "SessionSummaryDialog",
    "ShortcutsGuideDialog",
    "UpdateDialog",
    "apply_studio_dialog_style",
    "show_studio_message",
]
