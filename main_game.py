from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

import pygame

from snake_survival import run_game as run_snake
from sugar_game import run_game as run_sugar_game
from flappy_bird import run_game as run_flappy_bird

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 540
TITLE_BAR_HEIGHT = 64
TITLE_BG = (8, 8, 8)
TITLE_TEXT = (255, 255, 255)
MAIN_BG = (245, 245, 247)
CARD_BG = (186, 186, 195)
CARD_BG_HOVER = (150, 150, 164)
STORY_BG = (18, 18, 26)
CHARACTER_BG = (222, 222, 235)
CHARACTER_BORDER = (52, 52, 82)
ACCENT = (0, 0, 0)
INACTIVE_TEXT = (130, 130, 142)
STATUS_COLOR = (238, 94, 42)
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "main_game"
TITLE_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "new" / "01.title"
STORY_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "new" / "02.story"
MAIN_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "new" / "03.main"
MP3_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "mp3"
BGM_FILE = MP3_ASSET_DIR / "puzzle-game-bright-casual-video-game-music-249202.mp3"
GAME_BGM_FILE = MP3_ASSET_DIR / "retro-game-arcade-236133.mp3"
SFX_FILE = MP3_ASSET_DIR / "happy-pop-2-185287.mp3"
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
VERSION_FILE = Path(__file__).resolve().parent / "VERSION"

STORY_INTERVAL_MS = 3000
STORY_EXTRA_HOLD_MS = 1500
STORY_TYPING_CHARS_PER_SEC = 32
MENU_FONT_NAME = "pretendard"
FONT_CANDIDATES = [
    "Pretendard",
    "Apple SD Gothic Neo",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Arial Unicode MS",
]
PREFERRED_FONT_FILES = (
    # 프로젝트에 포함된 폰트를 최우선으로 사용합니다.
    # 현재 적용: Neo둥근모(NeoDGM)
    "neodgm.ttf",
    # 갈무리(Galmuri) 폰트를 쓰고 싶으면 아래 파일 중 하나(또는 여러 개)를 assets/fonts/에 넣어주세요.
    # (파일명은 자유롭게 바꿀 수 있지만, 그 경우 이 리스트에도 추가해야 합니다.)
    "Galmuri11.ttf",
    "Galmuri11-Bold.ttf",
    "Galmuri14.ttf",
    "Galmuri14-Bold.ttf",
    "Galmuri.ttf",
)

GameStartFn = Callable[[], None]

DEFAULT_APP_VERSION = "0.0.0-dev"


def _read_app_version() -> str:
    """프로젝트 루트의 VERSION 파일에서 배포 버전을 읽는다."""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return DEFAULT_APP_VERSION
    if not text:
        return DEFAULT_APP_VERSION
    return text


@dataclass
class GameEntry:
    """게임 카드에 노출할 각 미니게임의 메타데이터."""

    title: str
    description: str
    start_fn: GameStartFn


@dataclass
class CharacterOption:
    """유저가 선택할 수 있는 캐릭터 정보."""

    code: str
    display_name: str
    color: Tuple[int, int, int]


def _get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """환경에 설치된 한글 지원 폰트를 찾아 반환한다."""
    # 1) 프로젝트에 포함된 폰트 파일(갈무리 등)을 최우선 사용
    preferred_paths: list[Path] = []
    for filename in PREFERRED_FONT_FILES:
        path = FONT_DIR / filename
        if path.exists():
            preferred_paths.append(path)
    if preferred_paths:
        if bold:
            bold_path = next((p for p in preferred_paths if "Bold" in p.stem), None)
            if bold_path is not None:
                return pygame.font.Font(bold_path.as_posix(), size)
        return pygame.font.Font(preferred_paths[0].as_posix(), size)

    # 2) 시스템에 설치된 폰트(갈무리 포함 가능) 시도
    galmuri_system = pygame.font.match_font("Galmuri", bold=bold)
    if galmuri_system:
        return pygame.font.Font(galmuri_system, size)

    # 3) 기존 폰트 후보 폴백
    for name in FONT_CANDIDATES:
        font_path = pygame.font.match_font(name, bold=bold)
        if font_path:
            return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(None, size, bold=bold)


def _load_image(name: str, base_dir: Path = ASSET_DIR) -> pygame.Surface:
    """지정된 자산 이미지를 RGBA 형태로 불러온다."""
    path = base_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return pygame.image.load(path.as_posix()).convert_alpha()


def get_game_entries() -> List[GameEntry]:
    """런처에서 노출할 미니게임 목록을 반환한다."""
    # 아이콘 매핑(요청 사항)
    # - assets/new/03.main/game1_icon_buffet_140_140.png => Flappy Bird
    # - assets/new/03.main/game2_icon_140_140.png        => Sugar Game
    # - assets/new/03.main/game3_icon_140_140.png        => Snake Survival
    return [
        GameEntry(
            "날아부리",
            "뱀을 요리조리 피해서\n날아가버린 샌드위치를\n쫓아가자!!",
            lambda: run_flappy_bird(quit_on_exit=False),
        ),
        GameEntry(
            "쌓아부리",
            "내가 쌓은 만큼 꽁짜로\n햄버거를 먹을 수 있다고?\n최대한 높게 쌓아보자!",
            lambda: run_sugar_game(quit_on_exit=False),
        ),
        GameEntry(
            "모아부리",
            "꽁짜 햄버거에 정신 못\n차리는 친구들을 모아서\n구출하자!",
            lambda: run_snake(quit_on_exit=False),
        ),
    ]


