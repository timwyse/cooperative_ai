from dataclasses import replace
from datetime import datetime, timedelta

from agents import *
from config import DEFAULT_CONFIG, GameConfig, load_config
from game import Game
from logger import Logger
import prompts as p


# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    load_config("configs/4-4_md_id-21.yaml"), # can use DEFAULT_CONFIG or load a specific configs here eg load_config("configs/simple_prisoners_dilemma.yaml"),
   players=[FOUR_1, FOUR_1],
#     grid_size=6,
    #  colors=['R', 'B', 'G'],
# #     resource_mode='manual',
#     grid= [
# ['G', 'B', 'B', 'B'],
# ['B', 'B', 'R', 'R'],
# ['B', 'B', 'R', 'R'],
# ['R', 'R', 'R', 'G'],
#     ],
    manual_resources = [{'R':10, 'B': 0, 'G':2}, {'R':0, 'B': 10, 'G':2}],

    wait_for_enter=False,
    display_gui=True,  # Disable Pygame window, only show console output
    with_context=True,  # Enable turn history between players
    with_message_history=False,  # Enable conversation memory for each player
    # pay4partner=True,  # Enable 'pay for partner' mode
    # contract_type='tile_with_judge_implementation',  # Options: contract_for_finishing, strict, tile_with_judge_implementation
    system_prompts={'0': p.SELFISH_SYSTEM_PROMPT, '1': p.SELFISH_SYSTEM_PROMPT},  # Custom system prompts for each player
    # fog_of_war=[True, True],  # Enable fog of war for both players
    show_paths=True,  # Show best paths to goal for each player
    # allow_trades=False,  # Disable trading between players
)


if __name__ == "__main__":

    start_time = datetime.now()

    Game(config=CONFIG).run()

    end_time = datetime.now()
    total_time_seconds = (end_time - start_time).total_seconds()

    print("-" * 20)
    print(f"Game finished with p4p={CONFIG.pay4partner}, contract_type={CONFIG.contract_type}, players={[p.name for p in CONFIG.players]}")
    print(f"Total time: {total_time_seconds:.2f} seconds")