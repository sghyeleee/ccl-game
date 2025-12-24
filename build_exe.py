"""
EXE 빌드 스크립트
PyInstaller를 사용하여 main_game.py를 EXE 파일로 빌드합니다.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    # 현재 스크립트의 디렉토리로 이동
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # PyInstaller 설치 확인
    try:
        import PyInstaller
        print("PyInstaller가 이미 설치되어 있습니다.")
    except ImportError:
        print("PyInstaller를 설치하는 중...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("PyInstaller 설치 완료!")
    
    # PyInstaller 명령어 구성
    # Windows에서는 세미콜론(;)을 경로 구분자로 사용
    assets_path = f"assets{os.pathsep}assets"
    flappy_score = f".flappy_best_score{os.pathsep}."
    sugar_score = f".sugar_best_score{os.pathsep}."
    
    cmd = [
        "pyinstaller",
        "--name=더부리부리파티",
        "--onefile",  # 단일 EXE 파일로 생성
        "--windowed",  # 콘솔 창 숨기기
        f"--add-data={assets_path}",  # assets 폴더 포함
        f"--add-data={flappy_score}",  # 점수 파일 포함
        f"--add-data={sugar_score}",  # 점수 파일 포함
        "--clean",  # 빌드 전 캐시 정리
        "main_game.py"
    ]
    
    print("EXE 빌드를 시작합니다...")
    print(f"명령어: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\n빌드 완료!")
        print(f"EXE 파일 위치: {script_dir / 'dist' / '더부리부리파티.exe'}")
    except subprocess.CalledProcessError as e:
        print(f"\n빌드 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

