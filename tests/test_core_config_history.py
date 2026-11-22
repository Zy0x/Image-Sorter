"""Unit tests for core.config, core.history, core.file_ops, and core.media_queue."""

import os
import shutil
import tempfile
import unittest

import core.config as cfg
from core.file_ops import get_unique_destination, natural_sort_key, scan_image_files
from core.history import HistoryStore
from core.media_queue import MediaQueueModel


class CoreConfigHistoryQueueTests(unittest.TestCase):
    def setUp(self):
        self._orig_config_dir = cfg._RESOLVED_CONFIG_DIR
        self._orig_sig = cfg._LAST_INTERNAL_SETTINGS_SIG
        self.temp_dir = tempfile.mkdtemp(prefix="imgsorter_core_test_")
        self.cfg_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(self.cfg_dir, exist_ok=True)
        cfg._RESOLVED_CONFIG_DIR = self.cfg_dir

    def tearDown(self):
        cfg._RESOLVED_CONFIG_DIR = self._orig_config_dir
        cfg._LAST_INTERNAL_SETTINGS_SIG = self._orig_sig
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clamp_helpers_and_settings_atomic_roundtrip(self):
        self.assertEqual(cfg.clamp_folder_slots(1), cfg.MIN_FOLDER_SLOTS)
        self.assertEqual(cfg.clamp_folder_slots(99), cfg.MAX_FOLDER_SLOTS)
        self.assertEqual(cfg.clamp_folder_slots("bad"), cfg.DEFAULT_FOLDER_SLOTS)
        self.assertEqual(cfg.clamp_rapid_interval(5), cfg.RAPID_MOVE_MIN_MS)
        self.assertEqual(cfg.clamp_rapid_interval(5000), cfg.RAPID_MOVE_MAX_MS)
        self.assertEqual(cfg.clamp_rapid_interval(None), cfg.RAPID_MOVE_DEFAULT_MS)

        s = cfg.default_settings_copy(first_run=False)
        s["folder_slot_count"] = 7
        s["theme_mode"] = "dark"
        cfg.save_settings(s)

        loaded = cfg.load_settings()
        self.assertFalse(loaded["first_run"])
        self.assertEqual(loaded["folder_slot_count"], 7)
        self.assertEqual(loaded["theme_mode"], "dark")
        self.assertFalse(os.path.exists(cfg.get_config_path() + ".tmp"))

    def test_history_store_lockstep_and_persistence(self):
        store = HistoryStore()
        src1 = os.path.join(self.temp_dir, "a.png")
        dst1 = os.path.join(self.temp_dir, "dest", "a.png")
        dst2 = os.path.join(self.temp_dir, "dest2", "a.png")

        store.record_move(src1, dst1)
        self.assertTrue(store.is_moved(src1))
        self.assertEqual(store.get_new_path(src1), dst1)

        store.record_move(src1, dst2)
        self.assertEqual(len(store.records), 1)
        self.assertEqual(store.resolve_actual_path(src1), dst2)

        store.flush()
        reloaded = HistoryStore()
        self.assertEqual(len(reloaded.records), 1)
        self.assertTrue(reloaded.is_moved(src1))

        popped = reloaded.pop_last()
        self.assertEqual(popped, (src1, dst2))
        reloaded.clear_cache_entry(src1)
        self.assertFalse(reloaded.is_moved(src1))

    def test_file_ops_natural_sort_unique_dest_and_recursive_scan(self):
        dest = os.path.join(self.temp_dir, "out")
        sub = os.path.join(self.temp_dir, "album", "nested")
        excluded = os.path.join(self.temp_dir, "album", "sorted_out")
        os.makedirs(dest, exist_ok=True)
        os.makedirs(sub, exist_ok=True)
        os.makedirs(excluded, exist_ok=True)

        p1 = os.path.join(self.temp_dir, "album", "img_10.png")
        p2 = os.path.join(self.temp_dir, "album", "img_2.png")
        p3 = os.path.join(sub, "sub_1.jpg")
        p_ex = os.path.join(excluded, "ignore_me.png")
        for p in (p1, p2, p3, p_ex):
            with open(p, "wb") as f:
                f.write(b"x")

        flat = scan_image_files(os.path.join(self.temp_dir, "album"), include_subfolders=False)
        self.assertEqual([os.path.basename(p) for p in flat], ["img_2.png", "img_10.png"])

        rec = scan_image_files(
            os.path.join(self.temp_dir, "album"),
            include_subfolders=True,
            excluded_dirs=[excluded],
        )
        self.assertEqual(len(rec), 3)
        self.assertNotIn(p_ex, rec)

        existing = os.path.join(dest, "shot.png")
        with open(existing, "wb") as f:
            f.write(b"1")
        uniq = get_unique_destination(dest, "shot.png")
        self.assertTrue(uniq.endswith("shot (1).png"))
        self.assertLess(natural_sort_key("a_2.png"), natural_sort_key("a_10.png"))

    def test_media_queue_filters_and_navigation(self):
        store = HistoryStore()
        q = MediaQueueModel(store)
        f_png = os.path.join(self.temp_dir, "1.png")
        f_gif = os.path.join(self.temp_dir, "2.gif")
        f_mp4 = os.path.join(self.temp_dir, "3.mp4")
        for f in (f_png, f_gif, f_mp4):
            with open(f, "wb") as fp:
                fp.write(b"1")

        q.set_files([f_png, f_gif, f_mp4])
        q.apply_filter("All Videos", hide_moved=False)
        self.assertEqual(q.filtered_files, [f_mp4])

        q.apply_filter("Animated / GIF", hide_moved=False)
        self.assertEqual(q.filtered_files, [f_gif])

        store.record_move(f_png, os.path.join(self.temp_dir, "moved", "1.png"))
        q.apply_filter("All Files", hide_moved=True)
        self.assertNotIn(f_png, q.filtered_files)
        self.assertEqual(q.find_next_unmoved_index(-1), 0)


if __name__ == "__main__":
    unittest.main()
