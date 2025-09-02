#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime

def format_message_content(content, truncate=True):
    if not content:
        return ""
    
    content = content.replace('\\n', '\n')
    content = content.replace('\\"', '"')
    content = content.replace('\\\'', "'")
    
    if truncate and len(content) > 1000:
        lines = content.split('\n')
        if len(lines) > 20:
            content = '\n'.join(lines[:15]) + f"\n... [truncated {len(lines)-15} more lines] ..."
        else:
            content = content[:1000] + "... [truncated]"
    
    return content

def read_complete_logs(yulia_log_file, truncate=True, save_to_file=None):
    yulia_path = Path(yulia_log_file)
    game_log_path = Path("logs/game_log.jsonl")
    
    if not yulia_path.exists():
        print(f"Error: Yulia log file {yulia_log_file} not found.")
        return
    
    output_lines = []
    
    def output_print(text=""):
        if save_to_file:
            output_lines.append(text)
        else:
            print(text)
    
    output_print(f"Reading complete game logs")
    output_print("=" * 80)
    
    yulia_entries = []
    try:
        with open(yulia_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    log_entry = json.loads(line)
                    event_type = log_entry.get('event_type', log_entry.get('event', 'unknown'))
                    details = log_entry.get('details', {})
                    
                    if event_type != 'final_game_state':
                        player = details.get('player', 'unknown')
                        turn = details.get('turn', 'unknown')
                        decision_type = details.get('decision_type', 'unknown')
                        full_context = details.get('full_context', [])
                        timestamp = log_entry.get('timestamp', '')
                        
                        yulia_entries.append({
                            'timestamp': timestamp,
                            'turn': turn,
                            'player': player,
                            'decision_type': decision_type,
                            'full_context': full_context,
                            'type': 'prompt'
                        })
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print(f"Yulia log file not found: {yulia_log_file}")
        return
    
    game_entries = []
    if game_log_path.exists():
        try:
            with open(game_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        log_entry = json.loads(line)
                        event = log_entry.get('event', 'unknown')
                        details = log_entry.get('details', {})
                        timestamp = log_entry.get('timestamp', '')
                        
                        if event in ['trade_proposal', 'move_proposal', 'accept_trade_response']:
                            player = details.get('player', 'unknown')
                            message = details.get('message', '')
                            
                            game_entries.append({
                                'timestamp': timestamp,
                                'player': player,
                                'event': event,
                                'message': message,
                                'type': 'response'
                            })
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            output_print("No game_log.jsonl found - will show prompts only")
    
    all_entries = yulia_entries + game_entries
    all_entries.sort(key=lambda x: x.get('timestamp', ''))
    
    current_turn = None
    current_player = None
    prompt_entry = None
    
    for entry in all_entries:
        if entry['type'] == 'prompt':
            if prompt_entry:
                display_prompt_response_pair(prompt_entry, None, truncate, output_print)
            
            prompt_entry = entry
            
            if current_turn != entry['turn']:
                current_turn = entry['turn']
                output_print(f"\n" + "="*80)
                output_print(f"TURN {current_turn}")
                output_print("="*80)
            
            if current_player != entry['player']:
                current_player = entry['player']
                output_print(f"\n {current_player}")
                output_print("-" * 40)
        
        elif entry['type'] == 'response' and prompt_entry:
            if (entry['player'] == prompt_entry['player'] and 
                is_matching_response(prompt_entry['decision_type'], entry['event'])):
                display_prompt_response_pair(prompt_entry, entry, truncate, output_print)
                prompt_entry = None
    
    if prompt_entry:
        display_prompt_response_pair(prompt_entry, None, truncate, output_print)
    
    # Save to file if requested
    if save_to_file and output_lines:
        if save_to_file == "auto":
            import re
            import os
            yulia_filename = Path(yulia_log_file).name
            timestamp_match = re.search(r'yulia_logs_(\d{8}_\d{6})\.jsonl', yulia_filename)
            
            formatted_logs_dir = "logs/formatted_txt_logs"
            os.makedirs(formatted_logs_dir, exist_ok=True)
            
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                save_to_file = f"{formatted_logs_dir}/formatted_logs_{timestamp}.txt"
            else:
                save_to_file = f"{formatted_logs_dir}/formatted_logs.txt"
        
        try:
            with open(save_to_file, 'w') as f:
                for line in output_lines:
                    f.write(line + '\n')
            print(f"Formatted logs saved to: {save_to_file}")
        except Exception as e:
            print(f"Error saving to file: {e}")

def is_matching_response(decision_type, event):
    matches = {
        'trade_proposal': 'trade_proposal',
        'move': 'move_proposal',
        'trade_acceptance': 'accept_trade_response'
    }
    return matches.get(decision_type) == event

def display_prompt_response_pair(prompt_entry, response_entry, truncate=True, output_func=print):
    output_func(f"\n Decision: {prompt_entry['decision_type']}")
    
    full_context = prompt_entry['full_context']
    if full_context:
        output_func(f"\n AI PROMPTS:")
        output_func("─" * 60)
        
        if isinstance(full_context, str):
            try:
                import ast
                full_context = ast.literal_eval(full_context)
            except:
                output_func(f"Raw context: {format_message_content(full_context, truncate)}")
                return
        
        if isinstance(full_context, list):
            for msg in full_context:
                if isinstance(msg, dict):
                    role = msg.get('role', 'unknown').upper()
                    content = format_message_content(msg.get('content', ''), truncate)
                    
                    if role == 'SYSTEM':
                        output_func(f"\n SYSTEM (Game Rules):")
                    elif role == 'USER':
                        output_func(f"\n USER (Game State & Request):")
                    elif role == 'ASSISTANT':
                        output_func(f"\n ASSISTANT (Previous Response):")
                    
                    if content:
                        for line in content.split('\n'):
                            if line.strip():
                                output_func(f"   {line}")
    
    output_func(f"\n AI ACTION:")
    output_func("─" * 20)
    if response_entry:
        message = response_entry['message'].strip()
        if message:
            output_func(f"   AI Response: {message}")
        else:
            output_func("  Empty response")
    else:
        output_func("   No matching response found in game logs")
    
    output_func()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_complete_logs.py <yulia_log_file.jsonl> [options]")
        print("Options:")
        print("  --no-truncate    Show full content without truncation")
        print("  --save <file>    Save formatted output to file")
        print("  --save auto      Auto-generate filename with same timestamp as yulia log")
        print("\nExamples:")
        print("  python read_complete_logs.py yulia_logs_20250902_121505.jsonl")
        print("  python read_complete_logs.py yulia_logs_20250902_121505.jsonl --no-truncate")
        print("  python read_complete_logs.py yulia_logs_20250902_121505.jsonl --save formatted_logs.txt")
        print("  python read_complete_logs.py yulia_logs_20250902_121505.jsonl --save auto")
        print("  python read_complete_logs.py yulia_logs_20250902_121505.jsonl --no-truncate --save auto")
        print("\nThis script will read both the yulia logs (AI prompts) and game_log.jsonl (AI responses)")
        sys.exit(1)
    
    yulia_log_file = sys.argv[1]
    truncate = True
    save_to_file = None
    
    # Parse options
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--no-truncate':
            truncate = False
            print("Running with no truncation - showing full content")
            i += 1
        elif sys.argv[i] == '--save' and i + 1 < len(sys.argv):
            save_to_file = sys.argv[i + 1]
            print(f"Will save formatted output to: {save_to_file}")
            i += 2  # Skip both --save and the filename
        else:
            print(f"Unknown option: {sys.argv[i]}")
            sys.exit(1)
    
    read_complete_logs(yulia_log_file, truncate, save_to_file)
