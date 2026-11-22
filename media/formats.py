"""Supported media extension registries, format detection, size/duration formatters, and pixmap sizing."""

import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QPixmap

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
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".wmv",
})

PIL_FALLBACK_EXTENSIONS = frozenset({
    ".avif", ".heic", ".heif", ".psd", ".apng", ".tga", ".icns",
    ".cur", ".pbm", ".pgm", ".ppm", ".xbm", ".xpm", ".wbmp", ".svgz",
})

SUPPORTED_IMAGE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".jfif", ".gif", ".bmp", ".webp",
    ".avif", ".heic", ".heif", ".apng",
    ".tiff", ".tif", ".ico", ".cur", ".icns", ".svg", ".svgz",
    ".tga", ".psd", ".pbm", ".pgm", ".ppm", ".xbm", ".xpm", ".wbmp",
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".wmv",
)

_READABLE_EXTENSIONS = None


def is_video_file(path: str) -> bool:
    """Return True if path has a supported video extension."""
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def format_file_size(num_bytes: int) -> str:
    """Format byte size into compact human-readable string (B, KB, MB, GB)."""
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
    """Format seconds into M:SS or H:MM:SS."""
    if not seconds or seconds <= 0:
        return "0:00"
    total = int(round(seconds))
    hrs = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def readable_image_extensions():
    """Return cached frozenset of extensions readable by Qt, Pillow/HEIF, or OpenCV on this system."""
    global _READABLE_EXTENSIONS
    if _READABLE_EXTENSIONS is None:
        qt_formats = {
            bytes(f).decode("ascii", "ignore").lower()
            for f in QImageReader.supportedImageFormats()
        }
        aliases = {
            ".jpg": "jpeg",
            ".jpeg": "jpeg",
            ".jfif": "jpeg",
            ".tiff": "tiff",
            ".tif": "tiff",
            ".heic": "heic",
            ".heif": "heif",
            ".apng": "png",
        }
        result = set()
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            name = ext.lstrip(".")
            if name in qt_formats or aliases.get(ext, name) in qt_formats:
                result.add(ext)
            elif ext in VIDEO_EXTENSIONS and _HAS_CV2:
                result.add(ext)
            elif ext in (".heic", ".heif") and (_HAS_HEIF or _HAS_PIL):
                result.add(ext)
            elif ext in PIL_FALLBACK_EXTENSIONS and _HAS_PIL:
                result.add(ext)
        _READABLE_EXTENSIONS = frozenset(result)
    return _READABLE_EXTENSIONS


def fit_pixmap_to_box(pixmap: QPixmap, max_w: int, max_h: int) -> QPixmap:
    """Scale pixmap cleanly within (max_w x max_h) while preserving aspect ratio."""
    if pixmap.isNull():
        return pixmap
    mw = max(48, int(max_w))
    mh = max(48, int(max_h))
    return pixmap.scaled(mw, mh, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def resize_image(pixmap: QPixmap) -> QPixmap:
    """Legacy aspect-bucket preview scaler retained for backward-compatible fallback callers."""
    if pixmap.isNull():
        return pixmap
    w, h = pixmap.width(), pixmap.height()
    if w == h:
        tw, th = 500, 500
    elif w > h:
        tw, th = 720, 450
    else:
        tw, th = 450, 500
    return pixmap.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def resize_next_preview(pixmap: QPixmap, max_width: int = 200, max_height: int = 260) -> QPixmap:
    """Scale upcoming media thumbnail cleanly within UP NEXT budget."""
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