class BuriBuriPartyApp:
    """인트로 → 스토리 → 캐릭터 → 메인 허브 플로우를 담당하는 컨트롤러."""

    def __init__(self) -> None:
        """pygame 초기화와 상태 기본값을 세팅한다."""
        self.games = get_game_entries()
        self.game_page = 0
        self.games_per_page = 4
        self.hovered_card_idx: Optional[int] = None

        # NOTE: 설정 메뉴는 아직 제공 기능이 없어서 임시로 숨김(주석처리)
        self.menu_items = ["게임 시작하기", "종료"]
        self.menu_index = 0
        self.state = "title"
        self.running = True
        self.has_started = False
        # 스토리(텍스트) 상태
        self.story_start_ms: Optional[int] = None
        self.story_scene_index = 0
        self.story_char_index = 0
        self.story_char_accum = 0.0
        self.story_scenes = [
            "서기 2521년....\n"
            "지구와 97억광년 떨어져있는 부리부리 행성은 넘쳐나는 식재료에 비해\n식문화가 발전하지 못해 굶주려있다.......\n\n"
            "신하: 전하~~~ 부디.. 부디 식문화에 힘써주시옵소서...\n"
            "왕: 흐음.. 먼저 갔던 요원들은 왜 하나도 돌아 오질 않는 건지....",
            "왕: 거기 있는 너!!! 말차부리!!!!! 지구라는 곳에 가서 식문화를 조사하고 오거라..\n"
            "말차부리: 네? 저요?\n\n"
            "그렇게 말차부리는 지구에 있는 대한민국으로 식문화를 조사하는 임무를 떠난다...",
        ]

        self.character_options = [
            CharacterOption("A", "Pang", (255, 163, 163)),
            CharacterOption("B", "Dori", (166, 209, 255)),
            CharacterOption("C", "Nimo", (255, 220, 164)),
            CharacterOption("D", "Ning", (190, 247, 190)),
        ]
        self.selected_character_idx = 0
        self.hovered_character_idx: Optional[int] = None
        self.current_character: Optional[CharacterOption] = None

        self.status_message: Optional[str] = None
        self.status_until_ms = 0

        # 닉네임 입력 관련 상태
        self.nickname: str = ""
        self.nickname_input: str = ""  # 확정된 텍스트
        self.nickname_composing: str = ""  # 조합 중인 텍스트 (한글 IME)
        self.nickname_confirmed: bool = False
        self.nickname_input_focused: bool = False
        self._nickname_input_box_rect: Optional[pygame.Rect] = None
        self._nickname_confirm_btn_rect: Optional[pygame.Rect] = None

        self.assets: dict[str, pygame.Surface] = {}
        self._button_cache: dict[tuple[int, int, bool], pygame.Surface] = {}
        self._title_menu_button_rects: list[pygame.Rect] = []
        self.app_version = _read_app_version()
        self._bgm_started = False
        self._bgm_current: Optional[Path] = None
        self._sfx_move: Optional[pygame.mixer.Sound] = None

        self._init_pygame()

    def _init_sfx(self) -> None:
        """짧은 UI 효과음을 로드한다(실패해도 게임은 계속 실행)."""
        if self._sfx_move is not None:
            return
        if not SFX_FILE.exists():
            self._sfx_move = None
            return
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            sfx = pygame.mixer.Sound(SFX_FILE.as_posix())
            sfx.set_volume(0.55)
            self._sfx_move = sfx
        except Exception:
            self._sfx_move = None

    def _play_ui_move_sfx(self) -> None:
        if self._sfx_move is None:
            return
        try:
            self._sfx_move.play()
        except Exception:
            return

    def _play_bgm(self, path: Path, *, volume: float = 0.35) -> None:
        """지정된 mp3를 루프 재생한다(동일 트랙이면 재호출해도 무시)."""
        if not path.exists():
            return
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            # 같은 트랙이 이미 재생 중이면 스킵
            if self._bgm_current == path and pygame.mixer.music.get_busy():
                self._bgm_started = True
                return
            pygame.mixer.music.load(path.as_posix())
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(-1)  # loop
            self._bgm_started = True
            self._bgm_current = path
        except Exception:
            # 오디오 장치/코덱 문제 등으로 실패할 수 있으니 무시(폴백)
            self._bgm_started = False

    def _init_bgm(self) -> None:
        """BGM을 1회만 초기화/재생한다(실패해도 게임은 계속 실행)."""
        if self._bgm_started:
            return
        self._play_bgm(BGM_FILE, volume=0.35)

    def _init_pygame(self) -> None:
        """pygame 디스플레이와 폰트를 재구성한다."""
        pygame.init()
        self._init_bgm()
        self._init_sfx()
        pygame.display.set_caption("the buriburi party")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_large = _get_font(58, bold=True)
        self.font_medium = _get_font(32, bold=True)
        # 타이틀 메뉴 버튼 텍스트는 조금 더 작게
        self.font_menu = _get_font(28, bold=True)
        self.font_small = _get_font(22)
        self.font_micro = _get_font(18)
        self.assets = self._load_assets()

    def _load_assets(self) -> dict[str, pygame.Surface]:
        """런처에서 사용하는 모든 스킨 이미지를 불러온다."""
        files = {
            "title_bar": "main_title_bar.png",
            "menu_idle": "menu_button_idle.png",
            "menu_hover": "menu_button_hover.png",
            "story_card": "story_card.png",
            "skip_idle": "skip_button_idle.png",
            "skip_hover": "skip_button_hover.png",
            "character_card_base": "character_card_base.png",
            "character_card_border": "character_card_selected_border.png",
            "character_speech": "character_panel_speech_bubble.png",
            "character_box": "character_panel_box.png",
            "game_card_idle": "game_card_idle.png",
            "game_card_hover": "game_card_hover.png",
            "options_background": "options_background.png",
        }
        assets = {key: _load_image(filename) for key, filename in files.items()}
        # Title(메인) 화면 스킨
        assets["title_background"] = _load_image("title_background_800_540.png", base_dir=TITLE_ASSET_DIR)
        # 로고는 작은 버전이 타이틀 상단 배치에 적합해서 기본으로 사용한다.
        assets["title_logo"] = _load_image("logo_160_108.png", base_dir=TITLE_ASSET_DIR)
        # 버튼 UI 스킨(모든 버튼 요소 공통)
        assets["ui_button"] = _load_image("button.png", base_dir=STORY_ASSET_DIR)
        # 게임 선택(메인) 아이콘/디폴트 캐릭터
        assets["char_default"] = _load_image("char_default_140_140.png", base_dir=MAIN_ASSET_DIR)
        assets["icon_flappy"] = _load_image("game2_icon_140_140.png", base_dir=MAIN_ASSET_DIR)
        assets["icon_sugar"] = _load_image("game1_icon_buffet_140_140.png", base_dir=MAIN_ASSET_DIR)
        assets["icon_snake"] = _load_image("game3_icon_140_140.png", base_dir=MAIN_ASSET_DIR)
        return assets

    def _get_ui_button(self, size: Tuple[int, int], hovered: bool) -> pygame.Surface:
        """공통 버튼 이미지를 사이즈/호버 상태에 맞게 캐싱해 반환한다."""
        w, h = size
        key = (w, h, hovered)
        cached = self._button_cache.get(key)
        if cached:
            return cached

        base = self.assets.get("ui_button")
        if not base:
            # 안전장치: 버튼 이미지가 없으면 기존 스킨으로 폴백
            fallback = self.assets["menu_hover"] if hovered else self.assets["menu_idle"]
            self._button_cache[key] = fallback
            return fallback

        # 호버 시 과도하게 커지면 레이아웃이 밀리므로 확대는 최소화한다.
        scale = 1.02 if hovered else 1.0
        target_w = max(1, int(w * scale))
        target_h = max(1, int(h * scale))
        surface = pygame.transform.smoothscale(base, (target_w, target_h))
        if hovered:
            surface = surface.copy()
            surface.set_alpha(245)
        self._button_cache[key] = surface
        return surface

    def run(self) -> None:
        """메인 루프를 돌면서 상태 머신을 갱신한다."""
        while self.running:
            delta_ms = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self._handle_event(event)

            if not self.running or not pygame.display.get_init() or pygame.display.get_surface() is None:
                break

            self._update(delta_ms)
            self._draw()
            pygame.display.flip()

        pygame.quit()

    def _handle_event(self, event: pygame.event.Event) -> None:
        """현재 상태에 맞춰 입력 이벤트를 분기 처리한다."""
        if self.state == "title":
            self._handle_title_event(event)
        elif self.state == "story":
            self._handle_story_event(event)
        elif self.state == "nickname":
            self._handle_nickname_event(event)
        elif self.state == "characters":
            self._handle_character_event(event)
        elif self.state == "hub":
            self._handle_hub_event(event)
        elif self.state == "options":
            self._handle_options_event(event)

    def _handle_title_event(self, event: pygame.event.Event) -> None:
        """타이틀 메뉴에서의 키 입력을 처리한다."""
        if event.type == pygame.KEYDOWN:
            prev = self.menu_index
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._trigger_menu_action()
            elif event.key == pygame.K_ESCAPE:
                self.running = False
            if self.menu_index != prev:
                self._play_ui_move_sfx()
            return

        # 마우스로도 메뉴 선택/실행 가능하도록 처리
        if event.type == pygame.MOUSEMOTION:
            hovered = self._hit_test_title_menu(event.pos)
            if hovered is not None:
                if hovered != self.menu_index:
                    self.menu_index = hovered
                    self._play_ui_move_sfx()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hovered = self._hit_test_title_menu(event.pos)
            if hovered is not None:
                self.menu_index = hovered
                self._trigger_menu_action()

    def _hit_test_title_menu(self, pos: Tuple[int, int]) -> Optional[int]:
        """타이틀 메뉴 버튼 영역에서 마우스 위치에 해당하는 인덱스를 반환한다."""
        for idx, rect in enumerate(self._title_menu_button_rects):
            if rect.collidepoint(pos):
                return idx
        return None

    def _trigger_menu_action(self) -> None:
        """선택된 메뉴 항목에 맞는 액션을 수행한다."""
        current_item = self.menu_items[self.menu_index]
        if current_item == "게임 시작하기":
            self._start_game()
        elif current_item == "종료":
            self.running = False

    def _start_game(self) -> None:
        """'게임 시작하기' 선택 시: 닉네임이 등록되어 있으면 허브로, 없으면 스토리부터 시작한다."""
        if self.nickname_confirmed and self.nickname:
            self.state = "hub"
        else:
            self._start_new_play()

    def _start_new_play(self) -> None:
        """새로 플레이 흐름을 시작한다."""
        self.story_start_ms = pygame.time.get_ticks()
        self.story_scene_index = 0
        self.story_char_index = 0
        self.story_char_accum = 0.0
        self.current_character = None
        self.selected_character_idx = 0
        self.state = "story"

    def _continue_play(self) -> None:
        """이어하기 선택 시 적절한 단계로 이동한다."""
        # 캐릭터 선택 화면 제거 이후에는 허브로 바로 이동한다.
        self.state = "hub"

    def _handle_story_event(self, event: pygame.event.Event) -> None:
        """스토리(텍스트) 화면 입력을 처리한다.

        - 클릭/Enter 1회: 타이핑 중이면 즉시 전체 표시
        - 클릭/Enter 2회: 다음 씬으로 이동 (마지막 씬이면 캐릭터 선택으로 이동)
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._advance_story_on_confirm()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._advance_story_on_confirm()

    def _advance_story_on_confirm(self) -> None:
        """스토리에서 확인 입력(클릭/Enter) 시의 동작을 처리한다."""
        # 스토리 확인 입력(클릭/Enter) 시 효과음
        self._play_ui_move_sfx()
        scene = self.story_scenes[self.story_scene_index]
        if self.story_char_index < len(scene):
            self.story_char_index = len(scene)
            return
        # 이미 전체가 보인 상태면 다음 씬
        if self.story_scene_index < len(self.story_scenes) - 1:
            self.story_scene_index += 1
            self.story_char_index = 0
            self.story_char_accum = 0.0
            return
        # 스토리 끝 → 닉네임 입력 화면으로 이동
        self._enter_nickname_screen()

    def _go_to_character_select(self) -> None:
        """스토리 종료 후 캐릭터 선택으로 전환한다."""
        # 캐릭터 선택 화면은 더 이상 사용하지 않음(디폴트 캐릭터 고정)
        self.has_started = True
        self.state = "hub"
        self.story_start_ms = None

    def _handle_nickname_event(self, event: pygame.event.Event) -> None:
        """닉네임 입력 화면에서의 입력을 처리한다.
        
        한글 IME 처리 참고: 
        - https://fireing123.tistory.com/entry/pygame-입력-필드-만들기
        - https://github.com/fireing123/pygamefwk/blob/main/pygamefwk/objects/ui/inputfield.py
        """
        # 마우스 클릭: 입력창 또는 확인 버튼
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            # 입력창 클릭 시 포커스 활성화
            if self._nickname_input_box_rect and self._nickname_input_box_rect.collidepoint(pos):
                if not self.nickname_input_focused:
                    self.nickname_input_focused = True
                    pygame.key.start_text_input()
                    self._play_ui_move_sfx()
            # 확인 버튼 클릭
            elif self._nickname_confirm_btn_rect and self._nickname_confirm_btn_rect.collidepoint(pos):
                if (self.nickname_input + self.nickname_composing).strip():
                    self._confirm_nickname()
            else:
                # 다른 곳 클릭 시 포커스 해제
                if self.nickname_input_focused:
                    self.nickname_input_focused = False
                    pygame.key.stop_text_input()
            return

        # 텍스트 조합 중 (한글 IME - 자음/모음 조합 중)
        if event.type == pygame.TEXTEDITING:
            # 글자 제한 체크
            if len(self.nickname_input) < 8:
                self.nickname_composing = event.text
            else:
                # 제한 도달 시 IME 끄기
                pygame.key.stop_text_input()
            return

        # 텍스트 입력 확정 (한글 IME 지원)
        if event.type == pygame.TEXTINPUT:
            # 먼저 조합 텍스트 초기화
            self.nickname_composing = ""
            # 글자 제한 체크 후 삽입
            if len(self.nickname_input) < 8:
                self.nickname_input += event.text
                self._play_ui_move_sfx()
            return

        # 특수 키 처리 (KEYDOWN)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Enter: 닉네임 확정
                if (self.nickname_input + self.nickname_composing).strip():
                    self._confirm_nickname()
            elif event.key == pygame.K_BACKSPACE:
                # 조합 중일 때는 IME가 처리하도록 둠 (TEXTEDITING으로 업데이트됨)
                # 조합 중이 아닐 때만 확정된 텍스트에서 삭제
                if not self.nickname_composing:
                    if len(self.nickname_input) > 0:
                        self.nickname_input = self.nickname_input[:-1]
            elif event.key == pygame.K_ESCAPE:
                # ESC: 타이틀로 돌아가기
                pygame.key.stop_text_input()
                self.nickname_composing = ""
                self.state = "title"

    def _enter_nickname_screen(self) -> None:
        """닉네임 입력 화면으로 진입한다."""
        self.nickname_input = ""
        self.nickname_composing = ""
        self.nickname_input_focused = True
        pygame.key.start_text_input()  # IME 활성화
        self.state = "nickname"

    def _confirm_nickname(self) -> None:
        """닉네임을 확정하고 허브 화면으로 이동한다."""
        # 조합 중인 글자도 포함해서 저장
        self.nickname = (self.nickname_input + self.nickname_composing).strip()
        self.nickname_input = self.nickname  # 동기화
        self.nickname_composing = ""  # 조합 중인 텍스트 초기화
        self.nickname_confirmed = True
        self.has_started = True
        self._play_ui_move_sfx()
        pygame.key.stop_text_input()  # IME 비활성화
        self.state = "hub"

    def _handle_character_event(self, event: pygame.event.Event) -> None:
        """캐릭터 선택 화면 입력을 처리한다."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected_character_idx = (self.selected_character_idx - 1) % len(self.character_options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected_character_idx = (self.selected_character_idx + 1) % len(self.character_options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._confirm_character(self.selected_character_idx)
            elif event.key == pygame.K_ESCAPE:
                self.state = "title"
        elif event.type == pygame.MOUSEMOTION:
            self.hovered_character_idx = self._hit_test_character(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hovered = self._hit_test_character(event.pos)
            if hovered is not None:
                self._confirm_character(hovered)

    def _confirm_character(self, idx: int) -> None:
        """선택한 캐릭터를 확정하고 허브 화면으로 이동한다."""
        self.current_character = self.character_options[idx]
        self.selected_character_idx = idx
        self.state = "hub"

    def _handle_hub_event(self, event: pygame.event.Event) -> None:
        """메인 허브 화면에서의 입력을 처리한다."""
        total = min(len(self.games), 3)
        if event.type == pygame.KEYDOWN:
            prev = self.hovered_card_idx
            if event.key == pygame.K_ESCAPE:
                self.state = "title"
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                current = self.hovered_card_idx if self.hovered_card_idx is not None else 0
                self.hovered_card_idx = (current - 1) % max(total, 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                current = self.hovered_card_idx if self.hovered_card_idx is not None else 0
                self.hovered_card_idx = (current + 1) % max(total, 1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                idx = self.hovered_card_idx if self.hovered_card_idx is not None else 0
                self._launch_game(idx)
            if self.hovered_card_idx != prev and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                self._play_ui_move_sfx()
        elif event.type == pygame.MOUSEMOTION:
            idx = self._get_game_icon_at(event.pos)
            if idx is not None:
                if idx != self.hovered_card_idx:
                    self.hovered_card_idx = idx
                    self._play_ui_move_sfx()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._get_game_icon_at(event.pos)
            if idx is not None:
                self.hovered_card_idx = idx
                self._launch_game(idx)

    def _get_game_icon_at(self, pos: Tuple[int, int]) -> Optional[int]:
        """게임 선택 화면에서 클릭/호버한 아이콘 인덱스를 반환한다(0..2)."""
        total = min(len(self.games), 3)
        y = 230
        size = 140
        gap = 90
        total_w = total * size + max(0, total - 1) * gap
        start_x = (SCREEN_WIDTH - total_w) // 2
        rects = [pygame.Rect(start_x + i * (size + gap), y, size, size) for i in range(total)]
        for i, rect in enumerate(rects):
            if rect.collidepoint(pos):
                return i
        return None

    def _handle_options_event(self, event: pygame.event.Event) -> None:
        """옵션 화면에서 ESC/Enter 입력으로 타이틀로 복귀한다."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.state = "title"

    def _change_page(self, delta: int) -> None:
        """게임 카드 페이지를 변경한다."""
        total_pages = math.ceil(len(self.games) / self.games_per_page)
        self.game_page = (self.game_page + delta) % max(total_pages, 1)

    def _launch_game(self, game_index: int) -> None:
        """선택된 미니게임을 실행한다."""
        game_entry = self.games[game_index]
        # pygame.display.quit() 제거 - display 공유 방식으로 변경
        # 미니게임 실행 중에는 다른 BGM으로 전환
        self._play_bgm(GAME_BGM_FILE, volume=0.35)
        
        # 게임별로 닉네임 전달 (점수 저장용)
        if game_index == 0:  # 날아부리 (flappy_bird)
            run_flappy_bird(quit_on_exit=False, nickname=self.nickname)
        elif game_index == 1:  # 쌓아부리 (sugar_game)
            run_sugar_game(quit_on_exit=False, nickname=self.nickname)
        elif game_index == 2:  # 모아부리 (snake_survival)
            run_snake(quit_on_exit=False, nickname=self.nickname)
        else:
            game_entry.start_fn()
        
        # 런처로 복귀하면 런처 BGM으로 되돌림
        self._play_bgm(BGM_FILE, volume=0.35)
        # 미니게임이 display 모드/서피스를 바꿀 수 있으니, 복귀 후 현재 서피스로 동기화한다.
        current_surface = pygame.display.get_surface()
        if current_surface is not None:
            self.screen = current_surface
        # 각 게임이 종료되면 pygame을 다시 초기화하지 않음
        self._show_status(f"{game_entry.title} 완료!")
        self.state = "hub"

    def _update(self, delta_ms: int) -> None:
        """매 프레임 상태를 갱신한다."""
        now = pygame.time.get_ticks()
        if self.state == "story":
            # 타이핑 효과 업데이트
            scene = self.story_scenes[self.story_scene_index]
            if self.story_char_index < len(scene):
                self.story_char_accum += (delta_ms / 1000.0) * STORY_TYPING_CHARS_PER_SEC
                add = int(self.story_char_accum)
                if add > 0:
                    self.story_char_accum -= add
                    self.story_char_index = min(len(scene), self.story_char_index + add)
        if self.status_message and now > self.status_until_ms:
            self.status_message = None

    def _draw(self) -> None:
        """현재 상태에 맞춰 화면을 렌더링한다."""
        if self.state == "title":
            self._draw_title_screen()
        elif self.state == "story":
            self._draw_story_screen()
        elif self.state == "nickname":
            self._draw_nickname_screen()
        elif self.state == "characters":
            self._draw_character_screen()
        elif self.state == "hub":
            self._draw_hub_screen()
        elif self.state == "options":
            self._draw_options_screen()

    def _draw_title_screen(self) -> None:
        """타이틀 화면을 렌더링한다."""
        title_bg = self.assets.get("title_background")
        if title_bg:
            if title_bg.get_size() != (SCREEN_WIDTH, SCREEN_HEIGHT):
                bg = pygame.transform.smoothscale(title_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
            else:
                bg = title_bg
            self.screen.blit(bg, (0, 0))
        else:
            self.screen.fill(MAIN_BG)

        # 상단 로고
        logo = self.assets.get("title_logo")
        logo_bottom_y = 80
        if logo:
            # 로고가 너무 크면 메뉴 영역이 아래로 밀리므로 조금 작게 잡는다.
            desired_w = int(SCREEN_WIDTH * 0.36)
            desired_w = max(180, min(desired_w, SCREEN_WIDTH - 80))
            scale = desired_w / max(1, logo.get_width())
            desired_h = int(logo.get_height() * scale)
            desired_h = max(1, desired_h)
            logo_surface = pygame.transform.smoothscale(logo, (desired_w, desired_h))
            logo_rect = logo_surface.get_rect()
            logo_rect.centerx = SCREEN_WIDTH // 2
            logo_rect.y = 36
            self.screen.blit(logo_surface, logo_rect)
            logo_bottom_y = logo_rect.bottom

        subtitle = self.font_small.render("방향키로 이동 후 Enter로 선택하세요", True, INACTIVE_TEXT)
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, logo_bottom_y + 34))
        self.screen.blit(subtitle, subtitle_rect)

        # 메뉴 레이아웃: 가용 높이 안에서 항상 화면 내로 들어오도록 자동 배치한다.
        base_w, base_h = self.assets["menu_idle"].get_size()
        # 버튼은 조금 더 크게(단, 화면 밖으로 안 나가도록 아래 가용 높이 계산 로직 유지)
        button_w = int(base_w * 0.98)
        button_h = int(base_h * 0.88)
        button_size = (max(1, button_w), max(1, button_h))
        gap = 18
        menu_total_h = len(self.menu_items) * button_size[1] + max(0, len(self.menu_items) - 1) * gap
        available_top = subtitle_rect.bottom + 22
        available_bottom = SCREEN_HEIGHT - 70  # footer 영역 확보
        menu_start_y = max(available_top, int((available_top + available_bottom - menu_total_h) / 2))
        menu_start_y = min(menu_start_y, max(available_top, available_bottom - menu_total_h))

        self._title_menu_button_rects = []
        for idx, item in enumerate(self.menu_items):
            is_selected = idx == self.menu_index
            button_surface = self._get_ui_button(button_size, hovered=is_selected)
            button_rect = button_surface.get_rect()
            button_rect.centerx = SCREEN_WIDTH // 2
            button_rect.y = menu_start_y + idx * (button_size[1] + gap)
            self.screen.blit(button_surface, button_rect)
            self._title_menu_button_rects.append(button_rect)

            # 기본은 회색, 선택/호버(키보드 이동 또는 마우스 hover로 menu_index가 잡힌 상태)일 때만 검정
            text_color = ACCENT if is_selected else INACTIVE_TEXT
            label = self.font_menu.render(item, True, text_color)
            self.screen.blit(label, label.get_rect(center=button_rect.center))

        footer = self.font_micro.render("Team. The buriburi  |  %배포 버전%", True, INACTIVE_TEXT)
        footer = self.font_micro.render(f"Team. The buriburi  |  v{self.app_version}", True, INACTIVE_TEXT)
        self.screen.blit(footer, (40, SCREEN_HEIGHT - 50))

        if self.status_message:
            status = self.font_small.render(self.status_message, True, STATUS_COLOR)
            self.screen.blit(status, status.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80)))

    def _draw_story_screen(self) -> None:
        """컷신 화면을 렌더링한다."""
        self.screen.fill(STORY_BG)
        header = self.font_medium.render("STORY", True, TITLE_TEXT)
        self.screen.blit(header, (40, 30))

        scene = self.story_scenes[self.story_scene_index]
        visible_text = scene[: self.story_char_index]

        # 본문 텍스트(자동 줄바꿈)
        max_width = SCREEN_WIDTH - 80
        lines = self._wrap_text(visible_text, self.font_small, max_width=max_width)
        x = 40
        y = 110
        line_gap = 10
        for line in lines:
            surf = self.font_small.render(line, True, TITLE_TEXT)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + line_gap

        # 하단 안내
        hint = "클릭/Enter: 전체 보기" if self.story_char_index < len(scene) else "클릭/Enter: 다음"
        hint_surf = self.font_micro.render(hint, True, INACTIVE_TEXT)
        self.screen.blit(hint_surf, (40, SCREEN_HEIGHT - 60))

        page = self.font_micro.render(f"{self.story_scene_index + 1} / {len(self.story_scenes)}", True, INACTIVE_TEXT)
        self.screen.blit(page, (SCREEN_WIDTH - page.get_width() - 40, SCREEN_HEIGHT - 60))

    def _draw_nickname_screen(self) -> None:
        """닉네임 입력 화면을 렌더링한다 (게임 선택 화면과 유사한 레이아웃)."""
        self.screen.fill(MAIN_BG)

        # 상단 타이틀
        title = self.font_medium.render("요원 등록", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 82)))

        helper = self.font_micro.render("부리부리 행성에서 온 당신의 이름을 입력하세요", True, INACTIVE_TEXT)
        self.screen.blit(helper, helper.get_rect(center=(SCREEN_WIDTH // 2, 112)))

        # 디폴트 캐릭터(장식용) - 게임 선택 화면과 동일
        char = self.assets.get("char_default")
        if char:
            char_s = pygame.transform.smoothscale(char, (84, 84))
            char_pos = (40, 46)
            self.screen.blit(char_s, char_pos)

            # 말풍선
            bubble_w, bubble_h = 160, 52
            bubble_x = char_pos[0] + 84 + 6
            bubble_y = char_pos[1] - 2
            bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_w, bubble_h)

            # 그림자
            shadow_rect = bubble_rect.move(3, 3)
            pygame.draw.rect(self.screen, (0, 0, 0, 40), shadow_rect, border_radius=16)

            # 본체
            pygame.draw.rect(self.screen, (255, 255, 255), bubble_rect, border_radius=16)
            pygame.draw.rect(self.screen, (30, 30, 30), bubble_rect, width=2, border_radius=16)

            bubble_text = self.font_small.render("이름이 뭐야?", True, ACCENT)
            self.screen.blit(bubble_text, bubble_text.get_rect(center=bubble_rect.center))

        # 닉네임 입력 박스 (중앙에 크게)
        input_box_w, input_box_h = 400, 70
        input_box_x = (SCREEN_WIDTH - input_box_w) // 2
        input_box_y = 200
        input_box_rect = pygame.Rect(input_box_x, input_box_y, input_box_w, input_box_h)
        self._nickname_input_box_rect = input_box_rect

        # 입력 박스 배경 (포커스 시 테두리 색상 변경)
        pygame.draw.rect(self.screen, (255, 255, 255), input_box_rect, border_radius=12)
        border_color = (50, 120, 200) if self.nickname_input_focused else ACCENT
        border_width = 4 if self.nickname_input_focused else 3
        pygame.draw.rect(self.screen, border_color, input_box_rect, width=border_width, border_radius=12)

        # 입력 텍스트 또는 플레이스홀더
        # 확정된 텍스트 + 조합 중인 텍스트를 합쳐서 표시
        display_text = self.nickname_input + self.nickname_composing
        
        base_x = input_box_rect.x + 20
        text_y = input_box_rect.centery
        
        if display_text:
            # 전체 텍스트를 한 번에 렌더링
            full_text_surf = self.font_medium.render(display_text, True, ACCENT)
            self.screen.blit(full_text_surf, (base_x, text_y - full_text_surf.get_height() // 2))
            
            # 조합 중인 텍스트가 있으면 밑줄 표시
            if self.nickname_composing:
                # 확정된 텍스트의 너비 계산
                confirmed_width = 0
                if self.nickname_input:
                    confirmed_width = self.font_medium.size(self.nickname_input)[0]
                # 조합 중인 텍스트의 너비 계산
                composing_width = self.font_medium.size(self.nickname_composing)[0]
                # 밑줄 그리기
                underline_x = base_x + confirmed_width
                underline_y = text_y + full_text_surf.get_height() // 2 - 2
                pygame.draw.line(
                    self.screen, ACCENT,
                    (underline_x, underline_y),
                    (underline_x + composing_width, underline_y),
                    width=2
                )
        else:
            # 포커스 상태일 때는 플레이스홀더 숨김
            if not self.nickname_input_focused:
                placeholder_surf = self.font_medium.render("클릭해서 입력...", True, INACTIVE_TEXT)
                self.screen.blit(placeholder_surf, (base_x, text_y - placeholder_surf.get_height() // 2))

        # 깜빡이는 커서 (포커스 상태이고 조합 중이 아닐 때만 표시)
        # 조합 중일 때는 밑줄이 이미 표시되므로 커서는 숨김
        if self.nickname_input_focused and not self.nickname_composing:
            # 깜빡임 효과 (500ms 간격)
            if (pygame.time.get_ticks() // 500) % 2 == 0:
                # 커서 위치: 기본 위치 + 확정된 텍스트 너비
                cursor_x = base_x
                if self.nickname_input:
                    cursor_x += self.font_medium.size(self.nickname_input)[0]
                cursor_x += 2
                cursor_y = input_box_rect.centery
                pygame.draw.line(
                    self.screen, ACCENT,
                    (cursor_x, cursor_y - 18),
                    (cursor_x, cursor_y + 18),
                    width=2
                )

        # 확인 버튼
        button_w, button_h = 200, 50
        button_rect = pygame.Rect(
            (SCREEN_WIDTH - button_w) // 2,
            input_box_rect.bottom + 40,
            button_w,
            button_h
        )
        self._nickname_confirm_btn_rect = button_rect

        can_confirm = bool((self.nickname_input + self.nickname_composing).strip())
        button_color = ACCENT if can_confirm else INACTIVE_TEXT
        button_text_color = (255, 255, 255) if can_confirm else (200, 200, 200)

        pygame.draw.rect(self.screen, button_color, button_rect, border_radius=10)
        button_label = self.font_small.render("확인 (Enter)", True, button_text_color)
        self.screen.blit(button_label, button_label.get_rect(center=button_rect.center))

        # 안내 문구
        guide_lines = [
            "• 닉네임은 1~8자까지 입력 가능합니다",
            "• 게임 점수는 닉네임별로 저장됩니다",
        ]
        guide_y = button_rect.bottom + 50
        for line in guide_lines:
            line_surf = self.font_micro.render(line, True, INACTIVE_TEXT)
            self.screen.blit(line_surf, line_surf.get_rect(center=(SCREEN_WIDTH // 2, guide_y)))
            guide_y += 28

        # 하단 푸터
        footer = self.font_micro.render(f"ESC: 타이틀로  |  v{self.app_version}", True, INACTIVE_TEXT)
        self.screen.blit(footer, (40, SCREEN_HEIGHT - 50))

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        """지정 폭 안에 들어오도록 텍스트를 줄바꿈한다(한글 포함 안전)."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            if paragraph == "":
                lines.append("")
                continue
            current = ""
            for ch in paragraph:
                candidate = current + ch
                if font.size(candidate)[0] <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = ch
            if current:
                lines.append(current)
        return lines

    def _story_cells(self) -> Iterable[pygame.Rect]:
        """컷 씬 카드 위치를 생성한다."""
        card_width = 320
        card_height = 150
        padding = 16
        start_x = (SCREEN_WIDTH - (card_width * 2 + padding)) // 2
        start_y = 140
        for row in range(2):
            for col in range(2):
                x = start_x + col * (card_width + padding)
                y = start_y + row * (card_height + padding)
                yield pygame.Rect(x, y, card_width, card_height)

    def _story_cell_alpha(self, idx: int) -> int:
        """각 컷의 페이드 인 알파 값을 계산한다."""
        if self.story_start_ms is None:
            return 0
        elapsed = pygame.time.get_ticks() - self.story_start_ms
        appear_time = idx * STORY_INTERVAL_MS
        if elapsed < appear_time:
            return 0
        progress = min(1.0, (elapsed - appear_time) / 800)
        return int(255 * progress)

    def _draw_character_screen(self) -> None:
        """캐릭터 선택 화면을 렌더링한다."""
        self.screen.fill(MAIN_BG)
        title = self.font_large.render("캐릭터를 고르세요", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 120)))

        spacing = 32
        card_size = 140
        total_width = len(self.character_options) * card_size + (len(self.character_options) - 1) * spacing
        start_x = (SCREEN_WIDTH - total_width) // 2
        y = 190

        card_base = self.assets["character_card_base"]
        card_border = self.assets["character_card_border"]

        for idx, option in enumerate(self.character_options):
            x = start_x + idx * (card_size + spacing)
            rect = pygame.Rect(x, y, card_size, card_size)
            hover = self.hovered_character_idx == idx
            selected = self.selected_character_idx == idx
            lift = -12 if hover else 0
            animated_offset = math.sin(pygame.time.get_ticks() / 120) * 4 if hover else 0
            draw_rect = rect.move(0, lift + animated_offset)

            card_rect = card_base.get_rect().copy()
            card_rect.topleft = draw_rect.topleft
            self.screen.blit(card_base, card_rect)

            color_center = (card_rect.centerx, card_rect.centery - 8)
            pygame.draw.circle(self.screen, option.color, color_center, 36)
            code_label = self.font_small.render(option.code, True, ACCENT)
            self.screen.blit(code_label, code_label.get_rect(center=(card_rect.centerx, card_rect.centery + 30)))

            if selected or hover:
                border_surface = card_border.copy()
                if hover and not selected:
                    border_surface.set_alpha(180)
                border_rect = border_surface.get_rect(center=card_rect.center)
                self.screen.blit(border_surface, border_rect)

            label = self.font_small.render(option.display_name, True, ACCENT)
            label_rect = label.get_rect(center=(card_rect.centerx, card_rect.bottom + 24))
            self.screen.blit(label, label_rect)

        helper = self.font_micro.render("Enter 키 또는 마우스 클릭으로 선택합니다.", True, INACTIVE_TEXT)
        self.screen.blit(helper, helper.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80)))

    def _draw_hub_screen(self) -> None:
        """게임 선택 화면(아이콘 기반)을 렌더링한다."""
        self.screen.fill(MAIN_BG)
        self._draw_game_select()

    def _draw_game_select(self) -> None:
        """아이콘 기반 게임 선택 UI를 렌더링한다."""
        title = self.font_medium.render("게임 선택", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 82)))

        helper = self.font_micro.render("마우스로 선택하거나 방향키로 이동 후, Enter로 시작", True, INACTIVE_TEXT)
        self.screen.blit(helper, helper.get_rect(center=(SCREEN_WIDTH // 2, 112)))

        # 디폴트 캐릭터(장식용)
        char = self.assets.get("char_default")
        if char:
            char_s = pygame.transform.smoothscale(char, (84, 84))
            char_pos = (40, 46)
            self.screen.blit(char_s, char_pos)

            # 말풍선(캐릭터가 덩그러니 서 있는 느낌 완화)
            # 닉네임이 있으면 환영 메시지, 없으면 기본 메시지
            if self.nickname:
                bubble_msg = f"{self.nickname}!"
            else:
                bubble_msg = "뭐하지?"
            
            # 말풍선 너비를 텍스트 길이에 맞게 동적 조정
            bubble_text = self.font_small.render(bubble_msg, True, ACCENT)
            text_width = bubble_text.get_width()
            bubble_w = max(100, text_width + 40)  # 최소 100, 텍스트 + 여백
            bubble_h = 52
            
            bubble_x = char_pos[0] + 84 + 6
            bubble_y = char_pos[1] - 2
            bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_w, bubble_h)

            # 그림자
            shadow_rect = bubble_rect.move(3, 3)
            pygame.draw.rect(self.screen, (0, 0, 0, 40), shadow_rect, border_radius=16)

            # 본체
            pygame.draw.rect(self.screen, (255, 255, 255), bubble_rect, border_radius=16)
            pygame.draw.rect(self.screen, (30, 30, 30), bubble_rect, width=2, border_radius=16)

            self.screen.blit(bubble_text, bubble_text.get_rect(center=bubble_rect.center))

        icon_keys = ["icon_flappy", "icon_sugar", "icon_snake"]
        total = min(len(self.games), 3)
        # 타이틀과 아이콘 컨테이너 사이 간격을 줄이기 위해 위로 당김
        y = 190
        size = 140
        gap = 90
        total_w = total * size + max(0, total - 1) * gap
        start_x = (SCREEN_WIDTH - total_w) // 2
        rects = [pygame.Rect(start_x + i * (size + gap), y, size, size) for i in range(total)]

        selected_idx = self.hovered_card_idx if self.hovered_card_idx is not None else 0
        selected_idx = max(0, min(total - 1, selected_idx)) if total else 0

        for i, rect in enumerate(rects):
            is_selected = i == selected_idx
            icon = self.assets.get(icon_keys[i])
            if icon:
                draw_size = int(size * (1.08 if is_selected else 1.0))
                icon_s = pygame.transform.smoothscale(icon, (draw_size, draw_size))
                draw_rect = icon_s.get_rect(center=rect.center)
                self.screen.blit(icon_s, draw_rect)
                hit_rect = draw_rect
            else:
                pygame.draw.rect(self.screen, CARD_BG, rect, border_radius=18)
                hit_rect = rect

            if is_selected:
                pygame.draw.rect(self.screen, (30, 30, 30), hit_rect.inflate(12, 12), width=3, border_radius=22)

            # 게임명 + 설명
            label = self.font_small.render(self.games[i].title, True, ACCENT)
            label_rect = label.get_rect(center=(rect.centerx, rect.bottom + 28))
            self.screen.blit(label, label_rect)

            desc_lines = self._wrap_text(self.games[i].description, self.font_micro, max_width=220)
            y = label_rect.bottom + 10
            for line in desc_lines[:3]:
                line_surf = self.font_micro.render(line, True, INACTIVE_TEXT)
                self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, y + line_surf.get_height() // 2)))
                y += line_surf.get_height() + 6

        footer = self.font_micro.render(f"ESC: 타이틀로  |  v{self.app_version}", True, INACTIVE_TEXT)
        self.screen.blit(footer, (40, SCREEN_HEIGHT - 50))

    def _draw_options_screen(self) -> None:
        """옵션 화면을 단순하게 렌더링한다."""
        options_bg = self.assets.get("options_background")
        if options_bg:
            self.screen.blit(options_bg, (0, 0))
        else:
            self.screen.fill(MAIN_BG)
        title = self.font_large.render("옵션", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 200)))
        desc = self.font_small.render("사운드 · 그래픽 옵션은 곧 추가됩니다.", True, ACCENT)
        self.screen.blit(desc, desc.get_rect(center=(SCREEN_WIDTH // 2, 280)))
        helper = self.font_micro.render("ESC 또는 Enter로 돌아가기", True, INACTIVE_TEXT)
        self.screen.blit(helper, helper.get_rect(center=(SCREEN_WIDTH // 2, 360)))

    def _draw_character_panel(self) -> None:
        """센터 영역의 캐릭터 말풍선 UI를 렌더링한다."""
        center_x = SCREEN_WIDTH // 2
        speech_surface = self.assets["character_speech"]
        bubble_rect = speech_surface.get_rect()
        bubble_rect.topleft = (center_x - bubble_rect.width // 2, 210)
        self.screen.blit(speech_surface, bubble_rect)
        bubble_text = self.font_small.render("어디로 갈까?", True, ACCENT)
        self.screen.blit(bubble_text, bubble_text.get_rect(center=bubble_rect.center))

        box_surface = self.assets["character_box"]
        char_rect = box_surface.get_rect()
        char_rect.topleft = (center_x - char_rect.width // 2, 274)
        self.screen.blit(box_surface, char_rect)
        if self.current_character:
            pygame.draw.circle(self.screen, self.current_character.color, char_rect.center, 48)
            char_label = self.font_small.render(self.current_character.code, True, ACCENT)
            self.screen.blit(char_label, char_label.get_rect(center=char_rect.center))
            name_label = self.font_micro.render(self.current_character.display_name, True, ACCENT)
            self.screen.blit(name_label, name_label.get_rect(center=(char_rect.centerx, char_rect.bottom + 20)))
        else:
            placeholder = self.font_small.render("Character", True, ACCENT)
            self.screen.blit(placeholder, placeholder.get_rect(center=char_rect.center))

    def _draw_game_cards(self) -> None:
        """게임 카드 4개를 현재 페이지에 맞게 배치한다."""
        subtitle = self.font_small.render("게임 선택", True, ACCENT)
        self.screen.blit(subtitle, (60, 160))

        page_text = self.font_micro.render(
            f"←/→ 로 페이지 이동 ( {self.game_page + 1} / {math.ceil(len(self.games) / self.games_per_page)} )",
            True,
            INACTIVE_TEXT,
        )
        self.screen.blit(page_text, (60, 190))

        for global_idx, game, rect in self._visible_game_cards():
            is_hovered = self._is_card_hovered(global_idx)
            card_surface = self.assets["game_card_hover"] if is_hovered else self.assets["game_card_idle"]
            self.screen.blit(card_surface, rect)

            name = self.font_small.render(game.title, True, ACCENT)
            desc = self.font_micro.render(game.description, True, TITLE_BG)

            self.screen.blit(name, (rect.x + 18, rect.y + 16))
            self.screen.blit(desc, (rect.x + 18, rect.y + 50))

            if is_hovered:
                prompt = self.font_micro.render("클릭해서 플레이!", True, TITLE_BG)
                self.screen.blit(prompt, (rect.right - prompt.get_width() - 16, rect.bottom - 36))

    def _visible_game_cards(self) -> Iterable[Tuple[int, GameEntry, pygame.Rect]]:
        """현재 페이지에서 보이는 카드와 위치를 반환한다."""
        start = self.game_page * self.games_per_page
        subset = self.games[start : start + self.games_per_page]
        card_width = 220
        card_height = 130
        left_x = 70
        right_x = 510
        top_y = 220
        vertical_gap = 150

        positions = [
            (left_x, top_y),
            (right_x, top_y),
            (left_x, top_y + vertical_gap),
            (right_x, top_y + vertical_gap),
        ]

        for idx, game in enumerate(subset):
            pos_x, pos_y = positions[idx]
            rect = pygame.Rect(pos_x, pos_y, card_width, card_height)
            yield start + idx, game, rect

    def _is_card_hovered(self, idx: int) -> bool:
        """현재 호버 중인 카드인지 확인한다."""
        return self.hovered_card_idx == idx

    def _update_hovered_card(self, pos: Tuple[int, int]) -> None:
        """마우스 좌표에 맞는 카드 인덱스를 저장한다."""
        self.hovered_card_idx = self._get_card_at(pos)

    def _get_card_at(self, pos: Tuple[int, int]) -> Optional[int]:
        """마우스 좌표에 해당하는 카드 인덱스를 찾는다."""
        for idx, _, rect in self._visible_game_cards():
            if rect.collidepoint(pos):
                return idx
        return None

    def _hit_test_character(self, pos: Tuple[int, int]) -> Optional[int]:
        """캐릭터 선택 박스에서 마우스 위치에 해당하는 인덱스를 반환한다."""
        spacing = 32
        card_size = 140
        total_width = len(self.character_options) * card_size + (len(self.character_options) - 1) * spacing
        start_x = (SCREEN_WIDTH - total_width) // 2
        y = 190
        rects = [
            pygame.Rect(start_x + i * (card_size + spacing), y, card_size, card_size)
            for i in range(len(self.character_options))
        ]
        for idx, rect in enumerate(rects):
            if rect.collidepoint(pos):
                return idx
        return None

    def _show_status(self, message: str, duration_ms: int = 2200) -> None:
        """일시적으로 표시할 상태 메시지를 세팅한다."""
        self.status_message = message
        self.status_until_ms = pygame.time.get_ticks() + duration_ms


def run_launcher() -> None:
    """버리부리 파티 런처를 실행한다."""
    app = BuriBuriPartyApp()
    app.run()


if __name__ == "__main__":
    run_launcher()

