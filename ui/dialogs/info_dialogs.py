"""Studio Slate informational dialogs: Update, About, Shortcuts Guide, Jump To Media, and styled message helper."""

import os
import webbrowser
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
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
    SLOT_ACCENTS,
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
                ("Bookmark / Flag file", ["*", "or", "Alt+F"]),
            ]),
            ("NAVIGATION", [
                ("Previous / Next media", ["←", "→"]),
                ("Skip to next unmoved", ["Space"]),
                ("First / Last media", ["Home", "End"]),
                ("Jump to media number", ["Ctrl", "G"]),
                ("Toggle filmstrip bar", ["Ctrl", "B"]),
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
            ("TOOLS & FILE", [
                ("Import folder", ["Ctrl", "O"]),
                ("Session summary report", ["Ctrl", "Shift", "R"]),
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


class SessionSummaryDialog(QDialog):
    """Studio Slate dialog presenting comprehensive sorting statistics for the current folder session."""

    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session Summary Report")
        self.resize(540, 540)
        self.setMinimumSize(480, 440)
        tokens = apply_studio_dialog_style(self, parent)

        self.summary = summary or {}
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Header with report icon, title and source folder chip
        header = QVBoxLayout()
        header.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        rep_icon_lbl = QLabel()
        rep_icon_lbl.setPixmap(make_vector_icon("report", color=tokens["accent"], size=22).pixmap(22, 22))
        title_row.addWidget(rep_icon_lbl)

        title = QLabel("Session Summary Report")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {tokens['text']};")
        title_row.addWidget(title)
        title_row.addStretch()
        header.addLayout(title_row)

        src_folder = str(self.summary.get("source_folder") or "-")
        src_chip = QFrame()
        src_chip.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens['surface']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
            }}
        """)
        src_lay = QHBoxLayout(src_chip)
        src_lay.setContentsMargins(8, 4, 8, 4)
        src_lay.setSpacing(6)

        f_icon = QLabel()
        f_icon.setPixmap(make_vector_icon("folder", color=tokens["text_muted"], size=13).pixmap(13, 13))
        src_lay.addWidget(f_icon)

        display_src = src_folder if len(src_folder) <= 60 else (src_folder[:28] + "..." + src_folder[-28:])
        src_lbl = QLabel(f"Source: {display_src}")
        src_lbl.setToolTip(src_folder)
        src_lbl.setStyleSheet(f"font-size: 11.5px; color: {tokens['text_muted']}; border: none; background: transparent;")
        src_lay.addWidget(src_lbl)
        src_lay.addStretch()
        header.addWidget(src_chip)
        root.addLayout(header)

        # 2x2 Metric Cards Grid
        stat_grid = QGridLayout()
        stat_grid.setSpacing(10)

        total_files = int(self.summary.get("total_files", 0))
        total_moved = int(self.summary.get("total_moved", 0))
        remaining = int(self.summary.get("remaining_unmoved", 0))
        flagged = int(self.summary.get("flagged_count", 0))

        def make_stat_card(label: str, value_num: int, col: str, icon_kind: str, subtext: str = None):
            card = QFrame()
            card.setObjectName("studioCard")
            card.setStyleSheet(f"""
                QFrame#studioCard {{
                    background-color: {tokens['stage_bg']};
                    border: 1px solid {tokens['border']};
                    border-radius: 10px;
                }}
            """)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(14, 11, 14, 11)
            lay.setSpacing(3)

            top_row = QHBoxLayout()
            top_row.setSpacing(6)
            l_lbl = QLabel(label)
            l_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {tokens['text_muted']};")
            top_row.addWidget(l_lbl)
            top_row.addStretch()

            ic_lbl = QLabel()
            ic_lbl.setPixmap(make_vector_icon(icon_kind, color=col, size=14).pixmap(14, 14))
            top_row.addWidget(ic_lbl)
            lay.addLayout(top_row)

            val_str = f"{value_num:,}"
            v_lbl = QLabel(val_str)
            v_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {col};")
            lay.addWidget(v_lbl)

            if subtext:
                s_lbl = QLabel(subtext)
                s_lbl.setStyleSheet(f"font-size: 10px; color: {tokens['text_muted']};")
                lay.addWidget(s_lbl)

            return card

        pct_moved = (total_moved / total_files * 100.0) if total_files > 0 else 0.0
        c_total = make_stat_card("Total Media", total_files, tokens["text"], "file_text")
        c_moved = make_stat_card("Moved", total_moved, tokens["accent"], "check", f"{pct_moved:.1f}% sorted" if total_files > 0 else None)
        c_remain = make_stat_card("Remaining", remaining, tokens["text_muted"], "clock")
        c_flag = make_stat_card("★ Flagged", flagged, "#f59e0b", "star_filled")

        stat_grid.addWidget(c_total, 0, 0)
        stat_grid.addWidget(c_moved, 0, 1)
        stat_grid.addWidget(c_remain, 1, 0)
        stat_grid.addWidget(c_flag, 1, 1)
        root.addLayout(stat_grid)

        # Destination Breakdown Card
        breakdown_card = QFrame()
        breakdown_card.setObjectName("studioCard")
        breakdown_card.setStyleSheet(f"""
            QFrame#studioCard {{
                background-color: {tokens['stage_bg']};
                border: 1px solid {tokens['border']};
                border-radius: 10px;
            }}
        """)
        b_lay = QVBoxLayout(breakdown_card)
        b_lay.setContentsMargins(14, 12, 14, 12)
        b_lay.setSpacing(9)

        # Card Header: Title & Progress Label
        b_hdr = QHBoxLayout()
        b_title = QLabel("Destination Breakdown")
        b_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {tokens['text']};")
        b_hdr.addWidget(b_title)
        b_hdr.addStretch()

        status_text = f"{total_moved:,} of {total_files:,} sorted ({pct_moved:.1f}%)" if total_files > 0 else "0 sorted"
        b_status = QLabel(status_text)
        b_status.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {tokens['accent']};")
        b_hdr.addWidget(b_status)
        b_lay.addLayout(b_hdr)

        # Progress bar
        prog_bar = QProgressBar()
        prog_bar.setFixedHeight(5)
        prog_bar.setTextVisible(False)
        prog_bar.setRange(0, max(1, total_files))
        prog_bar.setValue(total_moved)
        prog_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {tokens['surface']};
                border: 1px solid {tokens['border']};
                border-radius: 2.5px;
            }}
            QProgressBar::chunk {{
                background-color: {tokens['accent']};
                border-radius: 2px;
            }}
        """)
        b_lay.addWidget(prog_bar)

        # Scroll area with styled destination row cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setContentsMargins(0, 2, 0, 2)
        scroll_lay.setSpacing(6)

        # Extract slots info
        slots = self.summary.get("slots")
        if not slots:
            folder_counts = self.summary.get("folder_counts", {})
            slots = [
                {
                    "index": i + 1,
                    "letter": ALL_SLOT_LETTERS[i] if i < len(ALL_SLOT_LETTERS) else str(i + 1),
                    "name": name,
                    "path": "",
                    "count": cnt,
                }
                for i, (name, cnt) in enumerate(folder_counts.items())
            ]

        for s_info in slots:
            slot_idx = s_info.get("index", 1)
            slot_letter = s_info.get("letter", "")
            slot_name = s_info.get("name", f"Slot {slot_idx}")
            slot_path = s_info.get("path", "")
            slot_cnt = int(s_info.get("count", 0))
            slot_col = SLOT_ACCENTS[(slot_idx - 1) % len(SLOT_ACCENTS)]

            row_card = QFrame()
            row_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {tokens['surface']};
                    border: 1px solid {tokens['border']};
                    border-radius: 7px;
                }}
            """)
            r_lay = QHBoxLayout(row_card)
            r_lay.setContentsMargins(10, 6, 10, 6)
            r_lay.setSpacing(10)

            # Slot badge pill [1] A
            badge_text = f"[{slot_idx}] {slot_letter}".strip() if slot_letter else f"[{slot_idx}]"
            badge_lbl = QLabel(badge_text)
            badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {hex_rgba(slot_col, 28)};
                    color: {slot_col};
                    border: 1px solid {hex_rgba(slot_col, 85)};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 6px;
                }}
            """)
            r_lay.addWidget(badge_lbl)

            f_ic = QLabel()
            f_ic.setPixmap(make_vector_icon("folder", color=slot_col, size=15).pixmap(15, 15))
            r_lay.addWidget(f_ic)

            info_lay = QVBoxLayout()
            info_lay.setSpacing(1)
            n_lbl = QLabel(slot_name)
            n_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens['text']}; border: none; background: transparent;")
            info_lay.addWidget(n_lbl)

            if slot_path:
                short_p = slot_path if len(slot_path) <= 45 else (slot_path[:20] + "..." + slot_path[-22:])
                p_lbl = QLabel(short_p)
                p_lbl.setToolTip(slot_path)
                p_lbl.setStyleSheet(f"font-size: 10px; color: {tokens['text_muted']}; border: none; background: transparent;")
                info_lay.addWidget(p_lbl)

            r_lay.addLayout(info_lay)
            r_lay.addStretch()

            cnt_lbl = QLabel(f"{slot_cnt:,} files")
            if slot_cnt > 0:
                cnt_lbl.setStyleSheet(f"""
                    QLabel {{
                        background-color: {hex_rgba(slot_col, 25)};
                        color: {slot_col};
                        border: 1px solid {hex_rgba(slot_col, 80)};
                        border-radius: 10px;
                        font-size: 11.5px;
                        font-weight: 700;
                        padding: 3px 9px;
                    }}
                """)
            else:
                cnt_lbl.setStyleSheet(f"""
                    QLabel {{
                        background-color: {hex_rgba(tokens['border'], 40)};
                        color: {tokens['text_muted']};
                        border: 1px solid {hex_rgba(tokens['border'], 70)};
                        border-radius: 10px;
                        font-size: 11.5px;
                        font-weight: 500;
                        padding: 3px 9px;
                    }}
                """)
            r_lay.addWidget(cnt_lbl)
            scroll_lay.addWidget(row_card)

        # Other Destinations row if > 0
        other_cnt = int(self.summary.get("other_moved_count", 0))
        if other_cnt > 0:
            row_card = QFrame()
            row_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {tokens['surface']};
                    border: 1px solid {tokens['border']};
                    border-radius: 7px;
                }}
            """)
            r_lay = QHBoxLayout(row_card)
            r_lay.setContentsMargins(10, 6, 10, 6)
            r_lay.setSpacing(10)

            badge_lbl = QLabel("[Other]")
            badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {hex_rgba(tokens['text_muted'], 25)};
                    color: {tokens['text_muted']};
                    border: 1px solid {hex_rgba(tokens['text_muted'], 70)};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 6px;
                }}
            """)
            r_lay.addWidget(badge_lbl)

            f_ic = QLabel()
            f_ic.setPixmap(make_vector_icon("folder", color=tokens["text_muted"], size=15).pixmap(15, 15))
            r_lay.addWidget(f_ic)

            n_lbl = QLabel("Other Destinations")
            n_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens['text']}; border: none; background: transparent;")
            r_lay.addWidget(n_lbl)
            r_lay.addStretch()

            cnt_lbl = QLabel(f"{other_cnt:,} files")
            cnt_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {hex_rgba(tokens['accent'], 25)};
                    color: {tokens['accent']};
                    border: 1px solid {hex_rgba(tokens['accent'], 80)};
                    border-radius: 10px;
                    font-size: 11.5px;
                    font-weight: 700;
                    padding: 3px 9px;
                }}
            """)
            r_lay.addWidget(cnt_lbl)
            scroll_lay.addWidget(row_card)

        scroll_lay.addStretch()
        scroll.setWidget(scroll_content)
        b_lay.addWidget(scroll)
        root.addWidget(breakdown_card, stretch=1)

        # Footer Buttons with vector icons
        footer = QHBoxLayout()
        footer.setSpacing(8)

        copy_btn = QPushButton("Copy Report")
        copy_btn.setIcon(make_vector_icon("copy", color=tokens["text"], size=14))
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setToolTip("Copy formatted summary report to clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        footer.addWidget(copy_btn)

        export_btn = QPushButton("Export to File...")
        export_btn.setIcon(make_vector_icon("download", color=tokens["text"], size=14))
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setToolTip("Export summary report as a text file")
        export_btn.clicked.connect(self._export_to_file)
        footer.addWidget(export_btn)

        footer.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryBtn")
        close_btn.setIcon(make_vector_icon("check", color="#ffffff", size=14))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)

        root.addLayout(footer)

    def _generate_report_text(self) -> str:
        lines = [
            "=== Image Sorter - Session Summary Report ===",
            f"Source Folder: {self.summary.get('source_folder', '-')}",
            f"Total Media: {self.summary.get('total_files', 0)}",
            f"Total Moved: {self.summary.get('total_moved', 0)}",
            f"Remaining Unmoved: {self.summary.get('remaining_unmoved', 0)}",
            f"Flagged Media: {self.summary.get('flagged_count', 0)}",
            "",
            "Destination Folder Breakdown:",
        ]
        for name, cnt in self.summary.get("folder_counts", {}).items():
            lines.append(f"  - {name}: {cnt} files")
        if self.summary.get("other_moved_count", 0) > 0:
            lines.append(f"  - Other Destinations: {self.summary.get('other_moved_count', 0)} files")
        lines.append("===========================================")
        return "\n".join(lines)

    def _copy_to_clipboard(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self._generate_report_text())
            show_studio_message(self, "Copied", "Session report copied to clipboard.", kind="info")

    def _export_to_file(self):
        default_name = "session_summary.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Export Session Summary", default_name, "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._generate_report_text())
            show_studio_message(self, "Export Complete", f"Session report saved to:\n{path}", kind="info")
        except OSError as e:
            show_studio_message(self, "Export Error", f"Could not save report file:\n{e}", kind="error")
