from __future__ import annotations  # must be first

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class GameConfig:
    """Store game configuration settings. What is shared between Game and Player."""
    players: List["Agent"]  # Agent can be forward-referenced now
    temperature: float
    surplus: float
    grid_size: int
    resource_mode: str = 'single_type_each'
    random_start_block_size: int = 1
    random_goal_block_size: int = 1
    colors: List[str] = field(default_factory=list)
    grid: Optional[List[List[str]]] = None

