from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import pygame

from ui_common import draw_game_over_ui
from leaderboard import LeaderboardEntry, submit_and_fetch_async
from ui_common import draw_input_box, draw_leaderboard_list

# 요청: 캐릭터/음식 등을 더 크게 보이게(20x20 → 30x30 느낌)
# 화면(800x540, HUD 60)을 벗어나지 않도록 그리드 크기도 함께 조정한다.
CELL_SIZE = 30
GRID_WIDTH = 26
GRID_HEIGHT = 16
HUD_HEIGHT = 60
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 540
GRID_PIXEL_WIDTH = GRID_WIDTH * CELL_SIZE
GRID_PIXEL_HEIGHT = GRID_HEIGHT * CELL_SIZE
PLAYFIELD_OFFSET_X = (SCREEN_WIDTH - GRID_PIXEL_WIDTH) // 2
PLAYFIELD_OFFSET_Y = HUD_HEIGHT
BACKGROUND_COLOR = (12, 16, 28)
TEXT_COLOR = (240, 240, 240)
INITIAL_SPEED = 8  # moves per second
SPEED_INCREMENT = 0.15
GRID_OVERLAY_ALPHA = 40  # 0이면 격자 완전 제거, 숫자가 클수록 진해짐
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "snake_survival"
NEW_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "new" / "06.game3_dolyuburi"
FONT_FILE = ASSET_DIR / "Pretendard-Regular.ttf"
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
NEODGM_FONT_FILE = FONT_DIR / "neodgm.ttf"
FONT_CANDIDATES = (
    "Pretendard",
    "Pretendard-Regular",
    "Apple SD Gothic Neo",
    "NanumGothic",
    "NanumSquare",
    "Noto Sans CJK KR",
    "NotoSansKR",
    "Malgun Gothic",
)

UP: Tuple[int, int] = (0, -1)
DOWN: Tuple[int, int] = (0, 1)
LEFT: Tuple[int, int] = (-1, 0)
RIGHT: Tuple[int, int] = (1, 0)
DIRECTION_TO_INDEX: Dict[Direction, int] = {
    UP: 0,
    DOWN: 1,
    LEFT: 2,
    RIGHT: 3,
}
CORNER_TO_INDEX: Dict[frozenset[Direction], int] = {
    frozenset({UP, RIGHT}): 2,
    frozenset({RIGHT, DOWN}): 3,
    frozenset({DOWN, LEFT}): 4,
    frozenset({LEFT, UP}): 5,
}
SPARK_FRAME_DURATION = 0.06

Direction = Tuple[int, int]
Point = Tuple[int, int]


@dataclass
class SpriteAssets:
    """Container for all sprite resources used by Snake Survival."""

    head_frames: List[pygame.Surface]
    body_frames: List[pygame.Surface]
    tail_frames: List[pygame.Surface]
    food_frames: List[pygame.Surface]
    # New theme: 친구(파랑/디폴트/빨강/노랑) 머리(방향별) 스프라이트
    friend_head_frames: List[List[pygame.Surface]]
    background_tile: pygame.Surface
    grid_overlay: pygame.Surface
    hud_panel: pygame.Surface
    game_over_card: pygame.Surface
    shadow: pygame.Surface
    spark_frames: List[pygame.Surface]


@dataclass
class SparkEffect:
    """Store spark animation state for food collection feedback."""

    center: Tuple[int, int]
    frame_index: int = 0
    timer: float = 0.0


def load_image(name: str, *, base_dir: Path = ASSET_DIR) -> pygame.Surface:
    """Load a single image from the asset directory with alpha support."""
    path = base_dir / name
    return pygame.image.load(path.as_posix()).convert_alpha()


def scale_to_cell(image: pygame.Surface) -> pygame.Surface:
    """Scale an arbitrary sprite image to the current CELL_SIZE."""
    if image.get_width() == CELL_SIZE and image.get_height() == CELL_SIZE:
        return image
    return pygame.transform.smoothscale(image, (CELL_SIZE, CELL_SIZE))


