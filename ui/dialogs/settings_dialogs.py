"""Studio Slate configuration dialogs: Custom Theme Editor, Folder Slots Settings, and Rapid Move Timing."""

import copy
import os
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import (
    ALL_SLOT_LETTERS,
    DEFAULT_CUSTOM_THEME,
    DEFAULT_FOLDER_NAMES,
    DEFAULT_FOLDER_PATHS,
    MAX_FOLDER_SLOTS,
    MIN_FOLDER_SLOTS,
    RAPID_MOVE_DEFAULT_MS,
    RAPID_MOVE_MAX_MS,
    RAPID_MOVE_MIN_MS,
    clamp_folder_slots,
    clamp_rapid_interval,
    load_settings,
    save_settings,
)
from ui.dialogs.info_dialogs import apply_studio_dialog_style
from ui.theme import SLOT_ACCENTS, hex_rgba, make_vector_icon

_THEME_COLOR_FIELDS = (
    ("bg_color", "Window Background", "Main Studio backdrop fill"),
    ("label_bg", "Stage & Card Surface", "Preview cards and recessed panels"),
    ("text_color", "Primary Text", "Headings, filenames, and labels"),
    ("btn_bg", "Button Surface", "Default resting button fill"),
    ("btn_hover", "Button Hover Surface", "Hover highlight fill"),
    ("main_border_color", "Main Focus Accent", "Active preview card border & accent"),
    ("next_border_color", "Up-Next Card Border", "Secondary queue card outline"),
    ("menu_bg", "Menu Surface", "Top menubar dropdown background"),
    ("menu_text", "Menu Text", "Menubar dropdown item text"),
)


