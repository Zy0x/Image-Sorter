# Image Sorter — Product & Technical Roadmap

Dokumen ini merangkum peta jalan pengembangan **Image Sorter** mengikuti skema versi `2.1.x` → `2.1.99` → `2.2.0`.

---

## ✅ v2.1.1-Stable (Selesai)
Fokus: **Keamanan File, Perbaikan Bug Kritis, Skala 100.000+ File, & Panduan Shortcut**

- [x] **Zero-Overwrite Protection:** Penamaan ulang otomatis (`nama (1).ext`, `nama (2).ext`) saat memindahkan file ke folder tujuan yang sudah memiliki nama file sama, serta proteksi tabrakan saat *Undo*.
- [x] **Sinkronisasi Filter & Aksi Pindah:** Memastikan gambar yang dipindahkan selalu sesuai dengan gambar yang tampil saat filter ekstensi aktif.
- [x] **Pemindaian Skala Besar (`FolderScanThread`):** Satu kali lintasan `os.scandir()` di *background thread* dengan pengurutan natural (`IMG_2` sebelum `IMG_10`), meningkatkan kecepatan impor 100.000 file dari ~22,9 detik menjadi ~0,43 detik.
- [x] **Operasi Move & Undo $O(1)$:** Penulisan `history.json` secara *debounced* & atomik (`.tmp` + `os.replace`) serta batas riwayat navigasi `deque(maxlen=500)`.
- [x] **Stabilitas Rapid Move:** Perbaikan *runaway move* pada konfigurasi folder awal dan penghentian otomatis pada gambar terakhir/saat error/kehilangan fokus.
- [x] **Pemuat Gambar Tangguh (`load_pixmap`):** Rotasi otomatis berdasarkan metadata EXIF (`setAutoTransform`) dan deteksi format dari isi file (`setDecideFormatFromContent`).
- [x] **Panduan Shortcut 3 Lapis:** Label `[1]`–`[5]` & tooltip pada tombol folder, panduan singkat di layar awal (*empty state*), serta dialog **`Help → Keyboard Shortcuts & Guide` (`F1`)** dan shortcut **`Ctrl+O`**.

---

## ✅ v2.1.2-Stable (Selesai)
Fokus: **Penyempurnaan Fungsi Inti, Fitur Produktivitas Lengkap, Performa Media Berat, & Konsolidasi Repo**

- [x] **Perbaikan `File → Export Log`:** Membaca dan mengekspor log langsung dari `config/event.log`.
- [x] **Auto-Load Pengaturan Saat Startup & Menu Reset:** Memuat pengaturan terakhir secara otomatis tanpa popup berisiko, dilengkapi menu **`Settings → Reset Default Settings`** dengan konfirmasi.
- [x] **Dukungan Lokasi Konfigurasi `%LOCALAPPDATA%` & Mode `--portable`:** Otomatis beralih ke `%LOCALAPPDATA%\ImageSorter\config` bila folder aplikasi tidak *writable* (mis. `C:\Program Files`).
- [x] **Sinkronisasi Daftar Filter Ekstensi:** Menyesuaikan isi dropdown filter dengan format yang didukung decoder Qt pada sistem (termasuk `.jfif`, `.tif`, `.ico`, `.svg`).
- [x] **Modernisasi `FolderSettingsDialog` & Perbaikan `build.bat` / `res_compiler.bat`:** Dialog pengaturan folder bertema dengan tombol `Cancel`, serta perbaikan build PyInstaller tunggal tanpa membungkus `config/` pribadi.
- [x] **Seragamkan *Rapid Move* untuk Kelima Folder (`1`–`5` / Folder A–E):** Tahan tombol `1`–`5` atau tahan klik tombol Folder A–E semuanya mendukung *Rapid Move*.
- [x] **Informasi Dimensi & Ukuran File di Baris Atas:** Menampilkan `(lebar×tinggi • ukuran)` di samping nama file.
- [x] **Navigasi Cepat (`Home`, `End`, *Jump to Image* `Ctrl+G`) & Filter *"Hide Moved Images"* (`Ctrl+H`).**
- [x] **Decode Hemat Memori (`setScaledSize`) & Animasi `.gif`/`.webp` (`QMovie` via buffer memori tanpa mengunci file).**
- [x] **Hapus Aman ke *Recycle Bin* (`Delete`), Buka di Explorer (`Ctrl+E`), & Pratinjau Penuh / Zoom (`F` / klik ganda).**

---

