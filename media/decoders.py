"""Zero-file-lock decoders and metadata readers for images, animations, and OpenCV video frames."""

import gzip
import os

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap

from media.formats import _HAS_CV2, _HAS_PIL, _PILImage, _PILImageOps, _cv2, is_video_file

_PILLOW_PRIORITY_EXTS = frozenset({".avif", ".heic", ".heif", ".psd"})


def _pil_image_to_qimage(pil_img) -> QImage:
    """Convert PIL.Image into a detached QImage safe across Python GC cycles."""
    if pil_img.mode not in ("RGBA", "RGB"):
        pil_img = pil_img.convert("RGBA")
    if pil_img.mode == "RGBA":
        raw = QByteArray(pil_img.tobytes("raw", "RGBA"))
        qimg = QImage(raw, pil_img.width, pil_img.height, pil_img.width * 4, QImage.Format_RGBA8888)
        return qimg.copy()
    raw = QByteArray(pil_img.tobytes("raw", "RGB"))
    qimg = QImage(raw, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format_RGB888)
    return qimg.copy()


def _cv2_frame_to_qimage(bgr_frame, max_width: int = 0, max_height: int = 0) -> QImage:
    """Convert OpenCV BGR ndarray into a detached QImage (thread-safe for background QThread)."""
    if bgr_frame is None or not _HAS_CV2:
        return QImage()
    h, w = bgr_frame.shape[:2]
    if max_width > 0 and max_height > 0 and (w > max_width or h > max_height):
        scale = min(max_width / float(w), max_height / float(h))
        nw = max(16, int(round(w * scale)))
        nh = max(16, int(round(h * scale)))
        bgr_frame = _cv2.resize(bgr_frame, (nw, nh), interpolation=_cv2.INTER_AREA)
        h, w = bgr_frame.shape[:2]
    rgb = _cv2.cvtColor(bgr_frame, _cv2.COLOR_BGR2RGB)
    ch = rgb.shape[2] if len(rgb.shape) > 2 else 3
    raw = QByteArray(rgb.tobytes())
    return QImage(raw, w, h, ch * w, QImage.Format_RGB888).copy()


