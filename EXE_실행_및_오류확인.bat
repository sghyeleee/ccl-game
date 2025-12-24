@echo off
chcp 65001 >nul
echo ========================================
echo 더 부리부리 파티 실행 및 오류 확인
echo ========================================
echo.

if not exist "dist\더부리부리파티.exe" (
    echo [오류] EXE 파일을 찾을 수 없습니다!
    echo 먼저 빌드.bat를 실행해서 EXE 파일을 생성하세요.
    echo.
    pause
    exit /b 1
)

echo EXE 파일을 실행합니다...
echo 오류가 발생하면 이 창에 표시됩니다.
echo.
echo ========================================
echo.

cd dist
더부리부리파티.exe

echo.
echo ========================================
echo 프로그램이 종료되었습니다.
echo ========================================
echo.

if exist "error_log.txt" (
    echo 오류 로그 파일이 생성되었습니다!
    echo 내용을 확인하시겠습니까? (Y/N)
    set /p choice=
    if /i "%choice%"=="Y" (
        type error_log.txt
    )
    echo.
)

pause



