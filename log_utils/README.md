# Log Utils

This directory contains utilities for reading and analyzing game logs.

## Scripts

- `read_complete_logs.py` - Main script for reading and formatting both AI prompts and responses

## Usage

From the main project directory:

```bash
# List available logs
python read_logs.py

# Read a specific log (just filename needed)
python read_logs.py yulia_logs_20250902_121505.jsonl

# Read with full content (no truncation)
python read_logs.py yulia_logs_20250902_121505.jsonl --no-truncate

# Save to file
python read_logs.py yulia_logs_20250902_121505.jsonl --save formatted_output.txt

# Auto-generate filename with same timestamp as yulia log
python read_logs.py yulia_logs_20250902_121505.jsonl --save auto

# Full content saved with auto-generated filename
python read_logs.py yulia_logs_20250902_121505.jsonl --no-truncate --save auto
```

## Direct Usage

You can also run the script directly:

```bash
cd log_utils
python read_complete_logs.py ../logs/yulia_agent_prompt_logs/yulia_logs_20250902_121505.jsonl --no-truncate
```

## Directory Structure

```
logs/
├── game_log.jsonl                     # Main game events and AI responses
├── yulia_agent_prompt_logs/           # AI prompts sent to agents
│   └── yulia_logs_TIMESTAMP.jsonl
└── formatted_txt_logs/                # Human-readable formatted logs
    └── formatted_logs_TIMESTAMP.txt
```

## Output Format

The script combines two types of logs:
- **Yulia logs** (`logs/yulia_agent_prompt_logs/`) - AI prompts sent to agents
- **Game logs** (`logs/game_log.jsonl`) - AI responses and game events

Formatted output is saved to `logs/formatted_txt_logs/` and organized by:
1. Turn number
2. Player name
3. Decision type (trade_proposal, move, trade_acceptance)
4. AI prompts (what the AI saw)
5. AI actions (what the AI decided)
