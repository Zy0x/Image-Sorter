# Changelog

All notable changes to Image Sorter are listed here.

## 2.1.7 — 2026-11-20

### Changed — editorial monochrome shortcut sheet (anti-slop redesign)
- **Replaced generic card/emoji layout with a native typographic keymap (`ShortcutsGuideDialog`):** Removed decorative emojis, neon cyan accents, and wide combined pills in favor of individual physical keycaps (`[1]` `–` `[5]`, `[Ctrl]` `[Z]`, `[←]` `[→]`), hairline row dividers, and muted uppercase category headers (`SORTING`, `NAVIGATION`, `VIEW & INSPECT`, `FILE & MOUSE`).
- **Refined empty-state palette:** Neutral monochrome key labels and muted descriptions.

## 2.1.6 — 2026-11-20

### Changed — streamlined navigation & distinct Skip shortcut
- **Removed redundant `A` / `D` navigation shortcuts:** `Previous` and `Next` now use the dedicated arrow keys **`←` (`Left`)** and **`→` (`Right`)** only.
- **Distinct `Skip` (`Space`) behavior (`find_next_unmoved_index`):** While `Next` (`→`) steps through every image sequentially (including already-moved ones), `Skip` (`Space`) now jumps directly to the next **unmoved** image.
- **Cleaner `ShortcutsGuideDialog` (`F1`) & empty-state table:** Combined `← / →` into one row and separated `Ctrl + E` (Show in Explorer) and `Delete` (Recycle Bin) into distinct rows so every shortcut maps 1-to-1 to a unique action.

## 2.1.5 — 2026-11-20

### Added — live hot-reload
- **Automatic Live Hot-Reload (`init_hot_reload`):** Watches `main.py`, `utils/image_utils.py`, and `config/settings.json` while running from source. Editing `settings.json` refreshes themes and folder buttons in-place; editing code files validates syntax in memory and seamlessly reloads the window at the exact same position, folder, image index, filter, and open dialog without manual close/reopen.

## 2.1.4 — 2026-11-20

### Changed — UI polish for shortcuts & quick guide
- **Redesigned `ShortcutsGuideDialog` (`F1`):** Built with native Qt cards (`QFrame`), circular step badges, a 2-column `QGridLayout`, and 3D rounded keycap pill badges (`QLabel#keyBadge`) instead of raw HTML `<div>`/`<span>` blocks, so all 3 sections fit cleanly on one screen without scrollbars or clipped backgrounds.
- **Redesigned Empty-State Quick Guide (`No Image Loaded`):** Formatted as a clean, centered 2-column shortcut table with contrasting row cards and balanced spacing.

## 2.1.3 — 2026-11-20

### Added
- **`run.bat` one-click launcher:** Double-click `run.bat` to open Image Sorter directly without a background console window (automatically checks and installs `requirements.txt` if missing; supports `run.bat --debug` to view console logs).

## 2.1.2 — 2026-11-20

### Added — productivity & media features
- **Unified Rapid Move for all 5 folders (`1`–`5` & Folder A–E):** Holding key `5` or holding left-click on Folder E now performs Rapid Move just like Folders A–D (`1`–`4`).
- **Image dimensions & file size in top bar:** Displays `(width×height • size)` next to the current filename.
- **Full-Size & Zoom Preview (`F` or double-click main image):** Inspect images in a dedicated resizable dialog with Zoom In (`+`), Zoom Out (`−`), Fit, 100%, and mouse-wheel zoom.
- **Fast navigation (`Home`, `End`, `Ctrl+G` Jump to Image) & `Hide Moved Images` (`Ctrl+H`):** Jump to first/last image or any image number, and optionally hide images that have already been moved.
- **Move to Windows Recycle Bin (`Delete`) & Show in File Explorer (`Ctrl+E`):** Safely send unwanted images to the Windows Recycle Bin or reveal the current file in Explorer.
- **Animated `.gif` / `.webp` playback (`QMovie`):** Plays multi-frame animations from an in-memory buffer so files on disk are never locked on Windows.
- **Memory-efficient scaled decoding:** High-resolution images (12–50 MP) are pre-scaled during decode via `QImageReader.setScaledSize()` to reduce RAM usage.

### Fixed — technical & build gaps
- **`File → Export Log` fixed:** Reads and exports the activity log directly from `config/event.log` on disk instead of failing with `"No log to export."`.
- **Automatic settings load on startup + `Settings → Reset Default Settings`:** Removed the startup `"Would you like to load last settings?"` popup that could accidentally overwrite folder settings; added a dedicated `Reset Default Settings` menu action with confirmation.
- **Smart config path (`%LOCALAPPDATA%` fallback & `--portable` support):** Automatically stores configuration in `%LOCALAPPDATA%\ImageSorter\config` when installed in a read-only directory such as `C:\Program Files`, while keeping local `config/` for portable and writable directories.
- **Synced extension filter dropdown:** Populates the extension filter from formats supported by Qt on the current machine (including `.jfif`, `.tif`, `.ico`, `.svg`) and hides unsupported placeholders.
- **Modernized `FolderSettingsDialog`:** Added theme support (Light/Dark/Custom), column headers, `Cancel` button, and fallback default names when an input is left blank.
- **Fixed `build.bat` & `res_compiler.bat`:** Eliminated double PyInstaller execution, excluded private `config/` files from being bundled into `.exe`, and restored `pyside6-rcc` verification.

## 2.1.1 — 2026-11-20

### Added — shortcuts & quick guide
- Folder buttons display their keyboard numbers (`[1] Folder A` – `[5] Folder E`) and tooltips.
- Added empty-state quick-start guide and `Help → Keyboard Shortcuts & Guide` (`F1`) plus `Ctrl+O` for `Import Folder`.

### Fixed — file safety & large-folder performance
- Moving an image never overwrites an existing file (`name (1).ext`, `name (2).ext`), and Undo never overwrites a file at the original path.
- Active extension filter always moves the displayed image; importing a second folder immediately refreshes the list.
- Clicking an unconfigured folder button opens folder settings and moves only one image.
- Single-pass `os.scandir` background scanner (`FolderScanThread`) with natural sort (`IMG_2` before `IMG_10`), $O(1)$ move/undo updates, and atomic debounced `history.json` writes (100,000-file import reduced from ~22.9s to ~0.43s).
- `load_pixmap` applies EXIF auto-orientation and content-based format detection.

## 2.0 — 2025-07-28
- Rapid Move, update checker, About dialog with social links, installer.
