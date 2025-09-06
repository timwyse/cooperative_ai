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


class CombinedGameLogger(BaseLogger):
    """Combined logger that handles both structured JSON events and verbose text logging."""
    def __init__(self, game_id=None, base_log_dir: str = "logs"):
        if game_id is None:
            self.game_id = self._generate_unique_game_id()
        else:
            self.game_id = game_id
        
        # Create logs/{timestamp}/
        self.log_dir = Path(base_log_dir) / self.game_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        

        self.event_filepath = self.log_dir / f"event_log_{self.game_id}.json"
        self.verbose_filepath = self.log_dir / f"verbose_log_{self.game_id}.txt"
        
        # Init event log 
        self.log_data = {
            "config": {},
            "game": {
                "id": f"game_event_log_{self.game_id}",
                "start_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "end_timestamp": None,
                "turns": {}
            }
        }
        
        # Init verbose log 
        with open(self.verbose_filepath, "w") as f:
            f.write(f"VERBOSE GAME LOG - {self.game_id}\n")
            f.write("=" * 80 + "\n")
            f.write(f"Started: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n")
            f.write("=" * 80 + "\n\n")
    
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
            "players": player_policies,
            "manual_resources": manual_resources,
            "with_message_history": getattr(config, 'with_message_history', True),
            "pay4partner": getattr(config, 'pay4partner', False),
            "with_context": getattr(config, 'with_context', True),
            "resource_mode": getattr(config, 'resource_mode', 'single_type_each'),
            "grid_size": getattr(config, 'grid_size', 4),
            "colors": getattr(config, 'colors', []),
            "mode": "Pay4Partner" if getattr(config, 'pay4partner', False) else "Standard Trading",
            "player_details": player_details
        }
    
    def log_turn_start(self, turn_number):

        self.log_data["game"]["turns"][str(turn_number)] = {
            "players": {}
        }
        
        with open(self.verbose_filepath, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"TURN {turn_number}\n")
            f.write(f"{'='*80}\n\n")
    
    def log_player_prompt(self, turn_number, player_name, player_model, decision_type, full_prompt):
        """Log the complete prompt sent to a player (verbose only)."""
        with open(self.verbose_filepath, "a") as f:
            f.write(f"[TURN {turn_number}] {player_name} ({player_model}) - {decision_type.upper()}\n")
            f.write(f"{'-'*80}\n")
            f.write("PROMPT:\n")
            f.write(f"{full_prompt}\n")
            f.write(f"{'-'*80}\n\n")
    
    def log_player_response(self, turn_number, player_name, player_model, decision_type, response):
        """Log the complete response from a player (verbose only)."""
        with open(self.verbose_filepath, "a") as f:
            f.write(f"[TURN {turn_number}] {player_name} ({player_model}) - {decision_type.upper()} RESPONSE\n")
            f.write(f"{'-'*80}\n")
            f.write("RESPONSE:\n")
            f.write(f"{response}\n")
            f.write(f"{'-'*80}\n\n")
    
    def log_player_turn_summary(self, turn_number, player_name, player_data):
        """Log a player's turn data in JSON format (event log only)."""
        # Extract player ID from name (e.g., "Player 0" -> "0")
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        
        trade_data = None
        trade_proposed = player_data.get('trade_proposed')
        if trade_proposed and trade_proposed.get('resources_to_offer'):
            trade_data = {
                "offer": trade_proposed.get('resources_to_offer', []),
                "request": trade_proposed.get('resources_to_receive', []),
                "outcome": player_data.get('trade_proposal_outcome', 'none')
            }
        
        player_turn_data = {
            "from": list(player_data.get('position_start', [0, 0])),
            "to": list(player_data.get('position_end', [0, 0])),
            "trade": trade_data,
            "resources_start": player_data.get('resources_start', {}),
            "resources_end": player_data.get('resources_end', {})
        }
        
        self.log_data["game"]["turns"][str(turn_number)]["players"][player_id] = player_turn_data
    
    def log_turn_end(self, turn_number):

        self._save_event_log()
        
        with open(self.verbose_filepath, "a") as f:
            f.write(f"END OF TURN {turn_number}\n")
            f.write(f"{'='*80}\n\n")
    
    def log_game_end(self, players, total_turns):

        self.log_data["game"]["end_timestamp"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
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
        
        self._save_event_log()
    
    def _save_event_log(self):
        with open(self.event_filepath, "w") as f:
            json.dump(self.log_data, f, indent=2, ensure_ascii=False)



def preprocess_details(details):
    """Preprocess details for logging, converting non-serializable objects."""
    def serialize(obj):
        if isinstance(obj, str):
            return obj
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)  # Fallback to string representation for non-serializable objects

    return {key: serialize(value) for key, value in details.items()}
