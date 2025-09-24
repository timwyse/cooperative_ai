from dataclasses import replace

from agents import *
from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import Logger
import prompts as p


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    load_config("my_configs/single_board_3x3_md11.yaml"), # can use DEFAULT_CONFIG or load a specific configs here eg load_config("configs/simple_prisoners_dilemma.yaml"),
#    players=[SONNET_4, SONNET_4],
#     grid_size=6,
# #     colors=['R', 'B', 'G', 'Y', 'PK'],
# #     resource_mode='manual',
#     grid= [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'R', 'B', 'R', 'B', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']],
    # manual_resources = [{'R':0, 'B': 10}, {'R':10, 'B': 0}],

    wait_for_enter=False,
    display_gui=True,  # Disable Pygame window, only show console output
    with_context=True,  # Enable turn history between players
    with_message_history=False,  # Enable conversation memory for each player
    # pay4partner=True,  # Enable 'pay for partner' mode
    contract_type='contract_for_finishing',  # Enable contract negotiation contract_for_finishing, strict, tile_with_judge_implementation
    # system_prompt=p.SELFISH_SYSTEM_PROMPT,
    # fog_of_war=[True, True],  # Enable fog of war for both players
)


if __name__ == "__main__":
    Game(config=CONFIG).run()