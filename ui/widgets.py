"""Reusable Studio Slate UI widgets: ClickSeekSlider, StageViewport, MediaHudOverlay, LoadingOverlay, ToastNotification."""

from PySide6.QtCore import QPropertyAnimation, QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from media.formats import format_duration
from ui.theme import make_vector_icon


class ClickSeekSlider(QSlider):
    """Horizontal slider supporting instant jump-on-click timeline seeking."""

    seek_clicked = Signal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            span = max(1, self.maximum() - self.minimum())
            ratio = max(0.0, min(1.0, event.position().x() / float(self.width())))
            val = self.minimum() + int(round(ratio * span))
            self.setValue(val)
            self.seek_clicked.emit(val)
            event.accept()
            return
        super().mousePressEvent(event)


class StageViewport(QWidget):
    """Responsive stage container free of rigid minimumSizeHint locks, auto-centering its preview card."""

    resized = Signal()

    def __init__(self, child_widget: QWidget, min_w: int = 240, min_h: int = 180, parent=None):
        super().__init__(parent)
        self._min_sz = QSize(min_w, min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.child_widget = child_widget
        child_widget.setParent(self)

    def minimumSizeHint(self):
        return self._min_sz

    def sizeHint(self):
        return QSize(max(self._min_sz.width(), 320), max(self._min_sz.height(), 260))

    def center_child(self):
        if self.child_widget is None:
            return
        vw, vh = self.width(), self.height()
        cw, ch = self.child_widget.width(), self.child_widget.height()
        self.child_widget.move(max(0, (vw - cw) // 2), max(0, (vh - ch) // 2))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()
        self.center_child()


class LoadingOverlay(QDialog):
    """Frameless Studio Slate modal status pill centered over the parent window."""

    def __init__(self, parent):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel("Loading folder...", self)
        self.label.setAlignment(Qt.AlignCenter)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self.label)
        self.setFixedSize(310, 96)
        self.hide()

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def show_with_tokens(self, tokens: dict) -> None:
        bg_rgba = "rgba(18, 20, 27, 238)" if tokens["is_dark"] else "rgba(255, 255, 255, 244)"
        self.label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {tokens['text']}; "
            f"background-color: {bg_rgba}; border: 1px solid {tokens['border_strong']}; "
            f"border-radius: 12px; padding: 18px 22px;"
        )
        parent = self.parentWidget()
        if parent is not None:
            rect = parent.geometry()
            x = rect.x() + (rect.width() - self.width()) // 2
            y = rect.y() + (rect.height() - self.height()) // 2
            self.move(x, y)
        self.show()
        self.raise_()
        QApplication.processEvents()


class ToastNotification(QLabel):
    """Floating transient toast notification with smooth fade-in / fade-out transitions."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._text_width = 280
        self.fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self.fade_out.start)
        self.fade_in.finished.connect(lambda: self._hold_timer.start(2100))
        self.fade_out.finished.connect(self.hide)
        self.hide()

    def show_message(self, text: str, tokens: dict) -> None:
        if self.fade_in.state() == QPropertyAnimation.Running:
            self.fade_in.stop()
        if self.fade_out.state() == QPropertyAnimation.Running:
            self.fade_out.stop()
        self._hold_timer.stop()

        bg_rgba = "rgba(22, 25, 34, 232)" if tokens["is_dark"] else "rgba(255, 255, 255, 240)"
        self.setText(text)
        self.setStyleSheet(
            f"font-size: 12px; font-weight: 600; padding: 8px 16px; border-radius: 10px; "
            f"color: {tokens['text']}; background-color: {bg_rgba}; "
            f"border: 1px solid {tokens['border_strong']}; text-align: center;"
        )
        self._text_width = self.fontMetrics().horizontalAdvance(text) + 36
        self.reposition()

        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()

        self.fade_in.setDuration(180)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_out.setDuration(220)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_in.start()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        available = max(140, parent.width() - 40)
        label_width = min(available, max(260, min(680, self._text_width)))
        x = max(20, (parent.width() - label_width) // 2)
        y = max(56, parent.height() - 220)
        self.setGeometry(x, y, label_width, 42)


class MediaHudOverlay(QFrame):
    """Frosted-glass media HUD capsule floating at the bottom of the main media preview."""

    play_pause_clicked = Signal()
    mute_clicked = Signal()
    seek_pressed = Signal()
    seek_released = Signal(int)
    seek_clicked = Signal(int)

    def __init__(self, parent_label: QWidget, target_size: QSize, is_video: bool, duration_s: float = 0.0):
        super().__init__(parent_label)
        self.setObjectName("mainMediaHud")
        self.is_video = bool(is_video)
        self.compact_labels = False
        self.seek_slider = None
        self.cur_time_lbl = None
        self.tot_time_lbl = None
        self.mute_btn = None

        self.setStyleSheet("""
            QFrame#mainMediaHud {
                background-color: rgba(14, 16, 22, 218);
                border: 1px solid rgba(255, 255, 255, 36);
                border-radius: 12px;
            }
            QLabel {
                color: #e6e8ee;
                background: transparent;
                border: none;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 20);
                color: #f0f2f5;
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
                padding: 0px 8px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 42);
                border-color: rgba(255, 255, 255, 68);
            }
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 45);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
        """)

        self.play_pause_btn = QPushButton("Pause")
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFocusPolicy(Qt.NoFocus)
        self.play_pause_btn.setToolTip("Play / Pause (P)")
        self.play_pause_btn.setFixedHeight(22)
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)

        w_lbl = max(120, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))

        if self.is_video:
            hud_w = min(360, max(84, w_lbl - 12))
            self.compact_labels = hud_w < 190
            use_two_rows = hud_w >= 176 and h_lbl >= 120
            hud_h = 54 if use_two_rows else 32
            self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - hud_h - 8), hud_w, hud_h)

            outer = QVBoxLayout(self)
            outer.setContentsMargins(8, 4 if use_two_rows else 3, 8, 4 if use_two_rows else 3)
            outer.setSpacing(3)

            dur_ms = int(round(duration_s * 1000)) if duration_s > 0 else 0
            if use_two_rows:
                seek_row = QHBoxLayout()
                seek_row.setContentsMargins(0, 0, 0, 0)
                seek_row.setSpacing(5)
                self.cur_time_lbl = QLabel("0:00")
                self.cur_time_lbl.setFixedWidth(28)
                self.seek_slider = ClickSeekSlider(Qt.Horizontal)
                self.seek_slider.setRange(0, max(100, dur_ms))
                self.seek_slider.setFocusPolicy(Qt.NoFocus)
                self.seek_slider.sliderPressed.connect(self.seek_pressed.emit)
                self.seek_slider.sliderMoved.connect(
                    lambda v: self.cur_time_lbl.setText(format_duration(v / 1000.0)) if self.cur_time_lbl else None
                )
                self.seek_slider.sliderReleased.connect(
                    lambda: self.seek_released.emit(int(self.seek_slider.value())) if self.seek_slider else None
                )
                self.seek_slider.seek_clicked.connect(self._handle_seek_click)
                self.tot_time_lbl = QLabel(format_duration(dur_ms / 1000.0) if dur_ms > 0 else "0:00")
                self.tot_time_lbl.setFixedWidth(28)
                self.tot_time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                seek_row.addWidget(self.cur_time_lbl)
                seek_row.addWidget(self.seek_slider, stretch=1)
                seek_row.addWidget(self.tot_time_lbl)
                outer.addLayout(seek_row)

            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.setSpacing(6)
            btn_row.addStretch()
            btn_row.addWidget(self.play_pause_btn)

            self.mute_btn = QPushButton("Sound")
            self.mute_btn.setCursor(Qt.PointingHandCursor)
            self.mute_btn.setFocusPolicy(Qt.NoFocus)
            self.mute_btn.setToolTip("Mute / Unmute (M)")
            self.mute_btn.setFixedHeight(22)
            self.mute_btn.clicked.connect(self.mute_clicked.emit)
            btn_row.addWidget(self.mute_btn)
            btn_row.addStretch()
            outer.addLayout(btn_row)
        else:
            self.compact_labels = w_lbl < 140
            hud_w = min(112, max(60, w_lbl - 12))
            self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - 32 - 8), hud_w, 32)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.addWidget(self.play_pause_btn)

        self.show()
        self.raise_()

    def _handle_seek_click(self, pos_ms: int):
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))
        self.seek_clicked.emit(int(pos_ms))

    def set_duration_ms(self, dur_ms: int):
        if dur_ms <= 0:
            return
        if self.seek_slider is not None:
            self.seek_slider.setRange(0, int(dur_ms))
        if self.tot_time_lbl is not None:
            self.tot_time_lbl.setText(format_duration(dur_ms / 1000.0))

    def set_position_ms(self, pos_ms: int):
        if self.seek_slider is not None:
            self.seek_slider.setValue(int(pos_ms))
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))

    def reposition(self, target_size: QSize, paused: bool, muted: bool):
        w_lbl = max(90, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))
        if self.is_video:
            hud_w = min(360, max(84, w_lbl - 12))
            self.compact_labels = hud_w < 190
            if self.seek_slider is not None:
                show_seek = hud_w >= 176
                self.seek_slider.setVisible(show_seek)
                if self.cur_time_lbl is not None:
                    self.cur_time_lbl.setVisible(show_seek)
                if self.tot_time_lbl is not None:
                    self.tot_time_lbl.setVisible(show_seek)
                hud_h = 54 if show_seek else 32
            else:
                hud_h = self.height() or 32
        else:
            self.compact_labels = w_lbl < 140
            hud_w = min(112, max(60, w_lbl - 12))
            hud_h = 32
        self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - hud_h - 8), hud_w, hud_h)
        self.refresh_labels(paused=paused, muted=muted)
        self.raise_()

    def refresh_labels(self, paused: bool, muted: bool):
        compact = self.compact_labels
        self.play_pause_btn.setText("" if compact else ("Play" if paused else "Pause"))
        self.play_pause_btn.setIcon(make_vector_icon("play" if paused else "pause", "#f0f2f5", 12))
        self.play_pause_btn.setIconSize(QSize(12, 12))
        if self.mute_btn is not None:
            self.mute_btn.setText("" if compact else ("Muted" if muted else "Sound"))
            self.mute_btn.setIcon(make_vector_icon("sound_off" if muted else "sound_on", "#f0f2f5", 12))
            self.mute_btn.setIconSize(QSize(12, 12))


_ClickSeekSlider = ClickSeekSlider
_StageViewport = StageViewport