def scale_to_width(image: pygame.Surface, target_width: int) -> pygame.Surface:
    """Scale an image keeping aspect ratio by width."""
    if image.get_width() == target_width:
        return image
    ratio = target_width / max(1, image.get_width())
    target_height = max(1, int(image.get_height() * ratio))
    return pygame.transform.smoothscale(image, (target_width, target_height))


def slice_sheet(sheet: pygame.Surface, frame_width: int, frame_height: int) -> List[pygame.Surface]:
    """Split a sprite sheet into equal-sized frame surfaces."""
    frames = []
    columns = sheet.get_width() // frame_width
    for idx in range(columns):
        rect = pygame.Rect(idx * frame_width, 0, frame_width, frame_height)
        frames.append(sheet.subsurface(rect).copy())
    return frames


def load_assets() -> SpriteAssets:
    """Load all required sprite assets for the game."""
    # New theme assets (친구 구출 컨셉)
    use_new = NEW_ASSET_DIR.exists()
    if use_new:
        # 플레이어(머리)는 파란 캐릭터를 우선 사용하고, 파일이 없으면 기본 캐릭터로 폴백한다.
        head_prefix = "char_blue" if (NEW_ASSET_DIR / "char_blue_head_up_140_140.png").exists() else "char_default"
        head_frames = []
        for dir_key in ("up", "down", "left", "right"):
            candidate = f"{head_prefix}_head_{dir_key}_140_140.png"
            fallback = f"char_default_head_{dir_key}_140_140.png"
            filename = candidate if (NEW_ASSET_DIR / candidate).exists() else fallback
            head_frames.append(scale_to_cell(load_image(filename, base_dir=NEW_ASSET_DIR)))
        # 친구(맵에 서있는 픽업) + 친구 머리(등 뒤에 붙는 세그먼트) 스프라이트
        # 픽업은 'char_*_140_140', 세그먼트는 'char_*_head_{dir}_140_140' 사용
        friend_kinds = ["blue", "default", "red", "yell"]
        food_frames = [scale_to_cell(load_image(f"char_{k}_140_140.png", base_dir=NEW_ASSET_DIR)) for k in friend_kinds]
        friend_head_frames: List[List[pygame.Surface]] = []
        for k in friend_kinds:
            frames = []
            for dir_key in ("up", "down", "left", "right"):
                frames.append(scale_to_cell(load_image(f"char_{k}_head_{dir_key}_140_140.png", base_dir=NEW_ASSET_DIR)))
            friend_head_frames.append(frames)

        # 기존 API 호환을 위해 body/tail은 일단 픽업 프레임을 재사용(실제 렌더링은 friend_head_frames 사용)
        body_frames = food_frames
        tail_frames = food_frames

        # 배경은 800x540 전체 배경 1장을 사용
        background_tile = load_image("tile_background_800_540.png", base_dir=NEW_ASSET_DIR)
        if background_tile.get_size() != (SCREEN_WIDTH, SCREEN_HEIGHT):
            background_tile = pygame.transform.smoothscale(background_tile, (SCREEN_WIDTH, SCREEN_HEIGHT))
    else:
        # Legacy snake assets
        SOURCE_CELL = 20
        head_frames = [scale_to_cell(f) for f in slice_sheet(load_image("snake_head.png"), SOURCE_CELL, SOURCE_CELL)]
        body_frames = [scale_to_cell(f) for f in slice_sheet(load_image("snake_body.png"), SOURCE_CELL, SOURCE_CELL)]
        tail_frames = [scale_to_cell(f) for f in slice_sheet(load_image("snake_tail.png"), SOURCE_CELL, SOURCE_CELL)]
        food_frames = [scale_to_cell(f) for f in slice_sheet(load_image("food_fruit_sheet.png"), SOURCE_CELL, SOURCE_CELL)]
        background_tile = load_image("background_tile.png")
        friend_head_frames = []

    # Keep legacy UI/effects (new pack doesn't include these)
    grid_overlay = scale_to_cell(load_image("grid_overlay.png"))
    if GRID_OVERLAY_ALPHA <= 0:
        # draw_background에서 스킵 가능하도록 투명 처리
        grid_overlay = grid_overlay.copy()
        grid_overlay.set_alpha(0)
    else:
        grid_overlay = grid_overlay.copy()
        grid_overlay.set_alpha(max(0, min(255, GRID_OVERLAY_ALPHA)))
    hud_panel = load_image("hud_panel.png")
    game_over_card = load_image("game_over_card.png")
    shadow = scale_to_width(load_image("shadow_ellipse.png"), CELL_SIZE)
    spark_sheet = load_image("spark_effect.png")
    spark_frame_width = spark_sheet.get_width() // 4
    # 셀 크기 증가에 맞춰 이펙트도 약간 키운다(원본은 20 기준으로 가정)
    spark_scale = CELL_SIZE / 20
    spark_frames = [
        pygame.transform.smoothscale(f, (max(1, int(f.get_width() * spark_scale)), max(1, int(f.get_height() * spark_scale))))
        for f in slice_sheet(spark_sheet, spark_frame_width, spark_sheet.get_height())
    ]

    return SpriteAssets(
        head_frames=head_frames,
        body_frames=body_frames,
        tail_frames=tail_frames,
        food_frames=food_frames,
        friend_head_frames=friend_head_frames,
        background_tile=background_tile,
        grid_overlay=grid_overlay,
        hud_panel=hud_panel,
        game_over_card=game_over_card,
        shadow=shadow,
        spark_frames=spark_frames,
    )


