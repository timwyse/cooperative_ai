from dataclasses import replace

from agents import *
from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import GameLogger
import prompts as p


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    load_config("configs/mutual_trade_necessary.yaml"), # can use DEFAULT_CONFIG or load a specific configs here eg load_config("configs/simple_prisoners_dilemma.yaml"),
    players=[QWEN_2_7B, QWEN_2_7B],
#     grid_size=5,
#     colors=['R', 'B', 'G', 'Y', 'PK'],
#     resource_mode='manual',
#     grid=[['G', 'R', 'R', 'R', 'R'],
#           ['B', 'PK','PK','PK', 'R'],
#           ['B', 'PK','PK', 'PK', 'R'],
#           ['B', 'PK','PK', 'PK', 'B'],
#           ['B', 'B', 'B', 'R', 'G'],
#           ],
    manual_resources = [{'G':1, 'B': 3}, {'G':1, 'R': 3}],
# #     manual_start_positions=[(0, 0), (0, 4)],
# #     manual_goal_positions=[(4, 4), (4, 0)],

    # wait_for_enter=True,
    # display_gui=False,  # Disable Pygame window, only show console output
    # with_context=True,  # Enable turn history between players
    with_message_history=True,  # Enable conversation memory for each player
    pay4partner=False,  # Enable 'pay for partner' mode
)


# set LOGGER = GameLogger() to enable logging to a file, or None to disable logging
LOGGER = GameLogger(filepath="logs/game_log.jsonl")

if __name__ == "__main__":
    Game(config=CONFIG, logger=LOGGER).run()