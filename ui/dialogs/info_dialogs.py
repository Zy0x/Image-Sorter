"""Studio Slate informational dialogs: Update, About, Shortcuts Guide, Jump To Media, and styled message helper."""

import os
import webbrowser
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.config import APP_NAME, APP_VERSION, ALL_SLOT_LETTERS, resource_path
from core.workers import is_newer_version
from ui.widgets import StudioSpinBox
from ui.theme import (
    apply_studio_palette,
    build_studio_dialog_qss,
    hex_rgba,
    make_vector_icon,
    render_github_markdown_html,
    resolve_studio_tokens,
    slot_text_color,
)


def apply_studio_dialog_style(widget: QWidget, owner=None) -> dict:
    """Apply unified Studio Slate tokens, palette, window icon, and dialog QSS to any QDialog or QMessageBox."""
    tokens = resolve_studio_tokens(owner or widget.parentWidget())
    apply_studio_palette(tokens)
    widget.setStyleSheet(build_studio_dialog_qss(tokens))
    icon_path = resource_path("assets/icons/app_icon.png")
    if os.path.exists(icon_path):
        widget.setWindowIcon(QIcon(icon_path))
    return tokens


def show_studio_message(
    owner,
    title: str,
    text: str,
    kind: str = "info",
    buttons=QMessageBox.Ok,
    default_button=None,
) -> QMessageBox.StandardButton:
    """Show a consistently themed QMessageBox without duplicated setup across dialogs."""
    box = QMessageBox(owner)
    box.setWindowTitle(title)
    box.setText(text)
    icon_map = {
        "info": QMessageBox.Information,
        "warning": QMessageBox.Warning,
        "error": QMessageBox.Critical,
        "question": QMessageBox.Question,
    }
    box.setIcon(icon_map.get(kind, QMessageBox.Information))
    box.setStandardButtons(buttons)
    if default_button is not None:
        box.setDefaultButton(default_button)
    apply_studio_dialog_style(box, owner)
    return QMessageBox.StandardButton(box.exec())


