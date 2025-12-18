from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pygame


SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
GROUND_Y = 320

PLAYER_WIDTH = 44
PLAYER_HEIGHT = 72
CROUCH_HEIGHT = 44

JUMP_POWER = 360
GRAVITY = 900

TEXT_COLOR = (240, 240, 240)

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "last_product_rush"

RUN_FRAME_DURATION = 0.12

FONT_CANDIDATES = [
    "Pretendard",
    "Apple SD Gothic Neo",
    "AppleGothic",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Arial Unicode MS",
]

BASE_SPEED = 42.0
SPEED_INCREASE_RATE = 0.085  # meters per second^2 (시간 기반 가속)
MAX_SPEED = 95.0

OBSTACLE_SPAWN_INTERVAL = 1100  # milliseconds
MIN_OBSTACLE_GAP_MS = 750  # 타입 전환 최소 시간 간격
MIN_OBSTACLE_GAP_DISTANCE = 32.0  # 타입 전환 최소 거리 간격(m)
MIN_OBSTACLE_GAP_PX = 180  # 타입 전환 시, 화면 내 가장 오른쪽 장애물과의 최소 픽셀 간격

ITEM_SPAWN_INTERVAL = 1500  # milliseconds
ITEM_THRESHOLD = 3

BOOST_DURATION = 5.0  # seconds
BOOST_SPEED_MULTIPLIER = 2.0

MAX_JUMPS = 2


ObstacleKind = Literal["high", "low"]


@dataclass
class Obstacle:
    """오른쪽에서 왼쪽으로 이동하는 장애물."""

    rect: pygame.Rect
    speed: float
    kind: ObstacleKind

    def update(self, delta_time: float) -> None:
        """시간 경과에 따라 장애물을 이동시킨다."""
        self.rect.x -= self.speed * delta_time

    def is_off_screen(self) -> bool:
        """화면 밖으로 완전히 나갔는지 여부를 반환한다."""
        return self.rect.right < -60


@dataclass
class RunnerAnimation:
    """러너 달리기 애니메이션 상태."""

    frame_index: int = 0
    timer: float = 0.0


@dataclass
class Item:
    """아이템(부스터 카운트 증가용)."""

    rect: pygame.Rect
    x: float


def load_image(name: str) -> pygame.Surface:
    """지정된 에셋 이미지를 불러온다."""
    path = ASSET_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return pygame.image.load(path.as_posix()).convert_alpha()


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """한글이 깨지지 않도록, 환경에 설치된 한글 지원 폰트를 찾아 반환한다."""
    for name in FONT_CANDIDATES:
        font_path = pygame.font.match_font(name, bold=bold)
        if font_path:
            return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(None, size, bold=bold)


def slice_strip(sheet: pygame.Surface, frame_width: int) -> list[pygame.Surface]:
    """가로 스프라이트 시트를 프레임 단위로 분리한다."""
    frames: list[pygame.Surface] = []
    columns = sheet.get_width() // frame_width
    for idx in range(columns):
        rect = pygame.Rect(idx * frame_width, 0, frame_width, sheet.get_height())
        frames.append(sheet.subsurface(rect).copy())
    return frames


def load_assets() -> dict[str, pygame.Surface | list[pygame.Surface]]:
    """게임에서 사용하는 모든 스프라이트를 로드한다."""
    runner_run_sheet = load_image("runner_run_strip.png")
    return {
        "background": load_image("background.png"),
        "mountains": load_image("parallax_mountains.png"),
        "ground_tile": load_image("ground_tile.png"),
        "hud_panel": load_image("hud_panel.png"),
        "progress_frame": load_image("progress_bar.png"),
        "progress_fill": load_image("progress_fill.png"),
        "runner_idle": load_image("runner_idle.png"),
        "runner_run_frames": slice_strip(runner_run_sheet, PLAYER_WIDTH),
        "runner_crouch": load_image("runner_crouch.png"),
        "runner_jump": load_image("runner_jump.png"),
        "runner_eye_trail": load_image("runner_eye_trail.png"),
        "obstacle_high": load_image("obstacle_high.png"),
        "obstacle_low": load_image("obstacle_low.png"),
        "overlay_mask": load_image("overlay_mask.png"),
        "overlay_card": load_image("overlay_card.png"),
        "game_over_card": load_image("game_over_card.png"),
        "victory_card": load_image("victory_card.png"),
        "item_plate_base": load_image("plate_base.png"),
        "item_plate_active": load_image("plate_active.png"),
    }


def spawn_obstacle(kind: ObstacleKind, speed: float) -> Obstacle:
    """지정된 종류의 장애물을 생성한다."""
    if kind == "high":
        width, height = 56, 110
        rect = pygame.Rect(
            SCREEN_WIDTH + 20,
            GROUND_Y - PLAYER_HEIGHT - height + 16,
            width,
            height,
        )
    else:
        width, height = 50, 60
        rect = pygame.Rect(SCREEN_WIDTH + 20, GROUND_Y - height, width, height)

    return Obstacle(rect=rect, speed=speed, kind=kind)


