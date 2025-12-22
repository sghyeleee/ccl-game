from __future__ import annotations

import pygame


def draw_overlay(surface: pygame.Surface, *, alpha: int = 120) -> None:
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, max(0, min(255, alpha))))
    surface.blit(overlay, (0, 0))


def draw_card(surface: pygame.Surface, rect: pygame.Rect) -> None:
    # 쌓아부리 톤과 동일: 흰색 카드 + 검은 테두리 + 살짝 그림자
    shadow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 40), shadow.get_rect(), border_radius=18)
    surface.blit(shadow, (rect.x - 5, rect.y - 3))

    pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=18)
    pygame.draw.rect(surface, (40, 40, 40), rect, width=2, border_radius=18)


def draw_text_center(surface: pygame.Surface, font: pygame.font.Font, text: str, y: int, *, color=(20, 20, 20)) -> None:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(surface.get_width() // 2, y))
    surface.blit(rendered, rect)


def draw_game_over_ui(
    surface: pygame.Surface,
    *,
    font_title: pygame.font.Font,
    font: pygame.font.Font,
    font_small: pygame.font.Font,
    reason: str,
    score: int,
    best_score: int | None,
    hint: str,
) -> None:
    """세 게임 공통 게임오버 UI(오버레이 + 카드 + 텍스트)."""
    draw_overlay(surface, alpha=120)

    w, h = surface.get_size()
    card = pygame.Rect((w - 560) // 2, 150, 560, 260)
    draw_card(surface, card)

    draw_text_center(surface, font_title, "게임오버", card.top + 52, color=(20, 20, 20))
    draw_text_center(surface, font, reason, card.top + 94, color=(60, 60, 60))
    draw_text_center(surface, font_title, str(score), card.top + 155, color=(35, 35, 35))
    if best_score is not None:
        draw_text_center(surface, font_small, f"최고 기록: {best_score}", card.top + 198, color=(70, 70, 70))
    draw_text_center(surface, font_small, hint, card.top + 222, color=(70, 70, 70))


