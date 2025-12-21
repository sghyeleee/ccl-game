# 윈도우(PC)에서 `main_game.py` 실행 가이드 (기획자용)

이 폴더는 “더 부리부리 파티” 런처(`main_game.py`)와 미니게임들이 들어있는 **파이썬(Python) 프로젝트**입니다.  
아래 순서대로 하면 **윈도우 PC에서 실행**할 수 있어요.

---

## 1) 준비물 (딱 2개)

- **Python 설치**: Windows용 Python 3.x (권장: 3.10 이상)
- **pygame 설치**: 게임 화면을 띄우는 라이브러리

---

## 2) 한 번만 하면 되는 설치

### 2-1. Python 설치

1. Windows에서 브라우저를 열고 “Python 다운로드”를 검색해 **Python 3**를 설치합니다.
2. 설치 화면에서 **“Add Python to PATH”**(파이썬을 PATH에 추가) 옵션이 있으면 **반드시 체크**하고 설치합니다.

### 2-2. pygame 설치

1. 키보드에서 **Windows 키**를 누르고 `cmd`를 입력해서 **명령 프롬프트**를 엽니다.
2. 아래를 그대로 입력하고 Enter:

```bash
pip install pygame
```

---

## 3) 실행 방법 (매번 여기만 하면 됨)

1. 이 프로젝트 폴더(`ccl-game`)를 엽니다.
2. 폴더 빈 공간에서 **Shift + 마우스 우클릭** → “여기서 PowerShell 창 열기”(또는 터미널 열기)를 선택합니다.
3. 아래를 그대로 입력하고 Enter:

```bash
python main_game.py
```

실행되면 런처 화면이 뜨고, 메뉴에서 미니게임을 선택해 플레이할 수 있습니다.

---

## 4) 자주 생기는 문제 해결

### “python을 찾을 수 없습니다 / python이 명령이 아닙니다”
- Python 설치할 때 **Add Python to PATH**가 체크되지 않은 경우가 많습니다.
- 해결:
  - Python을 다시 설치하면서 **Add Python to PATH**를 체크하거나,
  - 아래 명령으로도 시도해보세요:

```bash
py main_game.py
```

### “pip이 명령이 아닙니다”
- 아래로 설치를 시도해보세요:

```bash
py -m pip install pygame
```

### 실행했는데 이미지가 없다고 나옵니다 (Missing asset)
- `assets/` 폴더가 프로젝트 안에 있어야 합니다.
- 해결:
  - `main_game.py`와 `assets/`가 **같은 폴더**에 있는지 확인하고,
  - 반드시 **프로젝트 폴더 안에서**(ccl-game 폴더에서) 실행하세요.

---

## 5) 기획자용 “한 줄 요약”

- 처음 한 번: `pip install pygame`
- 매번 실행: `python main_game.py`