def spawn_item() -> Item:
    """아이템을 생성한다(지면 위쪽 영역)."""
    item_size = 26
    y = random.randint(GROUND_Y - 170, GROUND_Y - 90)
    rect = pygame.Rect(SCREEN_WIDTH + 20, y, item_size, item_size)
    return Item(rect=rect, x=float(rect.x))


def update_items(items: list[Item], delta_time: float, scroll_speed_px: float) -> None:
    """월드 스크롤 속도에 맞춰 아이템을 이동시키고 화면 밖 아이템을 제거한다."""
    for item in items[:]:
        item.x -= scroll_speed_px * delta_time
        item.rect.x = int(item.x)
        if item.rect.right < -60:
            items.remove(item)


def draw_background(surface: pygame.Surface, distance: float, assets: dict[str, pygame.Surface]) -> None:
    """배경/산/지면을 레이어로 그려 속도감을 표현한다."""
    surface.blit(assets["background"], (0, 0))

    mountains = assets["mountains"]
    offset = int((distance * 0.2) % SCREEN_WIDTH)
    for x in (-offset, SCREEN_WIDTH - offset):
        surface.blit(mountains, (x, 0))

    ground_tile = assets["ground_tile"]
    tile_width = ground_tile.get_width()
    tile_offset = int((distance * 4) % tile_width)
    for x in range(-tile_offset, SCREEN_WIDTH + tile_width, tile_width):
        surface.blit(ground_tile, (x, GROUND_Y))


def draw_player(
    surface: pygame.Surface,
    rect: pygame.Rect,
    is_crouching: bool,
    is_jumping: bool,
    assets: dict[str, pygame.Surface | list[pygame.Surface]],
    run_frame_index: int,
    is_running: bool,
) -> None:
    """플레이어 상태에 맞는 스프라이트를 그린다."""
    if is_jumping:
        sprite = assets["runner_jump"]
    elif is_crouching:
        sprite = assets["runner_crouch"]
    elif is_running:
        sprite = assets["runner_run_frames"][run_frame_index]
    else:
        sprite = assets["runner_idle"]

    surface.blit(sprite, rect)
    if is_running and not is_crouching:
        surface.blit(assets["runner_eye_trail"], rect)


def draw_obstacles(
    surface: pygame.Surface,
    obstacles: list[Obstacle],
    assets: dict[str, pygame.Surface | list[pygame.Surface]],
) -> None:
    """장애물 스프라이트를 그린다."""
    for obstacle in obstacles:
        sprite_key = "obstacle_high" if obstacle.kind == "high" else "obstacle_low"
        surface.blit(assets[sprite_key], obstacle.rect)


def draw_items(
    surface: pygame.Surface,
    items: list[Item],
    assets: dict[str, pygame.Surface | list[pygame.Surface]],
    booster_active: bool,
) -> None:
    """아이템(접시)을 그린다."""
    sprite_key = "item_plate_active" if booster_active else "item_plate_base"
    sprite = assets[sprite_key]
    for item in items:
        surface.blit(sprite, item.rect)


def draw_hud(
    surface: pygame.Surface,
    font: pygame.font.Font,
    distance: float,
    elapsed_time: float,
    assets: dict[str, pygame.Surface | list[pygame.Surface]],
    current_speed: float,
    item_count: int,
    booster_active: bool,
    booster_time_left: float,
    best_distance: float,
) -> None:
    """HUD에 거리/시간/속도/아이템/부스터 정보를 표시한다."""
    surface.blit(assets["hud_panel"], (0, 0))

    surface.blit(font.render(f"생존 시간: {elapsed_time:05.1f} s", True, TEXT_COLOR), (20, 16))
    surface.blit(font.render(f"진행 거리: {distance:07.1f} m", True, TEXT_COLOR), (20, 40))
    surface.blit(font.render(f"최고 기록: {best_distance:07.1f} m", True, TEXT_COLOR), (20, 64))
    surface.blit(font.render("자동 전진 | ↓ 슬라이드 | SPACE 점프(2단)", True, TEXT_COLOR), (20, 88))

    status_line = f"아이템 {item_count}/{ITEM_THRESHOLD} · 속도 {current_speed:.0f} m/s"
    surface.blit(font.render(status_line, True, TEXT_COLOR), (20, 112))

    progress_ratio = min(item_count / ITEM_THRESHOLD, 1.0)
    frame = assets["progress_frame"]
    fill = assets["progress_fill"]
    bar_pos = (SCREEN_WIDTH - frame.get_width() - 20, 20)
    fill_width = int(fill.get_width() * progress_ratio)
    if fill_width > 0:
        fill_slice = fill.subsurface((0, 0, fill_width, fill.get_height()))
        surface.blit(fill_slice, bar_pos)
    surface.blit(frame, bar_pos)

    if booster_active:
        booster_text = f"부스터 ON ({booster_time_left:04.1f}s) · 장애물 무시"
    elif item_count >= ITEM_THRESHOLD:
        booster_text = "부스터 준비 완료!"
    else:
        booster_text = f"부스터 준비 중 ({ITEM_THRESHOLD - item_count}개 남음)"

    surface.blit(
        font.render(booster_text, True, TEXT_COLOR),
        (bar_pos[0], bar_pos[1] + frame.get_height() + 12),
    )


