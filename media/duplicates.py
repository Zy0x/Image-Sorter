"""Perceptual duplicate and visually similar media scanner (64-bit dHash + Union-Find)."""

import hashlib
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from media.decoders import load_pixmap
from media.formats import _HAS_PIL, _PILImage, _PILImageOps, is_video_file


def compute_file_hash(path: str, chunk_size: int = 65536):
    """Compute MD5 checksum for exact bit-for-bit duplicate detection."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def compute_fast_sample_hash(path: str):
    """Compute rapid sample hash (size + first 64KB + last 64KB) for pre-filtering large libraries."""
    try:
        sz = os.path.getsize(path)
        if sz <= 131072:
            return compute_file_hash(path)
        h = hashlib.md5()
        h.update(str(sz).encode("ascii"))
        with open(path, "rb") as f:
            h.update(f.read(65536))
            f.seek(-65536, os.SEEK_END)
            h.update(f.read(65536))
        return h.hexdigest()
    except Exception:
        return None


def compute_dhash(path: str, hash_size: int = 8):
    """Compute 64-bit Difference Perceptual Hash (dHash) for images and video keyframes."""
    w_target = hash_size + 1
    h_target = hash_size

    if _HAS_PIL and not is_video_file(path) and not path.lower().endswith((".svg", ".svgz")):
        try:
            with _PILImage.open(path) as im:
                try:
                    im = _PILImageOps.exif_transpose(im)
                except Exception:
                    pass
                gray = im.convert("L").resize((w_target, h_target), _PILImage.Resampling.BILINEAR)
                pixels = list(
                    gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata()
                )
                bits = 0
                for row in range(h_target):
                    base = row * w_target
                    for col in range(hash_size):
                        bits = (bits << 1) | (1 if pixels[base + col] > pixels[base + col + 1] else 0)
                return bits
        except Exception:
            pass

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
    """Return Hamming bit distance between two 64-bit perceptual hashes."""
    return (hash_a ^ hash_b).bit_count()


def find_duplicate_groups(
    paths,
    max_distance: int = 6,
    engine: str = "dhash",
    should_cancel=None,
    should_pause=None,
    on_progress=None,
):
    """Group exact or visually similar files using selectable engine: 'dhash', 'exact_hash', or 'size_fast'."""
    total = len(paths)
    if total < 2:
        return set(), [], {}

    # Engine 1: Exact Byte-for-Byte MD5 Checksum
    if engine == "exact_hash":
        hash_groups = {}
        hash_map = {}
        for idx, p in enumerate(paths):
            if should_cancel is not None and should_cancel():
                return set(), [], {}
            if should_pause is not None and should_pause():
                return set(), [], {}
            if on_progress is not None and idx % 20 == 0:
                on_progress(idx, total)
            if not os.path.exists(p):
                continue
            fh = compute_file_hash(p)
            if fh:
                norm = os.path.normcase(os.path.normpath(p))
                hash_groups.setdefault(fh, []).append(p)
                hash_map[norm] = fh
        if on_progress is not None:
            on_progress(total, total)
        groups = [g for g in hash_groups.values() if len(g) > 1]
        dup_norms = {os.path.normcase(os.path.normpath(p)) for g in groups for p in g}
        return dup_norms, groups, hash_map

    # Engine 2: Fast Pre-filter by File Size + Header/Tail Checksum
    if engine == "size_fast":
        size_buckets = {}
        for idx, p in enumerate(paths):
            if should_cancel is not None and should_cancel():
                return set(), [], {}
            if should_pause is not None and should_pause():
                return set(), [], {}
            if on_progress is not None and idx % 100 == 0:
                on_progress(idx // 2, total)
            if not os.path.exists(p):
                continue
            try:
                sz = os.path.getsize(p)
                size_buckets.setdefault(sz, []).append(p)
            except OSError:
                pass

        candidates = [p for g in size_buckets.values() if len(g) > 1 for p in g]
        cand_total = len(candidates)
        hash_groups = {}
        hash_map = {}
        half_total = total // 2
        for c_idx, p in enumerate(candidates):
            if should_cancel is not None and should_cancel():
                return set(), [], {}
            if should_pause is not None and should_pause():
                return set(), [], {}
            if on_progress is not None and c_idx % 20 == 0:
                prog = half_total + (c_idx * half_total // max(1, cand_total))
                on_progress(prog, total)
            fh = compute_fast_sample_hash(p)
            if fh:
                norm = os.path.normcase(os.path.normpath(p))
                hash_groups.setdefault(fh, []).append(p)
                hash_map[norm] = fh
        if on_progress is not None:
            on_progress(total, total)
        groups = [g for g in hash_groups.values() if len(g) > 1]
        dup_norms = {os.path.normcase(os.path.normpath(p)) for g in groups for p in g}
        return dup_norms, groups, hash_map

    # Engine 3: Perceptual 64-bit Difference Hash (dHash)
    hashes = []
    hash_map = {}
    for idx, p in enumerate(paths):
        if should_cancel is not None and should_cancel():
            return set(), [], {}
        if should_pause is not None and should_pause():
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

    if on_progress is not None:
        on_progress(total, total)

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

    exact_buckets = {}
    unique_reps = []
    for i, (_p, _norm, dh) in enumerate(hashes):
        if dh in exact_buckets:
            union(exact_buckets[dh], i)
        else:
            exact_buckets[dh] = i
            unique_reps.append(i)

    if max_distance > 0 and len(unique_reps) <= 8000:
        u_len = len(unique_reps)
        for a in range(u_len):
            if should_cancel is not None and a % 100 == 0 and should_cancel():
                return set(), [], {}
            if should_pause is not None and a % 100 == 0 and should_pause():
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
