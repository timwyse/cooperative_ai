import yaml
import json
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from config import GameConfig
from game import Game
from agents import *
from logger import Logger
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

NUM_WORKERS = 8

# Files
GRIDS_FILE = "experiment_configs/4x4_experiment_grids.yaml"
PARAM_VARIATIONS = "parameter_variations_yv"

AGENT_LIST = {
    "FOUR_1": FOUR_1,
    # "SONNET_4": SONNET_4,
    # "LLAMA_405B": LLAMA_405B,
}

def make_pair_name(a, b) -> str:
    return f"{a.replace(' ', '_')}-{b.replace(' ', '_')}"

def parse_pairs(pair_args: List[str]) -> List[Tuple[str, List]]:
    """
    Convert ['A,B', 'C,D', ...] into:
      [ ('A-B', [AGENT_LIST['A'], AGENT_LIST['B']]), ... ]
    """
    pairs = []
    if not pair_args:
        raise ValueError(
            "No --pairs provided. Example: --pairs FOUR_1,FOUR_1 --pairs SONNET_4,SONNET_4"
        )
    for p in pair_args:
        try:
            a_name, b_name = [x.strip() for x in p.split(",", 1)]
        except ValueError:
            raise ValueError(f"--pairs must be 'A,B', got: {p}")
        if a_name not in AGENT_LIST or b_name not in AGENT_LIST:
            missing = [n for n in (a_name, b_name) if n not in AGENT_LIST]
            raise ValueError(f"Unknown agent(s) in pair '{p}': {missing}. "
                             f"Known: {sorted(AGENT_LIST.keys())}")
        agents = [AGENT_LIST[a_name], AGENT_LIST[b_name]]
        pairs.append((make_pair_name(a_name, b_name), agents))
    return pairs

def generate_config_dir_name(config):
    contract_type = "none" if config.contract_type in [None, "none"] else str(config.contract_type)
    ctx = "ctx1" if config.with_context else "ctx0"
    fog = "fog" + "".join("1" if f else "0" for f in config.fog_of_war)
    return f"{ctx}_{fog}_p4p{str(config.pay4partner).lower()}_contract_{contract_type}"

def now_ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def generate_experiment_path(pair_name: str, grid_data, config, run_id=None):
    """logs/experiments/per_grid/<PAIR_NAME>/<bucket>/grid_id/config_dir/<timestamp>_<runid>/"""
    bucket = grid_data['bucket'].replace(" ", "_").replace("(", "").replace(")", "")
    grid_id = f"grid_{grid_data['id']:03d}"
    config_dir = generate_config_dir_name(config)
    timestamp = now_ts()
    run_id = run_id or uuid.uuid4().hex[:8]
    base_path = Path("logs") / "experiments" / "per_grid" / pair_name / bucket / grid_id / config_dir / f"{timestamp}_{run_id}"
    return base_path, f"{timestamp}_{run_id}"

