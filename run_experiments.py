import yaml
import json
import uuid
import traceback
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from config import GameConfig
from game import Game
from agents import *
from logger import Logger
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from prompts import DEFAULT_SYSTEM_PROMPT, SELFISH_SYSTEM_PROMPT

NUM_WORKERS = 8

# Files
GRIDS_FILE = "experiment_configs/4x4_experiment_grids.yaml"
PARAM_VARIATIONS = "parameter_variations"

AGENT_LIST = {
    "FOUR_1": FOUR_1,
    "GPT_5_2": GPT_5_2,
    "HAIKU_4_5": HAIKU_4_5,
    "HAIKU_3_5": HAIKU_3_5,  # Known working model for testing
    "SONNET_4_5": SONNET_4_5,
    # "LLAMA_405B": LLAMA_405B,
}

QUOTA_ERROR_PATTERNS = [
    "rate limit", "rate_limit", "quota exceeded", "quota_exceeded",
    "insufficient_quota", "insufficient quota", "too many requests", "429",
    "billing", "credit", "exceeded your current quota", "out of quota"
]

class QuotaError(Exception):
    pass

def is_experiment_completed(run_timestamp: str, pair_name: str, grid_data: dict, config, selfish_str: str) -> bool:
    """Check if a completed experiment already exists for this configuration."""
    bucket = grid_data['bucket'].replace(" ", "_").replace("(", "").replace(")", "")
    grid_id = f"grid_{grid_data['id']:03d}"
    config_dir = generate_config_dir_name(config, selfish=selfish_str)
    
    # Path to the config directory where runs would be stored
    config_path = Path("logs") / "experiments" / "per_grid" / run_timestamp / pair_name / bucket / grid_id / config_dir
    
    if not config_path.exists():
        return False
    
    # Check each run folder for a completed event log
    for run_folder in config_path.iterdir():
        if run_folder.is_dir():
            for log_file in run_folder.glob("event_log_*.json"):
                try:
                    with open(log_file, 'r') as f:
                        content = f.read()
                        if '"total_scores"' in content:
                            return True
                except Exception:
                    continue
    
    return False

def _is_quota_error(error_str: str) -> bool:
    error_lower = error_str.lower()
    return any(pattern in error_lower for pattern in QUOTA_ERROR_PATTERNS)
def make_pair_name(a, b) -> str:
    return f"{a.replace(' ', '_')}-{b.replace(' ', '_')}"

def parse_pairs(pair_args: List[str]) -> List[Tuple[str, List]]:
    """Convert ['A,B', 'C,D', ...] into: [ ('A-B', [AGENT_LIST['A'], AGENT_LIST['B']]), ... ]"""
    pairs = []
    if not pair_args:
        raise ValueError("No --pairs provided. Example: --pairs FOUR_1,FOUR_1 --pairs SONNET_4,SONNET_4")
    for p in pair_args:
        try:
            a_name, b_name = [x.strip() for x in p.split(",", 1)]
        except ValueError:
            raise ValueError(f"--pairs must be 'A,B', got: {p}")
        if a_name not in AGENT_LIST or b_name not in AGENT_LIST:
            missing = [n for n in (a_name, b_name) if n not in AGENT_LIST]
            raise ValueError(f"Unknown agent(s) in pair '{p}': {missing}. Known: {sorted(AGENT_LIST.keys())}")
        agents = [AGENT_LIST[a_name], AGENT_LIST[b_name]]
        pairs.append((make_pair_name(a_name, b_name), agents))
    return pairs

def generate_config_dir_name(config, selfish="00"):
    contract_type = "none" if config.contract_type in [None, "none"] else str(config.contract_type)
    ctx = "ctx1" if config.with_context else "ctx0"
    fog = "fog" + "".join("1" if f else "0" for f in config.fog_of_war)
    return f"{ctx}_{fog}_p4p{str(config.pay4partner).lower()}_contract_{contract_type}_selfish{selfish}"

def now_ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def generate_experiment_path(pair_name: str, grid_data, config, run_timestamp, run_id=None, selfish="00"):
    """logs/experiments/per_grid/<RUN_TIMESTAMP>/<PAIR_NAME>/<bucket>/grid_id/config_dir/<timestamp>_<runid>/"""
    bucket = grid_data['bucket'].replace(" ", "_").replace("(", "").replace(")", "")
    grid_id = f"grid_{grid_data['id']:03d}"
    config_dir = generate_config_dir_name(config, selfish=selfish)
    timestamp = now_ts()
    run_id = run_id or uuid.uuid4().hex[:8]
    base_path = Path("logs") / "experiments" / "per_grid" / run_timestamp / pair_name / bucket / grid_id / config_dir / f"{timestamp}_{run_id}"
    return base_path, f"{timestamp}_{run_id}"

