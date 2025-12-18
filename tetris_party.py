from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import pygame


SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

GRID_COLS = 10
GRID_ROWS = 20
CELL_SIZE = 26

BOARD_LEFT = 80
BOARD_TOP = 50

FPS = 60

BG_COLOR = (18, 18, 26)
PANEL_COLOR = (26, 26, 38)
GRID_LINE_COLOR = (42, 42, 62)
TEXT_COLOR = (240, 240, 240)
SUBTEXT_COLOR = (190, 190, 204)

FONT_CANDIDATES = [
    "Pretendard",
    "Apple SD Gothic Neo",
    "AppleGothic",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
    "Arial Unicode MS",
]

TetrominoKind = Literal["I", "O", "T", "S", "Z", "J", "L"]
OrderKind = Literal["SINGLE", "DOUBLE", "TRIPLE", "TETRIS"]


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """한글이 깨지지 않도록, 환경에 설치된 한글 지원 폰트를 찾아 반환한다."""
    for name in FONT_CANDIDATES:
        font_path = pygame.font.match_font(name, bold=bold)
        if font_path:
            return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(None, size, bold=bold)


def _rotate_cw(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """블록 셀 좌표를 시계 방향으로 90도 회전한다."""
    return [(y, -x) for x, y in cells]


TETROMINO_CELLS: dict[TetrominoKind, list[tuple[int, int]]] = {
    "I": [(-1, 0), (0, 0), (1, 0), (2, 0)],
    "O": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "T": [(-1, 0), (0, 0), (1, 0), (0, 1)],
    "S": [(-1, 1), (0, 1), (0, 0), (1, 0)],
    "Z": [(-1, 0), (0, 0), (0, 1), (1, 1)],
    "J": [(-1, 0), (0, 0), (1, 0), (-1, 1)],
    "L": [(-1, 0), (0, 0), (1, 0), (1, 1)],
}

TETROMINO_COLORS: dict[TetrominoKind, tuple[int, int, int]] = {
    "I": (80, 220, 240),
    "O": (240, 220, 90),
    "T": (190, 120, 255),
    "S": (120, 240, 160),
    "Z": (255, 110, 120),
    "J": (110, 160, 255),
    "L": (255, 170, 90),
}


@dataclass
class Piece:
    """현재 조작 중인 테트로미노."""

    kind: TetrominoKind
    x: int
    y: int
    rotation: int = 0

    def cells(self) -> list[tuple[int, int]]:
        """현재 회전 상태의 셀 좌표(offset)를 반환한다."""
        base = TETROMINO_CELLS[self.kind]
        cells = base[:]
        if self.kind == "O":
            return cells
        for _ in range(self.rotation % 4):
            cells = _rotate_cw(cells)
        return cells


def _empty_board() -> list[list[tuple[int, int, int] | None]]:
    """빈 보드를 생성한다."""
    return [[None for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]


def _in_bounds(x: int, y: int) -> bool:
    """그리드 범위 내 좌표인지 확인한다."""
    return 0 <= x < GRID_COLS and 0 <= y < GRID_ROWS


def _collides(board: list[list[tuple[int, int, int] | None]], piece: Piece) -> bool:
    """현재 piece가 벽/바닥/고정 블록과 충돌하는지 확인한다."""
    for dx, dy in piece.cells():
        gx = piece.x + dx
        gy = piece.y + dy
        if gx < 0 or gx >= GRID_COLS:
            return True
        if gy >= GRID_ROWS:
            return True
        if gy >= 0 and board[gy][gx] is not None:
            return True
    return False


def _try_move(board: list[list[tuple[int, int, int] | None]], piece: Piece, dx: int, dy: int) -> bool:
    """이동을 시도하고 성공 여부를 반환한다."""
    candidate = Piece(kind=piece.kind, x=piece.x + dx, y=piece.y + dy, rotation=piece.rotation)
    if _collides(board, candidate):
        return False
    piece.x = candidate.x
    piece.y = candidate.y
    return True


def _try_rotate(board: list[list[tuple[int, int, int] | None]], piece: Piece) -> bool:
    """회전을 시도하고 성공 여부를 반환한다(간단 wall-kick 포함)."""
    if piece.kind == "O":
        return True

    next_rotation = (piece.rotation + 1) % 4
    kicks = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)]
    for kx, ky in kicks:
        candidate = Piece(kind=piece.kind, x=piece.x + kx, y=piece.y + ky, rotation=next_rotation)
        if not _collides(board, candidate):
            piece.x = candidate.x
            piece.y = candidate.y
            piece.rotation = next_rotation
            return True
    return False