class UpdateDialog(QDialog):
    """Studio Slate software update checker and rendered GitHub Release Notes viewer."""

    def __init__(
        self,
        parent=None,
        current_version: str = None,
        latest_version: str = "",
        release_notes: str = "",
        download_url: str = "",
        check_failed: bool = False,
        error_message: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.resize(540, 440)
        self.setMinimumSize(460, 360)

        self.current_version = current_version or APP_VERSION
        self.latest_version = latest_version or self.current_version
        self.release_notes = release_notes or ""
        self.download_url = download_url or "https://github.com/Zy0x/Image-Sorter/releases"

        tokens = apply_studio_dialog_style(self, parent)
        has_update = (not check_failed) and is_newer_version(self.current_version, self.latest_version)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # Header row: title + status pill badge
        header = QHBoxLayout()
        title_lbl = QLabel("Software Update")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {tokens['text']};")
        header.addWidget(title_lbl)
        header.addStretch()

        if check_failed:
            badge_text = "Check Failed"
            badge_col = "#ef4444"
        elif has_update:
            badge_text = "Update Available"
            badge_col = tokens["accent"]
        else:
            badge_text = "Up to Date"
            badge_col = "#10b981"

        badge_fg = slot_text_color(badge_col, tokens["is_dark"])
        self.status_badge = QLabel(badge_text)
        self.status_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {badge_fg}; "
            f"background-color: {hex_rgba(badge_col, 28 if tokens['is_dark'] else 22)}; "
            f"border: 1px solid {hex_rgba(badge_fg, 110)}; "
            f"border-radius: 6px; padding: 3px 12px;"
        )
        header.addWidget(self.status_badge)
        root.addLayout(header)

        # Version comparison summary card
        card = QFrame()
        card.setObjectName("studioCard")
        card_lay = QHBoxLayout(card)
        card_lay.setContentsMargins(16, 12, 16, 12)

        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        inst_cap = QLabel("INSTALLED")
        inst_cap.setStyleSheet(f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; color: {tokens['text_muted']};")
        inst_val = QLabel(self.current_version)
        inst_val.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {tokens['text']};")
        left_col.addWidget(inst_cap)
        left_col.addWidget(inst_val)
        card_lay.addLayout(left_col)
        card_lay.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        lat_cap = QLabel("LATEST RELEASE")
        lat_cap.setAlignment(Qt.AlignRight)
        lat_cap.setStyleSheet(f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; color: {tokens['text_muted']};")
        lat_val = QLabel("Unavailable" if check_failed else self.latest_version)
        lat_val.setAlignment(Qt.AlignRight)
        lat_val.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {tokens['accent']};")
        right_col.addWidget(lat_cap)
        right_col.addWidget(lat_val)
        card_lay.addLayout(right_col)
        root.addWidget(card)

        # Release notes section
        notes_cap = QLabel("RELEASE NOTES")
        notes_cap.setStyleSheet(
            f"font-size: 11px; font-weight: 700; letter-spacing: 0.6px; color: {tokens['text_muted']};"
        )
        root.addWidget(notes_cap)

        self.notes_text = QTextBrowser()
        self.notes_text.setObjectName("releaseNotesView")
        self.notes_text.setOpenExternalLinks(True)
        self.notes_text.document().setIndentWidth(15)
        md_source = (
            f"**Could not reach GitHub Releases API.**\n\n`{error_message}`"
            if check_failed and error_message
            else self.release_notes
        )
        self.notes_text.setHtml(render_github_markdown_html(md_source, tokens))
        root.addWidget(self.notes_text, stretch=1)

        # Action footer
        footer = QHBoxLayout()
        footer.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)

        self.download_button = QPushButton("Download Update")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.setIcon(make_vector_icon("download", tokens["text"] if has_update else tokens["text_muted"], 14))
        self.download_button.setIconSize(QSize(14, 14))
        if has_update:
            self.download_button.setObjectName("primaryBtn")
            self.download_button.setIcon(make_vector_icon("download", "#ffffff", 14))
        self.download_button.setEnabled(has_update)
        self.download_button.clicked.connect(lambda: webbrowser.open(self.download_url))
        footer.addWidget(self.download_button)
        root.addLayout(footer)


class AboutDialog(QDialog):
    """Studio Slate application info, version, creator links, and stack summary."""

    VERSION = APP_VERSION

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(470, 445)
        tokens = apply_studio_dialog_style(self, parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        # App identity header
        top = QHBoxLayout()
        top.setSpacing(14)
        logo_lbl = QLabel()
        logo_path = resource_path("assets/icons/app_icon.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        top.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        name_lbl = QLabel(APP_NAME)
        name_lbl.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {tokens['text']};")
        ver_lbl = QLabel(f"Version {self.VERSION}")
        ver_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens['accent']};")
        title_col.addWidget(name_lbl)
        title_col.addWidget(ver_lbl)
        top.addLayout(title_col)
        top.addStretch()
        root.addLayout(top)

        desc = QLabel(
            "High-speed desktop media organizer for curating large photo, animated image, "
            "and video collections with single-key sorting, rapid move, duplicate detection, "
            "and safe undo recovery."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 12.5px; line-height: 1.45; color: {tokens['text_muted']};")
        root.addWidget(desc)

        # Details card
        card = QFrame()
        card.setObjectName("studioCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        rows = [
            ("Developer", "Zy0x"),
            ("Framework", "PySide6 (Qt 6) · OpenCV · Pillow"),
            ("License", "MIT Open Source License"),
            ("Architecture", "Modular Core / Media / UI Packages"),
        ]
        for row_idx, (k, v) in enumerate(rows):
            kl = QLabel(k)
            kl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens['text_muted']};")
            vl = QLabel(v)
            vl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens['text']};")
            grid.addWidget(kl, row_idx, 0)
            grid.addWidget(vl, row_idx, 1, Qt.AlignRight)
        grid.setColumnStretch(1, 1)
        root.addWidget(card)

        # Social & repository links
        link_row = QHBoxLayout()
        link_row.setSpacing(10)

        for label, icon_file, url in (
            ("GitHub", "assets/icons/github.png", "https://github.com/Zy0x"),
            ("Telegram", "assets/icons/telegram.png", "https://t.me/ThuandMuda"),
        ):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            ip = resource_path(icon_file)
            if os.path.exists(ip):
                btn.setIcon(QIcon(ip))
                btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda _=False, target=url: webbrowser.open(target))
            link_row.addWidget(btn)
        root.addLayout(link_row)

        root.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryBtn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setMinimumWidth(96)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)


