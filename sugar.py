# sugar_stack.py
# Pygame “각설탕쌓기” (원버튼 타이밍 + 카메라 클램프 스크롤로 상단 공간 유지)

import math
import sys
from dataclasses import dataclass

import pygame


# ---------------------------
# Config
# ---------------------------
WIDTH, HEIGHT = 800, 600
FPS = 60

GROUND_Y = 540

BLOCK_W = 76
BLOCK_H = 42

# 요정은 화면에서 고정
CARRIER_SCREEN_Y = 120
CARRIER_MARGIN = 70

# "탑 최상단(블록의 top y)"이 화면에서 이 값보다 위로 올라가지 않게 강제
# => TOP_ANCHOR가 330이면, 최상단은 항상 y=330 이하로만 보임(더 위로 못 감)
TOP_ANCHOR_SCREEN_Y = HEIGHT // 2  # "항상 화면 반 정도 거리" 느낌이면 대략 절반~0.6 추천
# TOP_ANCHOR_SCREEN_Y = int(HEIGHT * 0.60)

GRAVITY = 2200.0  # px/s^2
MAX_FALL_SPEED = 2200.0

MIN_OVERLAP_RATIO = 0.20
SUPPORT_RATIO = 0.47

CARRIER_SPEED_BASE = 220.0
CARRIER_SPEED_INC = 11.0
CARRIER_SPEED_MAX = 780.0

WOBBLE_MAX_DEG = 5.0
WOBBLE_SMOOTH = 0.08


# ---------------------------
# Data
# ---------------------------
@dataclass
class Block:
    x: float
    y: float
    w: int = BLOCK_W
    h: int = BLOCK_H

    @property
    def center_x(self) -> float:
        return self.x + self.w / 2


@dataclass
class FallingBlock:
    x: float
    y: float
    vy: float = 0.0
    w: int = BLOCK_W
    h: int = BLOCK_H

    @property
    def center_x(self) -> float:
        return self.x + self.w / 2


# ---------------------------
# Helpers
# ---------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def draw_text(surf, text, font, x, y, color=(20, 20, 20), center=True):
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = (x, y)
    else:
        r.topleft = (x, y)
    surf.blit(img, r)


def rounded_rect(surf, rect, color, radius=10, border=0, border_color=(0, 0, 0)):
    if border > 0:
        pygame.draw.rect(surf, border_color, rect, border_radius=radius)
        inner = rect.inflate(-border * 2, -border * 2)
        pygame.draw.rect(surf, color, inner, border_radius=max(0, radius - border))
    else:
        pygame.draw.rect(surf, color, rect, border_radius=radius)


