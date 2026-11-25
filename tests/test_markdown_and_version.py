"""Unit tests for version comparison, Markdown rendering, dialogs, and menu icons."""

import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

import core.config as cfg
import main as app_main
from core.workers import is_newer_version
from ui.theme import make_vector_icon, render_github_markdown_html, resolve_studio_tokens, slot_text_color


class MarkdownVersionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._orig_cfg = cfg._RESOLVED_CONFIG_DIR
        self._orig_sig = cfg._LAST_INTERNAL_SETTINGS_SIG
        self._tmp = tempfile.mkdtemp(prefix="imgsorter_md_test_")
        cfg._RESOLVED_CONFIG_DIR = self._tmp

    def tearDown(self):
        cfg._RESOLVED_CONFIG_DIR = self._orig_cfg
        cfg._LAST_INTERNAL_SETTINGS_SIG = self._orig_sig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_version_comparison_and_app_version(self):
        self.assertEqual(app_main.APP_VERSION, "2.1.32-Stable")
        self.assertEqual(app_main.AboutDialog.VERSION, "2.1.32-Stable")
        self.assertTrue(is_newer_version("2.1.31-Stable", "2.1.32-Stable"))
        self.assertTrue(is_newer_version("2.1.32-Beta", "2.1.32-Stable"))
        self.assertFalse(is_newer_version("2.1.32-Stable", "2.1.31-Stable"))
        self.assertFalse(is_newer_version("2.1.32-Stable", "1.0-Stable"))

    def test_github_markdown_html_renderer(self):
        t = resolve_studio_tokens()
        md = (
            "## Release Overview\n"
            "- Top bullet with `inline_code`\n"
            "  - Nested sub-item\n"
            "> **Note**: [Releases](https://github.com/Zy0x/Image-Sorter/releases)"
        )
        rendered = render_github_markdown_html(md, t)
        self.assertIn("Release Overview", rendered)
        self.assertIn("<hr", rendered)
        self.assertIn("<ul", rendered)
        self.assertIn("<code", rendered)
        self.assertIn("https://github.com/Zy0x/Image-Sorter/releases", rendered)

    def test_dialogs_and_all_menus_have_icons(self):
        win = app_main.ImageSorterApp()
        try:
            for menu_action in win.menuBar().actions():
                menu = menu_action.menu()
                if menu is None:
                    continue
                for act in menu.actions():
                    if not act.isSeparator():
                        self.assertFalse(
                            act.icon().isNull(),
                            f"Menu item '{act.text()}' must have a non-null icon",
                        )

            up = app_main.UpdateDialog(
                win,
                current_version="2.1.20-Stable",
                latest_version="2.2.0-Stable",
                release_notes="- Modular refactor\n  - Nested list check",
                download_url="https://github.com/Zy0x/Image-Sorter/releases",
            )
            self.assertEqual(up.status_badge.text(), "Update Available")
            self.assertTrue(up.download_button.isEnabled())
            up.close()

            about = app_main.AboutDialog(win)
            about.close()

            sg = app_main.ShortcutsGuideDialog(win)
            sg.close()

            # Verify Light Mode & Dark Mode palette sync, contrast helpers, and non-black translucent vector icon fill
            win.set_theme_mode("light")
            self.assertEqual(self.app.palette().window().color().name().lower(), "#f4f6fa")
            self.assertNotEqual(slot_text_color("#f59e0b", is_dark=False), "#f59e0b")

            icon_img = make_vector_icon("folder", "#3b82f6", 16).pixmap(16, 16).toImage()
            mid_px = icon_img.pixelColor(icon_img.width() // 2, icon_img.height() // 2)
            self.assertGreater(mid_px.blue(), mid_px.red(), "Folder vector icon fill must be blue-tinted, not opaque black")

            win.set_theme_mode("dark")
            self.assertEqual(self.app.palette().window().color().name().lower(), "#0e1015")
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
