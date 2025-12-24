@echo off
chcp 65001 >nul
echo ========================================
echo Building EXE file...
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python is not installed.
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

echo Python found: %PYTHON_CMD%
echo.

REM Install PyInstaller if needed
echo Checking PyInstaller...
%PYTHON_CMD% -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    %PYTHON_CMD% -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)
echo.

REM Build
echo ========================================
echo Starting build...
echo ========================================
echo.

%PYTHON_CMD% -m PyInstaller 더부리부리파티.spec

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo Build complete!
    echo ========================================
    echo EXE file location: dist\더부리부리파티.exe
    echo.
) else (
    echo.
    echo ========================================
    echo Build failed!
    echo ========================================
    echo.
)

pause

