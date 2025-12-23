from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

from leaderboard import LeaderboardEntry, submit_and_fetch_async
from ui_common import draw_game_over_ui, draw_input_box, draw_leaderboard_list

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 540
FPS = 60

BG_COLOR = (132, 205, 255)
TEXT_COLOR = (20, 20, 20)

GRAVITY = 1700.0
# 스페이스/탭 플랩이 과하게 튀어오르지 않도록 점프 힘을 완화
JUMP_VELOCITY = -430.0
MAX_FALL_SPEED = 900.0

BIRD_X = 220
BIRD_SIZE = 64

GROUND_HEIGHT = 0
CEILING_MARGIN = 8

# 파이프 다양화(재미를 위해 고정값 제거)
PIPE_WIDTH_MIN = 55
PIPE_WIDTH_MAX = 55

PIPE_GAP_MIN = 140
PIPE_GAP_MAX = 216

# 갭 중심 y 범위(파이프마다 gap이 달라지므로, 실제 범위는 계산 시 gap/2를 고려)
PIPE_GAP_CENTER_MIN_Y = 120
PIPE_GAP_CENTER_MAX_Y = SCREEN_HEIGHT - GROUND_HEIGHT - 120

PIPE_SPEED_BASE = 220.0
PIPE_SPEED_PER_SCORE = 2.2
PIPE_SPAWN_INTERVAL_MIN_MS = 1050
PIPE_SPAWN_INTERVAL_MAX_MS = 1550

NEW_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "new" / "05. game2_naraburi"
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
NEODGM_FONT_FILE = FONT_DIR / "neodgm.ttf"

FONT_CANDIDATES = [
    "Pretendard",
    "Apple SD Gothic Neo",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Arial Unicode MS",
]


def _draw_card(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """쌓아부리 스타일과 비슷한 버튼 카드."""
    pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=18)
    pygame.draw.rect(surface, (40, 40, 40), rect, width=2, border_radius=18)


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    if NEODGM_FONT_FILE.exists():
        try:
            return pygame.font.Font(NEODGM_FONT_FILE.as_posix(), size)
        except OSError:
            pass
    for name in FONT_CANDIDATES:
        font_path = pygame.font.match_font(name, bold=bold)
        if font_path:
            return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(None, size, bold=bold)


def _load_image(path: Path) -> pygame.Surface:
    return pygame.image.load(path.as_posix()).convert_alpha()


