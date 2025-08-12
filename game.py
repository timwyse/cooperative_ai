import pygame
import copy
from time import sleep
from constants import WIDTH, HEIGHT, COLOR_MAP, TILE_SIZE, FPS, DEFAULT_PLAYERS, GRID_SIZE
from utils import freeze
from grid import Grid
from player import Player
from collections import Counter, defaultdict
from tabulate import tabulate


class Game:
    def __init__(self, players=DEFAULT_PLAYERS):
        self.n_players = len(players)
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        # Assign player colors
        self.player_colors = [color for color in COLOR_MAP if color not in ('black')][:self.n_players]
        self.players = [Player(self.player_colors[i], self.n_players, player) for i, player in enumerate(players)]

        # Create grid with player colors
        self.grid = Grid(GRID_SIZE, self.player_colors)

        self.turn = 0
        self.running = True
        self.game_state = self.initialize_game_state()
        self.game_states = [copy.deepcopy(self.game_state)]

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

    def print_game_state(self):
        """Print the current game state to the console."""
        print(f"GAME STATE FOR TURN {self.turn}:")
        for player_name, state in self.game_state.items():
            print(f"""{player_name} ({state['model']}):
                  Resources: {state['resources']}""")
                #   Position: {state['position']}
                #   Goal: {state['goal']}
                  

    def draw(self):
        self.screen.fill(COLOR_MAP['black'])
        for y in range(len(self.grid.tiles)):
            for x in range(len(self.grid.tiles)):
                tile_color = self.grid.get_color(x, y)
                pygame.draw.rect(
                    self.screen, COLOR_MAP[tile_color],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                )
                pygame.draw.rect(
                    self.screen, COLOR_MAP['black'],
                    (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE), 1
                )

        # Draw start tiles with overlapping text handling
        start_positions = defaultdict(list)
        for player in self.players:
            sx, sy = player.start_pos
            start_positions[(sx, sy)].append(player.color)

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
                text = font.render(f"S_{color}", True, COLOR_MAP['black'])
                self.screen.blit(text, (sx * TILE_SIZE + 5, sy * TILE_SIZE + 5 + offset_y))

        # Draw goal tiles with overlapping text handling
        goal_positions = defaultdict(list)
        for player in self.players:
            gx, gy = player.goal
            goal_positions[(gx, gy)].append(player.color)

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
                text = font.render(f"G_{color}", True, COLOR_MAP['black'])
                self.screen.blit(text, (gx * TILE_SIZE + 5, gy * TILE_SIZE + 5 + offset_y))

        # Draw players and handle multiple players on the same tile
        player_positions = defaultdict(list)
        for player in self.players:
            player_positions[player.position].append(player)

        for (px, py), players in player_positions.items():
            if len(players) == 1:
                # Single player on the tile
                player = players[0]
                pygame.draw.circle(
                    self.screen, COLOR_MAP[player.color],
                    (px * TILE_SIZE + TILE_SIZE // 2, py * TILE_SIZE + TILE_SIZE // 2), 20
                )
                pygame.draw.circle(
                    self.screen, COLOR_MAP['black'],
                    (px * TILE_SIZE + TILE_SIZE // 2, py * TILE_SIZE + TILE_SIZE // 2), 21, 1
                )
            else:
                # Multiple players on the same tile
                offset = TILE_SIZE // (2 * len(players))  # Adjust offset based on the number of players
                for i, player in enumerate(players):
                    offset_x = (i % 2) * offset - offset // 2
                    offset_y = (i // 2) * offset - offset // 2
                    pygame.draw.circle(
                        self.screen, COLOR_MAP[player.color],
                        (px * TILE_SIZE + TILE_SIZE // 2 + offset_x, py * TILE_SIZE + TILE_SIZE // 2 + offset_y), 10
                    )
                    pygame.draw.circle(
                        self.screen, COLOR_MAP['black'],
                        (px * TILE_SIZE + TILE_SIZE // 2 + offset_x, py * TILE_SIZE + TILE_SIZE // 2 + offset_y), 11, 1
                    )

        pygame.display.flip()

    def draw_basic_grid(self):
        grid = copy.deepcopy(self.grid.tile_colors)
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                for player in self.players:
                    if player.position == (j, i):
                        grid[i][j] = f"{grid[i][j]} (Player {player.color})"
        print(tabulate(grid, tablefmt="fancy_grid"))

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
                print(f"{player.name} chose not to move.")
            else:
                if player.can_move_to(move, self.grid):
                    player.move(move, self.grid)
                    print(f"{player.name} moved to {move}.")
                else:
                    print(f"{player.name} cannot move to {move}. Not adjacent or insufficient resources.")

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
        player_to_trade_with = next((p for p in self.players if p.name.lower() == propose_trade['player_to_trade_with'].lower()), None)
        if not player_to_trade_with:
            print(f"The proposed player '{propose_trade['player_to_trade_with']}' does not exist.")
            return
        elif propose_trade['resource_to_offer_to_other_player'] not in player.resources or player.resources[propose_trade['resource_to_offer_to_other_player']] < propose_trade['quantity_to_offer_to_other_player']:
            print(f"{player.name} does not have enough {propose_trade['resource_to_offer_to_other_player']} to offer.")
            return
        elif propose_trade['resource_to_receive_from_other_player'] not in player_to_trade_with.resources or player_to_trade_with.resources[propose_trade['resource_to_receive_from_other_player']] < propose_trade['quantity_to_receive_from_other_player']:
            print(f"{player_to_trade_with.name} does not have enough {propose_trade['resource_to_receive_from_other_player']} for the trade.")
            return

        # Ask the target player if they accept the trade
        if player_to_trade_with.accept_trade(self.grid, self, propose_trade):
            # Execute the trade
            print(f"{player_to_trade_with.name} accepted the trade with {player.name}.")
            player.resources[propose_trade['resource_to_offer_to_other_player']] -= propose_trade['quantity_to_offer_to_other_player']
            player.resources[propose_trade['resource_to_receive_from_other_player']] += propose_trade['quantity_to_receive_from_other_player']
            player_to_trade_with.resources[propose_trade['resource_to_receive_from_other_player']] -= propose_trade['quantity_to_receive_from_other_player']
            player_to_trade_with.resources[propose_trade['resource_to_offer_to_other_player']] += propose_trade['quantity_to_offer_to_other_player']
        else:
            print(f"{player_to_trade_with.name} rejected the trade.")    

    def run(self, full_draw=True):
        while self.running and not all(p.has_finished() for p in self.players):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
            self.draw_basic_grid()
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
            sleep(10)
        
        print("Game over!")
        self.draw_basic_grid()
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
        most_common_item, count = state_counter.most_common(1)[0] 
        if count == n_repeats:
            print(f"{self.print_game_state} has occurs more than 3 times, finishing the game.")
            return True
        elif count == n_repeats - 1:
            print(f"Current game state has occurred {count} times, game will stop if this occurs again.")
            return False
        else:
            return False