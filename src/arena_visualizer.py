from arena import Arena
import pygame
import heapq
from typing import List, Tuple

from card import TargetType
from unit import Owner

# Arena constants
WIDTH, HEIGHT = 19, 30
TILE_SIZE = 20  # Pixels per tile
SCREEN_WIDTH, SCREEN_HEIGHT = WIDTH * TILE_SIZE, HEIGHT * TILE_SIZE

# Colors
COLORS = {
    0: (220, 220, 220),  # Empty - Light Gray
    1: (0, 100, 255),  # River - Blue
    2: (139, 69, 19),  # Bridge - Brown
    3: (255, 0, 0),  # Crown Towers - Red
    4: (255, 215, 0),  # King Tower - Gold
    "start": (255, 255, 0),  # Green
    "goal": (255, 165, 0),  # Orange
    "path": (150, 255, 100),  # Light Green
    "tower_center": (255, 150, 0),
}

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Clash Royale Arena Pathfinding")

arena: Arena = Arena()
start_pos = None
goal_pos = None
path = []


def draw_grid():
    for y in range(HEIGHT):
        for x in range(WIDTH):
            color = COLORS[arena.tiles[y][x]]
            pygame.draw.rect(
                screen, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            )

            if (x, y) in path:
                pygame.draw.rect(
                    screen,
                    COLORS["path"],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                )

            if start_pos == (x, y):
                pygame.draw.rect(
                    screen,
                    COLORS["start"],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                )
            if goal_pos == (x, y):
                pygame.draw.rect(
                    screen,
                    COLORS["goal"],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                )

    for tower in arena.towers:
        pygame.draw.rect(
            screen,
            COLORS["tower_center"],
            (
                tower.center_x * TILE_SIZE,
                tower.center_y * TILE_SIZE,
                TILE_SIZE,
                TILE_SIZE,
            ),
        )

    # Grid lines
    for x in range(WIDTH):
        pygame.draw.line(
            screen, (50, 50, 50), (x * TILE_SIZE, 0), (x * TILE_SIZE, SCREEN_HEIGHT)
        )
    for y in range(HEIGHT):
        pygame.draw.line(
            screen, (50, 50, 50), (0, y * TILE_SIZE), (SCREEN_WIDTH, y * TILE_SIZE)
        )


running = True
while running:
    screen.fill((0, 0, 0))
    draw_grid()
    pygame.display.flip()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            x, y = event.pos[0] // TILE_SIZE, event.pos[1] // TILE_SIZE

            if event.button == 1:  # Left-click: Set start or goal
                if start_pos is None:
                    start_pos = (x, y)
                elif goal_pos is None:
                    goal_pos = (x, y)
                    path = arena.find_path(start_pos, goal_pos)
                else:
                    start_pos = None
                    goal_pos = None
                    path = []
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_a and start_pos is not None:
                goal_pos = None
                path = arena.get_target(start_pos, Owner.P1, [TargetType.GROUND]).path
                start_pos = None
            if event.key == pygame.K_b and start_pos is not None:
                goal_pos = None
                path = arena.get_target(start_pos, Owner.P2, [TargetType.GROUND]).path
                start_pos = None


pygame.quit()
