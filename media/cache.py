"""In-memory LRU cache for decoded pixmaps, image/video metadata, and animation frames."""

import os
from collections import OrderedDict
from PySide6.QtGui import QPixmap

from media.decoders import (
    load_animation_frames,
    load_pixmap,
    read_image_metadata,
    read_video_metadata,
)
from media.formats import is_video_file


class PixmapLRUCache:
    """Fast stat-keyed LRU cache enabling ~2-4 ms back/forth navigation and Rapid Move."""

    def __init__(self, max_entries: int = 36, capacity: int = None):
        limit = capacity if capacity is not None else max_entries
        self.max_entries = max(8, int(limit))
        self._pix_cache = OrderedDict()
        self._meta_cache = OrderedDict()
        self._video_meta_cache = OrderedDict()
        self._anim_cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _file_token(path: str):
        try:
            st = os.stat(path)
            norm = os.path.normcase(os.path.normpath(path))
            return norm, st.st_mtime_ns, st.st_size
        except OSError:
            return None

    def get_metadata(self, path: str):
        tok = self._file_token(path)
        if tok is None:
            return 0, 0, 0, b"", 1
        if tok in self._meta_cache:
            self._meta_cache.move_to_end(tok)
            return self._meta_cache[tok]
        meta = read_image_metadata(path)
        self._meta_cache[tok] = meta
        if len(self._meta_cache) > self.max_entries * 4:
            self._meta_cache.popitem(last=False)
        return meta

    def get_video_metadata(self, path: str):
        tok = self._file_token(path)
        if tok is None:
            return 0, 0, 0, 0.0, 0, 0.0
        if tok in self._video_meta_cache:
            self._video_meta_cache.move_to_end(tok)
            return self._video_meta_cache[tok]
        if is_video_file(path):
            vmeta, thumbs = read_video_metadata(path, capture_sizes=((720, 500), (200, 260)))
            self._video_meta_cache[tok] = vmeta
            if len(self._video_meta_cache) > self.max_entries * 4:
                self._video_meta_cache.popitem(last=False)
            for (mw, mh), pix in thumbs.items():
                pkey = (tok, mw, mh)
                if pkey not in self._pix_cache:
                    self._pix_cache[pkey] = pix
                    if len(self._pix_cache) > self.max_entries:
                        self._pix_cache.popitem(last=False)
            return vmeta
        vmeta = read_video_metadata(path)
        self._video_meta_cache[tok] = vmeta
        return vmeta

    def get_animation_frames(self, path: str, max_width: int = 0, max_height: int = 0, max_frames: int = 60):
        tok = self._file_token(path)
        if tok is None:
            return []
        key = (tok, int(max_width), int(max_height), int(max_frames))
        if key in self._anim_cache:
            self.hits += 1
            self._anim_cache.move_to_end(key)
            return self._anim_cache[key]
        self.misses += 1
        frames = load_animation_frames(path, max_width, max_height, max_frames=max_frames)
        if frames:
            self._anim_cache[key] = frames
            if len(self._anim_cache) > max(6, self.max_entries // 3):
                self._anim_cache.popitem(last=False)
        return frames

    def set_animation_frames(self, path: str, max_width: int, max_height: int, max_frames: int, frames):
        tok = self._file_token(path)
        if tok is None or not frames:
            return
        key = (tok, int(max_width), int(max_height), int(max_frames))
        self._anim_cache[key] = list(frames)
        if len(self._anim_cache) > max(6, self.max_entries // 3):
            self._anim_cache.popitem(last=False)

    def has_animation_frames(self, path: str, max_width: int = 0, max_height: int = 0, max_frames: int = 60) -> bool:
        tok = self._file_token(path)
        if tok is None:
            return False
        return (tok, int(max_width), int(max_height), int(max_frames)) in self._anim_cache

    def get_pixmap(self, path: str, max_width: int = 0, max_height: int = 0) -> QPixmap:
        tok = self._file_token(path)
        if tok is None:
            return QPixmap()
        key = (tok, int(max_width), int(max_height))
        if key in self._pix_cache:
            self.hits += 1
            self._pix_cache.move_to_end(key)
            return self._pix_cache[key]
        self.misses += 1
        pix = load_pixmap(path, max_width, max_height)
        if not pix.isNull():
            self._pix_cache[key] = pix
            if len(self._pix_cache) > self.max_entries:
                self._pix_cache.popitem(last=False)
        return pix

    def has_pixmap(self, path: str, max_width: int = 0, max_height: int = 0) -> bool:
        tok = self._file_token(path)
        if tok is None:
            return False
        return (tok, int(max_width), int(max_height)) in self._pix_cache

    def get_or_load(self, path: str, max_width: int = 0, max_height: int = 0) -> QPixmap:
        """Alias for get_pixmap for flexible LRU retrieval."""
        return self.get_pixmap(path, max_width, max_height)

    def get(self, path: str, max_width: int = 0, max_height: int = 0):
        tok = self._file_token(path)
        if tok is None:
            return None
        key = (tok, int(max_width), int(max_height))
        if key in self._pix_cache:
            self.hits += 1
            self._pix_cache.move_to_end(key)
            return self._pix_cache[key]
        self.misses += 1
        return None

    def put(self, path: str, pix: QPixmap, max_width: int = 0, max_height: int = 0) -> None:
        tok = self._file_token(path)
        if tok is None or pix is None or pix.isNull():
            return
        key = (tok, int(max_width), int(max_height))
        self._pix_cache[key] = pix
        self._pix_cache.move_to_end(key)
        if len(self._pix_cache) > self.max_entries:
            self._pix_cache.popitem(last=False)

    def invalidate(self, path: str) -> None:
        norm = os.path.normcase(os.path.normpath(path))
        for store in (self._pix_cache, self._meta_cache, self._video_meta_cache, self._anim_cache):
            stale = [k for k in store if (isinstance(k, tuple) and isinstance(k[0], tuple) and k[0][0] == norm)]
            for k in stale:
                del store[k]

    def clear(self):
        self._pix_cache.clear()
        self._meta_cache.clear()
        self._video_meta_cache.clear()
        self._anim_cache.clear()
