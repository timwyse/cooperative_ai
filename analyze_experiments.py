import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import re

OUTPUT_DIR = 'results'


def _safe_filename(name: str) -> str:
    name = re.sub(r'[^A-Za-z0-9._-]+', '-', str(name).strip())
    name = re.sub(r'-{2,}', '-', name)
    return name or "unnamed"


def _print_per_pair_counts(df: pd.DataFrame):
    """Print only row counts per model pair."""
    print("\n=== Per-Model-Pair Row Counts ===")
    counts = df.groupby("Model Pair", dropna=False).size().reset_index(name="Rows")
    for _, row in counts.iterrows():
        print(f"Model Pair: {row['Model Pair']}  |  Rows: {row['Rows']}")


def _save_per_model_pair_csvs(df: pd.DataFrame, output_dir: Path, timestamp: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs_dir = output_dir / "by_model_pair"
    pairs_dir.mkdir(parents=True, exist_ok=True)

    for pair, g in df.groupby("Model Pair", dropna=False):
        pair_name = _safe_filename(pair)
        g_sorted = g.sort_values(['Bucket', 'Grid ID', 'Config ID', 'Run ID'])
        ts_path = pairs_dir / f"{pair_name}_{timestamp}.csv"
        latest_path = pairs_dir / f"{pair_name}_latest.csv"
        g_sorted.to_csv(ts_path, index=False)
        g_sorted.to_csv(latest_path, index=False)
        print(f"Saved per-pair CSVs for '{pair}':")
        print(f"  - {ts_path}")
        print(f"  - {latest_path}")


def load_experiment_data(experiment_dir="logs/experiments/per_grid"):
    """
    Load all experiment data from per_grid directory and save global CSVs.

    Only include runs where:
      - final_state exists (top-level or under 'game'), is a dict, and
      - final_state['metrics'] exists and is a non-empty dict.
    Print notes for all skipped files.
    """
    experiment_dir = Path(experiment_dir)
    print(f"\nSearching for event logs in: {experiment_dir}")

    event_logs = [p for p in experiment_dir.rglob("event_log_*.json") if p.is_file()]
    print(f"\nFound {len(event_logs)} event log files")

    rows = []
    skipped_empty_metrics = 0
    skipped_files = []

    for event_log in event_logs:
        # print(f"\nProcessing log file: {event_log}")
        try:
            metadata_file = event_log.parent / "metadata.json"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)

            with open(event_log) as f:
                data = json.load(f)

            # final_state + metrics
            final_state = data.get('final_state')
            if final_state is None:
                final_state = data.get('game', {}).get('final_state')

            # Must be a dict (not None/str/number/etc.)
            if not isinstance(final_state, dict):
                print(
                    f"Note: final_state missing or not a dict (found: {type(final_state).__name__}) — skipping: {event_log}")
                skipped_empty_metrics += 1
                skipped_files.append(str(event_log))
                continue

            metrics = final_state.get('metrics')

            # Must be a non-empty dict
            if not isinstance(metrics, dict) or len(metrics) == 0:
                print(f"Note: Empty or missing final_state.metrics — skipping: {event_log}")
                skipped_empty_metrics += 1
                skipped_files.append(str(event_log))
                continue

            run_id = metadata.get('timestamp', event_log.parent.name)

            # Parse config from directory structure if not in metadata
            config_dir = event_log.parent.parent.name  # e.g., ctx0_fog00_p4ptrue_contract_none
            config_parts = config_dir.split('_')
            context = 'ctx1' in config_dir
            fog = config_parts[1][3:] if len(config_parts) > 1 else '00'
            p4p = 'p4ptrue' in config_dir
            contract = config_parts[-1] if len(config_parts) > 3 else 'none'

            # Grid/bucket from directory structure
            grid_dir = event_log.parent.parent.parent.name  # e.g., grid_000
            bucket_dir = event_log.parent.parent.parent.parent.name  # e.g., Independent_Both_have_optimal_paths

            # turns may be list/dict/None
            turns_obj = (data.get('game') or {}).get('turns', [])
            total_turns = len(turns_obj) if hasattr(turns_obj, '__len__') else 0

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
                'Total Turns': total_turns,
                'Format Errors': final_state.get('format_errors_total', 0),
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
                'Total P4P Arrangements Proposed': final_state.get('metrics', {}).get('total_p4p_arrangements_proposed', 0),
                'Total P4P Arrangements Accepted': final_state.get('metrics', {}).get('total_p4p_arrangements_accepted', 0),
                'Total P4P Arrangements Rejected': final_state.get('metrics', {}).get('total_p4p_arrangements_rejected', 0),
                'Total P4P Promises Kept': final_state.get('metrics', {}).get('total_p4p_promises_kept', 0),
                'Total P4P Promises Broken': final_state.get('metrics', {}).get('total_p4p_promises_broken', 0),
                'amount_received_by_0_from_trades': final_state.get('metrics', {}).get('amount_received_by_0_from_trades', 0),
                'amount_received_by_1_from_trades': final_state.get('metrics', {}).get('amount_received_by_1_from_trades', 0),
                'contract_accepted': final_state.get('metrics', {}).get('contract_accepted', 0),
                'contract_negotiaion_length': final_state.get('metrics', {}).get('contract_negotiaion_length', 0),
                'num_tiles_in_contract': final_state.get('metrics', {}).get('num_tiles_in_contract', 0),
                'num_tiles_promised_to_receive_from_contract_0': final_state.get('metrics', {}).get('num_tiles_promised_to_receive_from_contract_0', 0),
                'num_tiles_promised_to_receive_from_contract_1': final_state.get('metrics', {}).get('num_tiles_promised_to_receive_from_contract_1', 0),
                'moves_made_under_strict_contract_0': final_state.get('metrics', {}).get('moves_made_under_strict_contract_0', 0),
                'moves_made_under_strict_contract_1': final_state.get('metrics', {}).get('moves_made_under_strict_contract_1', 0),
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
            # print(f"Successfully processed run: {run_id}")

        except Exception as e:
            print(f"Error processing {event_log}: {str(e)}")
            continue

    if not rows:
        # Still show a summary of what happened before failing
        print(f"\nNo rows collected. Skipped due to empty/missing final_state or metrics: {skipped_empty_metrics}")
        if skipped_files:
            print("Files skipped (first 10 shown):")
            for f in skipped_files[:10]:
                print(f"  - {f}")
        raise ValueError("No valid experiment data found (all runs missing or with empty final_state.metrics).")

    # Create DataFrame and sort
    df = pd.DataFrame(rows)
    df = df.sort_values(['Bucket', 'Grid ID', 'Config ID', 'Run ID'])
    # Save with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_dir / f"all_runs_{timestamp}.csv", index=False)
    df.to_csv(output_dir / "all_runs_latest.csv", index=False)

    print(f"\nProcessed {len(df)} valid runs")
    print(f"Skipped runs with empty/missing final_state or metrics: {skipped_empty_metrics}")
    if skipped_files:
        print("Skipped files (first 10 shown):")
        for f in skipped_files[:10]:
            print(f"  - {f}")
    print(f"Earliest run: {df['Run ID'].min()}")
    print(f"Latest run: {df['Run ID'].max()}")
    print(f"\nSaved results to:")
    print(f"- {output_dir}/all_runs_{timestamp}.csv")
    print(f"- {output_dir}/all_runs_latest.csv")

    # Return df along with where/when we saved, so caller can reuse timestamp for per-pair files
    return df, output_dir, timestamp


def analyze_experiments(experiment_dir=None):
    """Load and analyze experiment data; save per-model-pair CSVs and print row counts only."""
    if experiment_dir is None:
        experiment_dir = "logs/experiments/per_grid"

    df, output_dir, timestamp = load_experiment_data(experiment_dir)

    _save_per_model_pair_csvs(df, output_dir, timestamp)
    _print_per_pair_counts(df)

    return df


if __name__ == "__main__":
    analyze_experiments()
