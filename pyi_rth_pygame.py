"""
PyInstaller 런타임 훅: pygame 오류를 파일로 저장
"""
import sys
import traceback
from pathlib import Path

def handle_exception(exc_type, exc_value, exc_traceback):
    """예외 발생 시 파일로 저장하고 콘솔에 출력"""
    if exc_type is KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_log = Path(__file__).parent / "error_log.txt"
    with open(error_log, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("오류 발생!\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"오류 타입: {exc_type.__name__}\n")
        f.write(f"오류 메시지: {exc_value}\n\n")
        f.write("전체 트레이스백:\n")
        f.write("-" * 60 + "\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        f.write("\n" + "=" * 60 + "\n")
    
    # 콘솔에도 출력
    print("\n" + "=" * 60)
    print("오류가 발생했습니다!")
    print("=" * 60)
    print(f"오류 타입: {exc_type.__name__}")
    print(f"오류 메시지: {exc_value}")
    print("\n전체 트레이스백:")
    print("-" * 60)
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("\n" + "=" * 60)
    print(f"\n오류 로그가 저장되었습니다: {error_log}")
    print("\n아무 키나 누르면 종료됩니다...")
    try:
        input()
    except:
        pass

# 전역 예외 핸들러 설정
sys.excepthook = handle_exception