## ✅ v2.1.3-Stable (Selesai)
- [x] **One-Click Batch Launcher (`run.bat`):** Peluncur cepat yang otomatis memeriksa dependensi Python (`PySide6`, `requests`), mendukung `.venv` maupun Python sistem, berjalan tanpa jendela CMD menggantung (`pythonw`), serta mendukung mode `run.bat --debug`.

---

## ✅ v2.1.4-Stable (Selesai)
- [x] **Redesign Visual Panduan Shortcut (`F1` & Layar Awal):** Mengganti HTML `<div>`/`<span>` pada `ShortcutsGuideDialog` dengan kartu native `QFrame`, badge langkah melingkar, grid 2 kolom (`QGridLayout`), dan *keycap pill* 3D (`QLabel#keyBadge`) tanpa *scrollbar* yang memotong teks, serta merapikan tabel *quick-start* pada area *No Image Loaded*.

---

## ✅ v2.1.5-Stable (Selesai)
- [x] **Live Auto-Reload / Hot-Reload:** Memantau perubahan file `main.py`, `utils/image_utils.py`, dan `config/settings.json` secara *real-time* (memvalidasi sintaks di memori lalu memuat ulang tampilan, posisi jendela, folder aktif, indeks gambar, dan dialog secara otomatis tanpa tutup-buka manual).

---

## ✅ v2.1.6-Stable (Selesai)
- [x] **Perapian Redundansi Shortcut Navigasi & Fungsi `Skip` (`Space`):** Menghapus duplikasi tombol `A`/`D` sehingga `Previous` dan `Next` eksklusif memakai panah **`←` / `→`**, serta membedakan fungsi **`Skip` (`Space`)** agar langsung melompat ke gambar berikutnya yang **belum dipindahkan (*unmoved*)**.

---

## ✅ v2.1.7-Stable (Selesai)
- [x] **Minimalist Monochrome Keymap Design (Anti-Slop UI):** Menghapus seluruh emoji dekoratif, warna neon cyan, dan kotak gabungan lebar pada `ShortcutsGuideDialog` (`F1`), digantikan dengan *keycap* fisik individual (`[1]` `–` `[5]`, `[Ctrl]` `[Z]`, `[←]` `[→]`), garis pemisah tipis (*hairline divider*), dan tipografi monokrom bergaya perangkat lunak desktop profesional.

---

## ✅ v2.1.8-Stable (Selesai)
- [x] **Smart Cursor-Anchored Double-Click Zoom & Drag-to-Pan (`ImagePreviewDialog`):** Klik ganda pada titik mana pun di jendela *Full-Size Preview* langsung melakukan *zoom-in* tepat ke koordinat kursor (~2,25× fit / minimal 100%) dan klik ganda kedua mengembalikan tampilan ke *Fit-to-Window*; saat diperbesar, gambar dapat ditarik/digeser dengan klik-tahan mouse kiri (*Hand Tool / Drag Move* dengan kursor `OpenHand` / `ClosedHand`) serta mendukung *mouse-wheel zoom* berpusat pada posisi kursor.

---

## ✅ v2.1.9-Stable (Selesai)
- [x] **Live Animated Zoom Preview & Frame Stepping (`ImagePreviewDialog`):** Animasi `.gif`, `.webp`, `.apng`, `.avif`, dan video tetap bergerak secara *live* saat di-zoom dan di-geser (*drag-to-pan*), dilengkapi kontrol `Play/Pause` (`Space`) dan navigasi per-frame (`[` / `]`).
- [x] **Dukungan Sortir Video Tanpa File-Lock (`.mp4`, `.webm`, `.mkv`, `.mov`, `.avi`, `.m4v`, `.wmv`):** Memutar pratinjau video di memori lengkap dengan informasi durasi (`▶ M:SS`) dan resolusi tanpa mengunci file di Windows saat dipindahkan (`1`–`5`) maupun di-*Undo* (`Ctrl+Z`).
- [x] **Ekspansi 25+ Format Gambar Modern & Desain (`.avif`, `.heic`, `.heif`, `.psd`, `.apng`, `.svgz`, `.tga`, `.icns`, `.cur`, `.ppm`, dll.):** Integrasi decoder `Pillow` + `pillow-heif` + `OpenCV` serta filter kategori cerdas (`All Images`, `All Videos`, `Animated / GIF`).

---

