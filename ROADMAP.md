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

## 🔭 v2.2.x (Ide Pengembangan Masa Depan)
- [ ] **Custom Jumlah Slot Folder Dinamis (3–10 Folder):** Menambah atau mengurangi jumlah tombol folder tujuan sesuai kebutuhan proyek.
- [ ] **Deteksi Gambar Duplikat / Mirip (Perceptual Hash):** Menandai foto kembar dalam satu folder sebelum disortir.
- [ ] **Batch Rename & Tagging:** Mengganti nama file berdasarkan pola tanggal/urutan saat disortir.
