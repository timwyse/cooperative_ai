from dataclasses import replace
from game import Game
from config import DEFAULT_CONFIG, GameConfig
from player import NANO, MINI, FOUR_1, FOUR_0, HUMAN, LLAMA_3_3B



# refer to config.py to see which arguments are available for the game and what their defaults are
# can replace any of the default values in DEFAULT_CONFIG with your own values
CONFIG = replace(
    DEFAULT_CONFIG,
    players=[HUMAN, LLAMA_3_3B, FOUR_1],
    grid_size=3,
    colors=['R', 'G', 'B'],
    # grid=[['R', 'R'], ['G', 'R']]
)

if __name__ == "__main__":
    Game(config=CONFIG).run()