class ShortcutsGuideDialog(QDialog):
    """Scrollable Studio Slate quick-reference guide covering all keyboard and mouse shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts & Quick Guide")
        self.resize(740, 560)
        self.setMinimumSize(640, 460)
        tokens = apply_studio_dialog_style(self, parent)

        slot_count = getattr(parent, "folder_slot_count", 5) if parent else 5
        slot_count = max(3, min(9, int(slot_count)))
        max_letter = ALL_SLOT_LETTERS[slot_count - 1]

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        # Title bar
        header = QHBoxLayout()
        title_lbl = QLabel("Keyboard Shortcuts")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {tokens['text']};")
        hint_lbl = QLabel("F1 / Esc")
        hint_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens['text_muted']};")
        header.addWidget(title_lbl)
        header.addStretch()
        header.addWidget(hint_lbl)
        root.addLayout(header)

        # Concise workflow banner
        wf_bar = QFrame()
        wf_bar.setObjectName("workflowBar")
        wf_lay = QHBoxLayout(wf_bar)
        wf_lay.setContentsMargins(14, 9, 14, 9)
        wf_lbl = QLabel(
            f"<b>Workflow:</b> 1. Set slots 3–9 (<i>Settings → Folder Settings</i>) &nbsp;·&nbsp; "
            f"2. Import (<b>Ctrl+O</b> or drop) &nbsp;·&nbsp; 3. Press/hold <b>1–{slot_count}</b> to sort Folders A–{max_letter}"
        )
        wf_lbl.setWordWrap(True)
        wf_lbl.setStyleSheet(f"font-size: 12px; color: {tokens['text_muted']};")
        wf_lay.addWidget(wf_lbl)
        root.addWidget(wf_bar)

        # Scrollable 2-column shortcuts matrix
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet("background-color: transparent;")

        body = QWidget()
        body.setObjectName("scrollBody")
        grid = QGridLayout(body)
        grid.setContentsMargins(2, 4, 6, 4)
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(14)

        left_sections = [
            ("SORTING", [
                (f"Move to Folder 1–{slot_count}", [f"1", "–", f"{slot_count}"]),
                ("Rapid Move (continuous)", ["Hold", "1", "–", f"{slot_count}"]),
                ("Undo last move", ["Ctrl", "Z"]),
            ]),
            ("NAVIGATION", [
                ("Previous / Next media", ["←", "→"]),
                ("Skip to next unmoved", ["Space"]),
                ("First / Last media", ["Home", "End"]),
                ("Jump to media number", ["Ctrl", "G"]),
            ]),
        ]
        right_sections = [
            ("VIEW & INSPECT", [
                ("Full-size zoom preview", ["F"]),
                ("Play / Pause video or GIF", ["P"]),
                ("Mute / Unmute video sound", ["M"]),
                ("Find duplicate / similar", ["Ctrl", "D"]),
                ("Include subfolders", ["Ctrl", "Shift", "S"]),
                ("Hide moved media", ["Ctrl", "H"]),
                ("Shortcuts reference", ["F1"]),
            ]),
            ("FILE & MOUSE", [
                ("Import folder", ["Ctrl", "O"]),
                ("Show in File Explorer", ["Ctrl", "E"]),
                ("Move to Recycle Bin", ["Delete"]),
                ("Rapid Move with mouse", ["Hold", f"Click 1–{slot_count}"]),
                ("Zoom preview with mouse", ["Double-Click"]),
            ]),
        ]

        grid.addWidget(self._build_column(left_sections, tokens), 0, 0, Qt.AlignTop)
        grid.addWidget(self._build_column(right_sections, tokens), 0, 1, Qt.AlignTop)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # Footer note & Close
        footer = QHBoxLayout()
        note = QLabel("Duplicate filenames in destination folders are auto-renamed — existing files are never overwritten.")
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: 11.5px; color: {tokens['text_muted']};")
        footer.addWidget(note, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setMinimumWidth(86)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _build_column(self, sections, tokens: dict) -> QWidget:
        col = QWidget()
        col.setObjectName("scrollColumn")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        for sec_title, items in sections:
            sec_lbl = QLabel(sec_title)
            sec_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 700; letter-spacing: 0.8px; color: {tokens['text_muted']}; margin-bottom: 2px;"
            )
            lay.addWidget(sec_lbl)
            for desc, keys in items:
                lay.addWidget(self._make_shortcut_row(desc, keys, tokens))
        return col

    def _make_shortcut_row(self, desc: str, keys, tokens: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("shortcutRow")
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(0, 6, 0, 6)
        row_lay.setSpacing(6)

        lbl = QLabel(desc)
        lbl.setStyleSheet(f"font-size: 12.5px; font-weight: 500; color: {tokens['text']}; border: none;")
        row_lay.addWidget(lbl)
        row_lay.addStretch()

        for k in keys:
            if k in ("–", "Hold"):
                hint = QLabel(k)
                hint.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {tokens['text_muted']}; border: none; padding: 0 2px;")
                row_lay.addWidget(hint)
            else:
                cap = QLabel(k)
                cap.setAlignment(Qt.AlignCenter)
                cap.setStyleSheet(
                    f"font-family: Consolas, monospace; font-size: 11.5px; font-weight: 700; "
                    f"color: {tokens['text']}; background-color: {tokens['surface']}; "
                    f"border: 1px solid {tokens['border_strong']}; border-radius: 5px; padding: 2px 7px;"
                )
                row_lay.addWidget(cap)
        return row


class JumpToMediaDialog(QDialog):
    """Compact Studio Slate dialog for jumping directly to any 1-based queue position."""

    def __init__(self, parent=None, total_count: int = 1, current_one_based: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Jump to Media")
        self.setFixedSize(330, 155)
        tokens = apply_studio_dialog_style(self, parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        prompt = QLabel(f"Enter media index (1 – {total_count}):")
        prompt.setStyleSheet(f"font-size: 12.5px; font-weight: 600; color: {tokens['text']};")
        root.addWidget(prompt)

        self.index_spin = StudioSpinBox()
        self.index_spin.setRange(1, max(1, int(total_count)))
        self.index_spin.setValue(max(1, min(int(total_count), int(current_one_based))))
        self.index_spin.selectAll()
        root.addWidget(self.index_spin)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        go_btn = QPushButton("Jump")
        go_btn.setObjectName("primaryBtn")
        go_btn.setCursor(Qt.PointingHandCursor)
        go_btn.setDefault(True)
        go_btn.clicked.connect(self.accept)
        btn_row.addWidget(go_btn)
        root.addLayout(btn_row)

    def selected_index(self) -> int:
        """Return 0-based queue index selected by the user."""
        return self.index_spin.value() - 1
