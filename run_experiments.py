import yaml
import json
import sys
import io
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from config import GameConfig, load_config
from game import Game
from agents import *
from logger import Logger
from utils import calculate_scores
import argparse

# File containing all 4x4 grids
GRIDS_FILE = "experiment_configs/4x4_experiment_grids.yaml"  
# Name of the variations file without .yaml extension
PARAM_VARIATIONS = "parameter_variations"  
AGENTS = [LLAMA_3_3B, LLAMA_3_3B]  

MODEL_PAIR = {
    "agents": AGENTS,
    "name": "-".join(agent.name.replace(" ", "_") for agent in AGENTS)  # e.g., "FOUR_1-FOUR_1"
}

def generate_config_dir_name(config):
    # Convert None or "none" to "none" for consistent path naming
    contract_type = "none" if config.contract_type in [None, "none"] else str(config.contract_type)
    
    # Generate context and fog parts
    ctx = "ctx1" if config.with_context else "ctx0"
    fog = "fog" + "".join("1" if f else "0" for f in config.fog_of_war)
    
    return f"{ctx}_{fog}_p4p{str(config.pay4partner).lower()}_contract_{contract_type}"

def generate_experiment_path(grid_data, config):
    """Generate path: logs/experiments/per_grid/bucket/grid_id/config_dir/timestamp/"""

    bucket = grid_data['bucket'].replace(" ", "_").replace("(", "").replace(")", "")
    grid_id = f"grid_{grid_data['id']:03d}"
    config_dir = generate_config_dir_name(config)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    base_path = Path("logs") / "experiments" / "per_grid" / MODEL_PAIR['name']/ bucket / grid_id / config_dir / timestamp
    print(f"\nGenerating path for experiment:")
    print(f"  Bucket: {bucket}")
    print(f"  Grid: {grid_id}")
    print(f"  Config: {config_dir}")
    print(f"  Path: {base_path}")
    return base_path, timestamp

def run_experiments(start_id=None, end_id=None):
    param_file = f"experiment_configs/{PARAM_VARIATIONS}.yaml"
    print(f"\nLoading parameter variations from: {param_file}")
    try:
        with open(param_file, "r") as f:
            param_variations = yaml.safe_load(f)
            print("\nLoaded variations:")
            print(f"Type: {type(param_variations)}")
            print(f"Content: {param_variations}")
            if param_variations is None:
                raise ValueError(f"YAML file {param_file} was loaded but contains no data")
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

    # Filter grids based on start_id and end_id
    if start_id is not None:
        grids = [g for g in grids if g['id'] >= start_id]
        print(f"Starting from grid ID {start_id}")
    if end_id is not None:
        grids = [g for g in grids if g['id'] <= end_id]
        print(f"Running until grid ID {end_id}")
    print(f"Will process {len(grids)} grids")

    # Run experiments for each grid and parameter combination
    print("\nProcessing grids and parameter variations:")
    for grid_data in grids:
        grid_id = grid_data['id']
        grid = grid_data['grid']
        bucket = grid_data['bucket']
        sub_stratum = grid_data['sub_stratum']
        print(f"\nGrid {grid_id}")
        print(f"Bucket: {bucket}")
        print(f"Sub-stratum: {sub_stratum}")
        if bucket == 'Needy Player (Red)' and AGENTS[0] == AGENTS[1]:
            print(f"Skipping this grid because it is type {bucket} which is symmetry to Needy Player (Blue) when agents are identical.")
            continue
        
         # Run experiments for each parameter variation
        
        for i, variation in enumerate(param_variations):
            print(f"\nVariation {i+1}:")
            print(f"  pay4partner: {variation['pay4partner']}")
            print(f"  contract_type: {variation['contract_type']}")
            
            config = GameConfig(
                # Fixed board settings for 4x4 experiments
                grid_size=4,
                colors=['R', 'B', 'G'],  
                grid=grid,  
                resource_mode='manual',  
                manual_resources=[
                    {"R": 14, "B": 0, "G": 1},  # Player 0: Red chips + 1 Green
                    {"R": 0, "B": 14, "G": 1}   # Player 1: Blue chips + 1 Green
                ],
                
                players=MODEL_PAIR["agents"],
                
                pay4partner=variation["pay4partner"],
                contract_type=variation["contract_type"],
                with_message_history=variation["with_message_history"],
                fog_of_war=variation["fog_of_war"],
                
                display_gui=False,
                wait_for_enter=False,
                with_context = True
            )

            # Generate experiment path and timestamp
            exp_path, timestamp = generate_experiment_path(grid_data, config)
            exp_path.mkdir(parents=True, exist_ok=True)

            # Create metadata file with experiment info
            game_id = f"grid_{grid_id}_{timestamp}"

            metadata = {
                'model_pair': MODEL_PAIR['name'],
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
                    "fog_of_war": variation["fog_of_war"]
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

            print(f"\nRunning experiment in {exp_path}")
            print(f"Configuration: {variation}")
            print(f"Contract type: {config.contract_type}")
            print(f"Pay4Partner: {config.pay4partner}")

            # Run game with this configuration
            try:
                # This creates a string buffer (f) and redirects all console output
                # to this buffer instead of the terminal.
                # This is being used to capture any output that happens during the game run.
                f = io.StringIO()
                with redirect_stdout(f):
                    # Create logger with experiment path
                    logger = Logger(
                        game_id=game_id,  
                        base_log_dir=str(exp_path),  
                        skip_default_logs=True  # Skip creating default logs in logs/
                    )
                    # Create game with custom logger
                    game = Game(config=config, logger=logger)
                    game.run()
                
                # Print success summary
                scores = {p.name: (10 + 5 * sum(dict(p.resources).values())) if p.has_finished() else 0 
                         for p in game.players}
                print(f"Run completed: SUCCESS")
                print(f"Turns: {game.turn}")
                print(f"Score: {sum(scores.values())}")
                print(f"Goals reached: {[p.has_finished() for p in game.players]}")
                print("-" * 60)  # Add separator between runs
            except Exception as e:
                print(f"\nRun CRASHED!")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                print("\nLast output before crash:")
                print(f.getvalue())
                raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run grid-based experiments')
    parser.add_argument('--start-id', type=int, help='Start from this grid ID (inclusive)')
    parser.add_argument('--end-id', type=int, help='Run until this grid ID (inclusive)')
    
    args = parser.parse_args()
    run_experiments(start_id=args.start_id, end_id=args.end_id)