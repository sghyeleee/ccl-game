@echo off
setlocal enabledelayedexpansion

REM ==========================================
REM  Windows EXE build script (PyInstaller)
REM  - Outputs to: dist\BuriBuriParty.exe
REM  - Includes assets/ 폴더 전체를 exe에 포함
REM ==========================================

cd /d "%~dp0..\.."

echo [1/4] Python check...
python --version
if errorlevel 1 (
  echo Python이 설치되어 있지 않거나 PATH에 없습니다.
  echo 해결: Python 설치 후 "Add Python to PATH" 체크.
  exit /b 1
)

echo [2/4] Install deps...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt

echo [3/4] Clean previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] Build exe...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name BuriBuriParty ^
  --add-data "assets;assets" ^
  main_game.py

if errorlevel 1 (
  echo 빌드 실패. 위 에러 로그를 확인해주세요.
  exit /b 1
)

echo.
echo DONE: dist\BuriBuriParty.exe 생성 완료
echo.
pause


