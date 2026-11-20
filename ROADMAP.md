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

## 🔭 v2.2.x (Ide Pengembangan Masa Depan)
- [ ] **Pengurutan Antrean Fleksibel (*Sort By*: Tanggal, Ukuran, Resolusi)**
- [ ] **Batch Rename & Tagging:** Mengganti nama file berdasarkan pola tanggal/urutan saat disortir.