## ✅ v2.1.10-Stable (Selesai)
- [x] **Custom Jumlah Slot Folder Dinamis (`3`–`9` Folder & Shortcut `1`–`9`):** Menambah atau mengurangi jumlah slot folder tujuan di `Folder Settings` lengkap dengan *Rapid Move* pada tombol keyboard `1`–`9` maupun tahan klik mouse.
- [x] **Pemindaian Subfolder Rekursif Cerdas (`View → Include Subfolders` / `Ctrl+Shift+S`):** Memindai seluruh sub-direktori secara iteratif menggunakan `os.scandir` dengan pengecualian otomatis terhadap folder tujuan (*destination exclusion*).
- [x] **Deteksi Gambar Duplikat / Mirip (`View → Find Duplicate / Similar Images` / `Ctrl+D`):** Menggunakan *64-bit Perceptual dHash* dan *Hamming distance* untuk mendeteksi gambar kembar identik maupun gambar yang di-resize/dikompres ulang lintas format, dilengkapi filter **`Duplicates Only`** dan badge **`DUP #`**.
- [x] **LRU Pixmap Pre-Fetch Cache (`PixmapLRUCache`):** Pre-decode otomatis gambar tetangga (`+1`, `+2`, `-1`, `+3`) ke dalam memori saat waktu *idle*, mempercepat navigasi bolak-balik dan *Rapid Move* hingga ~2,49 ms per langkah.

---

## ✅ v2.1.11-Stable (Selesai)
- [x] **Instant Video Navigation & Video LRU Cache (`get_video_metadata` / `_start_deferred_video_anim`):** Menyimpan metadata durasi/resolusi serta frame video di dalam `PixmapLRUCache`, menampilkan keyframe pertama secara instan saat berpindah cepat atau *Rapid Move* (~5,66 ms/video), dan memutar multi-frame video secara otomatis begitu navigasi berhenti sejenak (75 ms) tanpa mengunci file di Windows.

---

## ✅ v2.1.12-Stable (Selesai)
- [x] **Background Streaming Video Decoder & Zero-Lag Playback (`VideoDecodeThread` / `decode_video_qimages`):** Memindahkan ekstraksi multi-frame video sepenuhnya ke *background thread* dengan teknik `cap.grab()` + `cv2.resize(INTER_AREA)` di C++ serta pengiriman frame bertahap (*chunked streaming* tiap 8 frame), memangkas waktu buka keyframe video HD 720×1280 menjadi ~31–34 ms dengan **0 ms UI freeze** di layar utama maupun di `ImagePreviewDialog`.

---

## ✅ v2.1.13-Stable (Selesai)
- [x] **Synced Video + Sound Playback, Play/Pause (`P`) & Mute (`M`):** Pemutaran video *native-FPS* dengan suara tersinkronisasi (`QMediaPlayer` + `QAudioOutput` + `QVideoSink`) berbasis *in-memory `QBuffer`* (bebas *file lock* Windows saat *Move* / *Delete* / *Undo*), lengkap dengan kontrol tombol *overlay* **`❚❚ Pause` / `▶ Play`** (`P`) untuk video & animasi serta **`Sound` / `Muted`** (`M`) dengan penyimpanan preferensi otomatis di layar utama maupun *Full-Size Preview*.

---

## ✅ v2.1.14-Stable (Selesai)
- [x] **Studio Slate UI Redesign, Ikon Vektor 2× DPI & Interactive Video Seekbar:** Pembaruan antarmuka bergaya studio (*Obsidian Dark* & *Warm Gallery Light*), penghapusan glow neon dan ikon PNG lama dengan ikon vektor adaptif, kartu tujuan `[1]`–`[9]` bertema aksen lembut minimal sentuh 44px, antrean `UP NEXT`, serta kapsul kontrol video terpadu lengkap dengan *seekbar* interaktif di layar utama maupun *Full-Size Preview*.

---

## ✅ v2.1.15-Stable (Selesai)
- [x] **Responsive Viewport & Auto-Adaptive Scaling (`640×500` – `4K`):** Ukuran awal jendela utama & *Full-Size Preview* menyesuaikan area aman layar (`availableGeometry`), didukung `_StageViewport` agar preview, *empty state*, dan kapsul *seekbar* diskalakan presisi secara *real-time*, *grid* folder `[1]`–`[9]` terlipat otomatis ke 2 baris di layar sempit, serta panel `UP NEXT` bersembunyi cerdas di lebar `<680px`.

---

## ✅ v2.1.16-Stable (Selesai)
- [x] **Batas Minimum Ergonomis Tanpa Komponen Hilang/Tumpang Tindih (`_sync_minimum_window_size`):** Menetapkan batas minimum presisi (**`780×580`** untuk 3–5 slot / **`800×620`** untuk 6–9 slot 2 baris & **`680×460`** untuk *Full-Size Preview*) yang menjaga seluruh panel (`UP NEXT`, kapsul kontrol, metadata header, dan seluruh kartu folder) selalu tampil penuh, sejajar, dan nyaman di setiap ukuran jendela.

