"""Media codecs, LRU cache, duplicate detection, and video+audio playback controllers."""

from media.cache import PixmapLRUCache
from media.decoders import (
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
from media.video_controller import (
    HAS_QTMULTIMEDIA,
    VideoDecodeThread,
    VideoMediaController,
    create_qtmm_video_session,
    dispose_qtmm_video_session,
)

__all__ = [
    "PIL_FALLBACK_EXTENSIONS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "_HAS_CV2",
    "_HAS_HEIF",
    "_HAS_PIL",
    "HAS_QTMULTIMEDIA",
    "PixmapLRUCache",
    "VideoDecodeThread",
    "VideoMediaController",
    "compute_dhash",
    "create_qtmm_video_session",
    "decode_video_qimages",
    "dispose_qtmm_video_session",
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
