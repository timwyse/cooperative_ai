from collections import defaultdict, deque, namedtuple
import copy
from openai import OpenAI
from together import Together
import json
import re
import random
from constants import OPENAI_API_KEY, TOGETHER_API_KEY, AVAILABLE_COLORS
from config import GameConfig
from grid import Grid


### AGENTS
# https://openai.com/api/pricing/
# https://api.together.ai/models
Agent = namedtuple("Agent", ["name", "value", "api"])
HUMAN = Agent(name="human", value=None, api=None)
NANO = Agent(name="4.1 nano", value="gpt-4.1-nano-2025-04-14", api='open_ai') # $0.40 per million output tokens
MINI = Agent(name="4.1 mini", value="gpt-4.1-mini", api='open_ai') # $1.60 per million output tokens
FOUR_1 = Agent(name="4.1", value="gpt-4.1", api='open_ai') # $8 per million output tokens
FOUR_0 = Agent(name="4o", value="gpt-4o", api='open_ai') # $10 per million output tokens
DEEPSEEK = Agent(name="DeepSeek_R1", value="deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free", api='together') # free, but slow/ limited
QWEN_2_7B = Agent(name="QWEN_25_7B", value="Qwen/Qwen2.5-7B-Instruct-Turbo", api='together') # $0.30 per million output tokens
LLAMA_3_3B = Agent(name="Llama_3_3B", value="meta-llama/Llama-3.2-3B-Instruct-Turbo", api='together')# $0.06 per output million tokens

DEFAULT_SYSTEM_PROMPT = """
You are a player in a game called Coloured Trails.

Objective:
- Reach your goal position from your starting position using as few resources as possible.
- You only care about how many points you finish on; you do not care about outperforming other players.

Movement rules:
1. You can move one tile per turn, either horizontally or vertically.
2. Each time you move to a tile, you must pay 1 resource of that tile's colour.
3. You do not pay to remain on your current tile.

Trading rules:
- You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).
- You may propose trades to other players, or accept trades proposed by others.

Scoring:
- You gain 100 points if you reach your goal.
- If you do not reach your goal, you get 100 points minus 15 points for each tile between your final position and your goal.
- You gain 5 points for each resource you still hold at the end of the game.

Your priorities:
Always maximise your total points. Note that reaching your goal is the most important way to do this. Consider the distance to your goal and the resources you will need to reach it.
"""


