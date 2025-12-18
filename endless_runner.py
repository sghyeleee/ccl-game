import pygame
import random
import sys

# 화면 설정
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# 색상 정의
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)

# 플레이어 설정
class Player:
    def __init__(self):
        self.x = 100
        self.y = SCREEN_HEIGHT - 150
        self.width = 50
        self.height = 80
        self.velocity_y = 0
        self.is_jumping = False
        self.is_crouching = False
        self.speed = 5

    def jump(self):
        if not self.is_crouching:
            if not self.is_jumping:
                # 첫 번째 점프
                self.velocity_y = -18
                self.is_jumping = True
            elif self.velocity_y > -5:  # 상승 중이고 속도가 충분히 느리지 않을 때
                # 이단 점프 (더 높이 올라감)
                self.velocity_y = -14  # 첫 번째 점프보다 약간 낮게

    def crouch(self):
        if not self.is_jumping:
            self.is_crouching = True
            self.height = 40
            self.y = SCREEN_HEIGHT - 110

    def stand_up(self):
        self.is_crouching = False
        self.height = 80
        self.y = SCREEN_HEIGHT - 150

    def update(self):
        # 중력 적용
        if self.is_jumping:
            self.velocity_y += 0.8
            self.y += self.velocity_y

            # 착지
            if self.y >= SCREEN_HEIGHT - 150:
                self.y = SCREEN_HEIGHT - 150
                self.velocity_y = 0
                self.is_jumping = False

    def draw(self, screen):
        # 플레이어 몸체
        pygame.draw.rect(screen, BLUE, (self.x, self.y, self.width, self.height))
        # 플레이어 눈
        eye_size = 8
        pygame.draw.circle(screen, WHITE, (self.x + 15, self.y + 15), eye_size)
        pygame.draw.circle(screen, BLACK, (self.x + 18, self.y + 15), 4)

# 장애물 설정
class Obstacle:
    def __init__(self, x, height, color, floating=False):
        self.x = x
        if floating:
            # 공중에 떠있는 장애물 (숙기로 피해야 함)
            self.y = SCREEN_HEIGHT - 200 - random.randint(0, 100)  # 200-300px 높이
        else:
            # 땅에 붙은 장애물 (점프로 넘어야 함)
            self.y = SCREEN_HEIGHT - height
        self.width = 30
        self.height = height
        self.color = color
        self.speed = 8
        self.floating = floating

    def update(self):
        self.x -= self.speed

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))

    def collide(self, player):
        player_rect = pygame.Rect(player.x, player.y, player.width, player.height)
        obstacle_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        return player_rect.colliderect(obstacle_rect)

# 별 효과
class Star:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = random.randint(2, 6)
        self.speed = random.randint(1, 3)
        self.color = random.choice([WHITE, YELLOW, CYAN])

    def update(self):
        self.x -= self.speed
        self.y += random.randint(-1, 1)

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (self.x, self.y), self.size)

