import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

def load_experiment_data(experiment_dir):
    """Load all experiment data from a timestamp directory"""
    experiment_dir = Path(experiment_dir)
    print(f"\nSearching for event logs in: {experiment_dir}")
    
    # Structure to hold all data
    all_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    # List all files to debug
    print("\nFound files:")
    for file in experiment_dir.rglob("*"):
        print(f"  {file}")
    
    # Walk through experiment directory
    event_logs = list(experiment_dir.glob("**/event_log_*.json"))
    print(f"\nFound {len(event_logs)} event log files")
    
    for event_log in event_logs:
        print(f"\nProcessing log file: {event_log}")
        # Parse directory structure
        parts = event_log.parts
        timestamp_idx = parts.index("experiments") + 1
        board = parts[timestamp_idx + 1]
        model_pair = parts[timestamp_idx + 2]
        config_name = parts[timestamp_idx + 3]
        
        # Load event log
        with open(event_log) as f:
            data = json.load(f)
            
        # Extract key metrics
        metrics = {
            "total_turns": data["game"]["final_state"]["total_turns"],
            "total_scores": sum(data["game"]["final_state"]["scores"].values()),
            "reached_goal": {
                player: state["reached_goal"]
                for player, state in data["game"]["final_state"]["players"].items()
            },
            "final_resources": {
                player: state["resources"]
                for player, state in data["game"]["final_state"]["players"].items()
            }
        }
        
        # Store with full config info
        metrics["config"] = data["config"]
        all_data[board][model_pair][config_name].append(metrics)
    
    return all_data

def calculate_aggregate_metrics(metrics_list):
    """Calculate aggregate statistics from a list of run metrics"""
    n_runs = len(metrics_list)
    
    # Extract arrays for numerical metrics
    total_turns = [m["total_turns"] for m in metrics_list]
    total_scores = [m["total_scores"] for m in metrics_list]
    
    # Calculate success rates per player
    success_rates = {}
    for player in metrics_list[0]["reached_goal"].keys():
        successes = sum(m["reached_goal"][player] for m in metrics_list)
        success_rates[player] = successes / n_runs
    
    # Calculate joint success rate (both players reached goal)
    both_success = sum(
        all(m["reached_goal"].values())  # True if all players reached goal
        for m in metrics_list
    )
    success_rates["both"] = both_success / n_runs
    
    return {
        "total_turns": {
            "mean": np.mean(total_turns),
            "std": np.std(total_turns),
            "min": min(total_turns),
            "max": max(total_turns)
        },
        "total_scores": {
            "mean": np.mean(total_scores),
            "std": np.std(total_scores),
            "min": min(total_scores),
            "max": max(total_scores)
        },
        "success_rates": success_rates,
        "n_runs": n_runs
    }

