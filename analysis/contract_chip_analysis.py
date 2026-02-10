# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import json
import glob
import os
import zipfile

def analyze_contract(experiments, analysis_label, condition_func):
    """
    Iterates through experiments, unzips files, parses logs, and applies
    a condition function to count specific contract occurrences.

    Args:
        experiments (dict): Dictionary of {folder_name: zip_filename}
        analysis_label (str): Description for the print output (e.g., "Invalid Chips")
        condition_func (function): A function that takes a contract dictionary
                                   and returns True if it matches criteria.
    """
    print(f"\n{'#'*30}")
    print(f"### STARTING ANALYSIS: {analysis_label}")
    print(f"{'#'*30}\n")

    for exp_folder_name, zip_name in experiments.items():
        print(f"--- Processing: {exp_folder_name} ---")

        # --- Unzip if needed ---
        if os.path.exists(zip_name):
            with zipfile.ZipFile(zip_name, 'r') as zip_ref:
                zip_ref.extractall(".")
        else:
            if not os.path.exists(exp_folder_name):
                print(f"⚠️ Zip {zip_name} not found and folder missing. Skipping.")
                continue

        # --- Search Pattern ---
        search_pattern = f"**/{exp_folder_name}/**/event_log_*.json"
        all_files = glob.glob(search_pattern, recursive=True)

        total_matches = 0
        grids_with_matches = 0
        matched_grid_ids = []

        # --- Analysis Loop ---
        for filepath in sorted(all_files):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                # Navigate: data -> game -> final_contract_state -> contract
                game_data = data.get("game", {})
                final_state = game_data.get("final_contract_state", {})
                contracts = final_state.get("contract", {})

                if not contracts:
                    continue

                found_in_this_grid = False

                for details in contracts.values():
                    # Apply the custom condition passed to the function
                    if condition_func(details):
                        total_matches += 1
                        found_in_this_grid = True

                if found_in_this_grid:
                    grids_with_matches += 1

                    # Extract Grid ID
                    path_parts = filepath.split(os.sep)
                    grid_id = next((part for part in path_parts if part.startswith("grid_")), "unknown_grid")
                    matched_grid_ids.append(grid_id)

            except Exception as e:
                pass

        # --- Results for this Experiment ---
        print(f"Total {analysis_label}: {total_matches}")
        print(f"Grids containing at least one: {grids_with_matches}")
        print(f"List of Grids: {matched_grid_ids}\n")


def check_invalid_chips(details):
    """Logic for invalid promises (P1 gives R or P0 gives B)."""
    giver = details.get("giver")
    color = details.get("color")
    return (giver == "Player 1" and color == "R") or \
           (giver == "Player 0" and color == "B")


def check_green_chips(details):
    """Logic for green chips."""
    return details.get("color") == "G"


def main():
    # 1. Define experiments
    experiments = {
        "Mutual_Dependency": "Mutual_Dependency.zip",
        "Needy_Player_Blue": "Needy_Player_Blue.zip",
        "Independent_Both_have_optimal_paths": "Independent_Both_have_optimal_paths.zip"
    }

    # 2. Run First Analysis (Invalid Promises)
    analyze_contract(
        experiments=experiments,
        analysis_label="Invalid Chips Promised",
        condition_func=check_invalid_chips
    )

    # 3. Run Second Analysis (Green Chips)
    analyze_contract(
        experiments=experiments,
        analysis_label="Green Chips Promised",
        condition_func=check_green_chips
    )

if __name__ == "__main__":
    main()