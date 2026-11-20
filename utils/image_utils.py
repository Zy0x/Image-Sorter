# utils/image_utils.py

import os
import gzip
from PySide6.QtGui import QPixmap, QImage, QImageReader
from PySide6.QtCore import Qt, QSize, QByteArray, QBuffer, QIODevice

try:
    from PIL import Image as _PILImage, ImageOps as _PILImageOps
    _HAS_PIL = True
except ImportError:
    _PILImage = None
    _PILImageOps = None
    _HAS_PIL = False

try:
    import pillow_heif as _pillow_heif
    _pillow_heif.register_heif_opener()
    _HAS_HEIF = True
except ImportError:
    _HAS_HEIF = False

try:
    import cv2 as _cv2
    _HAS_CV2 = True
except ImportError:
    _cv2 = None
    _HAS_CV2 = False

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".wmv"
})

PIL_FALLBACK_EXTENSIONS = frozenset({
    ".avif", ".heic", ".heif", ".psd", ".apng", ".tga", ".icns",
    ".cur", ".pbm", ".pgm", ".ppm", ".xbm", ".xpm", ".wbmp", ".svgz"
})


def is_video_file(path: str) -> bool:
    """Kembalikan True jika path memiliki ekstensi video yang didukung."""
    ext = os.path.splitext(path)[1].lower()
    return ext in VIDEO_EXTENSIONS


