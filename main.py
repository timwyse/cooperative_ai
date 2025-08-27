from dataclasses import replace

from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import GameLogger
# from player import NANO, MINI, FOUR_1, FOUR_0, HUMAN, LLAMA_3_3B, QWEN_2_7B, DEEPSEEK
from agents import *


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    DEFAULT_CONFIG,
    players=[QWEN_2_7B, QWEN_2_7B],
    grid_size=3,
    colors=['R', 'B'],
    # resource_mode='manual',
    grid=[['R', 'B', 'R'], ['R', 'B', 'R'], ['R','B', 'B']],
    # manual_resources = [{'R':4, 'B':1, 'G':1}, {'R':2, 'B':2, 'G': 2}]
)

# Alternatively, load a config from a JSON or YAML file
# CONFIG = load_config("configs/full_info_trade_needed.yaml")



# set LOGGER = GameLogger() to enable logging to a file, or None to disable logging
LOGGER = GameLogger()

if __name__ == "__main__":
    print(f"""
          ******

          Starting new Game with parameters: {CONFIG}

          ******
          """)
    Game(config=CONFIG, logger=LOGGER).run()