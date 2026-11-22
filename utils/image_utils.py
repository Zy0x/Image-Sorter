"""Backward-compatibility facade preserving existing `from utils.image_utils import ...` imports."""

from media.cache import PixmapLRUCache
from media.decoders import (
    _cv2_frame_to_qimage,
    _cv2_frame_to_qpixmap,
    _pil_image_to_qimage,
    decode_video_qimages,
    load_animation_frames,
    load_pixmap,
    read_image_metadata,
    read_video_metadata,
)
from media.duplicates import compute_dhash, find_duplicate_groups, hamming_distance
from media.formats import (
    PIL_FALLBACK_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    _HAS_CV2,
    _HAS_HEIF,
    _HAS_PIL,
    fit_pixmap_to_box,
    format_duration,
    format_file_size,
    is_video_file,
    readable_image_extensions,
    resize_image,
    resize_next_preview,
)

__all__ = [
    "PIL_FALLBACK_EXTENSIONS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "_HAS_CV2",
    "_HAS_HEIF",
    "_HAS_PIL",
    "_cv2_frame_to_qimage",
    "_cv2_frame_to_qpixmap",
    "_pil_image_to_qimage",
    "PixmapLRUCache",
    "compute_dhash",
    "decode_video_qimages",
    "find_duplicate_groups",
    "fit_pixmap_to_box",
    "format_duration",
    "format_file_size",
    "hamming_distance",
    "is_video_file",
    "load_animation_frames",
    "load_pixmap",
    "read_image_metadata",
    "read_video_metadata",
    "readable_image_extensions",
    "resize_image",
    "resize_next_preview",
]
