# Cooperative AI Colored Trails Framework

This repository provides a research framework for running **Colored Trails**-style games and experiments. Colored Trails is a multi-agent bargaining and coordination game in which players move tokens on a colored board and exchange resources (chips) to achieve individual and joint goals. It is used to study negotiation, cooperation, and social decision-making.

This framework is structured to let you:
- Define and configure Colored Trails game instances.
- Plug in different agent policies (e.g., scripted, learned, or human-in-the-loop).
- Run controlled experiments and collect logs.
- Analyze outcomes to understand cooperative capabilities.

## Project Layout

- `game/` – core game logic (player, udge, agents, etc.).
- `experiments/` – experiment scripts (e.g., batched runs, sweeps).
- `configs/` - board types and parameter variations (eg contract type)
- `results/`  – outputs and summary statistics (path may vary).
- `analysis/`  – scripts or notebooks for analyzing experiment outputs.

## Setup

From the repository root:

```bash
# (optional) create and activate a virtualenv/conda env
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# install dependencies
pip install -r requirements.txt
```

## Running a Single Game

From the repo root, run:

```bash
python -m src.game.main
```

Configurations can be edited directly in `main.py`

## Running Experiments

Experiments run many games with varying parameters 
Specify the parameters in configs/experiment_configs

```bash

python -m src.experiments.run_experiments --pairs FOUR_1,FOUR_1 
```

## Analyzing Results

Initially run 

```bash

python -m src.experiments.analyze_experiments
```

And perform analysis on all_runs.csv 
