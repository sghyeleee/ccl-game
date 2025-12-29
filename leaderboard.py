"""리더보드 화면 모듈.

게임별 상위 점수를 표시하는 화면을 제공합니다.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

# 색상 상수
MAIN_BG = (245, 245, 247)
ACCENT = (0, 0, 0)
INACTIVE_TEXT = (130, 130, 142)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 540

# 게임 목록 (게임 ID, 표시명)
GAMES = [
    ("flappy_bird", "날아부리"),
    ("sugar_game", "쌓아부리"),
    ("snake_survival", "모아부리"),
]

# 더미 데이터 (나중에 Firebase 연동 시 교체)
DUMMY_SCORES = {
    "flappy_bird": [
        ("부리킹", 999),
        ("햄버거왕", 850),
        ("치킨마스터", 720),
        ("피자러버", 650),
        ("스네이크", 580),
        ("점프맨", 510),
        ("플라이어", 450),
        ("버거보이", 380),
    ],
    "sugar_game": [
        ("슈가러시", 1200),
        ("달콤이", 1100),
        ("케이크장인", 950),
        ("캔디킹", 800),
        ("초코파이", 720),
        ("사탕왕", 650),
        ("마카롱", 580),
        ("도넛맨", 500),
    ],
    "snake_survival": [
        ("뱀술사", 1500),
        ("서바이버", 1350),
        ("생존왕", 1200),
        ("모아모아", 1050),
        ("친구수집가", 900),
        ("구출대장", 780),
        ("헬퍼", 650),
        ("레스큐", 520),
    ],
}

# 내 더미 점수 (실제 연동 시 Firebase에서 조회)
DUMMY_MY_SCORES = {
    "flappy_bird": 320,
    "sugar_game": 480,
    "snake_survival": 420,
}


def run_leaderboard(
    screen: pygame.Surface,
    nickname: str,
    font_medium: pygame.font.Font,
    font_small: pygame.font.Font,
    font_micro: pygame.font.Font,
    char_default: Optional[pygame.Surface],
    app_version: str,
) -> None:
    """리더보드 화면을 실행합니다.
    
    Args:
        screen: pygame 디스플레이 서피스
        nickname: 현재 유저 닉네임
        font_medium: 중간 크기 폰트
        font_small: 작은 크기 폰트
        font_micro: 아주 작은 크기 폰트
        char_default: 기본 캐릭터 이미지
        app_version: 앱 버전 문자열
    """
    clock = pygame.time.Clock()
    running = True
    
    # 현재 선택된 게임 인덱스
    selected_game_idx = 0
    
    # 게임 탭 버튼 rect 저장
    tab_rects: List[pygame.Rect] = []
    
    # 표시할 최대 랭킹 수
    max_display_ranks = 5
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    selected_game_idx = (selected_game_idx - 1) % len(GAMES)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    selected_game_idx = (selected_game_idx + 1) % len(GAMES)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 탭 클릭 체크
                for idx, rect in enumerate(tab_rects):
                    if rect.collidepoint(event.pos):
                        selected_game_idx = idx
                        break
        
        # 화면 그리기
        screen.fill(MAIN_BG)
        
        # === 상단 헤더 ===
        title = font_medium.render("랭킹", True, ACCENT)
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 82)))
        
        helper = font_micro.render("방향키로 게임 선택, ESC로 돌아가기", True, INACTIVE_TEXT)
        screen.blit(helper, helper.get_rect(center=(SCREEN_WIDTH // 2, 112)))
        
        # === 왼쪽 상단: 캐릭터 + 말풍선 ===
        if char_default:
            char_s = pygame.transform.smoothscale(char_default, (84, 84))
            char_pos = (40, 46)
            screen.blit(char_s, char_pos)
            
            # 말풍선 (닉네임 표시)
            if nickname:
                bubble_msg = f"{nickname}!"
            else:
                bubble_msg = "랭킹!"
            
            bubble_text = font_small.render(bubble_msg, True, ACCENT)
            text_width = bubble_text.get_width()
            bubble_w = max(100, text_width + 40)
            bubble_h = 52
            
            bubble_x = char_pos[0] + 84 + 6
            bubble_y = char_pos[1] - 2
            bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_w, bubble_h)
            
            # 그림자
            shadow_rect = bubble_rect.move(3, 3)
            pygame.draw.rect(screen, (0, 0, 0, 40), shadow_rect, border_radius=16)
            
            # 본체
            pygame.draw.rect(screen, (255, 255, 255), bubble_rect, border_radius=16)
            pygame.draw.rect(screen, (30, 30, 30), bubble_rect, width=2, border_radius=16)
            
            screen.blit(bubble_text, bubble_text.get_rect(center=bubble_rect.center))
        
        # === 랭킹 데이터 준비 ===
        current_game_id = GAMES[selected_game_idx][0]
        scores = DUMMY_SCORES.get(current_game_id, [])
        my_score = DUMMY_MY_SCORES.get(current_game_id, 0)
        
        # 내 등수 계산
        my_rank = len(scores) + 1  # 기본값: 리스트 끝
        for i, (name, score) in enumerate(scores):
            if my_score > score:
                my_rank = i + 1
                break
            elif my_score == score:
                my_rank = i + 2  # 동점이면 뒤 순위
        
        # === 오른쪽 상단: 내 점수 표시 ===
        my_box_w = 180
        my_box_h = 70
        my_box_x = SCREEN_WIDTH - my_box_w - 40
        my_box_y = 50
        my_box_rect = pygame.Rect(my_box_x, my_box_y, my_box_w, my_box_h)
        
        # 내 점수 배경 (강조 색상)
        pygame.draw.rect(screen, (60, 140, 200), my_box_rect, border_radius=12)
        pygame.draw.rect(screen, (30, 30, 30), my_box_rect, width=2, border_radius=12)
        
        # "내 기록" 라벨
        my_label = font_micro.render("내 기록", True, (255, 255, 255))
        screen.blit(my_label, my_label.get_rect(center=(my_box_rect.centerx, my_box_y + 14)))
        
        # 내 등수 + 점수
        my_rank_text = font_small.render(f"#{my_rank}", True, (255, 220, 100))
        screen.blit(my_rank_text, my_rank_text.get_rect(center=(my_box_rect.centerx - 35, my_box_y + 45)))
        
        my_score_text = font_small.render(f"{my_score:,}점", True, (255, 255, 255))
        screen.blit(my_score_text, my_score_text.get_rect(center=(my_box_rect.centerx + 35, my_box_y + 45)))
        
        # === 게임 탭 버튼들 ===
        tab_y = 145
        tab_h = 40
        tab_gap = 20
        total_tab_width = len(GAMES) * 140 + (len(GAMES) - 1) * tab_gap
        tab_start_x = (SCREEN_WIDTH - total_tab_width) // 2
        
        tab_rects = []
        for idx, (game_id, game_name) in enumerate(GAMES):
            tab_x = tab_start_x + idx * (140 + tab_gap)
            tab_rect = pygame.Rect(tab_x, tab_y, 140, tab_h)
            tab_rects.append(tab_rect)
            
            is_selected = idx == selected_game_idx
            mouse_pos = pygame.mouse.get_pos()
            is_hovered = tab_rect.collidepoint(mouse_pos)
            
            # 탭 배경
            if is_selected:
                tab_color = (50, 50, 60)
                text_color = (255, 255, 255)
            elif is_hovered:
                tab_color = (100, 100, 110)
                text_color = (255, 255, 255)
            else:
                tab_color = (200, 200, 210)
                text_color = ACCENT
            
            pygame.draw.rect(screen, tab_color, tab_rect, border_radius=8)
            if is_selected:
                pygame.draw.rect(screen, (30, 30, 30), tab_rect, width=2, border_radius=8)
            
            tab_text = font_small.render(game_name, True, text_color)
            screen.blit(tab_text, tab_text.get_rect(center=tab_rect.center))
        
        # 리스트 영역
        list_y_start = 200
        list_item_height = 40
        list_x = 120
        list_width = SCREEN_WIDTH - 240
        
        # 헤더
        header_rect = pygame.Rect(list_x, list_y_start - 5, list_width, 30)
        pygame.draw.rect(screen, (220, 220, 225), header_rect, border_radius=6)
        
        rank_header = font_micro.render("등수", True, INACTIVE_TEXT)
        name_header = font_micro.render("닉네임", True, INACTIVE_TEXT)
        score_header = font_micro.render("점수", True, INACTIVE_TEXT)
        
        screen.blit(rank_header, (list_x + 30, list_y_start))
        screen.blit(name_header, (list_x + 120, list_y_start))
        screen.blit(score_header, (list_x + list_width - 100, list_y_start))
        
        # 상위 n개 표시
        display_scores = scores[:max_display_ranks]
        for idx, (player_name, score) in enumerate(display_scores):
            rank = idx + 1
            item_y = list_y_start + 35 + idx * list_item_height
            
            # 배경 (홀수/짝수 구분)
            item_rect = pygame.Rect(list_x, item_y, list_width, list_item_height - 4)
            bg_color = (255, 255, 255) if idx % 2 == 0 else (248, 248, 250)
            pygame.draw.rect(screen, bg_color, item_rect, border_radius=6)
            pygame.draw.rect(screen, (230, 230, 235), item_rect, width=1, border_radius=6)
            
            # 등수 (1, 2, 3위는 특별 색상)
            rank_colors = {1: (255, 200, 50), 2: (192, 192, 200), 3: (205, 127, 50)}
            rank_color = rank_colors.get(rank, ACCENT)
            rank_text = font_small.render(f"{rank}", True, rank_color)
            screen.blit(rank_text, (list_x + 30, item_y + 8))
            
            # 닉네임
            name_text = font_small.render(player_name, True, ACCENT)
            screen.blit(name_text, (list_x + 120, item_y + 8))
            
            # 점수
            score_text = font_small.render(f"{score:,}", True, ACCENT)
            screen.blit(score_text, (list_x + list_width - 100, item_y + 8))
        
        # === 하단 푸터 ===
        footer = font_micro.render(f"ESC: 게임 선택으로  |  v{app_version}", True, INACTIVE_TEXT)
        screen.blit(footer, (40, SCREEN_HEIGHT - 50))
        
        pygame.display.flip()
        clock.tick(60)

