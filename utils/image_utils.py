# utils/image_utils.py

import os
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtCore import Qt, QSize


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


def read_image_metadata(path: str):
    """
    Baca metadata header gambar tanpa men-decode seluruh piksel.
    Mengembalikan tuple: (width, height, file_size_bytes, format_bytes, image_count).
    """
    try:
        file_size = os.path.getsize(path)
    except OSError:
        file_size = 0

    reader = QImageReader(path)
    reader.setAutoTransform(True)
    reader.setDecideFormatFromContent(True)
    sz = reader.size()
    w = sz.width() if sz.isValid() else 0
    h = sz.height() if sz.isValid() else 0
    # Jika EXIF merotasi 90° atau 270°, tukar dimensi tampilan
    try:
        if (reader.transformation().value & 4) and w > 0 and h > 0:
            w, h = h, w
    except Exception:
        pass
    fmt = bytes(reader.format()).lower()
    count = reader.imageCount()
    reader.setFileName("")
    return w, h, file_size, fmt, count


def load_pixmap(path: str, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """
    Baca gambar dengan orientasi EXIF otomatis (autoTransform) dan deteksi format
    berdasarkan isi file (decideFormatFromContent).
    Jika max_width dan max_height diberikan dan ukuran asli jauh lebih besar,
    decode langsung ke ukuran lebih kecil (setScaledSize) untuk menghemat RAM.
    """
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    reader.setDecideFormatFromContent(True)
    if max_width > 0 and max_height > 0:
        sz = reader.size()
        if sz.isValid() and (sz.width() > max_width * 2 or sz.height() > max_height * 2):
            scaled = sz.scaled(QSize(max_width * 2, max_height * 2), Qt.AspectRatioMode.KeepAspectRatio)
            if scaled.isValid():
                reader.setScaledSize(scaled)
    image = reader.read()
    reader.setFileName("")
    if image.isNull():
        return QPixmap()
    return QPixmap.fromImage(image)


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
