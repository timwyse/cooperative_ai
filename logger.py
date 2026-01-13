from datetime import datetime, timezone
import json
import copy
import prompts

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
        turn = str(self.turn)
        
        self.verbose_log_data["game"]["turns"].setdefault(turn, {})
        self.verbose_log_data["game"]["turns"][turn].setdefault("events", {})
        self.verbose_log_data["game"]["turns"][turn]["events"][event] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            **details
        }
        self._save_verbose_log()

        self.log_data["game"]["turns"].setdefault(turn, {"players": {}})
        self.log_data["game"]["turns"][turn].setdefault("events", {})
        self.log_data["game"]["turns"][turn]["events"][event] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            **details
        }
        self._save_event_log()
            
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
            "config": {},  # log_game_config
            "game": {
                "id": self.game_id,
                "start_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "end_timestamp": None,
                "turns": {}  # log_player_turn_summary
            }
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
        self._save_event_log()
        self._save_verbose_log()
        self.turn = 0
    
    def _generate_unique_game_id(self):
        """based on timestamp."""
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
                "initial_chips": dict(player.resources),
                "non_cooperative_baseline": player.non_cooperative_baseline
            })
        
        self.log_data["config"] = {
            "player_models": player_models,
            "manual_chips": manual_resources,
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
    
    def log_turn_start(self):
        """Start a new turn in both event and verbose logs."""
        turn = str(self.turn)
        # create buckets if missing
        self.log_data["game"]["turns"].setdefault(turn, {"players": {}})
        self.verbose_log_data["game"]["turns"].setdefault(turn, {})
        
        self._save_event_log()
        self._save_verbose_log()
    
    def log_player_prompt(self, player_name, decision_type, system_prompt, user_prompt):
        """Log the complete prompt sent to a player (verbose only)."""
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        turn = str(self.turn)

        # ensure turn bucket exists
        self.verbose_log_data["game"]["turns"].setdefault(turn, {})
        # ensure actions list exists
        actions = self.verbose_log_data["game"]["turns"][turn].setdefault("actions", [])

        # Add action entry
        action_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "player": player_name,
            "action_type": decision_type.upper(),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "agent_response": None  # will be filled by log_player_response
        }

        actions.append(action_data)
        self._save_verbose_log()

    
    def log_player_response(self, player_name, decision_type, response):
        """Log the complete response from a player (verbose only)."""
        turn = str(self.turn)

        # ensure turn bucket exists
        turn_bucket = self.verbose_log_data["game"]["turns"].setdefault(turn, {})
        actions = turn_bucket.setdefault("actions", [])

        # Find the action (prompt) that this response belongs to
        for action in actions:
            if (action["player"] == player_name and 
                action["action_type"] == decision_type.upper()):
                # For trade responses, store parsing error attempts to help with debugging
                if (decision_type.upper() == "TRADE_RESPONSE" and 
                    isinstance(response, dict) and 
                    response.get("parsed", {}).get("status") == "rejected" and
                    "Failed to" in response.get("parsed", {}).get("rationale", "")):
                    if "agent_responses" not in action:
                        action["agent_responses"] = []
                    action["agent_responses"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        "response": response
                    })
                # Set the response that will be shown in turn history
                action["agent_response"] = response
                break  # Found the right prompt, no need to check others

        self._save_verbose_log()

    
    def log_player_turn_summary(self, player_name, player_data):
        """Log a player's turn data in JSON format (event log only)."""
        # Extract player ID from name (e.g., "Player 0" -> "0")
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        turn = str(self.turn)
        
        # Initialize turn if not exists
        if turn not in self.log_data["game"]["turns"]:
            self.log_data["game"]["turns"][turn] = {
                "players": {}
            }
        
        # Build clean player turn data
        player_turn_data = {
            "position": {
                "start": list(player_data.get('position_start')) if player_data.get('position_start') is not None else [0, 0],
                "end": list(player_data.get('position_end')) if player_data.get('position_end') is not None else [0, 0]
            },
            "chips": {
                "start": player_data.get('chips_start', {}),
                "end": player_data.get('chips_end', {})
            }
        }
        # Log trades first
        trade_proposed = player_data.get('trade_proposed')
        if trade_proposed and isinstance(trade_proposed, dict) and trade_proposed.get('chips_to_offer'):
            if player_data.get('is_pay4partner', False):
                # Pay4partner arrangement
                player_turn_data["arrangement_proposed"] = {
                    "promised_to_cover": trade_proposed.get('chips_to_offer', []),
                    "requested_coverage": trade_proposed.get('chips_to_receive', []),
                    "outcome": player_data.get('trade_proposal_outcome', 'none')
                }
            else:
                # Regular trade
                player_turn_data["trade"] = {
                    "offer": trade_proposed.get('chips_to_offer', []),
                    "request": trade_proposed.get('chips_to_receive', []),
                    "outcome": player_data.get('trade_proposal_outcome', 'rejected')  # Default to rejected instead of none
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
        
        # Add to turn data
        players_bucket = self.log_data["game"]["turns"][turn]["players"]
        existing_entry = players_bucket.get(player_id, {})

        # keep any format_errors that were logged earlier in the turn
        if "format_errors" in existing_entry and "format_errors" not in player_turn_data:
            player_turn_data["format_errors"] = existing_entry["format_errors"]
        elif "format_errors" in existing_entry and "format_errors" in player_turn_data:
            # both exist (paranoia): concatenate
            if not isinstance(player_turn_data["format_errors"], list):
                player_turn_data["format_errors"] = [player_turn_data["format_errors"]]
            prev = existing_entry["format_errors"]
            if not isinstance(prev, list):
                prev = [prev]
            player_turn_data["format_errors"] = prev + player_turn_data["format_errors"]

        existing_entry.update(player_turn_data)
        players_bucket[player_id] = existing_entry
    
    def log_turn_end(self):
        """End the current turn in both event and verbose logs."""
        # Save both logs
        self._save_event_log()
        self._save_verbose_log()
    
    def _save_verbose_log(self):
        """Save the verbose log to file."""
        with open(self.verbose_filepath, "w") as f:
            json.dump(self.verbose_log_data, f, indent=2, ensure_ascii=False)
    
    def log_game_end(self, game, players, additional_metrics=None):
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
        judge_api_calls = game.judge.n_api_calls if hasattr(game, 'judge') else 0
        
        # Add final state section with metrics
        self.log_data["game"]["final_state"] = {
            "players": {},
            "total_turns": str(self.turn),
            "scores": scores,
            "metrics": {
                "total_scores": total_scores,
                "total_accuracy": total_accuracy,
                "gini_coefficient": gini,
                "max_possible_score": max_score
            },
            "api_calls": {
                "total": sum(p.n_api_calls for p in players) + judge_api_calls,
                "by_player": {f"player_{i}": p.n_api_calls for i, p in enumerate(players)
                              }, 
                "judge": judge_api_calls
            }
        }
        


        # Add additional metrics if provided
        if additional_metrics:
            self.log_data["game"]["final_state"]["metrics"].update(additional_metrics)
    
        # Add player states
        for i, player in enumerate(players):
            self.log_data["game"]["final_state"]["players"][str(i)] = {
                "position": list(player.position),
                "goal": list(player.goal),
                "reached_goal": player.has_finished(),
                "chips": dict(player.resources),
                "route": player.route
            }
        
        # Count format errors
        format_error_count = 0
        for turn_data in self.log_data["game"]["turns"].values():
            for player_data in turn_data.get("players", {}).values():
                format_error_count += len(player_data.get("format_errors", []))

        # Add to metrics
        self.log_data["game"]["final_state"]["metrics"]["format_errors_total"] = format_error_count


        # Count format errors (total + breakdowns)
        format_errors_total = 0
        format_errors_by_type = {}
        format_errors_by_player = {}
        format_errors_by_turn = {}

        for turn, turn_data in self.log_data["game"]["turns"].items():
            turn_counts = {}
            for player_id, player_data in turn_data.get("players", {}).items():
                errors = player_data.get("format_errors", [])
                for e in errors:
                    etype = e.get("type", "unknown")
                    format_errors_total += 1

                    # by type
                    format_errors_by_type[etype] = format_errors_by_type.get(etype, 0) + 1

                    # by player
                    if player_id not in format_errors_by_player:
                        format_errors_by_player[player_id] = {}
                    format_errors_by_player[player_id][etype] = (
                        format_errors_by_player[player_id].get(etype, 0) + 1
                    )

                    # by turn (aggregate per turn regardless of player)
                    turn_counts[etype] = turn_counts.get(etype, 0) + 1

            if turn_counts:
                format_errors_by_turn[turn] = turn_counts

        # Add to metrics (keep the old total and add new breakdowns)
        metrics = self.log_data["game"]["final_state"]["metrics"]
        metrics["format_errors_total"] = format_errors_total
        metrics["format_errors_by_type"] = dict(sorted(format_errors_by_type.items()))
        metrics["format_errors_by_player"] = {
            pid: dict(sorted(cts.items())) for pid, cts in format_errors_by_player.items()
        }
        metrics["format_errors_by_turn"] = {
            t: dict(sorted(cts.items())) for t, cts in format_errors_by_turn.items()
        }


        # Log final contract state if contract exists
        if hasattr(game, 'contract') and game.contract_type == 'strict' and game.contract is not None:
            self.log_final_contract_state(game.contract)
        
        # Save final JSON
        self._save_event_log()
        self._save_verbose_log()
    
    def _save_event_log(self):
        with open(self.event_filepath, "w") as f:
            json.dump(self.log_data, f, indent=2, ensure_ascii=False)

    def log_contract_negotiation(self, 
                                 contract_type,
                                 judge_contract,
                                 history_0,
                                 history_1,
                                 agree_0,
                                 agree_1,
                                 agreement_status):
        """
        Log the conversation between players and the outcome of the contract negotiation.
        
        """

        turn = str(self.turn)

        # Initialize turn in verbose log if not already present
        if turn not in self.verbose_log_data["game"]["turns"]:
            self.verbose_log_data["game"]["turns"][turn] = {}
        # Log the negotiation details with deep copy to preserve initial state
        self.verbose_log_data["game"]["turns"][turn]["contract_negotiation"] = {
                    "judge_contract": copy.deepcopy(judge_contract),
                    "agreement_status": agreement_status,
                    "conversation_history_0": history_0,
                    "conversation_history_1": history_1,
                    "agreement_from_player_0": agree_0,
                    "agreement_from_player_1": agree_1,
            
        }

        # Save the verbose log
        self._save_verbose_log()
        
        # Also log contract to event log (simplified version without conversation history)
        if turn not in self.log_data["game"]["turns"]:
            self.log_data["game"]["turns"][turn] = {"players": {}}
        
        if contract_type == 'tile_with_judge_implementation':
            self.log_data["game"]["turns"][turn]["contract"] = {
                "judge_contract": copy.deepcopy(judge_contract),
                "agreement_status": agreement_status,
                "player_0_agreed": True,
                "player_1_agreed": True,
            }
        else:
            self.log_data["game"]["turns"][turn]["contract"] = {
                "judge_contract": copy.deepcopy(judge_contract),
                "agreement_status": agreement_status,
                "player_0_agreed": agree_0.get("parsed", {}).get("status") if agree_0 else None,
                "player_1_agreed": agree_1.get("parsed", {}).get("status") if agree_1 else None,
            }
        
        # Save the event log
        self._save_event_log()
    
    def log_final_contract_state(self, contract):
        """
        Log the final state of the contract at game end, showing which tiles were used.
        This is stored separately from the initial contract logged in turn 0.
        """
        # Add to verbose log
        if "final_contract_state" not in self.verbose_log_data["game"]:
            self.verbose_log_data["game"]["final_contract_state"] = {}
        
        self.verbose_log_data["game"]["final_contract_state"] = {
            "contract": copy.deepcopy(contract),
            "summary": {
                "total_tiles": len(contract),
                "tiles_used": sum(1 for tile in contract.values() if tile.get("status") == "used"),
                "tiles_unused": sum(1 for tile in contract.values() if tile.get("status") == "unused")
            }
        }
        
        # Add to event log
        if "final_contract_state" not in self.log_data["game"]:
            self.log_data["game"]["final_contract_state"] = {}
        
        self.log_data["game"]["final_contract_state"] = {
            "contract": copy.deepcopy(contract),
            "summary": {
                "total_tiles": len(contract),
                "tiles_used": sum(1 for tile in contract.values() if tile.get("status") == "used"),
                "tiles_unused": sum(1 for tile in contract.values() if tile.get("status") == "unused")
            }
        }

    def log_contract_system_prompt(self, player_id, contract_type, system_prompt):
        """Log system prompts used for contract negotiation"""
        
        #FIXME AS: It has to be implemented
        #below commented code proposed by Clode 
        #I'm not testing contracts yet
        #So I'm leaving it as a place holder for future. 
        """
        turn = str(self.turn)
        
        # Initialize turns if not exists (following existing pattern)
        if turn not in self.verbose_log_data["game"]["turns"]:
            self.verbose_log_data["game"]["turns"][turn] = {}
        
        # Initialize contract prompts section if not exists
        if "contract_prompts" not in self.verbose_log_data["game"]["turns"][turn]:
            self.verbose_log_data["game"]["turns"][turn]["contract_prompts"] = {}
        
        self.verbose_log_data["game"]["turns"][turn]["contract_prompts"][f"player_{player_id}"] = {
            "contract_type": contract_type,
            "system_prompt": system_prompt,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        self._save_verbose_log() """

    def log_judge_prompt(self, judge_action, system_prompt, user_prompt):
        """Log prompts sent to the judge"""

        #FIXME It has to be implemented
        #below commented code proposed by Clode 
        #I'm not testing contracts yet
        #So I'm leaving it as a place holder for future. 

        """ turn = str(self.turn)
        
        # Initialize turn if not exists
        if turn not in self.verbose_log_data["game"]["turns"]:
            self.verbose_log_data["game"]["turns"][turn] = {}
        
        # Initialize judge section if not exists
        if "judge_actions" not in self.verbose_log_data["game"]["turns"][turn]:
            self.verbose_log_data["game"]["turns"][turn]["judge_actions"] = []
        
        judge_entry = {
            "action": judge_action,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response": None,  # Will be filled by log_judge_response
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        self.verbose_log_data["game"]["turns"][turn]["judge_actions"].append(judge_entry)
        self._save_verbose_log()
        
        # Return the index so we can update it later with the response
        return len(self.verbose_log_data["game"]["turns"][turn]["judge_actions"]) - 1 """

    def log_judge_response(self, judge_action_index, response):

        #FIXME It has to be implemented
        #below commented code proposed by Clode 
        #I'm not testing contracts yet
        #So I'm leaving it as a place holder for future. 

        """Log judge responses"""
        """ 
        turn = str(self.turn)
        
        if turn in self.verbose_log_data["game"]["turns"]:
            if "judge_actions" in self.verbose_log_data["game"]["turns"][turn]:
                if judge_action_index < len(self.verbose_log_data["game"]["turns"][turn]["judge_actions"]):
                    self.verbose_log_data["game"]["turns"][turn]["judge_actions"][judge_action_index]["response"] = response
                    self._save_verbose_log()  """

    def log_format_error(self, player_name, error_type, error_details):
        """Log format errors to both event and verbose logs."""
        turn = str(self.turn)
        player_id = player_name.split()[-1] if "Player" in player_name else player_name
        
        # Log to verbose log
        if turn not in self.verbose_log_data["game"]["turns"]:
            self.verbose_log_data["game"]["turns"][turn] = {}
        if "events" not in self.verbose_log_data["game"]["turns"][turn]:
            self.verbose_log_data["game"]["turns"][turn]["events"] = {}
        
        self.verbose_log_data["game"]["turns"][turn]["events"][f"format_error_{error_type}"] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "player": player_name,
            "error_type": error_type,
            "details": error_details
        }
        
        # Log to event log
        if turn not in self.log_data["game"]["turns"]:
            self.log_data["game"]["turns"][turn] = {"players": {}}
        if player_id not in self.log_data["game"]["turns"][turn]["players"]:
            self.log_data["game"]["turns"][turn]["players"][player_id] = {}
        
        if "format_errors" not in self.log_data["game"]["turns"][turn]["players"][player_id]:
            self.log_data["game"]["turns"][turn]["players"][player_id]["format_errors"] = []
        
        self.log_data["game"]["turns"][turn]["players"][player_id]["format_errors"].append({
            "type": error_type,
            "details": error_details,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        })
        
        self._save_event_log()
        self._save_verbose_log()

    def log_system_prompts(self, prompt_config):
        """Log all system prompt templates and configuration at game start"""