---

## ✅ v2.1.17-Stable (Selesai)
- [x] **Konsistensi Penuh Studio Slate di Seluruh Dialog, Popup, Overlay & Menu (`resolve_studio_tokens` / `build_studio_dialog_qss`):** Menyeragamkan seluruh jendela dialog (`ShortcutsGuideDialog`, `AboutDialog`, `UpdateDialog`, `FolderSettingsDialog`, `RapidMoveSettingsDialog`, `CustomThemeDialog`, `Jump to Image`, `QMessageBox`, `loading_widget`, dan `QToolTip`) dengan sistem token Studio Slate, menambahkan ikon vektor 2× DPI lengkap di **seluruh opsi menu** (`File`, `View`, `Settings`, `Help`), serta melengkapi `ShortcutsGuideDialog` (`F1`) dengan `QScrollArea` vertikal dan *word-wrap* agar tidak pernah tumpang tindih atau terpotong di ukuran layar mana pun.

---

## ✅ v2.1.18-Stable (Selesai)
- [x] **Compact Scrollable Filter Dropdown (`combobox-popup: 0` & `setMaxVisibleItems(10)`):** Membatasi tinggi popup `QComboBox` filter ekstensi/kategori media menjadi maksimal **10 baris (`~350 px`)** lengkap dengan *scrollbar* vertikal 8px bergaya Studio Slate agar tidak lagi menjulang memenuhi tinggi layar.

---

## ✅ v2.1.19-Stable (Selesai)
- [x] **Presisi Jarak Ikon Menu & Pratinjau Release Notes Bergaya GitHub (`QMenu::item` / `render_github_markdown_html`):** Merapatkan jarak antara ikon vektor dan teks label di seluruh menu (`File`, `View`, `Settings`, `Help`), serta merender *Release Notes* di dialog *Check for Updates* menjadi pratinjau Markdown bergaya GitHub yang rapi dengan indentasi ringkas (`15px`), tautan klik langsung, *code badge*, dan *blockquote* terstruktur.

---

## ✅ v2.1.20-Stable (Selesai)
- [x] **Modularisasi & Refactoring Arsitektur (`core/`, `media/`, `ui/`, `tests/`) + Pembersihan Aset Usang:** Memecah kode monolitik `main.py` menjadi modul `core/` (config, `HistoryStore`, `file_ops`, `MediaQueueModel`, `workers`, `HotReloadWatcher`), `media/` (`formats`, `decoders`, `duplicates`, `PixmapLRUCache`, `VideoMediaController`), dan `ui/` (`theme`, `widgets`, `dialogs/`, `main_window`), menghapus 16 ikon PNG usang & skrip Qt resource (`resources.py`/`.qrc`/`res_compiler.bat`), memperbarui `build.bat`/`installer.iss`/`cleaner.bat`, serta menambahkan test suite permanen di `tests/`.

---

## ✅ v2.1.21-Stable (Selesai)
- [x] **Konsistensi Kontras Tema Gelap & Terang (`apply_studio_palette`, `slot_text_color`, `StudioComboBox`, `StudioSpinBox`, `MediaHudOverlay`):** Sinkronisasi penuh `QPalette` global dengan token Studio Slate di seluruh dialog dan `QScrollArea`, perbaikan warna *fill* transparan pada ikon vektor (`_qcolor_alpha`), peningkatan kontras teks/badge di *Light Mode* & *Dark Mode*, kontrol `StudioComboBox` dan `StudioSpinBox` berikon chevron vektor, serta kapsul `MediaHudOverlay` yang adaptif terhadap tema aktif.

---

