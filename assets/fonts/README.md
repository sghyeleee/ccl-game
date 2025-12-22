# 폰트 넣는 방법 (NeoDGM / 갈무리 등)

이 프로젝트는 `pygame.font.Font()`로 폰트를 불러옵니다.

## 1) 폰트 파일 준비
- `.ttf` 또는 `.otf` 폰트 파일을 준비합니다.

## 2) 이 폴더에 복사
이 폴더(`assets/fonts/`)에 폰트 파일을 복사합니다.

권장 파일명(코드에서 자동 인식, 위에 있을수록 우선 적용):
- `neodgm.ttf` (현재 기본 우선순위)
- `Galmuri11.ttf`
- `Galmuri11-Bold.ttf`
- `Galmuri14.ttf`
- `Galmuri14-Bold.ttf`
- `Galmuri.ttf`

다른 이름으로 넣어도 되지만, 그 경우 `main_game.py`의 `PREFERRED_FONT_FILES` 목록에 파일명을 추가해야 합니다.

## 3) 적용 확인
런처 실행:
- macOS: `python3 main_game.py`
- Windows: `python main_game.py`

## 참고
- 폰트 라이선스에 따라 배포 시 저작권/라이선스 문구가 필요할 수 있어요.