# ---------------------------
# Game
# ---------------------------
class SugarStackGame:
    STATE_TITLE = "TITLE"
    STATE_HOWTO = "HOWTO"
    STATE_PLAY = "PLAY"
    STATE_GAMEOVER = "GAMEOVER"

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("각설탕쌓기 (Pygame)")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_xl = pygame.font.SysFont(None, 64)
        self.font_l = pygame.font.SysFont(None, 36)
        self.font_m = pygame.font.SysFont(None, 26)
        self.font_s = pygame.font.SysFont(None, 20)

        self.state = self.STATE_TITLE
        self.best = 0
        self.reset_play()

    # ---------- Camera (screen offset) ----------
    # camera_y는 "월드 -> 화면 변환 시 더해주는 오프셋" (screen_y = world_y + camera_y)
    def world_to_screen_y(self, wy: float) -> int:
        return int(wy + self.camera_y)

    def screen_to_world_y(self, sy: float) -> float:
        return sy - self.camera_y

    def carrier_world_y(self) -> float:
        # 요정은 화면 고정이므로, 월드에서는 카메라 오프셋만큼 역변환
        return self.screen_to_world_y(CARRIER_SCREEN_Y)

    def clamp_camera_to_top(self):
        """
        최상단 블록의 화면 y가 TOP_ANCHOR보다 '위로' 올라가면(값이 더 작으면)
        카메라를 즉시 보정해서 top_screen_y == TOP_ANCHOR가 되게 만든다.
        => 절대 요정 영역까지 침범하지 않음(강제 보장)
        """
        top_world_y = self.stack[-1].y
        top_screen_y = top_world_y + self.camera_y  # world_to_screen_y와 동일한 계산
        if top_screen_y < TOP_ANCHOR_SCREEN_Y:
            self.camera_y += (TOP_ANCHOR_SCREEN_Y - top_screen_y)

        # 초반엔 카메라가 음수로 내려가면 바닥이 위로 올라가므로 막아줌
        if self.camera_y < 0:
            self.camera_y = 0.0

    def reset_play(self):
        base_x = WIDTH / 2 - BLOCK_W / 2
        base_y = GROUND_Y - BLOCK_H  # 월드 기준
        self.stack = [Block(base_x, base_y)]

        self.score = 1
        self.gameover_reason = ""

        self.carrier_x = WIDTH / 2
        self.carrier_dir = 1

        self.falling = None

        self.wobble_deg = 0.0
        self.target_wobble_deg = 0.0

        self.camera_y = 0.0  # 시작은 화면과 월드가 동일

    def carrier_speed(self):
        v = CARRIER_SPEED_BASE + (self.score - 1) * CARRIER_SPEED_INC
        return clamp(v, CARRIER_SPEED_BASE, CARRIER_SPEED_MAX)

    def top_y(self):
        return self.stack[-1].y - BLOCK_H

    def new_attached_block_pos(self):
        # "항상 화면에서 요정 아래"에 보이도록 월드 y를 계산
        x = self.carrier_x - BLOCK_W / 2
        y = self.carrier_world_y() + 18
        return x, y

    def handle_action(self):
        if self.state == self.STATE_TITLE:
            self.reset_play()
            self.state = self.STATE_PLAY
            return

        if self.state == self.STATE_HOWTO:
            self.state = self.STATE_TITLE
            return

        if self.state == self.STATE_GAMEOVER:
            self.reset_play()
            self.state = self.STATE_PLAY
            return

        if self.state == self.STATE_PLAY:
            if self.falling is not None:
                return
            x, y = self.new_attached_block_pos()
            self.falling = FallingBlock(x, y, vy=0.0)

    def compute_center_of_mass_x(self):
        return sum(b.center_x for b in self.stack) / len(self.stack)

    def check_collapse_by_support(self):
        base = self.stack[0]
        com_x = self.compute_center_of_mass_x()
        base_center = base.center_x
        support_half = (base.w / 2) * SUPPORT_RATIO
        return abs(com_x - base_center) > support_half

    def place_block(self, falling: FallingBlock):
        prev = self.stack[-1]
        dx = falling.center_x - prev.center_x
        overlap = BLOCK_W - abs(dx)

        if overlap <= BLOCK_W * MIN_OVERLAP_RATIO:
            self.gameover_reason = "겹침이 너무 적어서 무너졌어요"
            return False

        nx = falling.x
        ny = self.top_y()
        self.stack.append(Block(nx, ny))
        self.score += 1

        self.target_wobble_deg = clamp((dx / BLOCK_W) * WOBBLE_MAX_DEG, -WOBBLE_MAX_DEG, WOBBLE_MAX_DEG)

        if self.check_collapse_by_support():
            self.gameover_reason = "중심을 잃고 무너졌어요"
            return False

        # 블록이 추가된 직후 바로 카메라 클램프(겹침 방지 핵심)
        self.clamp_camera_to_top()
        return True

    def update_play(self, dt):
        # 캐리어 이동(화면 x축)
        speed = self.carrier_speed()
        self.carrier_x += self.carrier_dir * speed * dt

        if self.carrier_x < CARRIER_MARGIN:
            self.carrier_x = CARRIER_MARGIN
            self.carrier_dir *= -1
        elif self.carrier_x > WIDTH - CARRIER_MARGIN:
            self.carrier_x = WIDTH - CARRIER_MARGIN
            self.carrier_dir *= -1

        # 낙하(월드 좌표)
        if self.falling is not None:
            self.falling.vy = clamp(self.falling.vy + GRAVITY * dt, -MAX_FALL_SPEED, MAX_FALL_SPEED)
            self.falling.y += self.falling.vy * dt

            land_y = self.top_y()
            if self.falling.y >= land_y:
                ok = self.place_block(self.falling)
                self.falling = None

                if not ok:
                    self.best = max(self.best, self.score)
                    self.state = self.STATE_GAMEOVER
                else:
                    self.best = max(self.best, self.score)

        # 흔들림(시각)
        self.wobble_deg += (self.target_wobble_deg - self.wobble_deg) * WOBBLE_SMOOTH

        # 매 프레임 클램프(혹시라도 위로 튀는 케이스 방지)
        self.clamp_camera_to_top()

    # ---------- Draw ----------
    def draw_background(self):
        self.screen.fill((235, 245, 255))
        pygame.draw.rect(self.screen, (220, 240, 255), (0, 0, WIDTH, HEIGHT // 2))
        pygame.draw.rect(self.screen, (245, 250, 255), (0, HEIGHT // 2, WIDTH, HEIGHT // 2))

        ground_screen_y = self.world_to_screen_y(GROUND_Y)
        if ground_screen_y < HEIGHT:
            pygame.draw.rect(self.screen, (80, 90, 110), (0, ground_screen_y, WIDTH, HEIGHT - ground_screen_y))
            pygame.draw.rect(self.screen, (60, 70, 90), (0, ground_screen_y, WIDTH, 6))

    def draw_block_rect(self, rect: pygame.Rect):
        rounded_rect(
            self.screen,
            rect,
            color=(255, 255, 255),
            radius=10,
            border=2,
            border_color=(210, 220, 235),
        )
        pygame.draw.line(self.screen, (240, 245, 255),
                         (rect.left + 8, rect.top + 10),
                         (rect.right - 8, rect.top + 10), 2)

    def draw_stack(self):
        wobble = math.sin(pygame.time.get_ticks() * 0.003) * (self.wobble_deg * 1.2)

        for i, b in enumerate(self.stack):
            factor = (i / max(1, len(self.stack) - 1)) if len(self.stack) > 1 else 0
            dx = wobble * factor

            sx = int(b.x + dx)
            sy = self.world_to_screen_y(b.y)
            rect = pygame.Rect(sx, sy, b.w, b.h)

            if rect.bottom < -120 or rect.top > HEIGHT + 120:
                continue

            self.draw_block_rect(rect)

    def draw_carrier(self):
        # 요정은 화면 고정 y
        x = int(self.carrier_x)
        y = CARRIER_SCREEN_Y

        pygame.draw.ellipse(self.screen, (200, 230, 255), (x - 28, y - 10, 22, 18))
        pygame.draw.ellipse(self.screen, (200, 230, 255), (x + 6, y - 10, 22, 18))

        pygame.draw.circle(self.screen, (255, 220, 120), (x, y), 12)
        pygame.draw.circle(self.screen, (255, 200, 90), (x, y), 12, 2)

        pygame.draw.circle(self.screen, (30, 30, 30), (x - 4, y - 2), 2)
        pygame.draw.circle(self.screen, (30, 30, 30), (x + 4, y - 2), 2)

    def draw_attached_or_falling(self):
        if self.state != self.STATE_PLAY:
            return

        if self.falling is None:
            x, y = self.new_attached_block_pos()  # 월드
            rect = pygame.Rect(int(x), self.world_to_screen_y(y), BLOCK_W, BLOCK_H)
            self.draw_block_rect(rect)
        else:
            rect = pygame.Rect(int(self.falling.x), self.world_to_screen_y(self.falling.y), BLOCK_W, BLOCK_H)
            self.draw_block_rect(rect)

    def draw_hud(self):
        draw_text(self.screen, f"{self.score}", self.font_xl, WIDTH // 2, 70, color=(30, 40, 55))
        draw_text(self.screen, f"BEST {self.best}", self.font_s, WIDTH - 90, 22, color=(40, 60, 80))
        draw_text(self.screen, f"SPEED {int(self.carrier_speed())}", self.font_s, 90, 22, color=(40, 60, 80))

        # 디버그(원하면 주석 해제)
        # top_world = self.stack[-1].y
        # top_screen = int(top_world + self.camera_y)
        # draw_text(self.screen, f"cam={int(self.camera_y)} topS={top_screen}", self.font_s, WIDTH//2, 22, color=(120, 80, 80))

    def draw_title(self):
        self.draw_background()
        draw_text(self.screen, "각설탕쌓기", self.font_xl, WIDTH // 2, 170, color=(30, 40, 55))
        draw_text(self.screen, "원버튼 타이밍 게임", self.font_m, WIDTH // 2, 220, color=(60, 80, 110))

        start_rect = pygame.Rect(WIDTH // 2 - 140, 290, 280, 56)
        howto_rect = pygame.Rect(WIDTH // 2 - 140, 360, 280, 56)

        rounded_rect(self.screen, start_rect, (255, 255, 255), radius=14, border=2, border_color=(210, 220, 235))
        rounded_rect(self.screen, howto_rect, (255, 255, 255), radius=14, border=2, border_color=(210, 220, 235))

        draw_text(self.screen, "게임 시작 (SPACE/CLICK)", self.font_m, start_rect.centerx, start_rect.centery, color=(30, 40, 55))
        draw_text(self.screen, "게임 방법", self.font_m, howto_rect.centerx, howto_rect.centery, color=(30, 40, 55))

        draw_text(self.screen, "스페이스/클릭으로 바로 시작해도 돼요", self.font_s, WIDTH // 2, 460, color=(70, 90, 120))
        draw_text(self.screen, f"BEST {self.best}", self.font_m, WIDTH // 2, 520, color=(30, 40, 55))

        return start_rect, howto_rect

    def draw_howto(self):
        self.draw_background()
        draw_text(self.screen, "게임 방법", self.font_l, WIDTH // 2, 140, color=(30, 40, 55))

        lines = [
            "스페이스/클릭/터치를 하면 각설탕이 떨어집니다.",
            "각설탕을 높이 쌓을수록 요정이 더 빠르게 움직여요.",
            "중심을 잃고 탑이 무너지면 게임오버!",
            "",
            "아무 키나 누르면 타이틀로 돌아갑니다.",
        ]
        y = 220
        for ln in lines:
            draw_text(self.screen, ln, self.font_m, WIDTH // 2, y, color=(50, 70, 100))
            y += 40

    def draw_gameover(self):
        self.draw_background()
        self.draw_stack()

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 30, 40, 160))
        self.screen.blit(overlay, (0, 0))

        draw_text(self.screen, "GAME OVER", self.font_xl, WIDTH // 2, 190, color=(255, 255, 255))
        draw_text(self.screen, f"점수: {self.score}", self.font_l, WIDTH // 2, 250, color=(255, 255, 255))
        if self.gameover_reason:
            draw_text(self.screen, self.gameover_reason, self.font_m, WIDTH // 2, 292, color=(220, 235, 255))
        draw_text(self.screen, f"BEST: {self.best}", self.font_m, WIDTH // 2, 340, color=(255, 255, 255))
        draw_text(self.screen, "SPACE/CLICK 로 재시작", self.font_m, WIDTH // 2, 410, color=(255, 255, 255))
        draw_text(self.screen, "ESC 로 타이틀", self.font_s, WIDTH // 2, 450, color=(210, 220, 235))

    def run(self):
        start_rect = None
        howto_rect = None

        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = self.STATE_TITLE
                    else:
                        self.handle_action()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state == self.STATE_TITLE and start_rect and howto_rect:
                        mx, my = event.pos
                        if start_rect.collidepoint(mx, my):
                            self.handle_action()
                        elif howto_rect.collidepoint(mx, my):
                            self.state = self.STATE_HOWTO
                        else:
                            self.handle_action()
                    else:
                        self.handle_action()

            if self.state == self.STATE_PLAY:
                self.update_play(dt)

            if self.state == self.STATE_TITLE:
                start_rect, howto_rect = self.draw_title()
            elif self.state == self.STATE_HOWTO:
                self.draw_howto()
            elif self.state == self.STATE_PLAY:
                self.draw_background()
                self.draw_stack()
                self.draw_carrier()
                self.draw_attached_or_falling()
                self.draw_hud()

                if self.score <= 4 and self.falling is None:
                    draw_text(self.screen, "SPACE/CLICK 로 떨어뜨리기", self.font_s, WIDTH // 2, 110, color=(80, 100, 130))
            elif self.state == self.STATE_GAMEOVER:
                self.draw_gameover()

            pygame.display.flip()


if __name__ == "__main__":
    SugarStackGame().run()
