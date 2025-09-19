import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# pygame constants
TILE_SIZE = 100
FPS = 0.7

# Colors
COLOR_MAP = {
    'R': (240, 60, 60),  # red
    'G': (80, 220, 80),  # green
    'B': (100, 150, 220),  # blue
    'Y': (255, 245, 100),  # yellow
    'CY': (200, 245, 245),  # cyan
    'MG': (230, 110, 230),  # magenta
    'PU': (200, 170, 200),  # purple
    'T': (160, 220, 220),  # teal
    'NV': (90, 130, 220),  # navy
    'BK': (0, 0, 0),        # black
    'W': (255, 255, 255),   # white
    'O': (255, 180, 100),   # orange
    'PK': (255, 160, 180),  # pink
    'LG': (230, 230, 230)   # light grey
}

# Exclude 'black'
AVAILABLE_COLORS = [color for color in COLOR_MAP if color != 'BK']

POINTS_FOR_WIN = 20
POINTS_FOR_EXTRA_RESOURCE = 5