def _lock_piece(board: list[list[tuple[int, int, int] | None]], piece: Piece) -> None:
    """현재 piece를 보드에 고정한다."""
    color = TETROMINO_COLORS[piece.kind]
    for dx, dy in piece.cells():
        gx = piece.x + dx
        gy = piece.y + dy
        if _in_bounds(gx, gy):
            board[gy][gx] = color


def _clear_lines(board: list[list[tuple[int, int, int] | None]]) -> int:
    """완성된 라인을 지우고 지운 라인 수를 반환한다."""
    new_rows: list[list[tuple[int, int, int] | None]] = []
    cleared = 0
    for row in board:
        if all(cell is not None for cell in row):
            cleared += 1
        else:
            new_rows.append(row)

    while len(new_rows) < GRID_ROWS:
        new_rows.insert(0, [None for _ in range(GRID_COLS)])

    board[:] = new_rows
    return cleared


def _score_for_lines(lines: int, level: int) -> int:
    """라인 제거 수에 따른 점수를 계산한다."""
    base = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}[lines]
    return base * max(1, level)


def _spawn_piece(kind: TetrominoKind) -> Piece:
    """새 조작 블록을 스폰한다."""
    return Piece(kind=kind, x=GRID_COLS // 2 - 1, y=-1, rotation=0)


def _draw_cell(surface: pygame.Surface, x: int, y: int, color: tuple[int, int, int]) -> None:
    """1칸 블록을 그림자/테두리와 함께 그린다."""
    px = BOARD_LEFT + x * CELL_SIZE
    py = BOARD_TOP + y * CELL_SIZE
    rect = pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)
    shadow = rect.move(2, 2)
    pygame.draw.rect(surface, (0, 0, 0), shadow, border_radius=4)
    pygame.draw.rect(surface, color, rect, border_radius=4)
    pygame.draw.rect(surface, (255, 255, 255), rect, width=2, border_radius=4)


def _draw_board(surface: pygame.Surface, board: list[list[tuple[int, int, int] | None]]) -> None:
    """보드 및 그리드 라인을 그린다."""
    board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, GRID_COLS * CELL_SIZE, GRID_ROWS * CELL_SIZE)
    pygame.draw.rect(surface, PANEL_COLOR, board_rect, border_radius=12)

    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            cell = board[y][x]
            if cell is None:
                px = BOARD_LEFT + x * CELL_SIZE
                py = BOARD_TOP + y * CELL_SIZE
                pygame.draw.rect(surface, GRID_LINE_COLOR, (px, py, CELL_SIZE, CELL_SIZE), width=1)
            else:
                _draw_cell(surface, x, y, cell)

    pygame.draw.rect(surface, (80, 80, 110), board_rect, width=3, border_radius=12)


def _draw_piece(surface: pygame.Surface, piece: Piece, alpha: int = 255) -> None:
    """현재 조작 블록을 그린다."""
    color = TETROMINO_COLORS[piece.kind]
    draw_color = (color[0], color[1], color[2], alpha)
    for dx, dy in piece.cells():
        gx = piece.x + dx
        gy = piece.y + dy
        if gy < 0:
            continue
        px = BOARD_LEFT + gx * CELL_SIZE
        py = BOARD_TOP + gy * CELL_SIZE
        rect = pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)
        block = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        pygame.draw.rect(block, draw_color, (0, 0, CELL_SIZE, CELL_SIZE), border_radius=4)
        pygame.draw.rect(block, (255, 255, 255, alpha), (0, 0, CELL_SIZE, CELL_SIZE), width=2, border_radius=4)
        surface.blit(block, rect.topleft)


def _ghost_piece(board: list[list[tuple[int, int, int] | None]], piece: Piece) -> Piece:
    """현재 블록이 떨어질 수 있는 최종 위치(고스트)를 계산한다."""
    ghost = Piece(kind=piece.kind, x=piece.x, y=piece.y, rotation=piece.rotation)
    while True:
        candidate = Piece(kind=ghost.kind, x=ghost.x, y=ghost.y + 1, rotation=ghost.rotation)
        if _collides(board, candidate):
            return ghost
        ghost.y += 1


