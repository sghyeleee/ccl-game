from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame


SCREEN_WIDTH = 480
SCREEN_HEIGHT = 640
FPS = 60

BG_COLOR = (132, 205, 255)
TEXT_COLOR = (20, 20, 20)

GRAVITY = 1700.0
# 스페이스/탭 플랩이 과하게 튀어오르지 않도록 점프 힘을 완화
JUMP_VELOCITY = -430.0
MAX_FALL_SPEED = 900.0

BIRD_X = 140
BIRD_RADIUS = 16

GROUND_HEIGHT = 90
CEILING_MARGIN = 8

# 파이프 다양화(재미를 위해 고정값 제거)
PIPE_WIDTH_MIN = 62
PIPE_WIDTH_MAX = 86

PIPE_GAP_MIN = 140
PIPE_GAP_MAX = 216

# 갭 중심 y 범위(파이프마다 gap이 달라지므로, 실제 범위는 계산 시 gap/2를 고려)
PIPE_GAP_CENTER_MIN_Y = 150
PIPE_GAP_CENTER_MAX_Y = SCREEN_HEIGHT - GROUND_HEIGHT - 150

PIPE_SPEED_BASE = 220.0
PIPE_SPEED_PER_SCORE = 2.2
PIPE_SPAWN_INTERVAL_MIN_MS = 1050
PIPE_SPAWN_INTERVAL_MAX_MS = 1550

BEST_SCORE_FILE = Path(__file__).resolve().parent / ".flappy_best_score"

FONT_CANDIDATES = [
    "Pretendard",
    "Apple SD Gothic Neo",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Arial Unicode MS",
]


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in FONT_CANDIDATES:
        font_path = pygame.font.match_font(name, bold=bold)
        if font_path:
            return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(None, size, bold=bold)


