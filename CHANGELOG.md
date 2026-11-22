# Changelog

All notable changes to Image Sorter are listed here.

## 2.1.20 — 2026-11-22

### Refactored & Improved — modular `core/`, `media/`, `ui/` architecture, legacy asset cleanup & structured `tests/` suite
- **Modular Package Refactoring (`core/`, `media/`, `ui/`, thin `main.py`):** Split the monolithic 6,433-line `main.py` into cohesive modules:
  - `core/` (`config.py`, `history.py`, `file_ops.py`, `media_queue.py`, `workers.py`, `hot_reload.py`) handling atomic settings JSON I/O, lockstep `HistoryStore`, `os.scandir` file operations, queue filtering, background worker threads, and recursive multi-module live hot-reload.
  - `media/` (`formats.py`, `decoders.py`, `duplicates.py`, `cache.py`, `video_controller.py`) encapsulating unified OpenCV/Pillow decoders, perceptual 64-bit `dHash` duplicate grouping, stat-keyed `PixmapLRUCache`, and `VideoMediaController` for zero-lock QtMultimedia playback (while retaining `utils/image_utils.py` as a clean compatibility shim).
  - `ui/` (`theme.py`, `widgets.py`, `dialogs/`, `main_window.py`) centralizing Studio Slate tokens/QSS/2× DPI vector icons, reusable widgets (`StageViewport`, `MediaHudOverlay`, `ClickSeekSlider`, `ToastNotification`, `LoadingOverlay`), and cleanly separated dialogs (`UpdateDialog`, `AboutDialog`, `ShortcutsGuideDialog`, `JumpToMediaDialog`, `CustomThemeDialog`, `FolderSettingsDialog`, `RapidMoveSettingsDialog`, `ImagePreviewDialog`).
- **Obsolete Asset & Build Cleanup:** Removed unused legacy Qt resource files (`utils/resources.py`, `utils/resources.qrc`, `res_compiler.bat`), obsolete workflow stub, and 16 unused legacy PNG icons in `assets/icons/`. Updated `build.bat`, `cleaner.bat`, and `installer.iss` to bundle `core/`, `media/`, and `ui/`, and fixed `installer.iss` uninstaller cleanup to target `{localappdata}\ImageSorter`.
- **Structured Unittest Suite & Visual Polish:** Added a permanent `tests/` suite (`python -m unittest discover -s tests -v`), deduplicated stage pixmap fitting (`_paint_fitted_pixmap`) and modal messaging (`show_studio_message`), enabled clean word-wrapping on `FolderSettingsDialog` slot captions, and replaced Qt mnemonic ampersand on the custom theme save button.

## 2.1.19 — 2026-11-22

