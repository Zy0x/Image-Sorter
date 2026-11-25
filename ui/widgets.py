"""Reusable Studio Slate UI widgets: ClickSeekSlider, StageViewport, MediaHudOverlay, LoadingOverlay, ToastNotification."""

import os
import time
from PySide6.QtCore import QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from media.formats import format_duration, is_video_file
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


class StudioCheckBox(QCheckBox):
    """Studio Slate QCheckBox with custom anti-aliased vector check box and checkmark."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        tokens = resolve_studio_tokens(self.window())

        h = self.height()
        box_sz = 18.0
        box_y = (h - 18) // 2
        box_rect = QRectF(1.0, float(box_y), box_sz, box_sz)

        is_chk = self.isChecked()
        if is_chk:
            bg_col = QColor(tokens.get("accent", "#3b82f6"))
            border_col = bg_col
        elif self._hovered:
            bg_col = QColor(tokens.get("surface_hover", "#242b3a"))
            border_col = QColor(tokens.get("accent", "#3b82f6"))
        else:
            bg_col = QColor(tokens.get("surface", "#1b202b"))
            border_col = QColor(tokens.get("border_strong", "#3b4358"))

        p.setPen(QPen(border_col, 1.5))
        p.setBrush(bg_col)
        p.drawRoundedRect(box_rect, 4.5, 4.5)

        if is_chk:
            pen = QPen(QColor("#ffffff"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            pts = [
                QPointF(box_rect.left() + 4.2, box_rect.top() + 9.0),
                QPointF(box_rect.left() + 7.2, box_rect.top() + 12.8),
                QPointF(box_rect.left() + 13.8, box_rect.top() + 5.2),
            ]
            p.drawPolyline(QPolygonF(pts))

        txt = self.text()
        if txt:
            text_rect = QRect(int(box_sz + 10), 0, int(self.width() - box_sz - 10), h)
            p.setPen(QColor(tokens.get("text", "#f1f3f9")))
            font = self.font()
            p.setFont(font)
            p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, txt)

        p.end()


class ClickSeekSlider(QSlider):
    """Horizontal slider supporting instant jump-on-click and continuous drag timeline seeking."""

    seek_clicked = Signal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            self.setSliderDown(True)
            self.sliderPressed.emit()
            val = self._pos_to_val(event.position().x())
            self.setValue(val)
            self.seek_clicked.emit(val)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and (event.buttons() & Qt.LeftButton) and self.width() > 0:
            val = self._pos_to_val(event.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.seek_clicked.emit(val)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            val = self._pos_to_val(event.position().x())
            self.setValue(val)
            self.sliderReleased.emit()
            self.seek_clicked.emit(val)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _pos_to_val(self, px: float) -> int:
        w = max(1, self.width())
        ratio = max(0.0, min(1.0, float(px) / float(w)))
        return int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))


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
        super().__init__(parent, Qt.FramelessWindowHint)
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

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

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
            f"font-size: 12px; font-weight: 600; padding: 9px 18px; border-radius: 10px; "
            f"color: {tokens['text']}; background-color: {bg_rgba}; "
            f"border: 1px solid {border_col}; text-align: center;"
        )
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

        fm = self.fontMetrics()
        pad_h = 36  # 18px left + 18px right padding
        pad_v = 18  # 9px top + 9px bottom padding
        raw_text = self.text() or ""

        # Measure text width (handling multiple lines if newlines are present)
        lines = raw_text.split("\n")
        max_line_adv = max((fm.horizontalAdvance(line) for line in lines), default=0)
        desired_w = max_line_adv + pad_h + 16
        available_w = max(160, parent.width() - 48)
        label_width = min(available_w, max(260, min(740, desired_w)))

        # Accurately compute the wrapped text bounding box height
        inner_w = max(80, label_width - pad_h)
        text_rect = fm.boundingRect(
            QRect(0, 0, inner_w, 2000),
            Qt.TextWordWrap | Qt.TextWrapAnywhere | Qt.AlignCenter,
            raw_text,
        )
        label_height = max(38, text_rect.height() + pad_v + 8)

        x = max(20, (parent.width() - label_width) // 2)

        # Position cleanly above all bottom navigation buttons
        win = self.window()
        btn_top = None
        if win is not None and hasattr(win, "prev_button") and win.prev_button is not None:
            try:
                btn_pos = win.prev_button.mapTo(parent, QPoint(0, 0))
                if btn_pos.y() > 40:
                    btn_top = btn_pos.y()
            except Exception:
                btn_top = None

        if btn_top is not None:
            y = max(24, btn_top - label_height - 10)
        else:
            y = max(40, parent.height() - label_height - 180)

        self.setGeometry(x, y, label_width, label_height)
        self.raise_()


class MediaHudOverlay(QFrame):
    """Sleek ultra-compact floating media HUD capsule with auto-hide timer and hover reveal."""

    play_pause_clicked = Signal()
    mute_clicked = Signal()
    volume_changed = Signal(float)
    seek_pressed = Signal()
    seek_released = Signal(int)
    seek_clicked = Signal(int)

    def __init__(
        self,
        parent_label: QWidget,
        target_size: QSize,
        is_video: bool,
        duration_s: float = 0.0,
        volume: float = 0.85,
        tokens: dict = None,
    ):
        super().__init__(parent_label)
        self.setObjectName("mainMediaHud")
        self.is_video = bool(is_video)
        self.compact_labels = True
        self.seek_slider = None
        self.cur_time_lbl = None
        self.tot_time_lbl = None
        self.mute_btn = None
        self.volume_slider = None
        self._tokens = tokens or resolve_studio_tokens(parent_label.window() if parent_label else None)
        self._icon_color = self._tokens["text"]

        self._is_paused = False
        self._is_hovered = False
        self._is_seeking = False

        self.play_pause_btn = QPushButton(self)
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFocusPolicy(Qt.NoFocus)
        self.play_pause_btn.setToolTip("Play / Pause (P)")
        self.play_pause_btn.setFixedSize(24, 24)
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)

        w_lbl = max(120, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))

        row_lay = QHBoxLayout(self)
        row_lay.setContentsMargins(8, 3, 8, 3)
        row_lay.setSpacing(6)
        row_lay.addWidget(self.play_pause_btn)

        if self.is_video:
            dur_ms = int(round(duration_s * 1000)) if duration_s > 0 else 0

            self.cur_time_lbl = QLabel("0:00", self)
            self.cur_time_lbl.setFixedWidth(28)
            self.cur_time_lbl.setAlignment(Qt.AlignCenter)
            row_lay.addWidget(self.cur_time_lbl)

            self.seek_slider = ClickSeekSlider(Qt.Horizontal, self)
            self.seek_slider.setRange(0, max(100, dur_ms))
            self.seek_slider.setFixedHeight(16)
            self.seek_slider.setFocusPolicy(Qt.NoFocus)
            self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
            self.seek_slider.sliderMoved.connect(self._handle_seek_click)
            self.seek_slider.sliderReleased.connect(self._on_seek_released)
            self.seek_slider.seek_clicked.connect(self._handle_seek_click)
            row_lay.addWidget(self.seek_slider, stretch=1)

            self.tot_time_lbl = QLabel(format_duration(dur_ms / 1000.0) if dur_ms > 0 else "0:00", self)
            self.tot_time_lbl.setFixedWidth(28)
            self.tot_time_lbl.setAlignment(Qt.AlignCenter)
            row_lay.addWidget(self.tot_time_lbl)

            self.mute_btn = QPushButton(self)
            self.mute_btn.setCursor(Qt.PointingHandCursor)
            self.mute_btn.setFocusPolicy(Qt.NoFocus)
            self.mute_btn.setToolTip("Mute / Unmute (M)")
            self.mute_btn.setFixedSize(24, 24)
            self.mute_btn.clicked.connect(self.mute_clicked.emit)
            row_lay.addWidget(self.mute_btn)

            self.volume_slider = ClickSeekSlider(Qt.Horizontal, self)
            self.volume_slider.setObjectName("hudVolumeSlider")
            self.volume_slider.setRange(0, 100)
            self.volume_slider.setValue(max(0, min(100, int(volume * 100))))
            self.volume_slider.setFixedWidth(44)
            self.volume_slider.setFixedHeight(16)
            self.volume_slider.setFocusPolicy(Qt.NoFocus)
            self.volume_slider.setToolTip(f"Volume: {int(volume * 100)}%")
            self.volume_slider.valueChanged.connect(self._handle_volume_slider)
            row_lay.addWidget(self.volume_slider)

            hud_w = min(420, max(92, w_lbl - 16))
            hud_h = 32
        else:
            hud_w = min(118, max(54, w_lbl - 16))
            hud_h = 32

        self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - hud_h - 8), hud_w, hud_h)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(120)
        self._fade_anim.finished.connect(self._on_fade_finished)

        self._last_seek_time = 0.0
        self._initial_timer = QTimer(self)
        self._initial_timer.setSingleShot(True)
        self._initial_timer.setInterval(3000)
        self._initial_timer.timeout.connect(self._on_initial_timeout)
        self._auto_hide_timer = self._initial_timer

        self.apply_tokens(self._tokens)
        self.show()
        self.raise_()

        if self.is_video:
            self._initial_timer.start(3000)

    def _on_fade_finished(self):
        if self._opacity_effect.opacity() <= 0.02:
            self.hide()

    def _on_seek_pressed(self):
        self._is_seeking = True
        self._last_seek_time = time.time()
        self.wake_hud(from_hover=True)
        self.seek_pressed.emit()

    def _on_seek_released(self):
        self._is_seeking = False
        self._last_seek_time = time.time()
        val = int(self.seek_slider.value()) if self.seek_slider else 0
        self.seek_released.emit(val)

    def _handle_seek_click(self, pos_ms: int):
        self._last_seek_time = time.time()
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))
        self.seek_clicked.emit(int(pos_ms))
        self.wake_hud(from_hover=True)

    def _handle_volume_slider(self, val: int):
        if self.volume_slider is not None:
            self.volume_slider.setToolTip(f"Volume: {val}%")
        self.volume_changed.emit(val / 100.0)
        self.wake_hud(from_hover=True)

    def _on_initial_timeout(self):
        """Initial 3-second display on video load elapsed; hide if user is not hovering."""
        if not self._is_hovered and not self._is_seeking:
            self.hide_hud(fast=False)

    def _on_auto_hide_timeout(self):
        self._on_initial_timeout()

    def wake_hud(self, from_hover: bool = True):
        """Bring HUD to full opacity immediately when hovered or active."""
        if from_hover:
            self._initial_timer.stop()
        if not self.isVisible():
            self.show()
        self.raise_()
        if self._fade_anim.state() == QPropertyAnimation.Running:
            self._fade_anim.stop()
        if self._opacity_effect.opacity() < 1.0 or self._fade_anim.endValue() != 1.0:
            self._fade_anim.setDuration(100)
            self._fade_anim.setStartValue(self._opacity_effect.opacity())
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.start()
        else:
            self._opacity_effect.setOpacity(1.0)

    def hide_hud(self, fast: bool = True):
        """Immediately hide HUD when no longer hovered."""
        if self._is_seeking or (self.seek_slider is not None and self.seek_slider.isSliderDown()):
            return
        if self._fade_anim.state() == QPropertyAnimation.Running:
            self._fade_anim.stop()
        dur = 80 if fast else 220
        self._fade_anim.setDuration(dur)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def enterEvent(self, event):
        self._is_hovered = True
        self.wake_hud(from_hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        card = self.window().findChild(QWidget, "mainStageCard") if self.window() else None
        if card is None:
            card = self.parentWidget()
        if card is not None and card.isVisible():
            card_rect = QRect(card.mapToGlobal(QPoint(0, 0)), card.size())
            if card_rect.contains(QCursor.pos()):
                self._is_hovered = True
                super().leaveEvent(event)
                return
        self._is_hovered = False
        if not self._is_seeking and not self._initial_timer.isActive():
            self.hide_hud(fast=True)
        super().leaveEvent(event)

    def on_parent_leave(self):
        """Called when mouse leaves the parent preview container."""
        card = self.window().findChild(QWidget, "mainStageCard") if self.window() else None
        if card is None:
            card = self.parentWidget()
        if card is not None and card.isVisible():
            card_rect = QRect(card.mapToGlobal(QPoint(0, 0)), card.size())
            if card_rect.contains(QCursor.pos()):
                self._is_hovered = True
                return
        self._is_hovered = False
        if not self._is_seeking and not self._initial_timer.isActive():
            self.hide_hud(fast=True)

    def apply_tokens(self, tokens: dict = None) -> None:
        """Style HUD surface, time labels, slider, and buttons cleanly for Dark or Light theme."""
        if tokens is not None:
            self._tokens = tokens
        t = self._tokens
        is_dark = t.get("is_dark", True)
        self._icon_color = "#f1f3f9" if is_dark else "#11141c"
        hud_bg = "rgba(15, 18, 26, 220)" if is_dark else "rgba(255, 255, 255, 235)"
        hud_border = "rgba(255, 255, 255, 40)" if is_dark else "rgba(0, 0, 0, 30)"
        lbl_col = "#e6e9f2" if is_dark else "#11141c"
        btn_bg = "rgba(255, 255, 255, 20)" if is_dark else "rgba(0, 0, 0, 15)"
        btn_border = "rgba(255, 255, 255, 35)" if is_dark else "rgba(0, 0, 0, 30)"
        btn_hover = "rgba(255, 255, 255, 45)" if is_dark else "rgba(0, 0, 0, 35)"
        btn_hover_border = "rgba(255, 255, 255, 80)" if is_dark else "rgba(0, 0, 0, 60)"
        groove_bg = "rgba(255, 255, 255, 45)" if is_dark else "rgba(0, 0, 0, 35)"
        accent = t.get("accent", "#3b82f6")

        self.setStyleSheet(f"""
            QFrame#mainMediaHud {{
                background-color: {hud_bg};
                border: 1px solid {hud_border};
                border-radius: 16px;
                min-height: 30px;
                max-height: 30px;
            }}
            QLabel {{
                color: {lbl_col};
                background: transparent;
                border: none;
                font-family: Consolas, monospace;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {self._icon_color};
                border: 1px solid {btn_border};
                border-radius: 12px;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
                border-color: {btn_hover_border};
            }}
            QSlider::groove:horizontal {{
                background: {groove_bg};
                height: 3px;
                border-radius: 1.5px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                height: 3px;
                border-radius: 1.5px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 2px solid {accent};
                width: 8px;
                height: 8px;
                margin: -3px 0;
                border-radius: 5px;
            }}
        """)

    def set_volume(self, volume: float):
        if self.volume_slider is not None:
            val = max(0, min(100, int(volume * 100)))
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(val)
            self.volume_slider.blockSignals(False)
            self.volume_slider.setToolTip(f"Volume: {val}%")

    def set_duration_ms(self, dur_ms: int):
        if dur_ms <= 0:
            return
        if self.seek_slider is not None:
            self.seek_slider.setRange(0, int(dur_ms))
        if self.tot_time_lbl is not None:
            self.tot_time_lbl.setText(format_duration(dur_ms / 1000.0))

    def set_position_ms(self, pos_ms: int, force: bool = False):
        if not force:
            if self._is_seeking:
                return
            if self.seek_slider is not None and self.seek_slider.isSliderDown():
                return
            if time.time() - getattr(self, "_last_seek_time", 0.0) < 0.4:
                return
        if self.seek_slider is not None:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(pos_ms))
            self.seek_slider.blockSignals(False)
        if self.cur_time_lbl is not None:
            self.cur_time_lbl.setText(format_duration(pos_ms / 1000.0))

    def reposition(self, target_size: QSize, paused: bool, muted: bool):
        w_lbl = max(90, int(target_size.width()))
        h_lbl = max(60, int(target_size.height()))
        hud_h = 32

        if self.is_video:
            hud_w = min(420, max(92, w_lbl - 16))
            if self.volume_slider is not None:
                self.volume_slider.setVisible(hud_w >= 300)
            show_time = hud_w >= 220
            if self.cur_time_lbl is not None:
                self.cur_time_lbl.setVisible(show_time)
            if self.tot_time_lbl is not None:
                self.tot_time_lbl.setVisible(show_time)
            if self.seek_slider is not None:
                self.seek_slider.setVisible(hud_w >= 140)
            if self.mute_btn is not None:
                self.mute_btn.setVisible(hud_w >= 140)
        else:
            hud_w = min(118, max(54, w_lbl - 16))

        self.setGeometry(max(4, (w_lbl - hud_w) // 2), max(4, h_lbl - hud_h - 8), hud_w, hud_h)
        self.refresh_labels(paused=paused, muted=muted)

    def refresh_labels(self, paused: bool, muted: bool):
        self._is_paused = bool(paused)
        ic = getattr(self, "_icon_color", "#f1f3f9")
        self.play_pause_btn.setText("")
        self.play_pause_btn.setIcon(make_vector_icon("play" if paused else "pause", ic, 12))
        self.play_pause_btn.setIconSize(QSize(12, 12))
        self.play_pause_btn.setToolTip("Play (P)" if paused else "Pause (P)")

        if self.mute_btn is not None:
            self.mute_btn.setText("")
            self.mute_btn.setIcon(make_vector_icon("sound_off" if muted else "sound_on", ic, 12))
            self.mute_btn.setIconSize(QSize(12, 12))
            self.mute_btn.setToolTip("Unmute (M)" if muted else "Mute (M)")

        if self._is_paused:
            self._initial_timer.stop()
            self.wake_hud()
        else:
            if not self._is_hovered and not self._is_seeking and self.is_video and not self._initial_timer.isActive():
                self.hide_hud(fast=True)


_ClickSeekSlider = ClickSeekSlider
_StageViewport = StageViewport


class FilmstripItem(QFrame):
    """Clickable portrait thumbnail item inside FilmstripBar."""

    clicked = Signal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(44, 64)
        self.setCursor(Qt.PointingHandCursor)
        self.thumb_label = QLabel(self)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setGeometry(2, 2, 40, 60)
        self.thumb_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.thumb_label.setStyleSheet("border-radius: 5px; background: transparent;")
        self.is_active = False
        self.is_flagged = False
        self.is_video = False
        self.is_moved = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        if self.is_flagged:
            # Draw mini gold star badge in top-right corner
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#f59e0b"))
            star_pts = QPolygonF([
                QPointF(self.width() - 7.0, 3.0),
                QPointF(self.width() - 5.8, 5.8),
                QPointF(self.width() - 2.5, 6.2),
                QPointF(self.width() - 4.8, 8.5),
                QPointF(self.width() - 4.0, 11.8),
                QPointF(self.width() - 7.0, 10.0),
                QPointF(self.width() - 10.0, 11.8),
                QPointF(self.width() - 9.2, 8.5),
                QPointF(self.width() - 11.5, 6.2),
                QPointF(self.width() - 8.2, 5.8),
            ])
            p.drawPolygon(star_pts)

        if self.is_video:
            # Draw mini play badge in bottom-center
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 175))
            badge_w, badge_h = 18, 13
            bx = (self.width() - badge_w) / 2
            by = self.height() - badge_h - 4
            p.drawRoundedRect(QRectF(bx, by, badge_w, badge_h), 3, 3)
            p.setBrush(QColor("#ffffff"))
            p.drawPolygon(QPolygonF([
                QPointF(bx + 6.5, by + 3.5),
                QPointF(bx + 12.5, by + badge_h / 2),
                QPointF(bx + 6.5, by + badge_h - 3.5),
            ]))
        p.end()


class FilmstripBar(QFrame):
    """Horizontal portrait thumbnail preview dock docked inside UP NEXT panel."""

    item_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filmstripBar")
        self.setFixedHeight(74)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 4, 6, 4)
        self._layout.setSpacing(6)
        self._layout.setAlignment(Qt.AlignCenter)

        self._items = []
        self._last_files = []
        self._last_current_idx = -1
        self._last_lru_cache = None
        self._last_is_flagged_cb = None
        self._last_is_moved_cb = None
        self._tokens = resolve_studio_tokens(parent.window() if parent else None)
        self.apply_tokens(self._tokens)

    def apply_tokens(self, tokens: dict = None):
        if tokens is not None:
            self._tokens = tokens
        t = self._tokens
        is_dark = t.get("is_dark", True)
        bg = "rgba(18, 22, 31, 210)" if is_dark else "rgba(240, 244, 250, 230)"
        border = t.get("border", "#282e3d")
        self.setStyleSheet(f"""
            QFrame#filmstripBar {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 9px;
            }}
        """)
        self._refresh_items_style()

    def _refresh_items_style(self):
        t = self._tokens
        accent = t.get("accent", "#3b82f6")
        border = t.get("border", "#282e3d")
        surface = t.get("surface", "#1b202b")

        for item in self._items:
            if item.is_active:
                item.setStyleSheet(f"""
                    QFrame {{
                        background-color: {surface};
                        border: 2px solid {accent};
                        border-radius: 7px;
                    }}
                """)
            else:
                dim = "opacity: 0.55;" if item.is_moved else ""
                item.setStyleSheet(f"""
                    QFrame {{
                        background-color: {surface};
                        border: 1px solid {border};
                        border-radius: 7px;
                        {dim}
                    }}
                    QFrame:hover {{
                        border-color: {accent};
                    }}
                """)

    def update_strip(
        self,
        files: list,
        current_idx: int,
        lru_cache=None,
        is_flagged_cb=None,
        is_moved_cb=None,
    ):
        """Update filmstrip cards centered on current_idx."""
        self._last_files = files or []
        self._last_current_idx = current_idx
        self._last_lru_cache = lru_cache
        self._last_is_flagged_cb = is_flagged_cb
        self._last_is_moved_cb = is_moved_cb

        if not files or not (0 <= current_idx < len(files)):
            for it in self._items:
                it.hide()
            self.hide()
            return

        p_win = self.window()
        if p_win is not None and hasattr(p_win, "settings") and not p_win.settings.get("show_filmstrip", True):
            for it in self._items:
                it.hide()
            self.hide()
            return

        total = len(files)
        # Media after UP NEXT starts at current_idx + 2
        # (current_idx is in Main Stage, current_idx + 1 is in UP NEXT Stage)
        start_idx = current_idx + 2
        if start_idx >= total:
            for it in self._items:
                it.hide()
            self.hide()
            return

        self.show()

        # Determine number of slots based on widget width
        w = self.width() if self.width() > 100 else 240
        slots = max(3, min(5, (w - 12) // 50))
        end_idx = min(total, start_idx + slots)
        needed = end_idx - start_idx

        # Expand item pool if needed
        while len(self._items) < needed:
            new_item = FilmstripItem(0, self)
            new_item.clicked.connect(self.item_selected.emit)
            self._items.append(new_item)
            self._layout.addWidget(new_item)

        # Hide extra items
        for i in range(needed, len(self._items)):
            self._items[i].hide()

        # Update active pooled items
        for i, idx in enumerate(range(start_idx, end_idx)):
            item = self._items[i]
            item.show()
            item.index = idx
            fpath = files[idx]
            item.is_active = False
            item.is_video = is_video_file(fpath)
            item.is_flagged = bool(is_flagged_cb(fpath)) if is_flagged_cb else False
            item.is_moved = bool(is_moved_cb(fpath)) if is_moved_cb else False

            name = os.path.basename(fpath)
            status_desc = " (Moved)" if item.is_moved else ""
            flag_desc = " [★ Flagged]" if item.is_flagged else ""
            step_ahead = idx - current_idx
            item.setToolTip(f"+{step_ahead} (#{idx + 1}): {name}{status_desc}{flag_desc}\nClick to jump")

            pix = None
            if lru_cache:
                try:
                    # Non-blocking cache lookup during rapid scrolling
                    if hasattr(lru_cache, "has_pixmap") and lru_cache.has_pixmap(fpath, 100, 150):
                        pix = lru_cache.get_pixmap(fpath, 100, 150)
                    elif hasattr(lru_cache, "get"):
                        pix = lru_cache.get(fpath, 100, 150)
                    elif hasattr(lru_cache, "get_pixmap"):
                        pix = lru_cache.get_pixmap(fpath, 100, 150)
                except Exception:
                    pix = None

            if pix and not pix.isNull():
                # Center crop into portrait card (40x60)
                scaled = pix.scaled(QSize(40, 60), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                if scaled.width() > 40 or scaled.height() > 60:
                    cx = max(0, (scaled.width() - 40) // 2)
                    cy = max(0, (scaled.height() - 60) // 2)
                    scaled = scaled.copy(cx, cy, 40, 60)
                item.thumb_label.setPixmap(scaled)
            else:
                item.thumb_label.setText("VID" if item.is_video else "IMG")
                item.thumb_label.setStyleSheet("font-size: 9.5px; font-weight: 700; color: #949cb0;")

        self._refresh_items_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._last_files and 0 <= self._last_current_idx < len(self._last_files):
            QTimer.singleShot(
                50,
                lambda: self.update_strip(
                    self._last_files,
                    self._last_current_idx,
                    self._last_lru_cache,
                    self._last_is_flagged_cb,
                    self._last_is_moved_cb,
                ),
            )
