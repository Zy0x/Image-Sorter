"""Unit tests for media decoders, LRU cache, metadata, animation frames, and dHash duplicates."""

import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from media.cache import PixmapLRUCache
from media.decoders import (
    load_animation_frames,
    load_pixmap,
    read_image_metadata,
    read_video_metadata,
)
from media.duplicates import compute_dhash, find_duplicate_groups, hamming_distance


class MediaDecodersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="imgsorter_media_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_textured_image(self, path: str, seed: int, w: int = 240, h: int = 160, fmt: str = "PNG"):
        im = Image.new("RGB", (w, h), (20, 24, 34))
        draw = ImageDraw.Draw(im)
        for y in range(0, h, 20):
            for x in range(0, w, 20):
                v = ((x * (seed + 1)) ^ (y * (seed + 3))) & 0xFF
                draw.rectangle([x, y, x + 19, y + 19], fill=((v + seed * 31) % 256, (v * 2) % 256, 255 - v))
        draw.rectangle([30, 30, 100, 95], fill=(245, 245, 245))
        im.save(path, fmt)
        return im

    def _make_video(self, path: str, w: int = 240, h: int = 160, n_frames: int = 10):
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (w, h))
        for idx in range(n_frames):
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:, :] = (40, (idx * 20) % 255, 170)
            cv2.rectangle(frame, (25 + idx * 8, 40), (75 + idx * 8, 95), (255, 255, 255), -1)
            writer.write(frame)
        writer.release()

    def test_image_video_decode_metadata_and_lru_cache(self):
        png_path = os.path.join(self.temp_dir, "sample.png")
        gif_path = os.path.join(self.temp_dir, "anim.gif")
        mp4_path = os.path.join(self.temp_dir, "clip.mp4")

        base = self._make_textured_image(png_path, 7)
        f2 = self._make_textured_image(os.path.join(self.temp_dir, "f2.png"), 12)
        f3 = self._make_textured_image(os.path.join(self.temp_dir, "f3.png"), 19)
        f4 = self._make_textured_image(os.path.join(self.temp_dir, "f4.png"), 27)
        base.save(gif_path, save_all=True, append_images=[f2, f3, f4], duration=60, loop=0)
        self._make_video(mp4_path, n_frames=10)

        pix = load_pixmap(png_path)
        self.assertFalse(pix.isNull())
        self.assertEqual((pix.width(), pix.height()), (240, 160))

        w, h, sz, fmt, fcount = read_image_metadata(png_path)
        self.assertEqual((w, h), (240, 160))
        self.assertGreater(sz, 0)
        self.assertEqual(fmt, b"png")
        self.assertEqual(fcount, 1)

        vw, vh, vsz, _fps, vfcount, dur = read_video_metadata(mp4_path)
        self.assertEqual((vw, vh), (240, 160))
        self.assertGreater(vsz, 0)
        self.assertGreater(dur, 0.2)
        self.assertGreaterEqual(vfcount, 8)

        gif_frames = load_animation_frames(gif_path, 320, 240)
        self.assertGreaterEqual(len(gif_frames), 3)
        mp4_frames = load_animation_frames(mp4_path, 320, 240)
        self.assertGreaterEqual(len(mp4_frames), 4)

        cache = PixmapLRUCache(max_entries=2)
        cache.put(png_path, pix)
        self.assertIsNotNone(cache.get(png_path))
        self.assertEqual(cache.hits, 1)
        cache.invalidate(png_path)
        self.assertIsNone(cache.get(png_path))

    def test_dhash_duplicate_detection(self):
        p1 = os.path.join(self.temp_dir, "orig.png")
        p2 = os.path.join(self.temp_dir, "resized.jpg")
        p3 = os.path.join(self.temp_dir, "different.png")

        im = self._make_textured_image(p1, 42, 320, 240)
        im.resize((160, 120), Image.Resampling.LANCZOS).save(p2, "JPEG", quality=85)

        diff = Image.new("RGB", (320, 240), (240, 240, 240))
        ImageDraw.Draw(diff).polygon([(0, 239), (160, 0), (319, 239)], fill=(10, 10, 10))
        diff.save(p3, "PNG")

        h1, h2 = compute_dhash(p1), compute_dhash(p2)
        self.assertIsNotNone(h1)
        self.assertIsNotNone(h2)
        self.assertLessEqual(hamming_distance(h1, h2), 3)

        dup_norms, groups, _hmap = find_duplicate_groups([p1, p2, p3], max_distance=6)
        self.assertEqual(len(groups), 1)
        self.assertCountEqual(groups[0], [p1, p2])
        self.assertEqual(len(dup_norms), 2)


if __name__ == "__main__":
    unittest.main()
