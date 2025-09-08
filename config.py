from __future__ import annotations  

import json
import yaml
from dataclasses import dataclass, field, replace
from typing import List, Optional, TYPE_CHECKING
from pathlib import Path

from constants import AVAILABLE_COLORS
from prompts import DEFAULT_SYSTEM_PROMPT


@dataclass
class GameConfig:
    """
    Stores configuration settings shared between the Game and Player classes
    and defines default parameters for the game.
    """

    # PLAYER CONFIGURATION
    players: Optional[List[str]] = None  # list of Agent namedtuples (see agents.py)
    pay4partner: bool = False # if True, rather than direct trading, players pay their partner to move onto tiles of their color

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
    manual_start_positions: Optional[List[tuple]] = None  # list of (row, col) tuples for each player's start position; if None, random positions are generated within random_start_block_size. Must be of length equal to number of players.
    manual_goal_positions: Optional[List[tuple]] = None   # list of (row, col) tuples for each player's goal position; if None, random positions are generated within random_goal_block_size. Must be of length equal to number of players.

    # LLM PARAMETERS
    temperature: float = 1.0
    with_context: bool = True  # turn history between players (goes with system role prompt)
    with_message_history: bool = True  # conversation history for each player (goes with assistant role prompt)
    system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT  # custom system prompt to override DEFAULT_SYSTEM_PROMPT

    
    # DISPLAY PARAMETERS
    display_gui: bool = False  # if False, only show console output (no Pygame window)
    wait_for_enter: bool = True  # if True, wait for Enter key between turns

    def __post_init__(self):
        import agents as a 
        if self.players is None:
            self.players = [a.HUMAN, a.HUMAN]
        else:
            self.players = [
            getattr(a, player) if isinstance(player, str) and hasattr(a, player) else player
            for player in self.players
        ]
        if not self.colors:
            self.colors = AVAILABLE_COLORS[:len(self.players)]
        if self.resource_mode != 'manual' and self.manual_resources:
            print("Warning: manual_resources is set but resource_mode is not 'manual'. Ignoring manual_resources.")
        

# Base configuration used by Game unless overridden in main.py
DEFAULT_CONFIG = GameConfig()


def load_config(filename: str) -> GameConfig:
    """
    Load a configuration from a JSON or YAML file and return a GameConfig instance.
    Any fields not set in the loaded configuration will default to the values in DEFAULT_CONFIG.
    """
    filepath = Path(filename)
    if not filepath.exists():
        raise FileNotFoundError(f"Configuration file '{filename}' not found.")

    with open(filepath, "r") as f:
        if filepath.suffix == ".json":
            config_dict = json.load(f)
        elif filepath.suffix in [".yaml", ".yml"]:
            config_dict = yaml.safe_load(f)
        else:
            raise ValueError("Unsupported file format. Use .json or .yaml/.yml.")
    # Convert manual_start_positions and manual_goal_positions to tuples
    if "manual_start_positions" in config_dict:
        config_dict["manual_start_positions"] = [
            tuple(pos) for pos in config_dict["manual_start_positions"]
        ]
    if "manual_goal_positions" in config_dict:
        config_dict["manual_goal_positions"] = [
            tuple(pos) for pos in config_dict["manual_goal_positions"]
        ]
    # Merge loaded config with DEFAULT_CONFIG
    return replace(DEFAULT_CONFIG, **config_dict)