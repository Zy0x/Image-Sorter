"""End-to-end UI tests for ImageSorterApp, ImagePreviewDialog, sorting, Undo, filters, and slots."""

import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

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
            win.jump_to_index(0)

            # 3. Test Filmstrip Bar docked inside UP NEXT panel
            self.assertEqual(win.filmstrip_bar.parentWidget(), win.next_panel)
            self.assertFalse(win.filmstrip_bar.isHidden())
            self.assertEqual(len(win.filmstrip_bar._items), 2)

            # Toggle filmstrip
            win.show_filmstrip_action.setChecked(False)
            win.toggle_filmstrip()
            self.assertTrue(win.filmstrip_bar.isHidden())
            win.show_filmstrip_action.setChecked(True)
            win.toggle_filmstrip()
            self.assertFalse(win.filmstrip_bar.isHidden())

            # Jump via filmstrip item
            target_idx = min(2, len(win.filtered_files) - 1)
            win.filmstrip_bar.item_selected.emit(target_idx)
            self.assertEqual(win.current_index, target_idx)

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
            self.assertTrue(summ.get("slots"))
            self.assertEqual(len(summ["slots"]), win.folder_slot_count)
            from ui.theme import make_vector_icon
            copy_ic = make_vector_icon("copy", "#ffffff", 14)
            self.assertFalse(copy_ic.isNull())
            sum_dlg.close()
        finally:
            win.close()

    def test_ux_enhancements_and_dialog_polish(self):
        """Test non-redundant flag button text, empty stage click-to-import, slot badges, right-click menu, and StudioCheckBox."""
        win = app_main.ImageSorterApp()
        try:
            # 1. Non-redundant flag button text
            self.assertEqual(win.flag_btn.text(), "Flag")
            self.assertNotIn("☆", win.flag_btn.text())
            self.assertNotIn("★", win.flag_btn.text())

            # 2. Empty stage click-to-import
            imported = []
            win.import_folder_dialog = lambda: imported.append(True)
            press_evt = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(50.0, 50.0), QPointF(50.0, 50.0), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            handled = win.eventFilter(win.main_image_label, press_evt)
            self.assertTrue(handled)
            self.assertEqual(len(imported), 1)

            # 3. FolderSettingsDialog badges
            from ui.dialogs.settings_dialogs import FolderSettingsDialog
            dlg = FolderSettingsDialog(win)
            for i, card in enumerate(dlg._slot_cards):
                # badge is the first label in the card's row
                badge = card.findChild(QLabel)
                self.assertEqual(badge.text(), f"[{i + 1}]")
                self.assertNotIn("A", badge.text())
                self.assertIn(f"Pintasan Keyboard: Tekan tombol [{i + 1}]", badge.toolTip())
            dlg.close()

            # 4. Folder buttons right-click context menu & quick rename
            win.folder_names[0] = "Old Name"
            win.folder_paths[0] = self.dest_dir
            # Verify tooltip contains right-click hint
            win.update_folder_buttons()
            self.assertIn("Klik kanan untuk opsi folder", win.folder_buttons[0].toolTip())
            # Verify context menu shows without error
            from PySide6.QtCore import QTimer
            QTimer.singleShot(25, lambda: QApplication.activePopupWidget() and QApplication.activePopupWidget().close())
            win._show_folder_btn_context_menu(0, QPoint(10, 10))

            # 5. StudioCheckBox custom control
            from ui.widgets import StudioCheckBox
            chk = StudioCheckBox("Test Checkbox")
            self.assertFalse(chk.isChecked())
            chk.setChecked(True)
            self.assertTrue(chk.isChecked())
            # Test paint event rendering
            pm = QPixmap(200, 30)
            chk.resize(200, 30)
            chk.render(pm)
            self.assertFalse(pm.isNull())
        finally:
            win.close()

    def test_filmstrip_in_next_panel_and_toast_overlay(self):
        """Test mini filmstrip placement inside UP NEXT card, view toggle, and unclipped click-through toast overlay."""
        win = app_main.ImageSorterApp()
        try:
            win.resize(1000, 700)
            win.show()
            QApplication.processEvents()

            # 1. FilmstripBar is inside next_panel with portrait aspect cards
            self.assertEqual(win.filmstrip_bar.parentWidget(), win.next_panel)
            self.assertEqual(win.filmstrip_bar.height(), 74)
            from ui.widgets import FilmstripItem
            card = FilmstripItem(0)
            self.assertEqual(card.width(), 44)
            self.assertEqual(card.height(), 64)
            self.assertGreater(card.height(), card.width())

            # 2. Filmstrip shows media AFTER UP NEXT (starts at current_idx + 2)
            dummy_files = [f"file_{i}.jpg" for i in range(10)]
            win.filtered_files = dummy_files
            win.current_index = 0
            win.filmstrip_bar.update_strip(dummy_files, 0, win.pixmap_cache)
            self.assertEqual([it.index for it in win.filmstrip_bar._items], [2, 3, 4, 5])

            # 3. Toggle filmstrip hides and restores properly
            win.settings["show_filmstrip"] = True
            win.toggle_filmstrip()
            self.assertFalse(win.filmstrip_bar.isVisible())
            win.toggle_filmstrip()
            self.assertTrue(win.filmstrip_bar.isVisible())

            # 3. Toast overlay dynamic height with multi-line text (no clipping)
            long_msg = "Undo → Restored\nwFAD7xT7Vavhh7NrOOEoh1TazpnLLvOvrnKljroy08VApnS0br2ka0xWrhshTROhzmtSLk4OFePMantUMclw"
            from ui.theme import resolve_studio_tokens
            win.toast.show_message(long_msg, resolve_studio_tokens(win))
            QApplication.processEvents()

            # Verify toast is visible, has height >= 50px (multi-line) and not clipped at 42px
            self.assertTrue(win.toast.isVisible())
            self.assertGreaterEqual(win.toast.height(), 50)

            # 4. Toast overlay positioned above bottom buttons
            prev_top = win.prev_button.mapTo(win.centralWidget(), QPoint(0, 0)).y()
            toast_bottom = win.toast.geometry().bottom()
            self.assertLess(toast_bottom, prev_top)

            # 5. Toast overlay is click-through (WA_TransparentForMouseEvents)
            self.assertTrue(win.toast.testAttribute(Qt.WA_TransparentForMouseEvents))
        finally:
            win.close()

    def test_dynamic_smart_menu_actions_and_icons(self):
        """Test smart dynamic text and icons for Hide/Show Moved, Hide/Show Filmstrip, and Include/Exclude Subfolders."""
        win = app_main.ImageSorterApp()
        try:
            # 1. Hide / Show Moved Images text and icon flipping
            win.hide_moved = False
            win._update_dynamic_menu_actions()
            self.assertEqual(win.hide_moved_action.text(), "Hide Moved Images")

            win.toggle_hide_moved()
            self.assertTrue(win.hide_moved)
            self.assertEqual(win.hide_moved_action.text(), "Show Moved Images")

            win.toggle_hide_moved()
            self.assertFalse(win.hide_moved)
            self.assertEqual(win.hide_moved_action.text(), "Hide Moved Images")

            # 2. Hide / Show Filmstrip Bar text and icon flipping
            win.settings["show_filmstrip"] = True
            win._update_dynamic_menu_actions()
            self.assertEqual(win.show_filmstrip_action.text(), "Hide Filmstrip Bar")

            win.toggle_filmstrip()
            self.assertFalse(win.settings["show_filmstrip"])
            self.assertEqual(win.show_filmstrip_action.text(), "Show Filmstrip Bar")

            # 3. Include / Exclude Subfolders text and icon flipping
            win.include_subfolders = False
            win._update_dynamic_menu_actions()
            self.assertEqual(win.include_subfolders_action.text(), "Include Subfolders")

            win.toggle_include_subfolders()
            self.assertTrue(win.include_subfolders)
            self.assertEqual(win.include_subfolders_action.text(), "Exclude Subfolders")

            # 4. Active Theme and Sort indicators
            win.set_theme_mode("dark")
            self.assertIn("✓", win.theme_actions["dark"].text())
            self.assertNotIn("✓", win.theme_actions["light"].text())

            win.set_sort_order("name", "asc")
            self.assertIn("✓", win.sort_actions[("name", "asc")].text())
            self.assertNotIn("✓", win.sort_actions[("name", "desc")].text())
        finally:
            win.close()

    def test_duplicate_finder_overlay_and_engines(self):
        """Test non-floating loading overlay, duplicate finder multi-engine dialog, and pause/resume."""
        win = app_main.ImageSorterApp()
        try:
            # 1. Verify LoadingOverlay does NOT have WindowStaysOnTopHint
            self.assertEqual(int(win.loading_overlay.windowFlags() & Qt.WindowStaysOnTopHint), 0)

            # 2. Setup mock files for duplicate finder
            with tempfile.TemporaryDirectory() as tmp_dir:
                f1 = os.path.join(tmp_dir, "a.jpg")
                f2 = os.path.join(tmp_dir, "b.jpg")
                f3 = os.path.join(tmp_dir, "c.jpg")
                img = QImage(32, 32, QImage.Format_RGB32)
                img.fill(Qt.red)
                img.save(f1)
                img.save(f2)  # identical
                img.fill(Qt.blue)
                img.save(f3)

                win.current_folder = tmp_dir
                win.image_files = [f1, f2, f3]
                win.queue_model.set_files([f1, f2, f3])
                win.filtered_files = [f1, f2, f3]

                # 3. Test DuplicateFinderDialog
                from ui.dialogs import DuplicateFinderDialog
                dlg = DuplicateFinderDialog(win)
                self.assertEqual(int(dlg.windowFlags() & Qt.WindowStaysOnTopHint), 0)
                self.assertTrue(dlg.rb_dhash.isChecked())

                # Test engine switching
                dlg.rb_exact.setChecked(True)
                self.assertFalse(dlg.acc_combo.isEnabled())
                dlg.rb_fast.setChecked(True)
                self.assertFalse(dlg.acc_combo.isEnabled())
                dlg.rb_dhash.setChecked(True)
                self.assertTrue(dlg.acc_combo.isEnabled())

                # 4. Test DuplicateScanThread pause & resume
                from core.workers import DuplicateScanThread
                th = DuplicateScanThread([f1, f2, f3], max_distance=6, engine="exact_hash", parent=win)
                th.pause()
                self.assertTrue(th.is_paused())
                th.resume()
                self.assertFalse(th.is_paused())

                # 5. Test find_duplicate_groups with exact_hash and size_fast
                from media.duplicates import find_duplicate_groups
                d_norms, groups, _ = find_duplicate_groups([f1, f2, f3], engine="exact_hash")
                self.assertEqual(len(groups), 1)
                self.assertEqual(len(d_norms), 2)

                d_norms_fast, groups_fast, _ = find_duplicate_groups([f1, f2, f3], engine="size_fast")
                self.assertEqual(len(groups_fast), 1)

                dlg.close()
        finally:
            win.close()

    def test_compact_media_hud_overlay_and_autohide(self):
        """Verify MediaHudOverlay has 32px height, 3s initial timer, hover-hold, and immediate leave-hide."""
        from ui.widgets import MediaHudOverlay
        parent = QLabel()
        parent.resize(480, 360)
        hud = MediaHudOverlay(parent, parent.size(), is_video=True, duration_s=14.0, volume=0.75)
        try:
            self.assertEqual(hud.height(), 32)
            self.assertEqual(hud.play_pause_btn.width(), 24)
            self.assertEqual(hud.play_pause_btn.height(), 24)
            self.assertIsNotNone(hud.seek_slider)
            self.assertIsNotNone(hud.volume_slider)
            self.assertIsNotNone(hud.cur_time_lbl)
            self.assertIsNotNone(hud.tot_time_lbl)

            # Initial 3-second display timer is active
            self.assertTrue(hud._initial_timer.isActive())
            self.assertEqual(hud._initial_timer.interval(), 3000)

            # Hovering cancels initial timer and keeps HUD visible
            hud.wake_hud()
            self.assertFalse(hud._initial_timer.isActive())
            self.assertEqual(hud._opacity_effect.opacity(), 1.0)

            # When not hovered, hide_hud hides immediately
            hud.hide_hud(fast=True)
            self.assertEqual(hud._fade_anim.endValue(), 0.0)

            # Wake brings opacity back to 1.0
            hud.wake_hud()
            self.assertEqual(hud._fade_anim.endValue(), 1.0)

            # Reposition keeps height 32
            hud.reposition(QSize(300, 200), paused=False, muted=False)
            self.assertEqual(hud.height(), 32)
        finally:
            hud.close()
            parent.close()

    def test_video_seek_and_hover_hold_integration(self):
        """Verify video seek position lock, stale tick rejection, and hover polling integration."""
        _png, _dup, _gif, mp4_1 = self._create_sample_media()
        win = app_main.ImageSorterApp()
        try:
            win.show()
            self.app.processEvents()

            files = app_main.scan_image_files(self.src_dir)
            win.load_file_list(self.src_dir, files)
            win.filter_combo.setCurrentText("All Videos")
            self.app.processEvents()

            hud = win.hud_overlay
            self.assertIsNotNone(hud)
            self.assertTrue(hud.is_video)
            self.assertTrue(win._hover_check_timer.isActive())
            # Initial 3-second display timer is still active after creation and initial reposition
            self.assertTrue(hud._initial_timer.isActive())

            # Perform seek to 4000ms
            hud.set_duration_ms(10000)
            win._on_main_seek_clicked(4000)
            self.assertEqual(hud.seek_slider.value(), 4000)

            # Stale position tick right after seek should be ignored
            win._on_main_qtmm_position(500)
            self.assertEqual(hud.seek_slider.value(), 4000)

            # Slider down prevents position update during drag
            hud.seek_slider.setSliderDown(True)
            hud.set_position_ms(200, force=False)
            self.assertEqual(hud.seek_slider.value(), 4000)
            hud.seek_slider.setSliderDown(False)

            # Hover check timer polling
            win._check_video_hover_state()
            self.assertIsNotNone(win.hud_overlay)

            # Full Preview Dialog compact, icon-only elegant controls
            dlg = app_main.ImagePreviewDialog(mp4_1, win)
            try:
                dlg.show()
                self.app.processEvents()
                self.assertIsNotNone(dlg.media_bar)
                self.assertEqual(dlg.media_bar.objectName(), "previewMediaBar")
                self.assertEqual(dlg.play_pause_btn.text(), "")
                self.assertEqual(dlg.mute_btn.text(), "")
                self.assertIsNotNone(dlg.play_pause_btn.icon())
                self.assertIsNotNone(dlg.mute_btn.icon())
                self.assertEqual(dlg.play_pause_btn.width(), 28)
                self.assertEqual(dlg.mute_btn.width(), 28)

                # Test next/previous media navigation in preview dialog across active queue
                win.filter_combo.setCurrentText("All Files")
                self.app.processEvents()
                initial_idx = win.current_index
                dlg.show_next_media()
                self.app.processEvents()
                self.assertNotEqual(win.current_index, initial_idx)
                self.assertEqual(dlg.image_path, win.filtered_files[win.current_index])
                self.assertIn(os.path.basename(dlg.image_path), dlg.info_label.text())

                # Navigate back
                dlg.show_previous_media()
                self.app.processEvents()
                self.assertEqual(win.current_index, initial_idx)
                self.assertEqual(dlg.image_path, win.filtered_files[initial_idx])

                # Video frame / timeline stepping (+/- 80ms)
                dlg.step_frame(1)
                self.assertGreaterEqual(dlg._last_seek_time, 0.0)

                # Keyboard volume adjustment
                dlg._adjust_volume(-0.10)
                self.assertLessEqual(dlg.vol_slider.value(), 90)
                dlg._adjust_volume(0.05)
            finally:
                dlg.close()
        finally:
            win.close()

    def test_preview_dialog_playback_isolation_and_teardown(self):
        """Verify strict playback isolation: MainWindow stops during modal preview and preview teardown is 100% clean."""
        _png, _dup, _gif, mp4_1 = self._create_sample_media()
        win = app_main.ImageSorterApp()
        try:
            win.show()
            self.app.processEvents()
            files = app_main.scan_image_files(self.src_dir)
            win.load_file_list(self.src_dir, files)
            win.filter_combo.setCurrentText("All Files")
            self.app.processEvents()

            # Launch preview dialog
            dlg = app_main.ImagePreviewDialog(mp4_1, win)
            try:
                dlg.show()
                self.app.processEvents()

                # Simulate modal preview active state
                win._preview_dialog_active = True
                win.show_current_image(win.filtered_files)

                # MainWindow must NOT start deferred timer or video while preview is active
                self.assertFalse(win._deferred_anim_timer.isActive())
                self.assertFalse(win._hover_check_timer.isActive())

                # Teardown preview dialog
                dlg.stop_all_playback()
                self.assertFalse(dlg._anim_playing)
                self.assertFalse(dlg._anim_timer.isActive())
                self.assertIsNone(dlg.video_controller.player)
            finally:
                dlg.close()
                win._preview_dialog_active = False
        finally:
            win.close()

    def test_performance_and_ram_optimization_workflow(self):
        """Verify performance optimizations: cached natural sort keys, O(1) queue removal, RAM trim, and filmstrip item pooling."""
        from core.file_ops import natural_sort_key
        from core.media_queue import MediaQueueModel
        from media.cache import PixmapLRUCache
        from PySide6.QtGui import QPixmap

        # 1. Test cached natural sort key
        key1 = natural_sort_key("image_001.png")
        key2 = natural_sort_key("image_001.png")
        self.assertIs(key1, key2)
        self.assertEqual(key1, ("image_", 1, ".png"))

        # 2. Test MediaQueueModel O(1) removal
        from core.history import HistoryStore
        hs = HistoryStore()
        q = MediaQueueModel(hs)
        q.filtered_files = ["a.png", "b.png", "c.png"]
        self.assertEqual(len(q.filtered_files), 3)
        q.current_index = 2
        q.remove_item("c.png")
        self.assertEqual(len(q.filtered_files), 2)
        self.assertEqual(q.current_index, 1)

        # 3. Test PixmapLRUCache RAM bounding & trim
        cache = PixmapLRUCache(max_entries=24)
        for i in range(15):
            pm = QPixmap(10, 10)
            cache._pix_cache[(f"tok_{i}", 0, 0)] = pm
        self.assertEqual(len(cache._pix_cache), 15)
        cache.trim_memory(target_entries=5)
        self.assertEqual(len(cache._pix_cache), 5)
        cache.clear()
        self.assertEqual(len(cache._pix_cache), 0)

        # 4. Test Filmstrip widget pooling in UI
        _png, _dup, _gif, _mp4 = self._create_sample_media()
        win = app_main.ImageSorterApp()
        try:
            files = app_main.scan_image_files(self.src_dir)
            win.load_file_list(self.src_dir, files)
            strip = win.filmstrip_bar
            strip.update_strip(win.filtered_files, 0, win.pixmap_cache)
            initial_count = len(strip._items)
            self.assertGreater(initial_count, 0)
            first_item = strip._items[0]

            # Update strip for next index without widget destruction
            strip.update_strip(win.filtered_files, 1, win.pixmap_cache)
            self.assertEqual(len(strip._items), initial_count)
            self.assertIs(strip._items[0], first_item)
        finally:
            win.close()

    def test_filmstrip_thumbnails_and_button_hold_rapid_navigation(self):
        """Verify filmstrip decodes actual thumbnails instead of VID/IMG, and button/key hold navigates & rapid-moves."""
        _png, _dup, _gif, mp4 = self._create_sample_media()
        win = app_main.ImageSorterApp()
        try:
            files = app_main.scan_image_files(self.src_dir)
            win.load_file_list(self.src_dir, files)
            win.show()
            self.app.processEvents()

            # 1. Verify Next & Previous buttons have auto-repeat enabled
            self.assertTrue(win.next_button.autoRepeat())
            self.assertTrue(win.prev_button.autoRepeat())
            self.assertGreater(win.next_button.autoRepeatInterval(), 0)

            # 2. Verify Filmstrip decoded real thumbnails (not VID / IMG text)
            strip = win.filmstrip_bar
            strip.update_strip(win.filtered_files, 0, win.pixmap_cache)
            self.app.processEvents()
            for it in strip._items:
                if it.isVisible():
                    self.assertFalse(it.thumb_label.pixmap().isNull(), f"Item {it.index} thumbnail was null")
                    self.assertEqual(it.thumb_label.text(), "", f"Item {it.index} still had text '{it.thumb_label.text()}'")

            # 3. Verify keyboard auto-repeat for navigation (Key_Right / Key_Left)
            initial_idx = win.current_index
            ev_right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Right, Qt.NoModifier, "", True, 1)
            self.app.sendEvent(win, ev_right)
            self.assertEqual(win.current_index, initial_idx + 1)

            ev_left = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Left, Qt.NoModifier, "", True, 1)
            self.app.sendEvent(win, ev_left)
            self.assertEqual(win.current_index, initial_idx)

            # 4. Verify Folder button hold starts rapid move and immediately moves on delay expiration
            win._on_folder_btn_pressed(0)
            self.assertEqual(win._active_rapid_slot, 0)
            self.assertTrue(win._rapid_move_delay_timer.isActive())
            # Delay timeout immediately performs rapid_move step
            idx_before = win.current_index
            win._rapid_move_delay_timer.timeout.emit()
            self.assertTrue(win._rapid_move_timer.isActive())
            self.assertGreater(win.current_index, idx_before)
            win._on_folder_btn_released()
            self.assertFalse(win._rapid_move_timer.isActive())
            self.assertIsNone(win._active_rapid_slot)
        finally:
            win.close()

    def test_structured_filter_combo_and_realtime_search_bar(self):
        """Verify structured smart filter with dynamic counts, active-only extensions, and real-time search."""
        png_1, dup_jpg, gif_1, mp4_1 = self._create_sample_media()
        win = app_main.ImageSorterApp()
        try:
            win.show()
            files = app_main.scan_image_files(self.src_dir)
            win.load_file_list(self.src_dir, files)
            self.app.processEvents()

            # 1. Verify combo box contents and dynamic counts
            combo = win.filter_combo
            combo_texts = [combo.itemText(i) for i in range(combo.count())]
            self.assertIn("All Files (4)", combo_texts)
            self.assertIn("All Images (3)", combo_texts)
            self.assertIn("All Videos (1)", combo_texts)
            self.assertIn("Animated / GIF (1)", combo_texts)
            self.assertIn("Flagged Only (0)", combo_texts)
            self.assertIn("Duplicates Only (0)", combo_texts)

            # Active extensions must exist (.png, .jpg, .gif, .mp4)
            self.assertTrue(any(".png (1)" in t for t in combo_texts))
            self.assertTrue(any(".jpg (1)" in t for t in combo_texts))
            self.assertTrue(any(".gif (1)" in t for t in combo_texts))
            self.assertTrue(any(".mp4 (1)" in t for t in combo_texts))

            # Unused formats (.bmp, .tiff, etc.) must NOT clutter the menu
            self.assertFalse(any(".bmp" in t for t in combo_texts))
            self.assertFalse(any(".tiff" in t for t in combo_texts))

            # 2. Real-time search bar substring filtering
            self.assertIsNotNone(win.search_input)
            self.assertEqual(len(win.filtered_files), 4)

            # Search "clip" matches mp4_1
            win.search_input.setText("clip")
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 1)
            self.assertEqual(win.filtered_files[0], mp4_1)

            # Case-insensitive search "CLIP"
            win.search_input.setText("CLIP")
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 1)
            self.assertEqual(win.filtered_files[0], mp4_1)

            # Clear search restores files
            win.search_input.clear()
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 4)

            # 3. Combined Filter + Search
            combo.setCurrentText("All Images")
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 3)

            win.search_input.setText("loop")
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 1)
            self.assertEqual(win.filtered_files[0], gif_1)

            # Search non-matching term
            win.search_input.setText("nonexistent_filename_xyz")
            self.app.processEvents()
            self.assertEqual(len(win.filtered_files), 0)

            # 4. Shortcut Ctrl+F and Escape key handling
            win.search_input.clear()
            combo.setCurrentText("All Files")
            self.app.processEvents()

            win.focus_search()
            self.assertTrue(win.search_input.hasFocus())

            win.search_input.setText("test")
            esc_ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Escape, Qt.NoModifier)
            handled = win.eventFilter(win.search_input, esc_ev)
            self.assertTrue(handled)
            self.assertEqual(win.search_input.text(), "")
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