def create_metrics_table(model_data):
    """Create a DataFrame with metrics for all configurations"""
    rows = []
    
    print("\nAvailable configurations:")
    for config_name, run_metrics in model_data.items():
        print(f"\nConfig directory: {config_name}")
        print(f"Config settings: {run_metrics[0]['config']}")
        print(f"Contract type: {run_metrics[0]['config'].get('contract_type')}")
        
        agg_metrics = calculate_aggregate_metrics(run_metrics)
        config = run_metrics[0]["config"]
        
        # Extract config from the data structure
        config_data = run_metrics[0]["config"]
        
        # Get fog of war setting for display
        fog_of_war = config_data.get("fog_of_war", [False, False])
        
        # Use the directory name as configuration name
        # config_name is the directory name after MODEL-PAIR/
        
        # Create row with configuration details
        row = {
            "Configuration": config_name,  # Use the actual directory name
            "N_runs": agg_metrics['n_runs'],  # Add number of runs
            "Pay4Partner": config_data.get("pay4partner", False),
            "Contract Type": config_data.get("contract_type", "none"),  # Use "none" instead of None for display
            "Context": config_data.get("with_context", False),
            "Message History": config_data.get("with_message_history", False),
            "Fog of War": str(fog_of_war),
            "Avg Turns": f"{agg_metrics['total_turns']['mean']:.1f} ± {agg_metrics['total_turns']['std']:.1f}",
            "Avg Score": f"{agg_metrics['total_scores']['mean']:.1f} ± {agg_metrics['total_scores']['std']:.1f}",
            "Min Score": agg_metrics['total_scores']['min'],
            "Max Score": agg_metrics['total_scores']['max'],
        }
        
        # Add success rates for each player with clearer names
        for player, rate in agg_metrics['success_rates'].items():
            if player == "both":
                row["Both Players Success Rate"] = f"{rate*100:.1f}%"
            else:
                # Convert player name to clearer format (e.g., "Player 0" or "Player 1")
                player_num = player.split()[-1]  # Get the number from "Player X"
                row[f"Player {player_num} Success Rate"] = f"{rate*100:.1f}%"
        
        rows.append(row)
    
    # Create DataFrame and sort by configuration
    df = pd.DataFrame(rows)
    df = df.sort_values(["Pay4Partner", "Contract Type", "Context", "Message History", "Fog of War"])
    
    return df

def analyze_experiments(experiment_dir):
    """Analyze all experiments in a directory and generate tables"""
    print(f"Analyzing experiments in {experiment_dir}")
    
    # Load all experiment data
    all_data = load_experiment_data(experiment_dir)
    
    # Process each board configuration
    for board, board_data in all_data.items():
        print(f"\nBoard: {board}")
        
        # Create tables directory
        tables_dir = Path(experiment_dir) / board / "analysis"
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each model pair
        for model_pair, model_data in board_data.items():
            print(f"\nGenerating table for {model_pair}")
            
            # Create metrics table
            df = create_metrics_table(model_data)
            
            # Save as CSV with board name included
            csv_file = tables_dir / f"{board}_{model_pair}_metrics.csv"
            df.to_csv(csv_file, index=False)
            print(f"\nSaved metrics to {csv_file}")
            
            # Print table preview
            pd.set_option('display.max_columns', None)  # Show all columns
            pd.set_option('display.width', None)  # Don't wrap wide tables
            print("\n=== Metrics Table Preview ===")
            print("\nShape:", df.shape)
            print("\nColumns:", ", ".join(df.columns))
            print("\nFull table:")
            print(df.to_string())
            
            # Save aggregate metrics for each configuration
            for config_name, run_metrics in model_data.items():
                agg_metrics = calculate_aggregate_metrics(run_metrics)
                metrics_dir = Path(experiment_dir) / board / model_pair / config_name
                metrics_file = metrics_dir / "aggregate_metrics.json"
                with open(metrics_file, "w") as f:
                    json.dump({
                        "config": run_metrics[0]["config"],
                        "aggregate_metrics": agg_metrics,
                        "individual_runs": run_metrics
                    }, f, indent=2)

def get_latest_experiment_dir():
    """Find the most recent experiment directory"""
    exp_dir = Path("logs/experiments")
    if not exp_dir.exists():
        raise FileNotFoundError("No experiments directory found at logs/experiments")
    
    # Get all subdirectories and sort by modification time
    dirs = [d for d in exp_dir.iterdir() if d.is_dir()]
    if not dirs:
        raise FileNotFoundError("No experiment directories found")
    
    latest_dir = max(dirs, key=lambda x: x.stat().st_mtime)
    return latest_dir

if __name__ == "__main__":
    import sys
    
    try:
        if len(sys.argv) > 1:
            # Use specified directory
            experiment_dir = sys.argv[1]
            print(f"Analyzing specified experiment directory: {experiment_dir}")
        else:
            # Use latest directory
            experiment_dir = get_latest_experiment_dir()
            print(f"Analyzing latest experiment directory: {experiment_dir}")
        
        analyze_experiments(experiment_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
