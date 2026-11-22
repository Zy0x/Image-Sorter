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


if __name__ == "__main__":
    unittest.main()
