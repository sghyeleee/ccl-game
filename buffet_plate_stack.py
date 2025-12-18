from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pygame

SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
PLATE_HEIGHT = 22
INITIAL_PLATE_WIDTH = 200
PLATE_SPEED = 180
SPEED_INCREMENT = 14
ALIGN_TOLERANCE = 0
TEXT_COLOR = (240, 240, 240)
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "buffet_plate_stack"

PlateCacheKey = Tuple[str, int]
PLATE_SURFACE_CACHE: Dict[PlateCacheKey, pygame.Surface] = {}


def load_image(name: str) -> pygame.Surface:
    """Return a converted RGBA surface from the assets directory."""
    path = ASSET_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return pygame.image.load(path.as_posix()).convert_alpha()


def load_assets() -> dict[str, pygame.Surface]:
    """Load all buffet plate stack art assets."""
    return {
        "background": load_image("background.png"),
        "plate_base": load_image("plate_base.png"),
        "plate_active": load_image("plate_active.png"),
        "hud_panel": load_image("hud_panel.png"),
        "overlay_card": load_image("overlay_card.png"),
    }


def get_plate_surface(kind: str, width: int, assets: dict[str, pygame.Surface]) -> pygame.Surface:
    """Return a cached, scaled surface for the requested plate width."""
    key = (kind, width)
    if key not in PLATE_SURFACE_CACHE:
        base_surface = assets["plate_active"] if kind == "active" else assets["plate_base"]
        PLATE_SURFACE_CACHE[key] = pygame.transform.smoothscale(base_surface, (width, PLATE_HEIGHT))
    return PLATE_SURFACE_CACHE[key]


class Plate:
    """Simple rectangular plate representation."""

    def __init__(self, x: float, y: float, width: int, kind: str) -> None:
        self.rect = pygame.Rect(x, y, width, PLATE_HEIGHT)
        self.kind = kind

    def draw(self, surface: pygame.Surface, assets: dict[str, pygame.Surface]) -> None:
        """Render the plate using the correct sprite."""
        sprite = get_plate_surface(self.kind, self.rect.width, assets)
        surface.blit(sprite, self.rect)


def create_initial_stack(base_y: int) -> list[Plate]:
    """Return stack with one base plate centered at the bottom."""
    base_plate = Plate((SCREEN_WIDTH - INITIAL_PLATE_WIDTH) // 2, base_y, INITIAL_PLATE_WIDTH, "base")
    return [base_plate]


def spawn_active_plate(stack: list[Plate], direction: int, width: int) -> Plate:
    """Create a moving plate above the current stack."""
    top_y = stack[-1].rect.top - PLATE_HEIGHT
    x = 0 if direction > 0 else SCREEN_WIDTH - width
    return Plate(x, top_y, width, "active")


def drop_plate(active_plate: Plate, target_plate: Plate) -> tuple[Plate | None, int]:
    """Try to place the active plate on top of the target. Return new plate and overlap width."""
    left = max(active_plate.rect.left, target_plate.rect.left)
    right = min(active_plate.rect.right, target_plate.rect.right)
    overlap_width = right - left

    if overlap_width <= ALIGN_TOLERANCE:
        return None, overlap_width

    new_plate = Plate(left, target_plate.rect.top - PLATE_HEIGHT, overlap_width, "base")
    return new_plate, overlap_width


def draw_hud(
    surface: pygame.Surface,
    font: pygame.font.Font,
    height: int,
    best: int,
    assets: dict[str, pygame.Surface],
) -> None:
    """Draw score and instructions on top of the HUD panel."""
    surface.blit(assets["hud_panel"], (0, 0))
    surface.blit(font.render(f"쌓은 접시: {height}", True, TEXT_COLOR), (16, 12))
    surface.blit(font.render(f"최고 기록: {best}", True, TEXT_COLOR), (16, 38))
    surface.blit(font.render("스페이스: 떨어뜨리기 | R: 재시작 | ESC: 종료", True, TEXT_COLOR), (16, 64))


def draw_overlay(
    surface: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    assets: dict[str, pygame.Surface],
) -> None:
    """Draw semi-transparent overlay with themed card and text lines."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    card = assets["overlay_card"]
    card_rect = card.get_rect(center=(SCREEN_WIDTH // 2, 220))
    surface.blit(card, card_rect)

    for idx, text in enumerate(lines):
        rendered = font.render(text, True, TEXT_COLOR)
        rect = rendered.get_rect(center=(card_rect.centerx, card_rect.top + 50 + idx * 32))
        surface.blit(rendered, rect)


def run_game() -> None:
    """Run the buffet plate stacking mini-game."""
    pygame.init()
    pygame.display.set_caption("뷔페 접시 쌓기")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("pretendard", 22)
    assets = load_assets()

    stack = create_initial_stack(SCREEN_HEIGHT - PLATE_HEIGHT - 20)
    direction = 1
    speed = PLATE_SPEED
    active_plate = spawn_active_plate(stack, direction, stack[-1].rect.width)
    best_height = 0

    game_over = False
    victory = False
    goal_height = 12

    running = True
    while running:
        delta_ms = clock.tick(60)
        delta_time = delta_ms / 1000

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r and (game_over or victory):
                    stack = create_initial_stack(SCREEN_HEIGHT - PLATE_HEIGHT - 20)
                    direction = 1
                    speed = PLATE_SPEED
                    active_plate = spawn_active_plate(stack, direction, stack[-1].rect.width)
                    game_over = False
                    victory = False
                if event.key == pygame.K_SPACE and not (game_over or victory):
                    placed_plate, overlap = drop_plate(active_plate, stack[-1])
                    if placed_plate is None:
                        game_over = True
                    else:
                        stack.append(placed_plate)
                        best_height = max(best_height, len(stack) - 1)
                        if len(stack) - 1 >= goal_height or placed_plate.rect.top <= 40:
                            victory = True
                        direction *= -1
                        speed += SPEED_INCREMENT
                        active_plate = spawn_active_plate(stack, direction, placed_plate.rect.width)

        if not (game_over or victory):
            active_plate.rect.x += direction * speed * delta_time
            if active_plate.rect.left <= 0:
                active_plate.rect.left = 0
                direction = 1
            elif active_plate.rect.right >= SCREEN_WIDTH:
                active_plate.rect.right = SCREEN_WIDTH
                direction = -1

        screen.blit(assets["background"], (0, 0))
        for plate in stack:
            plate.draw(screen, assets)
        if not (game_over or victory):
            active_plate.draw(screen, assets)

        draw_hud(screen, font, len(stack) - 1, best_height, assets)

        if game_over:
            draw_overlay(
                screen,
                font,
                [
                    "접시가 비뚤어졌어요!",
                    f"총 쌓은 접시: {len(stack) - 1}",
                    "R로 다시 시작하세요",
                ],
                assets,
            )
        elif victory:
            draw_overlay(
                screen,
                font,
                [
                    "뷔페 접시 타워 완성!",
                    "R로 더 높은 기록에 도전해보세요",
                ],
                assets,
            )

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run_game()