def draw_overlay(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text_lines: list[str],
    assets: dict[str, pygame.Surface | list[pygame.Surface]],
) -> None:
    """게임 오버 오버레이를 그린다."""
    surface.blit(assets["overlay_mask"], (0, 0))
    card = assets["game_over_card"]
    card_rect = card.get_rect(center=(SCREEN_WIDTH // 2, 170))
    surface.blit(card, card_rect.topleft)

    for idx, line in enumerate(text_lines):
        rendered = font.render(line, True, TEXT_COLOR)
        rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, card_rect.top + 50 + idx * 32))
        surface.blit(rendered, rect)


def update_player_rect(player_rect: pygame.Rect, is_crouching: bool) -> None:
    """슬라이드 여부에 따라 충돌 박스 높이를 조정한다."""
    bottom = player_rect.bottom
    target_height = CROUCH_HEIGHT if is_crouching else PLAYER_HEIGHT
    player_rect.height = target_height
    player_rect.width = PLAYER_WIDTH
    player_rect.bottom = bottom


def _can_spawn_different_obstacle_kind(
    *,
    obstacles: list[Obstacle],
    candidate: ObstacleKind,
    last_kind: ObstacleKind | None,
    now_ms: int,
    last_type_switch_ms: int,
    distance_m: float,
    last_obstacle_distance_m: float,
) -> bool:
    """장애물 타입 전환이 가능한지 판단한다(간격 조건 기반).

    NOTE:
    - "다른 타입이 화면에 존재하면 무조건 금지"처럼 강하게 막으면, 스폰 주기상 화면에 항상 장애물이 남아
      타입 전환이 영구적으로 막힐 수 있다.
    - 따라서 타입 전환은 '시간/거리/픽셀 간격' 조건으로 제어해, 플레이어가 반응 불가능한 상황만 방지한다.
    """
    if last_kind is None or candidate == last_kind:
        return True

    enough_time_gap = now_ms - last_type_switch_ms >= MIN_OBSTACLE_GAP_MS
    enough_distance_gap = (distance_m - last_obstacle_distance_m) >= MIN_OBSTACLE_GAP_DISTANCE
    if not (enough_time_gap or enough_distance_gap):
        return False

    if obstacles:
        rightmost_right = max(obstacle.rect.right for obstacle in obstacles)
        spawn_x = SCREEN_WIDTH + 20
        pixel_gap = spawn_x - rightmost_right
        if pixel_gap < MIN_OBSTACLE_GAP_PX:
            return False

    return True


