from game import Game, DEFAULT_PLAYERS, DEFAULT_TEMPERATURE, DEFAULT_SURPLUS, DEFAULT_GRID_SIZE
from config import GameConfig
from constants import COLOR_MAP
from player import NANO, MINI, FOUR_1, FOUR_0, HUMAN, LLAMA_3_3B


CONFIG = GameConfig(
    players=[HUMAN, LLAMA_3_3B, FOUR_1],
    surplus=DEFAULT_SURPLUS,
    grid_size=5,
    resource_mode='single_type_each',
    # temperature=DEFAULT_TEMPERATURE,
    # random_start_block_size=1,
    # random_goal_block_size=1,
    # colors=[c for c in COLOR_MAP if c != 'BK'][:3],
    # grid=None
)

if __name__ == "__main__":
    Game(config=CONFIG).run()
