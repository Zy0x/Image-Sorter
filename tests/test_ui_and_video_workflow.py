"""End-to-end UI tests for ImageSorterApp, ImagePreviewDialog, sorting, Undo, filters, and slots."""

import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import core.config as cfg
import main as app_main


class UiAndVideoWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._orig_cfg_dir = cfg._RESOLVED_CONFIG_DIR
        self._orig_sig = cfg._LAST_INTERNAL_SETTINGS_SIG
        self.temp_root = tempfile.mkdtemp(prefix="imgsorter_ui_test_")
        self.cfg_dir = os.path.join(self.temp_root, "config")
        self.src_dir = os.path.join(self.temp_root, "src")
        self.dest_dir = os.path.join(self.temp_root, "dest_a")
        os.makedirs(self.cfg_dir, exist_ok=True)
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.dest_dir, exist_ok=True)
        cfg._RESOLVED_CONFIG_DIR = self.cfg_dir

    def tearDown(self):
        cfg._RESOLVED_CONFIG_DIR = self._orig_cfg_dir
        cfg._LAST_INTERNAL_SETTINGS_SIG = self._orig_sig
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def _create_sample_media(self):
        png_1 = os.path.join(self.src_dir, "01_scene.png")
        im1 = Image.new("RGB", (320, 200), (24, 60, 120))
        ImageDraw.Draw(im1).rectangle([40, 40, 220, 150], fill=(240, 240, 240))
        im1.save(png_1, "PNG")

        dup_jpg = os.path.join(self.src_dir, "02_scene_copy.jpg")
        im1.save(dup_jpg, "JPEG", quality=88)

        gif_1 = os.path.join(self.src_dir, "03_loop.gif")
        f2 = Image.new("RGB", (320, 200), (140, 50, 90))
        ImageDraw.Draw(f2).ellipse([80, 40, 200, 160], fill=(245, 220, 80))
        im1.save(gif_1, save_all=True, append_images=[f2, im1, f2], duration=50, loop=0)

        mp4_1 = os.path.join(self.src_dir, "04_clip.mp4")
        writer = cv2.VideoWriter(mp4_1, cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (240, 160))
        for idx in range(10):
            frame = np.zeros((160, 240, 3), dtype=np.uint8)
            frame[:, :] = (20, (idx * 24) % 255, 190)
            cv2.circle(frame, (30 + idx * 14, 80), 16, (255, 255, 255), -1)
            writer.write(frame)
        writer.release()

        return png_1, dup_jpg, gif_1, mp4_1

    def test_sorting_undo_filters_duplicates_and_video_controls(self):
        png_1, dup_jpg, gif_1, mp4_1 = self._create_sample_media()
        win = app_main.ImageSorterApp()
        try:
            win.show()
            win.folder_slot_count = 6
            win.folder_names = ["Sel"] + [f"Folder {c}" for c in "BCDEFGHI"]
            win.folder_paths = [self.dest_dir] * 9
            win.update_folder_buttons()
            self.app.processEvents()

            visible_slots = sum(1 for b in win.folder_buttons if b.isVisible())
            self.assertEqual(visible_slots, 6)

            files = app_main.scan_image_files(self.src_dir)
            win.load_file_list(self.src_dir, files)
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 4)

            # Filter to Videos
            win.filter_combo.setCurrentText("All Videos")
            self.app.processEvents()
            self.assertEqual(win.filtered_files, [mp4_1])

            # HUD & zero-lock move/undo on active video
            self.assertIsNotNone(win._play_pause_btn)
            self.assertIsNotNone(win._mute_btn)
            win.toggle_main_playback()
            self.assertTrue(win._main_paused)
            win.toggle_main_mute()
            self.assertTrue(win.video_muted)

            press_1 = QKeyEvent(QEvent.KeyPress, Qt.Key_1, Qt.NoModifier, "1")
            rel_1 = QKeyEvent(QEvent.KeyRelease, Qt.Key_1, Qt.NoModifier, "1")
            win.eventFilter(win, press_1)
            win.eventFilter(win, rel_1)
            self.app.processEvents()
            self.assertEqual(len(os.listdir(self.dest_dir)), 1)

            win.undo_action()
            self.app.processEvents()
            self.assertEqual(len(os.listdir(self.dest_dir)), 0)
            self.assertTrue(os.path.exists(mp4_1))

            # Animated GIF immediate in-memory QMovie & Play/Pause only (no mute btn)
            win.filter_combo.setCurrentText("Animated / GIF")
            self.app.processEvents()
            self.assertIsNotNone(win.current_movie)
            self.assertIsNotNone(win._play_pause_btn)
            self.assertIsNone(win._mute_btn)

            # Duplicate finder marks DUP #
            win.filter_combo.setCurrentText("All Files")
            self.app.processEvents()
            dup_count = win.scan_duplicates(max_distance=6, synchronous=True)
            self.assertGreaterEqual(dup_count, 2)
            self.assertIn("DUP #", win.file_info_label.text())

            # Preview dialog zoom, animation stepping, and mute sync
            dlg = app_main.ImagePreviewDialog(gif_1, win)
            dlg.resize(800, 580)
            dlg.show()
            self.app.processEvents()
            self.assertGreaterEqual(len(dlg.anim_frames), 3)
            idx0 = dlg._anim_index
            dlg.step_frame(1)
            self.assertEqual(dlg._anim_index, (idx0 + 1) % len(dlg.anim_frames))
            self.assertFalse(dlg._anim_playing)
            dlg._smart_double_click_zoom(QPoint(250, 180))
            self.assertFalse(dlg._fit_mode)
            dlg._smart_double_click_zoom(QPoint(250, 180))
            self.assertTrue(dlg._fit_mode)
            dlg.close()

            # Folder settings & Rapid Move dialogs initialize cleanly
            fs = app_main.FolderSettingsDialog(win)
            fs._set_slot_count(8)
            fs._save_and_accept()
            self.assertEqual(win.folder_slot_count, 8)
        finally:
            win.close()

    def test_cross_session_persistence_of_recent_folders_dialogs_and_history(self):
        png_1, dup_jpg, _gif_1, _mp4_1 = self._create_sample_media()
        second_dir = os.path.join(self.temp_root, "src_second")
        os.makedirs(second_dir, exist_ok=True)

        win1 = app_main.ImageSorterApp()
        try:
            # 1. Configure 7 folder slots via FolderSettingsDialog
            fs = app_main.FolderSettingsDialog(win1)
            fs._set_slot_count(7)
            fs.inputs[0][0].setText("Favorites")
            fs.inputs[0][1].setText(self.dest_dir)
            fs._save_and_accept()

            # 2. Configure Rapid Move interval via RapidMoveSettingsDialog
            rm = app_main.RapidMoveSettingsDialog(win1)
            rm.spin.setValue(175)
            rm._save_and_accept()

            # 3. Configure Custom Theme via CustomThemeDialog
            ct = app_main.CustomThemeDialog(win1)
            ct.custom_theme["main_border_color"] = "#ff5500"
            ct._save_and_accept()

            # 4. Subsequent actions must NOT overwrite dialog settings with stale self.settings
            win1._record_recent_folder(second_dir)
            win1.load_file_list(self.src_dir, [png_1, dup_jpg])
            win1.hide_moved_action.setChecked(True)
            win1.toggle_hide_moved()
            win1.include_subfolders_action.setChecked(True)
            win1.toggle_include_subfolders()
            win1.set_video_muted(True, notify=False)
            self.assertTrue(win1.move_to_custom_folder(self.dest_dir))
        finally:
            win1.close()

        # Re-open a brand-new window instance and verify 100% state restoration
        win2 = app_main.ImageSorterApp()
        try:
            self.assertEqual(win2.folder_slot_count, 7)
            self.assertEqual(win2.folder_names[0], "Favorites")
            self.assertEqual(win2.folder_paths[0], self.dest_dir)
            self.assertEqual(win2.rapid_move_interval_ms, 175)
            self.assertEqual(win2.theme_mode, "custom")
            self.assertEqual(win2.custom_theme["main_border_color"], "#ff5500")
            self.assertTrue(win2.hide_moved)
            self.assertTrue(win2.hide_moved_action.isChecked())
            self.assertTrue(win2.include_subfolders)
            self.assertTrue(win2.include_subfolders_action.isChecked())
            self.assertTrue(win2.video_muted)
            self.assertEqual(len(win2.recent_folders), 2)
            self.assertEqual(
                os.path.normcase(win2.recent_folders[0]),
                os.path.normcase(os.path.abspath(self.src_dir)),
            )
            self.assertEqual(
                os.path.normcase(win2.last_opened_folder),
                os.path.normcase(os.path.abspath(self.src_dir)),
            )
            self.assertEqual(len(win2.history_store.records), 1)
            self.assertGreaterEqual(len(win2.log_entries), 1)

            # Undo across restart restores the moved file
            win2.undo_action()
            self.assertTrue(os.path.exists(png_1))
            self.assertEqual(len(win2.history_store.records), 0)

            # Clear recent folders persists immediately
            win2.clear_recent_folders()
            self.assertEqual(win2.recent_folders, [])
            self.assertEqual(cfg.load_settings()["recent_folders"], [])
        finally:
            win2.close()

    def test_all_new_curation_features_workflow(self):
        png_1, dup_jpg, gif_1, mp4_1 = self._create_sample_media()

        win = app_main.ImageSorterApp()
        try:
            win.show()
            win.load_file_list(self.src_dir, [png_1, dup_jpg, gif_1, mp4_1])
            self.app.processEvents()

            # 1. Test Sort By feature
            win.set_sort_order("date", "desc")
            self.assertEqual(win.settings["sort_by"], "date")
            self.assertEqual(win.settings["sort_order"], "desc")

            # 2. Test Flagging & Flagged Only filter
            cur_file = win.filtered_files[win.current_index]
            self.assertFalse(win.queue_model.is_flagged(cur_file))
            win.toggle_flag_current()
            self.assertTrue(win.queue_model.is_flagged(cur_file))
            self.assertIn("Flagged", win.flag_btn.text())

            win.filter_combo.setCurrentText("Flagged Only")
            win.apply_filter()
            self.assertEqual(len(win.filtered_files), 1)
            self.assertEqual(win.filtered_files[0], cur_file)

            win.filter_combo.setCurrentText("All Files")
            win.apply_filter()

            # 3. Test Filmstrip Bar
            self.assertFalse(win.filmstrip_bar.isHidden())
            self.assertGreaterEqual(len(win.filmstrip_bar._items), 2)
            # Jump via filmstrip item
            target_idx = min(2, len(win.filtered_files) - 1)
            win.filmstrip_bar.item_selected.emit(target_idx)
            self.assertEqual(win.current_index, target_idx)

            # Toggle filmstrip
            win.show_filmstrip_action.setChecked(False)
            win.toggle_filmstrip()
            self.assertTrue(win.filmstrip_bar.isHidden())
            win.show_filmstrip_action.setChecked(True)
            win.toggle_filmstrip()
            self.assertFalse(win.filmstrip_bar.isHidden())

            # 4. Test Auto-Rename on Move & Safe Undo
            from ui.dialogs import AutoRenameSettingsDialog, SessionSummaryDialog
            ar_dlg = AutoRenameSettingsDialog(win)
            ar_dlg.enable_check.setChecked(True)
            ar_dlg.pat_edit.setText("{folder}_{index:03d}_{name}")
            ar_dlg._save_and_accept()
            self.assertTrue(win.settings["auto_rename_enabled"])

            cur_before = win.filtered_files[win.current_index]
            dest_dir = win.folder_paths[0]
            self.assertTrue(win.move_to_custom_folder(dest_dir))

            # Verify moved file was renamed according to pattern
            moved_actual = win.history_store.resolve_actual_path(cur_before)
            self.assertTrue(os.path.exists(moved_actual))
            self.assertIn("Folder A_001_", os.path.basename(moved_actual))

            # Verify Undo restores original name
            win.undo_action()
            self.assertTrue(os.path.exists(cur_before))

            # 5. Test Video Volume Slider
            win.set_video_volume(0.42)
            self.assertAlmostEqual(win.video_volume, 0.42, places=2)
            self.assertAlmostEqual(win.settings["video_volume"], 0.42, places=2)

            # 6. Test Session Summary Dialog
            from core.file_ops import generate_session_summary
            summ = generate_session_summary(
                source_folder=win.current_folder,
                all_files=win.queue_model.all_files,
                history_records=win.history_store.records,
                flagged_paths=win.queue_model.flagged_norms,
                slot_names=win.folder_names[: win.folder_slot_count],
                slot_paths=win.folder_paths[: win.folder_slot_count],
            )
            self.assertEqual(summ["total_files"], 4)
            self.assertEqual(summ["flagged_count"], 1)

            sum_dlg = SessionSummaryDialog(summ, win)
            rep_text = sum_dlg._generate_report_text()
            self.assertIn("Session Summary Report", rep_text)
            self.assertIn("Total Media: 4", rep_text)
            sum_dlg.close()
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
