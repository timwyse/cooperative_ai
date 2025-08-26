from __future__ import annotations  
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from constants import AVAILABLE_COLORS


@dataclass
class GameConfig:
    """
    Stores configuration settings shared between the Game and Player classes
    and defines default parameters for the game.
    """

    # PLAYER CONFIGURATION
    players: Optional[List[str]] = None  # list of Agent namedtuples (see player.py)

    # RESOURCE SETTINGS
    surplus: float = 1.5 # Multiplier of the minimum steps required to complete the game. Used to determine how many resources each player starts with.
    resource_mode: str = 'single_type_each'
    # Options:
    #   - 'single_type_each': each player has only one resource type, each player gets num_resources = surplus * 2 * (grid_size - 1)
    #   - 'random': random distribution, each player gets num_resources = surplus * 2 * (grid_size - 1)
    #   - 'manual': use manual_resources field
    manual_resources: Optional[List[dict]] = None # Manually set the starting resources of the players. Order is the same as the players variable. resource_mode must be 'manual'.
    # eg. [{'R':2, 'B':2}, {'R':2, 'B':2}]

    # GRID SETTINGS
    grid_size: int = 3  # grid is square, size grid_size x grid_size
    colors: List[str] = field(default_factory=list)  # list of colors from constants.AVAILABLE_COLORS
    grid: Optional[List[List[str]]] = None  # explicit grid (list of lists of colors); if None, a random one is generated with equal distribution of colors from colors
    random_start_block_size: int = 1  # top-left block within which start positions are generated
    random_goal_block_size: int = 1   # bottom-right block within which goals are generated

    # LLM PARAMETERS
    temperature: float = 1.0
    with_context: bool = True  # turn history between players (goes with system role prompt)
    with_message_history: bool = True  # conversation history for each player (goes with assistant role prompt)

    def __post_init__(self):
        if self.players is None:
            from player import HUMAN
            self.players = [HUMAN, HUMAN]
        if not self.colors:
            self.colors = AVAILABLE_COLORS[:len(self.players)]
        if self.resource_mode != 'manual' and self.manual_resources:
            print("Warning: manual_resources is set but resource_mode is not 'manual'. Ignoring manual_resources.")
        

# Base configuration used by Game unless overridden in main.py
DEFAULT_CONFIG = GameConfig()