class CustomThemeDialog(QDialog):
    """Interactive Studio Slate color-token editor with live swatch previews."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Theme Editor")
        self.resize(520, 560)
        self.setMinimumSize(460, 440)
        tokens = apply_studio_dialog_style(self, parent)

        settings = load_settings()
        self.custom_theme = copy.deepcopy(DEFAULT_CUSTOM_THEME)
        self.custom_theme.update(settings.get("custom_theme", {}))
        self._swatch_buttons = {}
        self._hex_labels = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Custom Theme Palette")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {tokens['text']};")
        sub = QLabel("Customize surface, text, border, and menu tokens for your Custom Theme mode.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12px; color: {tokens['text_muted']};")
        header.addWidget(title)
        header.addWidget(sub)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 2, 6, 2)
        body_lay.setSpacing(8)

        for key, label, desc in _THEME_COLOR_FIELDS:
            card = QFrame()
            card.setObjectName("studioCard")
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 10, 14, 10)
            row.setSpacing(12)

            info = QVBoxLayout()
            info.setSpacing(1)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(f"font-size: 12.5px; font-weight: 600; color: {tokens['text']};")
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(f"font-size: 11px; color: {tokens['text_muted']};")
            info.addWidget(name_lbl)
            info.addWidget(desc_lbl)
            row.addLayout(info, stretch=1)

            hex_val = self.custom_theme.get(key, DEFAULT_CUSTOM_THEME[key])
            hex_lbl = QLabel(hex_val.upper())
            hex_lbl.setStyleSheet(
                f"font-family: Consolas, monospace; font-size: 11.5px; color: {tokens['text_muted']};"
            )
            self._hex_labels[key] = hex_lbl
            row.addWidget(hex_lbl)

            swatch = QPushButton()
            swatch.setFixedSize(44, 28)
            swatch.setCursor(Qt.PointingHandCursor)
            swatch.setToolTip(f"Pick color for {label}")
            swatch.clicked.connect(lambda _=False, k=key: self._pick_color(k))
            self._swatch_buttons[key] = swatch
            self._update_swatch_style(key, hex_val, tokens)
            row.addWidget(swatch)

            body_lay.addWidget(card)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        reset_btn = QPushButton("Reset Default")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setIcon(make_vector_icon("reset", tokens["text"], 14))
        reset_btn.setIconSize(QSize(14, 14))
        reset_btn.clicked.connect(lambda: self._reset_defaults(tokens))
        footer.addWidget(reset_btn)

        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save Theme")
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setIcon(make_vector_icon("check", "#ffffff", 14))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.clicked.connect(self._save_and_accept)
        footer.addWidget(save_btn)
        root.addLayout(footer)

    def _update_swatch_style(self, key: str, color_hex: str, tokens: dict) -> None:
        self._hex_labels[key].setText(color_hex.upper())
        self._swatch_buttons[key].setStyleSheet(
            f"background-color: {color_hex}; border: 2px solid {tokens['border_strong']}; border-radius: 6px; padding: 0;"
        )

    def _pick_color(self, key: str) -> None:
        current = QColor(self.custom_theme.get(key, DEFAULT_CUSTOM_THEME[key]))
        chosen = QColorDialog.getColor(current, self, "Select Color")
        if chosen.isValid():
            val = chosen.name()
            self.custom_theme[key] = val
            tokens = apply_studio_dialog_style(self, self.parentWidget())
            for k in self._swatch_buttons:
                self._update_swatch_style(k, self.custom_theme[k], tokens)

    def _reset_defaults(self, tokens: dict) -> None:
        self.custom_theme = copy.deepcopy(DEFAULT_CUSTOM_THEME)
        for k in self._swatch_buttons:
            self._update_swatch_style(k, self.custom_theme[k], tokens)

    def save_and_close(self) -> None:
        """Backwards-compatible alias saving folder slots & closing dialog."""
        self._save_and_accept()

    def _save_and_accept(self) -> None:
        settings = load_settings()
        settings["custom_theme"] = copy.deepcopy(self.custom_theme)
        settings["theme_mode"] = "custom"
        save_settings(settings)
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "set_theme_mode"):
            parent.custom_theme = copy.deepcopy(self.custom_theme)
            parent.set_theme_mode("custom")
        self.accept()


class FolderSettingsDialog(QDialog):
    """Dynamic 3–9 folder slot count, label, and destination directory configuration dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Folder Slots & Destinations")
        self.resize(650, 560)
        self.setMinimumSize(540, 420)
        self._tokens = apply_studio_dialog_style(self, parent)

        settings = load_settings()
        if parent is not None and hasattr(parent, "folder_slot_count"):
            self._slot_count = clamp_folder_slots(parent.folder_slot_count)
            base_names = list(parent.folder_names)
            base_paths = list(parent.folder_paths)
        else:
            self._slot_count = clamp_folder_slots(settings.get("folder_slot_count", 5))
            base_names = list(settings.get("folder_names", DEFAULT_FOLDER_NAMES))
            base_paths = list(settings.get("folder_paths", DEFAULT_FOLDER_PATHS))

        while len(base_names) < MAX_FOLDER_SLOTS:
            base_names.append(DEFAULT_FOLDER_NAMES[len(base_names)])
        while len(base_paths) < MAX_FOLDER_SLOTS:
            base_paths.append(DEFAULT_FOLDER_PATHS[len(base_paths)])

        self._name_inputs = []
        self._path_inputs = []
        self._slot_cards = []
        self.row_widgets = self._slot_cards
        self.inputs = []
        self._count_buttons = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # Top header + slot count selector card
        title = QLabel("Folder Slots & Destinations")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {self._tokens['text']};")
        root.addWidget(title)

        count_card = QFrame()
        count_card.setObjectName("studioCard")
        count_lay = QHBoxLayout(count_card)
        count_lay.setContentsMargins(14, 10, 14, 10)
        count_lay.setSpacing(6)

        count_caption = QVBoxLayout()
        count_caption.setSpacing(1)
        c_title = QLabel("Active Sort Slots")
        c_title.setStyleSheet(f"font-size: 12.5px; font-weight: 600; color: {self._tokens['text']};")
        c_sub = QLabel("Choose how many quick-sort folder buttons & number keys (1–9) are active")
        c_sub.setWordWrap(True)
        c_sub.setStyleSheet(f"font-size: 11px; color: {self._tokens['text_muted']};")
        count_caption.addWidget(c_title)
        count_caption.addWidget(c_sub)
        count_lay.addLayout(count_caption, stretch=1)

        for n in range(MIN_FOLDER_SLOTS, MAX_FOLDER_SLOTS + 1):
            btn = QPushButton(str(n))
            btn.setFixedSize(30, 28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, cnt=n: self._set_slot_count(cnt))
            self._count_buttons[n] = btn
            count_lay.addWidget(btn)

        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(MIN_FOLDER_SLOTS, MAX_FOLDER_SLOTS)
        self.slot_spin.setValue(self._slot_count)
        self.slot_spin.setFixedWidth(54)
        self.slot_spin.valueChanged.connect(self._set_slot_count)
        count_lay.addWidget(self.slot_spin)
        root.addWidget(count_card)

        # Scrollable list of 9 slot cards (hidden cleanly beyond _slot_count)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 2, 6, 2)
        body_lay.setSpacing(8)

        for i in range(MAX_FOLDER_SLOTS):
            accent = SLOT_ACCENTS[i % len(SLOT_ACCENTS)]
            card = QFrame()
            card.setObjectName("studioCard")
            row = QHBoxLayout(card)
            row.setContentsMargins(12, 10, 12, 10)
            row.setSpacing(8)

            badge = QLabel(f"[{i + 1}] {ALL_SLOT_LETTERS[i]}")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedWidth(52)
            badge.setStyleSheet(
                f"font-family: Consolas, monospace; font-size: 12px; font-weight: 700; color: {accent}; "
                f"background-color: {hex_rgba(accent, 34)}; border: 1px solid {hex_rgba(accent, 110)}; "
                f"border-radius: 6px; padding: 5px 4px;"
            )
            row.addWidget(badge)

            name_edit = QLineEdit(base_names[i])
            name_edit.setPlaceholderText(f"Folder {ALL_SLOT_LETTERS[i]}")
            name_edit.setFixedWidth(138)
            row.addWidget(name_edit)

            path_edit = QLineEdit(base_paths[i])
            path_edit.setPlaceholderText("Select destination directory...")
            row.addWidget(path_edit, stretch=1)

            browse_btn = QPushButton("Browse")
            browse_btn.setCursor(Qt.PointingHandCursor)
            browse_btn.setIcon(make_vector_icon("folder", self._tokens["text"], 14))
            browse_btn.setIconSize(QSize(14, 14))
            browse_btn.clicked.connect(lambda _=False, idx=i: self._browse_slot_folder(idx))
            row.addWidget(browse_btn)

            self._name_inputs.append(name_edit)
            self._path_inputs.append(path_edit)
            self.inputs.append((name_edit, path_edit))
            self._slot_cards.append(card)
            body_lay.addWidget(card)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_defaults)
        footer.addWidget(reset_btn)

        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save Folders")
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setIcon(make_vector_icon("check", "#ffffff", 14))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.clicked.connect(self._save_and_accept)
        footer.addWidget(save_btn)
        root.addLayout(footer)

        self._set_slot_count(self._slot_count)

    def _set_slot_count(self, count: int) -> None:
        self._slot_count = clamp_folder_slots(count)
        if hasattr(self, "slot_spin") and self.slot_spin.value() != self._slot_count:
            self.slot_spin.blockSignals(True)
            self.slot_spin.setValue(self._slot_count)
            self.slot_spin.blockSignals(False)
        t = self._tokens
        for n, btn in self._count_buttons.items():
            if n == self._slot_count:
                btn.setStyleSheet(
                    f"background-color: {t['accent']}; color: #ffffff; border: 1px solid {t['accent']}; "
                    f"border-radius: 6px; padding: 0; font-weight: 700;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; "
                    f"border-radius: 6px; padding: 0; font-weight: 600;"
                )
        for i, card in enumerate(self._slot_cards):
            card.setVisible(i < self._slot_count)

    def _browse_slot_folder(self, idx: int) -> None:
        current = self._path_inputs[idx].text().strip()
        start_dir = current if os.path.isdir(current) else os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, f"Select Folder {idx + 1}", start_dir)
        if chosen:
            self._path_inputs[idx].setText(chosen)
            cur_name = self._name_inputs[idx].text().strip()
            if not cur_name or cur_name == DEFAULT_FOLDER_NAMES[idx]:
                self._name_inputs[idx].setText(os.path.basename(os.path.normpath(chosen)) or cur_name)

    def _reset_defaults(self) -> None:
        self._set_slot_count(5)
        for i in range(MAX_FOLDER_SLOTS):
            self._name_inputs[i].setText(DEFAULT_FOLDER_NAMES[i])
            self._path_inputs[i].setText(DEFAULT_FOLDER_PATHS[i])

    def save_and_close(self) -> None:
        """Backwards-compatible alias saving folder slots & closing dialog."""
        self._save_and_accept()

    def _save_and_accept(self) -> None:
        names = [
            (self._name_inputs[i].text().strip() or DEFAULT_FOLDER_NAMES[i])
            for i in range(MAX_FOLDER_SLOTS)
        ]
        paths = [
            (self._path_inputs[i].text().strip() or DEFAULT_FOLDER_PATHS[i])
            for i in range(MAX_FOLDER_SLOTS)
        ]
        settings = load_settings()
        settings["folder_slot_count"] = self._slot_count
        settings["folder_names"] = names
        settings["folder_paths"] = paths
        save_settings(settings)

        parent = self.parentWidget()
        if parent is not None:
            parent.folder_slot_count = self._slot_count
            parent.folder_names = list(names)
            parent.folder_paths = list(paths)
            if hasattr(parent, "update_folder_buttons"):
                parent.update_folder_buttons()
            if hasattr(parent, "_sync_minimum_window_size"):
                parent._sync_minimum_window_size()
        self.accept()