def spawn_food(snake: List[Point], variant_count: int) -> Tuple[Point, int]:
    """Return a safe food location and the sprite index to display."""
    position = create_food(snake)
    variant = random.randrange(max(variant_count, 1))
    return position, variant


def direction_between(a: Point, b: Point) -> Direction:
    """Return the direction vector needed to go from point a to point b."""
    return (b[0] - a[0], b[1] - a[1])


def body_frame_index(prev_segment: Point, current: Point, next_segment: Point) -> int:
    """Determine which body sprite frame fits a middle snake segment."""
    prev_dir = direction_between(current, prev_segment)
    next_dir = direction_between(current, next_segment)

    if prev_dir[0] == -next_dir[0] and prev_dir[0] != 0:
        return 0  # horizontal
    if prev_dir[1] == -next_dir[1] and prev_dir[1] != 0:
        return 1  # vertical

    return CORNER_TO_INDEX.get(frozenset({prev_dir, next_dir}), 0)


def create_food(snake: List[Point]) -> Point:
    """Return a random grid cell that does not overlap with the snake."""
    available = {(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT)} - set(snake)
    if not available:
        return snake[-1]
    return random.choice(tuple(available))


def draw_background(
    surface: pygame.Surface, background_tile: pygame.Surface, grid_overlay: pygame.Surface
) -> None:
    """Render the textured background and apply the grid overlay pattern."""
    surface.fill(BACKGROUND_COLOR)
    # If the background asset is a full-screen image, blit once; otherwise tile it.
    if background_tile.get_width() >= SCREEN_WIDTH and background_tile.get_height() >= SCREEN_HEIGHT:
        surface.blit(background_tile, (0, 0))
    else:
        tile_width, tile_height = background_tile.get_size()
        for x in range(0, SCREEN_WIDTH, tile_width):
            for y in range(0, SCREEN_HEIGHT, tile_height):
                surface.blit(background_tile, (x, y))

    # 격자는 너무 진하지 않게(또는 완전 제거) 처리
    if grid_overlay.get_alpha() != 0:
        for x in range(0, GRID_PIXEL_WIDTH, CELL_SIZE):
            for y in range(0, GRID_PIXEL_HEIGHT, CELL_SIZE):
                surface.blit(
                    grid_overlay,
                    (PLAYFIELD_OFFSET_X + x, PLAYFIELD_OFFSET_Y + y),
                )


