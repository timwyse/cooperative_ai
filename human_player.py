from typing import List, Tuple, Optional

class HumanPlayer:
    """All console I/O for a human-controlled player.
    """
    @staticmethod
    def get_move(player, grid) -> Optional[Tuple[int, int]]:
        print(f"{player.name}, it's your turn to make a move.")
        while True:
            move = input(
                "Enter your move: type row and column as 'row,col' (e.g., 2,1 to move to row 2 column 1. "
                "Note that rows and columns are 0- indexed), or use W/A/S/D for directions, or type 'n' to skip: "
            ).strip().lower()
            if move == 'n':
                return None
            elif move in ['w', 'a', 's', 'd']:
                if move == 'w':
                    r, c = player.position[0] - 1, player.position[1]
                elif move == 'a':
                    r, c = player.position[0], player.position[1] - 1
                elif move == 's':
                    r, c = player.position[0] + 1, player.position[1]
                elif move == 'd':
                    r, c = player.position[0], player.position[1] + 1
            else:
                try:
                    r, c = map(int, move.split(","))
                except ValueError:
                    print("Invalid input: Please enter the row and column in r,c format or use WASD. Try again.")
                    continue
            try:
                new_pos = (r, c)
                if not (0 <= r < player.grid_size and 0 <= c < player.grid_size):
                    print("Invalid move: The position is out of bounds. Try again.")
                    continue
                if new_pos not in grid.get_adjacent(player.position):
                    print("Invalid move: You can only move to an adjacent tile. Try again.")
                    continue
                return new_pos
            except (ValueError, IndexError):
                print("Invalid input: Please enter the new tile in r,c format. Try again.")

    @staticmethod
    def _get_resource_list(player, prompt_text: str) -> List[Tuple[str, int]]:
        resources = []
        i = 1
        while True:
            message = f"{i}st resource:" if i == 1 else "next resource:"
            print(message)
            resource = input(prompt_text).strip()
            if resource == '.':
                break
            if resource in player.colors:
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
                print(f"Invalid resource. Available resources: {player.colors}.")
        return resources

    @staticmethod
    def propose_trade(player, grid, game):
        trade_message_for_human = f"{player.name}, it's your turn to propose a trade."
        if player.pay4partner:
            trade_message_for_human += (
                "\nNote: You are in 'pay for other' mode, so you will pay the other player to move onto tiles "
                "of your color as agreed instead of direct swapping of resources."
            )
        print(trade_message_for_human)
        make_trade = input("Do you want to make a trade? y/n ").strip().lower()
        if make_trade != 'y':
            return None

        print("Enter the resources you want to offer (type '.' if you have finished):")
        resources_to_offer = HumanPlayer._get_resource_list(player, "Resource to offer (color): ")
        if not resources_to_offer:
            print("You must offer at least one resource.")
            return None

        print("Enter the resources you want to receive (type '.' if you have finished):")
        resources_to_receive = HumanPlayer._get_resource_list(player, "Resource to receive (color): ")
        if not resources_to_receive:
            print("You must request at least one resource.")
            return None

        trade_proposal = {
            "resources_to_offer": resources_to_offer,
            "resources_to_receive": resources_to_receive
        }
        return player.clean_trade_proposal(trade_proposal, grid, game)

    @staticmethod
    def accept_trade(player, grid, game, trade) -> bool:
        resources_to_offer = trade['resources_to_offer']
        resources_to_receive = trade['resources_to_receive']

        accept_message = f"{player.name} accepted the trade proposal. \n"
        reject_message = f"{player.name} rejected the trade proposal. \n"

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

    @staticmethod
    def agree_to_pay4partner(player, other_player, color) -> bool:
        print(f"{player.name}, {other_player.name} is invoking 'pay for partner' and asking you to pay "
              f"for their move onto a {color} tile.")
        while True:
            agree = input("Do you agree to this? y/n ").strip().lower()
            if agree not in ('y', 'n'):
                print("Please enter 'y' or 'n'.")
                continue
            return agree == 'y'
