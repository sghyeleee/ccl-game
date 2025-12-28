import pygame
from firebase.score_repository import get_leaderboard


class LeaderboardUI:
    def __init__(self, screen, font):
        self.screen = screen
        self.font = font
        self.entries = []

    def load(self):
        self.entries = get_leaderboard(10)

    def draw(self):
        title = self.font.render("Leaderboard", True, (255, 255, 0))
        self.screen.blit(title, (100, 50))

        for i, entry in enumerate(self.entries):
            text = self.font.render(
                f"{i + 1}. {entry['username']} - {entry['score']}",
                True,
                (255, 255, 255)
            )
            self.screen.blit(text, (100, 100 + i * 35))
