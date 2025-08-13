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
    'red': (240, 0, 0),
    'green': (0, 240, 0),
    'blue': (0, 0, 240),
    'yellow': (255, 255, 0),
    'aqua': (0, 255, 255),
    'magenta': (255, 0, 255),
    'silver': (192, 192, 192),
    'gray': (128, 128, 128),
    'maroon': (128, 0, 0),
    'olive': (128, 128, 0),
    'purple': (128, 0, 128),
    'teal': (0, 128, 128),
    'navy': (0, 0, 128),
    'black': (0, 0, 0),
    'white': (255, 255, 255)
}

# Exclude 'black'
AVAILABLE_COLORS = [color for color in COLOR_MAP if color not in ('black')]