def draw_snake(
    surface: pygame.Surface,
    snake: List[Point],
    head_frames: List[pygame.Surface],
    body_frames: List[pygame.Surface],
    tail_frames: List[pygame.Surface],
    current_direction: Direction,
    shadow: pygame.Surface,
    *,
    friend_head_frames: Optional[List[List[pygame.Surface]]] = None,
    friend_kinds: Optional[List[int]] = None,
) -> None:
    """Draw the snake using sprite assets for head, body, and tail."""
    shadow_offset_x = (CELL_SIZE - shadow.get_width()) // 2
    shadow_offset_y = CELL_SIZE - shadow.get_height()

    for idx, segment in enumerate(snake):
        pixel = (
            PLAYFIELD_OFFSET_X + segment[0] * CELL_SIZE,
            PLAYFIELD_OFFSET_Y + segment[1] * CELL_SIZE,
        )
        surface.blit(shadow, (pixel[0] + shadow_offset_x, pixel[1] + shadow_offset_y))

        if idx == 0:
            direction_index = DIRECTION_TO_INDEX.get(current_direction, DIRECTION_TO_INDEX[RIGHT])
            surface.blit(head_frames[direction_index], pixel)
            continue

        # New theme: 등 뒤 친구는 각자 'head' 스프라이트로 표시한다.
        if friend_head_frames and friend_kinds and idx - 1 < len(friend_kinds):
            kind = friend_kinds[idx - 1]
            prev_segment = snake[idx - 1]
            seg_dir = direction_between(segment, prev_segment)
            direction_index = DIRECTION_TO_INDEX.get(seg_dir, DIRECTION_TO_INDEX[RIGHT])
            if 0 <= kind < len(friend_head_frames):
                surface.blit(friend_head_frames[kind][direction_index], pixel)
                continue

        if idx == len(snake) - 1:
            prev_segment = snake[idx - 1]
            tail_direction = direction_between(segment, prev_segment)
            direction_index = DIRECTION_TO_INDEX.get(tail_direction, DIRECTION_TO_INDEX[RIGHT])
            # New friend-theme uses non-directional tail sprites; legacy uses directional sheets.
            if len(tail_frames) >= 4:
                surface.blit(tail_frames[direction_index], pixel)
            else:
                surface.blit(tail_frames[idx % len(tail_frames)], pixel)
            continue

        prev_segment = snake[idx - 1]
        next_segment = snake[idx + 1]
        frame_idx = body_frame_index(prev_segment, segment, next_segment)
        # New friend-theme uses a small set of variants; legacy uses indexed frames.
        if len(body_frames) >= 6:
            surface.blit(body_frames[frame_idx], pixel)
        else:
            surface.blit(body_frames[idx % len(body_frames)], pixel)


