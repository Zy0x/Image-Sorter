"""Full-resolution Studio Slate media preview dialog with GPU zoom/pan and synced video+audio."""

import os
import time
from PySide6.QtCore import QPoint, QSize, QTimer, Qt
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from core.config import save_settings, load_settings
from media.decoders import load_animation_frames, load_pixmap
from media.formats import format_duration, format_file_size, is_video_file
from media.video_controller import VideoMediaController
from ui.dialogs.info_dialogs import apply_studio_dialog_style
from ui.theme import make_vector_icon
from ui.widgets import ClickSeekSlider

_ANIM_EXTS = (".gif", ".webp", ".apng", ".avif")


class ImagePreviewDialog(QDialog):
    """High-DPI full-size preview window supporting smooth zoom, cursor pan, GIF/APNG stepping & video+audio."""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.is_video = is_video_file(image_path)
        self.setWindowTitle(f"Preview — {os.path.basename(image_path)}")
        self.resize(980, 700)
        self.setMinimumSize(600, 440)
        self._tokens = apply_studio_dialog_style(self, parent)

        self.zoom_factor = 1.0
        self._fit_mode = True
        self._dragging = False
        self._drag_origin = QPoint()
        self._scroll_origin = QPoint()

        self.anim_frames = []
        self._anim_index = 0
        self._anim_playing = False
        self._frame_step_mode = False
        self._is_seeking = False
        self._last_seek_time = 0.0
        self._duration_ms = 0
        self._position_ms = 0

        self._audio_muted = bool(
            getattr(parent, "video_muted", load_settings().get("video_muted", False))
        )
        self._audio_volume = float(
            getattr(parent, "video_volume", load_settings().get("video_volume", 0.85))
        )

        self.video_controller = VideoMediaController(self)
        self.video_controller.frame_image_ready.connect(self._on_qtmm_frame)
        self.video_controller.position_changed.connect(self._on_qtmm_position)
        self.video_controller.duration_changed.connect(self._on_qtmm_duration)
        self.video_controller.session_error.connect(self._on_qtmm_error)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_anim_frame)

        self.base_pixmap = self._load_initial_media()

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        is_dark = self._tokens.get("is_dark", True)
        accent = self._tokens.get("accent", "#3b82f6")
        bar_bg = "rgba(15, 18, 26, 230)" if is_dark else "rgba(255, 255, 255, 240)"
        bar_border = "rgba(255, 255, 255, 35)" if is_dark else "rgba(0, 0, 0, 30)"
        btn_bg = "rgba(255, 255, 255, 18)" if is_dark else "rgba(0, 0, 0, 15)"
        btn_border = "rgba(255, 255, 255, 30)" if is_dark else "rgba(0, 0, 0, 26)"
        btn_hover = "rgba(255, 255, 255, 42)" if is_dark else "rgba(0, 0, 0, 32)"
        btn_hover_border = "rgba(255, 255, 255, 75)" if is_dark else "rgba(0, 0, 0, 60)"
        btn_pressed = "rgba(255, 255, 255, 65)" if is_dark else "rgba(0, 0, 0, 48)"

        # Top toolbar: info readout + zoom controls + close
        top_bar = QFrame()
        top_bar.setObjectName("previewTopBar")
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(10, 4, 10, 4)
        top_lay.setSpacing(6)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"font-size: 11.5px; font-weight: 600; color: {self._tokens['text']};")
        top_lay.addWidget(self.info_label, stretch=1)

        for label, handler in (
            ("−", lambda: self.adjust_zoom(0.8)),
            ("100%", self.reset_actual_size),
            ("Fit", self.fit_to_window),
            ("+", lambda: self.adjust_zoom(1.25)),
        ):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(handler)
            top_lay.addWidget(btn)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.clicked.connect(self.accept)
        top_lay.addWidget(close_btn)

        top_bar.setStyleSheet(f"""
            QFrame#previewTopBar {{
                background-color: {bar_bg};
                border: 1px solid {bar_border};
                border-radius: 10px;
                min-height: 30px;
                max-height: 30px;
            }}
            QFrame#previewTopBar QPushButton {{
                background-color: {btn_bg};
                color: {self._tokens['text']};
                border: 1px solid {btn_border};
                border-radius: 6px;
                min-height: 22px;
                max-height: 22px;
                padding: 0px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QFrame#previewTopBar QPushButton:hover {{
                background-color: {btn_hover};
                border-color: {btn_hover_border};
            }}
            QFrame#previewTopBar QPushButton:pressed {{
                background-color: {btn_pressed};
            }}
            QFrame#previewTopBar QLabel {{
                color: {self._tokens['text']};
                background: transparent;
                border: none;
                font-size: 11.5px;
                font-weight: 600;
            }}
        """)
        root.addWidget(top_bar)

        # Scrollable canvas area
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {self._tokens['canvas_bg']}; "
            f"border: 1px solid {self._tokens['border']}; border-radius: 10px; }}"
        )
        self.scroll_area.viewport().setStyleSheet(f"background-color: {self._tokens['canvas_bg']};")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            f"background: transparent; border: none; color: {self._tokens['text']}; font-size: 13px; font-weight: 600;"
        )
        self.image_label.setCursor(Qt.OpenHandCursor)
        self.image_label.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.setWidget(self.image_label)
        root.addWidget(self.scroll_area, stretch=1)

        # Bottom media control bar
        self.play_pause_btn = None
        self.mute_btn = None
        self.seek_slider = None
        self.cur_time_lbl = None
        self.tot_time_lbl = None
        self.media_bar = None
        self.prev_btn = None
        self.next_btn = None
        self._build_media_bar(root)

        self._bind_shortcuts()
        self._start_playback_if_applicable()
        self._render_pixmap()
        self._update_info_text()

    # Backwards-compatible properties expected by tests
    @property
    def _audio_player(self):
        return self.video_controller.player

    @property
    def _audio_output(self):
        return self.video_controller.output

    @property
    def _video_sink(self):
        return self.video_controller.sink

    def _load_initial_media(self) -> QPixmap:
        ext = os.path.splitext(self.image_path)[1].lower()
        if self.is_video:
            # Quick bounded frame decode ensures step_frame & fallback work instantly even before QtMM buffers
            frames = load_animation_frames(self.image_path, 1280, 900, max_frames=48)
            if frames:
                self.anim_frames = frames
                return frames[0][0]
            return load_pixmap(self.image_path)

        if ext in _ANIM_EXTS:
            frames = load_animation_frames(self.image_path, 1920, 1440, max_frames=180)
            if len(frames) > 1:
                self.anim_frames = frames
                return frames[0][0]
        return load_pixmap(self.image_path)

    def _build_media_bar(self, root_layout: QVBoxLayout) -> None:
        self.media_bar = QFrame()
        self.media_bar.setObjectName("previewMediaBar")
        bar = QHBoxLayout(self.media_bar)
        bar.setContentsMargins(10, 4, 10, 4)
        bar.setSpacing(6)

        is_dark = self._tokens.get("is_dark", True)
        accent = self._tokens.get("accent", "#3b82f6")
        bar_bg = "rgba(15, 18, 26, 230)" if is_dark else "rgba(255, 255, 255, 240)"
        bar_border = "rgba(255, 255, 255, 35)" if is_dark else "rgba(0, 0, 0, 30)"
        btn_bg = "rgba(255, 255, 255, 18)" if is_dark else "rgba(0, 0, 0, 15)"
        btn_border = "rgba(255, 255, 255, 30)" if is_dark else "rgba(0, 0, 0, 26)"
        btn_hover = "rgba(255, 255, 255, 42)" if is_dark else "rgba(0, 0, 0, 32)"
        btn_hover_border = "rgba(255, 255, 255, 75)" if is_dark else "rgba(0, 0, 0, 60)"
        btn_pressed = "rgba(255, 255, 255, 65)" if is_dark else "rgba(0, 0, 0, 48)"
        groove_bg = "rgba(255, 255, 255, 45)" if is_dark else "rgba(0, 0, 0, 35)"
        lbl_col = "#e2e8f0" if is_dark else "#1e293b"
        icon_col = "#f1f3f9" if is_dark else "#1e293b"

        prev_f = QPushButton()
        prev_f.setToolTip("Previous Media / Video (Left / A / <)")
        prev_f.setCursor(Qt.PointingHandCursor)
        prev_f.setFocusPolicy(Qt.NoFocus)
        prev_f.setIcon(make_vector_icon("step_prev", icon_col, 12))
        prev_f.setIconSize(QSize(12, 12))
        prev_f.clicked.connect(self.show_previous_media)
        self.prev_btn = prev_f
        bar.addWidget(prev_f)

        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFocusPolicy(Qt.NoFocus)
        self.play_pause_btn.setToolTip("Play / Pause (Space / P)")
        self.play_pause_btn.clicked.connect(self.toggle_animation)
        bar.addWidget(self.play_pause_btn)

        next_f = QPushButton()
        next_f.setToolTip("Next Media / Video (Right / D / >)")
        next_f.setCursor(Qt.PointingHandCursor)
        next_f.setFocusPolicy(Qt.NoFocus)
        next_f.setIcon(make_vector_icon("step_next", icon_col, 12))
        next_f.setIconSize(QSize(12, 12))
        next_f.clicked.connect(self.show_next_media)
        self.next_btn = next_f
        bar.addWidget(next_f)

        self.cur_time_lbl = QLabel("0:00")
        self.cur_time_lbl.setFixedWidth(36)
        self.cur_time_lbl.setAlignment(Qt.AlignCenter)

        self.seek_slider = ClickSeekSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.setFocusPolicy(Qt.NoFocus)
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, "_is_seeking", True))
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.seek_slider.seek_clicked.connect(self._on_seek_clicked)

        self.tot_time_lbl = QLabel("0:00")
        self.tot_time_lbl.setFixedWidth(36)
        self.tot_time_lbl.setAlignment(Qt.AlignCenter)

        bar.addWidget(self.cur_time_lbl)
        bar.addWidget(self.seek_slider, stretch=1)
        bar.addWidget(self.tot_time_lbl)

        self.mute_btn = QPushButton()
        self.mute_btn.setCursor(Qt.PointingHandCursor)
        self.mute_btn.setFocusPolicy(Qt.NoFocus)
        self.mute_btn.setToolTip("Mute / Unmute Sound (M)")
        self.mute_btn.clicked.connect(self.toggle_audio_mute)
        bar.addWidget(self.mute_btn)

        self.vol_slider = ClickSeekSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("previewVolSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setFixedWidth(46)
        self.vol_slider.setFixedHeight(16)
        self.vol_slider.setFocusPolicy(Qt.NoFocus)
        vol_val = int(getattr(self, "_audio_volume", 0.85) * 100)
        self.vol_slider.setValue(vol_val)
        self.vol_slider.setToolTip(f"Volume: {vol_val}%")
        self.vol_slider.valueChanged.connect(self._on_vol_slider_changed)
        bar.addWidget(self.vol_slider)

        self._update_media_bar_visibility()

        self.media_bar.setStyleSheet(f"""
            QFrame#previewMediaBar {{
                background-color: {bar_bg};
                border: 1px solid {bar_border};
                border-radius: 17px;
                min-height: 34px;
                max-height: 34px;
            }}
            QFrame#previewMediaBar QPushButton {{
                background-color: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 13px;
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
                padding: 0px;
            }}
            QFrame#previewMediaBar QPushButton:hover {{
                background-color: {btn_hover};
                border-color: {btn_hover_border};
            }}
            QFrame#previewMediaBar QPushButton:pressed {{
                background-color: {btn_pressed};
            }}
            QFrame#previewMediaBar QLabel {{
                color: {lbl_col};
                background: transparent;
                border: none;
                font-family: Consolas, monospace;
                font-size: 11px;
                font-weight: 600;
            }}
            QFrame#previewMediaBar QSlider::groove:horizontal {{
                background: {groove_bg};
                height: 3px;
                border-radius: 1.5px;
            }}
            QFrame#previewMediaBar QSlider::sub-page:horizontal {{
                background: {accent};
                height: 3px;
                border-radius: 1.5px;
            }}
            QFrame#previewMediaBar QSlider::handle:horizontal {{
                background: #ffffff;
                border: 2px solid {accent};
                width: 8px;
                height: 8px;
                margin: -3px 0;
                border-radius: 5px;
            }}
        """)
        root_layout.addWidget(self.media_bar)

    def _update_media_bar_visibility(self) -> None:
        """Toggle control visibility between video timeline, frame animation, and static image."""
        if self.cur_time_lbl is None or self.media_bar is None:
            return
        is_vid = self.is_video
        has_anim = is_vid or len(self.anim_frames) > 1

        self.cur_time_lbl.setVisible(is_vid)
        self.seek_slider.setVisible(is_vid)
        self.tot_time_lbl.setVisible(is_vid)
        self.mute_btn.setVisible(is_vid)
        self.vol_slider.setVisible(is_vid)
        self.play_pause_btn.setVisible(has_anim)
        if self.prev_btn is not None:
            self.prev_btn.setVisible(True)
        if self.next_btn is not None:
            self.next_btn.setVisible(True)

        if is_vid:
            self.cur_time_lbl.setText("0:00")
            self.tot_time_lbl.setText("0:00")
            self.seek_slider.blockSignals(True)
            self.seek_slider.setRange(0, 100)
            self.seek_slider.setValue(0)
            self.seek_slider.blockSignals(False)

    def show_next_media(self) -> None:
        """Advance to the next media item in the parent queue with wrap-around support."""
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "filtered_files") and hasattr(parent, "current_index"):
            files = getattr(parent, "filtered_files", [])
            if not files:
                return
            old_idx = parent.current_index
            if hasattr(parent, "media_queue"):
                next_idx = parent.media_queue.find_valid_next_index(old_idx, files=files)
                if next_idx is None and len(files) > 1:
                    next_idx = parent.media_queue.find_valid_next_index(-1, files=files)
            else:
                next_idx = (old_idx + 1) % len(files)

            if next_idx is not None:
                if hasattr(parent, "_record_nav"):
                    parent._record_nav()
                parent.current_index = next_idx
                if hasattr(parent, "show_current_image"):
                    parent.show_current_image(files)
                if hasattr(parent, "_stop_all_media_playback"):
                    parent._stop_all_media_playback()
                    parent._main_paused = True

                src_path = files[parent.current_index]
                if hasattr(parent, "history_store"):
                    actual = parent.history_store.resolve_actual_path(src_path)
                else:
                    actual = src_path
                self.load_media(actual)

    def show_previous_media(self) -> None:
        """Navigate to the previous media item in the parent queue with wrap-around support."""
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "filtered_files") and hasattr(parent, "current_index"):
            files = getattr(parent, "filtered_files", [])
            if not files:
                return
            old_idx = parent.current_index
            if hasattr(parent, "media_queue"):
                prev_idx = parent.media_queue.find_valid_previous_index(old_idx, files=files)
                if prev_idx is None and len(files) > 1:
                    prev_idx = parent.media_queue.find_valid_previous_index(len(files), files=files)
            else:
                prev_idx = (old_idx - 1) % len(files)

            if prev_idx is not None:
                if hasattr(parent, "_record_nav"):
                    parent._record_nav()
                parent.current_index = prev_idx
                if hasattr(parent, "show_current_image"):
                    parent.show_current_image(files)
                if hasattr(parent, "_stop_all_media_playback"):
                    parent._stop_all_media_playback()
                    parent._main_paused = True

                src_path = files[parent.current_index]
                if hasattr(parent, "history_store"):
                    actual = parent.history_store.resolve_actual_path(src_path)
                else:
                    actual = src_path
                self.load_media(actual)

    def load_media(self, new_path: str) -> None:
        """Dynamically load and display a new media file in-place within the preview dialog."""
        if not new_path or not os.path.exists(new_path):
            return

        self.stop_all_playback()
        self.anim_frames.clear()
        self._anim_index = 0
        self._duration_ms = 0
        self._position_ms = 0

        self.image_path = new_path
        self.is_video = is_video_file(new_path)
        self.setWindowTitle(f"Preview — {os.path.basename(new_path)}")

        self.base_pixmap = self._load_initial_media()
        self._update_media_bar_visibility()
        self._render_pixmap()
        self._update_info_text()
        self._start_playback_if_applicable()
        self._refresh_media_buttons()

    def _adjust_volume(self, delta: float) -> None:
        """Keyboard helper to raise/lower volume in 5% increments."""
        if not self.is_video or self.vol_slider is None:
            return
        new_val = max(0, min(100, int(self.vol_slider.value() + round(delta * 100))))
        self.vol_slider.setValue(new_val)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.accept)
        QShortcut(QKeySequence(Qt.Key_F), self, activated=self.accept)
        QShortcut(QKeySequence(Qt.Key_P), self, activated=self.toggle_animation)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_animation)
        QShortcut(QKeySequence(Qt.Key_M), self, activated=self.toggle_audio_mute)
        QShortcut(QKeySequence(Qt.Key_Comma), self, activated=lambda: self.step_frame(-1))
        QShortcut(QKeySequence(Qt.Key_Period), self, activated=lambda: self.step_frame(1))
        QShortcut(QKeySequence("Shift+Left"), self, activated=lambda: self.step_frame(-1))
        QShortcut(QKeySequence("Shift+Right"), self, activated=lambda: self.step_frame(1))
        QShortcut(QKeySequence(Qt.Key_Plus), self, activated=lambda: self.adjust_zoom(1.25))
        QShortcut(QKeySequence(Qt.Key_Equal), self, activated=lambda: self.adjust_zoom(1.25))
        QShortcut(QKeySequence(Qt.Key_Minus), self, activated=lambda: self.adjust_zoom(0.8))
        QShortcut(QKeySequence(Qt.Key_0), self, activated=self.fit_to_window)

        # Full navigation across parent queue in preview
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=self.show_previous_media)
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=self.show_next_media)
        QShortcut(QKeySequence(Qt.Key_A), self, activated=self.show_previous_media)
        QShortcut(QKeySequence(Qt.Key_D), self, activated=self.show_next_media)
        QShortcut(QKeySequence(Qt.Key_Backspace), self, activated=self.show_previous_media)

        # Volume adjustment shortcuts
        QShortcut(QKeySequence(Qt.Key_Up), self, activated=lambda: self._adjust_volume(0.05))
        QShortcut(QKeySequence(Qt.Key_Down), self, activated=lambda: self._adjust_volume(-0.05))

    def _start_playback_if_applicable(self) -> None:
        if self.is_video:
            self._anim_playing = True
            started_qtmm = self.video_controller.start(
                self.image_path,
                muted=self._audio_muted,
                volume=self._audio_volume,
                paused=False,
            )
            if not started_qtmm and len(self.anim_frames) > 1:
                self._anim_timer.start(max(30, self.anim_frames[0][1]))
        elif len(self.anim_frames) > 1:
            self._anim_playing = True
            self._anim_timer.start(max(25, self.anim_frames[0][1]))
        self._refresh_media_buttons()

    def _on_qtmm_frame(self, qimg: QImage) -> None:
        if self._frame_step_mode or not self._anim_playing:
            return
        pix = QPixmap.fromImage(qimg)
        if not pix.isNull():
            self.base_pixmap = pix
            self._render_pixmap()

    def _on_qtmm_position(self, pos_ms: int) -> None:
        self._position_ms = int(pos_ms)
        if self._is_seeking or (time.time() - getattr(self, "_last_seek_time", 0.0) < 0.4):
            return
        if self.seek_slider is not None and self.seek_slider.isSliderDown():
            return
        if self.seek_slider is not None:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(pos_ms))
            self.seek_slider.blockSignals(False)
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))

    def _on_qtmm_duration(self, dur_ms: int) -> None:
        self._duration_ms = int(dur_ms)
        if dur_ms > 0 and self.seek_slider is not None:
            self.seek_slider.setRange(0, int(dur_ms))
            if self.tot_time_lbl is not None:
                self.tot_time_lbl.setText(format_duration(dur_ms / 1000.0))

    def _on_qtmm_error(self, _err: str) -> None:
        if self._anim_playing and len(self.anim_frames) > 1 and not self._anim_timer.isActive():
            self._anim_timer.start(max(30, self.anim_frames[self._anim_index][1]))

    def _on_seek_released(self) -> None:
        self._is_seeking = False
        self._last_seek_time = time.time()
        if self.seek_slider is not None:
            self._on_seek_clicked(int(self.seek_slider.value()))

    def _on_seek_clicked(self, pos_ms: int) -> None:
        self._last_seek_time = time.time()
        if self.video_controller.player is not None:
            self.video_controller.seek(pos_ms)
        if self.seek_slider is not None:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(pos_ms))
            self.seek_slider.blockSignals(False)
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))

    def _advance_anim_frame(self) -> None:
        if not self.anim_frames or not self._anim_playing:
            return
        self._anim_index = (self._anim_index + 1) % len(self.anim_frames)
        pix, delay = self.anim_frames[self._anim_index]
        self.base_pixmap = pix
        self._render_pixmap()
        self._anim_timer.setInterval(max(25, int(delay)))

    def step_frame(self, delta: int) -> None:
        """Pause playback and advance or rewind a single cached frame or video timeline."""
        if self.is_video:
            cur_ms = getattr(self, "_position_ms", 0)
            target_ms = max(0, cur_ms + int(delta * 80))
            if getattr(self, "_duration_ms", 0) > 0:
                target_ms = min(target_ms, self._duration_ms)
            self._on_seek_clicked(target_ms)
            return

        if not self.anim_frames:
            return
        self._anim_playing = False
        self._frame_step_mode = True
        self._anim_timer.stop()
        if self.video_controller.player is not None:
            self.video_controller.pause()
        self._anim_index = (self._anim_index + int(delta)) % len(self.anim_frames)
        self.base_pixmap = self.anim_frames[self._anim_index][0]
        self._render_pixmap()
        self._refresh_media_buttons()
        self._update_info_text()

    def toggle_animation(self) -> None:
        """Toggle between playing and paused states across QtMultimedia and frame animation."""
        if not self.is_video and len(self.anim_frames) <= 1:
            return
        self._anim_playing = not self._anim_playing
        if self._anim_playing:
            self._frame_step_mode = False
            if self.video_controller.player is not None:
                self.video_controller.play()
            elif len(self.anim_frames) > 1:
                self._anim_timer.start(max(25, self.anim_frames[self._anim_index][1]))
        else:
            self._anim_timer.stop()
            if self.video_controller.player is not None:
                self.video_controller.pause()
        self._refresh_media_buttons()
        self._update_info_text()

    def toggle_audio_mute(self) -> None:
        """Toggle sound mute state and synchronize back to the parent window and persistent settings."""
        if not self.is_video:
            return
        self._audio_muted = not self._audio_muted
        self.video_controller.set_muted(self._audio_muted)
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "set_video_muted"):
            parent.set_video_muted(self._audio_muted, notify=False)
        else:
            settings = load_settings()
            settings["video_muted"] = self._audio_muted
            save_settings(settings)
        self._refresh_media_buttons()

    def _on_vol_slider_changed(self, val: int) -> None:
        """Update live preview video volume and synchronize back to main window and settings."""
        self.vol_slider.setToolTip(f"Volume: {val}%")
        self._audio_volume = val / 100.0
        if self.video_controller is not None:
            self.video_controller.set_volume(self._audio_volume)
        if self._audio_muted and self._audio_volume > 0.0:
            self.toggle_audio_mute()
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "set_video_volume"):
            parent.set_video_volume(self._audio_volume)
        else:
            settings = load_settings()
            settings["video_volume"] = self._audio_volume
            save_settings(settings)

    def _refresh_media_buttons(self) -> None:
        ic = "#f1f3f9" if self._tokens.get("is_dark", True) else "#1e293b"
        if self.play_pause_btn is not None:
            self.play_pause_btn.setText("")
            self.play_pause_btn.setIcon(
                make_vector_icon("pause" if self._anim_playing else "play", ic, 13)
            )
            self.play_pause_btn.setIconSize(QSize(13, 13))
            self.play_pause_btn.setToolTip("Pause (Space / P)" if self._anim_playing else "Play (Space / P)")
        if self.mute_btn is not None:
            self.mute_btn.setText("")
            self.mute_btn.setIcon(
                make_vector_icon("sound_off" if self._audio_muted else "sound_on", ic, 13)
            )
            self.mute_btn.setIconSize(QSize(13, 13))
            self.mute_btn.setToolTip("Unmute Sound (M)" if self._audio_muted else "Mute Sound (M)")

    def _render_pixmap(self) -> None:
        if self.base_pixmap.isNull():
            self.image_label.setText("Unable to load preview")
            self.image_label.resize(320, 120)
            return

        vp = self.scroll_area.viewport().size()
        if self._fit_mode:
            target = self.base_pixmap.size().scaled(
                max(64, vp.width() - 8),
                max(64, vp.height() - 8),
                Qt.KeepAspectRatio,
            )
            self.zoom_factor = target.width() / max(1, self.base_pixmap.width())
        else:
            target = QSize(
                max(24, int(round(self.base_pixmap.width() * self.zoom_factor))),
                max(24, int(round(self.base_pixmap.height() * self.zoom_factor))),
            )

        scaled = self.base_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        self.image_label.setCursor(Qt.OpenHandCursor if not self._fit_mode else Qt.ArrowCursor)

    def _update_info_text(self) -> None:
        fname = os.path.basename(self.image_path)
        sz_str = format_file_size(os.path.getsize(self.image_path)) if os.path.exists(self.image_path) else "—"
        dims = f"{self.base_pixmap.width()}×{self.base_pixmap.height()}" if not self.base_pixmap.isNull() else "—"
        pct = f"{int(round(self.zoom_factor * 100))}%"
        mode = "Fit" if self._fit_mode else pct
        state = ""
        if self.is_video or len(self.anim_frames) > 1:
            state = "  ·  Playing" if self._anim_playing else "  ·  Paused"
        counter_str = ""
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "filtered_files") and parent.filtered_files:
            counter_str = f" [{parent.current_index + 1}/{len(parent.filtered_files)}]"
        self.info_label.setText(f"{fname}{counter_str}  ·  {dims}  ·  {sz_str}  ·  {mode}{state}")

    def adjust_zoom(self, scale_multiplier: float) -> None:
        """Scale zoom around current viewport center cleanly within [10%, 800%]."""
        self._fit_mode = False
        self.zoom_factor = max(0.10, min(8.0, self.zoom_factor * float(scale_multiplier)))
        self._render_pixmap()
        self._update_info_text()

    def fit_to_window(self) -> None:
        """Fit media neatly inside the viewport bounds."""
        self._fit_mode = True
        self._render_pixmap()
        self._update_info_text()

    def reset_actual_size(self) -> None:
        """Reset zoom scale to exact 1:1 original pixels."""
        self._fit_mode = False
        self.zoom_factor = 1.0
        self._render_pixmap()
        self._update_info_text()

    def _smart_double_click_zoom(self, click_pos: QPoint) -> None:
        """Toggle between Fit and 2x cursor-centered zoom on double click."""
        if self._fit_mode:
            rel_x = click_pos.x() / max(1, self.image_label.width())
            rel_y = click_pos.y() / max(1, self.image_label.height())
            self._fit_mode = False
            self.zoom_factor = max(1.0, min(2.5, self.zoom_factor * 2.0))
            self._render_pixmap()
            vp = self.scroll_area.viewport()
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(int(rel_x * self.image_label.width() - vp.width() / 2))
            v_bar.setValue(int(rel_y * self.image_label.height() - vp.height() / 2))
            self._update_info_text()
        else:
            self.fit_to_window()

    def eventFilter(self, obj, event):
        etype = event.type()
        if obj is self.image_label:
            if etype == event.Type.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self._smart_double_click_zoom(event.pos())
                return True
            if etype == event.Type.MouseButtonPress and event.button() == Qt.LeftButton and not self._fit_mode:
                self._dragging = True
                self._drag_origin = event.globalPosition().toPoint()
                self._scroll_origin = QPoint(
                    self.scroll_area.horizontalScrollBar().value(),
                    self.scroll_area.verticalScrollBar().value(),
                )
                self.image_label.setCursor(Qt.ClosedHandCursor)
                return True
            if etype == event.Type.MouseMove and self._dragging:
                delta = event.globalPosition().toPoint() - self._drag_origin
                self.scroll_area.horizontalScrollBar().setValue(self._scroll_origin.x() - delta.x())
                self.scroll_area.verticalScrollBar().setValue(self._scroll_origin.y() - delta.y())
                return True
            if etype == event.Type.MouseButtonRelease and self._dragging:
                self._dragging = False
                self.image_label.setCursor(Qt.OpenHandCursor if not self._fit_mode else Qt.ArrowCursor)
                return True

        if obj is self.scroll_area.viewport() and etype == event.Type.Wheel:
            delta_y = event.angleDelta().y()
            if delta_y != 0:
                self.adjust_zoom(1.15 if delta_y > 0 else 0.87)
                return True

        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self._render_pixmap()
            self._update_info_text()

    def stop_all_playback(self) -> None:
        """Completely stop and teardown all video, audio, and frame animation playback."""
        if hasattr(self, "_anim_timer") and self._anim_timer.isActive():
            self._anim_timer.stop()
        if hasattr(self, "video_controller"):
            self.video_controller.stop()
        self._anim_playing = False
        self._frame_step_mode = False
        self._is_seeking = False

    def done(self, r: int) -> None:
        self.stop_all_playback()
        super().done(r)

    def closeEvent(self, event):
        self.stop_all_playback()
        super().closeEvent(event)
