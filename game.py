import pygame
import copy
from typing import Optional
from time import sleep
from constants import COLOR_MAP, TILE_SIZE, FPS
from config import GameConfig, DEFAULT_CONFIG
from utils import freeze
from grid import Grid
from player import Player
from collections import Counter, defaultdict
from tabulate import tabulate



class Game:
    def __init__(self, config: Optional[GameConfig] = DEFAULT_CONFIG):
                
        self.config = config
        self.width = self.height = self.config.grid_size * TILE_SIZE
        self.grid_size = config.grid_size
        self.colors = config.colors
        self.players = [Player(i,  player, self.config) for i, player in enumerate(self.config.players)]
        self.grid = Grid(self.grid_size, self.colors, grid=self.config.grid)
        self.distribute_resources()
        self.game_state = self.initialize_game_state()
        self.game_states = [copy.deepcopy(self.game_state)]
        
        self.turn = 0
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.running = True
        
        
                
    def distribute_resources(self):
        if self.config.resource_mode == 'single_type_each':
            if len(self.players) != len(self.colors):
                raise ValueError(f"""Number of players must match number of colors for 'single_type_each' resource mode.
                                 You have currently specified {len(self.players)} players but {len(self.colors)} colors.
                                 """)
            for player, color in zip(self.players, self.colors):
                print(f"Distributing resources for {player.name} with color {color}.")
                print(f"Player {player.name} will receive {round(self.config.surplus * 2 * (self.grid_size - 1))} resources of color {color}.")
                player.resources[color] = round(self.config.surplus * 2 * (self.grid_size - 1))
    
    
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


    def update_game_state(self):
        """Update the game state after each turn."""
        for player in self.players:
            self.game_state[player.name]["position"] = player.position
            self.game_state[player.name]["resources"] = dict(player.resources)


    def draw_basic_grid(self):
        grid = copy.deepcopy(self.grid.tile_colors)
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                for player in self.players:
                    if player.position == (j, i):
                        grid[i][j] = f"{grid[i][j]} ({player.name})"
                    elif player.goal == (j, i):
                        grid[i][j] = f"{grid[i][j]} (Goal {player.name})"
        print(tabulate(grid, tablefmt="fancy_grid"))


    def print_game_state(self):
        """Print the current game state to the console."""
        print(f"GAME STATE FOR TURN {self.turn}:")
        self.draw_basic_grid()
        for player_name, state in self.game_state.items():
            print(f"""{player_name} ({state['model']}):
                  Resources: {state['resources']}""")


    def draw(self):
        self.screen.fill(COLOR_MAP['BK'])
        for y in range(len(self.grid.tiles)):
            for x in range(len(self.grid.tiles)):
                tile_color = self.grid.get_color(x, y)
                pygame.draw.rect(
                    self.screen, COLOR_MAP[tile_color],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                )
                pygame.draw.rect(
                    self.screen, COLOR_MAP['BK'],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE), 1
                )

        # Draw start tiles with overlapping text handling
        start_positions = defaultdict(list)
        for player in self.players:
            sx, sy = player.start_pos
            start_positions[(sx, sy)].append(player.name)

        for (sx, sy), colors in start_positions.items():
            pygame.draw.rect(
                self.screen, COLOR_MAP[self.grid.get_color(sx, sy)],
                (sx * TILE_SIZE, sy * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            )
            font_size = 24 if len(colors) == 1 else 16
            font = pygame.font.Font(None, font_size)
            offset = TILE_SIZE // (len(colors))
            for i, color in enumerate(colors):
                offset_y = i * offset
                text = font.render(f"S_{color}", True, COLOR_MAP['BK'])
                self.screen.blit(text, (sx * TILE_SIZE + 5, sy * TILE_SIZE + 5 + offset_y))

        # Draw goal tiles with overlapping text handling
        goal_positions = defaultdict(list)
        for player in self.players:
            gx, gy = player.goal
            goal_positions[(gx, gy)].append(player.name)

        for (gx, gy), colors in goal_positions.items():
            pygame.draw.rect(
                self.screen, COLOR_MAP[self.grid.get_color(gx, gy)],
                (gx * TILE_SIZE, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            )
            font_size = 24 if len(colors) == 1 else 16
            font = pygame.font.Font(None, font_size)
            offset = TILE_SIZE // (len(colors))
            for i, color in enumerate(colors):
                offset_y = i * offset
                text = font.render(f"G_{color}", True, COLOR_MAP['BK'])
                self.screen.blit(text, (gx * TILE_SIZE + 5, gy * TILE_SIZE + 5 + offset_y))

        # Draw players and handle multiple players on the same tile
        player_positions = defaultdict(list)
        for player in self.players:
            player_positions[player.position].append(player)

        for (px, py), players in player_positions.items():
            if len(players) == 1:
                # Single player on the tile
                player = players[0]
                draw_player_circle(self.screen, player, (px, py), radius=20)
            else:
                # Multiple players on the same tile
                offset = TILE_SIZE // (2 * len(players))  # Adjust offset based on the number of players
                for i, player in enumerate(players):
                    offset_x = (i % 2) * offset - offset // 2
                    offset_y = (i // 2) * offset - offset // 2
                    draw_player_circle(self.screen, player, (px, py), radius=10, offset=(offset_x, offset_y))

        pygame.display.flip()


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
                    player.move(move, self.grid)
                    print(f"{player.name} moved to {move}.")
                

    def handle_trade(self, player, propose_trade):
        """
        Handle a trade proposal from a player.
        - Validate the trade proposal.
        - Execute the trade if the target player accepts.
        """
        # Validate trade proposal
        required_fields = ['player_to_trade_with', 'resource_to_offer_to_other_player', 'quantity_to_offer_to_other_player', 'resource_to_receive_from_other_player', 'quantity_to_receive_from_other_player']
        if not all(field in propose_trade for field in required_fields):
            print("Invalid trade proposal: Missing required fields.")
            return

        # Find the player to trade with
        def normalize_name(name: str) -> str:
            return name.lower().replace("player", "").strip()

        player_to_trade_with = next(
            (p for p in self.players if normalize_name(p.name) == normalize_name(propose_trade['player_to_trade_with'])),
            None
        )
        try:
            resource_offered = propose_trade['resource_to_offer_to_other_player'].strip().upper()
            quantity_offered = propose_trade['quantity_to_offer_to_other_player']
            resource_to_receive = propose_trade['resource_to_receive_from_other_player'].strip().upper()
            quantity_to_receive = propose_trade['quantity_to_receive_from_other_player']
        except AttributeError as e:
            print(f"Invalid trade proposal: {e}")
            return
        if not player_to_trade_with:
            print(f"The proposed player '{propose_trade['player_to_trade_with']}' does not exist.")
            return
        
        elif resource_offered not in player.resources or player.resources[resource_offered] < quantity_offered:
            print(f"{player.name} does not have enough {resource_offered} to offer.")
            return
        elif resource_to_receive not in player_to_trade_with.resources or player_to_trade_with.resources[resource_to_receive] < quantity_to_receive:
            print(f"{player_to_trade_with.name} does not have enough {resource_to_receive} for the trade.")
            return

        # Ask the target player if they accept the trade
        if player_to_trade_with.accept_trade(self.grid, self, propose_trade):
            # Execute the trade
            player.resources[resource_offered] -= quantity_offered
            player.resources[resource_to_receive] += quantity_to_receive
            player_to_trade_with.resources[resource_to_receive] -= quantity_to_receive
            player_to_trade_with.resources[resource_offered] += quantity_offered

            print("\n *** Updated resources for trade players: ***")
            for trade_player in [player, player_to_trade_with]:
                print(f"""{trade_player.name}:
                        Resources: {trade_player.resources} \n""")


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
        print(f"Final scores: {scores}")
        pygame.quit()


    def get_scores(self):
        """Calculate and return the scores for each player."""
        scores = {}
        for player in self.players:
            scores[player.name] = max(0, 100 - (10 * player.distance_to_goal())) + (5 * sum(player.resources.values()))
        return scores


    def check_for_repeated_states(self, n_repeats=3):
        """Check if the game has entered a repeated state."""
        
        hashable_states = [freeze(state) for state in self.game_states]
        state_counter = Counter(hashable_states)
        count = state_counter[freeze(self.game_state)]
        if count == n_repeats:
            print(f"The position has repeated {n_repeats} times, finishing the game.")
            return True
        elif count == n_repeats - 1:
            print(f"Current position has repeated {count} times, game will stop if this occurs again.")
            return False
        else:
            return False
        

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
