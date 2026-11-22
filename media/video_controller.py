"""Zero-disk-lock QtMultimedia synced video+audio controller and OpenCV streaming fallback thread."""

import os
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QThread, QUrl, Signal
from PySide6.QtGui import QImage

from core.config import debug_log
from media.decoders import decode_video_qimages

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink
    HAS_QTMULTIMEDIA = True
except ImportError:
    QMediaPlayer = None
    QAudioOutput = None
    QVideoSink = None
    HAS_QTMULTIMEDIA = False


def dispose_qtmm_video_session(player, output, sink, buf):
    """Stop and release QMediaPlayer/QAudioOutput/QVideoSink/QBuffer handles cleanly."""
    if sink is not None:
        try:
            sink.videoFrameChanged.disconnect()
        except Exception:
            pass
        sink.deleteLater()
    if player is not None:
        try:
            player.stop()
            player.setVideoSink(None)
            player.setAudioOutput(None)
            player.setSource(QUrl())
        except Exception:
            pass
        player.deleteLater()
    if output is not None:
        output.deleteLater()
    if buf is not None:
        try:
            buf.close()
        except Exception:
            pass
        buf.deleteLater()


def create_qtmm_video_session(owner, video_path: str, muted: bool, volume: float, on_frame, on_error=None):
    """Create in-memory QBuffer-backed QtMultimedia video+audio session (<=120 MB) to avoid Windows locks."""
    if not HAS_QTMULTIMEDIA or not video_path or not os.path.exists(video_path):
        return None
    fsize = os.path.getsize(video_path)
    if fsize <= 0 or fsize > 120 * 1024 * 1024:
        return None
    with open(video_path, "rb") as f:
        raw = f.read()
    qbytes = QByteArray(raw)
    qbuf = QBuffer(owner)
    qbuf.setData(qbytes)
    qbuf.open(QIODevice.ReadOnly)
    output = QAudioOutput(owner)
    output.setVolume(max(0.0, min(1.0, float(volume))))
    output.setMuted(bool(muted))
    sink = QVideoSink(owner)
    if on_frame is not None:
        sink.videoFrameChanged.connect(on_frame)
    player = QMediaPlayer(owner)
    player.setAudioOutput(output)
    player.setVideoSink(sink)
    player.setLoops(QMediaPlayer.Infinite)
    if on_error is not None:
        player.errorOccurred.connect(on_error)
    player.setSourceDevice(qbuf, QUrl.fromLocalFile(video_path))
    return player, output, sink, qbuf, qbytes


class VideoDecodeThread(QThread):
    """Decode sampled OpenCV QImages asynchronously in batched chunks for fallback video playback."""

    chunk_ready = Signal(str, list)

    def __init__(
        self,
        video_path: str,
        max_width: int = 720,
        max_height: int = 500,
        max_frames: int = 60,
        chunk_size: int = 8,
        parent=None,
    ):
        super().__init__(parent)
        self.video_path = video_path
        self.max_width = int(max_width)
        self.max_height = int(max_height)
        self.max_frames = int(max_frames)
        self.chunk_size = int(chunk_size)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def _emit_chunk(self, chunk):
        if not self._cancelled and chunk:
            self.chunk_ready.emit(self.video_path, chunk)

    def run(self):
        decode_video_qimages(
            self.video_path,
            max_width=self.max_width,
            max_height=self.max_height,
            max_frames=self.max_frames,
            should_cancel=self.is_cancelled,
            on_chunk=self._emit_chunk,
            chunk_size=self.chunk_size,
        )


class VideoMediaController(QObject):
    """Shared QtMultimedia video+audio playback session controller used by both MainWindow & PreviewDialog."""

    frame_image_ready = Signal(QImage)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    session_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.output = None
        self.sink = None
        self.buffer = None
        self.raw_bytes = None
        self.active = False

    def start(self, video_path: str, muted: bool, volume: float, paused: bool = False) -> bool:
        """Start an in-memory QtMultimedia video+audio session; return False if caller should fallback."""
        self.stop()
        try:
            session = create_qtmm_video_session(
                self,
                video_path,
                muted=muted,
                volume=volume,
                on_frame=self._on_video_frame,
                on_error=self._on_media_error,
            )
            if session is None:
                return False
            self.player, self.output, self.sink, self.buffer, self.raw_bytes = session
            self.active = True
            self.player.positionChanged.connect(self.position_changed.emit)
            self.player.durationChanged.connect(self.duration_changed.emit)
            if paused:
                self.player.pause()
            else:
                self.player.play()
            return True
        except Exception as e:
            debug_log(f"VideoMediaController init warning: {e}")
            self.stop()
            return False

    def _on_video_frame(self, frame):
        if not self.active or not frame.isValid():
            return
        qimg = frame.toImage()
        if not qimg.isNull():
            self.frame_image_ready.emit(qimg)

    def _on_media_error(self, error, error_string=""):
        self.stop()
        self.session_error.emit(f"({error}): {error_string}")

    def play(self):
        if self.player is not None:
            self.player.play()

    def pause(self):
        if self.player is not None:
            self.player.pause()

    def seek(self, pos_ms: int):
        if self.player is not None:
            self.player.setPosition(int(pos_ms))

    def set_muted(self, muted: bool):
        if self.output is not None:
            self.output.setMuted(bool(muted))

    def set_volume(self, volume: float):
        if self.output is not None:
            self.output.setVolume(max(0.0, min(1.0, float(volume))))

    def stop(self):
        self.active = False
        dispose_qtmm_video_session(self.player, self.output, self.sink, self.buffer)
        self.player = None
        self.output = None
        self.sink = None
        self.buffer = None
        self.raw_bytes = None