#        self.log_data["system_prompts"] = prompt_config
        self.verbose_log_data["system_prompts"] = prompt_config
#        self._save_event_log()
        self._save_verbose_log() 

    
    def log_system_prompt_config(self, config, players):
        """Log the base system prompts and configuration at game start"""
        
        # Log which base prompt is being used
        base_prompt_name = "DEFAULT" if "selfish" not in config.system_prompt.lower() else "SELFISH"
        
        # Log the actual template
        self.log_data["system_prompts"] = {
            "base_template": config.system_prompt,
            "template_type": base_prompt_name,
            "constants": {
                "POINTS_FOR_WIN": POINTS_FOR_WIN,
                "POINTS_FOR_EXTRA_RESOURCE": POINTS_FOR_EXTRA_RESOURCE
            },
            "pay4partner_enabled": config.pay4partner,
            "contract_type": config.contract_type
        }
        
        # Log per-player system prompt variations
        for player in players:
            player_key = f"player_{player.id}"
            self.log_data["system_prompts"][player_key] = {
                "pay4partner_mode_info": player.pay4partner_mode_sys_prompt if hasattr(player, 'pay4partner_mode_sys_prompt') else None,
                "pay4partner_scoring_info": player.pay4partner_scoring_info if hasattr(player, 'pay4partner_scoring_info') else None
            }


    def log_prompt_components(self, player):
        """Log the dynamic components that fill system prompt templates"""
        # Commented out for now as we're evaluating if this logging is needed
        # turn = str(self.turn)
        
        # # Initialize turn if not exists
        # if turn not in self.verbose_log_data["game"]["turns"]:
        #     self.verbose_log_data["game"]["turns"][turn] = {}
        
        # components = {
        #     "player_id": player.id,
        #     "player_name": player.name,
        #     "pay4partner_mode_info": prompts.generate_pay4partner_mode_info(player) if player.pay4partner else "",
        #     "promised_resources_to_give": dict(player.promised_resources_to_give),
        #     "promised_resources_to_receive": dict(player.promised_resources_to_receive),
        #     "current_position": list(player.position),  # Convert tuple to list for JSON
        #     "goal": list(player.goal),  # Convert tuple to list for JSON
        #     "resources": dict(player.resources),
        #     "contract": player.contract,
        #     "contract_type": player.contract_type
        # }
        
        # if "prompt_components" not in self.verbose_log_data["game"]["turns"][turn]:
        #     self.verbose_log_data["game"]["turns"][turn]["prompt_components"] = {}
        
        # self.verbose_log_data["game"]["turns"][turn]["prompt_components"][player.name] = components
        # self._save_verbose_log()
        pass

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