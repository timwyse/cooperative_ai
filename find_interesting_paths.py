import itertools
import json
from math import comb
from collections import Counter
from itertools import islice
import os


# grid size
N = 5

# fixed positions for 'G'
fixed = {(0,0): 'G', (4,4): 'G'}

# all grid positions
positions = [(r,c) for r in range(N) for c in range(N) if (r,c) not in fixed]

# number of B's to place
num_B = 12
MAX_LEN = 12
# total combinations
total = comb(len(positions), num_B)
print(f"Total configurations: {total}")

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
    start, goal = (0,0), (4,4)
    all_paths = enumerate_paths(grid, start, goal, max_len=MAX_LEN)

    B_cond1 = B_cond2 = B_cond3 = False
    R_cond1 = R_cond2 = R_cond3 = False

    for path in all_paths:
        colors = [grid[r][c] for (r,c) in path[1:]]
        length = len(path) - 1
        b_count = colors.count('B')
        r_count = colors.count('R')
        g_count = colors.count('G')

        # --- Blue POV ---
        if length == 8 and b_count == 7 and g_count == 1 and r_count == 0:
            # needs = False
            B_cond1 = True
        if length > 8 and b_count == (length-1) and g_count == 1 and r_count == 0:
            # has a longer path
            B_cond2 = True
            # short path with one trade exists
        if length == 8 and b_count == 6 and r_count == 1 and g_count == 1:
            B_cond3 = True

        # --- Red POV ---
        if length == 8 and r_count == 7 and g_count == 1 and b_count == 0:
            # needs = False
            R_cond1 = True
        if length > 8 and r_count == (length-1) and g_count == 1 and b_count == 0:
            # has a longer path
            R_cond2 = True
        if length == 8 and r_count == 6 and b_count == 1 and g_count == 1:
            # short path with one trade exists
            R_cond3 = True

        if B_cond1 and B_cond2 and B_cond3 and R_cond1 and R_cond2 and R_cond3:
            break

    return B_cond1, B_cond2, B_cond3, R_cond1, R_cond2, R_cond3

def classify_board(grid):
    start, goal = (0,0), (4,4)
    all_paths = enumerate_paths(grid, start, goal, max_len=MAX_LEN)

    # Track best/worst for each player
    stats = {"B": {"min_trades": float("inf"), "max_trades": -1},
             "R": {"min_trades": float("inf"), "max_trades": -1}}

    for path in all_paths:
        colors = [grid[r][c] for (r,c) in path[1:]]
        b_count = colors.count("B")
        r_count = colors.count("R")

        # For Blue, "trades" are red squares encountered
        stats["B"]["min_trades"] = min(stats["B"]["min_trades"], r_count)
        stats["B"]["max_trades"] = max(stats["B"]["max_trades"], r_count)
        # For Red, "trades" are blue squares encountered
        stats["R"]["min_trades"] = min(stats["R"]["min_trades"], b_count)
        stats["R"]["max_trades"] = max(stats["R"]["max_trades"], b_count)

    # --- Scores ---
    asymmetry_score = abs(stats["B"]["min_trades"] - stats["R"]["min_trades"])
    efficiency_score = (
        (stats["B"]["max_trades"] - stats["B"]["min_trades"]) +
        (stats["R"]["max_trades"] - stats["R"]["min_trades"])
    )
    symmetry = (stats["B"]["min_trades"] > 0 and stats["R"]["min_trades"] > 0)

    return {
        "symmetry": symmetry,
        "asymmetry_score": asymmetry_score,
        "efficiency_score": efficiency_score,
        "stats": stats
    }

# open file to stream results in JSON Lines format
output_file = "boards_and_properties.jsonl"

# Count how many boards already generated
if os.path.exists(output_file):
    with open(output_file, "r") as f:
        already_done = sum(1 for _ in f)
else:
    already_done = 0

BATCH_SIZE = 100  # how many boards to generate per run

with open(output_file, "a") as f:  # append mode
    for i, combo in enumerate(
            islice(itertools.combinations(positions, num_B),
                   already_done,
                   already_done + BATCH_SIZE),
            start=already_done+1):

        # Build the grid
        grid = [[None]*N for _ in range(N)]
        for (r,c), v in fixed.items():
            grid[r][c] = v
        for (r,c) in combo:
            grid[r][c] = "B"
        for (r,c) in positions:
            if grid[r][c] is None:
                grid[r][c] = "R"

        # Classification (replace with your function)
        result = {
            "grid": grid,
            "classification": classify_board(grid)  # << uses your new scoring
        }

        json.dump(result, f)
        f.write("\n")

    print(f"Generated boards {already_done+1} to {already_done+BATCH_SIZE}")