## ✅ v2.1.22-Stable (Selesai)
- [x] **Persistensi Pengaturan Anti-Timpa, Memori Recent Folders & Jejak Histori Lintas Sesi (`_sync_and_save_settings`, `normalize_settings`, `read_recent_event_log`):** Menjamin seluruh perubahan di `FolderSettingsDialog`, `RapidMoveSettingsDialog`, `CustomThemeDialog`, `Recent Folders` (lengkap dengan `last_opened_folder` dan `Clear Recent Folders`), `Hide Moved`, `Include Subfolders`, `Video Mute`, `history.json`, serta `event.log` tersimpan atomik dan termuat kembali secara utuh saat aplikasi dibuka ulang.
- [x] **Pengurutan Antrean Fleksibel (*Sort By*: Nama, Tanggal, Ukuran, Tipe File):** Akses cepat melalui `View → Sort By` dengan pilihan Nama (A–Z / Z–A natural sort), Tanggal Modifikasi (Terbaru/Terlama), Ukuran File (Besar/Kecil), dan Tipe/Ekstensi tanpa mengubah target pilihan kursor aktif secara tiba-tiba.
- [x] **Mini Filmstrip / Dock Thumbnail Interaktif (`FilmstripBar` / `Ctrl+B`):** Pratinjau strip thumbnail horizontal di bawah stage yang menampilkan item sebelum dan sesudah media aktif, dilengkapi bingkai fokus aktif, ikon bintang emas untuk bookmark, badge play untuk video, dan navigasi klik langsung (`jump_to_index`).
- [x] **Batch Auto-Rename Saat Pemindahan File (`AutoRenameSettingsDialog`):** Pengaturan pola format nama otomatis (`Settings → Auto-Rename on Move...`) berbasis token dinamis (`{folder}`, `{name}`, `{date}`, `{index:04d}`) yang terintegrasi aman dengan proteksi konflik tanpa timpa serta dukungan pemulihan *Undo* (`Ctrl+Z`) penuh.
- [x] **Media Bookmark & Quick Flagging (`*` / `Alt+F`):** Menandai file favorit atau penting dengan tombol bintang di info bar atau pintasan `*` / `Alt+F`, dilengkapi filter eksklusif **`Flagged Only`** dan penyimpanan status flag persisten di konfigurasi.
- [x] **Interactive HUD Video Volume Slider (0–100%):** Slider volume audio pada kapsul `MediaHudOverlay` dan `ImagePreviewDialog` dengan tooltip persentase, auto-unmute saat digeser, dan sinkronisasi preferensi volume antar sesi.
- [x] **Laporan Ringkasan Sesi Sortir (`SessionSummaryDialog` / `Ctrl+Shift+R`):** Dialog statistik komprehensif bergaya Studio Slate yang merangkum total file, jumlah terpindah per slot, sisa file, dan media bertanda bookmark, lengkap dengan fitur salin ke clipboard dan ekspor ke file teks.
- [x] **Penyempurnaan Ergonomi & Interaksi UX (Redundan Ikon, Smart Import, Badge Slot, Context Menu, & Checkbox):** Menghapus duplikasi bintang tombol flag, klik stage kosong langsung memicu impor folder, penyederhanaan badge keycap `[1]`–`[9]` di pengaturan folder dengan tooltip interaktif, context menu klik kanan pada tombol folder (pilih folder cepat, buka di File Explorer, ubah nama), serta implementasi kontrol `StudioCheckBox` dengan kotak centang bergaris tegas dan tanda centang vektor yang jelas.

---

## 🚀 v2.2.0-Stable (Milestone Release — Selesai)
- [x] **Complete Zero-Lock Multimedia & Video Engine:** Pemutaran video (`.mp4`, `.webm`, `.mkv`, `.mov`, `.avi`, `.m4v`, `.wmv`) dengan sinkronisasi audio, HUD melayang hemat ruang, dan pelepasan handle file tanpa kunci di Windows.
- [x] **Smart Filter Terstruktur & Kolom Pencarian Real-Time (`Ctrl+F`):** Filter berkategori bersih dengan pemisah visual, deteksi ekstensi aktif dinamis, badge jumlah file real-time, dan kolom pencarian instan nama file.
- [x] **Arsitektur Super Cepat & Penghematan RAM 60%:** Pemindahan file secepat kilat (`os.replace`), prefetch santai 40ms saat idle, batas cache 24 entri 1.25x DPI, dan pengurutan natural ter-cache.
- [x] **Navigasi Tombol Tahan Interaktif & Rapid Move:** Auto-repeat pada tombol navigasi (`< Previous` / `> Next`) dan loop pemindahan instan saat tombol folder `[1]`–`[5]` ditahan.
- [x] **Thumbnail UP NEXT & Isolasi Playback Dialog Preview Penuh:** Pratinjau filmstrip mini dengan thumbnail ter-decode nyata dan isolasi ketat playback modal preview tanpa audio hantu.
- [x] **Sistem Desain Studio Slate & Registry 33 Format Terverifikasi:** Dokumentasi clean `README.md`, tangkapan layar privasi tinggi, dan tabel format resmi 33 ekstensi.

---

## 🔭 v2.3.x (Ide Pengembangan Masa Depan)
- [ ] **Multi-Select & Bulk Action:** Memilih beberapa file sekaligus dari filmstrip atau antrean untuk dipindahkan bersamaan.
- [ ] **Integrasi Tagging & Metadata EXIF Viewer:** Panel inspeksi metadata EXIF/kamera mendalam dan penyematan tag kustom.
