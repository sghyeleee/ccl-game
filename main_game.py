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
PROGRESS_BG = (223, 223, 230)
PROGRESS_FILL = (69, 94, 220)
STATUS_COLOR = (238, 94, 42)
COUNTDOWN_BG = (16, 18, 32)
COUNTDOWN_TEXT = (255, 255, 255)
COUNTDOWN_SECONDS = 3
COUNTDOWN_DURATION_MS = COUNTDOWN_SECONDS * 1000
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "main_game"

STORY_INTERVAL_MS = 3000
STORY_EXTRA_HOLD_MS = 1500
MENU_FONT_NAME = "pretendard"
FONT_CANDIDATES = [
    "Pretendard",
    "Apple SD Gothic Neo",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Arial Unicode MS",
]

GameStartFn = Callable[[], None]


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
    for name in FONT_CANDIDATES:
        font_path = pygame.font.match_font(name, bold=bold)
        if font_path:
            return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(None, size, bold=bold)


def _load_image(name: str) -> pygame.Surface:
    """지정된 자산 이미지를 RGBA 형태로 불러온다."""
    path = ASSET_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return pygame.image.load(path.as_posix()).convert_alpha()


def get_game_entries() -> List[GameEntry]:
    """런처에서 노출할 미니게임 목록을 반환한다."""
    return [
        GameEntry(
            "Flappy Bird",
            "탭으로 날아올라 파이프 사이를 통과하세요. 부딪히면 게임오버!",
            lambda: run_flappy_bird(quit_on_exit=False),
        ),
        GameEntry(
            "Snake Survival",
            "친구를 구해 내 등 뒤에 붙이세요! (동작은 뱀 게임과 같아요)",
            lambda: run_snake(quit_on_exit=False),
        ),
        GameEntry(
            "Sugar Game",
            "햄버거 재료를 쌓아 높이 올리세요. 중심을 잃으면 게임오버!",
            lambda: run_sugar_game(quit_on_exit=False),
        ),
    ]


