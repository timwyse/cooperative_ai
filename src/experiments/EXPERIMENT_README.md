# Experiment Framework

## Quick Start

### Running Experiments

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Run experiments for a single model pair
python -m src.experiments.run_experiments --pairs FOUR_1,FOUR_1 --start-id 0 --end-id 99

# Run experiments for multiple model pairs
python -m src.experiments.run_experiments --pairs SONNET_4_5,SONNET_4_5 --pairs HAIKU_4_5,HAIKU_4_5 --start-id 0 --end-id 99

# Add experiments to an existing run folder
python -m src.experiments.run_experiments --pairs FOUR_1,FOUR_1 --run-folder 2026_01_08_17 --skip-completed

# Run with more workers for faster execution
python -m src.experiments.run_experiments --pairs FOUR_1,FOUR_1 --workers 12 --start-id 0 --end-id 50
```

### Available Model Pairs

| Model Name | Description |
|------------|-------------|
| `FOUR_1` | GPT 4.1 |
| `GPT_5_2` | GPT 5.2 |
| `SONNET_4_5` | Claude Sonnet 4.5 |
| `HAIKU_4_5` | Claude Haiku 4.5 |
| `HAIKU_3_5` | Claude Haiku 3.5 |

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--pairs A,B` | Model pair to run (can repeat for multiple) | `--pairs FOUR_1,FOUR_1` |
| `--start-id N` | Start from grid ID N (inclusive) | `--start-id 0` |
| `--end-id N` | Run until grid ID N (inclusive) | `--end-id 99` |
| `--workers N` | Number of parallel workers (default: 8) | `--workers 12` |
| `--add` | Add to most recent run folder | `--add` |
| `--run-folder` | Specify exact run folder | `--run-folder 2026_01_08_17` |
| `--skip-completed` | Skip already completed experiments | `--skip-completed` |

## Generating Metrics CSVs

After running experiments, generate CSV files with metrics:

```bash
# Generate from a specific run folder
python -m src.experiments.analyze_experiments --dir logs/experiments/per_grid/2026_01_08_17
```

This creates:
- `results/all_runs_latest.csv` - All experiments combined
- `results/by_model_pair/<MODEL_PAIR>_latest.csv` - Per-model breakdowns

### Final CSVs for Analysis

Copy the latest CSVs to `results/final/` for use in notebooks:

```bash
cp results/by_model_pair/FOUR_1-FOUR_1_latest.csv results/final/FOUR_1-FOUR_1.csv
cp results/by_model_pair/SONNET_4_5-SONNET_4_5_latest.csv results/final/SONNET_4_5-SONNET_4_5.csv
cp results/by_model_pair/HAIKU_4_5-HAIKU_4_5_latest.csv results/final/HAIKU_4_5-HAIKU_4_5.csv
```

The `results/final/` directory contains:
- `FOUR_1-FOUR_1.csv` - GPT 4.1 experiments
- `SONNET_4_5-SONNET_4_5.csv` - Sonnet 4.5 experiments
- `HAIKU_4_5-HAIKU_4_5.csv` - Haiku 4.5 experiments

These are used by `Model_Comparison_Analysis.ipynb` for generating comparison graphs.

## Experiment Configuration

### Parameter Variations

Experiments use configurations from `experiment_configs/parameter_variations.yaml`:

```yaml
# Example variation
- pay4partner: false
  contract_type: none
  with_message_history: true
  fog_of_war: [false, false]
  selfish: [true, true]
```

**Contract Types:**
- `none` - No contract enforcement
- `strict` - Judge enforces contract moves (players can only move on contracted tiles)
- `contract_for_finishing` - Contract specifies bonus for reaching goal
- `tile_with_judge_implementation` - Judge creates fair contract based on negotiation

**Game Modes:**
- `pay4partner: false` - Regular Trading (direct chip trades)
- `pay4partner: true` - Pay4Partner (promise-based payments)

### Grid Buckets

Experiments run on grids from `experiment_configs/4x4_experiment_grids.yaml`:

| Bucket | Description | Grid IDs |
|--------|-------------|----------|
| Independent_Both_have_optimal_paths | Both players can reach goal independently | 0-39 |
| Mutual_Dependency | Both players need each other to succeed | 40-79 |
| Needy_Player_Blue | Player 1 (Blue) needs Player 0's help | 80-119 |