def load_best_score() -> int:
    try:
        if BEST_SCORE_FILE.exists():
            return int(BEST_SCORE_FILE.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        pass
    return 0


def save_best_score(score: int) -> None:
    try:
        BEST_SCORE_FILE.write_text(str(score), encoding="utf-8")
    except Exception:
        pass


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
        pygame.display.set_caption("플래피 버드")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = get_font(44, bold=True)
        self.font_big = get_font(56, bold=True)
        self.font = get_font(20)
        self.font_small = get_font(16)

        self.state: str = "title"  # title | play | gameover
        self.running = True

        self.best_score = load_best_score()

        self.reset_run()

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

        # 일부는 “움직이는 갭” 타입으로 변주
        # 움직이는 파이프는 “변주” 용도라 초반엔 빼고, 속도/진폭도 과하지 않게 제한한다.
        # (너무 빠르면 사실상 확정 사망 패턴이 나오기 쉬움)
        if self.score < 5:
            moving_chance = 0.0
        else:
            moving_chance = min(0.16, 0.08 + (self.score - 5) * 0.01)

        if random.random() < moving_chance:
            # 갭이 좁을수록 움직임은 더 “느리고 작게”
            base_amp = random.uniform(12.0, 28.0)
            amp_cap = max(10.0, (gap - 120) * 0.35)
            amp = min(base_amp, amp_cap)

            speed = random.uniform(0.6, 1.05)  # radians/sec (이전보다 확실히 느리게)
            phase = random.uniform(0.0, math.tau)
        else:
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
        return pygame.Rect(BIRD_X - BIRD_RADIUS, int(self.bird_y) - BIRD_RADIUS, BIRD_RADIUS * 2, BIRD_RADIUS * 2)

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
        for pipe in self.pipes:
            if not pipe.passed and pipe.x + pipe.width < BIRD_X - BIRD_RADIUS:
                pipe.passed = True
                self.score += 1

        # 충돌 판정
        br = self.bird_rect()
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
                self.game_over_reason = "파이프에 부딪혔어요!"
                self.state = "gameover"
                return

    # -------------------
    # 렌더링
    # -------------------
    def draw_background(self) -> None:
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

    def draw_pipes(self) -> None:
        for pipe in self.pipes:
            # 움직이는 파이프는 시각적으로 확실히 구분(파란색)해서 억까 느낌을 줄인다.
            if pipe.moving_amp > 0.0:
                pipe_fill = (92, 165, 255)
                pipe_edge = (28, 70, 160)
            else:
                pipe_fill = (64, 200, 110)
                pipe_edge = (20, 80, 40)

            rt = pipe.rect_top()
            rb = pipe.rect_bottom()
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
        body = pygame.Surface((BIRD_RADIUS * 2 + 10, BIRD_RADIUS * 2 + 10), pygame.SRCALPHA)
        pygame.draw.circle(body, (255, 220, 60), (BIRD_RADIUS + 5, BIRD_RADIUS + 5), BIRD_RADIUS)
        pygame.draw.circle(body, (40, 40, 40), (BIRD_RADIUS + 10, BIRD_RADIUS + 1), 3)  # 눈
        pygame.draw.polygon(
            body,
            (255, 140, 60),
            [
                (BIRD_RADIUS + 18, BIRD_RADIUS + 6),
                (BIRD_RADIUS + 30, BIRD_RADIUS + 10),
                (BIRD_RADIUS + 18, BIRD_RADIUS + 14),
            ],
        )
        rotated = pygame.transform.rotate(body, angle)
        r = rotated.get_rect(center=(cx, cy))
        self.screen.blit(rotated, r)

    def draw_score(self) -> None:
        rendered = self.font_big.render(str(self.score), True, (30, 30, 30))
        rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, 130))
        self.screen.blit(rendered, rect)
        self.screen.blit(self.font_small.render(f"최고: {self.best_score}", True, (50, 50, 50)), (14, 10))

    def draw_title(self) -> None:
        self.draw_background()
        self.draw_ground()
        title = self.font_title.render("플래피 버드", True, (20, 20, 20))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 220)))
        self.screen.blit(
            self.font.render("스페이스/아무 키/클릭/터치로 시작", True, (40, 40, 40)),
            (80, 280),
        )
        self.screen.blit(self.font_small.render("ESC: 종료", True, (70, 70, 70)), (14, 34))
        # 미리보기 새
        self.draw_bird()

    def draw_play(self) -> None:
        self.draw_background()
        self.draw_pipes()
        self.draw_ground()
        self.draw_bird()
        self.draw_score()

    def draw_gameover(self) -> None:
        self.draw_play()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        card = pygame.Rect(46, 190, SCREEN_WIDTH - 92, 250)
        pygame.draw.rect(self.screen, (255, 255, 255), card, border_radius=18)
        pygame.draw.rect(self.screen, (40, 40, 40), card, width=2, border_radius=18)

        self.screen.blit(self.font_title.render("게임오버", True, TEXT_COLOR), (card.x + 120, card.y + 34))
        reason = self.game_over_reason or "부딪혔어요!"
        self.screen.blit(self.font.render(reason, True, (60, 60, 60)), (card.x + 92, card.y + 96))

        self.screen.blit(self.font_big.render(str(self.score), True, (30, 30, 30)), (card.x + 185, card.y + 138))
        self.screen.blit(
            self.font_small.render(f"최고 기록: {self.best_score}", True, (70, 70, 70)),
            (card.x + 150, card.y + 202),
        )
        self.screen.blit(
            self.font_small.render("스페이스/클릭: 재시작   ENTER: 타이틀", True, (70, 70, 70)),
            (card.x + 36, card.y + 224),
        )

    # -------------------
    # 메인 루프
    # -------------------
    def run(self) -> None:
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

                    if self.state == "gameover" and event.key == pygame.K_RETURN:
                        self.state = "title"
                        continue

                    # 플래피는 “아무 키/스페이스”가 곧 플랩
                    self.flap()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.flap()

            if self.state == "play":
                self.update_play(dt)

            if self.state == "gameover":
                if self.score > self.best_score:
                    self.best_score = self.score
                    save_best_score(self.best_score)

            if self.state == "title":
                self.draw_title()
            elif self.state == "play":
                self.draw_play()
            elif self.state == "gameover":
                self.draw_gameover()

            pygame.display.flip()

        pygame.quit()


def run_game() -> None:
    FlappyBirdGame().run()


if __name__ == "__main__":
    run_game()