def draw_food(
    surface: pygame.Surface,
    food: Point,
    food_frames: List[pygame.Surface],
    variant: int,
    shadow: pygame.Surface,
) -> None:
    """Draw the active food sprite with a subtle shadow."""
    pixel = (
        PLAYFIELD_OFFSET_X + food[0] * CELL_SIZE,
        PLAYFIELD_OFFSET_Y + food[1] * CELL_SIZE,
    )
    surface.blit(shadow, (pixel[0] + (CELL_SIZE - shadow.get_width()) // 2, pixel[1] + CELL_SIZE - shadow.get_height()))
    frame = food_frames[variant % len(food_frames)]
    surface.blit(frame, pixel)


def draw_hud(
    surface: pygame.Surface,
    hud_panel: pygame.Surface,
    font: pygame.font.Font,
    score: int,
    speed: float,
) -> None:
    """Render the HUD panel with score information."""
    # 기존 hud_panel.png는 색이 너무 진하고 폭이 작아 보이므로
    # 화면 폭에 맞는 밝은 반투명 패널을 코드로 그려 통일한다.
    _ = hud_panel
    panel_margin = 24
    panel_rect = pygame.Rect(panel_margin, 10, SCREEN_WIDTH - panel_margin * 2, 44)

    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (255, 255, 255, 165), panel.get_rect(), border_radius=18)
    pygame.draw.rect(panel, (30, 30, 30, 90), panel.get_rect(), width=2, border_radius=18)
    surface.blit(panel, panel_rect.topleft)

    left_text = font.render(f"친구 수: {score}", True, (30, 30, 30))
    right_text = font.render(f"속도: {speed:.1f}/s", True, (30, 30, 30))

    surface.blit(left_text, (panel_rect.x + 18, panel_rect.y + 12))
    surface.blit(right_text, (panel_rect.right - right_text.get_width() - 18, panel_rect.y + 12))


def draw_game_over(
    surface: pygame.Surface, font: pygame.font.Font, score: int, card_surface: pygame.Surface
) -> None:
    """Draw the game-over overlay card with status text."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    surface.blit(overlay, (0, 0))

    card_rect = card_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    surface.blit(card_surface, card_rect)

    lines = [
        "게임 오버!",
        f"구한 친구 수: {score}",
        "R: 다시 시작 | ESC: 종료",
    ]
    for idx, text in enumerate(lines):
        rendered = font.render(text, True, TEXT_COLOR)
        text_rect = rendered.get_rect(center=(card_rect.centerx, card_rect.top + 50 + idx * 32))
        surface.blit(rendered, text_rect)


def update_sparks(effects: List[SparkEffect], delta_time: float, total_frames: int) -> None:
    """Advance spark animations and remove finished instances."""
    for effect in effects[:]:
        effect.timer += delta_time
        if effect.timer >= SPARK_FRAME_DURATION:
            effect.timer -= SPARK_FRAME_DURATION
            effect.frame_index += 1
            if effect.frame_index >= total_frames:
                effects.remove(effect)


def draw_sparks(surface: pygame.Surface, frames: List[pygame.Surface], effects: List[SparkEffect]) -> None:
    """Draw active spark animations centered on their spawn points."""
    if not effects or not frames:
        return

    frame_width, frame_height = frames[0].get_size()
    for effect in effects:
        frame = frames[min(effect.frame_index, len(frames) - 1)]
        surface.blit(
            frame,
            (effect.center[0] - frame_width // 2, effect.center[1] - frame_height // 2),
        )


def next_direction(current: Direction, queued: Deque[Direction]) -> Direction:
    """Return the next direction, ensuring reverse turns are ignored."""
    if not queued:
        return current
    proposed = queued.popleft()
    if (proposed[0] == -current[0] and proposed[0] != 0) or (proposed[1] == -current[1] and proposed[1] != 0):
        return current
    return proposed


def load_game_font(size: int) -> pygame.font.Font:
    """Load Pretendard font if available, otherwise fall back to default."""
    if NEODGM_FONT_FILE.exists():
        try:
            return pygame.font.Font(NEODGM_FONT_FILE.as_posix(), size)
        except OSError:
            pass
    if FONT_FILE.exists():
        try:
            return pygame.font.Font(FONT_FILE.as_posix(), size)
        except OSError:
            pass

    for candidate in FONT_CANDIDATES:
        font_name = pygame.font.match_font(candidate)
        if font_name:
            return pygame.font.Font(font_name, size)

    return pygame.font.Font(None, size)


def run_game(*, quit_on_exit: bool = True) -> None:
    """Run the endless snake survival mini-game."""
    pygame.init()
    pygame.display.set_caption("돌려부리")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    font_title = load_game_font(46)
    font = load_game_font(22)
    font_small = load_game_font(18)
    assets = load_assets()

    def draw_card(surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=18)
        pygame.draw.rect(surface, (40, 40, 40), rect, width=2, border_radius=18)

    btn_w, btn_h = 240, 64
    btn_x = (SCREEN_WIDTH - btn_w) // 2
    btn_start = pygame.Rect(btn_x, 300, btn_w, btn_h)
    btn_howto = pygame.Rect(btn_x, 378, btn_w, btn_h)
    btn_back = pygame.Rect(26, 22, 110, 46)
    menu_index = 0  # 0=start, 1=howto
    mode: str = "title"  # title | howto | play

    snake: List[Point] = []
    # head(플레이어) 뒤에 붙는 친구 종류(0..3): blue/default/red/yell
    friend_kinds: List[int] = []
    current_direction: Direction = (1, 0)
    direction_queue: Deque[Direction] = deque()
    friend_pos: Point = (0, 0)
    friend_kind = 0
    move_timer = 0.0
    moves_per_second = INITIAL_SPEED
    score = 1
    game_over = False
    sparks: List[SparkEffect] = []
    lb_nickname = ""
    lb_status: Optional[str] = None
    lb_top: list[LeaderboardEntry] = []
    lb_submitted = False

    def reset_play() -> None:
        nonlocal snake, current_direction, friend_pos, friend_kind, move_timer, moves_per_second, score, game_over
        snake = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]
        friend_kinds.clear()
        current_direction = (1, 0)
        direction_queue.clear()
        friend_pos, friend_kind = spawn_food(snake, len(assets.food_frames))
        move_timer = 0.0
        moves_per_second = INITIAL_SPEED
        score = 1
        game_over = False
        sparks.clear()

    running = True
    while running:
        delta_ms = clock.tick(60)
        delta_time = delta_ms / 1000
        update_sparks(sparks, delta_time, len(assets.spark_frames))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if mode == "howto":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        mode = "title"
                    continue
                if mode == "title":
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_index = (menu_index + 1) % 2
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        menu_index = (menu_index - 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if menu_index == 0:
                            reset_play()
                            mode = "play"
                        else:
                            mode = "howto"
                    continue

                # play 모드 입력
                if game_over:
                    if event.key == pygame.K_r:
                        reset_play()
                        lb_nickname = ""
                        lb_status = None
                        lb_top = []
                        lb_submitted = False
                    elif event.key == pygame.K_RETURN:
                        if not lb_submitted:
                            nick = lb_nickname
                            lb_status = "저장 중..."

                            def _cb(err: Optional[str], entries: Optional[list[LeaderboardEntry]]) -> None:
                                nonlocal lb_status, lb_submitted, lb_top
                                if err:
                                    lb_status = f"저장 실패: {err}"
                                    return
                                lb_status = "저장 완료!"
                                lb_submitted = True
                                lb_top = entries or []

                            submit_and_fetch_async("spin", nick, score, callback=_cb)
                        else:
                            mode = "title"
                    elif event.key == pygame.K_BACKSPACE:
                        lb_nickname = lb_nickname[:-1]
                    elif event.unicode and len(lb_nickname) < 12 and event.unicode.isprintable():
                        lb_nickname += event.unicode
                    continue
                if mode == "play" and not game_over:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        direction_queue.append((0, -1))
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        direction_queue.append((0, 1))
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        direction_queue.append((-1, 0))
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        direction_queue.append((1, 0))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mode == "title":
                    if btn_start.collidepoint(mx, my):
                        menu_index = 0
                        reset_play()
                        mode = "play"
                    elif btn_howto.collidepoint(mx, my):
                        menu_index = 1
                        mode = "howto"
                elif mode == "howto":
                    if btn_back.collidepoint(mx, my):
                        mode = "title"

        if mode == "play" and not game_over:
            move_timer += delta_time
            move_interval = 1 / moves_per_second
            if move_timer >= move_interval:
                move_timer -= move_interval
                current_direction = next_direction(current_direction, direction_queue)
                head_x, head_y = snake[0]
                new_head = (head_x + current_direction[0], head_y + current_direction[1])

                if (
                    new_head[0] < 0
                    or new_head[0] >= GRID_WIDTH
                    or new_head[1] < 0
                    or new_head[1] >= GRID_HEIGHT
                    or new_head in snake
                ):
                    game_over = True
                else:
                    snake.insert(0, new_head)
                    if new_head == friend_pos:
                        score += 1
                        moves_per_second += SPEED_INCREMENT
                        # 구출한 친구의 head가 등 뒤(꼬리 세그먼트)로 붙는다.
                        friend_kinds.append(friend_kind)
                        friend_pos, friend_kind = spawn_food(snake, len(assets.food_frames))
                        center = (
                            PLAYFIELD_OFFSET_X + new_head[0] * CELL_SIZE + CELL_SIZE // 2,
                            PLAYFIELD_OFFSET_Y + new_head[1] * CELL_SIZE + CELL_SIZE // 2,
                        )
                        sparks.append(SparkEffect(center=center))
                    else:
                        snake.pop()

        if mode == "title":
            draw_background(screen, assets.background_tile, assets.grid_overlay)
            title_surf = font_title.render("돌려부리", True, (20, 20, 20))
            screen.blit(title_surf, title_surf.get_rect(center=(SCREEN_WIDTH // 2, 180)))
            subtitle = font.render("맵을 돌아다니며 친구들을 구출하자!", True, (60, 60, 60))
            screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 220)))
            for idx, (rect, label) in enumerate([(btn_start, "게임시작"), (btn_howto, "게임방법")]):
                draw_card(screen, rect)
                color = (20, 20, 20) if idx == menu_index else (90, 90, 90)
                t = font.render(label, True, color)
                screen.blit(t, t.get_rect(center=rect.center))
            esc = font_small.render("ESC: 종료", True, (70, 70, 70))
            screen.blit(esc, (14, SCREEN_HEIGHT - 30))
        elif mode == "howto":
            draw_background(screen, assets.background_tile, assets.grid_overlay)
            title_surf = font_title.render("게임방법", True, (20, 20, 20))
            screen.blit(title_surf, title_surf.get_rect(center=(SCREEN_WIDTH // 2, 120)))
            card = pygame.Rect((SCREEN_WIDTH - 520) // 2, 170, 520, 240)
            draw_card(screen, card)
            lines = [
                "방향키로 이동합니다.",
                "꽁짜 햄버거를 먹으면 친구가 늘어나요!",
                "벽이나 내 몸에 부딪히면 게임오버!",
                "",
                "R: 재시작(게임오버)  ENTER: 타이틀",
            ]
            y = card.top + 34
            for line in lines:
                if line == "":
                    y += 12
                    continue
                surf = font.render(line, True, (50, 50, 50))
                screen.blit(surf, surf.get_rect(center=(card.centerx, y)))
                y += 30
            draw_card(screen, btn_back)
            back = font.render("뒤로", True, (20, 20, 20))
            screen.blit(back, back.get_rect(center=btn_back.center))
        else:
            draw_background(screen, assets.background_tile, assets.grid_overlay)
            draw_snake(
                screen,
                snake,
                assets.head_frames,
                assets.body_frames,
                assets.tail_frames,
                current_direction,
                assets.shadow,
                friend_head_frames=assets.friend_head_frames,
                friend_kinds=friend_kinds,
            )
            draw_food(screen, friend_pos, assets.food_frames, friend_kind, assets.shadow)
            draw_sparks(screen, assets.spark_frames, sparks)
            draw_hud(screen, assets.hud_panel, font, score, moves_per_second)

            if game_over:
                draw_game_over_ui(
                    screen,
                    font_title=font_title,
                    font=font,
                    font_small=font_small,
                    reason="벽이나 내 몸에 부딪혔어요!",
                    score=score,
                    hint="닉네임 입력 후 ENTER로 저장  |  ESC: 종료  |  R: 재시작",
                )
                draw_input_box(surface=screen, font=font_small, label="닉네임", value=lb_nickname, y=360)
                if lb_status:
                    rendered = font_small.render(lb_status, True, (60, 60, 60))
                    screen.blit(rendered, rendered.get_rect(center=(SCREEN_WIDTH // 2, 412)))
                if lb_top:
                    draw_leaderboard_list(
                        screen,
                        font=font_small,
                        title="TOP 5",
                        entries=[(e.nickname, e.score) for e in lb_top],
                        y=440,
                    )

        pygame.display.flip()

    if quit_on_exit:
        pygame.quit()


if __name__ == "__main__":
    run_game()

