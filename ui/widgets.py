"""Reusable Studio Slate UI widgets: ClickSeekSlider, StageViewport, MediaHudOverlay, LoadingOverlay, ToastNotification."""

from PySide6.QtCore import QPropertyAnimation, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from media.formats import format_duration
from ui.theme import make_vector_icon, resolve_studio_tokens


class StudioSpinBox(QSpinBox):
    """QSpinBox with custom anti-aliased vector up/down stepper chevrons and clean internal padding."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if self.lineEdit() is not None:
            self.lineEdit().setTextMargins(4, 0, 4, 0)

    def paintEvent(self, event):
        super().paintEvent(event)
        tokens = resolve_studio_tokens(self.window())
        col = tokens.get("text_muted", "#949cb0")
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        up_pm = make_vector_icon("chevron_up", col, 10).pixmap(QSize(10, 10))
        dn_pm = make_vector_icon("chevron_down", col, 10).pixmap(QSize(10, 10))
        x = self.width() - 17
        mid_y = self.height() // 2
        p.drawPixmap(QRect(x, mid_y - 10, 10, 10), up_pm)
        p.drawPixmap(QRect(x, mid_y, 10, 10), dn_pm)
        p.end()


class StudioComboBox(QComboBox):
    """QComboBox with custom anti-aliased vector chevron arrow and zero legacy 3D Fusion drop-down box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow_color = "#949cb0"

    def set_arrow_color(self, color: str) -> None:
        self._arrow_color = color
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        icon = make_vector_icon("chevron_down", self._arrow_color, 14)
        pm = icon.pixmap(QSize(14, 14))
        x = self.width() - 22
        y = (self.height() - 14) // 2
        p.drawPixmap(QRect(x, y, 14, 14), pm)
        p.end()


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

        bg_rgba = "rgba(18, 22, 31, 244)" if tokens["is_dark"] else "rgba(255, 255, 255, 248)"
        border_col = tokens["border_strong"]
        self.setText(text)
        self.setStyleSheet(
            f"font-size: 12.5px; font-weight: 600; padding: 8px 18px; border-radius: 10px; "
            f"color: {tokens['text']}; background-color: {bg_rgba}; "
            f"border: 1px solid {border_col}; text-align: center;"
        )
        self._text_width = self.fontMetrics().horizontalAdvance(text) + 48
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

    def __init__(self, parent_label: QWidget, target_size: QSize, is_video: bool, duration_s: float = 0.0, tokens: dict = None):
        super().__init__(parent_label)
        self.setObjectName("mainMediaHud")
        self.is_video = bool(is_video)
        self.compact_labels = False
        self.seek_slider = None
        self.cur_time_lbl = None
        self.tot_time_lbl = None
        self.mute_btn = None
        self._tokens = tokens or resolve_studio_tokens(parent_label.window() if parent_label else None)
        self._icon_color = self._tokens["text"]

        self.play_pause_btn = QPushButton("Pause")
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFocusPolicy(Qt.NoFocus)
        self.play_pause_btn.setToolTip("Play / Pause (P)")
        self.play_pause_btn.setFixedHeight(24)
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)

        w_lbl = max(120, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))

        if self.is_video:
            hud_w = min(370, max(92, w_lbl - 12))
            self.compact_labels = hud_w < 196
            use_two_rows = hud_w >= 180 and h_lbl >= 120
            hud_h = 58 if use_two_rows else 36
            self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - hud_h - 8), hud_w, hud_h)

            outer = QVBoxLayout(self)
            outer.setContentsMargins(10, 5 if use_two_rows else 4, 10, 5 if use_two_rows else 4)
            outer.setSpacing(4)

            dur_ms = int(round(duration_s * 1000)) if duration_s > 0 else 0
            if use_two_rows:
                seek_row = QHBoxLayout()
                seek_row.setContentsMargins(0, 0, 0, 0)
                seek_row.setSpacing(6)
                self.cur_time_lbl = QLabel("0:00")
                self.cur_time_lbl.setFixedWidth(36)
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
                self.tot_time_lbl.setFixedWidth(36)
                self.tot_time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                seek_row.addWidget(self.cur_time_lbl)
                seek_row.addWidget(self.seek_slider, stretch=1)
                seek_row.addWidget(self.tot_time_lbl)
                outer.addLayout(seek_row)

            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.setSpacing(8)
            btn_row.addStretch()
            btn_row.addWidget(self.play_pause_btn)

            self.mute_btn = QPushButton("Sound")
            self.mute_btn.setCursor(Qt.PointingHandCursor)
            self.mute_btn.setFocusPolicy(Qt.NoFocus)
            self.mute_btn.setToolTip("Mute / Unmute (M)")
            self.mute_btn.setFixedHeight(24)
            self.mute_btn.clicked.connect(self.mute_clicked.emit)
            btn_row.addWidget(self.mute_btn)
            btn_row.addStretch()
            outer.addLayout(btn_row)
        else:
            self.compact_labels = w_lbl < 140
            hud_w = min(118, max(64, w_lbl - 12))
            self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - 34 - 8), hud_w, 34)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(8, 4, 8, 4)
            lay.addWidget(self.play_pause_btn)

        self.apply_tokens(self._tokens)
        self.show()
        self.raise_()

    def apply_tokens(self, tokens: dict = None) -> None:
        """Style HUD surface, time labels, slider, and buttons cleanly for Dark or Light theme."""
        if tokens is not None:
            self._tokens = tokens
        t = self._tokens
        is_dark = t.get("is_dark", True)
        self._icon_color = "#f1f3f9" if is_dark else "#11141c"
        hud_bg = "rgba(15, 18, 26, 232)" if is_dark else "rgba(255, 255, 255, 242)"
        hud_border = "rgba(255, 255, 255, 48)" if is_dark else "#adb7c9"
        lbl_col = "#e6e9f2" if is_dark else "#11141c"
        btn_bg = "rgba(255, 255, 255, 24)" if is_dark else "#f4f6fa"
        btn_border = "rgba(255, 255, 255, 42)" if is_dark else "#cfd6e3"
        btn_hover = "rgba(255, 255, 255, 48)" if is_dark else "#e4e9f2"
        btn_hover_border = "rgba(255, 255, 255, 84)" if is_dark else "#94a3b8"
        groove_bg = "rgba(255, 255, 255, 52)" if is_dark else "#cfd6e3"
        accent = t.get("accent", "#3b82f6")

        self.setStyleSheet(f"""
            QFrame#mainMediaHud {{
                background-color: {hud_bg};
                border: 1px solid {hud_border};
                border-radius: 12px;
            }}
            QLabel {{
                color: {lbl_col};
                background: transparent;
                border: none;
                font-family: Consolas, monospace;
                font-size: 10.5px;
                font-weight: 600;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {self._icon_color};
                border: 1px solid {btn_border};
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
                padding: 0px 9px;
                min-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
                border-color: {btn_hover_border};
            }}
            QSlider::groove:horizontal {{
                background: {groove_bg};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 2px solid {accent};
                width: 10px;
                height: 10px;
                margin: -4px 0;
                border-radius: 6px;
            }}
        """)

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
            hud_w = min(370, max(92, w_lbl - 12))
            self.compact_labels = hud_w < 196
            if self.seek_slider is not None:
                show_seek = hud_w >= 180
                self.seek_slider.setVisible(show_seek)
                if self.cur_time_lbl is not None:
                    self.cur_time_lbl.setVisible(show_seek)
                if self.tot_time_lbl is not None:
                    self.tot_time_lbl.setVisible(show_seek)
                hud_h = 58 if show_seek else 36
            else:
                hud_h = self.height() or 36
        else:
            self.compact_labels = w_lbl < 140
            hud_w = min(118, max(64, w_lbl - 12))
            hud_h = 34
        self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - hud_h - 8), hud_w, hud_h)
        self.refresh_labels(paused=paused, muted=muted)
        self.raise_()

    def refresh_labels(self, paused: bool, muted: bool):
        compact = self.compact_labels
        ic = getattr(self, "_icon_color", "#f1f3f9")
        self.play_pause_btn.setText("" if compact else ("Play" if paused else "Pause"))
        self.play_pause_btn.setIcon(make_vector_icon("play" if paused else "pause", ic, 12))
        self.play_pause_btn.setIconSize(QSize(12, 12))
        if self.mute_btn is not None:
            self.mute_btn.setText("" if compact else ("Muted" if muted else "Sound"))
            self.mute_btn.setIcon(make_vector_icon("sound_off" if muted else "sound_on", ic, 12))
            self.mute_btn.setIconSize(QSize(12, 12))


_ClickSeekSlider = ClickSeekSlider
_StageViewport = StageViewport
