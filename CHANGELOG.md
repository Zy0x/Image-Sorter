# Changelog

All notable changes to Image Sorter are listed here.

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
