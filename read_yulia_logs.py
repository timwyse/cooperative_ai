import json
import sys
from pathlib import Path
import ast

def format_messages(messages):
    """Format message history in a readable way"""
    formatted = []
    for msg in messages:
        formatted.append(f"\n{msg['role'].upper()}:")
        content = msg['content']
        # Truncate very long messages
        if len(content) > 5000:
            content = content[:500] + "...[truncated]"
        formatted.append(content)
        formatted.append("-" * 50)
    return "\n".join(formatted)

def read_yulia_logs(filename):
    with open(filename, 'r') as f:
        log_entry = json.loads(f.read())
        game_state = log_entry['details']
        
        # Parse game config
        config = ast.literal_eval(game_state['game_config'])
        print("\n=== GAME CONFIGURATION ===")
        print(f"Total Turns: {config['total_turns']}")
        print(f"Context Enabled: {config['context_enabled']}")
        print(f"Grid Size: {config['grid_size']}")
        print(f"Colors: {config['colors']}")
        
        # Parse final turn summary
        print("\n=== FINAL TURN SUMMARY ===")
        final_turn = ast.literal_eval(game_state['final_turn_summary'])
        
        if final_turn['trades']:
            print("\nTrades:")
            for trade in final_turn['trades']:
                print(f"- {trade['proposer']} proposed trade with {trade['target']}")
                print(f"  Offered: {trade['offered']}")
                print(f"  Requested: {trade['requested']}")
                print(f"  Success: {trade['success']}")
        else:
            print("\nNo trades in final turn")
            
        print("\nMoves:")
        for move in final_turn['moves']:
            if move['success']:
                print(f"- {move['player']} moved from {move['from_pos']} to {move['to_pos']}")
            else:
                print(f"- {move['player']}: {move['reason']}")
        
        print("\nFinal Player States:")
        for player_name, state in final_turn['player_states'].items():
            print(f"\n{player_name}:")
            print(f"- Position: {state['position']}")
            print(f"- Distance to goal: {state['distance_to_goal']}")
            print(f"- Resources: {state['resources']}")
            if state['has_finished']:
                print("- Has reached their goal!")
        
        # Parse player histories
        print("\n=== PLAYER MESSAGE HISTORIES ===")
        histories = ast.literal_eval(game_state['player_histories'])
        for player_name, history in histories.items():
            print(f"\nPlayer: {player_name}")
            print(f"Model: {history['model']}")
            print(f"Message History Enabled: {history['with_message_history']}")
            
            if history['with_message_history'] == True:
                print("\nMessages:")
                messages = history['messages']
                print(format_messages(messages))
            else:
                print("Message history disabled")

if __name__ == "__main__":
    # Get the most recent yulia log file
    log_files = sorted(Path('.').glob('yulia_logs_*.jsonl'))
    if not log_files:
        print("No yulia log files found!")
        sys.exit(1)
    
    latest_log = log_files[-1]
    print(f"Reading log file: {latest_log}")
    read_yulia_logs(latest_log)