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
TARGET_DISTANCE_METERS = 1000
OBSTACLE_MIN_SPEED = 220
OBSTACLE_MAX_SPEED = 320
OBSTACLE_SPAWN_INTERVAL = 1200  # milliseconds
TEXT_COLOR = (240, 240, 240)
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "run_to_restaurant"
RUN_FRAME_DURATION = 0.12
BASE_SPEED = 40.0
SPEED_INCREASE_RATE = 0.08  # meters per second^2
MAX_SPEED = 90.0
MIN_OBSTACLE_GAP_MS = 700
ITEM_SPAWN_INTERVAL = 1600  # milliseconds
ITEM_THRESHOLD = 10
BOOST_DURATION = 5.0  # seconds
BOOST_SPEED_MULTIPLIER = 2.0
ITEM_COLOR = (255, 226, 138)
ITEM_GLOW_COLOR = (255, 250, 205)
ITEM_SIZE = 22
ITEM_MIN_Y = GROUND_Y - 170
ITEM_MAX_Y = GROUND_Y - 90


ObstacleKind = Literal["high", "low"]


@dataclass
class Obstacle:
    """Obstacle that travels from right to left toward the runner."""

    rect: pygame.Rect
    speed: float
    kind: ObstacleKind

    def update(self, delta_time: float) -> None:
        """Move based on its intrinsic speed."""
        self.rect.x -= self.speed * delta_time

    def is_off_screen(self) -> bool:
        """Return True when the obstacle is safely outside the view."""
        return self.rect.right < -40


@dataclass
class RunnerAnimation:
    """러너 달리기 애니메이션 상태."""

    frame_index: int = 0
    timer: float = 0.0


@dataclass
class Item:
    """스테이지에 등장하는 부스터 아이템."""

    rect: pygame.Rect


def load_image(name: str) -> pygame.Surface:
    """지정된 에셋 이미지를 불러온다."""
    path = ASSET_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return pygame.image.load(path.as_posix()).convert_alpha()


def slice_strip(sheet: pygame.Surface, frame_width: int) -> list[pygame.Surface]:
    """가로 스프라이트 시트를 프레임 단위로 분리한다."""
    frames: list[pygame.Surface] = []
    columns = sheet.get_width() // frame_width
    for idx in range(columns):
        rect = pygame.Rect(idx * frame_width, 0, frame_width, sheet.get_height())
        frames.append(sheet.subsurface(rect).copy())
    return frames


def load_assets() -> dict[str, pygame.Surface | list[pygame.Surface]]:
    """게임에서 사용하는 모든 스프라이트와 패널을 메모리에 로드한다."""
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
        "game_over_card": load_image("game_over_card.png"),
        "victory_card": load_image("victory_card.png"),
    }


def spawn_obstacle(kind: ObstacleKind) -> Obstacle:
    """Create a new obstacle for the given kind with slight speed variance."""
    speed = random.randint(OBSTACLE_MIN_SPEED, OBSTACLE_MAX_SPEED)
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
    """Spawn a collectible item slightly above ground."""
    y = random.randint(ITEM_MIN_Y, ITEM_MAX_Y)
    rect = pygame.Rect(SCREEN_WIDTH + 20, y, ITEM_SIZE, ITEM_SIZE)
    return Item(rect=rect)


def update_items(items: list[Item], delta_time: float, scroll_speed: float) -> None:
    """Move items with the world scroll speed and prune off-screen ones."""
    for item in items[:]:
        item.rect.x -= int(scroll_speed * delta_time)
        if item.rect.right < -40:
            items.remove(item)


