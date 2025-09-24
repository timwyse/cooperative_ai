from collections import defaultdict, deque, namedtuple, Counter
import copy
import json
import random
import re

from anthropic import Anthropic
from openai import OpenAI
from together import Together

from config import GameConfig
from constants import ANTHROPIC_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY, AVAILABLE_COLORS, POINTS_FOR_WIN, POINTS_FOR_EXTRA_RESOURCE
from grid import Grid
import prompts
from utils import get_last_alphabetic_word


class Player:
    def __init__(self, id, agent, logger, config: GameConfig):

        self.config = config
        self.logger = logger

        self.id = str(id)
        self.name = f"Player {id}"
        self.model = agent.value
        self.model_name = agent.name
        self.model_api = agent.api
        self.temperature = config.temperature
        self.system_prompt = config.system_prompt

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
        self.fog_of_war = False # set in game.py based on config.fog_of_war
        self.non_cooperative_baseline = 0

        # init pay4partner settings
        self.pay4partner = config.pay4partner
        self.pay4partner_log = []
        self.pay4partner_scoring_info = "In 'pay for other' mode, any resources you have promised to give to other players as part of trade agreements are still counted as your resources (and hence potential contributors to your final score) until you actually give them away." if self.pay4partner else ""

        self.pay4partner_mode_sys_prompt = prompts.generate_pay4partner_mode_info(self, short_summary=True) 


        # Init message history settings
        self.with_message_history = config.with_message_history
        self.messages = [{"role": "system", "content": self.system_prompt.format(player_name="you",
                                                                                 pay4partner_mode_info=self.pay4partner_mode_sys_prompt,
                                                                                 pay4partner_scoring_info=self.pay4partner_scoring_info)}] if self.with_message_history else []

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
        """Get display label for this player for user/console output"""
        # Just use the standard player name (Player 0, Player 1, etc.)
        return self.name

    ## Pathfinding and Strategy
    def best_routes(self, grid):
        """
        Runs a BFS to find the top n paths to the player's goal, given their current resources.
        Returns two paths:
        1) The path that requires the fewest additional resources (i.e. the path with the least shortfall)
        2) The shortest path (in steps) that requires the fewest additional resources (i.e. the shortest path with the least shortfall)
        """

        def _neighbors(pos, rows, cols):
            r, c = pos
            nbrs = []
            if r > 0: nbrs.append((r - 1, c))
            if r < rows - 1: nbrs.append((r + 1, c))
            if c > 0: nbrs.append((r, c - 1))
            if c < cols - 1: nbrs.append((r, c + 1))
            return nbrs

        def _path_colors(path, grid):
            """Colors paid along a path; you pay when you move ONTO a tile, i.e. path[1:]."""
            return [grid.get_color(r, c) for (r, c) in path[1:]]

        def _enumerate_paths(grid, start, goal):
            """Enumerate paths from start to goal.
            generates all simple paths (no revisits) via DFS.
            """
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
            """Return up to n best paths sorted by:
            1) resource shortfall ascending
            2) path length descending
            Each result item includes: path, length, shortfall, required_counts, resources.
            """
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

            scored.sort(key=lambda x: (x["path_length_in_steps"], sum(x["resources_missing_due_to_insufficient_inventory"].values())))

            shortest_path_with_fewest_resources_needed = scored[0]
            
            return [fewest_resources_needed_path, shortest_path_with_fewest_resources_needed]

        best = top_n_paths(grid, self.position, self.goal, self.resources)

        return best


    def format_turn_summary(self, turn_summary, turn_number, with_message_history=False):
        """Format turn summary with anonymized player names for AI prompts"""

        from turn_context import format_turn_summary_for_player
        return format_turn_summary_for_player(turn_summary, turn_number, self.name, self.pay4partner, with_message_history)

    def generate_player_context_message(self, game, grid):
        """
        Generates a reusable message about the board state, player's resources, position, and goal.
        Also includes recent turn history for context.
        """

        from turn_context import generate_turn_context
        return generate_turn_context(game, self)
    

    ## Decision-Making
    def come_up_with_move(self, game, grid):
        if self.model_name == 'human':
            print(f"{self.name}, it's your turn to make a move.")
            while True:
                move = input(
                    "Enter your move: type row and column as 'row,col' (e.g., 2,1 to move to row 2 column 1. Note that rows and columns are 0-indexed), or use W/A/S/D for directions, or type 'n' to skip: ").strip().lower()
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
        # LLM Player
        else:
            best_path = self.best_routes(grid)[0]
            next_move = best_path["path"][1] if best_path["path"] else None
            resources_needed = best_path["resources_required_for_path"]
            resources_missing = best_path["resources_missing_due_to_insufficient_inventory"]

            player_context = self.generate_player_context_message(game, grid)
            print(player_context)
            user_message = prompts.generate_move_prompt(self,
                player_context=player_context
            )
            
            # Prepare messages for this request
            system_prompt = self.system_prompt.format(player_name="you",
                                                    pay4partner_mode_info=self.pay4partner_mode_sys_prompt,
                                                    pay4partner_scoring_info=self.pay4partner_scoring_info)
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system",
                                                                                       "content": system_prompt}]
            current_messages.append({"role": "user", "content": user_message})

            # Log prompt to verbose logger
            user_prompt = current_messages[-1]["content"]
            game.logger.log_player_prompt(game.turn, self.name, self.model_name, "move", system_prompt, user_prompt)

            move = self.get_completion(current_messages)

            # Log response to verbose logger with full response

            game.logger.log_player_response(game.turn, self.name, self.model_name, "move", move)

            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": move}
                ])
            player_label = self.get_player_label(game)
            print(f"""{player_label} proposed a move:
                    {move}""")

            def ends_with_n(text: str) -> bool:
                """
                Returns True if the last alphanumeric 'word' in the text
                is exactly 'n' or 'N'.
                """
                # Find all alphanumeric words
                words = re.findall(r"[A-Za-z0-9]+", text)
                if not words:
                    return False
                return words[-1].lower() == "n"

            if ends_with_n(move):
                return None
            try:
                def extract_move(text: str):
                    '''
                    Finds the last occurrence of a pair of integers in the text formatted as "int,int"
                    '''
                    pair_matches = re.findall(r'(-?\d+)\s*,\s*(-?\d+)', text)
                    if pair_matches:
                        r, c = map(int, pair_matches[-1])
                        return r, c
                    return None
                
                extracted_move = extract_move(move)
                if extracted_move is None:
                    print("Invalid move: Could not extract a valid position.")
                    return None

                r, c = extract_move(move)
                new_pos = (r, c)
                if not (0 <= r < self.grid_size and 0 <= c < self.grid_size):
                    print("Invalid move: The position is out of bounds.")
                    return None
                if new_pos not in grid.get_adjacent(self.position):
                    print("Invalid move: You can only move to an adjacent tile.")
                    return None
                tile_color = grid.get_color(r, c)

                return new_pos
            except (ValueError, IndexError):
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

            def get_valid_player(prompt):
                available_players = [p.id for p in game.players if p.id != self.id]
                print(f"Available players: {available_players}")
                while True:
                    value = input(prompt).strip().lower()
                    if value.strip().lower() == 'n':
                        return value
                    try:
                        if value in available_players:
                            return value
                        else:
                            print(f"Please enter a valid player. The options are {available_players}.")
                    except ValueError:
                        print(f"Invalid input. Please enter a valid player ID from {available_players}.")

            def get_resource_list(prompt):
                resources = []
                i = 1
                while True:
                    message = f"{i}st resource:" if i == 1 else "next resource:"
                    print(message)
                    resource = input(prompt).strip()
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

        # LLM Player
        else:

            player_context = self.generate_player_context_message(game, grid)
            best_path = self.best_routes(grid)[0]
            user_message = prompts.generate_trade_proposal_prompt(self,
                player_context=player_context
            )

            # Prepare messages for this request
            system_prompt = self.system_prompt.format(player_name="you",
                                                      pay4partner_mode_info=self.pay4partner_mode_sys_prompt,
                                                      pay4partner_scoring_info=self.pay4partner_scoring_info)
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system",
                                                                                       "content": system_prompt}]
            current_messages.append({"role": "user", "content": user_message})

            # Log prompt to verbose logger
            user_prompt = current_messages[-1]["content"]
            game.logger.log_player_prompt(game.turn, self.name, self.model_name, "trade_proposal", system_prompt,
                                          user_prompt)

            # Make the API call
            trade_proposal = self.get_completion(current_messages, max_completion_tokens=2000)

            # Log response to verbose logger with full response
            game.logger.log_player_response(game.turn, self.name, self.model_name, "trade_proposal", trade_proposal)

            # Save to history if enabled
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": trade_proposal}
                ])
            if trade_proposal == 'n':
                return None

            player_label = self.get_player_label(game)
            if self.pay4partner:
                print(f"\n{player_label} proposes Pay for Partner trade:")
            else:
                print(f"\n{player_label} proposes trade:")
            try:
                match = re.search(r"\{.*?\}", trade_proposal, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    try:
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
                        if cleaned:
                            trade_proposal = cleaned
                            if self.pay4partner:
                                print(f"- Offering to cover: {trade_proposal['resources_to_offer']}")
                                print(f"- Requesting to be covered for: {trade_proposal['resources_to_receive']}")
                            else:
                                print(f"- Offering: {trade_proposal['resources_to_offer']}")
                                print(f"- Requesting: {trade_proposal['resources_to_receive']}")
                        else:
                            print("- Invalid trade proposal")
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON format in trade proposal: {e}"
                        print(error_msg)
                        game.logger.log_player_response(game.turn, self.name, self.model_name, "trade_proposal_invalid_json", 
                            f"(AI Agent does not see this)\n{error_msg}")
                        trade_proposal = None
            except Exception as e:
                error_msg = f"Error parsing trade proposal: {e}"
                print(error_msg)
                game.logger.log_player_response(game.turn, self.name, self.model_name, "trade_proposal_error", 
                    f"(AI Agent does not see this)\n{error_msg}")
                trade_proposal = None

            return trade_proposal

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
                elif accept_trade.strip().lower() == 'n':
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

            # Prepare messages for this request
            system_prompt =  self.system_prompt.format(player_name="you",
                                                       pay4partner_mode_info=self.pay4partner_mode_sys_prompt,
                                                       pay4partner_scoring_info=self.pay4partner_scoring_info)
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system",
                                                                                       "content": system_prompt}]
            current_messages.append({"role": "user", "content": user_message})
            user_prompt = current_messages[-1]["content"]
            game.logger.log_player_prompt(game.turn, self.name, self.model_name, "trade_response", system_prompt,
                                          user_prompt)

            # Make the API call to get rade response

            accept_trade = self.get_completion(current_messages)
            
            # Determine the actual decision made
            first_word = accept_trade.split()[0] if accept_trade.split() else ""

            last_word = get_last_alphabetic_word(accept_trade)
            if first_word == "yes" or accept_trade == "yes" or last_word == "yes":
                decision_result = "trade_accepted"
                will_accept = True
            elif first_word == "no" or accept_trade == "no" or last_word == "no":
                decision_result = "trade_rejected"
                will_accept = False
            else:
                decision_result = "trade_rejected_unclear_response"
                will_accept = False

            # Log response to verbose logger with full response
            game.logger.log_player_response(game.turn, self.name, self.model_name, "trade_response", accept_trade)

            # Save to history if enabled
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": accept_trade}
                ])

            # Return the decision we already determined
            if not will_accept and decision_result == "trade_rejected_unclear_response":
                print(f"Unclear response: '{accept_trade}', defaulting to NO")

            return will_accept

    ## Utility Functions
    def clean_trade_proposal(self, trade_proposal, grid=None, game=None):
        """
        Clean and validate a trade proposal:
        1. Make all strings uppercase and stripped
        2. Prevent trading with self
        3. Return None for invalid trades
        """
        # First clean the strings
        if isinstance(trade_proposal, dict):
            cleaned = {key: self.clean_trade_proposal(value, grid, game) for key, value in trade_proposal.items()}

            # Validate the cleaned proposal
            if game and game.players:
                # Prevent trading with self
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
            print(
                f"{self.name}, {other_player.name} is invoking 'pay for partner' and asking you to pay for their move onto a {color} tile.")
            while True:
                agree = input("Do you agree to this? y/n ").strip().lower()
                if agree not in ('y', 'n'):
                    print("Please enter 'y' or 'n'.")
                    continue
                return agree == 'y'
        else:
            # Prepare messages for this request
            system_prompt = self.system_prompt.format(player_name="you",
                                                      pay4partner_mode_info=self.pay4partner_mode_sys_prompt,
                                                      pay4partner_scoring_info=self.pay4partner_scoring_info)
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system",
                                                                                       "content": system_prompt}]
            current_messages.append({"role": "user", "content": message})

            # Log prompt to verbose logger
            user_prompt = message
            game.logger.log_player_prompt(game.turn, self.name, self.model_name, "pay4partner", system_prompt, user_prompt)

            # Make the API call
            agree = self.get_completion(current_messages)
            
            # Log response to verbose logger
            game.logger.log_player_response(game.turn, self.name, self.model_name, "pay4partner", agree)

            # Save to history if enabled
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": agree}
                ])

            final_response = get_last_alphabetic_word(agree)
            if "yes" in final_response or "accept" in final_response or "agree" in final_response:
                return True
            else:
                return False
    
    
    def generate_tile_level_contract_prompt(self, player_context):
        
        return prompts.generate_tile_level_contract_prompt(self.system_prompt, player_context)
    
    def generate_contract_for_finishing_prompt(self, player_context):
        
        return prompts.generate_contract_for_finishing_prompt(self.system_prompt, player_context)
    
    def get_completion(self, messages, max_completion_tokens=1000):
        if self.model_api == 'anthropic':
            try:
                system_prompt = ""
                for message in messages:
                    if message['role'] == 'system':
                        system_prompt += message['content'] + "\n"
                # Remove system messages from the list
                messages = [m for m in messages if m['role'] != 'system']   

                response = self.client.messages.create(model=self.model,
                                                    temperature=self.temperature,
                                                    messages=messages,
                                                    system=system_prompt,
                                                    max_tokens=max_completion_tokens)
                return response.content[0].text.strip().lower()
            except Exception as e:
                print(f"Error with Anthropic API: {e}")
                print(messages)
                raise e
        else:   
            response = self.client.chat.completions.create(model=self.model,
                                                           temperature=self.temperature,
                                                           messages=messages,
                                                           max_completion_tokens=max_completion_tokens)
            return response.choices[0].message.content.strip().lower()