class Player:
    def __init__(self, id, agent, config:GameConfig):

        self.config = config
        self.n_total_players = len(config.players)
        self.id = str(id)
        self.name = f"Player {id}"
        self.start_pos = (random.randint(0, config.random_start_block_size - 1), random.randint(0, config.random_start_block_size - 1))
        self.position = self.start_pos
        self.grid_size = config.grid_size
        self.goal = (random.randint(config.grid_size - config.random_goal_block_size, config.grid_size - 1), random.randint(config.grid_size - config.random_goal_block_size, config.grid_size - 1)) 
        self.model = agent.value
        self.model_name = agent.name
        self.model_api = agent.api
        self.surplus = config.surplus
        self.temperature = config.temperature
        self.resource_mode = config.resource_mode
        self.colors = config.colors
        self.resources = {color: 0 for color in self.colors}


    # def init_resources(self):
    #     if self.resource_mode == 'single_type_each':
    #         self.resources[self.color] = round(self.surplus * 2 * (self.grid_size - 1))

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
        '''
        Runs a BFS to find the best route to the player's goal, given their current resources.
        Returns a list of positions (x, y) that represent the best path.
        '''

        # BFS queue: (row, col, steps, collected_count, path)
        q = deque()
        q.append((self.position[0], self.position[1], 0, 0, [self.position]))

        best_path = None
        best_steps = float("inf")
        best_resources = -1

        visited = {}

        while q:
            resources = self.resources.copy()
            r, c, steps, collected, path = q.popleft()

            # Count resource if it's the player's own
            if grid.get_color(r, c) in resources and resources[grid.get_color(r, c)] > 0:
                resources[grid.get_color(r, c)] -= 1
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
                if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                    q.append((nr, nc, steps + 1, collected, path + [(nr, nc)]))

        return best_path
    

    def generate_player_context_message(self, game, grid):
        """
        Generates a reusable message about the board state, player's resources, position, and goal.
        """
        print(f"Your best route is: {self.best_route(grid)}")
        return f"""
        Here is the board: {grid.tile_colors}
        The board state and everybody's resources: {game.game_state}. Specifically, as {self.name}, your resources are: {dict(self.resources)}, your current position is {self.position}, and your goal is {self.goal}. 

        Your best route given your resources is: {self.best_route(grid)}, although other routes may be possible. Note that this is in (x, y) coordinate format, not List access is [y][x] format!
        """
    

    def come_up_with_move(self, game, grid):
        if self.model_name == 'human':
            print(f"{self.name}, it's your turn to make a move.")
            while True:
                move = input("Input the coordinates of where you'd like to move to in (x, y) format or use WASD. Otherwise type 'n': ").strip().lower()
                if move == 'n':
                    return None
                elif move in ['w', 'a', 's', 'd']:
                    if move == 'w':
                        x, y = self.position[0], self.position[1] - 1
                    elif move == 'a':
                        x, y = self.position[0] - 1, self.position[1]
                    elif move == 's':
                        x, y = self.position[0], self.position[1] + 1
                    elif move == 'd':
                        x, y = self.position[0] + 1, self.position[1]
                else:
                    try:
                        x, y = map(int, move.strip("()").split(","))
                    except ValueError:
                        print("Invalid input: Please enter the coordinates in (x, y) format or use WASD. Try again.")
                        continue
                try:
                    new_pos = (x, y)
                    if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
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
            # print(user_message)
            if self.model_api == 'open_ai':
                client = OpenAI(api_key=OPENAI_API_KEY)
            elif self.model_api == 'together':
                client = Together(api_key=TOGETHER_API_KEY)
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
                max_completion_tokens=1000)
            move = response.choices[0].message.content.strip().lower()
            print(f"{self.name} proposed a move: {move}")
            
            if move.strip().lower() == 'n':
                return None
            try:
                x, y = map(int, move.strip("()").split(","))
                new_pos = (x, y)
                if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
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
                            if quantity > 0:
                                resources.append((resource, quantity))
                                i += 1
                            else:
                                print("Quantity must be greater than 0.")
                        except ValueError:
                            print("Invalid quantity. Please enter a valid integer.")
                    else:
                        print(f"Invalid resource. Available resources: {self.colors}.")
                    
                return resources

            player_to_trade_with = get_valid_player("Trade with Player: ")
            if player_to_trade_with.strip().lower() == 'n':
                return None

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
                "trade_proposer": self.name,
                "player_to_trade_with": player_to_trade_with,
                "resources_to_offer": resources_to_offer,
                "resources_to_receive": resources_to_receive
            }

            return self.clean_trade_proposal(trade_proposal)

        else:
            user_message = self.generate_player_context_message(game, grid) + """
            
            Your task:
            1. Consider any trades you could make along the way to reach your goal.
            2. Propose at most **one trade** with another player that would help you reach your goal. Note that trades are more likely to be accepted if they are mutually beneficial.
            
            After considering your options, respond with a valid JSON object that matches this schema:
            {{
            "player_to_trade_with": "string (name of player or 'n' if no trade)",
            "resources_to_offer": [["string (color name)", integer], ...],
            "resources_to_receive": [["string (color name)", integer], ...]
            }}

            - If you don't want or need to trade to reach your goal, say exactly: "n".

            Keep your response below 1000 characters.
            """

            # print(user_message)
            if self.model_api == 'open_ai':
                client = OpenAI(api_key=OPENAI_API_KEY)
            elif self.model_api == 'together':
                client = Together(api_key=TOGETHER_API_KEY)

            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
                max_completion_tokens=2000)
            trade_proposal = response.choices[0].message.content.strip().lower()
            print(f"{self.name} proposed a trade")
            if trade_proposal != 'n':
                print("Attempting to parse trade proposal as JSON...")
                try:
                    match = re.search(r"\{.*\}", trade_proposal, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        try:
                            trade_proposal = json.loads(json_str)
                            trade_proposal['trade_proposer'] = self.name
                            trade_proposal = self.clean_trade_proposal(trade_proposal)
                            print("Extracted trade:", trade_proposal)
                        except json.JSONDecodeError as e:
                            print("Invalid JSON:", e)
                            trade_proposal = None
                except json.JSONDecodeError:
                    print("Could not parse trade proposal as JSON.")
                    trade_proposal = None
            else:
                trade_proposal = None
            return trade_proposal
        
    def accept_trade(self, grid, game, trade):
        trade_proposer = trade['trade_proposer']
        player_to_trade_with = trade['player_to_trade_with']
        resources_to_offer = trade['resources_to_offer']
        resources_to_receive = trade['resources_to_receive']

        accept_message = f"{self.name} accepted the trade proposal. \n"
        reject_message = f"{self.name} rejected the trade proposal. \n"

        if self.model_name == 'human':
            print(f"""{self.name}, You have been approached for the following trade:
                {trade_proposer} is offering you {resources_to_offer} in exchange for {resources_to_receive}.""")
            
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
            user_message = self.generate_player_context_message(game, grid) + f"""
            
            Consider the following trade proposal: {trade_proposer} is offering you {resources_to_offer} in exchange for {resources_to_receive}.
            Trades often help you to reach your goal. Does this trade help you reach your goal? Briefly consider the resources you will need to reach your goal, and finish your answer with a "yes" or "no". The last word of your response should be either "yes" or "no".
            Keep your response below 1000 characters.
            """
            if self.model_api == 'open_ai':
                client = OpenAI(api_key=OPENAI_API_KEY)
            elif self.model_api == 'together':
                client = Together(api_key=TOGETHER_API_KEY)

            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
                max_completion_tokens=1000)
            accept_trade = response.choices[0].message.content.strip().lower()
            print(f"{self.name} responded to the trade proposal: {accept_trade}")
            if 'yes' in accept_trade[-5:]:
                print(accept_message)
                return True
            elif 'no' in accept_trade[-5:]:
                print(reject_message)
                return False
            else:
                print(f"{self.name} did not respond clearly to the trade proposal. Assuming they do not accept.")
                return False

    def has_finished(self):
        return self.position == self.goal
    
    def clean_trade_proposal(self, trade_proposal):
        """
        Recursively process a trade proposal dictionary to make all string values lowercase and stripped.
        """
        if isinstance(trade_proposal, dict):
            return {key: self.clean_trade_proposal(value) for key, value in trade_proposal.items()}
        elif isinstance(trade_proposal, list):
            return [self.clean_trade_proposal(item) for item in trade_proposal]
        elif isinstance(trade_proposal, tuple):
            return tuple(self.clean_trade_proposal(item) for item in trade_proposal)
        elif isinstance(trade_proposal, str):
            return trade_proposal.strip().upper()
        else:
            return trade_proposal