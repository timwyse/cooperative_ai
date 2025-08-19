import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# pygame constants
TILE_SIZE = 100
FPS = 0.7

# Colors
COLOR_MAP = {
    'R': (240, 0, 0), # red
    'G': (0, 240, 0), # green
    'B': (0, 0, 240), # blue
    'Y': (255, 255, 0), # yellow
    'CY': (0, 255, 255), # cyan
    'MG': (255, 0, 255), # magenta
    'PU': (128, 0, 128), # purple
    'T': (0, 128, 128), # teal
    'NV': (0, 0, 128), # navy
    'BK': (0, 0, 0), # black
    'W': (255, 255, 255), # white
    'O': (255, 165, 0), # orange
    'PK': (255, 192, 203) # pink
}


# Exclude 'black'
AVAILABLE_COLORS = [color for color in COLOR_MAP if color != 'BK']
