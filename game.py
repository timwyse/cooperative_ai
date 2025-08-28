from collections import Counter, defaultdict
import copy
import random
from time import sleep
from typing import Optional

import pygame
from tabulate import tabulate

from config import GameConfig, DEFAULT_CONFIG
from constants import AVAILABLE_COLORS, COLOR_MAP, TILE_SIZE, FPS
from grid import Grid
from logger import GameLogger, NullLogger
from player import Player
from utils import freeze


class Game:
   
    def __init__(self, config: Optional[GameConfig] = DEFAULT_CONFIG, logger=None):
        # Configuration and Logging
        self.config = config
        self.logger = logger if logger is not None else NullLogger()

        # Grid Setup
        self.grid_size = self.config.grid_size
        self.colors = self.config.colors
        
        self.grid = Grid(self.grid_size, self.colors, grid=self.config.grid)

        # Player Initialization
        self.players = [Player(i, player, self.logger, self.config) for i, player in enumerate(self.config.players)]
        self.n_players = len(self.players)

        # Resource Distribution
        self.distribute_resources()

        # Game State Initialization
        self.game_state = self.initialize_game_state()
        self.game_states = [copy.deepcopy(self.game_state)]
        self.turn = 0
        self.max_possible_score = self.max_possible_score()

        # Pygame Initialization
        pygame.init()
        self.width = self.height = self.grid_size * TILE_SIZE
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.running = True

        # Logging Initial State
        self.logger.log("game_config", {"config": self.config})
        self.logger.log("initial_game_state", {"initial_game_state": copy.deepcopy(self.game_state)})
        self.logger.log("grid", {"grid": self.grid.tile_colors})

    
    # 1. Initialization and Setup
    def distribute_resources(self):
        '''
        Distribute resources to players based on the resource mode specified in the config.
        '''
        valid_resource_modes = ['single_type_each', 'random', 'manual']
        if self.config.resource_mode not in valid_resource_modes:
            raise ValueError(f"Invalid resource mode: {self.config.resource_mode}. Valid modes are: {valid_resource_modes}")
        
        print(f"Distributing resources in '{self.config.resource_mode}' mode.")
        default_total_num_resources = round(self.config.surplus * 2 * (self.grid_size - 1))
        
        if self.config.resource_mode == 'single_type_each':
            
            if self.n_players != len(self.colors):
                raise ValueError(f"""Number of players must match number of colors for 'single_type_each' resource mode.
                                 You have currently specified {self.n_players} players but {len(self.colors)} colors.
                                 """)
            print(f"Each player will receive {default_total_num_resources} resources of their assigned color.")
            for player, color in zip(self.players, self.colors):
                player.resources[color] = default_total_num_resources

        elif self.config.resource_mode == 'random':
            if self.n_players != len(self.colors):
                raise ValueError(f"""Number of players must match number of colors for 'random' resource mode.
                                 You have currently specified {self.n_players} players but {len(self.colors)} colors.
                                 """)
            print(f"Distributing {default_total_num_resources} resources randomly among players.")
            resource_pool = [color for _ in range(default_total_num_resources) for color in self.colors]
            random.shuffle(resource_pool)

            for player in self.players:
                player.resources = defaultdict(int)  # Initialize resources for the player
                for _ in range(default_total_num_resources):
                    if resource_pool:
                        resource = resource_pool.pop()
                        player.resources[resource] += 1
                player.resources = dict(sorted(player.resources.items()))
        
        elif self.config.resource_mode == 'manual':
            if self.config.manual_resources is None:
                raise ValueError("Manual resource mode requires a list of resource disctionaries in 'manual_resources'.")
            resources = list(set(color for players_resources in self.config.manual_resources for color in players_resources.keys()))
            if not all(color in AVAILABLE_COLORS for color in resources):
                raise ValueError(f"Invalid colors in manual resources. Available colors are: {AVAILABLE_COLORS}")
            print(f"Distributing manual resources: {self.config.manual_resources}. Note that the surplus parameter is ignored in this mode.")
            if len(self.config.manual_resources) != self.n_players:
                raise ValueError(f"Number of dicts of resources must match number of players. There are {self.n_players} players but {len(self.config.manual_resources)} dicts of resources.")
            for player, resources in zip(self.players, self.config.manual_resources):
                player.resources = defaultdict(int)
                for color, quantity in resources.items():
                    if color not in AVAILABLE_COLORS:
                        raise ValueError(f"Invalid color '{color}' in manual resources. Available colors are: {AVAILABLE_COLORS}")
                    player.resources[color] += quantity
                player.resources = dict(sorted(player.resources.items()))    
    

    def initialize_game_state(self):
        """Initialize the game state with player positions and resources."""
        state = {}
        for player in self.players:
            state[player.name] = {
                "model": player.model_name,
                "position": player.position,
                "goal": player.goal,
                "resources": dict(player.resources)
            }
        return state
    
    def max_possible_score(self):
        """
        Calculate the maximum possible score for the game.
        # Each player can score a maximum of 100 points (for reaching their destionation), plus 5 points for each resource remaining
        Assumes the players start at top-left and have to reach bottom-right.
        TODO should be based on actual player positions and goals, as well as the scoring logic.
        """
        total_resources = 0
        for player in self.players:
            total_resources += sum(player.resources.values())
        min_steps_total = (2 * (self.grid_size - 1)) * self.n_players  
        max_resources_remaining = total_resources - min_steps_total
        max_possible_score = 100 * self.n_players + (5 * max_resources_remaining)
        
        return max_possible_score

    
    # 2. Core Game Loop
    def run(self, full_draw=True):
        while self.running and not all(p.has_finished() for p in self.players):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
            if full_draw:
                self.draw()
            self.print_game_state()
            self.handle_turn(self.players)
            
            self.update_game_state()
            if self.turn > 0:
                self.game_states.append(copy.deepcopy(self.game_state))

            if self.check_for_repeated_states():
                break
            
            self.turn += 1
            self.clock.tick(FPS)

            # Wait for Enter to proceed
            # input("Press Enter to proceed to the next turn...")
            print(f"End of turn {self.turn}. Waiting for next turn...")
            sleep(0.1)
        
        print("Game over!")
        self.print_game_state()
        scores = self.get_scores()
        total_scores = self.get_total_scores(scores)
        total_accuracy = self.get_total_accuracy(scores)
        gini_coefficient = self.calculate_gini_coefficient(scores)
        self.logger.log("final_scores", {"scores": scores})
        self.logger.log("metrics", {
            "total_scores": total_scores,
            "total_accuracy": total_accuracy,
            "gini_coefficient": gini_coefficient,
            "max_possible_score": self.max_possible_score
            })
        print(f"Final scores: {scores}")
        pygame.quit()


    def handle_turn(self, players):
        """
        Handle each player's turn:
        - If the player has already finished, skip their turn.
        - If the player has not finished, let them propose a trade and/or make a move.
        - Validate trades and moves before executing them.
        """
        for player in players:
            if player.has_finished():
                print(f"{player.name} has already finished the game.")
                continue

            print(f"\n{player.name}'s turn:")

            # Handle trade proposal
            propose_trade = player.propose_trade(self.grid, self)
            if propose_trade and propose_trade is not None:
                self.handle_trade(player, propose_trade)


            # Handle movement
            move = player.come_up_with_move(self, self.grid)
            if move is None:
                print(f"{player.name} did not move.")
            else:
                if player.can_move_to(move, self.grid):
                    self.logger.log("move", {
                        "player": player.name,
                        "move_from": player.position,
                        "move_to": move,})
                    player.move(move, self.grid)
                    print(f"{player.name} moved to {move}.")
                    

    def handle_trade(self, player, propose_trade):
        """
        Handle a trade proposal from a player.
        - Validate the trade proposal.
        - Execute the trade if the target player accepts.
        """
        try:
            # Validate the trade proposal
            validation_result = self.validate_trade(player, propose_trade)
            if not validation_result["is_valid"]:
                print(f"Trade validation failed: {validation_result['message']}")
                return

            player_to_trade_with = validation_result["player_to_trade_with"]
            resources_to_offer = propose_trade['resources_to_offer']
            resources_to_receive = propose_trade['resources_to_receive']

            trade_log = copy.deepcopy(propose_trade)

            # Ask the target player if they accept the trade
            if player_to_trade_with.accept_trade(self.grid, self, propose_trade):
                # Execute the trade
                for resource, quantity in resources_to_offer:
                    player.resources[resource] -= quantity
                    player_to_trade_with.resources[resource] += quantity

                for resource, quantity in resources_to_receive:
                    player.resources[resource] += quantity
                    player_to_trade_with.resources[resource] -= quantity

                print("\n *** Updated resources for trade players: ***")
                for trade_player in [player, player_to_trade_with]:
                    print(f"""{trade_player.name}:
                                Resources: {trade_player.resources} \n""")
                
                trade_log['result'] = 'accepted'
                self.logger.log("trade", trade_log)
            else:
                trade_log['result'] = 'declined'
                self.logger.log("trade", trade_log)

        except Exception as e:
            print(f"An error occurred while handling the trade: {e}")
            self.logger.log("trade_error", {"error": str(e), "propose_trade": propose_trade})

    def validate_trade(self, player, propose_trade):
        """
        Validate a trade proposal.
        Returns a dictionary with the validation result, including:
        - is_valid: True/False
        - message: Error message if invalid
        - player_to_trade_with: The target player if valid
        """
        validation_result = {"is_valid": False, "message": "", "proposed trade": propose_trade}
        required_fields = ['player_to_trade_with', 'resources_to_offer', 'resources_to_receive']
        if not all(field in propose_trade for field in required_fields):
            validation_result['message'] = "Missing required fields in trade proposal."
            return validation_result

        # Find the player to trade with
        def normalize_name(name: str) -> str:
            return name.lower().replace("player", "").strip()

        player_to_trade_with = next(
            (p for p in self.players if normalize_name(p.name) == normalize_name(propose_trade['player_to_trade_with'])),
            None
        )

        if not player_to_trade_with:
            validation_result['message'] = f"The proposed player '{propose_trade['player_to_trade_with']}' does not exist."
            return validation_result

        resources_to_offer = propose_trade['resources_to_offer']  # List of tuples [(color, quantity), ...]
        resources_to_receive = propose_trade['resources_to_receive']  # List of tuples [(color, quantity), ...]

        # Validate that the proposing player has enough resources to offer
        for resource, quantity in resources_to_offer:
            if quantity < 0:
                validation_result["message"] = f"Invalid quantity to offer {quantity} for resource {resource}."
                return validation_result
            if resource not in player.resources or player.resources[resource] < quantity:
                validation_result["message"] = f"{player.name} does not have enough {resource} to offer."
                return validation_result

        # Validate that the target player has enough resources to fulfill the trade
        for resource, quantity in resources_to_receive:
            if quantity < 0:
                validation_result["message"] = f"Invalid quantity to receive {quantity} for resource {resource}."
                return validation_result
            if resource not in player_to_trade_with.resources or player_to_trade_with.resources[resource] < quantity:
                validation_result["message"] = f"{player_to_trade_with.name} does not have enough {resource} to fulfill the trade."
                return validation_result

        validation_result["message"] = "Trade proposal is valid."
        validation_result["is_valid"] = True
        validation_result["proposed_trade"] = propose_trade
        validation_result["player_to_trade_with"] = player_to_trade_with
        return validation_result


    def update_game_state(self):
        """Update the game state after each turn."""
        for player in self.players:
            self.game_state[player.name]["position"] = player.position
            self.game_state[player.name]["resources"] = dict(player.resources)


    # 3. Game State and Metrics
    def get_scores(self):
        """Calculate and return the scores for each player."""
        scores = {}
        for player in self.players:
            scores[player.name] = max(0, 100 - (10 * player.distance_to_goal())) + (5 * sum(player.resources.values()))
        return scores
    

    def get_total_scores(self, scores):
        return sum(scores.values())


    def get_total_accuracy(self, scores):
        """Defined as the total score divided by the maximum possible score."""
        return sum(scores.values())/ self.max_possible_score


    def calculate_gini_coefficient(self, scores):
        """
        Calculate the Gini coefficient for the final scores.
        """
        scores = list(scores.values())
        scores.sort()  
        n = len(scores)

        cumulative_sum = sum((i + 1) * score for i, score in enumerate(scores))
        total_sum = sum(scores)

        if total_sum == 0:
            return 0  

        gini = (2 * cumulative_sum) / (n * total_sum) - (n + 1) / n
        return gini


    def check_for_repeated_states(self, n_repeats=3):
        """Check if the game has entered a repeated state."""
        
        hashable_states = [freeze(state) for state in self.game_states]
        state_counter = Counter(hashable_states)
        count = state_counter[freeze(self.game_state)]
        if count == n_repeats:
            print(f"The position has repeated {n_repeats} times, finishing the game.")
            self.logger.log("repeated_states_break", {"n_repeats": n_repeats})
            return True
        elif count == n_repeats - 1:
            print(f"Current position has repeated {count} times, game will stop if this occurs again.")
            return False
        else:
            return False
    

    # 4. Rendering and Debugging

    def draw(self):
        # Add extra space for row and column labels
        label_space = TILE_SIZE//8  # Space for labels (equal to one tile size)
        screen_width = self.grid_size * TILE_SIZE + label_space
        screen_height = self.grid_size * TILE_SIZE + label_space

        # Resize the screen to include the label space
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        self.screen.fill(COLOR_MAP['LG'])  # Fill background with light gray

        # Draw the grid tiles
        for r in range(len(self.grid.tiles)):
            for c in range(len(self.grid.tiles[r])):
                tile_color = self.grid.get_color(r, c)
                pygame.draw.rect(
                    self.screen, COLOR_MAP[tile_color],
                    (c * TILE_SIZE + label_space, r * TILE_SIZE + label_space, TILE_SIZE, TILE_SIZE)
                )
                pygame.draw.rect(
                    self.screen, COLOR_MAP['BK'],
                    (c * TILE_SIZE + label_space, r * TILE_SIZE + label_space, TILE_SIZE, TILE_SIZE), 1
                )

        # Draw row numbers along the y-axis (left side)
        font = pygame.font.Font(None, round(1.25*label_space))  # Adjust font size as needed
        for r in range(len(self.grid.tiles)):
            text = font.render(str(r), True, COLOR_MAP['BK'])  # Render row number
            text_rect = text.get_rect(center=(label_space // 2, r * TILE_SIZE + label_space + TILE_SIZE // 2))
            self.screen.blit(text, text_rect)

        # Draw column numbers along the x-axis (top side)
        for c in range(len(self.grid.tiles[0])):
            text = font.render(str(c), True, COLOR_MAP['BK'])  # Render column number
            text_rect = text.get_rect(center=(c * TILE_SIZE + label_space + TILE_SIZE // 2, label_space // 2))
            self.screen.blit(text, text_rect)

        # Draw start tiles with overlapping text handling
        start_positions = defaultdict(list)
        for player in self.players:
            sr, sc = player.start_pos  # Start position as (row, column)
            start_positions[(sr, sc)].append(player.name)

        for (sr, sc), colors in start_positions.items():
            pygame.draw.rect(
                self.screen, COLOR_MAP[self.grid.get_color(sr, sc)],
                (sc * TILE_SIZE + label_space, sr * TILE_SIZE + label_space, TILE_SIZE, TILE_SIZE)
            )
            font_size = 24 if len(colors) == 1 else 16
            font = pygame.font.Font(None, font_size)
            offset = TILE_SIZE // (len(colors))
            for i, color in enumerate(colors):
                offset_y = i * offset
                text = font.render(f"S_{color}", True, COLOR_MAP['BK'])
                self.screen.blit(text, (sc * TILE_SIZE + 5 + label_space, sr * TILE_SIZE + 5 + offset_y + label_space))

        # Draw goal tiles with overlapping text handling
        goal_positions = defaultdict(list)
        for player in self.players:
            gr, gc = player.goal  # Goal position as (row, column)
            goal_positions[(gr, gc)].append(player.name)

        for (gr, gc), colors in goal_positions.items():
            pygame.draw.rect(
                self.screen, COLOR_MAP[self.grid.get_color(gr, gc)],
                (gc * TILE_SIZE + label_space, gr * TILE_SIZE + label_space, TILE_SIZE, TILE_SIZE)
            )
            font_size = 24 if len(colors) == 1 else 16
            font = pygame.font.Font(None, font_size)
            offset = TILE_SIZE // (len(colors))
            for i, color in enumerate(colors):
                offset_y = i * offset
                text = font.render(f"G_{color}", True, COLOR_MAP['BK'])
                self.screen.blit(text, (gc * TILE_SIZE + 5 + label_space, gr * TILE_SIZE + 5 + offset_y + label_space))
        
        # Draw players and handle multiple players on the same tile
        player_positions = defaultdict(list)
        for player in self.players:
            player_positions[player.position].append(player)

        for (pr, pc), players in player_positions.items():
            if len(players) == 1:
                # Single player on the tile
                player = players[0]
                draw_player_circle(self.screen, player, (pc, pr), radius=20, offset=(label_space, label_space))
            else:
                # Multiple players on the same tile
                offset = TILE_SIZE // (2 * len(players))  # Adjust offset based on the number of players
                for i, player in enumerate(players):
                    offset_x = (i % 2) * offset - offset // 2
                    offset_y = (i // 2) * offset - offset // 2
                    draw_player_circle(self.screen, player, (pc, pr), radius=10, offset=(label_space + offset_x, label_space + offset_y))

        pygame.display.flip()


    def draw_basic_grid(self):
        grid = copy.deepcopy(self.grid.tile_colors)
        for r in range(len(grid)):
            for c in range(len(grid[r])):
                for player in self.players:
                    if player.position == (r, c):
                        grid[r][c] = f"{grid[r][c]} ({player.name})"
                    elif player.goal == (r, c):
                        grid[r][c] = f"{grid[r][c]} (Goal {player.name})"
        print(tabulate(grid, tablefmt="fancy_grid"))


    def print_game_state(self):
        """Print the current game state to the console."""
        print(f"GAME STATE FOR TURN {self.turn}:")
        self.draw_basic_grid()
        for player_name, state in self.game_state.items():
            print(f"""{player_name} ({state['model']}):
                  Resources: {state['resources']}""")
        

def draw_player_circle(screen, player, position, radius, offset=(0, 0)):
    """
    Draw a translucent circle with the player's name at the given position.
    """
    px, py = position
    offset_x, offset_y = offset

    # Create a translucent surface for the circle
    circle_surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    circle_color = (0, 0, 0, 64)  # Black with 50% transparency (RGBA)
    pygame.draw.circle(
        circle_surface, circle_color,
        (TILE_SIZE // 2, TILE_SIZE // 2), radius
    )
    screen.blit(circle_surface, (px * TILE_SIZE + offset_x, py * TILE_SIZE + offset_y))

    # Render the player's name inside the circle
    font = pygame.font.Font(None, 24)  # Adjust font size as needed
    text = font.render(str(player.id), True, COLOR_MAP['BK'])  # Render the player's name in black
    text_rect = text.get_rect(center=(px * TILE_SIZE + TILE_SIZE // 2 + offset_x, py * TILE_SIZE + TILE_SIZE // 2 + offset_y))
    screen.blit(text, text_rect)
