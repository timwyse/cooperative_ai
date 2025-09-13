"""
- format_turn_summary_for_player: Format a turn's events from a player's perspective
- generate_turn_context: Generate complete game state and history for a player
"""

def format_turn_summary_for_player(turn_summary, turn_number, player_name, pay4partner=False):
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
                summary.append(f"You said: {trade.get('proposer_response', '')}")
            
            # Show acceptance/rejection based on who's the target
            if trade['target'] == player_name:
                # You were the target, so you made the decision
                if trade.get("success", False):
                    summary.append("You ACCEPTED the trade")
                    summary.append(f"You said: {trade.get('target_response', '')}")
                elif trade.get("rejected", False):
                    summary.append("You REJECTED the trade")
                    summary.append(f"You said: {trade.get('target_response', '')}")
            else:
                # The other player was the target, so they made the decision
                if trade.get("success", False):
                    summary.append("The other player ACCEPTED the trade")
                elif trade.get("rejected", False):
                    summary.append("The other player REJECTED the trade")
    
    # Moves
    if "moves" in turn_summary and turn_summary["moves"]:
        for move in turn_summary["moves"]:
            player_ref = "You" if move['player'] == player_name else "The other player"
            if move["success"]:
                summary.append(f"MOVE: {player_ref} moved from {move['from_pos']} to {move['to_pos']}")
                if move['player'] == player_name:
                    summary.append(f"You said: {move.get('response', '')}")
            else:
                if move["reason"] == "no_move":
                    summary.append(f"MOVE: {player_ref} did not move")
                    if move['player'] == player_name:
                        summary.append(f"You said: {move.get('response', '')}")
    
    # End positions
    if "player_states" in turn_summary:
        summary.append("\nPOSITIONS:")
        for state_player_name, state in turn_summary["player_states"].items():
            player_ref = "You" if state_player_name == player_name else "The other player"
            status = "FINISHED!" if state['has_finished'] else f"at {state['position']}"
            summary.append(f"- {player_ref}: {status}, resources: {state['resources']}")
            if pay4partner:
                summary.append(f"  - promised to give: {state['promised_to_give']}")
                summary.append(f"  - promised to receive: {state['promised_to_receive']}")

    return "\n".join(summary)


def generate_turn_context(game, player):
    """
    Generates a complete context message about the current turn, including:
    - Current game state (position, resources, etc.)
    - Recent turn history (last 3 turns)
    - Board layout
    """
    recent_history = ""
    if game.with_context and game.turn_summaries:
        history_entries = []
        recent_turns = game.turn_summaries[-3:]  # Get last 3 turns
        for turn_idx, turn in enumerate(recent_turns):
            turn_num = game.turn - (len(recent_turns) - turn_idx)
            history_entries.append(format_turn_summary_for_player(turn, turn_num, player.name, player.pay4partner))

        recent_history = "\nRecent turn history:\n" + "\n---\n".join(history_entries)

    current_turn = game.turn
    promised_resources_to_give_message = f"- Resources you have promised to give to other players (still yours, not yet given): {player.promised_resources_to_give}" if player.pay4partner else ''
    promised_resources_to_receive_message = f"- Resources you have been promised to receive from other players (still theirs, not yet received): {player.promised_resources_to_receive}" if player.pay4partner else ''
    best_path = player.best_routes(game.grid)[0]['path']
    fog_of_war_context = "You are in fog of war mode. You can only see the colors of tiles adjacent to your current position. As you move to other tiles you will be able to see the colors of new adjacent tiles" if player.fog_of_war else ""

    return f"""
=== GAME STATUS FOR YOU - TURN {current_turn} ===

- You are at position {player.position}
- Your goal is at {player.goal}
- Your resources: {dict(player.resources)}
{promised_resources_to_give_message}
{promised_resources_to_receive_message}
- Distance to goal: {player.distance_to_goal()} steps
- Your estimated best path to your goal (although other paths are possible): {best_path}

BOARD LAYOUT: {fog_of_war_context}
{player.get_readable_board()}

HISTORY OF EVENTS:
{recent_history if recent_history else "This is the first turn."}
"""
