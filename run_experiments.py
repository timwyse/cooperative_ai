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

# Experiment Configuration
BOARD_CONFIG = "yv_max_trade"  # Name of the board config file
PARAM_VARIATIONS = "parameter_variations_test"  # Name of the variations file without .yaml extension
AGENTS = [FOUR_1, FOUR_1]  

# Generate model pair info
MODEL_PAIR = {
    "agents": AGENTS,
    "name": "-".join(agent.name.replace(" ", "_") for agent in AGENTS)  # e.g., "FOUR_1-FOUR_1"
}
N_RUNS = 5  


def generate_run_name(config, run_id):
    ctx = "1" if config.with_context else "0"
    fog = "".join("1" if f else "0" for f in config.fog_of_war)
    return f"run_ctx{ctx}_fog{fog}_{run_id:03d}"

def generate_experiment_path(base_dir, board_name, model_pair, config):
    contract_mode = ""
    if config.pay4partner:
        contract_mode = "pay4partner_true_contract_none"
    elif config.contract_type == "strict":
        contract_mode = "pay4partner_false_contract_strict"
    elif config.contract_type == "natural_language":
        contract_mode = "pay4partner_false_contract_natural_language"
    else:
        contract_mode = "pay4partner_false_contract_none"
        
    return base_dir / board_name / model_pair / contract_mode

def run_experiments():
    # Load parameter combinations
    with open(f"experiment_configs/{PARAM_VARIATIONS}.yaml", "r") as f:
        param_variations = yaml.safe_load(f)
    print(param_variations)


    board_config = load_config(f"configs/{BOARD_CONFIG}.yaml")

    # Create timestamp for this experiment batch
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base_log_dir = Path("logs") / "experiments"/ timestamp

    # Run experiments for each parameter combination
    for variation in param_variations:
        config = GameConfig(
            # Board settings from YAML
            grid_size=board_config.grid_size,
            colors=board_config.colors,
            grid=board_config.grid,
            resource_mode=board_config.resource_mode,
            manual_resources=[
                {"R": 10, "B": 0, "G": 0},
                {"R": 0, "B": 10, "G": 0}
            ],
            manual_start_positions=[(0, 0), (0, 0)],
            manual_goal_positions=[(3, 3), (3, 3)],
            
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

        for run_id in range(N_RUNS):
            # Create unique run folder
            run_name = generate_run_name(config, run_id)
            run_dir = exp_path / run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            print(f"\nStarting run {run_id + 1}/{N_RUNS}")
            
            # Run game with this configuration, suppressing its output
            f = io.StringIO()
            with redirect_stdout(f):
                # Create game with custom log directory
                game = Game(config=config)
                # Override the logger's base directory before it creates any files
                game.logger = game.logger.__class__(
                    game_id=game.logger.game_id,
                    base_log_dir=str(run_dir)
                )
                game.run()
            
            # Print just the summary
            scores = {p.name: (100 + 5 * sum(dict(p.resources).values())) if p.has_finished() else 0 
                     for p in game.players}
            print(f"Run {run_id + 1}: turns={game.turn}, score={sum(scores.values())}, goals={[p.has_finished() for p in game.players]}")

if __name__ == "__main__":
    run_experiments()