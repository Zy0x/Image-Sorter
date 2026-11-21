# utils/image_utils.py

import os
import gzip
from collections import OrderedDict
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


def _cv2_frame_to_qimage(bgr_frame, max_width: int = 0, max_height: int = 0) -> QImage:
    """Konversi frame BGR numpy array dari OpenCV menjadi QImage (aman dipanggil dari background QThread)."""
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
    """Konversi frame BGR numpy array dari OpenCV menjadi QPixmap."""
    qimg = _cv2_frame_to_qimage(bgr_frame, max_width * 2 if max_width else 0, max_height * 2 if max_height else 0)
    if qimg.isNull():
        return QPixmap()
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


def decode_video_qimages(
    path: str,
    max_width: int = 720,
    max_height: int = 500,
    max_frames: int = 120,
    should_cancel=None,
    on_chunk=None,
    chunk_size: int = 10,
):
    """
    Decode frame video menjadi list [(QImage, delay_ms), ...] secara cepat menggunakan
    cap.grab() + cv2.resize() di C++. Aman dijalankan di background QThread tanpa
    membekukan UI sama sekali (0 ms UI lag) dan otomatis menutup file (cap.release()).
    """
    frames = []
    if not _HAS_CV2 or not is_video_file(path):
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
        delay_ms = max(25, int(round((1000.0 / fps) * step)))
        idx = 0
        pending_chunk = []
        while len(frames) < max_frames:
            if should_cancel is not None and should_cancel():
                break
            if idx % step == 0:
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    break
                qimg = _cv2_frame_to_qimage(bgr, max_width, max_height)
                if not qimg.isNull():
                    item = (qimg, delay_ms)
                    frames.append(item)
                    if on_chunk is not None:
                        pending_chunk.append(item)
                        if len(pending_chunk) >= chunk_size:
                            on_chunk(list(pending_chunk))
                            pending_chunk.clear()
            else:
                if not cap.grab():
                    break
            idx += 1
        if on_chunk is not None and pending_chunk and (should_cancel is None or not should_cancel()):
            on_chunk(list(pending_chunk))
    finally:
        cap.release()
    return frames


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
                if idx % step == 0:
                    ok, bgr = cap.read()
                    if not ok or bgr is None:
                        break
                    pix = _cv2_frame_to_qpixmap(bgr, max_width, max_height)
                    if not pix.isNull():
                        frames.append((pix, delay_ms))
                else:
                    if not cap.grab():
                        break
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


class PixmapLRUCache:
    """
    Cache LRU ultra-cepat untuk menyimpan hasil decode QPixmap, metadata gambar/video,
    dan frame animasi/video berdasarkan (normalized_path, mtime_ns, size, max_w, max_h).
    Membuat navigasi <- / -> dan Rapid Move pada gambar maupun video menjadi 0 ms (instan).
    """
    def __init__(self, max_entries: int = 36):
        self.max_entries = max(8, int(max_entries))
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
        file_size = tok[2]
        if _HAS_CV2 and is_video_file(path):
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
                vmeta = (w, h, file_size, fps, max(1, fcount), duration)
                self._video_meta_cache[tok] = vmeta
                if len(self._video_meta_cache) > self.max_entries * 4:
                    self._video_meta_cache.popitem(last=False)
                # Sekalian baca frame pertama ke _pix_cache agar tidak perlu buka VideoCapture 2x!
                ok, bgr = cap.read()
                if ok and bgr is not None:
                    for mw, mh in ((720, 500), (200, 260)):
                        pkey = (tok, mw, mh)
                        if pkey not in self._pix_cache:
                            pix = _cv2_frame_to_qpixmap(bgr, mw, mh)
                            if not pix.isNull():
                                self._pix_cache[pkey] = pix
                                if len(self._pix_cache) > self.max_entries:
                                    self._pix_cache.popitem(last=False)
                return vmeta
            finally:
                cap.release()
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

    def clear(self):
        self._pix_cache.clear()
        self._meta_cache.clear()
        self._video_meta_cache.clear()
        self._anim_cache.clear()


