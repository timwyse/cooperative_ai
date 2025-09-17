import yaml
import json
import sys
import io
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from config import GameConfig, load_config
from game import Game
from agents import FOUR_1, NANO, MINI
from logger import Logger
from utils import calculate_score

# Experiment Configuration
GRIDS_FILE = "experiment_configs/4x4_experiment_grids.yaml"  # File containing all 4x4 grids
PARAM_VARIATIONS = "parameter_variations_test"  # Name of the variations file without .yaml extension
AGENTS = [FOUR_1, FOUR_1]  

# Generate model pair info
MODEL_PAIR = {
    "agents": AGENTS,
    "name": "-".join(agent.name.replace(" ", "_") for agent in AGENTS)  # e.g., "FOUR_1-FOUR_1"
}
N_RUNS = 10

def generate_config_dir_name(config):
    """Generate unique directory name based on all settings"""
    # Convert None or "none" to "none" for consistent path naming
    contract_type = "none" if config.contract_type in [None, "none"] else str(config.contract_type)
    
    # Generate context and fog parts
    ctx = "ctx1" if config.with_context else "ctx0"
    fog = "fog" + "".join("1" if f else "0" for f in config.fog_of_war)
    
    # Generate unique directory name based on all settings
    return f"{ctx}_{fog}_p4p{str(config.pay4partner).lower()}_contract_{contract_type}"

def generate_experiment_path(grid_data, config):
    """Generate path: logs/experiments/per_grid/bucket/grid_id/config_dir/timestamp/"""
    # Clean bucket name for filesystem
    bucket = grid_data['bucket'].replace(" ", "_").replace("(", "").replace(")", "")
    grid_id = f"grid_{grid_data['id']:03d}"
    config_dir = generate_config_dir_name(config)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    base_path = Path("logs") / "experiments" / "per_grid" / bucket / grid_id / config_dir / timestamp
    print(f"\nGenerating path for experiment:")
    print(f"  Bucket: {bucket}")
    print(f"  Grid: {grid_id}")
    print(f"  Config: {config_dir}")
    print(f"  Path: {base_path}")
    return base_path

def run_experiments():
    # Load parameter combinations
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

    # Load all grids
    print(f"\nLoading grids from: {GRIDS_FILE}")
    try:
        with open(GRIDS_FILE, "r") as f:
            grids = yaml.safe_load(f)
            print(f"Loaded {len(grids)} grids")
    except FileNotFoundError:
        raise FileNotFoundError(f"Grids file not found: {GRIDS_FILE}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file {GRIDS_FILE}: {e}")

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
        
        for i, variation in enumerate(param_variations):
            print(f"\nVariation {i+1}:")
            print(f"  pay4partner: {variation['pay4partner']}")
            print(f"  contract_type: {variation['contract_type']}")
            
            config = GameConfig(
                # Fixed board settings for 4x4 experiments
                grid_size=4,
                colors=['R', 'B', 'G'],  # Fixed colors for all experiments
                grid=grid,  # Grid from the grids file
                resource_mode='manual',  # Always use manual mode
                manual_resources=[
                    {"R": 14, "B": 0, "G": 1},  # Player 0: Red chips + 1 Green
                    {"R": 0, "B": 14, "G": 1}   # Player 1: Blue chips + 1 Green
                ],
                
                players=MODEL_PAIR["agents"],
                
                pay4partner=variation["pay4partner"],
                contract_type=variation["contract_type"],
                with_context=variation["with_context"],
                with_message_history=variation["with_message_history"],
                fog_of_war=variation["fog_of_war"],
                
                # Always disable GUI and user interaction
                display_gui=False,
                wait_for_enter=False
            )

            # Generate experiment path
            exp_path = generate_experiment_path(grid_data, config)
            exp_path.mkdir(parents=True, exist_ok=True)

            print(f"\nRunning experiment in {exp_path}")
            print(f"Configuration: {variation}")
            print(f"Contract type: {config.contract_type}")
            print(f"Pay4Partner: {config.pay4partner}")

            # Create metadata file with experiment info
            metadata = {
                "grid_id": grid_id,
                "bucket": bucket,
                "sub_stratum": sub_stratum,
                "config": {
                    "pay4partner": variation["pay4partner"],
                    "contract_type": variation["contract_type"],
                    "with_context": variation["with_context"],
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
            
            # Run game with this configuration
            try:
                f = io.StringIO()
                with redirect_stdout(f):
                    # Create logger with experiment path
                    logger = Logger(
                        game_id="game",  # Fixed game_id
                        base_log_dir=str(exp_path),  # Save in experiment directory
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
            except Exception as e:
                print(f"\nRun CRASHED!")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                print("\nLast output before crash:")
                print(f.getvalue())
                raise  # Always raise to stop experiments on error

if __name__ == "__main__":
    run_experiments()