"""
- format_turn_summary_for_player: Format a turn's events from a player's perspective
- generate_turn_context: Generate complete game state and history for a player
"""

def format_turn_summary_for_player(turn_summary, turn_number, player_name, pay4partner=False, with_message_history=False):
    """Format turn summary with anonymized player names"""
    summary = [f"\n=== TURN {turn_number} ==="]
    
    # Trades
    if "trades" in turn_summary and turn_summary["trades"]:
        for trade in turn_summary["trades"]:
            proposer = "You" if trade['proposer'] == player_name else "The other player"
            target = "you" if trade['target'] == player_name else "the other player"
            
            summary.append(f"{proposer} proposed trade to {target}:")
            summary.append(f"- {proposer} offered: {trade['offered']}")
            summary.append(f"- {proposer} requested: {trade['requested']}")
            
            # Show proposer's response if it's the current player
            if trade['proposer'] == player_name:
                if with_message_history:
                    summary.append(f"You said: {trade.get('proposer_response', '')}")
            
            # Show acceptance/rejection based on who's the target
            if trade['target'] == player_name:
                # You were the target, so you made the decision
                if trade.get("success", False):
                    summary.append("You ACCEPTED the trade")
                    if with_message_history:
                        summary.append(f"You said: {trade.get('target_response', '')}")
                elif trade.get("rejected", False):
                    summary.append("You REJECTED the trade")
                    if with_message_history:
                        summary.append(f"You said: {trade.get('target_response', '')}")
            else:
                # The other player was the target, so they made the decision
                if trade.get("success", False):
                    summary.append("The other player ACCEPTED the trade")
                elif trade.get("rejected", False):
                    summary.append("The other player REJECTED the trade")
    
    # Pay4Partner Actions
    if "pay4partner_actions" in turn_summary and turn_summary["pay4partner_actions"]:
        for action in turn_summary["pay4partner_actions"]:
            if action["type"] == "promise_fulfilled":
                fulfiller = "You" if action["fulfiller"] == player_name else "The other player"
                requester = "you" if action["requester"] == player_name else "the other player"
                summary.append(f"PAY4PARTNER: {fulfiller} covered a {action['color']} move for {requester}")
                if action["fulfiller"] == player_name and with_message_history:
                    summary.append(f"You said: {action.get('response', '')}")
            elif action["type"] == "promise_broken":
                breaker = "You" if action["breaker"] == player_name else "The other player"
                requester = "you" if action["requester"] == player_name else "the other player"
                summary.append(f"PAY4PARTNER: {breaker} declined to cover a {action['color']} move for {requester}")
                if action["breaker"] == player_name and with_message_history:
                    summary.append(f"You said: {action.get('response', '')}")

    # Moves
    if "moves" in turn_summary and turn_summary["moves"]:
        for move in turn_summary["moves"]:
            player_ref = "You" if move['player'] == player_name else "The other player"
            if move["success"]:
                # Base move text
                move_text = f"MOVE: {player_ref} moved from {move['from_pos']} to {move['to_pos']}"
                
                # Add pay4partner details if relevant
                if move.get('move_type') == 'pay4partner':
                    other = "You" if move.get('covered_by') == player_name else "The other player"
                    move_text += f" ({other} covered the {move.get('covered_color')} chip)"
                
                summary.append(move_text)
                if move['player'] == player_name and with_message_history:
                    summary.append(f"You said: {move.get('response', '')}")
            else:
                if move["reason"] == "no_move":
                    summary.append(f"MOVE: {player_ref} did not move")
                elif move.get('move_type') == 'pay4partner_promise_broken':
                    breaker = "You" if move.get('promise_broken_by') == player_name else "The other player"
                    summary.append(f"MOVE FAILED: {breaker} declined to cover the promised {move.get('promised_color')} chip")
                
                if move['player'] == player_name and with_message_history:
                    summary.append(f"You said: {move.get('response', '')}")
    
    # End positions
    if "player_states" in turn_summary:
        summary.append("\nPOSITIONS:")
        for state_player_name, state in turn_summary["player_states"].items():
            player_ref = "You" if state_player_name == player_name else "The other player"
            status = "FINISHED!" if state['has_finished'] else f"at {state['position']}"
            summary.append(f"- {player_ref}: {status}, chips: {state['chips']}")
            if pay4partner:
                if state_player_name == player_name:
                    # For the current player
                    summary.append(f"  - promised to cover the other player with: {state['promised_to_give']}")
                    summary.append(f"  - were promised to be covered by the other player: {state['promised_to_receive']}")
                else:
                    # For the other player
                    summary.append(f"  - promised to cover for you: {state['promised_to_give']}")
                    summary.append(f"  - was promised to be covered by you: {state['promised_to_receive']}")

    return "\n".join(summary)


def generate_turn_context(game, player):
    """
    Generates a complete context message about the current turn, including:
    - Current game state (position, chips, etc.)
    - Recent turn history (last 3 turns)
    - Board layout
    """
    recent_history = ""
    if game.with_context and game.turn_summaries:
        history_entries = []
        recent_turns = game.turn_summaries[-5:]  # Get last 5 turns
        for turn_idx, turn in enumerate(recent_turns):
            turn_num = game.turn - (len(recent_turns) - turn_idx)
            history_entries.append(format_turn_summary_for_player(turn, turn_num, player.name, player.pay4partner, player.with_message_history))

        recent_history = "\nRecent turn history:\n" + "\n---\n".join(history_entries)

    current_turn = game.turn
    promised_resources_to_give_message = f"- Chips you have promised to cover for other player (still yours, not yet covered for them): {player.promised_resources_to_give}" if player.pay4partner else ''
    promised_resources_to_receive_message = f"- Chips you have been promised to be covered for by other player (still theirs, not yet covered for you): {player.promised_resources_to_receive}" if player.pay4partner else ''
    
    fog_of_war_context = "You are in fog of war mode. You can only see the colors of tiles adjacent to your current position. As you move to other tiles you will be able to see the colors of new adjacent tiles" if player.fog_of_war else ""

    # Get the other player's resources
    other_player = [p for p in game.players if p != player][0]
    other_resources = dict(other_player.resources)
    other_position = other_player.position

    best_paths_message = f"- Your best paths to your goal (although others may be possible) are: {player.best_routes(game.grid)[:2]}" if player.show_paths and not player.fog_of_war else ""
    
    

    return f"""
=== GAME STATUS FOR YOU - TURN {current_turn} ===

- You are at position {player.position}
- Your goal is at {player.goal}. 
- Your chip inventory: {dict(player.resources)}
{promised_resources_to_give_message}
{promised_resources_to_receive_message}
{best_paths_message}
- Considering potential paths to your goal: shorter paths require less chips, but a longer path for which you don't need to trade is also a strong option (as a backup plan or negotiation tool, but it means you finish with less chips than if you take the shorter path). A short path that you don't need to trade for is ideal, and your negotiation strategy should reflect this.

- The other player's goal is also {player.goal}. Note that because the other player likely has different chips to you, their best path to the goal may be different to yours.
- The other player's chips: {other_resources}
- The other player is at position {other_position}

BOARD LAYOUT: {fog_of_war_context}
{player.get_readable_board()}

{f"HISTORY OF EVENTS:\n{recent_history if recent_history else 'This is the first turn.'}" if game.with_context else ""}
"""


    
    