# utils/image_utils.py

from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

def resize_image(pixmap: QPixmap) -> QPixmap:
    """
    Resize pixmap untuk area preview utama berdasarkan rasio aspek:
    - Persegi     → 500x500
    - Landscape   → 720x450
    - Portrait    → 450x500
    """
    if pixmap.isNull():
        return pixmap

    # Konversi ke QImage untuk pengubahan ukuran yang lebih cepat
    image = pixmap.toImage()
    width, height = image.width(), image.height()

    # Tetapkan target ukuran berdasarkan orientasi gambar
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