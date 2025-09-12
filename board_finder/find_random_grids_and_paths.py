"""
Generates N_SAMPLES random paths for a 6 by 6 grid with all blue and red tiles except green start tile (0,0) and green end tile (5,5) and checks them for existence of:
1. 10-step path of all blue (shortest path)
2. 12-step path of all blue
3. 14-step path of all blue
4. 10-step path of all blue and 1 red
5. 10-step path of all blue and 2 red
6. 10-step path of all blue and 3 red

7-12: Equivalent paths from red POV

Writes them to a jsonl.
Note that 37_C_17 > 2B so we generate random grids instead of all grids.
"""

import random
import json
import os
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

# === CONFIG ===
N_SAMPLES = 1_000_000   # number of random grids
N = 6
rows, cols = 6 , 6
num_B = 17
MAX_LEN = 15
OUTPUT_FILE = f"random_boards_classification_{rows}x{cols}.jsonl"
# fixed greens
fixed = {(0, 0): 'G', (rows-1, cols-1): 'G'}

# all positions except the fixed G’s
positions = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in fixed]

# adjacency helper
def neighbors(pos):
    r, c = pos
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        if 0 <= nr < N and 0 <= nc < N:
            yield (nr,nc)

# DFS path enumerator with max length limit
def enumerate_paths(grid, start, goal, max_len=12):
    paths = []
    def dfs(curr, visited, path):
        if len(path) > max_len:
            return
        if curr == goal:
            paths.append(path[:])
            return
        for nb in neighbors(curr):
            if nb not in visited:
                visited.add(nb)
                path.append(nb)
                dfs(nb, visited, path)
                path.pop()
                visited.remove(nb)
    dfs(start, {start}, [start])
    return paths

# path checker for both POVs
def check_path_conditions(grid):
    start, goal = (0,0), (5,5)
    all_paths = enumerate_paths(grid, start, goal, max_len=MAX_LEN)

    B_10_path = B_12_path = B_14_path = B_1_trade = B_2_trade = B_3_trade = False
    R_10_path = R_12_path = R_14_path = R_1_trade = R_2_trade = R_3_trade = False

    for path in all_paths:
        colors = [grid[r][c] for (r,c) in path[1:]]
        length = len(path) - 1
        b_count = colors.count('B')
        r_count = colors.count('R')
        g_count = colors.count('G')

        # --- Blue POV ---
        if length == 10 and b_count == 9 and r_count == 0 and g_count == 1:
            # needs = False
            B_10_path = True
        if length == 12 and b_count == 11 and r_count == 0 and g_count == 1:
            # needs = False
            B_12_path = True
        if length == 14 and b_count == 13 and r_count == 0 and g_count == 1:
            # needs = False
            B_14_path = True
            # short path with one trade exists
        if length == 10 and b_count == 8 and r_count == 1 and g_count == 1:
            B_1_trade = True
        if length == 10 and b_count == 7 and r_count == 2 and g_count == 1:
            B_2_trade = True
        if length == 10 and b_count == 6 and r_count == 3 and g_count == 1:
            B_3_trade = True

        # --- Red POV ---
        if length == 10 and r_count == 9 and b_count == 0 and g_count == 1:
            # needs = False
            R_10_path = True
        if length == 12 and r_count == 11 and b_count == 0 and g_count == 1:
            # needs = False
            R_12_path = True
        if length == 14 and r_count == 13 and b_count == 0 and g_count == 1:
            # needs = False
            R_14_path = True
            # short path with one trade exists
        if length == 10 and r_count == 8 and b_count == 1 and g_count == 1:
            R_1_trade = True
        if length == 10 and r_count == 7 and b_count == 2 and g_count == 1:
            R_2_trade = True
        if length == 10 and r_count == 6 and b_count == 3 and g_count == 1:
            R_3_trade = True

        if B_10_path and B_12_path and B_14_path and B_1_trade and B_2_trade and B_3_trade and R_10_path and R_12_path and  R_14_path and R_1_trade and R_2_trade and R_3_trade:
            break
    return {
            'B_10_path': B_10_path,
            'B_12_path': B_12_path,
            'B_14_path': B_14_path,
            'B_1_trade': B_1_trade,
            'B_2_trade': B_2_trade,
            'B_3_trade': B_3_trade,
            'R_10_path': R_10_path,
            'R_12_path': R_12_path,
            'R_14_path': R_14_path,
            'R_1_trade': R_1_trade,
            'R_2_trade': R_2_trade,
            'R_3_trade': R_3_trade,
        }


