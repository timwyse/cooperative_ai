import random
from constants import COLOR_MAP

available_colors  = [color for color in list(COLOR_MAP.keys()) if color not in ('BK')]

class Tile:
    def __init__(self, color):
        self.color = color

class Grid:
    def __init__(self, size, colors, grid=None):
        self.size = size
        if grid is None:
            self.tiles = self.generate_tiles(size, colors)
            
        else:
            if len(grid) != size or any(len(row) != size for row in grid):
                raise ValueError("Grid must be a square of the specified size.")
            if any(color not in COLOR_MAP for color in colors):
                raise ValueError(f"The colors list inputted uses invalid colors. Please ensure all colors are taken from {available_colors}.")
            if any(color not in colors for row in grid for color in row):
                raise ValueError(f"Grid contains colors not in colors list.")
            
            self.tiles = [[Tile(color) for color in row] for row in grid]
        self.tile_colors = [[tile.color for tile in row] for row in self.tiles]

    def generate_tiles(self, size, colors):
        num_tiles = size * size
        num_colors = len(colors)
        tiles_per_color = num_tiles // num_colors
        remaining_tiles = num_tiles % num_colors

        colors = []
        for color in colors:
            colors.extend([color] * tiles_per_color)
        colors.extend(colors[:remaining_tiles])
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
    
if __name__ == "__main__":
    grid = Grid(2, ['R', 'CY', 'B'], grid=[['R', 'CY'], ['B', 'B']])
    print("Grid size:", grid.size)
    print("Tile colors:", grid.tile_colors)
    print("Tile at (0, 0):", grid.get_color(0, 0))
    print("Adjacent tiles to (0, 0):", grid.get_adjacent((0, 0)))
