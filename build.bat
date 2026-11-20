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

:: 2. If .spec already exists, ask whether to use it or rebuild cleanly
if not exist "%SPEC_FILE%" goto generate_and_build

echo.
echo Found existing %SPEC_FILE%:
echo [1] Build with default configuration (regenerate spec ^& build)
echo [2] Build using existing %SPEC_FILE% as-is
echo [3] Exit so I can edit %SPEC_FILE% manually
echo.
choice /c 123 /n /m "Select option (1/2/3): "
if errorlevel 3 goto edit_spec
if errorlevel 2 goto build_from_spec
if errorlevel 1 goto generate_and_build

:generate_and_build
echo [INFO] Building executable with latest configuration...
:: Note: 'config' directory is intentionally NOT bundled so personal logs/settings are never embedded in the executable.
if exist "%ICON_FILE%" (
    echo [INFO] Using application icon: %ICON_FILE%
    pyinstaller --noconfirm --clean --name=%SPEC_NAME% --onefile --windowed ^
        --icon="%ICON_FILE%" ^
        --add-data "%UTILS_DIR%;utils" ^
        --add-data "assets;assets" ^
        "%MAIN_SCRIPT%"
) else (
    echo [WARNING] File %ICON_FILE% not found. Building without custom icon.
    pyinstaller --noconfirm --clean --name=%SPEC_NAME% --onefile --windowed ^
        --add-data "%UTILS_DIR%;utils" ^
        --add-data "assets;assets" ^
        "%MAIN_SCRIPT%"
)
goto check_output

:build_from_spec
echo.
echo [INFO] Starting build process using %SPEC_FILE%...
pyinstaller --noconfirm --clean "%SPEC_FILE%"
goto check_output

:edit_spec
echo.
echo [INFO] Please edit the file %SPEC_FILE% as needed.
echo After finishing, rerun this script to continue building.
echo.
pause
exit /b 0

:check_output
if not exist "%DIST_DIR%\%SPEC_NAME%.exe" (
    echo [ERROR] Build failed. Executable file not found.
    echo Please review the %SPEC_FILE% and ensure there are no errors.
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Moving application to main directory...
copy /y "%DIST_DIR%\%SPEC_NAME%.exe" ".\%SPEC_NAME%.exe" >nul

echo [INFO] Cleaning up temporary build directories...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

echo.
echo #########################################################################
echo #                          BUILD SUCCESSFUL!                            #
echo #########################################################################
echo.
echo The executable file has been moved to:
echo   .\%SPEC_NAME%.exe
echo.
pause
exit /b 0
