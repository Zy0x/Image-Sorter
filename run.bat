@echo off
setlocal
cd /d "%~dp0"

set "MAIN_SCRIPT=main.py"

:: 1. Pilih interpreter Python (.venv lokal jika ada, atau Python sistem)
set "PYTHON_EXE="
set "PYTHONW_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    if exist ".venv\Scripts\pythonw.exe" set "PYTHONW_EXE=.venv\Scripts\pythonw.exe"
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
        where pythonw >nul 2>nul
        if %errorlevel% equ 0 set "PYTHONW_EXE=pythonw"
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python tidak ditemukan di sistem Anda.
    echo Silakan instal Python 3.8+ dan pastikan sudah ditambahkan ke PATH.
    echo.
    pause
    exit /b 1
)

if not exist "%MAIN_SCRIPT%" (
    echo [ERROR] File %MAIN_SCRIPT% tidak ditemukan di direktori ini:
    echo   %CD%
    echo.
    pause
    exit /b 1
)

:: 2. Pastikan dependensi (PySide6 & requests) sudah terpasang
"%PYTHON_EXE%" -c "import PySide6, requests" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Menginstal dependensi yang diperlukan dari requirements.txt...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Gagal menginstal dependensi. Periksa koneksi internet atau instalasi pip Anda.
        echo.
        pause
        exit /b 1
    )
)

:: 3. Jalankan aplikasi
:: Gunakan "run.bat --debug" jika ingin melihat log terminal secara langsung.
if /i "%~1"=="--debug" (
    echo [INFO] Menjalankan Image Sorter dalam mode debug...
    "%PYTHON_EXE%" "%MAIN_SCRIPT%" %2 %3 %4
    if %errorlevel% neq 0 pause
    exit /b %errorlevel%
)

if not "%PYTHONW_EXE%"=="" (
    start "" "%PYTHONW_EXE%" "%MAIN_SCRIPT%" %*
    exit /b 0
) else (
    "%PYTHON_EXE%" "%MAIN_SCRIPT%" %*
    if %errorlevel% neq 0 pause
    exit /b %errorlevel%
)
