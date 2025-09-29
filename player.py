from collections import defaultdict, deque, namedtuple, Counter
import copy
import json
import random
import re

from anthropic import Anthropic
from openai import OpenAI
from together import Together

from config import GameConfig
from constants import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    TOGETHER_API_KEY,
    AVAILABLE_COLORS,
    POINTS_FOR_WIN,
    POINTS_FOR_EXTRA_RESOURCE,
)
from grid import Grid
import prompts
from utils import get_last_alphabetic_word

# Structured-output schemas & tool defs
from schemas import (
    MOVE_DECISION_SCHEMA,
    TRADE_PROPOSAL_SCHEMA,
    YES_NO_SCHEMA,
    ANTHROPIC_MOVE_TOOL,
    ANTHROPIC_TRADE_TOOL,
    ANTHROPIC_YESNO_TOOL,
)


class Player:
    def __init__(self, id, agent, logger, config: GameConfig, game=None):

        self.config = config
        self.logger = logger

        self.id = str(id)
        self.name = f"Player {id}"
        self.model = agent.value
        self.model_name = agent.name
        self.model_api = agent.api
        self.temperature = config.temperature

        # Init API client
        if self.model_api == 'open_ai':
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        elif self.model_api == 'together':
            self.client = Together(api_key=TOGETHER_API_KEY)
        elif self.model_api == 'anthropic':
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            self.client = None

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
        self.fog_of_war = False  # set in game.py based on config.fog_of_war
        self.non_cooperative_baseline = 0
        self.show_paths = config.show_paths

        # pay4partner
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

        self.game = game

    # ---------- helper for Anthropic structured tool calls ----------
    def _anthropic_structured(self, messages, tool_def, max_tokens=1024):
        """
        Ask Claude to return a single tool call matching tool_def.input_schema.
        Returns the tool 'input' dict (already parsed).
        """
        system_text = "\n".join(m["content"] for m in messages if m["role"] == "system")
        msgs_wo_system = [m for m in messages if m["role"] != "system"]

        resp = self.client.messages.create(
            model=self.model,
            temperature=self.temperature,
            system=system_text or None,
            messages=msgs_wo_system,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_def["name"]},
            max_tokens=max_tokens,
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_def["name"]:
                return block.input
        raise RuntimeError("Claude did not return the expected tool call.")

    # ---------- general helpers ----------
    def get_readable_board(self):
        if self.fog_of_war is None or not self.fog_of_war:
            readable_board = '\n'.join([f'Row {i}: ' + ' '.join(row) for i, row in enumerate(self.grid.tile_colors)])
            return readable_board
        else:
            size = self.grid.size
            board = [['?' for _ in range(size)] for _ in range(size)]
            r, c = self.position
            board[r][c] = self.grid.get_color(r, c)
            for nr, nc in self.grid.get_adjacent(self.position):
                board[nr][nc] = self.grid.get_color(nr, nc)
            readable_board = '\n'.join([f'Row {i}: ' + ' '.join(row) for i, row in enumerate(board)])
            return readable_board

    def compute_non_cooperative_baseline(self):
        path_with_fewest_resources_needed = self.best_routes(self.grid)[0]
        resources_needed = path_with_fewest_resources_needed['resources_missing_due_to_insufficient_inventory']
        path_length = path_with_fewest_resources_needed['path_length_in_steps']
        if resources_needed == {}:
            return POINTS_FOR_WIN + POINTS_FOR_EXTRA_RESOURCE * (sum(self.resources.values()) - path_length)
        else:
            return 0

    ## Core Gameplay
    def distance_to_goal(self):
        distance = abs(self.position[0] - self.goal[0]) + abs(self.position[1] - self.goal[1])
        return distance

    def can_move_to(self, new_pos, grid):
        if new_pos in grid.get_adjacent(self.position) and self.resources[grid.get_color(*new_pos)] > 0:
            return True
        return False

    def can_move_to_with_promised(self, new_pos, grid):
        if new_pos in grid.get_adjacent(self.position) and self.promised_resources_to_receive[
            grid.get_color(*new_pos)] > 0:
            return True
        return False

    def move(self, new_pos, grid):
        tile_color = grid.get_color(*new_pos)
        self.resources[tile_color] -= 1
        self.position = new_pos

    def has_finished(self):
        return self.position == self.goal

    ## Player Anonymization Methods
    def get_player_label(self, game):
        return self.name

    ## Pathfinding and Strategy
    def best_routes(self, grid):
        def _neighbors(pos, rows, cols):
            r, c = pos
            nbrs = []
            if r > 0: nbrs.append((r - 1, c))
            if r < rows - 1: nbrs.append((r + 1, c))
            if c > 0: nbrs.append((r, c - 1))
            if c < cols - 1: nbrs.append((r, c + 1))
            return nbrs

        def _path_colors(path, grid):
            return [grid.get_color(r, c) for (r, c) in path[1:]]

        def _enumerate_paths(grid, start, goal):
            rows = cols = grid.size
            paths = []

            def dfs(curr, visited, path):
                if curr == goal:
                    paths.append(path[:])
                    return
                for nb in _neighbors(curr, rows, cols):
                    if nb not in visited:
                        visited.add(nb)
                        path.append(nb)
                        dfs(nb, visited, path)
                        path.pop()
                        visited.remove(nb)

            dfs(start, {start}, [start])
            return paths

        def top_n_paths(grid, start, goal, resources):
            all_paths = _enumerate_paths(grid, start, goal)
            scored = []
            for p in all_paths:
                colors = _path_colors(p, grid)
                needed = Counter(colors)
                have = Counter(resources)
                shortfall = {res: max(0, needed[res] - have.get(res, 0)) for res in needed}
                shortfall = {res: amt for res, amt in shortfall.items() if amt > 0}

                scored.append({
                    "path": p,
                    "path_length_in_steps": len(p) - 1,
                    "resources_required_for_path": dict(needed),
                    "resources_missing_due_to_insufficient_inventory": shortfall,
                })
            scored.sort(key=lambda x: (sum(x["resources_missing_due_to_insufficient_inventory"].values()),
                                       x["path_length_in_steps"]))
            fewest_resources_needed_path = scored[0]

            scored.sort(key=lambda x: (x["path_length_in_steps"],
                                       sum(x["resources_missing_due_to_insufficient_inventory"].values())))
            shortest_path_with_fewest_resources_needed = scored[0]

            return [fewest_resources_needed_path, shortest_path_with_fewest_resources_needed]

        return top_n_paths(grid, self.position, self.goal, self.resources)

    def format_turn_summary(self, turn_summary, turn_number, with_message_history=False):
        from turn_context import format_turn_summary_for_player
        return format_turn_summary_for_player(turn_summary, turn_number, self.name, self.pay4partner, with_message_history)

    def generate_player_context_message(self, game, grid):
        from turn_context import generate_turn_context
        return generate_turn_context(game, self)

    ## Decision-Making
    def come_up_with_move(self, game, grid):
        if self.model_name == 'human':
            print(f"{self.name}, it's your turn to make a move.")
            while True:
                move = input(
                    "Enter your move: type row and column as 'row,col' (e.g., 2,1 to move to row 2 column 1. Note that rows and columns are 0- indexed), or use W/A/S/D for directions, or type 'n' to skip: "
                ).strip().lower()
                if move == 'n':
                    return None
                elif move in ['w', 'a', 's', 'd']:
                    if move == 'w':
                        r, c = self.position[0] - 1, self.position[1]
                    elif move == 'a':
                        r, c = self.position[0], self.position[1] - 1
                    elif move == 's':
                        r, c = self.position[0] + 1, self.position[1]
                    elif move == 'd':
                        r, c = self.position[0], self.position[1] + 1
                else:
                    try:
                        r, c = map(int, move.split(","))
                    except ValueError:
                        print("Invalid input: Please enter the row and column in r,c format or use WASD. Try again.")
                        continue
                try:
                    new_pos = (r, c)
                    if not (0 <= r < self.grid_size and 0 <= c < self.grid_size):
                        print("Invalid move: The position is out of bounds. Try again.")
                        continue
                    if new_pos not in grid.get_adjacent(self.position):
                        print("Invalid move: You can only move to an adjacent tile. Try again.")
                        continue
                    return new_pos
                except (ValueError, IndexError):
                    print("Invalid input: Please enter the new tile in r,c format. Try again.")
        else:
            # LLM players
            player_context = self.generate_player_context_message(game, grid)
            user_message = prompts.generate_move_prompt(self, player_context=player_context)

            current_messages = list(self.messages) if self.with_message_history else [
                {"role": "system", "content": self.system_prompt}
            ]
            current_messages.append({"role": "user", "content": user_message})

            # Log prompt
            self.game.logger.log_player_prompt(self.name, "move", self.system_prompt, current_messages[-1]["content"])

            # --- Structured for Anthropic/OpenAI; regex for Together ---
            if self.model_api == 'anthropic':
                move_obj = self._anthropic_structured(current_messages, ANTHROPIC_MOVE_TOOL, max_tokens=1024)
                move_raw = json.dumps(move_obj)
            elif self.model_api == 'open_ai':
                move_raw = self.get_completion(
                    current_messages,
                    max_completion_tokens=1000,
                    response_format={"type": "json_schema", "json_schema": MOVE_DECISION_SCHEMA}
                )
                move_obj = json.loads(move_raw)
            else:
                # Together (free text)
                move_text = self.get_completion(current_messages)
                move_raw = move_text  # for logging
                move_obj = None

            # Log response
            payload = {"raw": move_raw}
            if move_obj is not None:
                payload["parsed"] = move_obj
            self.game.logger.log_player_response(self.name, "move", payload)

            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": move_raw}
                ])

            # Validate + return
            try:
                if self.model_api in ('anthropic', 'open_ai'):
                    decision = move_obj.get("decision")
                    if decision == "n":
                        return None
                    if decision != "move":
                        raise ValueError("Missing/invalid 'decision'")

                    move_str = move_obj["move"].strip()
                    r_str, c_str = [s.strip() for s in move_str.split(",")]
                    r, c = int(r_str), int(c_str)
                else:
                    # Together regex fallback
                    def extract_move(text: str):
                        pair_matches = re.findall(r'(-?\d+)\s*,\s*(-?\d+)', text)
                        if pair_matches:
                            rr, cc = map(int, pair_matches[-1])
                            return rr, cc
                        return None

                    if move_raw.strip().lower().endswith('n'):
                        return None
                    extracted = extract_move(move_raw)
                    if not extracted:
                        self.game.logger.log_format_error(
                            self.name, "move_format_error",
                            {"error": "Couldn't extract move", "raw_response": str(move_raw)}
                        )
                        return None
                    r, c = extracted

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
            trade_message_for_human = f"{self.name}, it's your turn to propose a trade."
            if self.pay4partner:
                trade_message_for_human += "\nNote: You are in 'pay for other' mode, so you will pay the other player to move onto tiles of your color as agreed instead of direct swapping of resources."
            print(trade_message_for_human)
            make_trade = input("Do you want to make a trade? y/n ").strip().lower()
            if make_trade != 'y':
                return None

            def get_resource_list(prompt_text):
                resources = []
                i = 1
                while True:
                    message = f"{i}st resource:" if i == 1 else "next resource:"
                    print(message)
                    resource = input(prompt_text).strip()
                    if resource == '.':
                        break
                    if resource in self.colors:
                        quantity = input(f"Enter quantity for {resource}: ").strip()
                        try:
                            quantity = int(quantity)
                            if quantity >= 0:
                                resources.append((resource, quantity))
                                i += 1
                            else:
                                print("Quantity must be positive.")
                        except ValueError:
                            print("Invalid quantity. Please enter a valid integer.")
                    else:
                        print(f"Invalid resource. Available resources: {self.colors}.")
                return resources

            print("Enter the resources you want to offer (type '.' if you have finished):")
            resources_to_offer = get_resource_list("Resource to offer (color): ")
            if not resources_to_offer:
                print("You must offer at least one resource.")
                return None

            print("Enter the resources you want to receive (type '.' if you have finished):")
            resources_to_receive = get_resource_list("Resource to receive (color): ")
            if not resources_to_receive:
                print("You must request at least one resource.")
                return None

            trade_proposal = {
                "resources_to_offer": resources_to_offer,
                "resources_to_receive": resources_to_receive
            }
            return self.clean_trade_proposal(trade_proposal, grid, game)

        # LLM
        player_context = self.generate_player_context_message(game, grid)
        user_message = prompts.generate_trade_proposal_prompt(self, player_context=player_context)

        current_messages = list(self.messages) if self.with_message_history else [
            {"role": "system", "content": self.system_prompt}
        ]
        current_messages.append({"role": "user", "content": user_message})

        # Log prompt
        game.logger.log_player_prompt(self.name, "trade_proposal", self.system_prompt, current_messages[-1]["content"])

        # Structured for Anthropic/OpenAI; regex for Together
        if self.model_api == 'anthropic':
            obj = self._anthropic_structured(current_messages, ANTHROPIC_TRADE_TOOL, max_tokens=2000)
            trade_raw = json.dumps(obj)
        elif self.model_api == 'open_ai':
            trade_raw = self.get_completion(
                current_messages,
                max_completion_tokens=2000,
                response_format={"type": "json_schema", "json_schema": TRADE_PROPOSAL_SCHEMA}
            )
            obj = json.loads(trade_raw)
        else:
            # Together (free text)
            trade_raw = self.get_completion(current_messages, max_completion_tokens=2000)
            obj = None

        # Log response
        payload = {"raw": trade_raw}
        if obj is not None:
            payload["parsed"] = obj
        game.logger.log_player_response(self.name, "trade_proposal", payload)

        if self.with_message_history:
            self.messages.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": trade_raw}
            ])

        if self.model_api not in ('anthropic', 'open_ai'):
            # Together only: allow raw 'n' to cancel
            if trade_raw and trade_raw.strip().lower().endswith('n'):
                return None

        # Normalize/validate + attach message
        try:
            if self.model_api in ('anthropic', 'open_ai'):
                def coerce_side(v):
                    out = []
                    for item in v:
                        if isinstance(item, dict) and "color" in item and "quantity" in item:
                            out.append((item["color"], int(item["quantity"])))
                        elif isinstance(item, (list, tuple)) and len(item) == 2:
                            out.append((item[0], int(item[1])))
                    return out

                offer = coerce_side(obj.get("resources_to_offer", []))
                receive = coerce_side(obj.get("resources_to_receive", []))
                if not offer or not receive:
                    raise ValueError("Missing offer/receive arrays")

                trade_proposal = {
                    "resources_to_offer": offer,
                    "resources_to_receive": receive
                }

            else:
                # Together: regex scrape last JSON object
                matches = re.findall(r"\{.*?\}", trade_raw, re.DOTALL)
                if not matches:
                    raise ValueError("No JSON object found in Together response.")
                json_str = matches[-1]
                trade_proposal = json.loads(json_str)

                # Fix common key errors
                if 'resources_to offer' in trade_proposal:
                    trade_proposal['resources_to_offer'] = trade_proposal.pop('resources_to offer')
                if 'resources to offer' in trade_proposal:
                    trade_proposal['resources_to_offer'] = trade_proposal.pop('resources to offer')
                if 'resources_to receive' in trade_proposal:
                    trade_proposal['resources_to_receive'] = trade_proposal.pop('resources_to receive')
                if 'resources to receive' in trade_proposal:
                    trade_proposal['resources_to_receive'] = trade_proposal.pop('resources to receive')

            cleaned = self.clean_trade_proposal(trade_proposal, grid, game)
            if not cleaned:
                print("- Invalid trade proposal")
                return None
            trade_proposal = cleaned

            # attach a concise summary for downstream logs/UI
            offer_str = ", ".join(f"{c}:{q}" for c, q in trade_proposal["resources_to_offer"])
            recv_str = ", ".join(f"{c}:{q}" for c, q in trade_proposal["resources_to_receive"])
            trade_proposal["message"] = f"{self.name} offers [{offer_str}] for [{recv_str}]"

            player_label = self.get_player_label(game)
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
            game.logger.log_player_response(self.name, "trade_proposal_error", f"(AI Agent does not see this)\n{error_msg}")
            game.logger.log_format_error(self.name, "trade_parse_error", {"error": str(e), "raw_response": str(trade_raw)})
            return None

    def accept_trade(self, grid, game, trade):
        resources_to_offer = trade['resources_to_offer']
        resources_to_receive = trade['resources_to_receive']

        accept_message = f"{self.name} accepted the trade proposal. \n"
        reject_message = f"{self.name} rejected the trade proposal. \n"

        if self.model_name == 'human':
            print(f"""You have been approached for the following trade:
                The other player is offering you {resources_to_offer} in exchange for {resources_to_receive}.""")
            while True:
                accept_trade = input("Do you accept this trade? y/n").strip().lower()
                if accept_trade.strip().lower() not in ('y', 'n'):
                    print("Please enter 'y' or 'n'.")
                    continue
                if accept_trade.strip().lower() == 'y':
                    print(accept_message)
                    return True
                else:
                    print(reject_message)
                    return False
        else:
            player_context = self.generate_player_context_message(game, grid)
            user_message = prompts.generate_trade_response_prompt(
                self,
                player_context=player_context,
                resources_to_offer=resources_to_offer,
                resources_to_receive=resources_to_receive
            )

            current_messages = list(self.messages) if self.with_message_history else [
                {"role": "system", "content": self.system_prompt}
            ]
            current_messages.append({"role": "user", "content": user_message})

            # Log prompt
            game.logger.log_player_prompt(self.name, "trade_response", self.system_prompt, current_messages[-1]["content"])

            # Structured for Anthropic/OpenAI; plain for Together
            if self.model_api == 'anthropic':
                obj = self._anthropic_structured(current_messages, ANTHROPIC_YESNO_TOOL, max_tokens=512)
                resp_raw = json.dumps(obj)
                answer = obj.get("answer", "").lower()
                reasoning = obj.get("rationale", "")
            elif self.model_api == 'open_ai':
                resp_raw = self.get_completion(
                    current_messages,
                    max_completion_tokens=256,
                    response_format={"type": "json_schema", "json_schema": YES_NO_SCHEMA}
                )
                # Robust parse: pure JSON or extract last JSON object; fallback to last alphabetic word
                try:
                    parsed = json.loads(resp_raw)
                except Exception:
                    match = re.findall(r"\{.*?\}", resp_raw, re.DOTALL)
                    if match:
                        parsed = json.loads(match[-1])
                    else:
                        parsed = {"answer": get_last_alphabetic_word(resp_raw).lower(), "rationale": resp_raw}
                answer = (parsed.get("answer") or "").lower()
                reasoning = parsed.get("rationale", "")
            else:
                resp_raw = self.get_completion(current_messages, max_completion_tokens=512)
                answer = get_last_alphabetic_word(resp_raw).lower()
                reasoning = resp_raw

            will_accept = (answer == "yes")

            # Log response
            game.logger.log_player_response(self.name, "trade_response",
                                            {"raw": resp_raw, "parsed": {"answer": answer, "rationale": reasoning}})

            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": resp_raw}
                ])

            if not will_accept and answer not in ("yes", "no"):
                print(f"Unclear response: '{resp_raw}', defaulting to NO")

            if will_accept:
                print(accept_message)
            else:
                print(reject_message)
            return will_accept

    ## Utility Functions
    def clean_trade_proposal(self, trade_proposal, grid=None, game=None):
        """
        Clean and validate a trade proposal:
        1. Make all strings uppercase and stripped
        2. Prevent trading with self
        3. Return None for invalid trades
        """
        if isinstance(trade_proposal, dict):
            cleaned = {key: self.clean_trade_proposal(value, grid, game) for key, value in trade_proposal.items()}
            if game and game.players:
                # Prevent trading with self (assumes 2 players; adapt if >2)
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
        player_context = self.generate_player_context_message(game, grid)
        agreements = [agreement['text_summary'] for agreement in self.pay4partner_log if agreement['with'] == other_player.name]
        message = prompts.generate_pay4partner_prompt(
            self,
            player_context=player_context,
            color=color,
            agreements=agreements
        )
        if self.model_name == 'human':
            print(f"{self.name}, {other_player.name} is invoking 'pay for partner' and asking you to pay for their move onto a {color} tile.")
            while True:
                agree = input("Do you agree to this? y/n ").strip().lower()
                if agree not in ('y', 'n'):
                    print("Please enter 'y' or 'n'.")
                    continue
                return agree == 'y'
        else:
            current_messages = list(self.messages) if self.with_message_history else [
                {"role": "system", "content": self.system_prompt}
            ]
            current_messages.append({"role": "user", "content": message})

            game.logger.log_player_prompt(self.name, "pay4partner", self.system_prompt, message)

            agree = self.get_completion(current_messages)

            game.logger.log_player_response(self.name, "pay4partner", agree)

            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": agree}
                ])

            final_response = get_last_alphabetic_word(agree)
            if "yes" in final_response or "accept" in final_response or "agree" in final_response:
                return True
            else:
                game.logger.log_format_error(self.name, "pay4partner_response_invalid_format",
                                             {"raw_response": agree})
                return False

    def generate_tile_level_contract_prompt(self, player_context):
        return prompts.generate_tile_level_contract_prompt(self.system_prompt, player_context)

    def generate_contract_for_finishing_prompt(self, player_context):
        return prompts.generate_contract_for_finishing_prompt(self.system_prompt, player_context)

    def get_completion(self, messages, max_completion_tokens=1000, response_format=None):
        """
        Generic model call.
        - For OpenAI, if response_format is provided (e.g., structured outputs), it will be used.
        - Anthropic/Together paths ignore response_format here (Anthropic structured is handled via _anthropic_structured).
        """
        # Optional: log full message set if your logger supports it
        if hasattr(self, 'game') and self.game and hasattr(self.game, 'logger') and hasattr(self.game.logger, 'log_complete_message_set'):
            self.game.logger.log_complete_message_set(self.name, messages, max_completion_tokens)

        if self.model_api == 'anthropic':
            # Free-text path for Anthropic (structured handled elsewhere)
            try:
                system_prompt = "\n".join(m['content'] for m in messages if m['role'] == 'system')
                msg_wo_sys = [m for m in messages if m['role'] != 'system']
                response = self.client.messages.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=msg_wo_sys,
                    system=system_prompt or None,
                    max_tokens=max_completion_tokens
                )
                for block in response.content:
                    if getattr(block, "type", None) == "text":
                        return block.text.strip()
                return ""
            except Exception as e:
                print(f"Error with Anthropic API: {e}")
                print(messages)
                raise e
        elif self.model_api == 'open_ai':
            kwargs = {
                "model": self.model,
                "temperature": self.temperature,
                "messages": messages,
                "max_completion_tokens": max_completion_tokens
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content.strip() if isinstance(content, str) else content
        else:
            # Together
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=messages,
                max_tokens=max_completion_tokens
            )
            return response.choices[0].message.content.strip()
