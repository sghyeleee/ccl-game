"""
PyInstaller 빌드 환경에서도 올바른 경로를 반환하는 유틸리티
"""
import sys
from pathlib import Path


def get_base_path() -> Path:
    """
    스크립트의 기본 경로를 반환합니다.
    PyInstaller로 빌드된 경우 sys._MEIPASS를 사용하고,
    그렇지 않으면 __file__의 부모 디렉토리를 사용합니다.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 경우
        return Path(sys._MEIPASS)
    else:
        # 일반 Python 스크립트로 실행되는 경우
        # 이 파일의 위치를 기준으로 프로젝트 루트를 찾습니다
        return Path(__file__).resolve().parent

