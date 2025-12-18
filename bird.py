# flappy_fun.py
import math
import random
import sys
from typing import Optional, Tuple, List

import pygame

WIDTH, HEIGHT = 480, 640
FPS = 60

GROUND_HEIGHT = 90

# Bird
BIRD_X = 120
BIRD_RADIUS = 16

# Physics (px/s^2, px/s)
GRAVITY = 1850
JUMP_VELOCITY = -440  # <- 여기로 점프 높이 조절 (덜 튀게 하려면 -420~-360)

# Base pipe settings (difficulty will override progressively)
PIPE_WIDTH = 72
BASE_PIPE_GAP = 168
BASE_PIPE_SPEED = 220       # px/s
BASE_SPAWN_INTERVAL = 1.22  # seconds

# Difficulty clamps
MIN_PIPE_GAP = 118
MAX_PIPE_SPEED = 420
MIN_SPAWN_INTERVAL = 0.86

# Colors helpers
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t)), int(lerp(c1[1], c2[1], t)), int(lerp(c1[2], c2[2], t)))

class Bird:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = float(BIRD_X)
        self.y = float(HEIGHT * 0.45)
        self.vy = 0.0

    def jump(self):
        self.vy = JUMP_VELOCITY

    def update(self, dt: float):
        self.vy += GRAVITY * dt
        self.y += self.vy * dt

    @property
    def center(self):
        return (self.x, self.y)

    @property
    def rect(self):
        r = BIRD_RADIUS
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)

class Difficulty:
    """
    score 기반으로 속도↑, 간격↓, 스폰 간격↓, 특수 장애물 비율↑
    """
    def __init__(self):
        self.pipe_speed = BASE_PIPE_SPEED
        self.pipe_gap = BASE_PIPE_GAP
        self.spawn_interval = BASE_SPAWN_INTERVAL

    def update(self, score: int):
        # 점수 1당 조금씩 빡세게
        speed = BASE_PIPE_SPEED + score * 6.0
        gap = BASE_PIPE_GAP - score * 1.25
        interval = BASE_SPAWN_INTERVAL - score * 0.010

        self.pipe_speed = clamp(speed, BASE_PIPE_SPEED, MAX_PIPE_SPEED)
        self.pipe_gap = clamp(gap, MIN_PIPE_GAP, BASE_PIPE_GAP)
        self.spawn_interval = clamp(interval, MIN_SPAWN_INTERVAL, BASE_SPAWN_INTERVAL)

    def special_chance(self, score: int) -> float:
        # 점수 올라갈수록 특수 장애물 비율 증가
        return clamp(0.10 + score * 0.012, 0.10, 0.55)

class Obstacle:
    def update(self, dt: float, speed: float):
        raise NotImplementedError

    def draw(self, surf: pygame.Surface):
        raise NotImplementedError

    def is_offscreen(self) -> bool:
        raise NotImplementedError

    def collides(self, bird: Bird) -> bool:
        raise NotImplementedError

    def score_passed(self, bird_x: float) -> bool:
        return False

    def score_collected(self, bird: Bird) -> int:
        return 0

# ---------- Visuals: procedural pipe texture ----------
def draw_pipe_block(surf: pygame.Surface, rect: pygame.Rect, theme: str):
    # theme sets palette
    if theme == "forest":
        base = (70, 200, 90)
        dark = (45, 165, 70)
        cap = (90, 230, 110)
        stripe = (35, 120, 55)
    elif theme == "ice":
        base = (90, 190, 230)
        dark = (60, 140, 190)
        cap = (120, 220, 250)
        stripe = (50, 110, 160)
    elif theme == "lava":
        base = (240, 110, 70)
        dark = (190, 70, 40)
        cap = (255, 150, 110)
        stripe = (140, 35, 25)
    else:
        base = (150, 200, 90)
        dark = (110, 160, 60)
        cap = (175, 230, 120)
        stripe = (80, 120, 40)

    # main body
    pygame.draw.rect(surf, base, rect, border_radius=8)
    inner = rect.inflate(-10, -10)
    if inner.width > 0 and inner.height > 0:
        pygame.draw.rect(surf, dark, inner, border_radius=7)

    # stripes (texture)
    step = 14
    x0 = rect.x + 8
    x1 = rect.right - 8
    for x in range(x0, x1, step):
        stripe_rect = pygame.Rect(x, rect.y + 6, 5, rect.height - 12)
        pygame.draw.rect(surf, stripe, stripe_rect, border_radius=3)

    # cap (simple 3D lip)
    cap_h = 14
    cap_rect = pygame.Rect(rect.x - 6, rect.y, rect.width + 12, cap_h)
    pygame.draw.rect(surf, cap, cap_rect, border_radius=10)

