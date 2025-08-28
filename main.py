from dataclasses import replace

from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import GameLogger
from agents import *


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    DEFAULT_CONFIG, # can use DEFAULT_CONFIG or load a specific configs here eg load_config("configs/fitn_3.yaml"),
    players=[LLAMA_3_3B, LLAMA_3_3B],
    grid_size=5,
    colors=['R', 'B', 'G', 'Y'],
    resource_mode='manual',
    grid=[['G', 'B', 'R', 'B', 'R'],
          ['R', 'Y', 'B', 'R', 'B'],
          ['B', 'R', 'Y', 'B', 'R'],
          ['R', 'B', 'R', 'Y', 'B'],
          ['B', 'R', 'B', 'R', 'G'],
          ],
    manual_resources = [{'R':20, 'G': 4}, {'B':20, 'G': 4}],
# manual_goal_positions=[(3, 4), (3, 4)],
)




# set LOGGER = GameLogger() to enable logging to a file, or None to disable logging
LOGGER = GameLogger()

if __name__ == "__main__":
    print(f"""
          ******

          Starting new Game with parameters: {CONFIG}

          ******
          """)
    Game(config=CONFIG, logger=LOGGER).run()