def format_file_size(num_bytes: int) -> str:
    """Format ukuran file byte menjadi string ringkas (B, KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024.0
    if kb < 1024:
        return f"{kb:.0f} KB" if kb >= 10 else f"{kb:.1f} KB"
    mb = kb / 1024.0
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024.0
    return f"{gb:.2f} GB"


def format_duration(seconds: float) -> str:
    """Format durasi detik menjadi M:SS atau H:MM:SS."""
    if not seconds or seconds <= 0:
        return "0:00"
    total = int(round(seconds))
    hrs = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _pil_image_to_qimage(pil_img) -> QImage:
    """Konversi objek PIL.Image ke QImage (deep-copied dari QByteArray agar aman dari GC Python 3.14)."""
    if pil_img.mode not in ("RGBA", "RGB"):
        pil_img = pil_img.convert("RGBA")
    if pil_img.mode == "RGBA":
        raw = QByteArray(pil_img.tobytes("raw", "RGBA"))
        qimg = QImage(raw, pil_img.width, pil_img.height, pil_img.width * 4, QImage.Format_RGBA8888)
        return qimg.copy()
    raw = QByteArray(pil_img.tobytes("raw", "RGB"))
    qimg = QImage(raw, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format_RGB888)
    return qimg.copy()


def _cv2_frame_to_qpixmap(bgr_frame, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """Konversi frame BGR numpy array dari OpenCV menjadi QPixmap (via QByteArray agar aman dari GC)."""
    if bgr_frame is None or not _HAS_CV2:
        return QPixmap()
    rgb = _cv2.cvtColor(bgr_frame, _cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    raw = QByteArray(rgb.tobytes())
    qimg = QImage(raw, w, h, ch * w, QImage.Format_RGB888).copy()
    if max_width > 0 and max_height > 0 and (w > max_width * 2 or h > max_height * 2):
        qimg = qimg.scaled(
            QSize(max_width * 2, max_height * 2),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return QPixmap.fromImage(qimg)


def read_video_metadata(path: str):
    """
    Baca metadata video (width, height, file_size, fps, frame_count, duration_sec)
    menggunakan OpenCV dan pastikan handle file segera dilepas (cap.release()).
    """
    try:
        file_size = os.path.getsize(path)
    except OSError:
        file_size = 0
    if not _HAS_CV2:
        return 0, 0, file_size, 0.0, 0, 0.0
    cap = _cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return 0, 0, file_size, 0.0, 0, 0.0
        w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(_cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0 or fps > 240:
            fps = 30.0
        fcount = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = (fcount / fps) if (fcount > 0 and fps > 0) else 0.0
        return w, h, file_size, fps, max(1, fcount), duration
    finally:
        cap.release()


def read_image_metadata(path: str):
    """
    Baca metadata header gambar/video tanpa mengunci file di disk.
    Mengembalikan tuple: (width, height, file_size_bytes, format_bytes, image_count).
    """
    try:
        file_size = os.path.getsize(path)
    except OSError:
        file_size = 0

    if is_video_file(path):
        w, h, file_size, _fps, fcount, _dur = read_video_metadata(path)
        ext_fmt = os.path.splitext(path)[1].lstrip(".").lower().encode("ascii", "ignore")
        return w, h, file_size, ext_fmt or b"video", fcount

    ext = os.path.splitext(path)[1].lower()
    # Format yang memerlukan Pillow langsung (tidak didukung QImageReader bawaan)
    if ext in (".avif", ".heic", ".heif", ".psd") and _HAS_PIL:
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

    # Fallback Pillow untuk AVIF, HEIC/HEIF, PSD, APNG, atau file yang tidak dikenali Qt
    if (w <= 0 or h <= 0 or count <= 1) and _HAS_PIL:
        ext = os.path.splitext(path)[1].lower()
        if w <= 0 or h <= 0 or ext in (".apng", ".png", ".avif", ".heic", ".heif", ".psd"):
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


def load_animation_frames(path: str, max_width: int = 0, max_height: int = 0, max_frames: int = 180):
    """
    Ekstrak daftar frame animasi [(QPixmap, delay_ms), ...] ke memori dan segera tutup file.
    Mendukung GIF, Animated WebP, APNG, Animated AVIF/HEIF, serta Video singkat.
    Tidak ada handle file yang tertinggal di Windows.
    """
    frames = []
    if is_video_file(path):
        if not _HAS_CV2:
            return frames
        cap = _cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                return frames
            fps = float(cap.get(_cv2.CAP_PROP_FPS) or 30.0)
            if fps <= 1.0 or fps > 120.0:
                fps = 30.0
            total = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
            step = max(1, total // max_frames) if total > max_frames else 1
            delay_ms = max(20, int(round((1000.0 / fps) * step)))
            idx = 0
            while len(frames) < max_frames:
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    break
                if idx % step == 0:
                    pix = _cv2_frame_to_qpixmap(bgr, max_width, max_height)
                    if not pix.isNull():
                        frames.append((pix, delay_ms))
                idx += 1
        finally:
            cap.release()
        return frames

    # Coba dengan Pillow terlebih dahulu untuk multi-frame (mendukung GIF, WebP, APNG, AVIF, HEIC)
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
    if ext in (".avif", ".heic", ".heif", ".psd", ".svgz"):
        return frames

    # Fallback QImageReader multi-frame
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


def load_pixmap(path: str, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """
    Baca gambar atau thumbnail video dengan orientasi EXIF otomatis dan deteksi format
    berdasarkan isi file. Mendukung fallback Pillow (AVIF, HEIC/HEIF, PSD, APNG, TGA, ICNS)
    dan OpenCV (MP4, WebM, MKV, MOV, AVI) tanpa mengunci file di disk.
    """
    if is_video_file(path):
        if not _HAS_CV2:
            return QPixmap()
        cap = _cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                return QPixmap()
            total = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total > 6:
                cap.set(_cv2.CAP_PROP_POS_FRAMES, min(5, total // 4))
            ok, bgr = cap.read()
            if not ok or bgr is None:
                cap.set(_cv2.CAP_PROP_POS_FRAMES, 0)
                ok, bgr = cap.read()
            if ok and bgr is not None:
                return _cv2_frame_to_qpixmap(bgr, max_width, max_height)
            return QPixmap()
        finally:
            cap.release()

    ext = os.path.splitext(path)[1].lower()
    # Format yang memerlukan Pillow langsung (AVIF, HEIC, HEIF, PSD)
    if ext in (".avif", ".heic", ".heif", ".psd") and _HAS_PIL:
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
                qimg = _pil_image_to_qimage(pil_img)
                return QPixmap.fromImage(qimg)
        except Exception:
            pass

    reader = QImageReader(path)
    if ext == ".svgz":
        reader.setFormat(b"svgz")
    else:
        reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    if max_width > 0 and max_height > 0:
        sz = reader.size()
        if sz.isValid() and (sz.width() > max_width * 2 or sz.height() > max_height * 2):
            scaled = sz.scaled(QSize(max_width * 2, max_height * 2), Qt.AspectRatioMode.KeepAspectRatio)
            if scaled.isValid():
                reader.setScaledSize(scaled)
    image = reader.read()
    reader.setFileName("")
    if not image.isNull():
        return QPixmap.fromImage(image)

    # Fallback khusus .svgz (dekompresi gzip ke buffer SVG di memori)
    if path.lower().endswith(".svgz"):
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

    # Fallback Pillow (AVIF, HEIC, HEIF, PSD, TGA, ICNS, dll.)
    if _HAS_PIL:
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
                qimg = _pil_image_to_qimage(pil_img)
                return QPixmap.fromImage(qimg)
        except Exception:
            pass

    return QPixmap()


def resize_image(pixmap: QPixmap) -> QPixmap:
    """
    Resize pixmap untuk area preview utama berdasarkan rasio aspek:
    - Persegi     → 500x500
    - Landscape   → 720x450
    - Portrait    → 450x500
    """
    if pixmap.isNull():
        return pixmap

    image = pixmap.toImage()
    width, height = image.width(), image.height()

    if width == height:
        target_width, target_height = 500, 500
    elif width > height:
        target_width, target_height = 720, 450  # Landscape
    else:
        target_width, target_height = 450, 500  # Portrait

    resized_image = image.scaled(
        target_width,
        target_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )
    return QPixmap.fromImage(resized_image)


def resize_next_preview(pixmap: QPixmap, max_width: int = 200, max_height: int = 260) -> QPixmap:
    """
    Resize pixmap untuk preview berikutnya (thumbnail kecil).
    Parameter `max_width` dan `max_height` dapat disesuaikan secara opsional.
    """
    if pixmap.isNull():
        return pixmap

    image = pixmap.toImage()
    resized_image = image.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation
    )
    return QPixmap.fromImage(resized_image)