def _run_single_experiment(pair_name: str, agents: List, grid_data, variation):
    """
    Thread worker for a single (pair, grid, variation).
    Returns (ok: bool, summary: dict).
    """
    grid_id = grid_data['id']
    grid = grid_data['grid']
    bucket = grid_data['bucket']
    sub_stratum = grid_data['sub_stratum']

    config = GameConfig(
        grid_size=4,
        colors=['R', 'B', 'G'],
        grid=grid,
        resource_mode='manual',
        manual_resources=[
            {"R": 14, "B": 0, "G": 1},
            {"R": 0, "B": 14, "G": 1}
        ],
        players=agents,
        pay4partner=variation["pay4partner"],
        contract_type=variation["contract_type"],
        with_message_history=variation["with_message_history"],
        fog_of_war=variation["fog_of_war"],
        display_gui=False,
        wait_for_enter=False,
        with_context=True
    )

    run_id = uuid.uuid4().hex[:8]
    exp_path, timestamp = generate_experiment_path(pair_name, grid_data, config, run_id=run_id)
    exp_path.mkdir(parents=True, exist_ok=True)

    game_id = f"grid_{grid_id}_{timestamp}"
    metadata = {
        'model_pair': pair_name,
        "grid_id": grid_id,
        "grid": grid,
        "game_id": game_id,
        "timestamp": timestamp,
        "bucket": bucket,
        "sub_stratum": sub_stratum,
        "config": {
            "pay4partner": variation["pay4partner"],
            "contract_type": variation["contract_type"],
            "with_context": config.with_context,
            "with_message_history": variation["with_message_history"],
            "fog_of_war": [False, False]
        },
        "grid_metrics": {
            "b_min_trades_efficient_path": grid_data["b_min_trades_efficient_path"],
            "b_max_trades_efficient_path": grid_data["b_max_trades_efficient_path"],
            "r_min_trades_efficient_path": grid_data["r_min_trades_efficient_path"],
            "r_max_trades_efficient_path": grid_data["r_max_trades_efficient_path"],
            "trade_asymmetry": grid_data["trade_asymmetry"]
        }
    }
    with open(exp_path / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    try:
        logger = Logger(
            game_id=game_id,
            base_log_dir=str(exp_path),
            skip_default_logs=True
        )
        game = Game(config=config, logger=logger)
        game.run()

        scores = {p.name: (10 + 5 * sum(dict(p.resources).values())) if p.has_finished() else 0
                  for p in game.players}
        summary = {
            "status": "SUCCESS",
            "pair": pair_name,
            "grid_id": grid_id,
            "turns": game.turn,
            "score_total": sum(scores.values()),
            "goals_reached": [p.has_finished() for p in game.players],
            "path": str(exp_path)
        }

        return True, summary

    except Exception as e:
        summary = {
            "status": "CRASHED",
            "pair": pair_name,
            "grid_id": grid_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "path": str(exp_path)
        }
        return False, summary

def run_experiments(start_id=None, end_id=None, pair_args: List[str] = None, num_workers=8):
    # Resolve model pairs
    model_pairs = parse_pairs(pair_args or [])

    param_file = f"experiment_configs/{PARAM_VARIATIONS}.yaml"
    print(f"\nLoading parameter variations from: {param_file}")
    try:
        with open(param_file, "r") as f:
            param_variations = yaml.safe_load(f)
            if param_variations is None:
                raise ValueError(f"YAML file {param_file} was loaded but contains no data")
            print(f"Loaded {len(param_variations)} variations.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Parameter variations file not found: {param_file}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file {param_file}: {e}")

    print(f"\nLoading grids from: {GRIDS_FILE}")
    try:
        with open(GRIDS_FILE, "r") as f:
            grids = yaml.safe_load(f)
            print(f"Loaded {len(grids)} grids")
    except FileNotFoundError:
        raise FileNotFoundError(f"Grids file not found: {GRIDS_FILE}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file {GRIDS_FILE}: {e}")

    # Filter grids
    if start_id is not None:
        grids = [g for g in grids if g['id'] >= start_id]
        print(f"Starting from grid ID {start_id}")
    if end_id is not None:
        grids = [g for g in grids if g['id'] <= end_id]
        print(f"Running until grid ID {end_id}")
    print(f"Will process {len(grids)} grids")

    # Build tasks across pairs × grids × variations
    tasks = []
    print("\nPlanning runs...")
    for pair_name, agents in model_pairs:
        print(f"\nPair: {pair_name}")
        for grid_data in grids:
            grid_id = grid_data['id']
            bucket = grid_data['bucket']
            sub_stratum = grid_data['sub_stratum']
            # Same symmetry rule but per pair:
            if bucket == 'Needy Player (Red)' and agents[0] == agents[1]:
                print(f"  - Skipping grid {grid_id} ({bucket}) due to symmetry with identical agents.")
                continue
            for variation in param_variations:
                tasks.append((pair_name, agents, grid_data, variation))

    print(f"\nTotal runs to execute: {len(tasks)}")
    print(f"Using {num_workers} workers")

    # Sequential fallback
    if num_workers <= 1 or len(tasks) <= 1:
        print("\nRunning sequentially...")
        results = []
        for pair_name, agents, grid_data, variation in tasks:
            ok, summary = _run_single_experiment(pair_name, agents, grid_data, variation)
            status = "SUCCESS" if ok else "CRASHED"
            print(f"[{status}] pair={summary.get('pair')} grid={summary.get('grid_id')} -> {summary.get('path')}")
            results.append((ok, summary))
        successes = sum(1 for ok, _ in results if ok)
        print(f"\nFinished. {successes}/{len(results)} runs succeeded.")
        return

    # Parallel (threads)
    print("\nRunning in parallel (threads)...")
    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        fut_to_task = {
            executor.submit(_run_single_experiment, pair_name, agents, grid_data, variation):
            (pair_name, agents, grid_data, variation)
            for (pair_name, agents, grid_data, variation) in tasks
        }
        for fut in as_completed(fut_to_task):
            try:
                ok, summary = fut.result()
                status = "SUCCESS" if ok else "CRASHED"
                print(f"[{status}] pair={summary.get('pair')} grid={summary.get('grid_id')} -> {summary.get('path')}")
                results.append((ok, summary))
            except Exception as e:
                print(f"[CRASHED] Unhandled in future: {type(e).__name__}: {e}")

    successes = sum(1 for ok, _ in results if ok)
    print(f"\nFinished. {successes}/{len(results)} runs succeeded.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run grid-based experiments (multi-pair)')
    parser.add_argument('--start-id', type=int, help='Start from this grid ID (inclusive)')
    parser.add_argument('--end-id', type=int, help='Run until this grid ID (inclusive)')
    parser.add_argument('--workers', type=int, default=8,
                        help='Number of parallel workers (default: 8, use 1 for sequential)')
    parser.add_argument('--pairs', action='append',
                        help="Model pair as 'A,B'. Repeat for multiple pairs. "
                             "Example: --pairs FOUR_1,FOUR_1 --pairs SONNET_4,SONNET_4")
    args = parser.parse_args()
    run_experiments(start_id=args.start_id, end_id=args.end_id, pair_args=args.pairs, num_workers=args.workers)
