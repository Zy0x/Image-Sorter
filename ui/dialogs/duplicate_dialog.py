"""Studio Slate dialog for configuring, scanning, pausing/resuming, and filtering duplicates."""

import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.file_ops import norm_path_key
from core.workers import DuplicateScanThread
from ui.dialogs.info_dialogs import apply_studio_dialog_style, show_studio_message
from ui.theme import hex_rgba, make_vector_icon


class DuplicateFinderDialog(QDialog):
    """Studio Slate modal dialog providing multi-engine duplicate and similarity detection with live controls."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Find Duplicate / Similar Images")
        self.resize(540, 520)
        self.setMinimumSize(480, 480)
        self.tokens = apply_studio_dialog_style(self, parent)

        self._parent_app = parent
        self._scan_thread = None
        self._actual_to_srcs = {}
        self._actual_paths = []
        self._resolved_groups = []

        self._init_targets()
        self._build_ui()

    def _init_targets(self):
        """Resolve actual media targets from parent queue model."""
        targets = self._parent_app.media_queue.resolve_duplicate_targets()
        self._actual_paths = []
        self._actual_to_srcs = {}
        seen = set()
        for src, act in targets:
            na = norm_path_key(act)
            self._actual_to_srcs.setdefault(na, []).append(src)
            if na not in seen:
                seen.add(na)
                self._actual_paths.append(act)

    def _build_ui(self):
        tokens = self.tokens
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Header with icon and title
        header = QVBoxLayout()
        header.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(make_vector_icon("duplicates", color=tokens["accent"], size=22).pixmap(22, 22))
        title_row.addWidget(icon_lbl)

        title = QLabel("Find Duplicate & Similar Media")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {tokens['text']};")
        title_row.addWidget(title)
        title_row.addStretch()
        header.addLayout(title_row)

        total_files = len(self._actual_paths)
        scope_chip = QFrame()
        scope_chip.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens['surface']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
                padding: 4px 8px;
            }}
        """)
        s_lay = QHBoxLayout(scope_chip)
        s_lay.setContentsMargins(8, 4, 8, 4)
        s_lay.setSpacing(6)
        f_ic = QLabel()
        f_ic.setPixmap(make_vector_icon("folder", color=tokens["text_muted"], size=13).pixmap(13, 13))
        s_lay.addWidget(f_ic)
        s_lbl = QLabel(f"Scan Scope: {total_files:,} media files in current session")
        s_lbl.setStyleSheet(f"font-size: 11.5px; color: {tokens['text_muted']}; border: none; background: transparent;")
        s_lay.addWidget(s_lbl)
        s_lay.addStretch()
        header.addWidget(scope_chip)
        root.addLayout(header)

        # Engine Selection Card
        self.engine_card = QFrame()
        self.engine_card.setObjectName("studioCard")
        self.engine_card.setStyleSheet(f"""
            QFrame#studioCard {{
                background-color: {tokens['stage_bg']};
                border: 1px solid {tokens['border']};
                border-radius: 10px;
            }}
        """)
        e_lay = QVBoxLayout(self.engine_card)
        e_lay.setContentsMargins(14, 12, 14, 12)
        e_lay.setSpacing(8)

        e_title = QLabel("Comparison Engine")
        e_title.setStyleSheet(f"font-size: 12.5px; font-weight: 700; color: {tokens['text']};")
        e_lay.addWidget(e_title)

        self.btn_group = QButtonGroup(self)

        self.rb_dhash = QRadioButton("Perceptual dHash (Visual Similarity)")
        self.rb_dhash.setChecked(True)
        self.rb_dhash.setToolTip("Detects visually similar images, resized versions, burst shots, and slight edits.")
        self.btn_group.addButton(self.rb_dhash, 1)
        e_lay.addWidget(self.rb_dhash)

        self.rb_exact = QRadioButton("Exact Content Hash (MD5 Checksum)")
        self.rb_exact.setToolTip("Finds 100% byte-for-byte identical duplicate files regardless of filename.")
        self.btn_group.addButton(self.rb_exact, 2)
        e_lay.addWidget(self.rb_exact)

        self.rb_fast = QRadioButton("Fast Pre-filter (File Size + Sample Checksum)")
        self.rb_fast.setToolTip("Ultra-fast comparison for large collections. Compares file sizes first, then verifies matches.")
        self.btn_group.addButton(self.rb_fast, 3)
        e_lay.addWidget(self.rb_fast)

        self.btn_group.idToggled.connect(self._on_engine_changed)
        root.addWidget(self.engine_card)

        # Accuracy / Distance Settings Card
        self.accuracy_card = QFrame()
        self.accuracy_card.setObjectName("studioCard")
        self.accuracy_card.setStyleSheet(f"""
            QFrame#studioCard {{
                background-color: {tokens['stage_bg']};
                border: 1px solid {tokens['border']};
                border-radius: 10px;
            }}
        """)
        a_lay = QVBoxLayout(self.accuracy_card)
        a_lay.setContentsMargins(14, 12, 14, 12)
        a_lay.setSpacing(6)

        a_title = QLabel("Accuracy & Similarity Threshold")
        a_title.setStyleSheet(f"font-size: 12.5px; font-weight: 700; color: {tokens['text']};")
        a_lay.addWidget(a_title)

        self.acc_combo = QComboBox()
        self.acc_combo.addItem("Balanced (Distance ≤ 6) — Recommended, catches crops & edits", 6)
        self.acc_combo.addItem("Strict (Distance ≤ 4) — High precision, minimal false positives", 4)
        self.acc_combo.addItem("Relaxed (Distance ≤ 10) — Detects burst shots & similar angles", 10)
        self.acc_combo.addItem("Exact Visual Match (Distance = 0) — 100% identical signature", 0)
        self.acc_combo.setCurrentIndex(0)
        a_lay.addWidget(self.acc_combo)

        self.acc_desc = QLabel("Compares 64-bit gradient hashes. Lower distance means higher similarity requirement.")
        self.acc_desc.setStyleSheet(f"font-size: 11px; color: {tokens['text_muted']};")
        a_lay.addWidget(self.acc_desc)
        root.addWidget(self.accuracy_card)

        # Progress & Live Status Card
        self.prog_card = QFrame()
        self.prog_card.setObjectName("studioCard")
        self.prog_card.setStyleSheet(f"""
            QFrame#studioCard {{
                background-color: {tokens['stage_bg']};
                border: 1px solid {tokens['border']};
                border-radius: 10px;
            }}
        """)
        p_lay = QVBoxLayout(self.prog_card)
        p_lay.setContentsMargins(14, 12, 14, 12)
        p_lay.setSpacing(8)

        p_hdr = QHBoxLayout()
        self.status_title = QLabel("Scan Status")
        self.status_title.setStyleSheet(f"font-size: 12.5px; font-weight: 700; color: {tokens['text']};")
        p_hdr.addWidget(self.status_title)
        p_hdr.addStretch()

        self.status_badge = QLabel("Idle")
        self.status_badge.setStyleSheet(f"""
            background-color: {hex_rgba(tokens['border'], 45)};
            color: {tokens['text_muted']};
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
        """)
        p_hdr.addWidget(self.status_badge)
        p_lay.addLayout(p_hdr)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {tokens['surface']};
                border: 1px solid {tokens['border']};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {tokens['accent']};
                border-radius: 3px;
            }}
        """)
        p_lay.addWidget(self.progress_bar)

        self.status_text = QLabel(f"Ready to scan {total_files:,} media items.")
        self.status_text.setStyleSheet(f"font-size: 11.5px; color: {tokens['text']};")
        p_lay.addWidget(self.status_text)
        root.addWidget(self.prog_card)

        root.addStretch()

        # Footer Action Controls
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)

        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self._on_close_clicked)
        self.footer.addWidget(self.close_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setIcon(make_vector_icon("pause", color=tokens["text"], size=14))
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.hide()
        self.footer.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("dangerBtn")
        self.cancel_btn.setIcon(make_vector_icon("trash", color="#dc2626", size=14))
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_scan)
        self.cancel_btn.hide()
        self.footer.addWidget(self.cancel_btn)

        self.footer.addStretch()

        self.start_btn = QPushButton("Start Scan")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setIcon(make_vector_icon("play", color="#ffffff", size=14))
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._start_scan)
        self.footer.addWidget(self.start_btn)

        self.filter_btn = QPushButton("Show Duplicates")
        self.filter_btn.setObjectName("primaryBtn")
        self.filter_btn.setIcon(make_vector_icon("duplicates", color="#ffffff", size=14))
        self.filter_btn.setCursor(Qt.PointingHandCursor)
        self.filter_btn.clicked.connect(self._apply_and_close)
        self.filter_btn.hide()
        self.footer.addWidget(self.filter_btn)

        root.addLayout(self.footer)

    def _on_engine_changed(self):
        tokens = self.tokens
        if self.rb_dhash.isChecked():
            self.acc_combo.setEnabled(True)
            self.acc_desc.setText("Compares 64-bit gradient hashes. Lower distance means higher similarity requirement.")
            self.acc_desc.setStyleSheet(f"font-size: 11px; color: {tokens['text_muted']};")
        elif self.rb_exact.isChecked():
            self.acc_combo.setEnabled(False)
            self.acc_desc.setText("Exact MD5 Verification: 100% byte-for-byte identical content match.")
            self.acc_desc.setStyleSheet(f"font-size: 11px; color: {tokens['accent']}; font-weight: 600;")
        else:
            self.acc_combo.setEnabled(False)
            self.acc_desc.setText("Fast Size Pre-filter: Groups identical file sizes then verifies with sample hashes.")
            self.acc_desc.setStyleSheet(f"font-size: 11px; color: {tokens['accent']}; font-weight: 600;")

    def _start_scan(self):
        if len(self._actual_paths) < 2:
            show_studio_message(self, "Insufficient Files", "Need at least 2 existing media files to compare.", kind="warning")
            return

        # Determine engine & accuracy
        engine = "dhash"
        max_dist = int(self.acc_combo.currentData())
        if self.rb_exact.isChecked():
            engine = "exact_hash"
            max_dist = 0
        elif self.rb_fast.isChecked():
            engine = "size_fast"
            max_dist = 0

        # UI state transitions to scanning
        self.engine_card.setEnabled(False)
        self.accuracy_card.setEnabled(False)
        self.start_btn.hide()
        self.filter_btn.hide()
        self.close_btn.hide()
        self.pause_btn.show()
        self.pause_btn.setText("Pause")
        self.pause_btn.setIcon(make_vector_icon("pause", color=self.tokens["text"], size=14))
        self.cancel_btn.show()

        tokens = self.tokens
        self.status_badge.setText("Scanning")
        self.status_badge.setStyleSheet(f"""
            background-color: {hex_rgba(tokens['accent'], 30)};
            color: {tokens['accent']};
            border: 1px solid {hex_rgba(tokens['accent'], 80)};
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
        """)
        self.progress_bar.setValue(0)
        self.status_text.setText(f"Starting scan with {engine} engine...")

        # Launch worker thread
        self._scan_thread = DuplicateScanThread(self._actual_paths, max_distance=max_dist, engine=engine, parent=self)
        self._scan_thread.progress_updated.connect(self._on_progress)
        self._scan_thread.status_updated.connect(self._on_status_updated)
        self._scan_thread.finished.connect(self._on_scan_finished)
        self._scan_thread.start()

    def _toggle_pause(self):
        if not self._scan_thread or not self._scan_thread.isRunning():
            return
        tokens = self.tokens
        if self._scan_thread.is_paused():
            self._scan_thread.resume()
            self.pause_btn.setText("Pause")
            self.pause_btn.setIcon(make_vector_icon("pause", color=tokens["text"], size=14))
            self.status_badge.setText("Scanning")
            self.status_badge.setStyleSheet(f"""
                background-color: {hex_rgba(tokens['accent'], 30)};
                color: {tokens['accent']};
                border: 1px solid {hex_rgba(tokens['accent'], 80)};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        else:
            self._scan_thread.pause()
            self.pause_btn.setText("Resume")
            self.pause_btn.setIcon(make_vector_icon("play", color=tokens["text"], size=14))
            self.status_badge.setText("PAUSED")
            self.status_badge.setStyleSheet(f"""
                background-color: {hex_rgba('#f59e0b', 30)};
                color: #f59e0b;
                border: 1px solid {hex_rgba('#f59e0b', 80)};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)

    def _cancel_scan(self):
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.cancel()
            self.status_text.setText("Cancelling scan...")
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int):
        if total <= 0:
            return
        pct = int(done * 100 / total)
        self.progress_bar.setValue(min(100, max(0, pct)))
        self.status_text.setText(f"Analyzing {done:,} / {total:,} files... ({pct}%)")

    def _on_status_updated(self, status: str):
        if status == "paused":
            self.status_text.setText("Scan paused. Click Resume to continue.")

    def _on_scan_finished(self):
        tokens = self.tokens
        self.engine_card.setEnabled(True)
        self.accuracy_card.setEnabled(True)
        self.pause_btn.hide()
        self.cancel_btn.hide()
        self.close_btn.show()

        if not self._scan_thread:
            return

        if self._scan_thread.is_cancelled():
            self.status_badge.setText("Cancelled")
            self.status_badge.setStyleSheet(f"""
                background-color: {hex_rgba(tokens['border'], 45)};
                color: {tokens['text_muted']};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_text.setText("Scan was cancelled by user.")
            self.start_btn.show()
            self.start_btn.setText("Scan Again")
            return

        if self._scan_thread.error:
            self.status_badge.setText("Error")
            self.status_badge.setStyleSheet(f"""
                background-color: {hex_rgba('#ef4444', 30)};
                color: #ef4444;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_text.setText(f"Error: {self._scan_thread.error}")
            self.start_btn.show()
            return

        groups = self._scan_thread.groups
        self._resolved_groups = groups
        total_dup_files = sum(len(g) for g in groups)

        self.progress_bar.setValue(100)
        if total_dup_files > 0:
            self.status_badge.setText(f"Found {len(groups)} groups")
            self.status_badge.setStyleSheet(f"""
                background-color: {hex_rgba('#10b981', 30)};
                color: #10b981;
                border: 1px solid {hex_rgba('#10b981', 80)};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
            self.status_text.setText(f"Scan complete! Found {total_dup_files:,} duplicate files across {len(groups):,} groups.")
            self.filter_btn.show()
            self.filter_btn.setText(f"Show Duplicates ({total_dup_files})")
            self.start_btn.hide()
        else:
            self.status_badge.setText("No Duplicates")
            self.status_badge.setStyleSheet(f"""
                background-color: {hex_rgba(tokens['border'], 45)};
                color: {tokens['text_muted']};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_text.setText("No duplicate or similar files found with current threshold.")
            self.start_btn.show()
            self.start_btn.setText("Scan Again")

    def _apply_and_close(self):
        """Pass results to parent main window, switch to Duplicates Only filter, and close."""
        if self._resolved_groups:
            self._parent_app._on_duplicate_scan_done(self._resolved_groups, self._actual_to_srcs, show_toast=True)
        self.accept()

    def _on_close_clicked(self):
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.cancel()
            self._scan_thread.wait(500)
        self.reject()

    def closeEvent(self, event):
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.cancel()
            self._scan_thread.wait(500)
        super().closeEvent(event)
