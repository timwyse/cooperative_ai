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


class Logger(BaseLogger):
    """Combined logger that handles both structured JSON events and verbose text logging."""
    
    def log(self, event: str, details: dict):
       
        # Only log to verbose log, keep event log clean
        with open(self.verbose_filepath, "a") as f:
            f.write(f"EVENT: {event}\n")
            f.write(f"DETAILS: {json.dumps(details, indent=2)}\n")
            f.write("-" * 80 + "\n\n")
            
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
        
        # Init event log with clean structure
        self.log_data = {
            "config": {},  # Will be populated by log_game_config
            "game": {
                "id": self.game_id,
                "start_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "end_timestamp": None,
                "turns": {}  # Will be populated by log_player_turn_summary
            },
            "final_state": None  # Will be populated by log_game_end
        }
        
        # Init verbose log 
        with open(self.verbose_filepath, "w") as f:
            f.write(f"VERBOSE GAME LOG - {self.game_id}\n") 
            f.write("=" * 80 + "\n")
            f.write(f"Started: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n")
            f.write("=" * 80 + "\n\n")
    
    def _generate_unique_game_id(self):
        """Game id based on timestamp."""
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    def log_game_config(self, config, players, grid):
        """Log initial game configuration for metrics calculation."""

        player_policies = [player.model_name for player in players]
        
        manual_resources = []
        for player in players:
            manual_resources.append(dict(player.resources))
        
        player_details = []
        for i, player in enumerate(players):
            player_details.append({
                "id": i,
                "model": player.model_name,
                "start": list(player.position),
                "goal": list(player.goal),
                "initial_resources": dict(player.resources)
            })
        
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
        """Start a new turn in both event and verbose logs."""

        self.log_data["game"]["turns"][str(turn_number)] = {
            "players": {}
        }
        
        # Write turn header to verbose log
        with open(self.verbose_filepath, "a") as f:
            f.write("\n")
            f.write("="*80 + "\n")
            f.write(f"TURN {turn_number}\n")
            f.write("="*80 + "\n")
    
    def log_player_prompt(self, turn_number, player_name, player_model, decision_type, full_prompt):
        """Log the complete prompt sent to a player (verbose only)."""
        with open(self.verbose_filepath, "a") as f:
            f.write("\n")  # Add spacing between events
            f.write(f"PLAYER {player_name} ({player_model}) - {decision_type.upper()}\n")
            f.write("-"*80 + "\n")
            f.write("SYSTEM AND USER PROMPTS:\n")
            f.write(f"{full_prompt}\n")
    
    def log_player_response(self, turn_number, player_name, player_model, decision_type, response):
        """Log the complete response from a player (verbose only)."""
        with open(self.verbose_filepath, "a") as f:
            f.write("\nAI RESPONSE:\n")
            f.write("-"*80 + "\n")
            f.write(f"{response}\n")
            f.write("-"*80 + "\n")
    
    def log_player_turn_summary(self, turn_number, player_name, player_data):
        """Log a player's turn data in JSON format (event log only)."""
        # Extract player ID from name (e.g., "Player 0" -> "0")
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        
        # Initialize turn if not exists
        if str(turn_number) not in self.log_data["game"]["turns"]:
            self.log_data["game"]["turns"][str(turn_number)] = {
                "players": {}
            }
        
        # Build clean player turn data
        player_turn_data = {
            "position": {
                "start": list(player_data.get('position_start')) if player_data.get('position_start') is not None else [0, 0],
                "end": list(player_data.get('position_end')) if player_data.get('position_end') is not None else [0, 0]
            },
            "resources": {
                "start": player_data.get('resources_start', {}),
                "end": player_data.get('resources_end', {})
            }
        }
        
        # Add trade data if exists
        trade_proposed = player_data.get('trade_proposed')
        if trade_proposed and trade_proposed.get('resources_to_offer'):
            player_turn_data["trade"] = {
                "offer": trade_proposed.get('resources_to_offer', []),
                "request": trade_proposed.get('resources_to_receive', []),
                "outcome": player_data.get('trade_proposal_outcome', 'none')
            }
        
        # Add to turn data
        self.log_data["game"]["turns"][str(turn_number)]["players"][player_id] = player_turn_data
    
    def log_turn_end(self, turn_number):
        """End the current turn in both event and verbose logs."""
        # Save event log state
        self._save_event_log()
        
        # Write turn footer to verbose log
        with open(self.verbose_filepath, "a") as f:
            f.write("\n")
            f.write("="*80 + "\n")
            f.write(f"END OF TURN {turn_number}\n")
            f.write("="*80 + "\n")
    
    def log_game_end(self, players, total_turns):
        """Log final game state and metrics."""
        # Set end timestamp
        self.log_data["game"]["end_timestamp"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # TODO: move metrics related code to a separate file
        # Calculate scores and metrics
        scores = {str(i): (100 + 5 * sum(dict(p.resources).values())) if p.has_finished() else 0 
                 for i, p in enumerate(players)}
        total_scores = sum(scores.values())
        max_possible_score = 100 * len(players) + (5 * sum(sum(dict(p.resources).values()) for p in players))
        total_accuracy = total_scores / max_possible_score if max_possible_score > 0 else 0
        
        # Calculate Gini
        scores_list = list(scores.values())
        scores_list.sort()
        n = len(scores_list)
        cumulative_sum = sum((i + 1) * score for i, score in enumerate(scores_list))
        total_sum = sum(scores_list)
        gini = (2 * cumulative_sum) / (n * total_sum) - (n + 1) / n if total_sum > 0 else 0
        
        # Add final state section with metrics
        self.log_data["game"]["final_state"] = {
            "players": {},
            "total_turns": total_turns,
            "scores": scores,
            "metrics": {
                "total_scores": total_scores,
                "total_accuracy": total_accuracy,
                "gini_coefficient": gini,
                "max_possible_score": max_possible_score
            }
        }
        
        # Add player states
        for i, player in enumerate(players):
            self.log_data["game"]["final_state"]["players"][str(i)] = {
                "position": list(player.position),
                "goal": list(player.goal),
                "reached_goal": player.has_finished(),
                "resources": dict(player.resources)
            }
        
        # Save final JSON
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
