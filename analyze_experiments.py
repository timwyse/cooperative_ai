import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import datetime

OUTPUT_DIR =  'results'

def load_experiment_data(experiment_dir="logs/experiments/per_grid"):
    """Load all experiment data from per_grid directory"""
    experiment_dir = Path(experiment_dir)
    print(f"\nSearching for event logs in: {experiment_dir}")
    
    # Find all event logs and metadata files
    event_logs = []
    for path in experiment_dir.rglob("event_log_*.json"):
        if path.is_file():
            event_logs.append(path)
    print(f"\nFound {len(event_logs)} event log files")
    
    rows = []
    for event_log in event_logs:
        print(f"\nProcessing log file: {event_log}")
        
        try:
            # Get metadata file from same directory
            metadata_file = event_log.parent / "metadata.json"
            
            # Load metadata if exists
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
            
            # Load event log
            with open(event_log) as f:
                data = json.load(f)
            
            # Skip if final state is missing
            if 'game' not in data or 'final_state' not in data['game']:
                print(f"Warning: Incomplete event log (missing final state) - skipping: {event_log}")
                continue
                
            final_state = data['game']['final_state']
            
            # Get run ID from directory name if not in metadata
            run_id = metadata.get('timestamp', event_log.parent.name)
            
            # Parse config from directory structure if not in metadata
            config_dir = event_log.parent.parent.name  # e.g., ctx0_fog00_p4ptrue_contract_none
            config_parts = config_dir.split('_')
            context = 'ctx1' in config_dir
            fog = config_parts[1][3:] if len(config_parts) > 1 else '00'
            p4p = 'p4ptrue' in config_dir
            contract = config_parts[-1] if len(config_parts) > 3 else 'none'
            
            # Get grid info from directory structure if not in metadata
            grid_dir = event_log.parent.parent.parent.name  # e.g., grid_000
            bucket_dir = event_log.parent.parent.parent.parent.name  # e.g., Independent_Both_have_optimal_paths
            
            # Extract metrics
            row = {
                'Model Pair': metadata.get('model_pair', '') if 'model_pair' in metadata else 'FOUR_1-FOUR_1',
                'Grid ID': metadata.get('grid_id', grid_dir.replace('grid_', '')),
                'Config ID': config_dir,
                'Run ID': run_id,
                'Context': metadata.get('config', {}).get('with_context', context),
                'Fog of War': metadata.get('config', {}).get('fog_of_war', fog),
                'Grid': metadata.get('grid', ''),
                'Bucket': metadata.get('bucket', bucket_dir),
                'Sub-stratum': metadata.get('sub_stratum', ''),
                'Pay4Partner': metadata.get('config', {}).get('pay4partner', p4p),
                'Contract Type': metadata.get('config', {}).get('contract_type', contract),
                'Total Turns': len(data['game']['turns']),
                'Non-Cooperative Baseline Player 0': data['config']['player_details'][0].get('non_cooperative_baseline',
                                                                                            0),
                'Non-Cooperative Baseline Player 1': data['config']['player_details'][1].get('non_cooperative_baseline',
                                                                                             0),
                'Total Score': sum(final_state['scores'].values()),
                'Score Player 0': final_state['scores'].get('Player 0', 0), 
                'Score Player 1': final_state['scores'].get('Player 1', 0), 
                'Gini': final_state.get('metrics', {}).get('gini_coefficient', 0),  # Updated path
                'Max Possible Score': final_state.get('metrics', {}).get('max_possible_score', 0),  # Updated path
                'Reached Goal Player 0': final_state['players']['0']['reached_goal'],  # Changed from 'Player 0' to '0'
                'Reached Goal Player 1': final_state['players']['1']['reached_goal'],  # Changed from 'Player 1' to '1'
                'Total Trades Proposed': final_state.get('metrics', {}).get('total_trades_proposed', 0),
                'Total Trades Accepted': final_state.get('metrics', {}).get('total_trades_accepted', 0),

                'Total Trades Rejected': final_state.get('metrics', {}).get('total_trades_rejected', 0),
                'Total P4P Promises Kept': final_state.get('metrics', {}).get('total_p4p_promises_kept', 0),
                'Total P4P Promises Broken': final_state.get('metrics', {}).get('total_p4p_promises_broken', 0),
                'amount_received_by_0_from_trades': final_state.get('metrics', {}).get('amount_received_by_0_from_trades', 0),
                'amount_received_by_1_from_trades': final_state.get('metrics', {}).get('amount_received_by_1_from_trades', 0),
                'contract_accepted': final_state.get('metrics', {}).get('contract_accepted', 0),
                'contract_negotiaion_length': final_state.get('metrics', {}).get('contract_negotiaion_length', 0),
                'num_tiles_in_contract': final_state.get('metrics', {}).get('num_tiles_in_contract', 0),
                'num_tiles_promised_to_receive_from_contract_0': final_state.get('metrics', {}).get('num_tiles_promised_to_receive_from_contract_0', 0),
                'num_tiles_promised_to_receive_from_contract_1': final_state.get('metrics', {}).get('num_tiles_promised_to_receive_from_contract_1', 0),
                'points_for_completion_promised_to_0': final_state.get('metrics', {}).get('points_for_completion_promised_to_0', 0),
                'points_for_completion_promised_to_1': final_state.get('metrics', {}).get('points_for_completion_promised_to_1', 0),
            }
            
            # Add grid metrics if available
            if 'grid_metrics' in metadata:
                row.update({
                    'B Min Trades Path': metadata['grid_metrics'].get('b_min_trades_efficient_path'),
                    'B Max Trades Path': metadata['grid_metrics'].get('b_max_trades_efficient_path'),
                    'R Min Trades Path': metadata['grid_metrics'].get('r_min_trades_efficient_path'),
                    'R Max Trades Path': metadata['grid_metrics'].get('r_max_trades_efficient_path'),
                    'Trade Asymmetry': metadata['grid_metrics'].get('trade_asymmetry')
                })
            
            rows.append(row)
            print(f"Successfully processed run: {run_id}")
            
        except Exception as e:
            print(f"Error processing {event_log}: {str(e)}")
            continue
    
    if not rows:
        raise ValueError("No valid experiment data found")
        
    # Create DataFrame and sort
    df = pd.DataFrame(rows)
    df = df.sort_values(['Bucket', 'Grid ID', 'Config ID', 'Run ID'])
    
    # Save with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not Path(OUTPUT_DIR).exists():
        Path(OUTPUT_DIR).mkdir(parents=True)
    output_dir = Path(OUTPUT_DIR)
    df.to_csv(output_dir / f"all_runs_{timestamp}.csv", index=False)
    df.to_csv(output_dir / "all_runs_latest.csv", index=False)
    
    print(f"\nProcessed {len(df)} valid runs")
    print(f"Earliest run: {df['Run ID'].min()}")
    print(f"Latest run: {df['Run ID'].max()}")
    print(f"\nSaved results to:")
    print(f"- {output_dir}/all_runs_{timestamp}.csv")
    print(f"- {output_dir}/all_runs_latest.csv")
    
    return df

def analyze_experiments(experiment_dir=None):
    """Load and analyze experiment data"""
    if experiment_dir is None:
        experiment_dir = "logs/experiments/per_grid"
    
    df = load_experiment_data(experiment_dir)
    return df

if __name__ == "__main__":
    analyze_experiments(experiment_dir='/Users/timwyse/cooperative_ai/logs/experiments/per_grid/GPT_4.1-GPT_4.1_fog_of_war')