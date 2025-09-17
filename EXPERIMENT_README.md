# Experiment Framework

## Workflow Guide

1. **Setup Experiment Parameters** in `run_experiments.py`:
   ```python
   N_RUNS = 10                    # Number of runs per configuration
   AGENTS = [FOUR_1, FOUR_1]      # Fixed model agents for all experiments
   GRIDS_FILE = "experiment_configs/4x4_experiment_grids.yaml"  # Grid configurations
   PARAM_VARIATIONS = "parameter_variations_test"  # Parameter variations file
   ```

2. **Configure Parameter Combinations** in `experiment_configs/parameter_variations_test.yaml`:
   ```yaml
   # Each entry is a different configuration to test
   - pay4partner: true
     contract_type: none
     with_context: true
     with_message_history: false
     fog_of_war: [false, false]
   ```

3. **Run Experiments**:
   You can run experiments in several ways:
   ```bash
   # Run all grids
   python run_experiments.py

   # Run specific grid IDs
   python run_experiments.py --grid-id 0 1 2

   # Run a range of grid IDs
   python run_experiments.py --range 0 10
   ```

4. **Run Analysis**:
   ```bash
   python analyze_experiments.py
   ```
   This creates a timestamped CSV file with all runs: `logs/experiments/per_grid/all_runs_TIMESTAMP.csv`
   and also updates `all_runs_latest.csv`

## Directory Structure

```
logs/
└── experiments/
    └── per_grid/                     # All grid-based experiments
        └── BUCKET/                   # e.g., Independent_Both_have_optimal_paths
            └── grid_ID/             # e.g., grid_000
                └── CONFIG_DIR/      # e.g., ctx0_fog00_p4ptrue_contract_none
                    └── TIMESTAMP/   # e.g., 20250916_220014
                        ├── metadata.json      # Grid and run metadata
                        ├── event_log_game.json    # Structured game events
                        └── verbose_log_game.json  # Detailed game logs
```

### Directory Components:

- `per_grid`: Root directory for all grid-based experiments
- `BUCKET`: Grid category (e.g., "Independent_Both_have_optimal_paths")
- `grid_ID`: Unique identifier for each grid (e.g., "grid_000")
- `CONFIG_DIR`: Configuration settings with naming convention:
  - `ctx[0/1]`: Context enabled (1) or disabled (0)
  - `fog[00/01/10/11]`: Fog of war settings for each player
  - `p4p[true/false]`: Pay4Partner mode
  - `contract_[none/strict/natural]`: Contract type
- `TIMESTAMP`: When the run was executed (YYYYMMDD_HHMMSS)

### Fixed Settings for 4x4 Experiments

All experiments use these fixed settings:
```python
grid_size = 4
colors = ['R', 'B', 'G']
resource_mode = 'manual'
manual_resources = [
    {"R": 14, "B": 0, "G": 1},  # Player 0: Red chips + 1 Green
    {"R": 0, "B": 14, "G": 1}   # Player 1: Blue chips + 1 Green
]
```

### Metrics CSV Columns

The analysis produces a CSV with the following columns:
- Grid ID
- Bucket
- Sub-stratum
- Config ID
- Pay4Partner
- Context
- Fog of War
- Contract Type
- Total Turns
- Run ID (timestamp)
- Total Scores
- Score Player 0
- Score Player 1
- Gini Coefficient
- Max Possible Score
- Reached Goal Player 0
- Reached Goal Player 1

### Scoring Rules

- If you reach your goal: 10 points + 5 points per remaining chip
- If you don't reach your goal: 0 points

## Adding New Experiments

1. Add new grids to `experiment_configs/4x4_experiment_grids.yaml`
2. Add new parameter variations to `experiment_configs/parameter_variations_test.yaml`
3. Run experiments for specific grids or ranges using command line arguments
4. Analysis will automatically include all runs in the per_grid directory