def _draw_side_panel(
    surface: pygame.Surface,
    font_title: pygame.font.Font,
    font_text: pygame.font.Font,
    score: int,
    level: int,
    lines: int,
    next_kind: TetrominoKind,
    is_game_over: bool,
    order_kind: OrderKind,
    order_remaining: int,
    fever_active: bool,
    fever_time_left: float,
    bomb_available: bool,
) -> None:
    """오른쪽 정보 패널을 그린다."""
    panel_rect = pygame.Rect(420, 50, 300, 520)
    pygame.draw.rect(surface, PANEL_COLOR, panel_rect, border_radius=14)
    pygame.draw.rect(surface, (80, 80, 110), panel_rect, width=3, border_radius=14)

    title = font_title.render("테트리스", True, TEXT_COLOR)
    surface.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

    surface.blit(font_text.render(f"점수: {score:,}", True, TEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 90))
    surface.blit(font_text.render(f"레벨: {level}", True, TEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 128))
    surface.blit(font_text.render(f"라인: {lines}", True, TEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 166))

    order_title = font_text.render("파티 주문", True, SUBTEXT_COLOR)
    surface.blit(order_title, (panel_rect.x + 20, panel_rect.y + 208))
    order_label_map: dict[OrderKind, str] = {
        "SINGLE": "1줄 지우기",
        "DOUBLE": "2줄 동시 삭제",
        "TRIPLE": "3줄 동시 삭제",
        "TETRIS": "4줄(테트리스)",
    }
    order_text = f"{order_label_map[order_kind]} x {order_remaining}"
    surface.blit(font_text.render(order_text, True, TEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 236))

    if fever_active:
        fever_text = f"피버 ON (x2)  {fever_time_left:04.1f}s"
        surface.blit(font_text.render(fever_text, True, (255, 210, 120)), (panel_rect.x + 20, panel_rect.y + 270))
        bomb_text = "폭탄(X): 가능" if bomb_available else "폭탄(X): 사용됨"
        surface.blit(font_text.render(bomb_text, True, (255, 210, 120)), (panel_rect.x + 20, panel_rect.y + 296))
    else:
        surface.blit(font_text.render("피버: 주문 달성 시 5초", True, SUBTEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 270))

    surface.blit(font_text.render("다음 블록", True, SUBTEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 330))
    preview_origin = (panel_rect.x + 60, panel_rect.y + 370)
    color = TETROMINO_COLORS[next_kind]
    for dx, dy in TETROMINO_CELLS[next_kind]:
        px = preview_origin[0] + (dx + 2) * 18
        py = preview_origin[1] + (dy + 2) * 18
        pygame.draw.rect(surface, color, (px, py, 16, 16), border_radius=4)
        pygame.draw.rect(surface, (255, 255, 255), (px, py, 16, 16), width=2, border_radius=4)

    controls = [
        "←/→ 이동",
        "↑ 회전",
        "↓ 소프트 드롭",
        "SPACE 하드 드롭",
        "X 피버 폭탄(1회)",
        "P 일시정지",
        "R 재시작",
        "ESC 종료",
    ]
    surface.blit(font_text.render("조작", True, SUBTEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 440))
    for idx, line in enumerate(controls):
        surface.blit(font_text.render(line, True, TEXT_COLOR), (panel_rect.x + 20, panel_rect.y + 470 + idx * 22))

    if is_game_over:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        msg1 = font_title.render("게임 오버", True, TEXT_COLOR)
        msg2 = font_text.render("R: 재시작 / ESC: 종료", True, TEXT_COLOR)
        surface.blit(msg1, msg1.get_rect(center=(SCREEN_WIDTH // 2, 240)))
        surface.blit(msg2, msg2.get_rect(center=(SCREEN_WIDTH // 2, 290)))


def run_game() -> None:
    """테트리스 미니게임을 실행한다."""
    pygame.init()
    pygame.display.set_caption("테트리스")

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    font_title = get_font(44, bold=True)
    font_text = get_font(22)

    rng = random.Random()
    board = _empty_board()

    next_kind: TetrominoKind = rng.choice(list(TETROMINO_CELLS.keys()))
    current = _spawn_piece(next_kind)
    next_kind = rng.choice(list(TETROMINO_CELLS.keys()))

    score = 0
    level = 1
    total_lines = 0
    best_score = 0
    fever_active = False
    fever_time_left = 0.0
    bomb_available = False

    order_kind: OrderKind = "SINGLE"
    order_remaining = 2

    fall_timer = 0.0
    soft_drop = False
    paused = False
    game_over = False

    def restart() -> None:
        """현재 라운드를 초기화한다."""
        nonlocal board
        nonlocal next_kind
        nonlocal current
        nonlocal score
        nonlocal level
        nonlocal total_lines
        nonlocal best_score
        nonlocal fall_timer
        nonlocal soft_drop
        nonlocal paused
        nonlocal game_over
        nonlocal fever_active
        nonlocal fever_time_left
        nonlocal bomb_available
        nonlocal order_kind
        nonlocal order_remaining
        board = _empty_board()
        next_kind = rng.choice(list(TETROMINO_CELLS.keys()))
        current = _spawn_piece(next_kind)
        next_kind = rng.choice(list(TETROMINO_CELLS.keys()))
        score = 0
        level = 1
        total_lines = 0
        best_score = max(best_score, 0)
        fall_timer = 0.0
        soft_drop = False
        paused = False
        game_over = False
        fever_active = False
        fever_time_left = 0.0
        bomb_available = False
        order_kind = "SINGLE"
        order_remaining = 2

    def _next_order() -> tuple[OrderKind, int]:
        """다음 파티 주문을 생성한다."""
        kind = rng.choice(["SINGLE", "DOUBLE", "TRIPLE", "TETRIS"])
        if kind == "SINGLE":
            return "SINGLE", 3
        if kind == "DOUBLE":
            return "DOUBLE", 2
        if kind == "TRIPLE":
            return "TRIPLE", 1
        return "TETRIS", 1

    def _apply_order_progress(cleared_lines: int) -> None:
        """라인 삭제 결과로 주문 진행도를 갱신한다."""
        nonlocal order_kind, order_remaining, fever_active, fever_time_left, bomb_available
        kind_map: dict[int, OrderKind] = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}
        achieved = kind_map.get(cleared_lines)
        if achieved is None:
            return
        if achieved != order_kind:
            return
        order_remaining = max(0, order_remaining - 1)
        if order_remaining == 0:
            fever_active = True
            fever_time_left = 5.0
            bomb_available = True
            order_kind, order_remaining = _next_order()

    def _use_bomb() -> None:
        """피버 중 1회 사용 가능한 폭탄: 바닥 2줄을 제거한다."""
        nonlocal bomb_available
        if not bomb_available:
            return
        remove_count = 2
        remaining = board[:-remove_count]
        for _ in range(remove_count):
            remaining.insert(0, [None for _ in range(GRID_COLS)])
        board[:] = remaining
        bomb_available = False

    def lock_and_spawn() -> None:
        """현재 블록을 고정하고 다음 블록을 스폰한다."""
        nonlocal current, next_kind, score, level, total_lines, best_score, game_over, fever_active, fever_time_left
        _lock_piece(board, current)
        cleared = _clear_lines(board)
        total_lines += cleared
        multiplier = 2 if fever_active else 1
        score += _score_for_lines(cleared, level) * multiplier
        level = 1 + total_lines // 10
        best_score = max(best_score, score)
        _apply_order_progress(cleared)

        current = _spawn_piece(next_kind)
        next_kind = rng.choice(list(TETROMINO_CELLS.keys()))
        if _collides(board, current):
            game_over = True

    running = True
    while running:
        delta_ms = clock.tick(FPS)
        delta_time = delta_ms / 1000

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_r:
                    restart()
                if game_over:
                    continue
                if paused:
                    continue

                if event.key == pygame.K_LEFT:
                    _try_move(board, current, -1, 0)
                elif event.key == pygame.K_RIGHT:
                    _try_move(board, current, 1, 0)
                elif event.key == pygame.K_UP:
                    _try_rotate(board, current)
                elif event.key == pygame.K_SPACE:
                    ghost = _ghost_piece(board, current)
                    current.y = ghost.y
                    score += 2 * (2 if fever_active else 1)
                    lock_and_spawn()
                elif event.key == pygame.K_x:
                    if fever_active:
                        _use_bomb()
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_DOWN:
                    soft_drop = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_DOWN] and not (paused or game_over):
            soft_drop = True

        if not (paused or game_over):
            if fever_active:
                fever_time_left -= delta_time
                if fever_time_left <= 0:
                    fever_active = False
                    fever_time_left = 0.0
                    bomb_available = False

            fall_speed = max(0.06, 0.65 - (level - 1) * 0.05)
            if soft_drop:
                fall_speed *= 0.12

            fall_timer += delta_time
            while fall_timer >= fall_speed:
                fall_timer -= fall_speed
                moved = _try_move(board, current, 0, 1)
                if not moved:
                    lock_and_spawn()
                    break
                if soft_drop:
                    score += 1 * (2 if fever_active else 1)

        screen.fill(BG_COLOR)
        _draw_board(screen, board)

        if not game_over:
            ghost = _ghost_piece(board, current)
            _draw_piece(screen, ghost, alpha=80)
        _draw_piece(screen, current, alpha=255)

        _draw_side_panel(
            screen,
            font_title,
            font_text,
            score,
            level,
            total_lines,
            next_kind,
            is_game_over=game_over,
            order_kind=order_kind,
            order_remaining=order_remaining,
            fever_active=fever_active,
            fever_time_left=fever_time_left,
            bomb_available=bomb_available,
        )

        best = font_text.render(f"최고점수: {best_score:,}", True, SUBTEXT_COLOR)
        screen.blit(best, (BOARD_LEFT, BOARD_TOP + GRID_ROWS * CELL_SIZE + 12))

        if paused and not game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            screen.blit(overlay, (0, 0))
            msg = font_title.render("일시정지", True, TEXT_COLOR)
            hint = font_text.render("P로 계속", True, TEXT_COLOR)
            screen.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, 240)))
            screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 290)))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run_game()