## Directory Structure

```
logs/
└── experiments/
    └── per_grid/
        └── <RUN_TIMESTAMP>/              # e.g., 2026_01_08_17
            └── <MODEL_PAIR>/             # e.g., FOUR_1-FOUR_1
                └── <BUCKET>/             # e.g., Mutual_Dependency
                    └── grid_<ID>/        # e.g., grid_042
                        └── <CONFIG>/     # e.g., ctx1_fog00_p4pfalse_contract_strict_selfish11
                            └── <TIMESTAMP>_<RUN_ID>/
                                ├── metadata.json
                                ├── event_log_*.json
                                └── verbose_log_*.json
```

### Config Directory Naming Convention

`ctx1_fog00_p4pfalse_contract_strict_selfish11`

- `ctx[0/1]` - Context enabled (always 1)
- `fog[00/01/10/11]` - Fog of war per player (always 00)
- `p4p[true/false]` - Pay4Partner mode
- `contract_<type>` - Contract type
- `selfish[00/11]` - Selfish prompt per player (always 11)

## Analysis Notebooks

### Model Comparison Analysis

`Model_Comparison_Analysis.ipynb` - Compare model performance across:
- Success rates by bucket and contract type
- Average player scores
- Trade activity and negotiation length
- Contract acceptance rates
- Format error rates

### Cooperation & Defection Analysis

`Cooperation_Defection_Analysis.ipynb` - Analyze:
- Negotiation length patterns
- Contract acceptance rates
- Strict contract defection rates
- P4P promise-keeping vs breaking
- Trade rejection patterns

## Metrics CSV Columns

| Column | Description |
|--------|-------------|
| Grid ID | Unique grid identifier |
| Bucket | Grid category |
| Model Pair | Agent models used |
| Pay4Partner | P4P mode (True/False) |
| Contract Type | none/strict/contract_for_finishing/tile_with_judge_implementation |
| Total Turns | Game length |
| Total Score | Combined score of both players |
| Score Player 0/1 | Individual player scores |
| Reached Goal Player 0/1 | Whether player reached goal |
| Non-Cooperative Baseline Player 0/1 | Score if playing alone |
| Gini Coefficient | Score inequality (0=equal, 1=unequal) |
| Total Trades Proposed/Accepted | Trade activity |
| Contract Accepted | Whether contract was agreed |
| Format Errors Total | Parsing/API errors |

## Scoring Rules

- **Reaching goal:** 20 points + 5 points per remaining chip
- **Not reaching goal:** 0 points (all chips worthless)

## Complete Workflow: Run Experiments → Generate CSVs → Plot Graphs

### Step 1: Run Experiments

```bash
source .venv/bin/activate

# Run all grids (0-119) for your model
python run_experiments.py --pairs FOUR_1,FOUR_1 --start-id 0 --end-id 119
```

This creates logs in `logs/experiments/per_grid/<TIMESTAMP>/<MODEL_PAIR>/`

### Step 2: Generate Metrics CSV

```bash
# Point to your run folder (check the timestamp from Step 1)
python analyze_experiments.py --dir logs/experiments/per_grid/2026_01_08_17
```

This creates `results/by_model_pair/<MODEL_PAIR>_latest.csv`

### Step 3: Copy to Final Directory

```bash
# Copy to results/final/ where the notebook reads from
cp results/by_model_pair/FOUR_1-FOUR_1_latest.csv results/final/FOUR_1-FOUR_1.csv
```

### Step 4: Generate Graphs

Open `Model_Comparison_Analysis.ipynb` and run all cells. The notebook loads CSVs from `results/final/`.

---

## Other Workflows

### Continue Incomplete Run

```bash
# Resume with skip-completed to avoid re-running finished experiments
python run_experiments.py --pairs MODEL_A,MODEL_A --run-folder 2026_01_08_17 --skip-completed
```

### Check for Errors in Logs

```python
import json
import glob

logs = glob.glob('logs/experiments/per_grid/2026_01_08_17/**/**/event_log*.json', recursive=True)
for log in logs:
    with open(log) as f:
        data = json.load(f)
    errors = data.get('game', {}).get('final_state', {}).get('metrics', {}).get('format_errors_total', 0)
    if errors > 0:
        print(f"{log}: {errors} errors")
```