def compute_dhash(path: str, hash_size: int = 8):
    """
    Hitung 64-bit Difference Perceptual Hash (dHash) dari gambar atau thumbnail video.
    Mengecilkan gambar langsung saat decode ke (hash_size+1) x hash_size grayscale
    agar pemindaian ratusan/ribuan gambar sangat cepat dan hemat memori.
    Mengembalikan int 64-bit, atau None jika gagal dibaca.
    """
    w_target = hash_size + 1
    h_target = hash_size

    # Jalur cepat via Pillow untuk gambar (termasuk AVIF, HEIC, PSD, PNG, JPG, WEBP)
    if _HAS_PIL and not is_video_file(path) and not path.lower().endswith((".svg", ".svgz")):
        try:
            with _PILImage.open(path) as im:
                try:
                    im = _PILImageOps.exif_transpose(im)
                except Exception:
                    pass
                gray = im.convert("L").resize((w_target, h_target), _PILImage.Resampling.BILINEAR)
                pixels = list(gray.getdata())
                bits = 0
                for row in range(h_target):
                    base = row * w_target
                    for col in range(hash_size):
                        bits = (bits << 1) | (1 if pixels[base + col] > pixels[base + col + 1] else 0)
                return bits
        except Exception:
            pass

    # Fallback untuk SVG/SVGZ, Video, atau format lain via load_pixmap
    pix = load_pixmap(path, 64, 64)
    if pix.isNull():
        return None
    qimg = pix.toImage().convertToFormat(QImage.Format_Grayscale8).scaled(
        w_target, h_target, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
    )
    bits = 0
    for y in range(h_target):
        for x in range(hash_size):
            left = qimg.pixelColor(x, y).red()
            right = qimg.pixelColor(x + 1, y).red()
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming_distance(hash_a: int, hash_b: int) -> int:
    """Hitung jumlah bit yang berbeda (Hamming distance) antara dua hash 64-bit."""
    return (hash_a ^ hash_b).bit_count()


def find_duplicate_groups(paths, max_distance: int = 6, should_cancel=None, on_progress=None):
    """
    Temukan kelompok gambar/video yang identik atau sangat mirip menggunakan 64-bit dHash.
    Mengembalikan tuple:
      - duplicate_paths_set: set berisi normalized_path dari semua file yang punya kembaran
      - groups: list of lists [[path1, path2, ...], ...]
      - hash_map: dict {normalized_path: dhash_int}
    """
    hashes = []  # [(path, norm_path, dhash)]
    hash_map = {}
    total = len(paths)
    for idx, p in enumerate(paths):
        if should_cancel is not None and should_cancel():
            return set(), [], {}
        if on_progress is not None and idx % 25 == 0:
            on_progress(idx, total)
        if not os.path.exists(p):
            continue
        dh = compute_dhash(p)
        if dh is not None:
            norm = os.path.normcase(os.path.normpath(p))
            hashes.append((p, norm, dh))
            hash_map[norm] = dh

    # Kelompokkan menggunakan Union-Find dengan fast exact-bucket + BK/prefix pruning
    n = len(hashes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            if ri < rj:
                parent[rj] = ri
            else:
                parent[ri] = rj

    # 1. Exact hash bucket O(N)
    exact_buckets = {}
    unique_reps = []  # indeks perwakilan unik per exact hash
    for i, (_p, _norm, dh) in enumerate(hashes):
        if dh in exact_buckets:
            union(exact_buckets[dh], i)
        else:
            exact_buckets[dh] = i
            unique_reps.append(i)

    # 2. Near-duplicate check (max_distance > 0) pada perwakilan unik
    if max_distance > 0 and len(unique_reps) <= 8000:
        u_len = len(unique_reps)
        for a in range(u_len):
            if should_cancel is not None and a % 100 == 0 and should_cancel():
                return set(), [], {}
            idx_a = unique_reps[a]
            dh_a = hashes[idx_a][2]
            for b in range(a + 1, u_len):
                idx_b = unique_reps[b]
                if (dh_a ^ hashes[idx_b][2]).bit_count() <= max_distance:
                    union(idx_a, idx_b)

    clusters = {}
    for i, (p, _norm, _dh) in enumerate(hashes):
        root = find(i)
        clusters.setdefault(root, []).append(p)

    groups = [g for g in clusters.values() if len(g) > 1]
    dup_norms = {
        os.path.normcase(os.path.normpath(p))
        for g in groups
        for p in g
    }
    return dup_norms, groups, hash_map