class RapidMoveSettingsDialog(QDialog):
    """Studio Slate hold-interval tuner for continuous keyboard/mouse Rapid Move sorting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rapid Move Timing")
        self.setFixedSize(460, 290)
        tokens = apply_studio_dialog_style(self, parent)

        settings = load_settings()
        current_ms = clamp_rapid_interval(
            getattr(parent, "rapid_move_interval_ms", None)
            or settings.get("rapid_move_interval", settings.get("rapid_move_interval_ms", RAPID_MOVE_DEFAULT_MS))
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("Rapid Move Interval")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {tokens['text']};")
        sub = QLabel(
            "Controls how fast items move when holding a folder key (1–9) or mouse button."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12px; color: {tokens['text_muted']};")
        root.addWidget(title)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("studioCard")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(10)

        top_row = QHBoxLayout()
        lbl = QLabel("Interval (ms)")
        lbl.setStyleSheet(f"font-size: 12.5px; font-weight: 600; color: {tokens['text']};")
        self.spin = QSpinBox()
        self.spin.setRange(RAPID_MOVE_MIN_MS, RAPID_MOVE_MAX_MS)
        self.spin.setSingleStep(25)
        self.spin.setSuffix(" ms")
        self.spin.setValue(current_ms)
        top_row.addWidget(lbl)
        top_row.addStretch()
        top_row.addWidget(self.spin)
        card_lay.addLayout(top_row)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(RAPID_MOVE_MIN_MS, RAPID_MOVE_MAX_MS)
        self.slider.setSingleStep(25)
        self.slider.setValue(current_ms)
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        card_lay.addWidget(self.slider)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        for p_label, p_ms in (("Fast (100 ms)", 100), ("Balanced (250 ms)", 250), ("Steady (500 ms)", 500)):
            p_btn = QPushButton(p_label)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.clicked.connect(lambda _=False, ms=p_ms: self.spin.setValue(ms))
            preset_row.addWidget(p_btn)
        card_lay.addLayout(preset_row)
        root.addWidget(card)

        root.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save Timing")
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_and_accept)
        footer.addWidget(save_btn)
        root.addLayout(footer)

    def save_and_close(self) -> None:
        """Backwards-compatible alias saving folder slots & closing dialog."""
        self._save_and_accept()

    def _save_and_accept(self) -> None:
        val = clamp_rapid_interval(self.spin.value())
        settings = load_settings()
        settings["rapid_move_interval"] = val
        save_settings(settings)
        parent = self.parentWidget()
        if parent is not None:
            parent.rapid_move_interval_ms = val
        self.accept()
