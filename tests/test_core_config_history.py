"""Unit tests for core.config, core.history, core.file_ops, and core.media_queue."""

import os
import shutil
import tempfile
import unittest

import core.config as cfg
from core.file_ops import (
    format_auto_rename_filename,
    generate_session_summary,
    get_unique_destination,
    natural_sort_key,
    scan_image_files,
)
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

    def test_normalize_settings_pads_slots_and_deduplicates_recent_folders(self):
        legacy = {
            "folder_slot_count": 7,
            "folder_names": ["Alpha", "Beta"],
            "folder_paths": ["out/alpha", "out/beta"],
            "recent_folders": [self.temp_dir, self.temp_dir, os.path.join(self.temp_dir, "sub")],
            "rapid_move_interval_ms": 175,
        }
        cfg.save_settings(legacy)
        loaded = cfg.load_settings()
        self.assertEqual(loaded["folder_slot_count"], 7)
        self.assertEqual(len(loaded["folder_names"]), cfg.MAX_FOLDER_SLOTS)
        self.assertEqual(loaded["folder_names"][:2], ["Alpha", "Beta"])
        self.assertEqual(len(loaded["folder_paths"]), cfg.MAX_FOLDER_SLOTS)
        self.assertEqual(loaded["rapid_move_interval"], 175)
        self.assertEqual(len(loaded["recent_folders"]), 2)
        self.assertEqual(loaded["last_opened_folder"], os.path.normpath(self.temp_dir))

    def test_sort_files_by_name_date_size_and_ext(self):
        store = HistoryStore()
        q = MediaQueueModel(store)
        f1 = os.path.join(self.temp_dir, "b_small.png")
        f2 = os.path.join(self.temp_dir, "a_large.gif")
        f3 = os.path.join(self.temp_dir, "c_mid.jpg")

        with open(f1, "wb") as fp:
            fp.write(b"x" * 10)
        with open(f2, "wb") as fp:
            fp.write(b"x" * 1000)
        with open(f3, "wb") as fp:
            fp.write(b"x" * 100)

        # Set specific timestamps: f1 oldest, f3 newest
        os.utime(f1, (1000, 1000))
        os.utime(f2, (2000, 2000))
        os.utime(f3, (3000, 3000))

        q.set_files([f1, f2, f3])

        # 1. Sort by name asc
        q.sort_files("name", "asc")
        self.assertEqual([os.path.basename(p) for p in q.all_files], ["a_large.gif", "b_small.png", "c_mid.jpg"])

        # 2. Sort by name desc
        q.sort_files("name", "desc")
        self.assertEqual([os.path.basename(p) for p in q.all_files], ["c_mid.jpg", "b_small.png", "a_large.gif"])

        # 3. Sort by date desc (newest first)
        q.sort_files("date", "desc")
        self.assertEqual([os.path.basename(p) for p in q.all_files], ["c_mid.jpg", "a_large.gif", "b_small.png"])

        # 4. Sort by size desc (largest first)
        q.sort_files("size", "desc")
        self.assertEqual([os.path.basename(p) for p in q.all_files], ["a_large.gif", "c_mid.jpg", "b_small.png"])

        # 5. Sort by ext asc
        q.sort_files("ext", "asc")
        self.assertEqual([os.path.basename(p) for p in q.all_files], ["a_large.gif", "c_mid.jpg", "b_small.png"])

    def test_media_queue_flagging_and_filter(self):
        store = HistoryStore()
        q = MediaQueueModel(store)
        f1 = os.path.join(self.temp_dir, "img1.png")
        f2 = os.path.join(self.temp_dir, "img2.png")
        for f in (f1, f2):
            with open(f, "wb") as fp:
                fp.write(b"1")

        q.set_files([f1, f2])
        self.assertFalse(q.is_flagged(f1))

        # Toggle flag
        self.assertTrue(q.toggle_flag(f1))
        self.assertTrue(q.is_flagged(f1))
        self.assertEqual(q.get_flagged_list(), [f1])

        # Filter by Flagged Only
        q.apply_filter("Flagged Only", hide_moved=False)
        self.assertEqual(q.filtered_files, [f1])

        # Toggle off
        self.assertFalse(q.toggle_flag(f1))
        self.assertFalse(q.is_flagged(f1))
        q.apply_filter("Flagged Only", hide_moved=False)
        self.assertEqual(q.filtered_files, [])

    def test_format_auto_rename_filename_and_session_summary(self):
        # Auto-rename token formatting
        fn = format_auto_rename_filename(
            pattern="{folder}_{index:03d}_{name}",
            orig_path="C:/Photos/vacation.jpg",
            folder_name="Best Shots",
            index=5,
        )
        self.assertEqual(fn, "Best Shots_005_vacation.jpg")

        # Session summary calculation
        all_f = [
            os.path.join(self.temp_dir, "f1.jpg"),
            os.path.join(self.temp_dir, "f2.jpg"),
            os.path.join(self.temp_dir, "f3.jpg"),
        ]
        out_a = os.path.join(self.temp_dir, "out_a")
        out_b = os.path.join(self.temp_dir, "out_b")
        history = [
            (all_f[0], os.path.join(out_a, "f1.jpg")),
            (all_f[1], os.path.join(out_b, "f2.jpg")),
        ]
        flagged = {q_norm for q_norm in [os.path.normcase(os.path.normpath(all_f[2]))]}
        summary = generate_session_summary(
            source_folder=self.temp_dir,
            all_files=all_f,
            history_records=history,
            flagged_paths=flagged,
            slot_names=["Slot A", "Slot B"],
            slot_paths=[out_a, out_b],
        )
        self.assertEqual(summary["total_files"], 3)
        self.assertEqual(summary["total_moved"], 2)
        self.assertEqual(summary["remaining_unmoved"], 1)
        self.assertEqual(summary["flagged_count"], 1)
        self.assertEqual(summary["folder_counts"]["Slot A"], 1)
        self.assertEqual(summary["folder_counts"]["Slot B"], 1)


if __name__ == "__main__":
    unittest.main()
