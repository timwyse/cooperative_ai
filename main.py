from dataclasses import replace

from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import GameLogger
from agents import *


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    DEFAULT_CONFIG,
    # players=[QWEN_2_7B, QWEN_2_7B],
    grid_size=7,
    colors=['R', 'B', 'G'],
    resource_mode='manual',
    grid=[['G', 'G', 'B', 'B', 'B', 'B', 'B'],
          ['G', 'R', 'R', 'R', 'R', 'R', 'B'],
          ['B', 'R', 'R', 'R', 'R', 'R', 'B'],
          ['B', 'R', 'R', 'R', 'B', 'B', 'R'],
          ['B', 'R', 'R', 'B', 'B', 'B', 'B'], 
          ['B', 'R', 'R', 'B', 'R', 'R', 'B'],
          ['B', 'B', 'B', 'B', 'R', 'R', 'G']
          ],
    manual_resources = [{'R':20, 'G': 4}, {'B':20, 'G': 4}]
)

# Alternatively, load a config from a JSON or YAML file
CONFIG = load_config("configs/fitn_3.yaml")



# set LOGGER = GameLogger() to enable logging to a file, or None to disable logging
LOGGER = GameLogger()

if __name__ == "__main__":
    print(f"""
          ******

          Starting new Game with parameters: {CONFIG}

          ******
          """)
    Game(config=CONFIG, logger=LOGGER).run()