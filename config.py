from __future__ import annotations  
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from constants import COLOR_MAP

if TYPE_CHECKING:
    from player import Agent  

@dataclass
class GameConfig:
    """
    Stores configuration settings shared between the Game and Player classes.
    Acts as a central source of truth for game parameters.
    """
    players: List[Agent]  # Agent can be forward-referenced now
    surplus: float
    grid_size: int
    resource_mode: str = 'single_type_each'
    temperature: float = 1.0
    random_start_block_size: int = 1
    random_goal_block_size: int = 1
    colors: List[str] = field(default_factory=list)
    grid: Optional[List[List[str]]] = None

    def __post_init__(self):
            # Dynamically set colors based on the number of players if not provided
            if not self.colors:
                self.colors = [c for c in COLOR_MAP if c != 'BK'][:len(self.players)]