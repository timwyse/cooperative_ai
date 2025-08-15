from __future__ import annotations  
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from constants import COLOR_MAP


@dataclass
class GameConfig:
    """
    Stores configuration settings shared between the Game and Player classes
    and sets the set the default parameters for the game. 
    """
    players: Optional[List[str]] = None
    surplus: float = 1.5 # this is a multiplier of the minimum number of steps required to complete the game.
    grid_size: int = 3
    resource_mode: str = 'single_type_each' # currently only 'single_type_each' is supported, where each player has a single type of resource
    temperature: float = 1.0
    random_start_block_size: int = 1 # this is the size of the top left corner within which the players start
    random_goal_block_size: int = 1 # this is the size of the bottom right corner within which the players' goals are located
    colors: List[str] = field(default_factory=list)
    grid: Optional[List[List[str]]] = None

    def __post_init__(self):
        if self.players is None:
            from player import HUMAN  
            self.players = [HUMAN, HUMAN]
        if not self.colors:
            self.colors = [
                c for c in COLOR_MAP if c != 'BK'
            ][:len(self.players)]
        
# Base configuration used by Game unless overridden in main.py
DEFAULT_CONFIG = GameConfig()