def _smoothscale(image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    if image.get_size() == size:
        return image
    return pygame.transform.smoothscale(image, size)


@dataclass
class PipePair:
    x: float
    gap_center_y: float
    gap_size: int
    width: int
    moving_amp: float = 0.0
    moving_speed: float = 0.0  # radians/sec
    moving_phase: float = 0.0
    passed: bool = False

    def current_gap_center_y(self, time_s: float) -> int:
        if self.moving_amp <= 0.0:
            return int(self.gap_center_y)
        return int(self.gap_center_y + math.sin(time_s * self.moving_speed + self.moving_phase) * self.moving_amp)

    def rect_top(self) -> pygame.Rect:
        gap_y = int(self.gap_center_y)
        return pygame.Rect(int(self.x), 0, self.width, gap_y - self.gap_size // 2)

    def rect_bottom(self) -> pygame.Rect:
        gap_y = int(self.gap_center_y)
        bottom_top = gap_y + self.gap_size // 2
        return pygame.Rect(int(self.x), bottom_top, self.width, SCREEN_HEIGHT - GROUND_HEIGHT - bottom_top)

    def is_off_screen(self) -> bool:
        return self.x + self.width < -40


class FlappyBirdGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("날아부리")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = get_font(44, bold=True)
        self.font_big = get_font(56, bold=True)
        self.font = get_font(20)
        self.font_small = get_font(16)

        self.state: str = "title"  # title | howto | play | gameover
        self.running = True
        self.menu_index = 0  # 0=start, 1=howto
        self.lb_nickname = ""
        self.lb_status: Optional[str] = None
        self.lb_top: list[LeaderboardEntry] = []
        self.lb_submitted = False

        self.use_new_assets = NEW_ASSET_DIR.exists()
        self.bg_surface: Optional[pygame.Surface] = None
        self.bird_surface: Optional[pygame.Surface] = None
        self.obstacle_head_up: Optional[pygame.Surface] = None
        self.obstacle_head_down: Optional[pygame.Surface] = None
        self.obstacle_body: Optional[pygame.Surface] = None
        self._load_assets()

        self.reset_run()
        btn_w, btn_h = 240, 64
        btn_x = (SCREEN_WIDTH - btn_w) // 2
        self.btn_start = pygame.Rect(btn_x, 300, btn_w, btn_h)
        self.btn_howto = pygame.Rect(btn_x, 378, btn_w, btn_h)
        self.btn_back = pygame.Rect(26, 22, 110, 46)

    def _load_assets(self) -> None:
        if not self.use_new_assets:
            return
        try:
            bg = _load_image(NEW_ASSET_DIR / "title_background_800_540.png")
            self.bg_surface = _smoothscale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT))

            bird = _load_image(NEW_ASSET_DIR / "char_flying_140_140.png")
            self.bird_surface = _smoothscale(bird, (BIRD_SIZE, BIRD_SIZE))

            # NOTE: 제공된 에셋에서 up/down 파일명이 실제 방향과 반대로 보이는 경우가 있어
            # 게임 내에서는 "위 장애물(아래로 향함) = head_down", "아래 장애물(위로 향함) = head_up"으로
            # 보이도록 로딩 단계에서 스왑해 맞춘다.
            head_up = _load_image(NEW_ASSET_DIR / "obstacle_head_down_55_55.png")
            head_down = _load_image(NEW_ASSET_DIR / "obstacle_head_up_55_55.png")
            body = _load_image(NEW_ASSET_DIR / "obstacle_body_55_55.png")
            self.obstacle_head_up = _smoothscale(head_up, (PIPE_WIDTH_MIN, PIPE_WIDTH_MIN))
            self.obstacle_head_down = _smoothscale(head_down, (PIPE_WIDTH_MIN, PIPE_WIDTH_MIN))
            self.obstacle_body = _smoothscale(body, (PIPE_WIDTH_MIN, PIPE_WIDTH_MIN))
        except Exception:
            # 에셋 로딩 실패 시에도 게임은 실행되게(기존 도형 렌더링으로 폴백)
            self.use_new_assets = False
            self.bg_surface = None
            self.bird_surface = None
            self.obstacle_head_up = None
            self.obstacle_head_down = None
            self.obstacle_body = None

    def reset_run(self) -> None:
        self.bird_y = float(SCREEN_HEIGHT * 0.42)
        self.bird_vy = 0.0
        self.score = 0
        self.pipes: list[PipePair] = []
        self.next_spawn_ms = pygame.time.get_ticks()
        self.ground_scroll = 0.0
        self.bg_scroll = 0.0
        self.game_over_reason: Optional[str] = None

    def flap(self) -> None:
        if self.state == "title":
            self.state = "play"
            self.reset_run()
            self.bird_vy = JUMP_VELOCITY
            return
        if self.state == "play":
            self.bird_vy = JUMP_VELOCITY
            return
        if self.state == "gameover":
            self.state = "play"
            self.reset_run()
            self.bird_vy = JUMP_VELOCITY

    def _compute_spawn_interval_ms(self) -> int:
        # 점수가 오를수록 평균 간격을 약간 줄이되, 랜덤성은 유지
        min_ms = max(850, int(PIPE_SPAWN_INTERVAL_MIN_MS - self.score * 6))
        max_ms = max(1100, int(PIPE_SPAWN_INTERVAL_MAX_MS - self.score * 5))
        return random.randint(min_ms, max_ms)

    def _compute_gap_size(self) -> int:
        # 점수가 오를수록 평균 갭을 조금씩 줄이되, 너무 억까는 방지
        min_gap = max(130, int(PIPE_GAP_MIN - self.score * 1.2))
        max_gap = max(min_gap + 26, int(PIPE_GAP_MAX - self.score * 0.8))
        return random.randint(min_gap, max_gap)

    def spawn_pipe(self) -> None:
        width = random.randint(PIPE_WIDTH_MIN, PIPE_WIDTH_MAX)
        gap = self._compute_gap_size()

        # gap이 커지면 중심 y의 유효 범위가 줄어드므로 gap/2를 고려해 클램프
        min_center = PIPE_GAP_CENTER_MIN_Y
        max_center = PIPE_GAP_CENTER_MAX_Y
        gap_y = float(random.randint(min_center, max_center))

        # 움직이는 장애물은 난이도가 높아서 제거: 항상 고정 장애물만 생성
        amp = 0.0
        speed = 0.0
        phase = 0.0

        self.pipes.append(
            PipePair(
                x=float(SCREEN_WIDTH + 60),
                gap_center_y=gap_y,
                gap_size=gap,
                width=width,
                moving_amp=amp,
                moving_speed=speed,
                moving_phase=phase,
            )
        )

    def bird_rect(self) -> pygame.Rect:
        half = BIRD_SIZE // 2
        # 살짝 타이트하게 잡아 “이미지 외곽 투명 영역” 충돌을 완화
        inset = max(6, BIRD_SIZE // 8)
        return pygame.Rect(BIRD_X - half + inset, int(self.bird_y) - half + inset, BIRD_SIZE - inset * 2, BIRD_SIZE - inset * 2)

    def update_play(self, dt: float) -> None:
        speed = PIPE_SPEED_BASE + PIPE_SPEED_PER_SCORE * self.score

        # 배경 스크롤(가벼운 연출)
        self.bg_scroll = (self.bg_scroll + speed * 0.12 * dt) % SCREEN_WIDTH
        self.ground_scroll = (self.ground_scroll + speed * dt) % 48

        # 중력/새 이동
        self.bird_vy = min(MAX_FALL_SPEED, self.bird_vy + GRAVITY * dt)
        self.bird_y += self.bird_vy * dt

        # 파이프 스폰(간격 랜덤)
        now_ms = pygame.time.get_ticks()
        if now_ms >= self.next_spawn_ms:
            self.spawn_pipe()
            self.next_spawn_ms = now_ms + self._compute_spawn_interval_ms()

        # 파이프 이동
        time_s = now_ms / 1000.0
        for pipe in self.pipes:
            pipe.x -= speed * dt
            # 움직이는 파이프는 갭 중심 y를 매 프레임 갱신(클램프 포함)
            if pipe.moving_amp > 0.0:
                y = pipe.current_gap_center_y(time_s)
                half_gap = pipe.gap_size // 2
                min_y = PIPE_GAP_CENTER_MIN_Y
                max_y = PIPE_GAP_CENTER_MAX_Y
                # 화면 밖으로 갭이 밀려나지 않도록
                y = max(min_y, min(max_y, y))
                # 위/아래 파이프가 역전되지 않도록(안전)
                y = max(half_gap + 40, min((SCREEN_HEIGHT - GROUND_HEIGHT) - half_gap - 40, y))
                pipe.gap_center_y = float(y)

        # 오프스크린 제거
        self.pipes = [p for p in self.pipes if not p.is_off_screen()]

        # 점수: 파이프 중앙을 지나가면 +1
        br = self.bird_rect()
        for pipe in self.pipes:
            # 새 사이즈/인셋에 관계없이 실제 충돌 박스 기준으로 “지나갔다”를 판정
            if not pipe.passed and pipe.x + pipe.width < br.left:
                pipe.passed = True
                self.score += 1

        # 충돌 판정
        if br.top <= CEILING_MARGIN:
            self.game_over_reason = "천장에 부딪혔어요!"
            self.state = "gameover"
            return
        if br.bottom >= SCREEN_HEIGHT - GROUND_HEIGHT:
            self.game_over_reason = "바닥에 떨어졌어요!"
            self.state = "gameover"
            return

        for pipe in self.pipes:
            if br.colliderect(pipe.rect_top()) or br.colliderect(pipe.rect_bottom()):
                self.game_over_reason = "뱀한테 먹혔어요!"
                self.state = "gameover"
                return

    # -------------------
    # 렌더링
    # -------------------
    def draw_background(self) -> None:
        if self.use_new_assets and self.bg_surface is not None:
            self.screen.blit(self.bg_surface, (0, 0))
            return

        self.screen.fill(BG_COLOR)

        # 간단한 구름(배경 스크롤)
        cloud_color = (235, 248, 255)
        base_x = -int(self.bg_scroll)
        for i in range(6):
            cx = base_x + i * 180 + 40
            cy = 80 + (i % 2) * 28
            pygame.draw.circle(self.screen, cloud_color, (cx, cy), 26)
            pygame.draw.circle(self.screen, cloud_color, (cx + 28, cy - 8), 18)
            pygame.draw.circle(self.screen, cloud_color, (cx + 52, cy + 6), 16)

    def _draw_obstacle_column(self, rect: pygame.Rect, *, facing: str) -> None:
        """장애물 컬럼을 이미지(머리/몸통)로 그린다. facing: 'down'(위 장애물) | 'up'(아래 장애물)."""
        assert self.obstacle_body is not None
        assert self.obstacle_head_up is not None
        assert self.obstacle_head_down is not None

        tile = PIPE_WIDTH_MIN
        x = rect.x

        # 타일 단위로 반복해서 그리면, 마지막 몸통 타일이 머리 영역까지 겹쳐 그려지는 경우가 있다.
        # 따라서 몸통을 그릴 때는 "머리 영역을 제외한 영역"으로 클리핑해서 절대 튀어나오지 않게 한다.
        prev_clip = self.screen.get_clip()
        try:
            if facing == "down":
                # 위 장애물: 아래쪽 끝에 head_down, 그 위로 body 타일링
                head_y = rect.bottom - tile
                body_area = pygame.Rect(rect.x, rect.y, rect.width, max(0, rect.height - tile))
                self.screen.set_clip(body_area)
                for y in range(rect.y, head_y, tile):
                    self.screen.blit(self.obstacle_body, (x, y))
                self.screen.set_clip(prev_clip)
                self.screen.blit(self.obstacle_head_down, (x, head_y))
            else:
                # 아래 장애물: 위쪽 끝에 head_up, 그 아래로 body 타일링
                head_y = rect.y
                self.screen.blit(self.obstacle_head_up, (x, head_y))
                body_area = pygame.Rect(rect.x, rect.y + tile, rect.width, max(0, rect.height - tile))
                self.screen.set_clip(body_area)
                for y in range(rect.y + tile, rect.bottom, tile):
                    self.screen.blit(self.obstacle_body, (x, y))
        finally:
            self.screen.set_clip(prev_clip)

    def draw_pipes(self) -> None:
        for pipe in self.pipes:
            rt = pipe.rect_top()
            rb = pipe.rect_bottom()

            if self.use_new_assets and self.obstacle_body and self.obstacle_head_up and self.obstacle_head_down:
                # 새 디자인: 뱀(장애물) 이미지로 렌더링
                # rect 높이가 타일보다 작으면 머리만 배치
                if rt.height >= PIPE_WIDTH_MIN:
                    self._draw_obstacle_column(rt, facing="down")
                else:
                    self.screen.blit(self.obstacle_head_down, (rt.x, max(0, rt.bottom - PIPE_WIDTH_MIN)))

                if rb.height >= PIPE_WIDTH_MIN:
                    self._draw_obstacle_column(rb, facing="up")
                else:
                    self.screen.blit(self.obstacle_head_up, (rb.x, rb.y))
                continue

            # 움직이는 파이프는 시각적으로 확실히 구분(파란색)해서 억까 느낌을 줄인다.
            if pipe.moving_amp > 0.0:
                pipe_fill = (92, 165, 255)
                pipe_edge = (28, 70, 160)
            else:
                pipe_fill = (64, 200, 110)
                pipe_edge = (20, 80, 40)

            pygame.draw.rect(self.screen, pipe_fill, rt, border_radius=10)
            pygame.draw.rect(self.screen, pipe_edge, rt, width=3, border_radius=10)
            pygame.draw.rect(self.screen, pipe_fill, rb, border_radius=10)
            pygame.draw.rect(self.screen, pipe_edge, rb, width=3, border_radius=10)

            # 입구 림(플래피 느낌)
            rim_h = 14
            rim_top = pygame.Rect(rt.x - 8, rt.bottom - rim_h, rt.width + 16, rim_h)
            rim_bottom = pygame.Rect(rb.x - 8, rb.top, rb.width + 16, rim_h)
            pygame.draw.rect(self.screen, pipe_fill, rim_top, border_radius=8)
            pygame.draw.rect(self.screen, pipe_edge, rim_top, width=3, border_radius=8)
            pygame.draw.rect(self.screen, pipe_fill, rim_bottom, border_radius=8)
            pygame.draw.rect(self.screen, pipe_edge, rim_bottom, width=3, border_radius=8)

    def draw_ground(self) -> None:
        if GROUND_HEIGHT <= 0:
            return
        ground_y = SCREEN_HEIGHT - GROUND_HEIGHT
        pygame.draw.rect(self.screen, (235, 220, 170), pygame.Rect(0, ground_y, SCREEN_WIDTH, GROUND_HEIGHT))
        pygame.draw.rect(self.screen, (120, 90, 60), pygame.Rect(0, ground_y, SCREEN_WIDTH, GROUND_HEIGHT), width=3)
        # 간단한 타일 느낌
        tile_w = 48
        offset = int(self.ground_scroll)
        for x in range(-tile_w, SCREEN_WIDTH + tile_w, tile_w):
            xx = x - offset
            pygame.draw.rect(
                self.screen,
                (225, 206, 150),
                pygame.Rect(xx, ground_y + 18, tile_w - 8, 20),
                border_radius=6,
            )

    def draw_bird(self) -> None:
        # 속도에 따라 약간 기울기
        angle = max(-28.0, min(42.0, -self.bird_vy * 0.06))
        cx, cy = BIRD_X, int(self.bird_y)

        if self.use_new_assets and self.bird_surface is not None:
            rotated = pygame.transform.rotate(self.bird_surface, angle)
            r = rotated.get_rect(center=(cx, cy))
            self.screen.blit(rotated, r)
            return

        # 폴백: 간단한 도형 새
        body = pygame.Surface((BIRD_SIZE + 10, BIRD_SIZE + 10), pygame.SRCALPHA)
        pygame.draw.circle(body, (255, 220, 60), (BIRD_SIZE // 2 + 5, BIRD_SIZE // 2 + 5), BIRD_SIZE // 2)
        pygame.draw.circle(body, (40, 40, 40), (BIRD_SIZE // 2 + 10, BIRD_SIZE // 2 - 5), 3)  # 눈
        pygame.draw.polygon(
            body,
            (255, 140, 60),
            [
                (BIRD_SIZE // 2 + 18, BIRD_SIZE // 2 + 6),
                (BIRD_SIZE // 2 + 30, BIRD_SIZE // 2 + 10),
                (BIRD_SIZE // 2 + 18, BIRD_SIZE // 2 + 14),
            ],
        )
        rotated = pygame.transform.rotate(body, angle)
        r = rotated.get_rect(center=(cx, cy))
        self.screen.blit(rotated, r)

    def draw_score(self) -> None:
        rendered = self.font_big.render(str(self.score), True, (30, 30, 30))
        rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, 130))
        self.screen.blit(rendered, rect)

    def draw_title(self) -> None:
        self.draw_background()
        self.draw_ground()
        title = self.font_title.render("날아부리", True, (20, 20, 20))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 220)))
        subtitle = self.font.render("장애물을 피하며 꽁짜 햄버거를 먹으러 가자!", True, (60, 60, 60))
        self.screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 262)))

        for idx, (rect, label) in enumerate([(self.btn_start, "게임시작"), (self.btn_howto, "게임방법")]):
            _draw_card(self.screen, rect)
            text_color = (20, 20, 20) if idx == self.menu_index else (90, 90, 90)
            rendered = self.font.render(label, True, text_color)
            self.screen.blit(rendered, rendered.get_rect(center=rect.center))
        self.screen.blit(self.font_small.render("ESC: 종료", True, (70, 70, 70)), (14, 34))
        # 미리보기 새
        self.draw_bird()

    def draw_howto(self) -> None:
        self.draw_background()
        self.draw_ground()
        title = self.font_title.render("게임방법", True, (20, 20, 20))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 150)))

        card = pygame.Rect((SCREEN_WIDTH - 520) // 2, 190, 520, 240)
        _draw_card(self.screen, card)

        lines = [
            "스페이스/클릭/아무 키로 날개짓!",
            "장애물에 부딪히면 게임오버예요.",
            "",
            "ENTER/클릭: 뒤로",
        ]
        y = card.top + 40
        for line in lines:
            if line == "":
                y += 12
                continue
            surf = self.font.render(line, True, (50, 50, 50))
            self.screen.blit(surf, surf.get_rect(center=(card.centerx, y)))
            y += 34

        _draw_card(self.screen, self.btn_back)
        back = self.font.render("뒤로", True, (20, 20, 20))
        self.screen.blit(back, back.get_rect(center=self.btn_back.center))

    def draw_play(self) -> None:
        self.draw_background()
        self.draw_pipes()
        self.draw_ground()
        self.draw_bird()
        self.draw_score()

    def draw_gameover(self) -> None:
        self.draw_play()
        draw_game_over_ui(
            self.screen,
            font_title=self.font_title,
            font=self.font,
            font_small=self.font_small,
            reason=self.game_over_reason or "부딪혔어요!",
            score=self.score,
            hint="닉네임 입력 후 ENTER로 저장  |  ESC: 종료  |  R: 재시작",
        )
        draw_input_box(surface=self.screen, font=self.font_small, label="닉네임", value=self.lb_nickname, y=360)
        if self.lb_status:
            draw_text = self.font_small.render(self.lb_status, True, (60, 60, 60))
            self.screen.blit(draw_text, draw_text.get_rect(center=(SCREEN_WIDTH // 2, 412)))
        if self.lb_top:
            draw_leaderboard_list(
                self.screen,
                font=self.font_small,
                title="TOP 5",
                entries=[(e.nickname, e.score) for e in self.lb_top],
                y=440,
            )

    # -------------------
    # 메인 루프
    # -------------------
    def run(self, quit_on_exit: bool = True) -> None:
        while self.running:
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        continue

                    if self.state == "howto":
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.state = "title"
                        continue

                    if self.state == "title":
                        if event.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_index = (self.menu_index + 1) % 2
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            self.menu_index = (self.menu_index - 1) % 2
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if self.menu_index == 0:
                                self.state = "play"
                                self.reset_run()
                            else:
                                self.state = "howto"
                        continue

                    if self.state == "gameover":
                        if event.key == pygame.K_r:
                            self.lb_nickname = ""
                            self.lb_status = None
                            self.lb_top = []
                            self.lb_submitted = False
                            self.state = "play"
                            self.reset_run()
                            continue
                        if event.key == pygame.K_RETURN:
                            if not self.lb_submitted:
                                nick = self.lb_nickname
                                self.lb_status = "저장 중..."

                                def _cb(err: Optional[str], entries: Optional[list[LeaderboardEntry]]) -> None:
                                    if err:
                                        self.lb_status = f"저장 실패: {err}"
                                        return
                                    self.lb_status = "저장 완료!"
                                    self.lb_submitted = True
                                    self.lb_top = entries or []

                                submit_and_fetch_async("fly", nick, self.score, callback=_cb)
                            else:
                                self.state = "title"
                            continue
                        if event.key == pygame.K_BACKSPACE:
                            self.lb_nickname = self.lb_nickname[:-1]
                            continue
                        if event.unicode and len(self.lb_nickname) < 12 and event.unicode.isprintable():
                            self.lb_nickname += event.unicode
                            continue

                    # 플래피는 “아무 키/스페이스”가 곧 플랩
                    self.flap()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if self.state == "title":
                        if self.btn_start.collidepoint(mx, my):
                            self.menu_index = 0
                            self.state = "play"
                            self.reset_run()
                        elif self.btn_howto.collidepoint(mx, my):
                            self.menu_index = 1
                            self.state = "howto"
                    elif self.state == "howto":
                        if self.btn_back.collidepoint(mx, my):
                            self.state = "title"
                        else:
                            self.state = "title"
                    else:
                        self.flap()

            if self.state == "play":
                self.update_play(dt)

            if self.state == "title":
                self.draw_title()
            elif self.state == "howto":
                self.draw_howto()
            elif self.state == "play":
                self.draw_play()
            elif self.state == "gameover":
                self.draw_gameover()

            pygame.display.flip()

        if quit_on_exit:
            pygame.quit()


def run_game(*, quit_on_exit: bool = True) -> None:
    FlappyBirdGame().run(quit_on_exit=quit_on_exit)


if __name__ == "__main__":
    run_game()