### Improved — balanced menu icon-to-label spacing & GitHub Markdown Release Notes preview
- **Refined Menu Item & Icon Padding (`QMenu::item` / `QMenu::icon`):** Reduced left `QMenu::item` padding from `28px` to `10px` (since Qt's Fusion menu style already reserves the left icon gutter column) and balanced `QMenu::icon` offset (`8px`), bringing menu icons and labels into a tight, natural studio alignment across `File`, `View`, `Settings`, `Help`, and `Recent Folders`.
- **GitHub-Style Rendered Release Notes Preview (`UpdateDialog` / `render_github_markdown_html`):** Replaced raw plain-text release notes with a formatted `QTextBrowser` renderer supporting GitHub Markdown headings (`#`–`####` + hairline dividers), compactly indented bullet & numbered lists (`setIndentWidth(15)` with sub-item nesting and task checkmarks), inline code pills, fenced code blocks, styled blockquotes, and clickable Markdown / release URLs in both Dark and Light themes.

## 2.1.18 — 2026-11-22

### Improved — compact scrollable Filter ComboBox popup (`combobox-popup: 0` & `maxVisibleItems=10`)
- **Bounded 10-Row Scrollable Filter Dropdown (`filter_combo`):** Enabled `combobox-popup: 0` on `QComboBox`, capped visible popup rows to **10 items (`~350 px` height)** via `setMaxVisibleItems(10)`, and styled a sleek 8px vertical scrollbar + 26px rounded item rows inside `QAbstractItemView` so the 38-item media filter menu never stretches across the full screen height.

## 2.1.17 — 2026-11-22

### Improved — end-to-end Studio Slate UI consistency, complete menu vector icons & scrollable anti-clipping dialogs
- **Unified Studio Slate Dialog, Popup & Overlay System (`resolve_studio_tokens` & `build_studio_dialog_qss`):** Standardized every secondary window, modal dialog, message box, loading overlay, and tooltip (`ShortcutsGuideDialog`, `AboutDialog`, `UpdateDialog`, `FolderSettingsDialog`, `RapidMoveSettingsDialog`, `CustomThemeDialog`, `jump_to_image_dialog`, `QMessageBox`, `loading_widget`, and `QToolTip`) on the shared Studio Slate token engine so colors, borders, typography, inputs, sliders, scrollbars, and action buttons remain 100% consistent across Dark, Light, System, and Custom themes.
- **Complete High-DPI Vector Icon Suite Across All Menus (`update_menu_icons`):** Added 2× DPI anti-aliased `QPainter` vector icons for **every item** in `File`, `View`, `Settings`, and `Help`—including `Hide Moved Images`, `Include Subfolders`, `Find Duplicate / Similar Images`, `Jump to Image...`, `Full-Size Preview`, `Recent Folders` entries, `Custom Theme`, `Light/Dark/System Mode`, `Folder Settings`, `Export/Import Settings`, `Rapid Move Speed`, `Reset Default Settings`, `Keyboard Shortcuts & Guide`, `About`, and `Check for Updates`.
- **Scrollable Anti-Clipping `ShortcutsGuideDialog` (`F1`):** Wrapped the two-column keymap table inside a frameless vertical `QScrollArea`, enabled word-wrapping on the Quick Workflow banner, and increased row height/padding so hairlines and keycaps never overlap or clip at any window height.
- **Refined Settings & Info Dialogs:** Upgraded `FolderSettingsDialog` with color-coded `[1]`–`[9]` key badges matching the main window's slot accents, expanded `CustomThemeDialog` into a comfortable `450×480` live hex-swatch editor, and updated `RapidMoveSettingsDialog` with live files/sec throughput feedback for slots `1`–`9`.

## 2.1.16 — 2026-11-22

### Improved — enforced ergonomic minimum window & preview bounds
- **Zero-Loss Ergonomic Minimum Floor (`_sync_minimum_window_size`):** Enforced adaptive minimum bounds (**`780×580`** for 3–5 slots, **`800×620`** when 6–9 slots wrap into 2 rows, safely clamped to physical screen work areas on smaller monitors) so **every UI panel**—including `UP NEXT`, header metadata, active media preview, HUD controls, and all folder cards—stays 100% visible, aligned, and unclipped with zero hidden features or overlaps.
- **Instant Header Elision & Preview Dialog Floor (`680×460`):** Upgraded `ImagePreviewDialog` minimum bounds (`680×460`, screen-safe) and direct window-width metric calculation in `_update_file_info_bar()` / `_update_info_label()` so filenames and resolution/playback tags never clip during live drag resizing.

## 2.1.15 — 2026-11-22

### Improved — viewport-aware compact sizing & responsive layout engine
- **Screen-Adaptive Default Window Size & Fluid Resizing (`640×500` to `4K`):** Initial window and `ImagePreviewDialog` dimensions now adapt automatically to `screen.availableGeometry()` (`min(960, 72%) × min(680, 84%)`), so laptops and small displays (`1280×720` / `1366×768`) are never covered or overflown beyond the taskbar.
- **Responsive Stage Viewports (`_StageViewport` & `_fit_pixmap_box`):** Replaced rigid fixed-size canvas locks with custom viewport wrappers that fluidly rescale images, animated frames, `UP NEXT` previews, empty-state guides, and the floating video seekbar HUD in real time without layout collapse.
- **Auto-Wrapping Folder Grid (`QGridLayout` via `_relayout_folder_grid`):** Destination slots (`3`–`9`) remain single-row on wide monitors and cleanly wrap into two balanced rows on narrow windows (while hiding the `UP NEXT` rail automatically below `680px` width to prioritize the active preview).

## 2.1.14 — 2026-11-22

### Improved — Studio Slate UI redesign, vector icons & interactive video seekbar
- **Unified Studio Slate Visual Identity (`_get_ui_tokens`):** Replaced pitch-black voids, harsh neon red/magenta glow shadows, and opaque flat folder blocks with a cohesive obsidian/warm-paper palette, soft ambient card depth, `UP NEXT` queue rail framing, flush edge-to-edge action bar alignment, and middle-elided header metadata badges.
- **High-DPI Vector Icon System (`make_vector_icon`):** Replaced pixelated/wordy PNG button badges (`BACK`, `NEXT`, `SKIP`, legacy folder icons) with 2× DPI anti-aliased `QPainter` vector icons that dynamically adapt to Light, Dark, System, and Custom themes.
- **Unified Frosted Media HUD & Interactive Video Seek Scrubber (`_ClickSeekSlider`):** Combined Play/Pause (`P`), Sound/Mute (`M`), live timecodes (`0:00 / 0:14`), and click-anywhere timeline scrubbing into one floating frosted-glass capsule at the bottom of video previews, and redesigned `ImagePreviewDialog` into an uncluttered header + bottom media dock layout.

## 2.1.13 — 2026-11-22

### Added & Improved — hardware-synced video + audio playback, Play/Pause & Mute controls
- **Synced Native-FPS Video & Sound Engine (`QMediaPlayer` + `QAudioOutput` + `QVideoSink` via In-Memory `QBuffer`):** Upgraded main window and Full-Size Preview playback from sampled slideshow frames to real-time, A/V-synced native-FPS decoding backed by FFmpeg in memory (up to 120 MB, with automatic `VideoDecodeThread` fallback for larger files), keeping video and audio perfectly in sync with **zero Windows disk locks** so files can be moved or deleted even mid-playback.
- **On-Canvas Play / Pause (`P`) & Mute / Unmute (`M`) Controls (`_build_video_controls`):** Added translucent overlay **`❚❚ Pause` / `▶ Play`** buttons for both videos and animated images (GIF/WebP/APNG/AVIF), plus **`Sound` / `Muted`** controls on videos in both the main viewer (`P` / `M`) and `ImagePreviewDialog` (`Space` / `P` / `M`), alongside double-click Full Preview safety pause to prevent overlapping audio tracks.
- **Persistent Sound Preference:** Added `video_muted` and `video_volume` settings so your mute state stays remembered across videos and restarts.

## 2.1.12 — 2026-11-21

### Fixed & Optimized — background streaming video decoder & zero-lag video playback
- **Non-Blocking Background Video Streaming (`VideoDecodeThread` & `decode_video_qimages`):** Moved multi-frame video decoding off the main GUI thread into a cancellable `VideoDecodeThread` that streams batches of 8–10 frames (`QImage` resized in C++ via `cv2.resize(..., INTER_AREA)` and skipping intermediate frames via `cap.grab()` without decoding unused pixels). Video playback now starts immediately after the first batch arrives with **0 ms main-thread UI freeze**.
- **Single-Open First-Keyframe (`I-Frame`) Thumbnail Extraction:** Removed `CAP_PROP_POS_FRAMES` seeking on initial thumbnail load and unified metadata + first-keyframe decoding into a single `cv2.VideoCapture` pass (~31–34 ms on 720×1280 H.264 `.mp4` files instead of ~170–800 ms).
- **Scaled Frame Cache in `ImagePreviewDialog` (`_get_scaled_frame`):** Pre-caches scaled frames at the current zoom level and removes redundant `QApplication.processEvents()` calls during animation ticks so full-size video/GIF playback and panning remain smooth at 60 FPS.

## 2.1.11 — 2026-11-21

### Improved — instant video navigation, deferred multi-frame decode & video LRU caching
- **Cached Video Metadata & Animation Frames (`PixmapLRUCache.get_video_metadata` / `get_animation_frames`):** Video resolution, FPS, frame count, duration, and extracted playback frames are now cached in memory alongside keyframe thumbnails, eliminating repeated `cv2.VideoCapture` opens during navigation.
- **Deferred 75 ms Idle Video Playback (`_start_deferred_video_anim`) & Rapid Move Fast-Path:** Stepping through videos (`←` / `→`) or holding `1`–`9` for Rapid Move renders the cached keyframe and duration badge immediately (~5.6–9.3 ms/video) and begins full multi-frame playback only after navigation pauses for 75 ms, automatically resuming playback when Rapid Move stops.

## 2.1.10 — 2026-11-20

### Added — dynamic 3–9 folder slots, subfolder scan, perceptual duplicate finder & LRU pre-fetch cache
- **Dynamic Folder Slots (`3`–`9` Folders & Keys `1`–`9`):** `FolderSettingsDialog` now includes an **Active Folder Slots (`3`–`9`)** selector. Both single-press and continuous **Rapid Move** work across all active slots (`1`–`9` on keyboard or mouse hold), with responsive button sizing.
- **Recursive Subfolder Scanning (`View → Include Subfolders`, `Ctrl+Shift+S`):** Optional iterative `os.scandir` subfolder traversal that automatically excludes configured destination folders to prevent recursive self-sorting.
- **Perceptual Duplicate & Similar Image Finder (`View → Find Duplicate / Similar Images`, `Ctrl+D`):** Computes 64-bit Difference Perceptual Hashes (`dHash`) in a background thread to detect exact and near-duplicate images across different formats/resolutions (e.g. PNG vs re-compressed JPEG/AVIF or resized copies), complete with a `Duplicates Only` filter and `DUP #N` badges.
- **Ultra-Fast In-Memory LRU Pre-Fetch Cache (`PixmapLRUCache`):** Caches decoded `QPixmap`s and image metadata keyed by `(path, mtime_ns, size)` and pre-fetches neighboring items (`+1`, `+2`, `-1`, `+3`) during idle time, reducing back-and-forth navigation latency to ~2.5 ms/step.

## 2.1.9 — 2026-11-20

### Added — video sorting, live animated zoom preview & 25+ media formats
- **Live Animated Playback & Frame Stepping in `ImagePreviewDialog` (`F` / double-click):** Animated `.gif`, `.webp`, `.apng`, `.avif`, and video files continue playing live while zoomed in and panned, complete with `Play/Pause` (`Space`) and frame-by-frame stepping (`⟨` / `[` and `⟩` / `]`).
- **Video Sorting Support (`.mp4`, `.webm`, `.mkv`, `.mov`, `.avi`, `.m4v`, `.wmv`):** Extracts live frames, duration badges (`▶ M:SS`), and resolution metadata into memory via OpenCV and immediately releases file handles so videos can be moved (`1`–`5`, Rapid Move) or restored (`Ctrl+Z`) on Windows without file locks.
- **Expanded Modern Image Decoders:** Added full decoding and metadata support for `.avif`, `.heic`, `.heif` (via `pillow-heif`), `.psd` (Photoshop), `.apng`, `.svgz`, `.tga`, `.icns`, `.cur`, `.pbm`, `.pgm`, `.ppm`, `.xbm`, `.xpm`, and `.wbmp`.
- **Smart Media Category Filters:** Added `All Images`, `All Videos`, and `Animated / GIF` quick filters alongside individual extension filters.

## 2.1.8 — 2026-11-20

### Added — smart double-click zoom & drag-to-pan in Full-Size Preview
- **Smart Cursor-Anchored Double-Click Zoom (`_smart_double_click_zoom`):** Double-clicking any point on the image inside `ImagePreviewDialog` zooms directly into that exact coordinate (~2.25× fit / at least 100%); double-clicking again when zoomed in toggles smoothly back to **Fit-to-Window**.
- **Click-and-Drag Panning / Hand Tool (`Drag Move`):** When zoomed in beyond Fit, clicking and dragging with the left mouse button pans the image smoothly in 1:1 pixel sync with automatic `OpenHandCursor` / `ClosedHandCursor` feedback.
- **Cursor-Anchored Mouse Wheel Zoom & Keyboard Controls:** Mouse-wheel scrolling zooms in and out anchored at the cursor position, accompanied by sleek 8px scrollbars and keyboard shortcuts (`+`/`=`, `-`, `0` for Fit, `1` for 100%).

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