# ---------- Coin ----------
class Coin:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.r = 10
        self.collected = False

    def update(self, dt: float, speed: float):
        self.x -= speed * dt

    def draw(self, surf: pygame.Surface):
        if self.collected:
            return
        pygame.draw.circle(surf, (255, 220, 60), (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (255, 245, 170), (int(self.x - 3), int(self.y - 3)), 4)

    def is_offscreen(self):
        return self.x + self.r < 0

    def collides(self, bird: Bird) -> bool:
        if self.collected:
            return False
        dx = bird.x - self.x
        dy = bird.y - self.y
        return (dx * dx + dy * dy) <= (BIRD_RADIUS + self.r) ** 2

# ---------- Pipe variants ----------
class PipePair(Obstacle):
    def __init__(self, x: float, gap_center: float, gap: float, theme: str):
        self.x = float(x)
        self.gap_center = float(gap_center)
        self.gap = float(gap)
        self.theme = theme
        self.passed = False
        self.coin: Optional[Coin] = None

    @property
    def gap_top(self):
        return self.gap_center - self.gap / 2

    @property
    def gap_bottom(self):
        return self.gap_center + self.gap / 2

    def update(self, dt: float, speed: float):
        self.x -= speed * dt
        if self.coin:
            self.coin.update(dt, speed)

    def make_coin(self):
        # coin in the middle of the gap
        self.coin = Coin(self.x + PIPE_WIDTH * 0.5, self.gap_center)

    def is_offscreen(self) -> bool:
        off = self.x + PIPE_WIDTH < 0
        if self.coin:
            off = off and self.coin.is_offscreen()
        return off

    def collides(self, bird: Bird) -> bool:
        top_h = int(self.gap_top)
        bottom_y = int(self.gap_bottom)
        ground_y = HEIGHT - GROUND_HEIGHT
        bottom_h = max(0, ground_y - bottom_y)

        top_rect = pygame.Rect(int(self.x), 0, PIPE_WIDTH, max(0, top_h))
        bottom_rect = pygame.Rect(int(self.x), bottom_y, PIPE_WIDTH, bottom_h)

        return bird.rect.colliderect(top_rect) or bird.rect.colliderect(bottom_rect)

    def score_passed(self, bird_x: float) -> bool:
        if not self.passed and (self.x + PIPE_WIDTH) < bird_x:
            self.passed = True
            return True
        return False

    def score_collected(self, bird: Bird) -> int:
        if self.coin and self.coin.collides(bird):
            self.coin.collected = True
            return 1
        return 0

    def draw(self, surf: pygame.Surface):
        top_rect = pygame.Rect(int(self.x), 0, PIPE_WIDTH, int(self.gap_top))
        ground_y = HEIGHT - GROUND_HEIGHT
        bottom_rect = pygame.Rect(int(self.x), int(self.gap_bottom), PIPE_WIDTH, int(ground_y - self.gap_bottom))

        if top_rect.height > 0:
            draw_pipe_block(surf, top_rect, self.theme)
        if bottom_rect.height > 0:
            draw_pipe_block(surf, bottom_rect, self.theme)

        if self.coin:
            self.coin.draw(surf)

class MovingGapPipe(PipePair):
    # gap center oscillates
    def __init__(self, x: float, gap_center: float, gap: float, theme: str):
        super().__init__(x, gap_center, gap, theme)
        self.base_center = gap_center
        self.amp = random.uniform(28, 60)
        self.freq = random.uniform(1.2, 2.2)
        self.phase = random.uniform(0, math.tau)
        self.t = 0.0

    def update(self, dt: float, speed: float):
        self.t += dt
        self.gap_center = self.base_center + math.sin(self.t * self.freq * math.tau + self.phase) * self.amp
        # keep in bounds
        margin_top = 70
        margin_bottom = GROUND_HEIGHT + 70
        self.gap_center = clamp(self.gap_center, margin_top + self.gap / 2, HEIGHT - margin_bottom - self.gap / 2)
        super().update(dt, speed)

class CrusherPipe(PipePair):
    # gap size pulses smaller for a moment
    def __init__(self, x: float, gap_center: float, gap: float, theme: str):
        super().__init__(x, gap_center, gap, theme)
        self.base_gap = gap
        self.t = 0.0
        self.pulse_freq = random.uniform(0.8, 1.35)
        self.squeeze = random.uniform(0.25, 0.42)  # max squeeze ratio

    def update(self, dt: float, speed: float):
        self.t += dt
        # 0..1..0 wave
        w = (math.sin(self.t * self.pulse_freq * math.tau) + 1) * 0.5
        # squeeze a bit (never below MIN_PIPE_GAP)
        squeezed = self.base_gap * (1.0 - self.squeeze * w)
        self.gap = max(MIN_PIPE_GAP, squeezed)
        super().update(dt, speed)

# ---------- Saw hazard ----------
class Saw(Obstacle):
    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.r = random.randint(18, 26)
        self.spin = random.uniform(5.0, 10.0)
        self.ang = random.uniform(0, math.tau)
        self.passed = False

    def update(self, dt: float, speed: float):
        self.x -= speed * dt * 1.05
        self.ang += self.spin * dt

    def is_offscreen(self) -> bool:
        return self.x + self.r < 0

    def collides(self, bird: Bird) -> bool:
        dx = bird.x - self.x
        dy = bird.y - self.y
        return (dx * dx + dy * dy) <= (BIRD_RADIUS + self.r - 2) ** 2

    def score_passed(self, bird_x: float) -> bool:
        if not self.passed and (self.x + self.r) < bird_x:
            self.passed = True
            return True
        return False

    def draw(self, surf: pygame.Surface):
        # gear-ish
        pygame.draw.circle(surf, (200, 200, 210), (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (120, 120, 135), (int(self.x), int(self.y)), int(self.r * 0.55))
        # spikes
        spikes = 10
        for i in range(spikes):
            a = self.ang + i * (math.tau / spikes)
            x1 = self.x + math.cos(a) * (self.r * 0.55)
            y1 = self.y + math.sin(a) * (self.r * 0.55)
            x2 = self.x + math.cos(a) * (self.r * 1.05)
            y2 = self.y + math.sin(a) * (self.r * 1.05)
            pygame.draw.line(surf, (90, 90, 105), (x1, y1), (x2, y2), 3)

# ---------- Background / ground ----------
def draw_background(screen: pygame.Surface, t: float, score: int):
    # day-night cycle
    cycle = (math.sin(t * 0.08) + 1) * 0.5  # 0..1
    sky_day = (135, 206, 235)
    sky_night = (30, 35, 65)
    sky = lerp_color(sky_night, sky_day, cycle)
    screen.fill(sky)

    # stars at night-ish
    star_alpha = int(140 * (1.0 - cycle))
    if star_alpha > 0:
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        random.seed(999)
        for _ in range(50):
            x = random.randint(0, WIDTH)
            y = random.randint(0, 260)
            r = random.choice([1, 1, 2])
            s.fill((255, 255, 255, star_alpha), pygame.Rect(x, y, r, r))
        screen.blit(s, (0, 0))

    # clouds (parallax dots)
    random.seed(1234)
    for layer in range(2):
        for _ in range(14 if layer == 0 else 10):
            cx = random.randint(0, WIDTH)
            cy = random.randint(50, 280)
            r = random.randint(14, 34)
            speed = (10 if layer == 0 else 18) + random.uniform(0, 6)
            x = (cx - (t * speed) % (WIDTH + 200)) + WIDTH
            col = (255, 255, 255) if cycle > 0.35 else (200, 205, 220)
            pygame.draw.circle(screen, col, (int(x % (WIDTH + 200)) - 100, cy + layer * 18), r)

    # tiny vibe text
    if score >= 15:
        # subtle “hard mode” hint
        font = pygame.font.Font(None, 18)
        txt = font.render("HARD MODE", True, (10, 10, 10))
        screen.blit(txt, (WIDTH - txt.get_width() - 14, HEIGHT - GROUND_HEIGHT - 22))

def draw_ground(screen: pygame.Surface, scroll_x: float):
    ground_y = HEIGHT - GROUND_HEIGHT
    pygame.draw.rect(screen, (95, 75, 60), (0, ground_y, WIDTH, GROUND_HEIGHT))
    pygame.draw.rect(screen, (120, 95, 75), (0, ground_y, WIDTH, 8))

    stripe_w = 22
    for i in range(-10, WIDTH // stripe_w + 20):
        x = int(i * stripe_w - (scroll_x % stripe_w))
        pygame.draw.rect(screen, (110, 86, 68), (x, ground_y + 10, 10, GROUND_HEIGHT - 18), border_radius=4)

def draw_bird(screen: pygame.Surface, bird: Bird):
    # body
    pygame.draw.circle(screen, (255, 220, 50), (int(bird.x), int(bird.y)), BIRD_RADIUS)
    # eye
    pygame.draw.circle(screen, (255, 255, 255), (int(bird.x + 6), int(bird.y - 6)), 6)
    pygame.draw.circle(screen, (0, 0, 0), (int(bird.x + 8), int(bird.y - 6)), 2)
    # beak
    pygame.draw.polygon(
        screen,
        (255, 140, 60),
        [(bird.x + 14, bird.y), (bird.x + 30, bird.y - 6), (bird.x + 30, bird.y + 6)]
    )
    # little trail when falling fast
    if bird.vy > 350:
        pygame.draw.circle(screen, (255, 255, 255), (int(bird.x - 18), int(bird.y + 10)), 4)

def pick_theme(score: int) -> str:
    # themes rotate as score grows
    themes = ["forest", "ice", "lava"]
    idx = (score // 8) % len(themes)
    return themes[idx]

def spawn_obstacle(score: int, difficulty: Difficulty) -> Obstacle:
    # common gap center range
    gap = difficulty.pipe_gap
    margin_top = 70
    margin_bottom = GROUND_HEIGHT + 70
    center_min = margin_top + gap / 2
    center_max = HEIGHT - margin_bottom - gap / 2
    gap_center = random.uniform(center_min, center_max)
    x = WIDTH + 60

    theme = pick_theme(score)

    # decide obstacle type
    special = random.random() < difficulty.special_chance(score)

    if special:
        # mix special types
        roll = random.random()
        if roll < 0.45 and score >= 6:
            ob = MovingGapPipe(x, gap_center, gap, theme)
        elif roll < 0.80 and score >= 12:
            ob = CrusherPipe(x, gap_center, gap, theme)
        else:
            # saw hazard (placed away from ground/top)
            y = random.uniform(100, HEIGHT - GROUND_HEIGHT - 120)
            ob = Saw(x, y)
    else:
        ob = PipePair(x, gap_center, gap, theme)

    # coin chance (only for pipes)
    if isinstance(ob, PipePair):
        # more coins in early game, fewer later
        coin_ch = clamp(0.35 - score * 0.010, 0.12, 0.35)
        if random.random() < coin_ch:
            ob.make_coin()

    return ob

def main():
    pygame.init()
    pygame.display.set_caption("Flappy FUN (Pygame)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    font = pygame.font.Font(None, 28)
    font_big = pygame.font.Font(None, 44)
    font_small = pygame.font.Font(None, 20)

    bird = Bird()
    difficulty = Difficulty()

    obstacles: List[Obstacle] = []
    score = 0
    hi = 0

    game_state = "READY"  # READY / PLAYING / DEAD
    spawn_timer = 0.0
    t = 0.0
    ground_scroll = 0.0

    def reset():
        nonlocal obstacles, score, spawn_timer, game_state, ground_scroll
        bird.reset()
        obstacles = []
        score = 0
        spawn_timer = 0.0
        game_state = "READY"
        ground_scroll = 0.0
        difficulty.update(0)

    reset()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = clamp(dt, 0.0, 1 / 20)  # prevent dt spikes
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                if event.key in (pygame.K_SPACE, pygame.K_UP):
                    if game_state in ("READY", "PLAYING"):
                        if game_state == "READY":
                            game_state = "PLAYING"
                        bird.jump()
                    else:
                        reset()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game_state in ("READY", "PLAYING"):
                    if game_state == "READY":
                        game_state = "PLAYING"
                    bird.jump()
                else:
                    reset()

        if game_state == "PLAYING":
            bird.update(dt)

            # difficulty update
            difficulty.update(score)

            spawn_timer += dt
            if spawn_timer >= difficulty.spawn_interval:
                spawn_timer -= difficulty.spawn_interval
                obstacles.append(spawn_obstacle(score, difficulty))

            # move & cleanup
            for ob in obstacles:
                ob.update(dt, difficulty.pipe_speed)

            obstacles = [ob for ob in obstacles if not ob.is_offscreen()]

            # scoring: pass obstacles (+1) + collect coins (+1)
            for ob in obstacles:
                if ob.score_passed(bird.x):
                    score += 1
                    hi = max(hi, score)

                score += ob.score_collected(bird)

            # clamp top
            if bird.y - BIRD_RADIUS < 0:
                bird.y = BIRD_RADIUS
                bird.vy = 0

            # ground collision
            ground_y = HEIGHT - GROUND_HEIGHT
            if bird.y + BIRD_RADIUS >= ground_y:
                bird.y = ground_y - BIRD_RADIUS
                game_state = "DEAD"

            # obstacle collision
            if any(ob.collides(bird) for ob in obstacles):
                game_state = "DEAD"

            ground_scroll += difficulty.pipe_speed * dt

        # draw
        draw_background(screen, t, score)

        for ob in obstacles:
            ob.draw(screen)

        draw_ground(screen, ground_scroll)
        draw_bird(screen, bird)

        # HUD
        score_s = font.render(f"{score}", True, (10, 10, 10))
        screen.blit(score_s, (18, 16))
        hi_s = font.render(f"HI {hi}", True, (10, 10, 10))
        screen.blit(hi_s, (WIDTH - hi_s.get_width() - 18, 16))

        # difficulty indicator (not too noisy)
        diff_s = font_small.render(
            f"speed {int(difficulty.pipe_speed)}  gap {int(difficulty.pipe_gap)}  spawn {difficulty.spawn_interval:.2f}s",
            True, (10, 10, 10)
        )
        screen.blit(diff_s, (18, 48))

        if game_state == "READY":
            msg = font_big.render("CLICK / SPACE TO FLAP", True, (10, 10, 10))
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 220))
            sub = font.render("Pipes + Coins + Specials", True, (10, 10, 10))
            screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 270))

        if game_state == "DEAD":
            over = font_big.render("GAME OVER", True, (10, 10, 10))
            screen.blit(over, (WIDTH // 2 - over.get_width() // 2, 220))
            tip = font.render("Press SPACE / Click to restart", True, (10, 10, 10))
            screen.blit(tip, (WIDTH // 2 - tip.get_width() // 2, 270))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()