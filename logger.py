from datetime import datetime, timezone
import json

from pathlib import Path

class BaseLogger:
    def log(self, event: str, details: dict):
        raise NotImplementedError


class NullLogger(BaseLogger):
    """A logger that ignores all messages (default)."""
    def log(self, event: str, details: dict):
        pass


class GameLogger(BaseLogger):
    """Logs game events to a JSONL file."""
    def __init__(self, game_id=None, filepath: str = "game_log.jsonl"):
        self.filepath = Path(filepath)
        self.log_dir = self.filepath.parent
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if game_id is None:
            self.game_id = self._generate_unique_game_id()
    
    def _generate_unique_game_id(self):
        """
        Generate a unique game id based on timestamp and existing files.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        base_id = timestamp
        existing_ids = {f.stem for f in self.log_dir.glob("*.jsonl")}
        counter = 1
        unique_id = base_id
        while unique_id in existing_ids:
            counter += 1
            unique_id = f"{base_id}_{counter}"
        return unique_id

    def log(self, event: str, details: dict):
        log_entry = {
            "game_id": self.game_id,
            "timestamp": datetime.now(timezone.utc).isoformat(), 
            "event": event,
            "details": preprocess_details(details),
        }
        with open(self.filepath, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")  # keep Unicode


class EventLogger(BaseLogger):
    """Logs structured game events and outcomes in JSON format."""
    def __init__(self, game_id=None, log_dir: str = "logs/event_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        if game_id is None:
            self.game_id = self._generate_unique_game_id()
        else:
            self.game_id = game_id
            
        self.filepath = self.log_dir / f"event_log_{self.game_id}.json"
        
        # Initialize the log structure
        self.log_data = {
            "config": {},
            "game": {
                "id": f"game_event_log_{self.game_id}",
                "start_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "end_timestamp": None,
                "turns": {}
            }
        }
    
    def _generate_unique_game_id(self):
        """Generate a unique game id based on timestamp."""
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    def log_game_config(self, config, players, grid):
        """Log initial game configuration for metrics calculation."""
        # Extract player models/policies
        player_policies = [player.model_name for player in players]
        
        # Build manual resources list
        manual_resources = []
        for player in players:
            manual_resources.append(dict(player.resources))
        
        # Build player details
        player_details = []
        for i, player in enumerate(players):
            player_details.append({
                "id": i,
                "policy": player.model_name,
                "start": list(player.position),
                "goal": list(player.goal),
                "initial_resources": dict(player.resources)
            })
        
        # Update config section
        self.log_data["config"] = {
            "loaded_from": "runtime_config",  # Could be enhanced to track actual config file
            "players": player_policies,
            "manual_resources": manual_resources,
            "with_message_history": getattr(config, 'with_message_history', True),
            "pay4partner": getattr(config, 'pay4partner', False),
            "with_context": getattr(config, 'with_context', True),
            "display_gui": getattr(config, 'display_gui', False),
            "wait_for_enter": getattr(config, 'wait_for_enter', False),
            "resource_mode": "manual",  # Could be enhanced to track actual mode
            "grid_size": getattr(config, 'grid_size', 4),
            "colors": getattr(config, 'colors', []),
            "mode": "Pay4Partner" if getattr(config, 'pay4partner', False) else "Standard Trading",
            "player_details": player_details
        }
    
    def log_turn_start(self, turn_number):
        """Initialize a new turn in the log structure."""
        self.log_data["game"]["turns"][str(turn_number)] = {
            "players": {}
        }
    
    def log_player_turn_summary(self, turn_number, player_name, player_data):
        """Log a player's turn data in JSON format."""
        # Extract player ID from name (e.g., "Player 0" -> "0")
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        
        # Build trade data
        trade_data = None
        trade_proposed = player_data.get('trade_proposed')
        if trade_proposed and trade_proposed.get('resources_to_offer'):
            trade_data = {
                "offer": trade_proposed.get('resources_to_offer', []),
                "request": trade_proposed.get('resources_to_receive', []),
                "outcome": player_data.get('trade_proposal_outcome', 'none')
            }
        
        # Build player turn data
        player_turn_data = {
            "from": list(player_data.get('position_start', [0, 0])),
            "to": list(player_data.get('position_end', [0, 0])),
            "trade": trade_data,
            "resources_start": player_data.get('resources_start', {}),
            "resources_end": player_data.get('resources_end', {})
        }
        
        # Add to the log structure
        self.log_data["game"]["turns"][str(turn_number)]["players"][player_id] = player_turn_data
    
    def log_turn_end(self, turn_number):
        """Save the current state after turn ends."""
        self._save_to_file()
    
    def log_game_end(self, players, total_turns):
        """Log final game state and save the complete JSON."""
        # Set end timestamp
        self.log_data["game"]["end_timestamp"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Add final state section
        self.log_data["game"]["final_state"] = {
            "players": {},
            "total_turns": total_turns
        }
        
        for i, player in enumerate(players):
            self.log_data["game"]["final_state"]["players"][str(i)] = {
                "position": list(player.position),
                "goal": list(player.goal),
                "reached_goal": player.has_finished(),
                "resources": dict(player.resources)
            }
        
        # Save final JSON
        self._save_to_file()
    
    def _save_to_file(self):
        """Save the current log data to JSON file."""
        with open(self.filepath, "w") as f:
            json.dump(self.log_data, f, indent=2, ensure_ascii=False)
    
    def log(self, event: str, details: dict):
        """Generic log method for compatibility with BaseLogger interface."""
        # For now, just save the current state
        self._save_to_file()


def preprocess_details(details):
    """Preprocess details for logging, converting non-serializable objects."""
    def serialize(obj):
        if isinstance(obj, str):
            return obj
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)  # Fallback to string representation for non-serializable objects

    return {key: serialize(value) for key, value in details.items()}
