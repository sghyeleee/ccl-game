from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pygame


# =========================
# 기본 설정
# =========================
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
FPS = 60

BG_COLOR = (210, 235, 255)
TEXT_COLOR = (25, 25, 25)
SHADOW = (0, 0, 0, 90)

CUBE_SIZE = 54
BASE_WIDTH = 260
BASE_HEIGHT = 22

GRAVITY = 1400.0
# 화면 내 고정 위치(카메라 적용 전, 스크린 좌표 기준)
CARRIER_SCREEN_Y = 86
HELD_CUBE_SCREEN_Y = 130

# 스택 최상단이 이 y(스크린)보다 위로 올라가려 하면 카메라가 위로 스크롤된다.
# (요정/스택이 겹치지 않도록 “화면 절반 정도 거리” 확보 목적)
STACK_TOP_MIN_SCREEN_Y = int(SCREEN_HEIGHT * 0.58)

# “요정 좌우 이동 가속” 느낌: 방향이 바뀔 때마다 속도가 0에서 다시 가속
CARRIER_ACCEL_BASE = 520.0
CARRIER_ACCEL_PER_LEVEL = 26.0
CARRIER_MAX_SPEED_BASE = 220.0
CARRIER_MAX_SPEED_PER_LEVEL = 10.0

# 안정도(세미-물리) 튜닝
MIN_OVERLAP_RATIO_FOR_SAFE = 0.62  # 이 이상이면 거의 흔들림 없이 안정
MIN_OVERLAP_RATIO_TO_PLACE = 0.20  # 이 미만이면 사실상 지지 불가 -> 즉시 붕괴
INSTABILITY_GAIN_MAX = 2.8
INSTABILITY_DECAY_PER_SEC = 1.4
TILT_GROWTH_PER_SEC = 1.25
# 기존 값(18도)은 시각적으로는 거의 안 기울어 보여도 게임오버가 나기 쉬웠다.
# 체감과 일치하도록 임계값을 조금 완화한다.
TILT_THRESHOLD_DEG = 28.0  # 탑이 중심을 잃는 기준(각도)

# “정확히 쌓았다” 체감을 살리기 위한 스냅(몇 px 이내면 자동 정렬)
SNAP_TO_TARGET_PX = 4

# COM 기반 보조 판정: 무게중심이 베이스 지지면 밖이면 즉시 게임오버
COM_MARGIN_PX = 6

BEST_SCORE_FILE = Path(__file__).resolve().parent / ".sugar_best_score"

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
        # 저장 실패는 게임 진행에 치명적이지 않으므로 무시
        pass


def draw_text_center(surface: pygame.Surface, font: pygame.font.Font, text: str, y: int, color=TEXT_COLOR) -> None:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, y))
    surface.blit(rendered, rect)


def draw_card(surface: pygame.Surface, rect: pygame.Rect) -> None:
    shadow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
    pygame.draw.rect(shadow, SHADOW, shadow.get_rect(), border_radius=18)
    surface.blit(shadow, (rect.x - 5, rect.y + 6))
    pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=18)
    pygame.draw.rect(surface, (40, 40, 40), rect, width=2, border_radius=18)


@dataclass
class Cube:
    rect: pygame.Rect
    is_falling: bool = False
    vel_y: float = 0.0

    def update(self, dt: float) -> None:
        if not self.is_falling:
            return
        self.vel_y += GRAVITY * dt
        self.rect.y += int(self.vel_y * dt)


class SugarStackGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("각설탕 쌓기")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = get_font(40, bold=True)
        self.font_big = get_font(54, bold=True)
        self.font = get_font(20)
        self.font_small = get_font(16)

        self.state: str = "title"  # title | howto | play | gameover
        self.running = True

        self.best_score = load_best_score()

        # UI 버튼
        self.btn_start = pygame.Rect(110, 320, 180, 54)
        self.btn_howto = pygame.Rect(110, 388, 180, 54)
        self.btn_back = pygame.Rect(18, 18, 86, 40)

        self.reset_game()

    # -------------------------
    # 게임 리셋/스폰
    # -------------------------
    def reset_game(self) -> None:
        # 월드 좌표계의 카메라(스크린 상단이 바라보는 월드 y)
        # 시작 시엔 0으로 두어 월드=스크린처럼 보이게 한다.
        self.camera_y = 0.0

        base_y = SCREEN_HEIGHT - 64
        base_x = (SCREEN_WIDTH - BASE_WIDTH) // 2
        self.base_rect = pygame.Rect(base_x, base_y, BASE_WIDTH, BASE_HEIGHT)

        # “탑”은 배치된 큐브 리스트(아래→위)
        first_cube_x = (SCREEN_WIDTH - CUBE_SIZE) // 2
        first_cube_y = self.base_rect.top - CUBE_SIZE
        self.stack: list[Cube] = [Cube(pygame.Rect(first_cube_x, first_cube_y, CUBE_SIZE, CUBE_SIZE), is_falling=False)]

        self.level = 1
        self.score = 1  # 첫 큐브를 1층으로 취급

        # 불안정/기울기(세미-물리)
        self.instability = 0.0
        self.tilt_deg = 0.0

        # 캐리어(요정) 이동 상태
        self.carrier_x = float((SCREEN_WIDTH - CUBE_SIZE) // 2)
        self.carrier_dir = 1
        self.carrier_speed = 0.0

        # 현재 들고 있는 큐브
        self.held_cube = Cube(
            pygame.Rect(int(self.carrier_x), int(self.camera_y + HELD_CUBE_SCREEN_Y), CUBE_SIZE, CUBE_SIZE),
            is_falling=False,
        )

        self.game_over_reason: Optional[str] = None

    def spawn_held_cube(self) -> None:
        self.held_cube = Cube(
            pygame.Rect(int(self.carrier_x), int(self.camera_y + HELD_CUBE_SCREEN_Y), CUBE_SIZE, CUBE_SIZE),
            is_falling=False,
        )

    def update_camera(self) -> None:
        """스택 최상단이 화면 상단 쪽으로 침범하지 않도록 카메라를 위로 올린다."""
        top_world_y = self.stack[-1].rect.top
        desired_camera_y = float(top_world_y - STACK_TOP_MIN_SCREEN_Y)
        # 카메라는 위로만(= world y가 더 작은 방향) 이동: 즉, camera_y는 감소만 허용
        if desired_camera_y < self.camera_y:
            self.camera_y = desired_camera_y

    # -------------------------
    # 입력 처리
    # -------------------------
    def handle_drop_input(self) -> None:
        if self.state != "play":
            return
        if self.held_cube.is_falling:
            return
        self.held_cube.is_falling = True
        self.held_cube.vel_y = 0.0

    # -------------------------
    # 전도/안정도 판정
    # -------------------------
    def _compute_overlap_ratio(self, top_rect: pygame.Rect, falling_rect: pygame.Rect) -> float:
        left = max(top_rect.left, falling_rect.left)
        right = min(top_rect.right, falling_rect.right)
        overlap = max(0, right - left)
        return overlap / float(CUBE_SIZE)

    def _compute_center_of_mass_x(self) -> float:
        # 간단하게 모든 큐브의 중심 x 평균을 COM으로 사용(동일 질량 가정)
        total = 0.0
        for cube in self.stack:
            total += cube.rect.centerx
        return total / max(1, len(self.stack))

    def _check_com_gameover(self) -> bool:
        com_x = self._compute_center_of_mass_x()
        support_left = self.base_rect.left + COM_MARGIN_PX
        support_right = self.base_rect.right - COM_MARGIN_PX
        if com_x < support_left or com_x > support_right:
            self.game_over_reason = "중심을 잃고 쓰러졌어요!"
            return True
        return False

    def place_cube_if_landed(self) -> None:
        if not self.held_cube.is_falling:
            return

        top = self.stack[-1].rect
        # 상단에 닿았는지 체크
        if self.held_cube.rect.bottom < top.top:
            return

        # 착지 처리(위에 얹기)
        self.held_cube.rect.bottom = top.top
        self.held_cube.is_falling = False
        self.held_cube.vel_y = 0.0

        # 사람이 보기엔 거의 딱 맞게 올렸다면 “스냅”으로 정확히 정렬해준다.
        # (고속 구간에서 int 반올림/프레임 타이밍으로 1~몇 px 어긋나는 문제 방지)
        if abs(self.held_cube.rect.centerx - top.centerx) <= SNAP_TO_TARGET_PX:
            self.held_cube.rect.centerx = top.centerx

        overlap_ratio = self._compute_overlap_ratio(top, self.held_cube.rect)
        if overlap_ratio <= 0.0:
            self.game_over_reason = "각설탕이 떨어졌어요!"
            self.state = "gameover"
            return

        if overlap_ratio < MIN_OVERLAP_RATIO_TO_PLACE:
            # 사실상 지지 불가 -> 즉시 붕괴(원작 감성: 너무 삐뚤면 바로 게임오버)
            self.game_over_reason = "너무 삐뚤게 얹어서 무너졌어요!"
            self.state = "gameover"
            return

        # 정상 배치
        self.stack.append(Cube(self.held_cube.rect.copy(), is_falling=False))
        self.score += 1
        self.level = self.score

        # 오버랩이 작을수록 불안정 상승(세미-물리)
        if overlap_ratio >= MIN_OVERLAP_RATIO_FOR_SAFE:
            gain = 0.0
        else:
            t = (MIN_OVERLAP_RATIO_FOR_SAFE - overlap_ratio) / max(1e-6, (MIN_OVERLAP_RATIO_FOR_SAFE - MIN_OVERLAP_RATIO_TO_PLACE))
            gain = min(INSTABILITY_GAIN_MAX, 0.6 + 2.2 * t)
        self.instability = min(6.0, self.instability + gain)

        # COM이 베이스 밖이면 즉시 게임오버(필수 규칙 강화)
        if self._check_com_gameover():
            self.state = "gameover"
            return

        # 다음 큐브 스폰
        self.spawn_held_cube()

    # -------------------------
    # 업데이트 루프
    # -------------------------
    def update_play(self, dt: float) -> None:
        # 캐리어 이동(가속 + 속도 상한)
        accel = CARRIER_ACCEL_BASE + CARRIER_ACCEL_PER_LEVEL * max(0, self.level - 1)
        max_speed = CARRIER_MAX_SPEED_BASE + CARRIER_MAX_SPEED_PER_LEVEL * max(0, self.level - 1)

        self.carrier_speed = min(max_speed, self.carrier_speed + accel * dt)
        self.carrier_x += self.carrier_dir * self.carrier_speed * dt

        left_bound = 12
        right_bound = SCREEN_WIDTH - CUBE_SIZE - 12
        if self.carrier_x <= left_bound:
            self.carrier_x = float(left_bound)
            self.carrier_dir = 1
            self.carrier_speed = 0.0
        elif self.carrier_x >= right_bound:
            self.carrier_x = float(right_bound)
            self.carrier_dir = -1
            self.carrier_speed = 0.0

        # 들고 있는 큐브는 캐리어 위치를 따라감(낙하 중이면 제외)
        if not self.held_cube.is_falling:
            self.held_cube.rect.x = int(self.carrier_x)
            # 카메라가 움직여도 요정/큐브는 화면 상단 근처에 고정되도록 월드 y를 재설정
            self.held_cube.rect.y = int(self.camera_y + HELD_CUBE_SCREEN_Y)

        # 낙하 업데이트
        self.held_cube.update(dt)
        self.place_cube_if_landed()

        # 불안정/기울기(프레임 기반)
        if self.instability > 0:
            self.tilt_deg += TILT_GROWTH_PER_SEC * self.instability * dt
            self.instability = max(0.0, self.instability - INSTABILITY_DECAY_PER_SEC * dt)
        else:
            self.tilt_deg = max(0.0, self.tilt_deg - 0.8 * dt)

        if self.tilt_deg >= TILT_THRESHOLD_DEG:
            self.game_over_reason = "중심을 잃고 쓰러졌어요!"
            self.state = "gameover"
            return

        # 보조 안전장치:
        # 카메라가 위로 스크롤되면 오래된 아래 블록들은 화면 밖(아래)로 사라지는 게 정상이다.
        # 따라서 "스택 블록이 화면 아래로 내려갔다"는 조건으로 게임오버를 내면 오작동한다.
        # 대신, 낙하 중인 블록이 화면 아래로 완전히 떨어져 나가는 경우만 실패로 처리한다.
        if self.held_cube.is_falling and self.held_cube.rect.top > int(self.camera_y + SCREEN_HEIGHT + 80):
            self.game_over_reason = "각설탕이 떨어졌어요!"
            self.state = "gameover"
            return

        # 스택이 높아지면 카메라를 위로 올려 “항상 화면 하단 쪽에서 쌓이는” 느낌을 유지
        self.update_camera()

    # -------------------------
    # 렌더링
    # -------------------------
    def draw_background(self) -> None:
        self.screen.fill(BG_COLOR)
        # 간단한 구름 느낌
        pygame.draw.circle(self.screen, (235, 248, 255), (70, 70), 28)
        pygame.draw.circle(self.screen, (235, 248, 255), (100, 62), 22)
        pygame.draw.circle(self.screen, (235, 248, 255), (125, 74), 18)
        pygame.draw.circle(self.screen, (235, 248, 255), (305, 90), 26)
        pygame.draw.circle(self.screen, (235, 248, 255), (330, 78), 20)

    def draw_base(self) -> None:
        rect = self.base_rect.move(0, -int(self.camera_y))
        pygame.draw.rect(self.screen, (220, 190, 140), rect, border_radius=10)
        pygame.draw.rect(self.screen, (80, 60, 40), rect, width=2, border_radius=10)

    def draw_cube(self, rect: pygame.Rect, shade: Tuple[int, int, int]) -> None:
        pygame.draw.rect(self.screen, shade, rect, border_radius=8)
        pygame.draw.rect(self.screen, (70, 70, 70), rect, width=2, border_radius=8)
        # 하이라이트
        hl = pygame.Rect(rect.x + 8, rect.y + 8, rect.width - 16, 10)
        pygame.draw.rect(self.screen, (255, 255, 255), hl, border_radius=6)

    def draw_carrier(self) -> None:
        # “요정”을 간단한 원/날개로 표현
        x = int(self.carrier_x) + CUBE_SIZE // 2
        # 요정은 스크린 기준 위치에 고정
        y = CARRIER_SCREEN_Y
        pygame.draw.circle(self.screen, (255, 220, 240), (x, y), 12)  # 얼굴
        pygame.draw.circle(self.screen, (30, 30, 30), (x - 4, y - 2), 2)
        pygame.draw.circle(self.screen, (30, 30, 30), (x + 4, y - 2), 2)
        # 날개
        pygame.draw.ellipse(self.screen, (210, 255, 230), pygame.Rect(x - 22, y - 14, 18, 22))
        pygame.draw.ellipse(self.screen, (210, 255, 230), pygame.Rect(x + 4, y - 14, 18, 22))

    def draw_hud(self) -> None:
        # 중앙 큰 숫자(원작 감성: 층수=점수)
        score_text = str(self.score)
        rendered = self.font_big.render(score_text, True, (35, 35, 35))
        rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, 240))
        self.screen.blit(rendered, rect)

        self.screen.blit(self.font_small.render(f"최고: {self.best_score}", True, (40, 40, 40)), (14, 10))

        if self.state == "play":
            hint = "스페이스/아무 키/클릭/터치: 떨어뜨리기"
            self.screen.blit(self.font_small.render(hint, True, (40, 40, 40)), (14, 32))

    def draw_stack(self) -> None:
        # 단순하지만 “기울기 진행”을 시각화: 위로 갈수록 x를 조금씩 밀어 기울어진 느낌을 줌
        tilt_rad = math.radians(self.tilt_deg)
        # 이전 값(2.0)은 기울기가 누적돼도 거의 안 보였다 → 체감과 판정 불일치.
        x_shift_per_level = math.tan(tilt_rad) * 8.0  # 픽셀 단위(더 잘 보이게)

        for idx, cube in enumerate(self.stack):
            shift = int(x_shift_per_level * idx)
            rect_world = cube.rect.move(shift, 0)
            rect_screen = rect_world.move(0, -int(self.camera_y))
            self.draw_cube(rect_screen, (255, 255, 255))

        # 낙하 중/대기 중인 큐브
        if self.state == "play":
            self.draw_cube(self.held_cube.rect.move(0, -int(self.camera_y)), (252, 252, 252))

    def draw_title(self) -> None:
        self.draw_background()
        draw_text_center(self.screen, self.font_title, "각설탕 쌓기", 170)
        draw_text_center(self.screen, self.font, "원버튼 타이밍으로 탑을 쌓아보세요", 210, color=(60, 60, 60))

        for rect, label in [(self.btn_start, "게임시작"), (self.btn_howto, "게임방법")]:
            draw_card(self.screen, rect)
            draw_text_center(self.screen, self.font, label, rect.centery)

        draw_text_center(self.screen, self.font_small, "ESC: 종료", 560, color=(70, 70, 70))

    def draw_howto(self) -> None:
        self.draw_background()
        draw_text_center(self.screen, self.font_title, "게임방법", 150)

        card = pygame.Rect(42, 200, 316, 210)
        draw_card(self.screen, card)

        lines = [
            "버튼(스페이스/클릭/터치)을 누르면",
            "각설탕이 떨어집니다.",
            "",
            "중심을 잃고 쓰러지면 게임오버입니다.",
            "높아질수록 요정 이동 속도가 빨라져요.",
        ]
        y = card.top + 34
        for line in lines:
            if line == "":
                y += 12
                continue
            rendered = self.font.render(line, True, TEXT_COLOR)
            self.screen.blit(rendered, rendered.get_rect(center=(card.centerx, y)))
            y += 30

        draw_card(self.screen, self.btn_back)
        draw_text_center(self.screen, self.font, "뒤로", self.btn_back.centery)

    def draw_play(self) -> None:
        self.draw_background()
        self.draw_base()
        self.draw_carrier()
        self.draw_stack()
        self.draw_hud()

    def draw_gameover(self) -> None:
        self.draw_play()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        card = pygame.Rect(40, 170, 320, 240)
        draw_card(self.screen, card)

        draw_text_center(self.screen, self.font_title, "게임오버", card.top + 52)
        reason = self.game_over_reason or "무너졌어요!"
        draw_text_center(self.screen, self.font, reason, card.top + 94, color=(60, 60, 60))

        draw_text_center(self.screen, self.font_big, str(self.score), card.top + 155)
        draw_text_center(self.screen, self.font_small, f"최고 기록: {self.best_score}", card.top + 198, color=(70, 70, 70))
        draw_text_center(self.screen, self.font_small, "R: 재시작   ENTER: 타이틀", card.top + 222, color=(70, 70, 70))

    # -------------------------
    # 메인 루프
    # -------------------------
    def run(self) -> None:
        while self.running:
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        continue

                    if self.state == "title":
                        # 타이틀에서는 아무 키로 시작해도 UX가 좋아짐(원작: 아무키나 가능)
                        self.state = "play"
                        self.reset_game()
                    elif self.state == "howto":
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.state = "title"
                    elif self.state == "play":
                        # 스페이스뿐 아니라 “아무 키”도 드롭
                        self.handle_drop_input()
                    elif self.state == "gameover":
                        if event.key == pygame.K_r:
                            self.state = "play"
                            self.reset_game()
                        elif event.key == pygame.K_RETURN:
                            self.state = "title"

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if self.state == "title":
                        if self.btn_start.collidepoint(mx, my):
                            self.state = "play"
                            self.reset_game()
                        elif self.btn_howto.collidepoint(mx, my):
                            self.state = "howto"
                    elif self.state == "howto":
                        if self.btn_back.collidepoint(mx, my):
                            self.state = "title"
                    elif self.state == "play":
                        self.handle_drop_input()
                    elif self.state == "gameover":
                        # 클릭으로도 빠른 재시작
                        self.state = "play"
                        self.reset_game()

            if self.state == "play":
                self.update_play(dt)

            if self.state == "gameover":
                if self.score > self.best_score:
                    self.best_score = self.score
                    save_best_score(self.best_score)

            if self.state == "title":
                self.draw_title()
            elif self.state == "howto":
                self.draw_howto()
            elif self.state == "play":
                self.draw_play()
            elif self.state == "gameover":
                self.draw_gameover()

            pygame.display.flip()

        pygame.quit()


def run_game() -> None:
    SugarStackGame().run()


if __name__ == "__main__":
    run_game()


