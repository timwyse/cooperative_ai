# Experiment Framework

## Workflow Guide

1. **Setup Experiment Parameters** in `run_experiments.py`:
   ```python
   N_RUNS = 5                     # Set number of runs to average over
   BOARD_CONFIG = "yv_max_trade"  # Select your board configuration
   AGENTS = [FOUR_1, FOUR_1]      # Select your model agents
   ```

2. **Configure Parameter Combinations** in `experiment_configs/parameter_variations_test.yaml`, you can also add your yaml and change the path in `run_experiments.py`:
   ```yaml
   # Each entry is a different configuration to test
   - pay4partner: true
     contract_type: none
     with_context: true
     # ... other parameters
   ```

3. **Run Experiments**:
   ```bash
   python run_experiments.py
   ```
   This creates a timestamped directory in `logs/experiments/TIMESTAMP/`

4. **Run Analysis**:
   ```bash
   python analyze_experiments.py
   ```
   This automatically analyzes the latest experiment run

5. **Get Results**:
   - Find your metrics CSV in:
     ```
     logs/experiments/TIMESTAMP/yv_max_trade/analysis/yv_max_trade_FOUR_1-FOUR_1_metrics.csv
     ```
   - The CSV contains averaged metrics for each parameter combination:
     - N_runs (number of runs averaged)
     - Success rates
     - Average turns and scores
     - etc.


## Directory Structure

```
logs/
└── experiments/
    └── TIMESTAMP/                      # e.g., 2025-09-15_10-30-22
        └── BOARD_NAME/                 # e.g., yv_max_trade
            ├── analysis/               # Aggregated metrics
            │   └── BOARD_NAME_MODEL-PAIR_metrics.csv  # e.g., yv_max_trade_FOUR_1-FOUR_1_metrics.csv
            └── MODEL-PAIR/             # e.g., FOUR_1-FOUR_1
                └── CONFIG_MODE/        # e.g., pay4partner_true_contract_none
                    ├── run_ctx0_fog00_000/  # Individual run directory
                    │   ├── event_log_*.json    # Structured game events
                    │   └── verbose_log_*.json  # Detailed game logs
                    ├── run_ctx0_fog00_001/
                    └── ...
```

### Directory Components:

- `TIMESTAMP`: When the experiment batch started (YYYY-MM-DD_HH-MM-SS)
- `BOARD_NAME`: Name of the board configuration used (e.g., "yv_max_trade")
- `MODEL-PAIR`: Models used for the players (e.g., "FOUR_1-FOUR_1")
- `CONFIG_MODE`: Combination of settings:
  - `pay4partner_[true/false]`: Whether Pay4Partner mode is enabled
  - `contract_[none/strict/natural]`: Contract type used
- `run_*`: Individual run directories with naming convention:
  - `ctx[0/1]`: Context enabled (1) or disabled (0)
  - `fog[00/01/10/11]`: Fog of war settings for each player
  - `[000-999]`: Run number


### Parameter Variations (experiment_configs/parameter_variations_test.yaml)
```yaml
- wait_for_enter: false
  display_gui: false
  with_context: false
  with_message_history: false
  pay4partner: true
  contract_type: none
  fog_of_war: [false, false]
# ... more configurations
```

### Board Configuration (configs/BOARD_NAME.yaml)
Contains board-specific settings like grid size, colors, and initial resource distribution.

### Metrics Table Columns
- Configuration: Human-readable config name
- N_runs: Number of runs averaged
- Pay4Partner: Whether Pay4Partner mode was enabled
- Contract Type: Type of contract used
- Context: Whether context was enabled
- Message History: Whether message history was enabled
- Fog of War: Fog of war settings for each player
- Avg Turns: Mean and std dev of turns taken
- Avg Score: Mean and std dev of total scores
- Min/Max Score: Score range
- Player Success Rates: % of runs where each player reached goal
- Both Players Success Rate: % of runs where both players succeeded

## Adding New Experiments

1. Create new parameter variations in `experiment_configs/`
2. Add new board configurations in `configs/`
3. Modify `run_experiments.py` settings:
   ```python
   BOARD_CONFIG = "your_board_name"  # without .yaml extension
   PARAM_VARIATIONS = "your_variations_file"  # without .yaml extension
   AGENTS = [FOUR_1, FOUR_1]  # or other model combinations
   N_RUNS = 5  # number of runs per configuration
   ```
