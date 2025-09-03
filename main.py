from dataclasses import replace

from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import GameLogger
from agents import *


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    load_config("configs/mutual_trade_necessary.yaml"), # can use DEFAULT_CONFIG or load a specific configs here eg load_config("configs/simple_prisoners_dilemma.yaml"),
    players=[FOUR_1, FOUR_1],
#     grid_size=5,
#     colors=['R', 'B', 'G', 'Y', 'PK'],
#     resource_mode='manual',
#     grid=[['G', 'R', 'R', 'R', 'R'],
#           ['B', 'PK','PK','PK', 'R'],
#           ['B', 'PK','PK', 'PK', 'R'],
#           ['B', 'PK','PK', 'PK', 'B'],
#           ['B', 'B', 'B', 'R', 'G'],
#           ],
#     manual_resources = [{'G':20, 'B': 4}, {'G':20, 'R': 4}],
# #     manual_start_positions=[(0, 0), (0, 4)],
# #     manual_goal_positions=[(4, 4), (4, 0)],

    wait_for_enter=True,
    # display_gui=False,  # Disable Pygame window, only show console output
    # with_context=True,  # Enable turn history between players
    with_message_history=True,  # Enable conversation memory for each player
    pay4partner=True,  # Enable 'pay for partner' mode
)


# set LOGGER = GameLogger() to enable logging to a file, or None to disable logging
LOGGER = GameLogger(filepath="logs/game_log.jsonl")

if __name__ == "__main__":
    print(f"""
          ******

          Starting new Game with parameters: {CONFIG}

          ******
          """)
    Game(config=CONFIG, logger=LOGGER).run()