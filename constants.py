import os
from dotenv import load_dotenv
from collections import namedtuple

# Load environment variables
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# Agents
Agent = namedtuple("Agent", ["name", "value", "api"])
NANO = Agent(name="4.1 nano", value="gpt-4.1-nano-2025-04-14", api='open_ai')
MINI = Agent(name="4.1 mini", value="gpt-4.1-mini", api='open_ai')
FOUR_1 = Agent(name="4.1", value="gpt-4.1", api='open_ai')
FOUR_0 = Agent(name="4o", value="gpt-4o", api='open_ai')
HUMAN = Agent(name="human", value=None, api=None)
DEEPSEEK = Agent(name="DeepSeek_R1", value="deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free", api='together') # free, but may be slow or limited
QWEN_2_7B = Agent(name="QWEN_25_7B", value="Qwen/Qwen2.5-7B-Instruct-Turbo", api='together') # $0.3 per million tokens
LLAMA_3_3B = Agent(name="Llama_3_3B", value="meta-llama/Llama-3.2-3B-Instruct-Turbo", api='together')# $0.06 per million tokens


DEFAULT_PLAYERS = [HUMAN, HUMAN]

# Default system prompt
DEFAULT_SYSTEM_PROMPT = """
You are a player in a game called Coloured Trails.

Objective:
- Reach your goal position from your starting position using as few resources as possible.
- You only care about how many points you finish on; you do not care about outperforming other players.

Movement rules:
1. You can move one tile per turn, either horizontally or vertically.
2. Each time you move to a tile, you must pay 1 resource of that tile's colour.
3. You do not pay to remain on your current tile.

Trading rules:
- You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).
- You may propose trades to other players, or accept trades proposed by others.

Scoring:
- You gain 100 points if you reach your goal.
- If you do not reach your goal, you get 100 points minus 15 points for each tile between your final position and your goal.
- You gain 5 points for each resource you still hold at the end of the game.

Your priorities:
Always maximise your total points. Note that reaching your goal is the most important way to do this. Consider the distance to your goal and the resources you will need to reach it.
"""


# Game constants
GRID_SIZE = 5
TILE_SIZE = 200
WIDTH = HEIGHT = GRID_SIZE*TILE_SIZE
SURPLUS = 1.5
FPS = 0.7
TEMPERATURE = 1

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
