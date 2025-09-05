from collections import defaultdict, deque, namedtuple, Counter
import copy
import json
import random
import re

from openai import OpenAI
from together import Together

from config import GameConfig
from constants import OPENAI_API_KEY, TOGETHER_API_KEY, AVAILABLE_COLORS
from grid import Grid

class Player:
    def __init__(self, id, agent, logger, config:GameConfig):

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
        else:
            self.client = None

        self.start_pos = (random.randint(0, config.random_start_block_size - 1), random.randint(0, config.random_start_block_size - 1))
        self.goal = (random.randint(config.grid_size - config.random_goal_block_size, config.grid_size - 1), random.randint(config.grid_size - config.random_goal_block_size, config.grid_size - 1)) 
        self.position = self.start_pos
        
        self.n_total_players = len(config.players)
        
        self.surplus = config.surplus
        self.grid_size = config.grid_size
        self.resource_mode = config.resource_mode
        self.colors = config.colors
        self.resources = {color: 0 for color in self.colors}
        self.promised_resources_to_give = {color: 0 for color in self.colors}
        self.promised_resources_to_receive = {color: 0 for color in self.colors}

        # init pay4partner settings
        self.pay4partner = config.pay4partner
        self.pay4partner_log = []
        self.pay4partner_scoring_info = "In 'pay for other' mode, any resources you have promised to give to other players as part of trade agreements are still counted as your resources (and hence potential contributors to your final score) until you actually give them away." if self.pay4partner else ""
        self.pay4partner_mode_sys_prompt = self.generate_pay4partner_mode_info(short_summary=True) if self.pay4partner else ""

        # Init message history settings
        self.with_message_history = config.with_message_history
        self.messages = [{"role": "system", "content": self.system_prompt.format(player_name=self.name, pay4partner_mode_info=self.pay4partner_mode_sys_prompt, pay4partner_scoring_info=self.pay4partner_scoring_info)}] if self.with_message_history else []

    ## Core Gameplay
    def distance_to_goal(self):
        distance = abs(self.position[0] - self.goal[0]) + abs(self.position[1] - self.goal[1])
        return distance


    def can_move_to(self, new_pos, grid):
        if new_pos in grid.get_adjacent(self.position) and self.resources[grid.get_color(*new_pos)] > 0:
            return True
        return False

    def can_move_to_with_promised(self, new_pos, grid):
        if new_pos in grid.get_adjacent(self.position) and self.promised_resources_to_receive[grid.get_color(*new_pos)] > 0:
            return True
        return False

    def move(self, new_pos, grid):
        tile_color = grid.get_color(*new_pos)
        self.resources[tile_color] -= 1
        self.position = new_pos

    def has_finished(self):
        return self.position == self.goal


    ## Pathfinding and Strategy

    def best_routes(self, grid, top_n=3):
        """
        Runs a BFS to find the top n paths to the player's goal, given their current resources.
        Path ranking is based on:
        1. Resource shortfall (ascending): the number of resources the player
           would still need to trade for or acquire to complete the path.
        2. Path length (ascending): among paths with the same shortfall,
           shorter paths are preferred.

        Example:
        Suppose there are 5 paths:
        a. 5 steps, player has all 5 required resources
        b. 5 steps, player has 4/5 required resources
        c. 6 steps, player has all 6 required resources
        d. 5 steps, player has 3/5 required resources
        e. 6 steps, player has 5/6 required resources

        Sorted order: a, c, b, e, d. With top_n=3 → returns [a, c, b]
        Note that the LM Agent isn't told this ranking explicitly, just that these are some good paths.
        """
        def _neighbors(pos, rows, cols):
            r, c = pos
            nbrs = []
            if r > 0: nbrs.append((r-1, c))
            if r < rows-1: nbrs.append((r+1, c))
            if c > 0: nbrs.append((r, c-1))
            if c < cols-1: nbrs.append((r, c+1))
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

        def top_n_paths( grid, start, goal, resources, n):
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
            scored.sort(key=lambda x: (sum(x["resources_missing_due_to_insufficient_inventory"].values()), x["path_length_in_steps"]))
            return scored[:n]

        best = top_n_paths(grid, self.position, self.goal, self.resources, n=top_n)  
        
        return best


    def format_turn_summary(self, turn_summary, turn_number):
        """Format turn summary focusing only on trades, moves, and positions"""
        summary = [f"\n=== TURN {turn_number} ==="]
        
        # Trades
        if turn_summary["trades"]:
            for trade in turn_summary["trades"]:
                summary.append(f"{trade['proposer']} proposed trade to {trade['target']}:")
                summary.append(f"- {trade['proposer']} offered: {trade['offered']}")
                summary.append(f"- {trade['proposer']} requested: {trade['requested']}")
                if trade.get("success", False):
                    summary.append(f"{trade['target']} ACCEPTED the trade")
                elif trade.get("rejected", False):
                    summary.append(f"{trade['target']} REJECTED the trade")
        
        # Moves
        for move in turn_summary["moves"]:
            if move["success"]:
                summary.append(f"MOVE: {move['player']} moved from {move['from_pos']} to {move['to_pos']}")
            else:
                if move["reason"] == "no_move":
                    summary.append(f"MOVE: {move['player']} did not move")
        
        # End positions
        summary.append("\nPOSITIONS:")
        for player_name, state in turn_summary["player_states"].items():
            status = "FINISHED!" if state['has_finished'] else f"at {state['position']}"
            summary.append(f"- {player_name}: {status}, resources: {state['resources']}")
            if self.pay4partner:
                summary.append(f"  - promised to give: {state['promised_to_give']}")
                summary.append(f"  - promised to receive: {state['promised_to_receive']}")

        
        return "\n".join(summary)

    def generate_player_context_message(self, game, grid):
        """
        Generates a reusable message about the board state, player's resources, position, and goal.
        Also includes recent turn history for context.
        """
        # Get recent turn history (last 3 turns) if context is enabled
        recent_history = ""
        if game.with_context and game.turn_summaries:
            history_entries = []
            recent_turns = game.turn_summaries[-3:]  # Get last 3 turns TODO: decide if this is configurable
            for turn_idx, turn in enumerate(recent_turns):
                turn_num = game.turn - (len(recent_turns) - turn_idx)
                history_entries.append(self.format_turn_summary(turn, turn_num))
            
            recent_history = "\nRecent turn history:\n" + "\n---\n".join(history_entries)

        current_turn = game.turn
        promised_resources_to_give_message = f"- Resources you have promised to give to other players (note they're still yours, you haven't yet given them away): {self.promised_resources_to_give}" if self.pay4partner else ''
        promised_resources_to_receive_message = f"- Resources you have been promised to receive from other players (note they're still theirs, you haven't received them yet): {self.promised_resources_to_receive}" if self.pay4partner else ''
        
        return f"""
=== GAME STATUS FOR {self.name} - TURN {current_turn} ===

YOUR CURRENT STATUS:
- You are at position {self.position}
- Your goal is at {self.goal}
- Your resources: {dict(self.resources)}
{promised_resources_to_give_message}
{promised_resources_to_receive_message}
- Distance to goal: {self.distance_to_goal()} steps

BOARD LAYOUT:
{grid.lm_readable}

HISTORY OF EVENTS:
{recent_history if recent_history else "This is the first turn."}

OTHER PLAYERS' STATUS:
{chr(10).join(f"- {name}: at {state['position']}, has {state['resources']}" for name, state in game.game_state.items() if name != self.name)}
"""
    def generate_pay4partner_mode_info(self, short_summary=False):
        if self.pay4partner:
            promised_resources_to_receive = {color: amt for color, amt in self.promised_resources_to_receive.items() if amt > 0}
            promised_resources_to_give = {color: amt for color, amt in self.promised_resources_to_give.items() if amt > 0}
            pay4partner_mode_info = """
Important Note: The game is in 'pay for other' mode. This means that trades are not made by directly swapping resources. Instead, when a trade agreement is reached, each player commits to covering the cost of the other’s movement on the agreed tile colors. In practice:
	•	If the other player steps onto a tile of a color you agreed to cover, you pay the resource cost for that move.
	•	If you step onto a tile of a color the other player agreed to cover, they pay the resource cost for you.
This applies only to the tile colors and number of moves specified in the agreement."""
            if short_summary:
                return pay4partner_mode_info
            else:
                pay4partner_mode_info += f"""
In addition to the information above, consider any promises you're already involved in:
\n- So far you have promised to give these resources to other players: {promised_resources_to_give if promised_resources_to_give else '{}'}"
\n- So far you have been promised to receive these resources from other players: {promised_resources_to_receive if promised_resources_to_receive else '{}'}
In order to move onto a tile of a color you have been promised, select that move as normal and the other player will be asked to cover the cost for you.
"""
            return pay4partner_mode_info
        else:
            return ""
    
    ## Decision-Making

    def come_up_with_move(self, game, grid):
        if self.model_name == 'human':
            print(f"{self.name}, it's your turn to make a move.")
            while True:
                move = input("Enter your move: type row and column as 'row,col' (e.g., 2,1 to move to row 2 column 1. Note that rows and columns are 0-indexed), or use W/A/S/D for directions, or type 'n' to skip: ").strip().lower()
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
                    tile_color = grid.get_color(r, c)
                    if (tile_color not in self.resources.keys() or self.resources[tile_color] <= 0) and (tile_color not in self.promised_resources_to_receive.keys() or self.promised_resources_to_receive[tile_color]) <= 0:
                        print(f"Invalid move: You don't have enough resources for a {tile_color} tile. Try again.")
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
            user_message = self.generate_player_context_message(game, grid) + f"""
                    
Choose your next move:

1. Look at the best path from your current position {self.position} to your goal {self.goal}:
   - Next move in best path: {next_move}

   - Resources needed for path: {resources_needed}

   - Your current resources: {dict(self.resources)}
   - Required resources for entire path: {str(self.best_routes(grid)[0]["resources_required_for_path"])}
   - Missing resources to complete the entire path: {str(self.best_routes(grid)[0]["resources_missing_due_to_insufficient_inventory"])} 
   
Important: You can still make individual moves if you have the required resource for that specific tile.
   
   {self.generate_pay4partner_mode_info()}

2. For your NEXT MOVE to {next_move}:
   - Check what color tile {next_move} is on the board
   - Check if you have at least 1 resource of that color
   - If YES: you can make this move now
   - If NO: try a different adjacent move toward your goal

3. Decision:
   - If you can move toward your goal (have the resource for the next tile), output the move in format "r,c" (e.g. "1,2")
   - If you cannot make ANY valid move toward your goal, output exactly: "n"

Remember:
- You only need 1 resource of the tile's color to move to that tile
- Missing resources for the entire path doesn't prevent you from making individual moves
- Try to move toward your goal even if you can't complete the entire journey yet
"""
            # Prepare messages for this request
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system", "content": self.system_prompt.format(player_name=self.name, pay4partner_mode_info=self.pay4partner_mode_sys_prompt, pay4partner_scoring_info=self.pay4partner_scoring_info)}]
            current_messages.append({"role": "user", "content": user_message})
            
            # Log full context to yulia logs
            game.yulia_logger.log("player_context", {
                "player": self.name,
                "turn": game.turn,
                "decision_type": "move",
                "full_context": current_messages,
                "context_summary": {
                    "total_messages": len(current_messages),
                    "system_messages": len([m for m in current_messages if m["role"] == "system"]),
                    "user_messages": len([m for m in current_messages if m["role"] == "user"]),
                    "assistant_messages": len([m for m in current_messages if m["role"] == "assistant"])
                }
            })
            
            self.logger.log("move_prompt", {"player": self.name, "message": user_message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=current_messages,
                max_completion_tokens=1000)
            move = response.choices[0].message.content.strip().lower()
            
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": move}
                ])
            self.logger.log("move_proposal", {"player": self.name, "message": move})
            print(f"{self.name} proposed a move: {move}")
            

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
                r, c = extract_move(move)
                new_pos = (r, c)
                if not (0 <= r < self.grid_size and 0 <= c < self.grid_size):
                    print("Invalid move: The position is out of bounds.")
                    return None
                if new_pos not in grid.get_adjacent(self.position):
                    print("Invalid move: You can only move to an adjacent tile.")
                    return None
                tile_color = grid.get_color(r, c)
                if (tile_color not in self.resources.keys() or self.resources[tile_color] <= 0) and (tile_color not in self.promised_resources_to_receive.keys() or self.promised_resources_to_receive[tile_color]) <= 0:
                    print(f"Invalid move: You don't have enough resources for a {tile_color} tile.")
                    return None
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

            return self.clean_trade_proposal(trade_proposal, grid)

        # LLM Player
        else:
            user_message = self.generate_player_context_message(game, grid) + """
            
IMPORTANT: First check if you need to trade at all:

1. Look at your best paths above. For the shortest path:

   - Required resources: """ + str(self.best_routes(grid)[0]["resources_required_for_path"]) + """
   YOUR CURRENT RESOURCES: """ + str(dict(self.resources)) + """
   - Required resources not currently in your possession: """ + str(self.best_routes(grid)[0]["resources_missing_due_to_insufficient_inventory"]) + """

""" + self.generate_pay4partner_mode_info() + """

2. If you have NO missing resources (empty dict {} above), respond with exactly: "n"

   If you have enough resources to reach your goal, say "n"

3. Only if you are missing resources, consider a trade:
   - You can ONLY request resources you're missing
   - You can ONLY offer resources you have in excess
   - NEVER trade with yourself """ + str(self.name) + """
   - NEVER offer 0 resources
   - NEVER request resources you already have enough of
   - Make the trade beneficial for both players

Respond in ONE of these two formats:

1. If you want to make a trade, use EXACTLY this JSON format (replace values in <>):
{
  "player_to_trade_with": "<other player's name>",
  "resources_to_offer": [["<color>", <number>]],
  "resources_to_receive": [["<color>", <number>]]
}

Example of valid trade:
{
  "player_to_trade_with": "Player 1",
  "resources_to_offer": [["R", 3]],
  "resources_to_receive": [["B", 2]]
}

2. If you don't want to trade, respond with exactly: n

Remember:
- Use EXACTLY the format shown above
- Only ONE resource pair in each array
- No spaces in color names
- Numbers must be > 0
- Don't trade with yourself """ + str(self.name) + """

Keep your response below 1000 characters.
"""

            # Prepare messages for this request
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system", "content": self.system_prompt.format(player_name=self.name, pay4partner_mode_info=self.pay4partner_mode_sys_prompt, pay4partner_scoring_info=self.pay4partner_scoring_info)}]
            current_messages.append({"role": "user", "content": user_message})
            
            # Log full context to yulia logs
            game.yulia_logger.log("player_context", {
                "player": self.name,
                "turn": game.turn,
                "decision_type": "trade_proposal",
                "full_context": current_messages,
                "context_summary": {
                    "total_messages": len(current_messages),
                    "system_messages": len([m for m in current_messages if m["role"] == "system"]),
                    "user_messages": len([m for m in current_messages if m["role"] == "user"]),
                    "assistant_messages": len([m for m in current_messages if m["role"] == "assistant"])
                }
            })
            
            self.logger.log("trade_prompt", {"player": self.name, "message": user_message})
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=current_messages,
                max_completion_tokens=2000)
            trade_proposal = response.choices[0].message.content.strip().lower()
            
            # Save to history if enabled
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": trade_proposal}
                ])
            self.logger.log("trade_proposal", {"player": self.name, "message": trade_proposal})
            if trade_proposal == 'n':
                return None
            
            print(f"\n{self.name} proposes trade:")
            try:
                match = re.search(r"\{.*\}", trade_proposal, re.DOTALL)
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
                        
                        trade_proposal['trade_proposer'] = self.name
                        cleaned = self.clean_trade_proposal(trade_proposal, grid)
                        if cleaned:
                            trade_proposal = cleaned
                            print(f"- To: {trade_proposal['player_to_trade_with']}")
                            print(f"- Offering: {trade_proposal['resources_to_offer']}")
                            print(f"- Requesting: {trade_proposal['resources_to_receive']}")
                        else:
                            print("- Invalid trade proposal")
                    except json.JSONDecodeError as e:
                        print("Invalid JSON:", e)
                        trade_proposal = None
            except Exception as e:
                print(f"Error parsing trade proposal: {e}")
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
            # Simple trade acceptance prompt
            user_message = self.generate_player_context_message(game, grid) + f"""
You have been offered a trade:
{trade_proposer} wants to give you {resources_to_offer} in exchange for {resources_to_receive}. {self.generate_pay4partner_mode_info(short_summary=True)}
Do you accept this trade? Think about your options and then answer 'yes' or 'no'. Make sure the last word of your response is exactly 'yes' or 'no'."""

            # Prepare messages for this request
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system", "content": self.system_prompt.format(player_name=self.name, pay4partner_mode_info=self.pay4partner_mode_sys_prompt, pay4partner_scoring_info=self.pay4partner_scoring_info)}]
            current_messages.append({"role": "user", "content": user_message})
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=current_messages,
                max_completion_tokens=1000)
            accept_trade = response.choices[0].message.content.strip().lower()
            
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
            
            # Log full context with actual decision made
            game.yulia_logger.log("player_context", {
                "player": self.name,
                "turn": game.turn,
                "decision_type": decision_result,
                "full_context": current_messages,
                "ai_response": accept_trade,
                "context_summary": {
                    "total_messages": len(current_messages),
                    "system_messages": len([m for m in current_messages if m["role"] == "system"]),
                    "user_messages": len([m for m in current_messages if m["role"] == "user"]),
                    "assistant_messages": len([m for m in current_messages if m["role"] == "assistant"])
                }
            })
            
            # Save to history if enabled
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": accept_trade}
                ])
            
            self.logger.log("accept_trade_response", {"player": self.name, "message": accept_trade})
            
            # Return the decision we already determined
            if not will_accept and decision_result == "trade_rejected_unclear_response":
                print(f"Unclear response: '{accept_trade}', defaulting to NO")
            
            return will_accept

    
    ## Utility Functions
    def clean_trade_proposal(self, trade_proposal, grid=None):
        """
        Clean and validate a trade proposal:
        1. Make all strings uppercase and stripped
        2. Prevent trading with self
        3. Check if trade is needed (have enough resources)
        4. Return None for invalid trades
        """
        # First clean the strings
        if isinstance(trade_proposal, dict):
            cleaned = {key: self.clean_trade_proposal(value, grid) for key, value in trade_proposal.items()}
            
            # Validate the cleaned proposal
            if cleaned.get('trade_proposer') and cleaned.get('player_to_trade_with'):
                # Prevent trading with self
                if cleaned['trade_proposer'].upper() == cleaned['player_to_trade_with'].upper():
                    print(f"Invalid trade: {cleaned['trade_proposer']} cannot trade with themselves")
                    return None
                
                # Check if we need to trade at all (only if grid is provided)
                if grid:
                    best_path = self.best_routes(grid)[0]
                    missing_resources = best_path["resources_missing_due_to_insufficient_inventory"]
                    if not missing_resources:  # Empty dict means we have all needed resources
                        print(f"Invalid trade: {cleaned['trade_proposer']} already has all needed resources")
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
        message = self.generate_player_context_message(game, grid) + f"""
Recall the 'pay for other' mode rules:
{self.generate_pay4partner_mode_info(short_summary=True)}\n\n

You have been asked by {other_player.name} to cover their movement cost onto a tile of color {color} as part of a previous trade agreement. Here are your past aggreements with this player:
{[agreement['text_summary'] for agreement in self.pay4partner_log if agreement['with'] == other_player.name]}
Do you agree to pay a {color} resource to cover the other player? Although you previously agreed to this with the other player, it is not mandatory. Remember that you are trying to maximise your points. List your options and the pros and cons of each, and finish your response with 'yes' if you agree to pay (and lose the resource) or 'no' if you want to keep the resource. Make sure the last word of your response is exactly 'yes' or 'no'.
""" 
        if self.model_name == 'human':
            print(f"{self.name}, {other_player.name} is envoking 'pay for partner' and asking you to pay for their move onto a {color} tile.")
            while True:
                agree = input("Do you agree to this? y/n ").strip().lower()
                if agree not in ('y', 'n'):
                    print("Please enter 'y' or 'n'.")
                    continue
                return agree == 'y'
        else:
            # Prepare messages for this request
            current_messages = list(self.messages) if self.with_message_history else [{"role": "system", "content": self.system_prompt.format(player_name=self.name, pay4partner_mode_info=self.pay4partner_mode_sys_prompt, pay4partner_scoring_info=self.pay4partner_scoring_info)}]
            current_messages.append({"role": "user", "content": message})
            
            # Log full context to yulia logs
            # Note: game object is not passed here, so we skip yulia logging for now
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=current_messages,
                max_completion_tokens=1000)
            agree = response.choices[0].message.content.strip().lower()
            
            # Save to history if enabled
            if self.with_message_history:
                self.messages.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": agree}
                ])
            
            self.logger.log("pay4partner_response", {"player": self.name, "message": agree})
            
            final_respones  = get_last_alphabetic_word(agree)
            if "yes" in final_respones:
                return True
            else:
                return False

def get_last_alphabetic_word(text):
                # Find all alphabetic words in the text
                words = re.findall(r"[a-zA-Z]+", text)
                # Return the last word if the list is not empty
                return words[-1] if words else None