from datetime import datetime, timezone
import json

from pathlib import Path

from constants import POINTS_FOR_WIN, POINTS_FOR_EXTRA_RESOURCE
from utils import calculate_scores

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
        """Log system events (errors, validations, etc.) to the verbose log."""
        turn = str(self.turn) if hasattr(self, 'turn') else '0'
        
        # Initialize events section if not exists
        if "events" not in self.verbose_log_data["game"]["turns"][turn]:
            self.verbose_log_data["game"]["turns"][turn]["events"] = {}
        
        # Add event with timestamp
        self.verbose_log_data["game"]["turns"][turn]["events"][event] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            **details
        }
        
        self._save_verbose_log()
            
    def __init__(self, game_id=None, base_log_dir: str = "logs", skip_default_logs=False):
        if game_id is None:
            self.game_id = self._generate_unique_game_id()
        else:
            self.game_id = game_id
        
        # When running experiments, use base_log_dir directly
        if skip_default_logs:
            self.log_dir = Path(base_log_dir)
        else:
            # Create logs/{timestamp}/
            self.log_dir = Path(base_log_dir) / self.game_id
            
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.event_filepath = self.log_dir / f"event_log_{self.game_id}.json"
        self.verbose_filepath = self.log_dir / f"verbose_log_{self.game_id}.json"
        
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
        
        # Init verbose log with clean structure
        self.verbose_log_data = {
            "game": {
                "id": self.game_id,
                "start_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "end_timestamp": None,
                "turns": {}
            }
        }
        
        # Write initial logs
        self._save_event_log()  # Write initial event log
        self._save_verbose_log()  # Write initial verbose log
    
    def _generate_unique_game_id(self):
        """Game id based on timestamp."""
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    def log_game_config(self, config, players, grid):
        """Log initial game configuration for metrics calculation."""

        player_models = [player.model_name for player in players]
        
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
                "initial_resources": dict(player.resources),
                "non_cooperative_baseline": player.non_cooperative_baseline
            })
        
        self.log_data["config"] = {
            "player_models": player_models,
            "manual_resources": manual_resources,
            "with_message_history": getattr(config, 'with_message_history', True),
            "pay4partner": getattr(config, 'pay4partner', False),
            "contract_type": getattr(config, 'contract_type', None),
            "with_context": getattr(config, 'with_context', True),
            "fog_of_war": getattr(config, 'fog_of_war', [False, False]),  # Add fog_of_war to logged config
            "resource_mode": getattr(config, 'resource_mode', 'single_type_each'),
            "grid_size": getattr(config, 'grid_size', 4),
            "colors": getattr(config, 'colors', []),
            "mode": "Pay4Partner" if getattr(config, 'pay4partner', False) else "Standard Trading",
            "player_details": player_details
        }
    
    def log_turn_start(self, turn_number):
        """Start a new turn in both event and verbose logs."""
        # Initialize turn in event log
        self.log_data["game"]["turns"][str(turn_number)] = {
            "players": {}
        }
        
        # Initialize turn in verbose log
        self.verbose_log_data["game"]["turns"][str(turn_number)] = {}
        self._save_verbose_log()
    
    def log_player_prompt(self, turn_number, player_name, player_model, decision_type, system_prompt, user_prompt):
        """Log the complete prompt sent to a player (verbose only)."""
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        turn = str(turn_number)
        
        # Initialize player data if not exists
        if f"player_{player_id}" not in self.verbose_log_data["game"]["turns"][turn]:
            self.verbose_log_data["game"]["turns"][turn][f"player_{player_id}"] = {}
        
        # Add action entry
        action_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "action": decision_type.upper(),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "agent_response": None  # Will be filled by log_player_response
        }
        
        # Add the action entry
        action_key = decision_type.lower()
        self.verbose_log_data["game"]["turns"][turn][f"player_{player_id}"][action_key] = action_data
        self._save_verbose_log()
    
    def log_player_response(self, turn_number, player_name, player_model, decision_type, response):
        """Log the complete response from a player (verbose only)."""
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        turn = str(turn_number)
        
        # Update the existing action entry with the response
        if f"player_{player_id}" in self.verbose_log_data["game"]["turns"][turn]:
            # Get the action entry key from the data
            action_key = decision_type.lower()
            if action_key in self.verbose_log_data["game"]["turns"][turn][f"player_{player_id}"]:
                self.verbose_log_data["game"]["turns"][turn][f"player_{player_id}"][action_key]["agent_response"] = response
                self._save_verbose_log()
    
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
        
        # Add pay4partner actions if any
        if player_data.get('broke_promise_for'):
            # This player broke their promise to someone else
            player_turn_data["pay4partner"] = {
                "action": "broke_promise",
                "promised_color": player_data.get('promised_color'),
                "broke_promise_for": player_data.get('broke_promise_for')
            }
        elif player_data.get('move_type') == 'pay4partner':
            player_turn_data["pay4partner"] = {
                "action": "promise_fulfilled",
                "covered_color": player_data.get('covered_color'),
                "covered_by": player_data.get('covered_by')
            }
        
        # Add move data if exists
        if player_data.get('move_made') is not None:
            move_info = {
                "move_made": list(player_data['move_made']),
                "move_type": player_data.get('move_type', 'regular')
            }
            # Add coverage info for pay4partner moves
            if player_data.get('move_type') == 'pay4partner':
                move_info.update({
                    "covered_by": player_data.get('covered_by'),
                    "covered_color": player_data.get('covered_color')
                })
            player_turn_data.update(move_info)
        
        # Add trade/arrangement data if exists
        trade_proposed = player_data.get('trade_proposed')
        if trade_proposed and trade_proposed.get('resources_to_offer'):
            if player_data.get('is_pay4partner', False):
                # Pay4partner arrangement
                player_turn_data["arrangement"] = {
                    "promised_to_cover": trade_proposed.get('resources_to_offer', []),
                    "requested_coverage": trade_proposed.get('resources_to_receive', []),
                    "outcome": player_data.get('trade_proposal_outcome', 'none')
                }
            else:
                # Regular trade
                player_turn_data["trade"] = {
                    "offer": trade_proposed.get('resources_to_offer', []),
                    "request": trade_proposed.get('resources_to_receive', []),
                    "outcome": player_data.get('trade_proposal_outcome', 'none')
                }
        
        # Add to turn data
        self.log_data["game"]["turns"][str(turn_number)]["players"][player_id] = player_turn_data
    
    def log_turn_end(self, turn_number):
        """End the current turn in both event and verbose logs."""
        # Save both logs
        self._save_event_log()
        self._save_verbose_log()
    
    def _save_verbose_log(self):
        """Save the verbose log to file."""
        with open(self.verbose_filepath, "w") as f:
            json.dump(self.verbose_log_data, f, indent=2, ensure_ascii=False)
    
    def log_game_end(self, players, total_turns):
        """Log final game state and metrics."""
        # Set end timestamp for both logs
        end_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        self.log_data["game"]["end_timestamp"] = end_time
        self.verbose_log_data["game"]["end_timestamp"] = end_time

        # TODO: move metrics related code to a separate file
        # Calculate scores and metrics
        scores = calculate_scores(players)
        total_scores = sum(scores.values())
        max_score = sum(max_possible_score(p) for p in players)
        total_accuracy = total_scores / max_score if max_score > 0 else 0
        
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
                "max_possible_score": max_score
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

    def log_contract_negotiation(self, turn_number, history_0,
                history_1,
                agree_0,
                agree_1,    
                judge_contract,
                agreement_status):
        """
        Log the conversation between players and the outcome of the contract negotiation.
        
        """
        turn = str(turn_number)

        # Initialize turn in verbose log if not already present
        if turn not in self.verbose_log_data["game"]["turns"]:
            self.verbose_log_data["game"]["turns"][turn] = {}
        # Log the negotiation details
        self.verbose_log_data["game"]["turns"][turn]["contract_negotiation"] = {
                
                    "conversation_history_0": history_0,
                    "conversation_history_1": history_1,
                    "agreement_from_player_0": agree_0,
                    "agreement_from_player_1": agree_1,
            "judge_contract": judge_contract,
            "agreement_status": agreement_status
        }

        # Save the verbose log
        self._save_verbose_log()

def preprocess_details(details):
    """Preprocess details for logging, converting non-serializable objects."""
    def serialize(obj):
        if isinstance(obj, str):
            return obj
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)  # Fallback to string representation for non-serializable objects

    return {key: serialize(value) for key, value in details.items()}


def max_possible_score(player):
    """
    Calculate the maximum possible score for a player based on their starting resources and grid size.
    """
    starting_resources = sum(player.starting_resources.values())
    min_steps = abs(player.goal[0] - player.start[0]) + abs(player.goal[1] - player.start[1])
    max_possible_score = POINTS_FOR_WIN + (POINTS_FOR_EXTRA_RESOURCE * (starting_resources - min_steps)) if starting_resources >= min_steps else 0
    
    return max_possible_score