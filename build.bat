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
    echo Please make sure you have run resources_compiler.bat first.
    echo.
    pause
    exit /b 1
)

:: 2. Create .spec file if it doesn't exist or user wants automatic build
if not exist "%SPEC_FILE%" goto generate_spec

:: 3. Ask user whether to use default configuration
echo.
echo Do you want to use the default build configuration?
echo [1] Yes - Continue with automatic build
echo [2] No - I will edit the %SPEC_FILE% manually
echo.
choice /c 12 /n /m "Select option (1/2): "
if errorlevel 2 goto edit_spec
if errorlevel 1 goto start_build

:generate_spec
echo [INFO] Regenerating spec file with latest configuration...

:: Check if icon is available
if exist "%ICON_FILE%" (
    echo [INFO] Using application icon: %ICON_FILE%
    pyinstaller --name=%SPEC_NAME% --onefile --windowed ^
        --icon="%ICON_FILE%" ^
        --add-data "%UTILS_DIR%;utils" ^
        --add-data "assets;assets" ^
        --add-data "output;output" ^
        --add-data "config;config" ^
        "%MAIN_SCRIPT%"
    echo Moving files out of _internal folder...
    cd dist\ImageSorter
    if exist _internal (
        for %%F in (_internal\*) do (
            move "%%F" .
        )
        rd _internal
    )
) else (
    echo [WARNING] File %ICON_FILE% not found. Building without custom icon.
    pyinstaller --name=%SPEC_NAME% --onefile --windowed ^
        --add-data "%UTILS_DIR%;utils" ^
        --add-data "assets;assets" ^
        --add-data "output;output" ^
        --add-data "config;config" ^
        "%MAIN_SCRIPT%"
)
goto start_build

:edit_spec
echo.
echo [INFO] Please edit the file %SPEC_FILE% as needed.
echo After finishing, rerun this script to continue building.
echo.
pause
exit /b 0

:start_build
echo.
echo [INFO] Starting build process using %SPEC_FILE%...

:: 4. Run PyInstaller using the .spec file
pyinstaller "%SPEC_FILE%"

:: 5. Check if the build was successful
if not exist "%DIST_DIR%\%SPEC_NAME%.exe" (
    echo [ERROR] Build failed. Executable file not found.
    echo Please review the %SPEC_FILE% and ensure there are no errors.
    echo.
    pause
    exit /b 1
)

:: 6. Move executable to main directory
echo.
echo [INFO] Moving application to main directory...
copy /y "%DIST_DIR%\%SPEC_NAME%.exe" ".\%SPEC_NAME%.exe" >nul

:: 7. Remove temporary folders
echo [INFO] Cleaning up temporary build directories...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

echo.
echo #########################################################################
echo #                          BUILD SUCCESSFUL!                           #
echo #########################################################################
echo.
echo The executable file has been moved to:
echo   .\%SPEC_NAME%.exe
echo.
pause
exit /b 0