def _selfish_to_str(selfish: list) -> str:
    return "".join("1" if s else "0" for s in selfish)

def _get_system_prompts(selfish: list) -> dict:
    return {
        '0': SELFISH_SYSTEM_PROMPT if selfish[0] else DEFAULT_SYSTEM_PROMPT,
        '1': SELFISH_SYSTEM_PROMPT if selfish[1] else DEFAULT_SYSTEM_PROMPT
    }

def _run_single_experiment(pair_name: str, agents: List, grid_data, variation, run_timestamp):
    """Thread worker for a single (pair, grid, variation). Returns (ok: bool, summary: dict)."""
    grid_id = grid_data['id']
    grid = grid_data['grid']
    bucket = grid_data['bucket']
    sub_stratum = grid_data['sub_stratum']
    
    selfish = variation.get("selfish", [False, False])
    selfish_str = _selfish_to_str(selfish)
    system_prompts = _get_system_prompts(selfish)

    config = GameConfig(
        grid_size=4,
        colors=['R', 'B', 'G'],
        grid=grid,
        resource_mode='manual',
        manual_resources=[
            {"R": 14, "B": 0, "G": 2},
            {"R": 0, "B": 14, "G": 2}
        ],
        players=agents,
        pay4partner=variation["pay4partner"],
        contract_type=variation["contract_type"],
        with_message_history=variation["with_message_history"],
        fog_of_war=variation["fog_of_war"],
        system_prompts=system_prompts,
        display_gui=False,
        wait_for_enter=False,
        with_context=True,
        show_paths=True
    )

    run_id = uuid.uuid4().hex[:8]
    exp_path, timestamp = generate_experiment_path(pair_name, grid_data, config, run_timestamp, run_id=run_id, selfish=selfish_str)
    exp_path.mkdir(parents=True, exist_ok=True)

    game_id = f"grid_{grid_id}_{timestamp}"
    metadata = {
        'model_pair': pair_name,
        "grid_id": grid_id, "grid": grid, "game_id": game_id, "timestamp": timestamp,
        "bucket": bucket, "sub_stratum": sub_stratum,
        "config": {
            "pay4partner": variation["pay4partner"], "contract_type": variation["contract_type"],
            "with_context": config.with_context, "with_message_history": variation["with_message_history"],
            "fog_of_war": [False, False], "selfish": selfish
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
        logger = Logger(game_id=game_id, base_log_dir=str(exp_path), skip_default_logs=True)
        game = Game(config=config, logger=logger)
        game.run()

        scores = {p.name: (10 + 5 * sum(dict(p.resources).values())) if p.has_finished() else 0 for p in game.players}
        return True, {"status": "SUCCESS", "pair": pair_name, "grid_id": grid_id, "turns": game.turn,
                      "score_total": sum(scores.values()), "goals_reached": [p.has_finished() for p in game.players],
                      "path": str(exp_path)}

    except Exception as e:
        error_str = str(e)
        tb_str = traceback.format_exc()
        
        # Check if this is a quota/rate limit error - raise to stop everything
        if _is_quota_error(error_str) or _is_quota_error(tb_str):
            raise QuotaError(f"Quota/rate limit error: {error_str}")
        
        return False, {"status": "CRASHED", "pair": pair_name, "grid_id": grid_id,
                       "error": error_str, "traceback": tb_str, "path": str(exp_path)}

def find_latest_run_folder() -> str:
    """Find the most recent run folder (YYYY_MM_DD_HH format)."""
    base_path = Path("logs") / "experiments" / "per_grid"
    if not base_path.exists():
        return None
    
    # Find all folders matching the timestamp pattern
    folders = [f for f in base_path.iterdir() if f.is_dir() and len(f.name) == 13]  # YYYY_MM_DD_HH = 13 chars
    if not folders:
        return None
    
    # Sort by name (which is chronological for this format) and get the latest
    latest = sorted(folders, key=lambda x: x.name, reverse=True)[0]
    return latest.name

def run_experiments(start_id=None, end_id=None, pair_args: List[str] = None, num_workers=NUM_WORKERS, add_to_latest=False, skip_completed=False, run_folder=None):
    model_pairs = parse_pairs(pair_args or [])
    
    if run_folder:
        # Use specified run folder
        run_timestamp = run_folder
        print(f"\n{'='*60}\nADDING to specified batch: {run_timestamp}\n{'='*60}\n")
    elif add_to_latest:
        run_timestamp = find_latest_run_folder()
        if run_timestamp is None:
            print("No existing run folder found, creating new one.")
            run_timestamp = datetime.now().strftime("%Y_%m_%d_%H")
        else:
            print(f"\n{'='*60}\nADDING to existing batch: {run_timestamp}\n{'='*60}\n")
    else:
        run_timestamp = datetime.now().strftime("%Y_%m_%d_%H")
        print(f"\n{'='*60}\nStarting experiment batch: {run_timestamp}\n{'='*60}\n")

    # Load parameter variations
    param_file = f"experiment_configs/{PARAM_VARIATIONS}.yaml"
    with open(param_file, "r") as f:
        param_variations = yaml.safe_load(f)
    print(f"Loaded {len(param_variations)} variations from {param_file}")

    # Load grids
    with open(GRIDS_FILE, "r") as f:
        grids = yaml.safe_load(f)
    if start_id is not None:
        grids = [g for g in grids if g['id'] >= start_id]
    if end_id is not None:
        grids = [g for g in grids if g['id'] <= end_id]
    print(f"Loaded {len(grids)} grids")

    # Build tasks
    tasks = []
    skipped_count = 0
    for pair_name, agents in model_pairs:
        for grid_data in grids:
            if grid_data['bucket'] == 'Needy Player (Red)' and agents[0] == agents[1]:
                continue  # Skip symmetric grids for identical agents
            for variation in param_variations:
                # Check if we should skip completed experiments
                if skip_completed:
                    selfish = variation.get("selfish", [False, False])
                    selfish_str = _selfish_to_str(selfish)
                    
                    # Create a temporary config to check completion status
                    temp_config = GameConfig(
                        grid_size=4,
                        colors=['R', 'B', 'G'],
                        grid=grid_data['grid'],
                        resource_mode='manual',
                        manual_resources=[{"R": 14, "B": 0, "G": 2}, {"R": 0, "B": 14, "G": 2}],
                        players=agents,
                        pay4partner=variation["pay4partner"],
                        contract_type=variation["contract_type"],
                        with_message_history=variation["with_message_history"],
                        fog_of_war=variation["fog_of_war"],
                        with_context=True
                    )
                    
                    if is_experiment_completed(run_timestamp, pair_name, grid_data, temp_config, selfish_str):
                        skipped_count += 1
                        continue
                
                tasks.append((pair_name, agents, grid_data, variation))
    
    if skip_completed and skipped_count > 0:
        print(f"Skipped {skipped_count} already completed experiments")

    print(f"Total runs: {len(tasks)}, Workers: {num_workers}")

    results = []
    try:
        if num_workers <= 1:
            # Sequential
            for pair_name, agents, grid_data, variation in tasks:
                ok, summary = _run_single_experiment(pair_name, agents, grid_data, variation, run_timestamp)
                print(f"[{summary['status']}] grid={summary['grid_id']} -> {summary.get('path')}")
                results.append((ok, summary))
        else:
            # Parallel
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(_run_single_experiment, *task, run_timestamp): task for task in tasks}
                for fut in as_completed(futures):
                    ok, summary = fut.result()  # Will raise QuotaError if quota issue
                    print(f"[{summary['status']}] grid={summary['grid_id']} -> {summary.get('path')}")
                    results.append((ok, summary))
                    
    except QuotaError as e:
        print(f"\n{'='*60}\nSTOPPING: {e}\nCompleted: {len(results)} experiments\n{'='*60}")
        sys.exit(1)

    successes = sum(1 for ok, _ in results if ok)
    print(f"\nFinished. {successes}/{len(results)} runs succeeded.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run grid-based experiments (multi-pair)')
    parser.add_argument('--start-id', type=int, help='Start from this grid ID (inclusive)')
    parser.add_argument('--end-id', type=int, help='Run until this grid ID (inclusive)')
    parser.add_argument('--workers', type=int, default=NUM_WORKERS, help='Number of parallel workers')
    parser.add_argument('--pairs', action='append', help="Model pair as 'A,B'")
    parser.add_argument('--add', action='store_true', help='Add experiments to the most recent run folder instead of creating a new one')
    parser.add_argument('--skip-completed', action='store_true', help='Skip experiments that already have completed logs')
    parser.add_argument('--run-folder', type=str, help='Specify exact run folder to add to (e.g., 2026_01_08_17)')
    args = parser.parse_args()
    run_experiments(start_id=args.start_id, end_id=args.end_id, pair_args=args.pairs, num_workers=args.workers, add_to_latest=args.add, skip_completed=args.skip_completed, run_folder=args.run_folder)
