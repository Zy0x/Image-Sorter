@echo off
setlocal

:: Important variables
set "SPEC_NAME=ImageSorter"
set "MAIN_SCRIPT=main.py"
set "UTILS_DIR=utils"
set "RESOURCES_PY=%UTILS_DIR%\resources.py"
set "SPEC_FILE=%SPEC_NAME%.spec"
set "DIST_DIR=dist"
set "BUILD_DIR=build"
set "ICON_FILE=assets/icons/app_icon.ico"
set "OUTPUT_FOLDER=ImageSorter"

cls
echo #########################################################################
echo #                       IMAGE SORTER - BUILD SCRIPT                     #
echo #########################################################################
echo.

:: 1. Check if resources.py exists
if not exist "%RESOURCES_PY%" (
    echo [ERROR] File %RESOURCES_PY% not found!
    echo Please make sure you have run res_compiler.bat first.
    echo.
    pause
    exit /b 1
)

:: 2. Generate or use existing .spec file
if exist "%SPEC_FILE%" goto start_build

:generate_spec
echo [INFO] Generating new spec file with latest configuration...

:: Check if icon is available
if exist "%ICON_FILE%" (
    echo [INFO] Using application icon: %ICON_FILE%
    pyinstaller --name=%SPEC_NAME% --windowed --clean ^
        --icon="%ICON_FILE%" ^
        --add-data "%UTILS_DIR%;%UTILS_DIR%" ^
        --add-data "assets;assets" ^
        --add-data "config;config" ^
        --add-data "output;output" ^
        --add-data "utils;utils" ^
        "%MAIN_SCRIPT%"
) else (
    echo [WARNING] File %ICON_FILE% not found. Building without custom icon.
    pyinstaller --name=%SPEC_NAME% --windowed --clean ^
        --add-data "%UTILS_DIR%;%UTILS_DIR%" ^
        --add-data "assets;assets" ^
        --add-data "config;config" ^
        --add-data "output;output" ^
        --add-data "utils;utils" ^
        "%MAIN_SCRIPT%"
)

:start_build
echo.
echo [INFO] Starting build process using %SPEC_FILE%...

:: Run PyInstaller using the .spec file
pyinstaller --noconfirm "%SPEC_FILE%"

:: Remove existing ImageSorter folder silently
if exist "%OUTPUT_FOLDER%" rmdir /s /q "%OUTPUT_FOLDER%"
mkdir "%OUTPUT_FOLDER%"

:: Move executable and dependencies into ImageSorter folder
echo [INFO] Moving files into folder: %OUTPUT_FOLDER%...
xcopy /e /i "%DIST_DIR%\%SPEC_NAME%" "%OUTPUT_FOLDER%" >nul

:: Move specific folders/files from _internal to root of ImageSorter
echo [INFO] Moving files from _internal to root of ImageSorter...
move /Y "%OUTPUT_FOLDER%\_internal\assets" "%OUTPUT_FOLDER%\assets" >nul 2>nul
move /Y "%OUTPUT_FOLDER%\_internal\config" "%OUTPUT_FOLDER%\config" >nul 2>nul
move /Y "%OUTPUT_FOLDER%\_internal\output" "%OUTPUT_FOLDER%\output" >nul 2>nul
move /Y "%OUTPUT_FOLDER%\_internal\utils" "%OUTPUT_FOLDER%\utils" >nul 2>nul
move /Y "%OUTPUT_FOLDER%\_internal\resources.py" "%OUTPUT_FOLDER%" >nul 2>nul

:: Copy additional files to ImageSorter folder
echo [INFO] Adding README.md and requirements.txt to ImageSorter folder...
if exist "README.md" copy /Y "README.md" "%OUTPUT_FOLDER%" >nul
if exist "requirements.txt" copy /Y "requirements.txt" "%OUTPUT_FOLDER%" >nul

:: Cleaning up temporary folders
echo [INFO] Cleaning up temporary build directories...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

echo.
echo #########################################################################
echo #                          BUILD SUCCESSFUL!                           #
echo #########################################################################
echo.
echo Build completed successfully!
echo Output can be found in the following directory:
echo   .\%OUTPUT_FOLDER%\
echo.
pause
exit /b 0