def _cv2_frame_to_qpixmap(bgr_frame, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """Convert OpenCV BGR ndarray into a QPixmap (GUI thread only)."""
    qimg = _cv2_frame_to_qimage(
        bgr_frame,
        max_width * 2 if max_width else 0,
        max_height * 2 if max_height else 0,
    )
    if qimg.isNull():
        return QPixmap()
    return QPixmap.fromImage(qimg)


def _iter_sampled_video_bgr(
    path: str,
    max_frames: int = 120,
    min_delay_ms: int = 20,
    should_cancel=None,
):
    """Single shared OpenCV VideoCapture sampler yielding (bgr_frame, delay_ms) with fast cap.grab() skips."""
    if not _HAS_CV2 or not is_video_file(path):
        return
    cap = _cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return
        fps = float(cap.get(_cv2.CAP_PROP_FPS) or 30.0)
        if fps <= 1.0 or fps > 120.0:
            fps = 30.0
        total = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(1, total // max_frames) if total > max_frames else 1
        delay_ms = max(min_delay_ms, int(round((1000.0 / fps) * step)))
        idx = 0
        yielded = 0
        while yielded < max_frames:
            if should_cancel is not None and should_cancel():
                break
            if idx % step == 0:
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    break
                yielded += 1
                yield bgr, delay_ms
            else:
                if not cap.grab():
                    break
            idx += 1
    finally:
        cap.release()


def read_video_metadata(path: str, capture_sizes=None):
    """
    Read (width, height, file_size, fps, frame_count, duration_sec) in one VideoCapture pass
    and immediately close the handle. If capture_sizes is given, also return {size_tuple: QPixmap}.
    """
    try:
        file_size = os.path.getsize(path)
    except OSError:
        file_size = 0

    thumbs = {}
    if not _HAS_CV2:
        meta = (0, 0, file_size, 0.0, 0, 0.0)
        return (meta, thumbs) if capture_sizes else meta

    cap = _cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            meta = (0, 0, file_size, 0.0, 0, 0.0)
            return (meta, thumbs) if capture_sizes else meta
        w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(_cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0 or fps > 240:
            fps = 30.0
        fcount = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = (fcount / fps) if (fcount > 0 and fps > 0) else 0.0
        meta = (w, h, file_size, fps, max(1, fcount), duration)

        if capture_sizes:
            ok, bgr = cap.read()
            if ok and bgr is not None:
                for mw, mh in capture_sizes:
                    pix = _cv2_frame_to_qpixmap(bgr, mw, mh)
                    if not pix.isNull():
                        thumbs[(int(mw), int(mh))] = pix
        return (meta, thumbs) if capture_sizes else meta
    finally:
        cap.release()


def read_image_metadata(path: str):
    """Read (width, height, file_size, format_bytes, frame_count) without locking disk files."""
    try:
        file_size = os.path.getsize(path)
    except OSError:
        file_size = 0

    if is_video_file(path):
        w, h, file_size, _fps, fcount, _dur = read_video_metadata(path)
        ext_fmt = os.path.splitext(path)[1].lstrip(".").lower().encode("ascii", "ignore")
        return w, h, file_size, ext_fmt or b"video", fcount

    ext = os.path.splitext(path)[1].lower()
    if ext in _PILLOW_PRIORITY_EXTS and _HAS_PIL:
        try:
            with _PILImage.open(path) as im:
                w, h = im.size
                count = getattr(im, "n_frames", 1) or 1
                fmt = (im.format or ext.lstrip(".")).lower().encode("ascii", "ignore")
                return w, h, file_size, fmt, max(1, count)
        except Exception:
            pass

    reader = QImageReader(path)
    if ext == ".svgz":
        reader.setFormat(b"svgz")
    else:
        reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    sz = reader.size()
    w = sz.width() if sz.isValid() else 0
    h = sz.height() if sz.isValid() else 0
    try:
        if (reader.transformation().value & 4) and w > 0 and h > 0:
            w, h = h, w
    except Exception:
        pass
    fmt = bytes(reader.format()).lower()
    count = reader.imageCount()
    reader.setFileName("")

    if (w <= 0 or h <= 0 or count <= 1) and _HAS_PIL:
        if w <= 0 or h <= 0 or ext in (".apng", ".png") or ext in _PILLOW_PRIORITY_EXTS:
            try:
                with _PILImage.open(path) as im:
                    if w <= 0 or h <= 0:
                        w, h = im.size
                    n_frames = getattr(im, "n_frames", 1) or 1
                    if n_frames > count:
                        count = n_frames
                    if not fmt:
                        fmt = (im.format or ext.lstrip(".")).lower().encode("ascii", "ignore")
            except Exception:
                pass

    return w, h, file_size, fmt, max(1, count)


def decode_video_qimages(
    path: str,
    max_width: int = 720,
    max_height: int = 500,
    max_frames: int = 120,
    should_cancel=None,
    on_chunk=None,
    chunk_size: int = 10,
):
    """Stream video frames as [(QImage, delay_ms), ...] safe for background QThreads."""
    frames = []
    pending_chunk = []
    for bgr, delay_ms in _iter_sampled_video_bgr(
        path, max_frames=max_frames, min_delay_ms=25, should_cancel=should_cancel
    ):
        qimg = _cv2_frame_to_qimage(bgr, max_width, max_height)
        if not qimg.isNull():
            item = (qimg, delay_ms)
            frames.append(item)
            if on_chunk is not None:
                pending_chunk.append(item)
                if len(pending_chunk) >= chunk_size:
                    on_chunk(list(pending_chunk))
                    pending_chunk.clear()
    if on_chunk is not None and pending_chunk and (should_cancel is None or not should_cancel()):
        on_chunk(list(pending_chunk))
    return frames


def load_animation_frames(path: str, max_width: int = 0, max_height: int = 0, max_frames: int = 180):
    """Extract animated frames [(QPixmap, delay_ms), ...] into memory and immediately release disk handles."""
    if is_video_file(path):
        frames = []
        for bgr, delay_ms in _iter_sampled_video_bgr(path, max_frames=max_frames, min_delay_ms=20):
            pix = _cv2_frame_to_qpixmap(bgr, max_width, max_height)
            if not pix.isNull():
                frames.append((pix, delay_ms))
        return frames

    frames = []
    if _HAS_PIL:
        try:
            with _PILImage.open(path) as im:
                n_frames = getattr(im, "n_frames", 1) or 1
                if n_frames > 1:
                    limit = min(n_frames, max_frames)
                    for i in range(limit):
                        im.seek(i)
                        delay = int(im.info.get("duration", 80) or 80)
                        if delay < 20:
                            delay = 80
                        rgba = im.convert("RGBA")
                        if max_width > 0 and max_height > 0 and (
                            rgba.width > max_width * 2 or rgba.height > max_height * 2
                        ):
                            rgba.thumbnail((max_width * 2, max_height * 2), _PILImage.Resampling.LANCZOS)
                        qimg = _pil_image_to_qimage(rgba)
                        pix = QPixmap.fromImage(qimg)
                        if not pix.isNull():
                            frames.append((pix, delay))
                    if frames:
                        return frames
        except Exception:
            frames.clear()

    ext = os.path.splitext(path)[1].lower()
    if ext in _PILLOW_PRIORITY_EXTS or ext == ".svgz":
        return frames

    reader = QImageReader(path)
    reader.setAutoTransform(True)
    reader.setDecideFormatFromContent(True)
    try:
        while len(frames) < max_frames and reader.canRead():
            img = reader.read()
            if img.isNull():
                break
            delay = reader.nextImageDelay()
            if delay < 20:
                delay = 80
            if max_width > 0 and max_height > 0 and (
                img.width() > max_width * 2 or img.height() > max_height * 2
            ):
                img = img.scaled(
                    QSize(max_width * 2, max_height * 2),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            frames.append((QPixmap.fromImage(img), delay))
            if not reader.jumpToNextImage():
                break
    finally:
        reader.setFileName("")
    return frames


def _load_pixmap_pillow(path: str, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """Load an image via Pillow with EXIF auto-orientation and bounding thumbnail resize."""
    if not _HAS_PIL:
        return QPixmap()
    try:
        with _PILImage.open(path) as pil_img:
            try:
                pil_img = _PILImageOps.exif_transpose(pil_img)
            except Exception:
                pass
            pil_img.load()
            if max_width > 0 and max_height > 0 and (
                pil_img.width > max_width * 2 or pil_img.height > max_height * 2
            ):
                pil_img.thumbnail((max_width * 2, max_height * 2), _PILImage.Resampling.LANCZOS)
            return QPixmap.fromImage(_pil_image_to_qimage(pil_img))
    except Exception:
        return QPixmap()


def load_pixmap(path: str, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """Decode still image or first video keyframe with EXIF orientation and zero disk lock."""
    if is_video_file(path):
        if not _HAS_CV2:
            return QPixmap()
        cap = _cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                return QPixmap()
            ok, bgr = cap.read()
            if ok and bgr is not None:
                return _cv2_frame_to_qpixmap(bgr, max_width, max_height)
            return QPixmap()
        finally:
            cap.release()

    ext = os.path.splitext(path)[1].lower()
    if ext in _PILLOW_PRIORITY_EXTS:
        pix = _load_pixmap_pillow(path, max_width, max_height)
        if not pix.isNull():
            return pix

    reader = QImageReader(path)
    if ext == ".svgz":
        reader.setFormat(b"svgz")
    else:
        reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    if max_width > 0 and max_height > 0:
        sz = reader.size()
        target_w = max(16, int(round(max_width * 1.25)))
        target_h = max(16, int(round(max_height * 1.25)))
        if sz.isValid() and (sz.width() > target_w or sz.height() > target_h):
            scaled = sz.scaled(QSize(target_w, target_h), Qt.AspectRatioMode.KeepAspectRatio)
            if scaled.isValid():
                reader.setScaledSize(scaled)
    image = reader.read()
    reader.setFileName("")
    if not image.isNull():
        return QPixmap.fromImage(image)

    if ext == ".svgz":
        try:
            with gzip.open(path, "rb") as gz:
                svg_bytes = gz.read()
            qba = QByteArray(svg_bytes)
            buf = QBuffer()
            buf.setData(qba)
            buf.open(QIODevice.ReadOnly)
            svg_reader = QImageReader(buf, b"svg")
            svg_img = svg_reader.read()
            buf.close()
            if not svg_img.isNull():
                return QPixmap.fromImage(svg_img)
        except Exception:
            pass

    return _load_pixmap_pillow(path, max_width, max_height)