def run_game() -> None:
    """Game3. 마지막 상품 사수하기: 무한 러닝(점프/슬라이드, 아이템 기반 자동 부스터)."""
    pygame.init()
    pygame.display.set_caption("마지막 상품 사수하기")

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    font = get_font(24)
    assets = load_assets()
    runner_anim = RunnerAnimation()

    player_rect = pygame.Rect(120, GROUND_Y - PLAYER_HEIGHT, PLAYER_WIDTH, PLAYER_HEIGHT)
    player_velocity_y = 0.0
    is_jumping = False
    is_crouching = False
    jump_count = 0

    distance_m = 0.0
    elapsed_time = 0.0
    best_distance = 0.0

    obstacles: list[Obstacle] = []
    last_spawn_ms = 0
    last_obstacle_kind: ObstacleKind | None = None
    last_type_switch_ms = 0
    last_obstacle_distance_m = 0.0

    items: list[Item] = []
    last_item_spawn_ms = 0
    item_count = 0

    booster_active = False
    booster_time_left = 0.0

    game_over = False

    running = True
    while running:
        delta_ms = clock.tick(60)
        delta_time = delta_ms / 1000
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r and game_over:
                    obstacles.clear()
                    items.clear()
                    player_rect.x = 120
                    player_rect.y = GROUND_Y - PLAYER_HEIGHT
                    player_rect.height = PLAYER_HEIGHT
                    player_velocity_y = 0.0
                    is_jumping = False
                    is_crouching = False
                    jump_count = 0
                    distance_m = 0.0
                    elapsed_time = 0.0
                    item_count = 0
                    booster_active = False
                    booster_time_left = 0.0
                    last_spawn_ms = now_ms
                    last_item_spawn_ms = now_ms
                    last_obstacle_kind = None
                    last_type_switch_ms = 0
                    last_obstacle_distance_m = 0.0
                    runner_anim = RunnerAnimation()
                    game_over = False
                if not game_over:
                    if event.key == pygame.K_SPACE and jump_count < MAX_JUMPS:
                        is_jumping = True
                        player_velocity_y = -JUMP_POWER
                        jump_count += 1

        keys = pygame.key.get_pressed()
        is_crouching = keys[pygame.K_DOWN] and not is_jumping and not game_over
        update_player_rect(player_rect, is_crouching)

        if not game_over:
            elapsed_time += delta_time

        current_speed = min(MAX_SPEED, BASE_SPEED + elapsed_time * SPEED_INCREASE_RATE)
        world_speed = current_speed * (BOOST_SPEED_MULTIPLIER if booster_active else 1.0)

        if not game_over:
            distance_m += world_speed * delta_time
            best_distance = max(best_distance, distance_m)

        if is_jumping and not game_over:
            player_velocity_y += GRAVITY * delta_time
            player_rect.y += player_velocity_y * delta_time
            if player_rect.bottom >= GROUND_Y:
                player_rect.bottom = GROUND_Y
                player_velocity_y = 0.0
                is_jumping = False
                jump_count = 0

        if not is_jumping:
            player_rect.bottom = GROUND_Y

        if booster_active:
            booster_time_left -= delta_time
            if booster_time_left <= 0:
                booster_active = False
                booster_time_left = 0.0
                item_count = 0
        elif item_count >= ITEM_THRESHOLD:
            booster_active = True
            booster_time_left = BOOST_DURATION

        is_running = not (is_jumping or is_crouching) and not game_over
        if is_running:
            runner_anim.timer += delta_time
            if runner_anim.timer >= RUN_FRAME_DURATION:
                runner_anim.timer -= RUN_FRAME_DURATION
                frames = assets["runner_run_frames"]
                runner_anim.frame_index = (runner_anim.frame_index + 1) % len(frames)
        else:
            runner_anim.timer = 0.0
            runner_anim.frame_index = 0

        if not game_over:
            if now_ms - last_spawn_ms >= OBSTACLE_SPAWN_INTERVAL:
                candidate = random.choice(["high", "low"])
                can_spawn = _can_spawn_different_obstacle_kind(
                    obstacles=obstacles,
                    candidate=candidate,
                    last_kind=last_obstacle_kind,
                    now_ms=now_ms,
                    last_type_switch_ms=last_type_switch_ms,
                    distance_m=distance_m,
                    last_obstacle_distance_m=last_obstacle_distance_m,
                )
                if can_spawn:
                    obstacle_speed = world_speed * 6.0
                    obstacles.append(spawn_obstacle(candidate, obstacle_speed))
                    last_spawn_ms = now_ms
                    last_obstacle_distance_m = distance_m
                    if candidate != last_obstacle_kind:
                        last_type_switch_ms = now_ms
                    last_obstacle_kind = candidate

            if now_ms - last_item_spawn_ms >= ITEM_SPAWN_INTERVAL:
                items.append(spawn_item())
                last_item_spawn_ms = now_ms

            for obstacle in obstacles[:]:
                obstacle.update(delta_time)
                if obstacle.is_off_screen():
                    obstacles.remove(obstacle)
                    continue

                if obstacle.rect.colliderect(player_rect):
                    if booster_active:
                        obstacles.remove(obstacle)
                        continue

                    if obstacle.kind == "high":
                        if not is_crouching:
                            game_over = True
                    else:
                        if not is_jumping:
                            game_over = True

                    if not game_over:
                        obstacles.remove(obstacle)

        update_items(items, delta_time, world_speed * 6.0)
        for item in items[:]:
            if item.rect.colliderect(player_rect):
                items.remove(item)
                item_count = min(item_count + 1, ITEM_THRESHOLD)

        draw_background(screen, distance_m, assets)
        draw_obstacles(screen, obstacles, assets)
        draw_items(screen, items, assets, booster_active)
        draw_player(
            screen,
            player_rect,
            is_crouching,
            is_jumping,
            assets,
            runner_anim.frame_index,
            is_running,
        )
        draw_hud(
            screen,
            font,
            distance_m,
            elapsed_time,
            assets,
            current_speed,
            item_count,
            booster_active,
            booster_time_left,
            best_distance,
        )

        if game_over:
            draw_overlay(
                screen,
                font,
                [
                    "장애물에 부딪혔습니다!",
                    f"기록: {distance_m:07.1f} m · 시간 {elapsed_time:05.1f}s",
                    "R: 재시작 / ESC: 종료",
                ],
                assets,
            )

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run_game()