class BuriBuriPartyApp:
    """인트로 → 스토리 → 캐릭터 → 메인 허브 플로우를 담당하는 컨트롤러."""

    def __init__(self) -> None:
        """pygame 초기화와 상태 기본값을 세팅한다."""
        self.games = get_game_entries()
        self.game_page = 0
        self.games_per_page = 4
        self.best_scores: dict[str, Optional[int]] = {game.title: None for game in self.games}
        self.hovered_card_idx: Optional[int] = None

        self.menu_items = ["새로 플레이", "이어서 플레이", "옵션", "나가기"]
        self.menu_index = 0
        self.state = "title"
        self.running = True
        self.story_start_ms: Optional[int] = None
        self.story_card_count = 4
        self.story_total_ms = self.story_card_count * STORY_INTERVAL_MS + STORY_EXTRA_HOLD_MS
        self.story_skip_rect = pygame.Rect(SCREEN_WIDTH - 140, 20, 120, 44)

        self.character_options = [
            CharacterOption("A", "Pang", (255, 163, 163)),
            CharacterOption("B", "Dori", (166, 209, 255)),
            CharacterOption("C", "Nimo", (255, 220, 164)),
            CharacterOption("D", "Ning", (190, 247, 190)),
        ]
        self.selected_character_idx = 0
        self.hovered_character_idx: Optional[int] = None
        self.current_character: Optional[CharacterOption] = None

        self.level = 1
        self.exp = 0
        self.exp_to_next = 100

        self.status_message: Optional[str] = None
        self.status_until_ms = 0

        self.countdown_game_index: Optional[int] = None
        self.countdown_start_ms: Optional[int] = None
        self.assets: dict[str, pygame.Surface] = {}

        self._init_pygame()

    def _init_pygame(self) -> None:
        """pygame 디스플레이와 폰트를 재구성한다."""
        pygame.init()
        pygame.display.set_caption("the buriburi party")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_large = _get_font(58, bold=True)
        self.font_medium = _get_font(32, bold=True)
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
            "exp_bar_frame": "exp_bar_frame.png",
            "game_card_idle": "game_card_idle.png",
            "game_card_hover": "game_card_hover.png",
            "countdown_background": "countdown_background.png",
            "options_background": "options_background.png",
        }
        return {key: _load_image(filename) for key, filename in files.items()}

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
        elif self.state == "characters":
            self._handle_character_event(event)
        elif self.state == "hub":
            self._handle_hub_event(event)
        elif self.state == "options":
            self._handle_options_event(event)
        elif self.state == "countdown":
            self._handle_countdown_event(event)

    def _handle_title_event(self, event: pygame.event.Event) -> None:
        """타이틀 메뉴에서의 키 입력을 처리한다."""
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_DOWN, pygame.K_s):
            self.menu_index = (self.menu_index + 1) % len(self.menu_items)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.menu_index = (self.menu_index - 1) % len(self.menu_items)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._trigger_menu_action()
        elif event.key == pygame.K_ESCAPE:
            self.running = False

    def _trigger_menu_action(self) -> None:
        """선택된 메뉴 항목에 맞는 액션을 수행한다."""
        current_item = self.menu_items[self.menu_index]
        if current_item == "새로 플레이":
            self._start_new_play()
        elif current_item == "이어서 플레이":
            self._continue_play()
        elif current_item == "옵션":
            self.state = "options"
        elif current_item == "나가기":
            self.running = False

    def _start_new_play(self) -> None:
        """새로 플레이 흐름을 시작한다."""
        self.story_start_ms = pygame.time.get_ticks()
        self.current_character = None
        self.selected_character_idx = 0
        self.state = "story"

    def _continue_play(self) -> None:
        """이어하기 선택 시 적절한 단계로 이동한다."""
        if self.current_character:
            self.state = "hub"
        else:
            self._show_status("먼저 캐릭터를 선택해주세요!")
            self.state = "characters"

    def _handle_story_event(self, event: pygame.event.Event) -> None:
        """스토리 화면에서 스킵 클릭을 감지한다."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.story_skip_rect.collidepoint(event.pos):
                self._go_to_character_select()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._go_to_character_select()

    def _go_to_character_select(self) -> None:
        """스토리 종료 후 캐릭터 선택으로 전환한다."""
        self.state = "characters"
        self.story_start_ms = None

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
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "title"
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._change_page(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._change_page(1)
        elif event.type == pygame.MOUSEMOTION:
            self._update_hovered_card(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            card_index = self._get_card_at(event.pos)
            if card_index is not None:
                self._start_countdown(card_index)

    def _handle_options_event(self, event: pygame.event.Event) -> None:
        """옵션 화면에서 ESC/Enter 입력으로 타이틀로 복귀한다."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.state = "title"

    def _handle_countdown_event(self, event: pygame.event.Event) -> None:
        """카운트다운 도중 입력을 처리한다."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._cancel_countdown()

    def _start_countdown(self, game_index: int) -> None:
        """선택된 게임을 실행하기 전 카운트다운을 시작한다."""
        self.countdown_game_index = game_index
        self.countdown_start_ms = pygame.time.get_ticks()
        self.state = "countdown"

    def _cancel_countdown(self) -> None:
        """카운트다운을 취소하고 허브로 돌아간다."""
        self.countdown_game_index = None
        self.countdown_start_ms = None
        self.state = "hub"

    def _change_page(self, delta: int) -> None:
        """게임 카드 페이지를 변경한다."""
        total_pages = math.ceil(len(self.games) / self.games_per_page)
        self.game_page = (self.game_page + delta) % max(total_pages, 1)

    def _launch_game(self, game_index: int) -> None:
        """선택된 미니게임을 실행한다."""
        game_entry = self.games[game_index]
        self.countdown_game_index = None
        self.countdown_start_ms = None
        # pygame.display.quit() 제거 - display 공유 방식으로 변경
        game_entry.start_fn()
        # 미니게임이 display 모드/서피스를 바꿀 수 있으니, 복귀 후 현재 서피스로 동기화한다.
        current_surface = pygame.display.get_surface()
        if current_surface is not None:
            self.screen = current_surface
        # 각 게임이 종료되면 pygame을 다시 초기화하지 않음
        self._gain_experience(20)
        self._show_status(f"{game_entry.title} 완료! 경험치 +20")
        self.state = "hub"

    def _gain_experience(self, amount: int) -> None:
        """미니게임 완료 후 경험치를 누적하고 레벨을 관리한다."""
        self.exp += amount
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.exp_to_next = int(self.exp_to_next * 1.2)

    def _update(self, delta_ms: int) -> None:
        """매 프레임 상태를 갱신한다."""
        _ = delta_ms
        now = pygame.time.get_ticks()
        if self.state == "story" and self.story_start_ms is not None:
            if now - self.story_start_ms >= self.story_total_ms:
                self._go_to_character_select()
        if self.status_message and now > self.status_until_ms:
            self.status_message = None
        if (
            self.state == "countdown"
            and self.countdown_start_ms is not None
            and self.countdown_game_index is not None
            and now - self.countdown_start_ms >= COUNTDOWN_DURATION_MS
        ):
            self._launch_game(self.countdown_game_index)

    def _draw(self) -> None:
        """현재 상태에 맞춰 화면을 렌더링한다."""
        if self.state == "title":
            self._draw_title_screen()
        elif self.state == "story":
            self._draw_story_screen()
        elif self.state == "characters":
            self._draw_character_screen()
        elif self.state == "hub":
            self._draw_hub_screen()
        elif self.state == "options":
            self._draw_options_screen()
        elif self.state == "countdown":
            self._draw_countdown_screen()

    def _draw_title_screen(self) -> None:
        """타이틀 화면을 렌더링한다."""
        self.screen.fill(MAIN_BG)
        title_bar = self.assets.get("title_bar")
        if title_bar:
            self.screen.blit(title_bar, (0, 0))
        else:
            pygame.draw.rect(self.screen, TITLE_BG, (0, 0, SCREEN_WIDTH, TITLE_BAR_HEIGHT))
        title_surface = self.font_large.render("더 부리부리 파티", True, TITLE_TEXT)
        self.screen.blit(title_surface, title_surface.get_rect(center=(SCREEN_WIDTH // 2, TITLE_BAR_HEIGHT // 2)))

        subtitle = self.font_small.render("방향키로 이동 후 Enter로 선택하세요", True, INACTIVE_TEXT)
        self.screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, TITLE_BAR_HEIGHT + 40)))

        menu_start_y = TITLE_BAR_HEIGHT + 120
        for idx, item in enumerate(self.menu_items):
            is_selected = idx == self.menu_index
            button_surface = self.assets["menu_hover"] if is_selected else self.assets["menu_idle"]
            button_rect = button_surface.get_rect()
            button_rect.centerx = SCREEN_WIDTH // 2
            button_rect.y = menu_start_y + idx * 70
            self.screen.blit(button_surface, button_rect)

            text_color = TITLE_TEXT if is_selected else ACCENT
            label = self.font_medium.render(item, True, text_color)
            self.screen.blit(label, label.get_rect(center=button_rect.center))

        footer = self.font_micro.render("Team. The buriburi  |  %배포 버전%", True, INACTIVE_TEXT)
        self.screen.blit(footer, (40, SCREEN_HEIGHT - 50))

        if self.status_message:
            status = self.font_small.render(self.status_message, True, STATUS_COLOR)
            self.screen.blit(status, status.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80)))

    def _draw_story_screen(self) -> None:
        """컷신 화면을 렌더링한다."""
        self.screen.fill(STORY_BG)
        intro_text = self.font_medium.render("Story...", True, TITLE_TEXT)
        self.screen.blit(intro_text, (40, 30))

        card_template = self.assets["story_card"]
        for idx, rect in enumerate(self._story_cells()):
            alpha = self._story_cell_alpha(idx)
            if alpha <= 0:
                continue
            if card_template.get_size() != rect.size:
                surface = pygame.transform.smoothscale(card_template, rect.size)
            else:
                surface = card_template.copy()
            surface.set_alpha(alpha)
            self.screen.blit(surface, rect)

            label = self.font_medium.render(f"Cut {idx + 1}", True, ACCENT)
            self.screen.blit(label, label.get_rect(center=rect.center))

        mouse_pos = pygame.mouse.get_pos()
        skip_surface = self.assets["skip_hover"] if self.story_skip_rect.collidepoint(mouse_pos) else self.assets["skip_idle"]
        self.screen.blit(skip_surface, self.story_skip_rect)
        skip_label = self.font_small.render("Skip >>", True, TITLE_TEXT)
        self.screen.blit(skip_label, skip_label.get_rect(center=self.story_skip_rect.center))

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
        """게임 메인 허브를 렌더링한다."""
        self.screen.fill(MAIN_BG)
        self._draw_top_status_bar()
        self._draw_character_panel()
        self._draw_game_cards()

    def _draw_countdown_screen(self) -> None:
        """미니게임 실행 전 카운트다운 화면을 렌더링한다."""
        countdown_bg = self.assets.get("countdown_background")
        if countdown_bg:
            self.screen.blit(countdown_bg, (0, 0))
        else:
            self.screen.fill(COUNTDOWN_BG)
        if self.countdown_game_index is None or self.countdown_start_ms is None:
            return

        game_entry = self.games[self.countdown_game_index]
        now = pygame.time.get_ticks()
        elapsed = now - self.countdown_start_ms
        remaining_ms = max(0, COUNTDOWN_DURATION_MS - elapsed)
        current_second = max(1, math.ceil(remaining_ms / 1000))

        title = self.font_medium.render(game_entry.title, True, COUNTDOWN_TEXT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120)))

        countdown_text = self.font_large.render(str(current_second), True, COUNTDOWN_TEXT)
        self.screen.blit(countdown_text, countdown_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))

        helper = self.font_small.render("ESC로 취소", True, COUNTDOWN_TEXT)
        self.screen.blit(helper, helper.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 120)))

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

    def _draw_top_status_bar(self) -> None:
        """레벨과 경험치 프로그레스 UI를 렌더링한다."""
        name = self.current_character.display_name if self.current_character else "%레벨 명%"
        header = self.font_small.render(f"{name}", True, ACCENT)
        self.screen.blit(header, (60, 34))

        level_label = self.font_medium.render(f"Lv.{self.level}", True, ACCENT)
        self.screen.blit(level_label, (60, 70))

        bar_rect = pygame.Rect(160, 88, 320, 16)
        inner_rect = bar_rect.inflate(-8, -8)
        progress_ratio = (self.exp / self.exp_to_next) if self.exp_to_next else 1.0
        fill_width = int(inner_rect.width * max(0.0, min(1.0, progress_ratio)))
        if fill_width > 0:
            fill_rect = pygame.Rect(inner_rect.x, inner_rect.y, fill_width, inner_rect.height)
            pygame.draw.rect(self.screen, PROGRESS_FILL, fill_rect, border_radius=6)
        self.screen.blit(self.assets["exp_bar_frame"], bar_rect.topleft)

        progress_text = self.font_micro.render(f"{self.exp} / {self.exp_to_next}", True, ACCENT)
        self.screen.blit(progress_text, (bar_rect.right + 16, bar_rect.y - 6))

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
            best_score = self.best_scores.get(game.title)
            score_text = "기록 없음" if best_score is None else f"{best_score:,}점"
            score_surface = self.font_micro.render(f"최고점수 : {score_text}", True, TITLE_BG)

            self.screen.blit(name, (rect.x + 18, rect.y + 16))
            self.screen.blit(desc, (rect.x + 18, rect.y + 50))
            self.screen.blit(score_surface, (rect.x + 18, rect.y + rect.height - 36))

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

