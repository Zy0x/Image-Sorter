@echo off
:: Navigate to the utils folder
cd /d "%~dp0%utils"

:: Check if resources.py exists and delete it if present
if exist resources.py (
    echo [INFO] Deleting existing resources.py...
    del /f /q resources.py >nul 2>nul
    if exist resources.py (
        echo.
        echo [ERROR] Failed to delete resources.py. Ensure the file is not open or locked.
        echo.
        pause
        exit /b 1
    )
)

:: Verify if pyside6-rcc is available
where pyside6-rcc >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] pyside6-rcc not found.
    echo Please ensure PySide6 is installed and added to your PATH.
    echo Run: pip install PySide6
    echo.
    pause
    exit /b 1
)

:: Compile resources.qrc into resources.py
echo.
echo [INFO] Compiling resources.qrc into resources.py...
echo.

pyside6-rcc resources.qrc -o resources.py

:: Check if compilation was successful
if exist resources.py (
    echo [SUCCESS] Compilation completed successfully. resources.py has been created.
) else (
    echo [ERROR] Compilation failed. resources.py was not generated.
    echo Please check the contents of resources.qrc and ensure there are no formatting errors.
)

echo.
pause