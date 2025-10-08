# player.py
from collections import defaultdict, deque, namedtuple, Counter
import copy
import json
import random
import re

from config import GameConfig
from constants import (
    AVAILABLE_COLORS,
    POINTS_FOR_WIN,
    POINTS_FOR_EXTRA_RESOURCE,
)
from grid import Grid
import prompts
from utils import get_last_alphabetic_word

from schemas import (
    MOVE_DECISION_SCHEMA,
    TRADE_PROPOSAL_SCHEMA,
    YES_NO_SCHEMA,
    ANTHROPIC_MOVE_TOOL,
    ANTHROPIC_TRADE_TOOL,
    ANTHROPIC_YESNO_TOOL,
)

# Adapter
from model_adapter import ModelAdapter

# Human I/O
from human_player import HumanPlayer

# Pathfinding helper
from player_helper import compute_best_routes


class Player:
    def __init__(self, id, agent, logger, config: GameConfig, game=None):
        self.config = config
        self.logger = logger
        self.game = game

        self.id = str(id)
        self.name = f"Player {id}"
        self.model = agent.value
        self.model_name = agent.name
        self.model_api = agent.api
        self.temperature = config.temperature

        # All vendor-specific client wiring is inside ModelAdapter
        self.api_llm_model = ModelAdapter(self.model_api, self.model, self.temperature)

        # Count API calls per player
        self.n_api_calls = 0

        self.start_pos = (random.randint(0, config.random_start_block_size - 1),
                          random.randint(0, config.random_start_block_size - 1))
        self.goal = (random.randint(config.grid_size - config.random_goal_block_size, config.grid_size - 1),
                     random.randint(config.grid_size - config.random_goal_block_size, config.grid_size - 1))
        self.position = self.start_pos

        self.n_total_players = len(config.players)
        self.surplus = config.surplus
        self.grid_size = config.grid_size
        self.resource_mode = config.resource_mode
        self.colors = config.colors
        self.resources = {color: 0 for color in self.colors}
        self.starting_resources = {color: 0 for color in self.colors}
        self.promised_resources_to_give = {color: 0 for color in self.colors}
        self.promised_resources_to_receive = {color: 0 for color in self.colors}
        self.contract_type = config.contract_type
        self.contract = None
        self.score = 0
        self.grid = Grid(self.grid_size, self.colors, grid=self.config.grid)
        self.fog_of_war = False
        self.non_cooperative_baseline = 0
        self.show_paths = config.show_paths

        # pay4partner configuration
        self.pay4partner = config.pay4partner
        self.pay4partner_log = []
        self.pay4partner_mode_sys_prompt = prompts.generate_pay4partner_mode_info(self, short_summary=True)
        self.trading_rules = prompts.generate_trade_system_info(self)
        self.system_prompt = config.system_prompt.format(
            pay4partner_mode_info=self.pay4partner_mode_sys_prompt,
            trading_rules=self.trading_rules
        )

        # message history
        self.with_message_history = config.with_message_history
        self.messages = [{"role": "system", "content": self.system_prompt}] if self.with_message_history else []

    # ====== Internal wrappers that bump n_api_calls ======
    def _structured(self, messages, schema_or_tool, max_tokens=1000):
        """Wrapper for adapter.structured that increments n_api_calls."""
        self.n_api_calls += 1
        return self.api_llm_model.structured(messages, schema_or_tool=schema_or_tool, max_tokens=max_tokens)

    def _chat(self, messages, max_completion_tokens=1000):
        """Wrapper for adapter.chat_completion that increments n_api_calls."""
        self.n_api_calls += 1
        return self.api_llm_model.chat_completion(messages, max_completion_tokens)

    def get_readable_board(self):
        if self.fog_of_war is None or not self.fog_of_war:
            return '\n'.join([f'Row {i}: ' + ' '.join(row) for i, row in enumerate(self.grid.tile_colors)])
        size = self.grid.size
        board = [['?' for _ in range(size)] for _ in range(size)]
        r, c = self.position
        board[r][c] = self.grid.get_color(r, c)
        for nr, nc in self.grid.get_adjacent(self.position):
            board[nr][nc] = self.grid.get_color(nr, nc)
        return '\n'.join([f'Row {i}: ' + ' '.join(row) for i, row in enumerate(board)])

    def compute_non_cooperative_baseline(self):
        path_with_fewest_resources_needed = self.best_routes(self.grid)[0]
        resources_needed = path_with_fewest_resources_needed['resources_missing_due_to_insufficient_inventory']
        path_length = path_with_fewest_resources_needed['path_length_in_steps']
        if resources_needed == {}:
            return POINTS_FOR_WIN + POINTS_FOR_EXTRA_RESOURCE * (sum(self.resources.values()) - path_length)
        else:
            return 0

    # ---------- Core gameplay ----------
    def distance_to_goal(self):
        return abs(self.position[0] - self.goal[0]) + abs(self.position[1] - self.goal[1])

    def can_move_to(self, new_pos, grid):
        return new_pos in grid.get_adjacent(self.position) and self.resources[grid.get_color(*new_pos)] > 0

    def can_move_to_with_promised(self, new_pos, grid):
        return new_pos in grid.get_adjacent(self.position) and \
               self.promised_resources_to_receive[grid.get_color(*new_pos)] > 0

    def move(self, new_pos, grid):
        tile_color = grid.get_color(*new_pos)
        self.resources[tile_color] -= 1
        self.position = new_pos

    def has_finished(self):
        return self.position == self.goal

    # ---------- Labels / context ----------
    def get_player_label(self, game):
        return self.name

    def best_routes(self, grid):
        """wrapper to player_helper"""
        return compute_best_routes(grid, self.position, self.goal, self.resources)

    def format_turn_summary(self, turn_summary, turn_number, with_message_history=False):
        from turn_context import format_turn_summary_for_player
        return format_turn_summary_for_player(turn_summary, turn_number, self.name, self.pay4partner, with_message_history)

    def generate_player_context_message(self, game, grid):
        from turn_context import generate_turn_context
        return generate_turn_context(game, self)

    # ---------- Decision-making ----------
    def come_up_with_move(self, game, grid):
        if self.model_name == 'human':
            return HumanPlayer.get_move(self, grid)

        player_context = self.generate_player_context_message(game, grid)
        print(player_context)
        user_message = prompts.generate_move_prompt(self, player_context=player_context)

        current_messages = list(self.messages) if self.with_message_history else \
            [{"role": "system", "content": self.system_prompt}]
        current_messages.append({"role": "user", "content": user_message})

        # Log prompt
        self.game.logger.log_player_prompt(self.name, "move", self.system_prompt, current_messages[-1]["content"])

        # One unified structured call (counts toward n_api_calls via _structured)
        schema_or_tool = ANTHROPIC_MOVE_TOOL if self.model_api == "anthropic" else MOVE_DECISION_SCHEMA
        move_obj, move_raw = self._structured(current_messages, schema_or_tool=schema_or_tool, max_tokens=1000)

        # Log response
        self.game.logger.log_player_response(self.name, "move", {"raw": move_raw, "parsed": move_obj})

        if self.with_message_history:
            self.messages.extend([{"role": "user", "content": user_message},
                                  {"role": "assistant", "content": move_raw}])

        # Validate + return
        try:
            decision = move_obj.get("decision")
            if decision == "n":
                return None
            if decision != "move":
                raise ValueError("Missing/invalid 'decision'")
            r_str, c_str = [s.strip() for s in move_obj["move"].strip().split(",")]
            r, c = int(r_str), int(c_str)

            new_pos = (r, c)
            if not (0 <= r < self.grid_size and 0 <= c < self.grid_size):
                self.game.logger.log_format_error(self.name, "move_out_of_bounds",
                                                  {"attempted_move": str(new_pos), "raw_response": str(move_raw)})
                return None
            if new_pos not in grid.get_adjacent(self.position):
                self.game.logger.log_format_error(self.name, "move_not_adjacent", {
                    "attempted_move_from": str(self.position),
                    "attempted_move_to": str(new_pos),
                    "raw_response": str(move_raw)
                })
                return None
            return new_pos
        except Exception as e:
            self.game.logger.log_format_error(self.name, "move_format_error",
                                              {"error": str(e), "raw_response": str(move_raw)})
            return None

    def propose_trade(self, grid, game):
        if self.model_name == 'human':
            return HumanPlayer.propose_trade(self, grid, game)

        player_context = self.generate_player_context_message(game, grid)
        user_message = prompts.generate_trade_proposal_prompt(self, player_context=player_context)

        current_messages = list(self.messages) if self.with_message_history else \
            [{"role": "system", "content": self.system_prompt}]
        current_messages.append({"role": "user", "content": user_message})

        self.game.logger.log_player_prompt(self.name, "trade_proposal", self.system_prompt, current_messages[-1]["content"])

        # Structured call (counts via _structured)
        schema_or_tool = ANTHROPIC_TRADE_TOOL if self.model_api == "anthropic" else TRADE_PROPOSAL_SCHEMA
        obj, trade_raw = self._structured(current_messages, schema_or_tool=schema_or_tool, max_tokens=2000)

        self.game.logger.log_player_response(self.name, "trade_proposal", {"raw": trade_raw, "parsed": obj})

        if self.with_message_history:
            self.messages.extend([{"role": "user", "content": user_message},
                                  {"role": "assistant", "content": trade_raw}])

        try:
            def coerce_side(v):
                out = []
                for item in v:
                    if isinstance(item, dict) and "color" in item and "quantity" in item:
                        out.append((item["color"], int(item["quantity"])))
                    elif isinstance(item, (list, tuple)) and len(item) == 2:
                        out.append((item[0], int(item[1])))
                return out

            rationale = obj.get("rationale", "")
            offer = coerce_side(obj.get("resources_to_offer", []))
            receive = coerce_side(obj.get("resources_to_receive", []))

            if not offer and not receive:
                return None
            if not offer or not receive:
                raise ValueError("Missing offer/receive arrays")

            trade_proposal = {
                "rationale": rationale,
                "resources_to_offer": offer,
                "resources_to_receive": receive
            }

            cleaned = self.clean_trade_proposal(trade_proposal, grid, game)
            if not cleaned:
                print("- Invalid trade proposal")
                return None
            trade_proposal = cleaned

            offer_str = ", ".join(f"{c}:{q}" for c, q in trade_proposal["resources_to_offer"])
            recv_str = ", ".join(f"{c}:{q}" for c, q in trade_proposal["resources_to_receive"])
            rationale = trade_proposal.get("rationale", "")
            trade_proposal["message"] = f"{self.name} offers [{offer_str}] for [{recv_str}]"
            if rationale:
                # Use JSON encoding to properly escape the rationale
                import json
                escaped_rationale = json.dumps(rationale)[1:-1]  # Remove outer quotes
                trade_proposal["message"] += f" (Rationale: {escaped_rationale})"

            player_label = self.get_player_label(game)
            if rationale:
                print(f"- Rationale: {rationale}")
            if self.pay4partner:
                print(f"\n{player_label} proposes Pay for Partner trade:")
                print(f"- Offering to cover: {trade_proposal['resources_to_offer']}")
                print(f"- Requesting to be covered for: {trade_proposal['resources_to_receive']}")
            else:
                print(f"\n{player_label} proposes trade:")
                print(f"- Offering: {trade_proposal['resources_to_offer']}")
                print(f"- Requesting: {trade_proposal['resources_to_receive']}")

            return trade_proposal

        except Exception as e:
            error_msg = f"Trade proposal parse/validation error: {e}"
            print(error_msg)
            game.logger.log_player_response(self.name, "trade_proposal_error",
                                            f"(AI Agent does not see this)\n{error_msg}")
            game.logger.log_format_error(self.name, "trade_parse_error",
                                         {"error": str(e), "raw_response": str(trade_raw)})
            return None

    def accept_trade(self, grid, game, trade):
        if self.model_name == 'human':
            return HumanPlayer.accept_trade(self, grid, game, trade)

        resources_to_offer = trade['resources_to_offer']
        resources_to_receive = trade['resources_to_receive']

        accept_message = f"{self.name} accepted the trade proposal. \n"
        reject_message = f"{self.name} rejected the trade proposal. \n"

        player_context = self.generate_player_context_message(game, grid)
        user_message = prompts.generate_trade_response_prompt(
            self,
            player_context=player_context,
            resources_to_offer=resources_to_offer,
            resources_to_receive=resources_to_receive
        )

        current_messages = list(self.messages) if self.with_message_history else \
            [{"role": "system", "content": self.system_prompt}]
        current_messages.append({"role": "user", "content": user_message})

        self.game.logger.log_player_prompt(self.name, "trade_response", self.system_prompt, current_messages[-1]["content"])

        # Structured call (counts via _structured)
        schema_or_tool = ANTHROPIC_YESNO_TOOL if self.model_api == "anthropic" else YES_NO_SCHEMA
        parsed, resp_raw = self._structured(current_messages, schema_or_tool=schema_or_tool, max_tokens=256)

        answer = (parsed.get("answer") or "").lower()
        reasoning = parsed.get("rationale", "")
        will_accept = (answer == "yes")

        self.game.logger.log_player_response(self.name, "trade_response",
                                             {"raw": resp_raw, "parsed": {"answer": answer, "rationale": reasoning}})

        if self.with_message_history:
            self.messages.extend([{"role": "user", "content": user_message},
                                  {"role": "assistant", "content": resp_raw}])

        if not will_accept and answer not in ("yes", "no"):
            print(f"Unclear response: '{resp_raw}', defaulting to NO")

        # Display rationale if provided
        if reasoning:
            print(f"- Rationale: {reasoning}")
        
        print(accept_message if will_accept else reject_message)
        return will_accept

    # ---------- Utility ----------
    def clean_trade_proposal(self, trade_proposal, grid=None, game=None):
        if isinstance(trade_proposal, dict):
            cleaned = {key: self.clean_trade_proposal(value, grid, game) for key, value in trade_proposal.items()}
            if game and game.players:
                other_player = next((p for p in game.players if p.name != self.name), None)
                if not other_player:
                    print(f"Invalid trade: Cannot trade with self")
                    return None
            return cleaned
        elif isinstance(trade_proposal, list):
            return [self.clean_trade_proposal(item) for item in trade_proposal]
        elif isinstance(trade_proposal, tuple):
            return tuple(self.clean_trade_proposal(item) for item in trade_proposal)
        elif isinstance(trade_proposal, str):
            return trade_proposal.strip().upper()
        else:
            return trade_proposal

    def agree_to_pay4partner(self, other_player, color, game, grid):
        if self.model_name == 'human':
            return HumanPlayer.agree_to_pay4partner(self, other_player, color)

        player_context = self.generate_player_context_message(game, grid)
        agreements = [a['text_summary'] for a in self.pay4partner_log if a['with'] == other_player.name]
        message = prompts.generate_pay4partner_prompt(self, player_context=player_context, color=color, agreements=agreements)

        current_messages = list(self.messages) if self.with_message_history else \
            [{"role": "system", "content": self.system_prompt}]
        current_messages.append({"role": "user", "content": message})

        self.game.logger.log_player_prompt(self.name, "pay4partner", self.system_prompt, message)

        # Structured call (counts via _structured)
        schema_or_tool = ANTHROPIC_YESNO_TOOL if self.model_api == "anthropic" else YES_NO_SCHEMA
        parsed, resp_raw = self._structured(current_messages, schema_or_tool=schema_or_tool, max_tokens=256)

        answer = (parsed.get("answer") or "").lower()
        reasoning = parsed.get("rationale", "")
        will_agree = (answer == "yes")

        self.game.logger.log_player_response(self.name, "pay4partner", {"raw": resp_raw, "parsed": {"answer": answer, "rationale": reasoning}})

        if self.with_message_history:
            self.messages.extend([{"role": "user", "content": message},
                                  {"role": "assistant", "content": resp_raw}])

        # Display rationale if provided
        if reasoning:
            print(f"- Rationale: {reasoning}")

        if not will_agree and answer not in ("yes", "no"):
            print(f"Unclear response: '{resp_raw}', defaulting to NO")

        return will_agree

    def generate_tile_level_contract_prompt(self, player_context):
        return prompts.generate_tile_level_contract_prompt(self.system_prompt, player_context)

    def generate_contract_for_finishing_prompt(self, player_context):
        return prompts.generate_contract_for_finishing_prompt(self.system_prompt, player_context)

    def get_completion(self, messages, max_completion_tokens=1000):
        if hasattr(self, 'game') and self.game and hasattr(self.game, 'logger'):
            self.game.logger.log_complete_message_set(self.name, messages, max_completion_tokens)
        return self._chat(messages, max_completion_tokens)