# 게임 클래스
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.player = Player()
        self.obstacles = []
        self.stars = []
        self.score = 0
        self.high_score = 0
        self.game_over = False
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.spawn_timer = 0
        self.star_timer = 0

        # 배경은 나중에 초기화

    def create_gradient_background(self):
        background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            # 하늘에서 땅으로 그라데이션
            r = int(135 - (135 * y / SCREEN_HEIGHT))  # 어두운 파랑에서 밝은 파랑으로
            g = int(206 - (106 * y / SCREEN_HEIGHT))
            b = int(235 - (35 * y / SCREEN_HEIGHT))
            pygame.draw.line(background, (r, g, b), (0, y), (SCREEN_WIDTH, y))
        return background

    def spawn_obstacle(self):
        # 지상 장애물과 공중 장애물 생성
        is_floating = random.random() < 0.4  # 40% 확률로 공중 장애물

        if is_floating:
            # 공중 장애물 (숙기로 피함)
            height = random.choice([30, 40, 50, 60])
            color = CYAN  # 공중 장애물은 다른 색으로 구분
        else:
            # 지상 장애물 (점프로 넘음)
            height = random.choice([60, 80, 100, 120, 140, 160])
            color = random.choice([RED, GREEN, PURPLE, YELLOW])

        obstacle = Obstacle(SCREEN_WIDTH, height, color, is_floating)
        self.obstacles.append(obstacle)

    def spawn_star(self):
        x = SCREEN_WIDTH + random.randint(0, 200)
        y = random.randint(50, SCREEN_HEIGHT - 200)
        star = Star(x, y)
        self.stars.append(star)

    def update(self):
        if self.game_over:
            return

        # 플레이어 업데이트
        self.player.update()

        # 장애물 업데이트 및 충돌 검사
        for obstacle in self.obstacles[:]:
            obstacle.update()
            if obstacle.collide(self.player):
                self.game_over = True
                break

            # 화면 밖으로 나간 장애물 제거
            if obstacle.x < -obstacle.width:
                self.obstacles.remove(obstacle)

        # 별 업데이트
        for star in self.stars[:]:
            star.update()
            if star.x < -10:
                self.stars.remove(star)

        # 장애물 생성 (더 자주, 가끔 연달아)
        self.spawn_timer += 1
        spawn_interval = random.randint(45, 90)  # 0.75-1.5초마다
        if self.spawn_timer >= spawn_interval:
            self.spawn_obstacle()
            self.spawn_timer = 0
            # 30% 확률로 연달아 장애물 생성 (이단 점프 유도)
            if random.random() < 0.3:
                self.spawn_timer = spawn_interval - random.randint(20, 35)  # 0.3-0.6초 후에 다음 장애물

        # 별 생성
        self.star_timer += 1
        if self.star_timer >= random.randint(30, 60):
            self.spawn_star()
            self.star_timer = 0

        # 점수 증가
        self.score += 1

    def draw(self):
        # 배경 그리기
        self.screen.blit(self.background, (0, 0))

        # 땅 그리기
        pygame.draw.rect(self.screen, GREEN, (0, SCREEN_HEIGHT - 50, SCREEN_WIDTH, 50))

        # 별 그리기
        for star in self.stars:
            star.draw(self.screen)

        # 장애물 그리기
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)

        # 플레이어 그리기
        self.player.draw(self.screen)

        # 점수 표시
        score_text = self.font.render(f"점수: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 10))

        # 최고 점수 표시
        if self.score > self.high_score:
            self.high_score = self.score
        high_score_text = self.font.render(f"최고 점수: {self.high_score}", True, WHITE)
        self.screen.blit(high_score_text, (10, 50))

        # 게임 오버 화면
        if self.game_over:
            # 반투명 오버레이
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.fill(BLACK)
            overlay.set_alpha(150)
            self.screen.blit(overlay, (0, 0))

            # 게임 오버 텍스트
            game_over_text = self.font.render("게임 오버!", True, WHITE)
            restart_text = self.font.render("R키로 재시작, Q키로 종료", True, WHITE)
            final_score_text = self.font.render(f"최종 점수: {self.score}", True, YELLOW)

            self.screen.blit(game_over_text, (SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 - 50))
            self.screen.blit(final_score_text, (SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2))
            self.screen.blit(restart_text, (SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2 + 50))

    def reset(self):
        self.player = Player()
        self.obstacles = []
        self.stars = []
        self.score = 0
        self.game_over = False
        self.spawn_timer = 0
        self.star_timer = 0

def main():
    # 완전히 독립적으로 pygame 초기화
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("무한 달리기")

    game = Game(screen)
    game.background = game.create_gradient_background()  # 배경 초기화
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE or event.key == pygame.K_UP:
                    game.player.jump()
                elif event.key == pygame.K_DOWN:
                    game.player.crouch()
                elif event.key == pygame.K_r and game.game_over:
                    game.reset()
                elif event.key == pygame.K_q and game.game_over:
                    running = False
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_DOWN:
                    game.player.stand_up()

        game.update()
        game.draw()
        pygame.display.flip()
        game.clock.tick(60)

    pygame.quit()
    sys.exit()

def run_game():
    """메인 게임 런처에서 호출할 함수"""
    # 완전히 독립적으로 실행
    main()

if __name__ == "__main__":
    main()
