from collections import defaultdict, deque
from openai import OpenAI
from together import Together
import json
import re
from constants import GRID_SIZE, SURPLUS, DEFAULT_SYSTEM_PROMPT, OPENAI_API_KEY, TOGETHER_API_KEY, AVAILABLE_COLORS, TEMPERATURE
from grid import Grid


class Player:
    def __init__(self, color, n_players, model):
        self.n_total_players = n_players
        self.name = f"Player {color}"
        self.color = color
        self.start_pos = (0, 0)
        self.position = self.start_pos
        self.goal = (GRID_SIZE - 1, GRID_SIZE - 1)
        self.resources = defaultdict(int)
        self.model = model.value
        self.model_name = model.name
        self.model_api = model.api
        self.init_resources()


    def init_resources(self):
        self.resources[self.color] = round(SURPLUS * 2 * (GRID_SIZE - 1))

    def distance_to_goal(self):
        distance = abs(self.position[0] - self.goal[0]) + abs(self.position[1] - self.goal[1])
        return distance

    def can_move_to(self, new_pos, grid):
        if new_pos in grid.get_adjacent(self.position) and self.resources[grid.get_color(*new_pos)] > 0:
            return True
        return False

    def move(self, new_pos, grid):
        tile_color = grid.get_color(*new_pos)
        self.resources[tile_color] -= 1
        self.position = new_pos

    def best_route(self, grid):
        # n = len(grid)
        # target = (n - 1, n-1)  # bottom-left corner

        # BFS queue: (row, col, steps, collected_count, path)
        q = deque()
        q.append((self.position[0], self.position[1], 0, 0, [self.position]))

        best_path = None
        best_steps = float("inf")
        best_resources = -1

        visited = {}

        while q:
            r, c, steps, collected, path = q.popleft()

            # Count resource if it's the player's own
            if grid.get_color(r, c) == self.color:
                collected += 1

            # If we reached target
            if (r, c) == self.goal:
                if steps < best_steps or (steps == best_steps and collected > best_resources):
                    best_steps = steps
                    best_resources = collected
                    best_path = path
                continue

            # Avoid unnecessary revisits
            if (r, c) in visited:
                prev_steps, prev_collected = visited[(r, c)]
                if steps > prev_steps or (steps == prev_steps and collected <= prev_collected):
                    continue
            visited[(r, c)] = (steps, collected)

            # Explore neighbors
            for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                    q.append((nr, nc, steps + 1, collected, path + [(nr, nc)]))

        return best_path
    
    def generate_player_context_message(self, game, grid):
        """
        Generates a reusable message about the board state, player's resources, position, and goal.
        """
        return f"""
        Here is the board: {grid.tile_colors}
        The board state and everybody's resources: {game.game_state}. Specifically, as {self.name}, your resources are: {dict(self.resources)}, your current position is {self.position}, and your goal is {self.goal}. 

        Your best route is: {self.best_route(grid)}, although other routes may be possible. Note that this is in (x, y) coordinate format, not List access is [y][x] format!
        """


    def come_up_with_move(self, game, grid):
        if self.model_name == 'human':
            print(f"{self.name}, it's your turn to make a move.")
            while True:
                move = input("Input the coordinates of where you'd like to move to in (x, y) format. Otherwise type 'n': ").strip().lower()
                if move == 'n':
                    return None
                try:
                    x, y = map(int, move.strip("()").split(","))
                    new_pos = (x, y)
                    if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
                        print("Invalid move: The position is out of bounds. Try again.")
                        continue
                    if new_pos not in grid.get_adjacent(self.position):
                        print("Invalid move: You can only move to an adjacent tile. Try again.")
                        continue
                    tile_color = grid.get_color(x, y)
                    if self.resources[tile_color] <= 0:
                        print(f"Invalid move: You don't have enough resources for a {tile_color} tile. Try again.")
                        continue
                    return new_pos
                except (ValueError, IndexError):
                    print("Invalid input: Please enter the coordinates in (x, y) format. Try again.")
        else:
            user_message = self.generate_player_context_message(game, grid) + """
                    
                    Output your next move in the format (x, y) where x and y are the coordinates of the tile you want to move to. If you do not want to move, say exactly: "n". Don't include any other information. Your next move should be one tile away from your current position, and you must have enough resources to pay for the tile you are moving to.
                    """
            print(user_message)
            if self.model_api == 'open_ai':
                client = OpenAI(api_key=OPENAI_API_KEY)
            elif self.model_api == 'together':
                client = Together(api_key=TOGETHER_API_KEY)
            response = client.chat.completions.create(
                model=self.model,
                temperature=TEMPERATURE,
                messages=[{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
                max_completion_tokens=1000)
            move = response.choices[0].message.content.strip().lower()
            print(f"{self.name} proposed a move: {move}")
            
            if move == 'n':
                return None
            try:
                x, y = map(int, move.strip("()").split(","))
                new_pos = (x, y)
                print(f"color of tile at new position: {grid.get_color(*new_pos)}")
                if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
                    print("Invalid move: The position is out of bounds.")
                    return None
                if new_pos not in grid.get_adjacent(self.position):
                    print("Invalid move: You can only move to an adjacent tile.")
                    return None
                tile_color = grid.get_color(x, y)
                if self.resources[tile_color] <= 0:
                    print(f"Invalid move: You don't have enough resources for a {tile_color} tile.")
                    return None
                return new_pos
            except (ValueError, IndexError):
                return None

    def propose_trade(self, grid, game):
        if self.model_name == 'human':
            print(f"{self.name}, it's your turn to propose a trade.")
            make_trade = input("Do you want to make a trade? y/n ").strip().lower()
            if make_trade != 'y':
                return None

            def get_valid_player(prompt):
                while True:
                    value = input(prompt).strip().lower()
                    if value:
                        if value == self.name.lower():
                            print("You cannot trade with yourself. Please enter a different player name")
                        elif value in [p.name.lower() for p in game.players]:
                            return value
                        else:
                            print("Please enter a valid player name in the format 'Player <color>'. If you do not want to trade, type 'n'.")

            def get_valid_resource(prompt):
                while True:
                    value = input(prompt).strip().lower()
                    if value in AVAILABLE_COLORS:
                        return value
                    else:
                        print("Please enter a valid resource color. If you do not want to trade, type 'n'.")

            def get_int(prompt):
                while True:
                    value = input(prompt).strip()
                    try:
                        return int(value)
                    except ValueError:
                        print("Please enter a valid integer. If you do not want to trade, type 'n'.")

            player_to_trade_with = get_valid_player("Trade with Player: ")
            if player_to_trade_with == 'n':
                return None
            resource_to_offer_to_other_player = get_valid_resource("Resource to offer (color): ")
            if resource_to_offer_to_other_player == 'n':
                return None
            quantity_to_offer_to_other_player = get_int("Quantity to offer (int): ")
            if resource_to_offer_to_other_player not in self.resources or self.resources[resource_to_offer_to_other_player] <= 0:
                print(f"You do not have enough {resource_to_offer_to_other_player} to offer. Please try again.")
                return None
            resource_to_receive_from_other_player = get_valid_resource("Resource to receive (color): ")
            if resource_to_receive_from_other_player == 'n':
                return None
            quantity_to_receive_from_other_player = get_int("Quantity to receive (int): ")
            if quantity_to_receive_from_other_player == 'n':
                return None

            trade_proposal = {
                "trade_proposer": self.name,
                "player_to_trade_with": player_to_trade_with,
                "resource_to_offer_to_other_player": resource_to_offer_to_other_player,
                "quantity_to_offer_to_other_player": quantity_to_offer_to_other_player,
                "resource_to_receive_from_other_player": resource_to_receive_from_other_player,
                "quantity_to_receive_from_other_player": quantity_to_receive_from_other_player
            }

            return trade_proposal

        else:
            user_message = self.generate_player_context_message(game, grid) + """
                
                Your task:
                1. Consider any trades you could make along the way to reach your goal.
                2. Propose at most **one trade** with another player that would help you reach your goal. Note that trades are more likely to be accepted if they are mutually beneficial.
                
                After considering your options, respond with a valid JSON object that matches this schema:
                {{
                "player_to_trade_with": "string (name of player or 'n' if no trade)",
                "resource_to_offer_to_other_player": "string (color name)",
                "quantity_to_offer_to_other_player": integer,
                "resource_to_receive_from_other_player": "string (color name)",
                "quantity_to_receive_from_other_player": integer
                }}

                - If you don't want or need to trade to reach your goal, say exactly: "n".

                Keep your response below 1000 characters.
                """
            if self.model_api == 'open_ai':
                client = OpenAI(api_key=OPENAI_API_KEY)
            elif self.model_api == 'together':
                client = Together(api_key=TOGETHER_API_KEY)

            response = client.chat.completions.create(
                model=self.model,
                temperature=TEMPERATURE,
                messages=[{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
                max_completion_tokens=2000)
            trade_proposal = response.choices[0].message.content.strip().lower()
            print(f"{self.name} proposed a trade: {trade_proposal}")
            if trade_proposal != 'n':
                print("Attempting to parse trade proposal as JSON...")
                try:
                    match = re.search(r"\{.*\}", trade_proposal, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        try:
                            trade_proposal = json.loads(json_str)
                            trade_proposal['trade_proposer'] = self.name
                            print("Extracted dictionary:", trade_proposal)
                        except json.JSONDecodeError as e:
                            print("Invalid JSON:", e)
                            trade_proposal = None
                #     trade_proposal['trade_proposer'] = self.name
                # except json.JSONDecodeError:
                #     print("⚠️ Could not parse trade proposal as JSON.")
                #     trade_proposal = None
                #     trade_proposal = json.loads(trade_proposal)
                #     trade_proposal['trade_proposer'] = self.name
                except json.JSONDecodeError:
                    print("⚠️ Could not parse trade proposal as JSON.")
                    trade_proposal = None
            else:
                trade_proposal = None
            return trade_proposal

    def accept_trade(self, grid, game, trade):
        if self.model_name == 'human':
            print(f"{self.name}, You have been approached for the above trade.")
            accept_trade = input("Do you accept this trade? y/n").strip().lower()
            if accept_trade == 'y':
                return True
            else:
                return False
        else:
            trade_proposer = trade['trade_proposer']
            player_to_trade_with = trade['player_to_trade_with']
            resource_to_offer_to_other_player = trade['resource_to_offer_to_other_player']
            quantity_to_offer_to_other_player = trade['quantity_to_offer_to_other_player']
            resource_to_receive_from_other_player = trade['resource_to_receive_from_other_player']
            quantity_to_receive_from_other_player = trade['quantity_to_receive_from_other_player']
            
            user_message = self.generate_player_context_message(game, grid) + f"""
            
            Consider the following trade proposal: {trade_proposer} is offering you {quantity_to_offer_to_other_player} of color {resource_to_offer_to_other_player} in exchange for you giving them {quantity_to_receive_from_other_player} of color {resource_to_receive_from_other_player}.
            Trades often help you to reach your goal. Does this trade help you reach your goal? Briefly consider the resources you will need to reach your goal, and finish your answer with a "yes" or "no". The last word of your response should be either "yes" or "no".
            Keep your response below 1000 characters.
            """
            if self.model_api == 'open_ai':
                client = OpenAI(api_key=OPENAI_API_KEY)
            elif self.model_api == 'together':
                client = Together(api_key=TOGETHER_API_KEY)

            response = client.chat.completions.create(
                model=self.model,
                temperature=TEMPERATURE,
                messages=[{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
                max_completion_tokens=1000)
            accept_trade = response.choices[0].message.content.strip().lower()
            print(f"Trade proposal message: {user_message}")
            print(f"{self.name} responded to the trade proposal: {accept_trade}")
            if 'yes' in accept_trade[-5:]:
                return True
            elif 'no' in accept_trade[-5:]:
                return False
            elif 'y' in accept_trade[-3:]:
                return True
            else:
                return False

    def has_finished(self):
        return self.position == self.goal