def draw_items(surface: pygame.Surface, items: list[Item]) -> None:
    """Draw collectible items with a subtle glow."""
    for item in items:
        pygame.draw.circle(surface, ITEM_GLOW_COLOR, item.rect.center, ITEM_SIZE // 2 + 4)
        pygame.draw.circle(surface, ITEM_COLOR, item.rect.center, ITEM_SIZE // 2)


def draw_background(surface: pygame.Surface, distance: float, assets: dict[str, pygame.Surface]) -> None:
    """Render the layered background, parallax mountains, and ground tiles."""
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
    """Draw the runner sprite based on stance and motion."""
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
    """Render obstacle sprites with their respective artwork."""
    for obstacle in obstacles:
        sprite_key = "obstacle_high" if obstacle.kind == "high" else "obstacle_low"
        sprite = assets[sprite_key]
        surface.blit(sprite, obstacle.rect)


def draw_hud(
    surface: pygame.Surface,
    font: pygame.font.Font,
    distance: float,
    assets: dict[str, pygame.Surface | list[pygame.Surface]],
    current_speed: float,
    item_count: int,
    booster_active: bool,
    booster_time_left: float,
) -> None:
    """Show current progress and controls using the HUD panel."""
    surface.blit(assets["hud_panel"], (0, 0))
    remaining = max(0, TARGET_DISTANCE_METERS - distance)
    progress = min(distance / TARGET_DISTANCE_METERS, 1.0)

    surface.blit(font.render(f"남은 거리: {remaining:05.1f} m", True, TEXT_COLOR), (20, 16))
    surface.blit(font.render(f"목표 1 km / 진행 {progress * 100:05.1f}%", True, TEXT_COLOR), (20, 40))
    controls_line = "자동 전진 | ↓ 슬라이드 | SPACE 점프"
    surface.blit(font.render(controls_line, True, TEXT_COLOR), (20, 64))
    status_line = f"아이템 {item_count}/{ITEM_THRESHOLD} · 속도 {current_speed:.0f} m/s"
    surface.blit(font.render(status_line, True, TEXT_COLOR), (20, 88))

    frame = assets["progress_frame"]
    fill = assets["progress_fill"]
    bar_pos = (SCREEN_WIDTH - frame.get_width() - 20, 20)
    fill_width = int(fill.get_width() * progress)
    if fill_width > 0:
        fill_slice = fill.subsurface((0, 0, fill_width, fill.get_height()))
        surface.blit(fill_slice, bar_pos)
    surface.blit(frame, bar_pos)

    if booster_active:
        booster_text = f"부스터 ON ({booster_time_left:04.1f}s)"
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
    is_victory: bool = False,
) -> None:
    """Draw overlay mask plus themed card with text."""
    surface.blit(assets["overlay_mask"], (0, 0))
    card = assets["victory_card"] if is_victory else assets["game_over_card"]
    card_rect = card.get_rect(center=(SCREEN_WIDTH // 2, 170))
    surface.blit(card, card_rect.topleft)

    for idx, line in enumerate(text_lines):
        rendered = font.render(line, True, TEXT_COLOR)
        rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, card_rect.top + 50 + idx * 32))
        surface.blit(rendered, rect)


def update_player_rect(player_rect: pygame.Rect, is_crouching: bool) -> None:
    """Adjust the player's collision box based on stance."""
    bottom = player_rect.bottom
    target_height = CROUCH_HEIGHT if is_crouching else PLAYER_HEIGHT
    player_rect.height = target_height
    player_rect.width = PLAYER_WIDTH
    player_rect.bottom = bottom


def run_game() -> None:
    """Run the restaurant dash mini-game."""
    pygame.init()
    pygame.display.set_caption("맛집으로 달려가기")

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("pretendard", 24)
    assets = load_assets()
    runner_anim = RunnerAnimation()

    player_rect = pygame.Rect(120, GROUND_Y - PLAYER_HEIGHT, PLAYER_WIDTH, PLAYER_HEIGHT)
    player_velocity_y = 0.0
    is_jumping = False
    is_crouching = False

    distance_m = 0.0
    elapsed_time = 0.0
    current_speed = BASE_SPEED

    obstacles: list[Obstacle] = []
    last_spawn_time = 0
    last_obstacle_kind: ObstacleKind | None = None
    last_type_switch_time = 0

    items: list[Item] = []
    last_item_spawn_time = 0
    item_count = 0
    booster_active = False
    booster_time_left = 0.0

    game_over = False
    victory = False

    running = True
    while running:
        delta_ms = clock.tick(60)
        delta_time = delta_ms / 1000
        now = pygame.time.get_ticks()
        elapsed_time += delta_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r and (game_over or victory):
                    obstacles.clear()
                    player_rect.x = 120
                    player_rect.y = GROUND_Y - PLAYER_HEIGHT
                    player_rect.height = PLAYER_HEIGHT
                    player_velocity_y = 0
                    is_jumping = False
                    is_crouching = False
                    distance_m = 0
                    last_spawn_time = now
                    last_obstacle_kind = None
                    last_type_switch_time = 0
                    items.clear()
                    last_item_spawn_time = now
                    item_count = 0
                    booster_active = False
                    booster_time_left = 0.0
                    current_speed = BASE_SPEED
                    elapsed_time = 0.0
                    game_over = False
                    victory = False
                    runner_anim = RunnerAnimation()
                if not game_over and not victory:
                    if event.key == pygame.K_SPACE and not is_jumping:
                        is_jumping = True
                        player_velocity_y = -JUMP_POWER

        keys = pygame.key.get_pressed()
        is_crouching = keys[pygame.K_DOWN] and not is_jumping
        update_player_rect(player_rect, is_crouching)

        current_speed = min(MAX_SPEED, BASE_SPEED + elapsed_time * SPEED_INCREASE_RATE)
        world_speed = current_speed * (BOOST_SPEED_MULTIPLIER if booster_active else 1.0)

        if not game_over and not victory:
            distance_m += world_speed * delta_time

        if is_jumping:
            player_velocity_y += GRAVITY * delta_time
            player_rect.y += player_velocity_y * delta_time
            if player_rect.bottom >= GROUND_Y:
                player_rect.bottom = GROUND_Y
                player_velocity_y = 0
                is_jumping = False

        if not is_jumping and not is_crouching:
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

        if not (game_over or victory) and not is_jumping and not is_crouching:
            runner_anim.timer += delta_time
            if runner_anim.timer >= RUN_FRAME_DURATION:
                runner_anim.timer -= RUN_FRAME_DURATION
                frames = assets["runner_run_frames"]
                runner_anim.frame_index = (runner_anim.frame_index + 1) % len(frames)
        else:
            runner_anim.timer = 0.0
            runner_anim.frame_index = 0

        if not game_over and not victory:
            if now - last_spawn_time > OBSTACLE_SPAWN_INTERVAL:
                candidate = random.choice(["high", "low"])
                can_switch = (
                    last_obstacle_kind is None
                    or candidate == last_obstacle_kind
                    or now - last_type_switch_time >= MIN_OBSTACLE_GAP_MS
                )
                if can_switch:
                    obstacles.append(spawn_obstacle(candidate))
                    last_spawn_time = now
                    if candidate != last_obstacle_kind:
                        last_type_switch_time = now
                    last_obstacle_kind = candidate

            if now - last_item_spawn_time > ITEM_SPAWN_INTERVAL:
                items.append(spawn_item())
                last_item_spawn_time = now

            for obstacle in obstacles[:]:
                obstacle.update(delta_time)
                if obstacle.is_off_screen():
                    obstacles.remove(obstacle)
                    continue
                if obstacle.rect.colliderect(player_rect):
                    if booster_active:
                        obstacles.remove(obstacle)
                    else:
                        if obstacle.kind == "high" and not is_crouching:
                            game_over = True
                        elif obstacle.kind == "low" and not is_jumping:
                            game_over = True
                        if not game_over:
                            obstacles.remove(obstacle)

            if distance_m >= TARGET_DISTANCE_METERS:
                victory = True

        update_items(items, delta_time, world_speed)
        for item in items[:]:
            if item.rect.colliderect(player_rect):
                items.remove(item)
                item_count = min(item_count + 1, ITEM_THRESHOLD)

        draw_background(screen, distance_m, assets)
        draw_obstacles(screen, obstacles, assets)
        draw_player(
            screen,
            player_rect,
            is_crouching,
            is_jumping,
            assets,
            runner_anim.frame_index,
            not (is_jumping or is_crouching) and not (game_over or victory),
        )
        draw_items(screen, items)
        draw_hud(
            screen,
            font,
            distance_m,
            assets,
            current_speed,
            item_count,
            booster_active,
            booster_time_left,
        )

        if game_over:
            draw_overlay(
                screen,
                font,
                [
                    "장애물에 부딪혔습니다!",
                    f"진행 거리: {distance_m:05.1f} m",
                    "다시 시작 R / 종료 ESC",
                ],
                assets,
                is_victory=False,
            )
        elif victory:
            draw_overlay(
                screen,
                font,
                [
                    "맛집 도착! 1 km 완주!",
                    "R 키로 다시 달려보세요",
                ],
                assets,
                is_victory=True,
            )

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run_game()

