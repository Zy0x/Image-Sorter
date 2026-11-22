"""Perceptual duplicate and visually similar media scanner (64-bit dHash + Union-Find)."""

import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from media.decoders import load_pixmap
from media.formats import _HAS_PIL, _PILImage, _PILImageOps, is_video_file


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


def find_duplicate_groups(paths, max_distance: int = 6, should_cancel=None, on_progress=None):
    """Group exact and visually similar files using O(N) exact buckets + pairwise Hamming pruning."""
    hashes = []
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
