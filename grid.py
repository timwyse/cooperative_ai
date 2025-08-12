import random

class Tile:
    def __init__(self, color):
        self.color = color

class Grid:
    def __init__(self, size, player_colors):
        self.size = size
        self.tiles = self.generate_tiles(size, player_colors)
        self.tile_colors = [[tile.color for tile in row] for row in self.tiles]

    def generate_tiles(self, size, player_colors):
        num_tiles = size * size
        num_colors = len(player_colors)
        tiles_per_color = num_tiles // num_colors
        remaining_tiles = num_tiles % num_colors

        colors = []
        for color in player_colors:
            colors.extend([color] * tiles_per_color)
        colors.extend(player_colors[:remaining_tiles])
        random.shuffle(colors)

        return [[Tile(colors.pop()) for _ in range(size)] for _ in range(size)]

    def get_color(self, x, y):
        return self.tiles[y][x].color

    def get_adjacent(self, pos):
        x, y = pos
        adj = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.size and 0 <= ny < self.size:
                adj.append((nx, ny))
        return adj