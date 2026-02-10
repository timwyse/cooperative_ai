"""
Generates all boards for a n by n grid with all blue and red tiles
except green start tile (0,0) and green end tile (bottom right)
and checks them for existence of paths with the following conditions:

Shortest path for blue with no trades
Shortest path + 2 for blue with no trades
Shortest path + 4 for blue with no trades
Shortest for blue with 1 trade
Shortest for blue with 2 trades
Shortest for blue with 3 trades
Equivalent paths from red POV

Writes them to a jsonl (~1,000,000 rows.)
"""

from concurrent.futures import ProcessPoolExecutor
import itertools
import json
from math import comb
from collections import Counter

# grid size
N = 4

# fixed positions for 'G'
FIXED = {(0,0): 'G', (N-1,N-1): 'G'}

# all grid positions
positions = [(r,c) for r in range(N) for c in range(N) if (r,c) not in FIXED]

# number of Blues's to place
num_B = (N**2 - 2) // 2  # half of remaining positions
MAX_LEN = 13
# total combinations
total = comb(len(positions), num_B)
# print(f"Total configurations: {total}")

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
    start, goal = (0,0), (3,3)
    all_paths = enumerate_paths(grid, start, goal, max_len=MAX_LEN)
    short_path_length = 2 * (N - 1)
    short_plus_2_path_length = short_path_length + 2
    short_plus_4_path_length = short_path_length + 4

    B_short_pure_path = B_pure_plus_2_path = B_pure_plus_4_path = B_1_trade = B_2_trade = B_3_trade = False
    R_short_pure_path = R_pure_plus_2_path = R_pure_plus_4_path = R_1_trade = R_2_trade = R_3_trade = False

    for path in all_paths:
        colors = [grid[r][c] for (r,c) in path[1:]]
        length = len(path) - 1
        b_count = colors.count('B')
        r_count = colors.count('R')
        g_count = colors.count('G')

        # --- Blue POV ---
        if length == short_path_length and b_count == short_path_length - 1 and r_count == 0 and g_count == 1:
            # needs = False
            B_short_pure_path = True
        if length == short_plus_2_path_length and b_count == short_plus_2_path_length - 1 and r_count == 0 and g_count == 1:
            # needs = False
            B_pure_plus_2_path = True
        if length == short_plus_4_path_length and b_count == short_plus_4_path_length - 1 and r_count == 0 and g_count == 1:
            # needs = False
            B_pure_plus_4_path = True
            # short path with one trade exists
        if length == short_path_length and b_count == short_path_length - 2 and r_count == 1 and g_count == 1:
            B_1_trade = True
        if length == short_path_length and b_count == short_path_length - 3 and r_count == 2 and g_count == 1:
            B_2_trade = True
        if length == short_path_length and b_count == short_path_length - 4 and r_count == 3 and g_count == 1:
            B_3_trade = True

        # --- Red POV ---
        if length == short_path_length and r_count == short_path_length - 1 and b_count == 0 and g_count == 1:
            R_short_pure_path = True
        if length == short_plus_2_path_length and r_count == short_plus_2_path_length - 1 and b_count == 0 and g_count == 1:
            R_pure_plus_2_path = True
        if length == short_plus_4_path_length and r_count == short_plus_4_path_length - 1 and b_count == 0 and g_count == 1:
            R_pure_plus_4_path = True
        if length == short_path_length and r_count == short_path_length - 2 and b_count == 1 and g_count == 1:
            R_1_trade = True
        if length == short_path_length and r_count == short_path_length - 3 and b_count == 2 and g_count == 1:
            R_2_trade = True
        if length == short_path_length and r_count == short_path_length - 4 and b_count == 3 and g_count == 1:
            R_3_trade = True
        
        if (B_short_pure_path and R_short_pure_path and
            B_pure_plus_2_path and R_pure_plus_2_path and
            B_pure_plus_4_path and R_pure_plus_4_path and
            B_1_trade and R_1_trade and
            B_2_trade and R_2_trade and
            B_3_trade and R_3_trade):
                break
    return {
            'B_short_pure_path': B_short_pure_path,
            'B_pure_plus_2_path': B_pure_plus_2_path,
            'B_pure_plus_4_path': B_pure_plus_4_path,
            'B_1_trade': B_1_trade,
            'B_2_trade': B_2_trade,
            'B_3_trade': B_3_trade,
            'R_short_pure_path': R_short_pure_path,
            'R_pure_plus_2_path': R_pure_plus_2_path,
            'R_pure_plus_4_path': R_pure_plus_4_path,
            'R_1_trade': R_1_trade,
            'R_2_trade': R_2_trade,
            'R_3_trade': R_3_trade
        }
        

def classify_board(conditions):
    """Analyzes boolean conditions to calculate metrics and classify the board."""
    # Minimum and Maximum trades for the most efficient (10-step) path
    b_min_trades = -1
    if conditions['B_short_pure_path']:
        b_min_trades = 0
    elif conditions['B_1_trade']:
        b_min_trades = 1
    elif conditions['B_2_trade']:
        b_min_trades = 2
    elif conditions['B_3_trade']:
        b_min_trades = 3

    r_min_trades = -1
    if conditions['R_short_pure_path']:
        r_min_trades = 0
    elif conditions['R_1_trade']:
        r_min_trades = 1
    elif conditions['R_2_trade']:
        r_min_trades = 2
    elif conditions['R_3_trade']:
        r_min_trades = 3

    b_max_trades = -1
    if conditions['R_3_trade']:
        b_max_trades = 3
    elif conditions['R_2_trade']:
        b_max_trades = 2
    elif conditions['R_1_trade']:
        b_max_trades = 1
    elif conditions['B_short_pure_path']:
        b_max_trades = 0

    r_max_trades = -1
    if conditions['R_3_trade']:
        r_max_trades = 3
    elif conditions['R_2_trade']:
        r_max_trades = 2
    elif conditions['R_1_trade']:
        r_max_trades = 1
    elif conditions['R_short_pure_path']:
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
    b_has_long_pure_path = conditions['B_pure_plus_2_path'] or conditions['B_pure_plus_4_path']
    r_has_long_pure_path = conditions['R_pure_plus_2_path'] or conditions['R_pure_plus_4_path']

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



# your existing function (unchanged)
def process_grid(combo):
    grid = [[None]*N for _ in range(N)]
    for (r,c), v in FIXED.items():
        grid[r][c] = v
    for (r,c) in combo:
        grid[r][c] = 'B'
    for r in range(N):
        for c in range(N):
            if grid[r][c] is None:
                grid[r][c] = 'R'
    conds = check_path_conditions(grid)
    analysis = classify_board(conds)
    return {"grid": grid, "conditions": conds, "analysis": analysis}

# positions and number of B’s


if __name__ == "__main__":
    
    all_combos = itertools.combinations(positions, num_B)
    if total > 10_000_000:
        raise ValueError(f"Too many combinations ({total}), reduce grid size or change num_B")

    from tqdm import tqdm
    with ProcessPoolExecutor() as executor, open(f"board_finder/boards_properties_{N}_by_{N}.jsonl", "w") as f:
        for result in tqdm(executor.map(process_grid, all_combos, chunksize=1000), total=total):
            json.dump(result, f)
            f.write("\n")
