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
BOARD_CONFIG = "needs_benefits_1"  # Name of the board config file
PARAM_VARIATIONS = "temp_parameter_variations"  # Name of the variations file without .yaml extension
AGENTS = [FOUR_1, FOUR_1]  

# Generate model pair info
MODEL_PAIR = {
    "agents": AGENTS,
    "name": "-".join(agent.name.replace(" ", "_") for agent in AGENTS)  # e.g., "FOUR_1-FOUR_1"
}
N_RUNS = 10


def generate_run_name(config, run_id):
# Note:
# ctx0 in log name means with_context=False
# ctx1 in log name mans with_context=True
    ctx = "1" if config.with_context else "0"
    fog = "".join("1" if f else "0" for f in config.fog_of_war)
    return f"run_ctx{ctx}_fog{fog}_{run_id:03d}"

def generate_experiment_path(base_dir, board_name, model_pair, config):
    """Generate unique path for each configuration combination"""
    # Convert None or "none" to "none" for consistent path naming
    contract_type = "none" if config.contract_type in [None, "none"] else str(config.contract_type)
    
    # Generate context and fog parts
    ctx = "ctx1" if config.with_context else "ctx0"
    fog = "fog" + "".join("1" if f else "0" for f in config.fog_of_war)
    
    # Generate unique directory name based on all settings
    config_dir = f"{ctx}_{fog}_p4p{str(config.pay4partner).lower()}_contract_{contract_type}"
    
    print(f"\nGenerating path for config: {config_dir}")
    return base_dir / board_name / model_pair / config_dir

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


    board_config = load_config(f"configs/{BOARD_CONFIG}.yaml")

    # Create timestamp for this experiment batch
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base_log_dir = Path("logs") / "experiments"/ timestamp

    # Run experiments for each parameter combination
    print("\nProcessing parameter variations:")
    for i, variation in enumerate(param_variations):
        print(f"\nVariation {i+1}:")
        print(f"  pay4partner: {variation['pay4partner']}")
        print(f"  contract_type: {variation['contract_type']}")
        
        config = GameConfig(
            # Board settings from YAML
            grid_size=board_config.grid_size,
            colors=board_config.colors,
            grid=board_config.grid,
            resource_mode=board_config.resource_mode,
            manual_resources=[
                {"R": 14, "B": 0, "G": 1},
                {"R": 0, "B": 14, "G": 1}
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
        exp_path = generate_experiment_path(base_log_dir, BOARD_CONFIG, MODEL_PAIR["name"], config)
        
        print(f"\nRunning experiment in {exp_path}")
        print(f"Configuration: {variation}")
        print(f"Contract type: {config.contract_type}")
        print(f"Pay4Partner: {config.pay4partner}")

        for run_id in range(N_RUNS):
            # Create unique run folder
            run_name = generate_run_name(config, run_id)
            run_dir = exp_path / run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            print(f"\nStarting run {run_id + 1}/{N_RUNS}")
            
            # Run game with this configuration
            try:
                f = io.StringIO()
                with redirect_stdout(f):
                    # Create logger first with experiment path
                    logger = Logger(
                        game_id=run_name,  # Use run name as game_id
                        base_log_dir=str(run_dir),  # Save in the run directory
                        skip_default_logs=True  # Skip creating default logs in logs/
                    )
                    # Create game with custom logger
                    game = Game(config=config, logger=logger)
                    game.run()
                
                # Print success summary
                scores = {p.name: calculate_score(p) for p in game.players}
                print(f"Run {run_id + 1}: SUCCESS, turns={game.turn}, score={sum(scores.values())}, goals={[p.has_finished() for p in game.players]}")
            except Exception as e:
                print(f"\nRun {run_id + 1}: CRASHED!")
                print(f"Error occurred in config: {run_name}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                # Print the captured output to help debug
                print("\nLast output before crash:")
                print(f.getvalue())
                # Re-raise if this is the first run to catch setup issues
                if run_id == 0:
                    raise

if __name__ == "__main__":
    run_experiments()