def classify_board(conditions):
    """Analyzes boolean conditions to calculate metrics and classify the board."""
    # Minimum and Maximum trades for the most efficient (10-step) path
    b_min_trades = -1
    if conditions['B_10_path']:
        b_min_trades = 0
    elif conditions['B_1_trade']:
        b_min_trades = 1
    elif conditions['B_2_trade']:
        b_min_trades = 2
    elif conditions['B_3_trade']:
        b_min_trades = 3

    r_min_trades = -1
    if conditions['R_10_path']:
        r_min_trades = 0
    elif conditions['R_1_trade']:
        r_min_trades = 1
    elif conditions['R_2_trade']:
        r_min_trades = 2
    elif conditions['R_3_trade']:
        r_min_trades = 3

    b_max_trades = -1
    if conditions['B_3_trade']:
        b_max_trades = 3
    elif conditions['B_2_trade']:
        b_max_trades = 2
    elif conditions['B_1_trade']:
        b_max_trades = 1
    elif conditions['B_10_path']:
        b_max_trades = 0

    r_max_trades = -1
    if conditions['R_3_trade']:
        r_max_trades = 3
    elif conditions['R_2_trade']:
        r_max_trades = 2
    elif conditions['R_1_trade']:
        r_max_trades = 1
    elif conditions['R_10_path']:
        r_max_trades = 0

    # Efficiency Choice Score
    b_efficiency_choice_score = -1
    if b_min_trades != -1 and b_max_trades != -1:
        b_efficiency_choice_score = b_max_trades - b_min_trades

    r_efficiency_choice_score = -1
    if r_min_trades != -1 and r_max_trades != -1:
        r_efficiency_choice_score = r_max_trades - r_min_trades

    # Asymmetry Metric
    trade_asymmetry = -1
    if b_min_trades != -1 and r_min_trades != -1:
        trade_asymmetry = abs(b_min_trades - r_min_trades)

    # CLASSIFY BOARD INTO BUCKETS
    bucket = "Uncategorized"

    # This checks if a long, pure path exists
    b_has_long_pure_path = conditions['B_12_path'] or conditions['B_14_path']
    r_has_long_pure_path = conditions['R_12_path'] or conditions['R_14_path']

    if b_min_trades > 0 and r_min_trades > 0:
        bucket = "Mutual Dependency"
    elif b_min_trades > 0 and r_min_trades == 0:
        bucket = "Needy Player (Blue)"
    elif r_min_trades > 0 and b_min_trades == 0:
        bucket = "Needy Player (Red)"

    # This captures the dilemma between a short/traded path and a long/pure path.
    elif b_min_trades > 0 and b_has_long_pure_path:
        bucket = "Path vs. Purity Dilemma (Blue)"
    elif r_min_trades > 0 and r_has_long_pure_path:
        bucket = "Path vs. Purity Dilemma (Red)"

    elif b_min_trades > 0 and b_efficiency_choice_score > 0:
        bucket = "Efficiency Trade-Off (Blue)"
    elif r_min_trades > 0 and r_efficiency_choice_score > 0:
        bucket = "Efficiency Trade-Off (Red)"
    elif b_min_trades == 0 and r_min_trades == 0:
        bucket = "Independent (Both have optimal paths)"

    metrics = {
        'b_min_trades_efficient_path': b_min_trades,
        'b_max_trades_efficient_path': b_max_trades,
        'b_efficiency_choice_score': b_efficiency_choice_score,
        'r_min_trades_efficient_path': r_min_trades,
        'r_max_trades_efficient_path': r_max_trades,
        'r_efficiency_choice_score': r_efficiency_choice_score,
        'trade_asymmetry': trade_asymmetry
    }
    return {"bucket": bucket, "metrics": metrics}

def build_random_grid(_):
    """Generate one random grid and check its conditions."""
    # sample positions for B
    combo = random.sample(positions, num_B)

    # fill grid
    grid = [[None] * cols for _ in range(rows)]
    for (r, c), v in fixed.items():
        grid[r][c] = v
    for (r, c) in combo:
        grid[r][c] = 'B'
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] is None:
                grid[r][c] = 'R'

    conds = check_path_conditions(grid)
    analysis = classify_board(conds)
    return {"grid": grid, "conditions": conds, "analysis": analysis}

# === MAIN EXECUTION ===
if __name__ == "__main__":
    num_existing = 0
    try:
        with open(OUTPUT_FILE, 'r') as f:
            num_existing = sum(1 for _ in f)
    except FileNotFoundError:
        print(f"Output file '{OUTPUT_FILE}' not found. Starting from scratch.")
        num_existing = 0

    samples_to_generate = N_SAMPLES - num_existing

    if samples_to_generate <= 0:
        print(f"Goal of {N_SAMPLES} samples already met. Found {num_existing} existing samples.")
        print("To generate more, increase N_SAMPLES or delete the output file.")
    else:
        print(f"Found {num_existing} existing samples. Generating {samples_to_generate} new samples...")

        # Open file in append mode 'a' to add new results without overwriting
        with ProcessPoolExecutor() as executor, open(OUTPUT_FILE, "a") as f:
            # Use chunksize for efficiency, sending work to processors in batches
            chunksize = max(1, min(1000, samples_to_generate // (os.cpu_count() or 1)))

            job = executor.map(build_random_grid, range(samples_to_generate), chunksize=chunksize)

            for result in tqdm(job, total=samples_to_generate, desc="Generating Boards"):
                json.dump(result, f)
                f.write("\n")

        print(f"Done. Total samples in file: {N_SAMPLES}")