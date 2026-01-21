@echo off
REM ============================================
REM UtilityHQ - Windows Build Script (Fast)
REM ============================================

echo.
echo ========================================
echo   UtilityHQ - Quick Build
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Check if PyInstaller is installed, install if not
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/3] Installing PyInstaller...
    pip install pyinstaller
) else (
    echo [1/3] PyInstaller already installed
)

echo.
echo [2/3] Building executable...
echo.
python -m PyInstaller build.spec --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo [3/3] Setting up data folder...
if not exist "dist\UtilityHQ\data" mkdir "dist\UtilityHQ\data"
if exist "data\utilities.db" (
    copy "data\utilities.db" "dist\UtilityHQ\data\utilities.db" >nul
    echo      Database copied successfully.
) else (
    echo      No database found - app will create empty one.
)

echo.
echo ========================================
echo   SUCCESS!
echo ========================================
echo.
echo Your app is located at:
echo   dist\UtilityHQ\UtilityHQ.exe
echo.
echo Double-click the EXE to run!
echo.

pause
