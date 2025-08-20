from dataclasses import replace

from config import DEFAULT_CONFIG, GameConfig
from game import Game
from logger import GameLogger
from player import NANO, MINI, FOUR_1, FOUR_0, HUMAN, LLAMA_3_3B


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    DEFAULT_CONFIG,
    players=[LLAMA_3_3B, LLAMA_3_3B],
    grid_size=3,
    # colors=['R', 'B'],
    # resource_mode='manual',
    grid=[['R', 'R', 'R'], ['G', 'R', 'G'], ['R','G', 'R']],
    # manual_resources = [{'R':4, 'B':1, 'G':1}, {'R':2, 'B':2, 'G': 2}]
)

# set LOGGER = GameLogger() to enable logging to a file, or None to disable logging
LOGGER = GameLogger()

if __name__ == "__main__":
    
    Game(config=CONFIG, logger=LOGGER).run()