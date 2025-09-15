from collections import Counter, defaultdict
import copy
import json
import random
import re
from time import sleep

import pygame
from tabulate import tabulate

from constants import AVAILABLE_COLORS, COLOR_MAP, TILE_SIZE, FPS
from grid import Grid
from judge import JUDGE
from logger import Logger
from player import Player
import prompts
from utils import freeze


class Game:
   
    def __init__(self, config):
        # Configuration and Logging
        self.config = config
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger = Logger(game_id=timestamp)

        # Grid Setup
        self.grid_size = self.config.grid_size
        self.colors = self.config.colors
        
        self.grid = Grid(self.grid_size, self.colors, grid=self.config.grid)

        # Player Initialization
        self.players = [Player(i, player, self.logger, self.config) for i, player in enumerate(self.config.players)]
        self.n_players = len(self.players)
        self.initialize_fog_of_war()
        
        # Resource Distribution
        self.distribute_resources()
        
        # Store initial resources for player labeling
        self.initial_resources = {player.name: dict(player.resources) for player in self.players}
        
        # Store initial positions for max score calculation
        for player in self.players:
            player.start = player.start_pos  # Save initial position from start_pos
            
        # trade version
        self.pay4partner = self.config.pay4partner
        self.contract_type = self.config.contract_type
        self.contract = None

        # Game State Initialization
        self.initialize_player_positions()
        self.game_state = self.initialize_game_state()
        self.game_states = [copy.deepcopy(self.game_state)]
        self.turn = 0
        self.with_context = config.with_context
        self.turn_summaries = [] if self.with_context else None  # List to store summaries of each turn's events
        
        # Pygame Initialization (only if display_gui is True)
        self.display_gui = config.display_gui
        if self.display_gui:
            pygame.init()
            self.width = self.height = self.grid_size * TILE_SIZE
            self.screen = pygame.display.set_mode((self.width, self.height))
            self.clock = pygame.time.Clock()
        self.running = True

        # Logging Initial State
        self.logger.log_game_config(self.config, self.players, self.grid)

    
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
                player.starting_resources = copy.deepcopy(player.resources)

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
                player.starting_resources = copy.deepcopy(player.resources)
        
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
                player.resources = {color: 0 for color in self.colors}
                for color, quantity in resources.items():
                    if color not in AVAILABLE_COLORS:
                        raise ValueError(f"Invalid color '{color}' in manual resources. Available colors are: {AVAILABLE_COLORS}")
                    player.resources[color] += quantity
                player.resources = dict(sorted(player.resources.items())) 
                player.starting_resources = copy.deepcopy(player.resources)   
    
    def initialize_player_positions(self):
        if self.config.manual_start_positions:
            if len(self.config.manual_start_positions) != self.n_players:
                raise ValueError(f"Number of manual start positions must match number of players. There are {self.n_players} players but {len(self.config.manual_start_positions)} start positions.")
            for player, pos in zip(self.players, self.config.manual_start_positions):
                if not (0 <= pos[0] < self.grid_size and 0 <= pos[1] < self.grid_size):
                    raise ValueError(f"Invalid start position {pos} for player {player.name}. Must be within grid size {self.grid_size}.")
                player.start_pos = pos
                player.position = player.start_pos
        else:
            for player in self.players:
                player.start_pos = (random.randint(0, self.config.random_start_block_size - 1), random.randint(0, self.config.random_start_block_size - 1))
                player.position = player.start_pos
        
        if self.config.manual_goal_positions:
            if len(self.config.manual_goal_positions) != self.n_players:
                raise ValueError(f"Number of manual goal positions must match number of players. There are {self.n_players} players but {len(self.config.manual_goal_positions)} goal positions.")
            for player, pos in zip(self.players, self.config.manual_goal_positions):
                if not (0 <= pos[0] < self.grid_size and 0 <= pos[1] < self.grid_size):
                    raise ValueError(f"Invalid goal position {pos} for player {player.name}. Must be within grid size {self.grid_size}.")
                player.goal = pos
        else:
            for player in self.players:
                player.goal = (random.randint(self.grid_size - self.config.random_goal_block_size, self.grid_size - 1), random.randint(self.grid_size - self.config.random_goal_block_size, self.grid_size - 1))
    
    
    def initialize_fog_of_war(self):
        fog_of_war_settings = self.config.fog_of_war
        if isinstance(fog_of_war_settings, bool):
            for player in self.players:
                player.fog_of_war = fog_of_war_settings
        elif isinstance(fog_of_war_settings, list):
            if len(fog_of_war_settings) != self.n_players:
                raise ValueError(f"fog_of_war list must be the same length as number of players. There are {self.n_players} players but fog_of_war is of length {len(fog_of_war_settings)}.")
            for player, fog in zip(self.players, fog_of_war_settings):
                if not isinstance(fog, bool):
                    raise ValueError("fog_of_war list must contain only boolean values (True/False).")
                player.fog_of_war = fog
    
    
    def initialize_game_state(self):
        """Initialize the game state with player positions and resources."""
        state = {}
        for player in self.players:
            state[player.name] = {
                "model": player.model_name,
                "position": player.position,
                "goal": player.goal,
                "resources": dict(player.resources),
                "promised_to_give": dict(player.promised_resources_to_give) if self.pay4partner else None,
                "promised_to_receive": dict(player.promised_resources_to_receive) if self.pay4partner else None,
            }
        return state

    
    # 2. Core Game Loop
    def run(self):
        while self.running and not all(p.has_finished() for p in self.players):
            # Handle Pygame events only if GUI is enabled
            if self.display_gui:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                
                self.draw()
                self.clock.tick(FPS)
            
            # Always show console output
            self.print_game_state()
            self.handle_turn(self.players)
            
            self.update_game_state()
            if self.turn > 0:
                self.game_states.append(copy.deepcopy(self.game_state))

            if self.check_for_repeated_states():
                break
            
            # Handle turn delay
            print(f"End of turn {self.turn}. Waiting for next turn...")
            if self.config.wait_for_enter:
                input("Press Enter to proceed to the next turn...")
            
            self.turn += 1

        print("Game over!")
        self.print_game_state()
        
        # Calculate final scores
        scores = {p.name: (100 + 5 * sum(dict(p.resources).values())) if p.has_finished() else 0 
                 for p in self.players}
        
        # Print final scores
        print("\nFinal Scores:")
        for player_name, score in scores.items():
            print(f"{player_name}: {score} points")
        
        # Log final game state and metrics to combined logger
        self.logger.log_game_end(self.players, self.turn)

        # for player in self.players:
        #     print(f"message history for player {player.name}: {player.messages}")
        
        if self.display_gui:
            pygame.quit()


    def handle_turn(self, players):
        """
        Handle each player's turn:
        - If the player has already finished, skip their turn.
        - If the player has not finished, let them propose a trade and/or make a move.
        - Validate trades and moves before executing them.
        """
        print("\n" + "="*60)
        print(f"=== USER VIEW - TURN {self.turn} STARTS ===")
        print("="*60)
        
        # Initialize logging for this turn (and config on first turn)
        
        if self.turn == 0:
            self.logger.log_game_config(self.config, self.players, self.grid)
        self.logger.log_turn_start(self.turn)
        
        # Initialize turn summary and player data
        if self.with_context:
            self.current_turn_summary = {
                "trades": [],
                "moves": [],
                "pay4partner_actions": [],
                "player_states": {}
            }
        
        # Track player data for event logging
        player_turn_data = {}

        #TODO: consider either remove for loop (diplomacy-style simultaneous turns), or shuffle players each turn to be fair
        for player in players:
            player_label = player.get_player_label(self)
            if player.has_finished():
                if not self.pay4partner or not any(v > 0 for v in player.promised_resources_to_give.values()):
                    print(f"{player_label} ({player.model_name}) has already finished the game.")
                    continue
                print(f"{player_label} ({player.model_name}) has finished but has promised to cover some moves for their partner.")

            print(f"\n{player_label} ({player.model_name})'s turn:")
            
            # For first player of the turn, initialize both players' data
            if not player_turn_data:
                # Record both players' resources at the start of the turn
                for p in self.players:
                    player_turn_data[p.name] = {
                        'resources_start': dict(p.resources),  # Resources at start of turn before any trades
                        'position_start': p.position,
                        'trade_proposed': None,
                        'trade_proposal_outcome': 'none',
                        'trade_received': None,
                        'trade_response': 'none',
                        'resources_after_trades': None,
                        'move_made': None,
                        'position_end': None,
                        'resources_end': None,
                        'is_pay4partner': self.pay4partner  # Flag to indicate pay4partner mode
                    }

            trade_result = None
            move_result = None
            
            # create a contract if in contract mode
            if self.contract_type is not None:
                propose_trade = None
                if self.turn == 0:
                    
                    contracts = self.come_up_with_contract(self.players)
                    if contracts:
                        contract = contracts['contract']
                        print(f"contract made! {contract}")
                        self.contract = contract
                        for player in self.players:
                            if player.id == '0':
                                player.contract = contracts['contract_for_0']
                            elif player.id == '1':
                                player.contract = contracts['contract_for_1']
                        break
                    else:
                        print("contract not made, trying again.")

            # otherwise Handle trade proposal
            else:
                # Skip trade proposals for finished players (they can only fulfill promises, not make new ones)
                propose_trade = None
                if not player.has_finished():
                    propose_trade = player.propose_trade(self.grid, self)
            
            if propose_trade and propose_trade is not None:
                # Record the trade proposal
                player_turn_data[player.name]['trade_proposed'] = propose_trade
                
                trade_result = self.validate_trade(player, propose_trade)
                if trade_result["is_valid"]:
                    trade_executed = self.handle_trade(player, propose_trade, player_turn_data)
                    trade_result["executed"] = trade_executed
                    player_turn_data[player.name]['trade_proposal_outcome'] = 'accepted' if trade_executed else 'rejected'
                    
                    # Add trade to turn summary immediately
                    if self.with_context:
                        if not hasattr(self, 'current_turn_summary'):
                            self.current_turn_summary = {
                                "trades": [],
                                "moves": [],
                                "player_states": {}
                            }
                        other_player = next(p for p in self.players if p.name != player.name)
                        # Get the full responses from the players' message history
                        proposer_response = player.messages[-1]["content"] if player.with_message_history else ""
                        target_response = other_player.messages[-1]["content"] if other_player.with_message_history else ""
                        
                        trade_summary = {
                            "proposer": player.name,
                            "target": other_player.name,
                            "offered": propose_trade["resources_to_offer"],
                            "requested": propose_trade["resources_to_receive"],
                            "success": trade_executed,
                            "rejected": not trade_executed,
                            "proposer_response": proposer_response,
                            "target_response": target_response
                        }
                        self.current_turn_summary["trades"].append(trade_summary)
                else:
                    print(f"{player_label}'s trade proposal was invalid: {trade_result['message']}")
                    player_turn_data[player.name]['trade_proposal_outcome'] = 'invalid'
            elif self.contract_type is None:
                print(f"{player_label} chose not to trade")

            # Record resources after trades (before moves)
            player_turn_data[player.name]['resources_after_trades'] = dict(player.resources)
            
        # Handle moves after all trades are done
        for player in players:

            player_label = player.get_player_label(self)
            old_position = player.position
            
            # For finished players in pay4partner mode
            if player.has_finished():
                if not self.pay4partner or not any(v > 0 for v in player.promised_resources_to_give.values()):
                    continue
                # Skip their own moves but stay in the loop to potentially cover partner's moves
                move = None
            else:
                # Only try to move if not finished
                move = player.come_up_with_move(self, self.grid)
            if move is None:
                print(f"{player_label} did not move.")
                move_result = "no_move"
                player_turn_data[player.name]['move_type'] = 'no_move'
            else:
                if player.can_move_to(move, self.grid):
                    player.move(move, self.grid)
                    move_result = move
                    player_turn_data[player.name]['move_made'] = move
                    player_turn_data[player.name]['move_type'] = 'regular'  # Regular move using own resources
                    # Record which color was used
                    r, c = move
                    color = self.grid.get_color(r, c)
                    player_turn_data[player.name]['used_color'] = color
                    print(f"{player_label} moved to {move}.")
                elif player.can_move_to_with_promised(move, self.grid):
                    partner_agrees_to_pay = self.handle_pay4partner_move(player, move)
                    if partner_agrees_to_pay:
                        player.move(move, self.grid)
                        move_result = move
                        player_turn_data[player.name]['move_made'] = move
                        player_turn_data[player.name]['move_type'] = 'pay4partner'
                        # Record which player covered the move
                        partner = next((p for p in self.players if p.name != player.name), None)
                        if partner:
                            player_turn_data[player.name]['covered_by'] = partner.name
                            r, c = move
                            color = self.grid.get_color(r, c)
                            player_turn_data[player.name]['covered_color'] = color
                            # Add pay4partner action to turn summary
                            if self.with_context:
                                self.current_turn_summary["pay4partner_actions"].append({
                                    "type": "promise_fulfilled",
                                    "requester": player.name,
                                    "fulfiller": partner.name,
                                    "color": color,
                                    "response": partner.messages[-1]["content"] if partner.with_message_history else ""
                                })
                        print(f"{player_label} moved to {move} via pay4partner.")
                    else:
                        move_result = "partner declined to fulfill p4p promise"
                        # Get partner and color info
                        partner = next((p for p in self.players if p.name != player.name), None)
                        r, c = move
                        color = self.grid.get_color(r, c)
                        
                        # Record under the player who broke their promise
                        if partner:
                            if partner.name not in player_turn_data:
                                player_turn_data[partner.name] = {
                                    'position_start': partner.position,
                                    'position_end': partner.position,
                                    'resources_start': dict(partner.resources),
                                    'resources_end': dict(partner.resources),
                                    'is_pay4partner': self.pay4partner
                                }
                            # Record the broken promise but don't affect the move_type
                            player_turn_data[partner.name]['broke_promise_for'] = player.name
                            player_turn_data[partner.name]['promised_color'] = color
                        
                        # Record in turn summary
                        if self.with_context:
                            self.current_turn_summary["pay4partner_actions"].append({
                                "type": "promise_broken",
                                "requester": player.name,
                                "breaker": partner.name if partner else None,
                                "color": color,
                                "response": partner.messages[-1]["content"] if partner and partner.with_message_history else ""
                            })
                            # Also record the broken promise in the breaker's turn data
                            if partner:
                                if not hasattr(self, 'current_turn_summary'):
                                    self.current_turn_summary = {
                                        "trades": [],
                                        "moves": [],
                                        "pay4partner_actions": [],
                                        "player_states": {}
                                    }
                                self.current_turn_summary["pay4partner_actions"].append({
                                    "type": "broke_promise",
                                    "breaker": partner.name,
                                    "broke_for": player.name,
                                    "color": color,
                                    "response": partner.messages[-1]["content"] if partner and partner.with_message_history else ""
                                })
                elif self.contract is not None:
                    if move in (tuple(map(int, key.strip("()").split(","))) for key in self.contract.keys() if re.match(r"^\(\d+,\s*\d+\)$", key)):
                        self.handle_contract_move(player, move)
                        player.move(move, self.grid)
                        move_result = move
                        player_turn_data[player.name]['move_made'] = move
                        print(f"{player_label} moved to {move} under contract terms.")
                else:
                    move_result = "invalid_move"
            
            # Record final state
            player_turn_data[player.name]['position_end'] = player.position
            player_turn_data[player.name]['resources_end'] = dict(player.resources)
            
            # Collect actions for turn summary
            if self.with_context:
                # Get the full response from the player's message history
                response = player.messages[-1]["content"] if player.with_message_history else ""
                
                # Add the move summary
                move_summary = {
                    "player": player.name,
                    "from_pos": old_position,
                    "to_pos": move_result if isinstance(move_result, tuple) else None,
                    "success": isinstance(move_result, tuple),
                    "reason": "successful" if isinstance(move_result, tuple) else move_result,
                    "response": response,
                    # Add pay4partner info if relevant
                    "move_type": player_turn_data[player.name].get('move_type', 'regular'),
                    "covered_by": player_turn_data[player.name].get('covered_by'),
                    "covered_color": player_turn_data[player.name].get('covered_color'),
                    "promise_broken_by": player_turn_data[player.name].get('promise_broken_by'),
                    "promised_color": player_turn_data[player.name].get('promised_color')
                }
                self.current_turn_summary["moves"].append(move_summary)
                
                # Update all player states
                for p in self.players:
                    self.current_turn_summary["player_states"][p.name] = {
                        "position": p.position,
                        "goal": p.goal,
                        "distance_to_goal": p.distance_to_goal(),
                        "resources": dict(p.resources),
                        "has_finished": p.has_finished(),
                        "promised_to_give": dict(p.promised_resources_to_give) if self.pay4partner else None,
                        "promised_to_receive": dict(p.promised_resources_to_receive) if self.pay4partner else None,
                    }
                
                # If this is the last player, finalize and distribute the turn summary
                if player == players[-1]:
                    print("\n" + "="*60)
                    print("=== END USER VIEW ===")
                    print("="*60)
                    
                    # Log structured event data for each player
                    for p in self.players:
                        if p.name in player_turn_data:
                            self.logger.log_player_turn_summary(self.turn, p.name, player_turn_data[p.name])
                    
                    self.logger.log_turn_end(self.turn)
                    
                    for p in self.players:
                        if p.model_name != 'human':
                            # Each player gets their own personalized turn summary
                            player_specific_summary = p.format_turn_summary(self.current_turn_summary, self.turn, with_message_history=p.with_message_history)
                            p.messages.append({
                                "role": "system",
                                "content": player_specific_summary
                            })
                    # Store the complete turn summary
                    self.turn_summaries.append(self.current_turn_summary)
                    # Clear for next turn
                    delattr(self, 'current_turn_summary')
                    print("="*60 + "\n")

                    

    def handle_pay4partner_move(self, player, move):
        # TODO: currently only supports 2 player version as we're not keeping track of who owes whom what
        partner = next((p for p in self.players if p.name != player.name), None)
        r, c = move
        color = self.grid.get_color(r, c)
        partner_agrees = partner.agree_to_pay4partner(player, color, self, self.grid)
        if partner_agrees:
            partner.promised_resources_to_give[color] -= 1
            partner.resources[color] -= 1
            player.promised_resources_to_receive[color] -= 1
            player.resources[color] += 1
            print(f"{partner.name} agreed to pay4partner.")
            return True
        else:
            print(f"{partner.name} declined pay4partner, move not executed.")
            return False
    
    def handle_contract_move(self, player, move):
        partner = next((p for p in self.players if p.name != player.name), None)
        r, c = move
        color = self.grid.get_color(r, c)
        partner.resources[color] -= 1
        player.resources[color] += 1
        
    
    def handle_trade(self, player, propose_trade, player_turn_data):
        """
        Handle a trade proposal from a player.
        - Validate the trade proposal.
        - Execute the trade if the target player accepts.
        - Update player_turn_data with new resources after trade.
        Returns True if trade was executed, False otherwise.
        """
        try:
            # Validate the trade proposal
            validation_result = self.validate_trade(player, propose_trade)
            if not validation_result["is_valid"]:
                error_msg = f"Trade validation failed: {validation_result['message']}"
                print(error_msg)
                # Log validation failure to verbose log
                self.logger.log("trade_validation_failed", {
                    "player": player.name,
                    "message": validation_result['message']
                })
                return False

            # Get the other player (in 2-player game, it's always the non-proposer)
            other_player = next(p for p in self.players if p.name != player.name)
            resources_to_offer = propose_trade['resources_to_offer']
            resources_to_receive = propose_trade['resources_to_receive']

            # Get the other player's response to the trade
            trade_accepted = other_player.accept_trade(self.grid, self, propose_trade)
            
            if trade_accepted:
                # Execute the trade immediately
                if self.pay4partner is False:
                    # Execute the trade by swapping resources
                    for resource, quantity in resources_to_offer:
                        player.resources[resource] -= quantity
                        other_player.resources[resource] += quantity

                    for resource, quantity in resources_to_receive:
                        player.resources[resource] += quantity
                        other_player.resources[resource] -= quantity
                else:
                    # In pay4partner mode, update promised resources instead of actual resources
                    for resource, quantity in resources_to_offer:
                        player.promised_resources_to_give[resource] += quantity
                        other_player.promised_resources_to_receive[resource] += quantity

                    for resource, quantity in resources_to_receive:
                        player.promised_resources_to_receive[resource] += quantity
                        other_player.promised_resources_to_give[resource] += quantity
                    player.pay4partner_log.append({
                        "agreement_turn": self.turn,
                        "with": other_player.name,
                        "offered": resources_to_offer,
                        "requested": resources_to_receive,
                        "text_summary": f"On turn {self.turn}, {player.name} and {other_player.name} agreed that at some stage in the future, {player.name} would pay {resources_to_offer} to {other_player.name} in exchange for {other_player.name} at some stage in the future paying for {resources_to_receive} to {player.name}.",
                    })
                    other_player.pay4partner_log.append({
                        "agreement_turn": self.turn,
                        "with": player.name,
                        "offered": resources_to_receive,
                        "requested": resources_to_offer,
                        "text_summary": f"On turn {self.turn}, {player.name} and {other_player.name} agreed that at some stage in the future, {player.name} would pay {resources_to_offer} to {other_player.name} in exchange for {other_player.name} at some stage in the future paying for {resources_to_receive} to {player.name}.",
                    })

                # Update game state immediately after trade execution
                self.game_state[player.name]["resources"] = dict(player.resources)
                self.game_state[other_player.name]["resources"] = dict(other_player.resources)
                self.game_state[player.name]["promised_to_give"] = dict(player.promised_resources_to_give)
                self.game_state[player.name]["promised_to_receive"] = dict(player.promised_resources_to_receive)

                # Print trade outcome
                proposer_label = player.get_player_label(self)
                target_label = other_player.get_player_label(self)
                if self.pay4partner:
                    print(f"\nPay for partner trade accepted between {proposer_label} and {target_label}")
                else:
                    print(f"\nTrade accepted between {proposer_label} and {target_label}")
                print(f"- {proposer_label} now has: {dict(player.resources)}")
                print(f"- {target_label} now has: {dict(other_player.resources)}")
                if self.pay4partner:
                    print('Additionally:')
                    print(f"- {proposer_label} has promised to cover: {dict(player.promised_resources_to_give)}")
                    print(f"- {target_label} has promised to cover: {dict(other_player.promised_resources_to_give)}")

                # Update both players' resources_after_trades
                player_turn_data[player.name]['resources_after_trades'] = dict(player.resources)
                player_turn_data[other_player.name]['resources_after_trades'] = dict(other_player.resources)
                
                return True
            else:
                target_label = other_player.get_player_label(self)
                print(f"\nTrade rejected by {target_label}")
                return False

        except Exception as e:
            print(f"An error occurred while handling the trade: {e}")
            return False

    
    def come_up_with_contract(self, players):
        """
        Facilitates a contract negotiation between two players, formats the contract using a judge,
        and ensures both players agree to the final contract.
        """
        def message_starts_or_ends_with_agree(text):
    
            # Find all alphabetic words in the text
            words = re.findall(r"[a-zA-Z]+", text)
            # Return the last word if the list is not empty
            if words:
                return words[0] == 'agree' or words[-1] == "agree"
            return False
        print("attempting to create a contract")
        # Initialize conversation history for both players
        player_0 = players[0]
        player_1 = players[1]
        history_0 = [{"role": "system", "content": player_0.generate_contract_prompt(player_0.generate_player_context_message(self, self.grid))}]
        history_1 = [{"role": "system", "content": player_1.generate_contract_prompt(player_1.generate_player_context_message(self, self.grid))}]
        n_exchanges = 5

        # Seed the conversation
        initial_message = "Let's begin negotiation to come up with a contract. What would you like to propose?"
        history_0.append({"role": "user", "content": initial_message})
        response_1 = ""
        # history_1.append({"role": "assistant", "content": initial_message})

        # Alternating dialogue
        agree = False
        for turn in range(n_exchanges):  # Number of exchanges
            turn_message = f"Turn: {turn + 1}" if turn < n_exchanges - 1 else "Turn: {turn + 1} (final turn)"

            response_0 = player_0.get_completion(history_0)
            history_0.append({"role": "assistant", "content": response_0})
            history_1.append({"role": "user", "content": response_0})
            if message_starts_or_ends_with_agree(response_0.lower()) and message_starts_or_ends_with_agree(response_1.lower()):
                agree = True
                break

            # Player 1 replies
            response_1 = player_1.get_completion(history_1)
            history_1.append({"role": "assistant", "content": f"{turn_message}: {response_1}"})
            history_0.append({"role": "user", "content": f"{turn_message}: {response_1}"})

            if message_starts_or_ends_with_agree(response_0.lower()) and message_starts_or_ends_with_agree(response_1.lower()):
                agree = True
                break
        if agree == True:
            print("Agreement reached! Consulting judge to formalize contract.")
            
            print(f"Player 0's resources: {player_0.resources}")
            print(f"Player 0's messages: {history_0}")
            print(f"Player 1's messages: {history_1}")
            
            conversation_formatted = JUDGE.format_conversation_for_contract(history_0, players, history_pov=0)
            print(f"Formatted conversation for judge based off player 0:\n{conversation_formatted}")

            judge_contract = JUDGE.create_contract(conversation_formatted)
            print(f"Raw judge contract: {judge_contract}")
            contract_for_0 = JUDGE.format_contract_for_player(judge_contract, player_0)
            print(f"Contract for player 0:\n{contract_for_0}")
            
            contract_for_1 = JUDGE.format_contract_for_player(judge_contract, player_1)
            print(f"Contract for player 1:\n{contract_for_1}")
            

            history_0.append({"role": "user", "content": prompts.generate_agree_to_final_contract_prompt(contract_for_0)})
            
            history_1.append({"role": "user", "content": prompts.generate_agree_to_final_contract_prompt(contract_for_1)})

            agree_0 = player_0.get_completion(history_0)
            agree_1 = player_1.get_completion(history_1)

            if message_starts_or_ends_with_agree(agree_0) and message_starts_or_ends_with_agree(agree_1):
                print("Both players agreed to the final contract.")
                
                return {'contract': judge_contract, 'contract_for_0': contract_for_0, 'contract_for_1': contract_for_1}
            elif not message_starts_or_ends_with_agree(agree_0):
                print(f"{player_0.name} did not agree to the final contract.")
                print(f"{player_0.name}'s response: {agree_0}")
                return None
            elif not message_starts_or_ends_with_agree(agree_1):
                print(f"{player_1.name} did not agree to the final contract.")
                print(f"{player_1.name}'s response: {agree_1}")
                return None

    
    
    def validate_trade(self, player, propose_trade):
        """
        Validate a trade proposal.
        Returns a dictionary with the validation result, including:
        - is_valid: True/False
        - message: Error message if invalid
        - player_to_trade_with: The target player if valid
        """
        validation_result = {"is_valid": False, "message": "", "proposed trade": propose_trade}
        required_fields = ['resources_to_offer', 'resources_to_receive']
        if not all(field in propose_trade for field in required_fields):
            validation_result['message'] = "Missing required fields in trade proposal."
            return validation_result

        # In 2-player game, the other player is always the trade partner
        player_to_trade_with = next(
            (p for p in self.players if p.name != player.name),
            None
        )

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
            self.game_state[player.name]["promised_to_give"] = dict(player.promised_resources_to_give) if self.pay4partner else None
            self.game_state[player.name]["promised_to_receive"] = dict(player.promised_resources_to_receive) if self.pay4partner else None


    # 3. Game State and Metrics


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
            if self.pay4partner:
                print(f"Promised to cover for: {state['promised_to_give']}")
                print(f"Promised to be covered for: {state['promised_to_receive']}")
        

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