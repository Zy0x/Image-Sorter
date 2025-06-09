@echo off
REM Hapus folder ImageSorter
rmdir /S /Q ImageSorter

REM Pindah file ImageSorter.exe dari folder Installer ke direktori utama
move installer\ImageSorter.exe .
REM Hapus folder Installer setelah memindahkan file
rmdir /S /Q installer

REM Buat folder baru bernama Source
mkdir Source

REM Pindahkan semua struktur folder dan file ke folder Source, kecuali ImageSorter.exe
move assets Source\
move config Source\
move output Source\
move utils Source\
move build.bat Source\
move ImageSorter.spec Source\
move installer.iss Source\
move main.py Source\
move README.md Source\
move requirements.txt Source\
move res_compiler.bat Source\
move cleaner.bat Source\