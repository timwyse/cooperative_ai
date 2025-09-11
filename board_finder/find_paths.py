"""
Generates all paths for a 5 by 5 grid with all blue and red tiles except green start tile (0,0) and green end tile (4,4) and checks them for existence of:
1. 8-step path of all blue (shortest path)
2. 10-step path of all blue
3. 12-step path of all blue
4. 8-step path of all blue and 1 red
5. 8-step path of all blue and 2 red
6. 8-step path of all blue and 3 red

7-12: Equivalent paths from red POV

Writes them to a jsonl (~1,000,000 rows.)
"""

from concurrent.futures import ProcessPoolExecutor
import itertools
import json
from math import comb
from collections import Counter

# grid size
N = 5

# fixed positions for 'G'
fixed = {(0,0): 'G', (4,4): 'G'}

# all grid positions
positions = [(r,c) for r in range(N) for c in range(N) if (r,c) not in fixed]

# number of B's to place
num_B = 12
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
    start, goal = (0,0), (4,4)
    all_paths = enumerate_paths(grid, start, goal, max_len=MAX_LEN)

    B_8_path = B_10_path = B_12_path = B_1_trade = B_2_trade = B_3_trade = False
    R_8_path = R_10_path = R_12_path = R_1_trade = R_2_trade = R_3_trade = False

    for path in all_paths:
        colors = [grid[r][c] for (r,c) in path[1:]]
        length = len(path) - 1
        b_count = colors.count('B')
        r_count = colors.count('R')
        g_count = colors.count('G')

        # --- Blue POV ---
        if length == 8 and b_count == 7 and r_count == 0 and g_count == 1:
            # needs = False
            B_8_path = True
        if length == 10 and b_count == 9 and r_count == 0 and g_count == 1:
            # needs = False
            B_10_path = True
        if length == 12 and b_count == 11 and r_count == 0 and g_count == 1:
            # needs = False
            B_12_path = True
            # short path with one trade exists
        if length == 8 and b_count == 6 and r_count == 1 and g_count == 1:
            B_1_trade = True
        if length == 8 and b_count == 5 and r_count == 2 and g_count == 1:
            B_2_trade = True
        if length == 8 and b_count == 4 and r_count == 3 and g_count == 1:
            B_3_trade = True

        # --- Red POV ---
        if length == 8 and r_count == 7 and b_count == 0 and g_count == 1:
            # needs = False
            R_8_path = True
        if length == 10 and r_count == 9 and b_count == 0 and g_count == 1:
            # needs = False
            R_10_path = True
        if length == 12 and r_count == 11 and b_count == 0 and g_count == 1:
            # needs = False
            R_12_path = True
            # short path with one trade exists
        if length == 8 and r_count == 6 and b_count == 1 and g_count == 1:
            R_1_trade = True
        if length == 8 and r_count == 5 and b_count == 2 and g_count == 1:
            R_2_trade = True
        if length == 8 and r_count == 4 and b_count == 3 and g_count == 1:
            R_3_trade = True

        if B_8_path and B_10_path and B_12_path and B_1_trade and B_2_trade and B_3_trade and R_8_path and R_10_path and R_12_path and R_1_trade and R_2_trade and R_3_trade:
            break
    return {
            'B_8_path': B_8_path,
            'B_10_path': B_10_path,
            'B_12_path': B_12_path,
            'B_1_trade': B_1_trade,
            'B_2_trade': B_2_trade,
            'B_3_trade': B_3_trade,
            'R_8_path': R_8_path,
            'R_10_path': R_10_path,
            'R_12_path': R_12_path,
            'R_1_trade': R_1_trade,
            'R_2_trade': R_2_trade,
            'R_3_trade': R_3_trade,
        }


# your existing function (unchanged)
def process_grid(combo):
    grid = [[None]*5 for _ in range(5)]
    fixed = {(0,0): 'G', (4,4): 'G'}
    for (r,c), v in fixed.items():
        grid[r][c] = v
    for (r,c) in combo:
        grid[r][c] = 'B'
    for r in range(5):
        for c in range(5):
            if grid[r][c] is None:
                grid[r][c] = 'R'
    conds = check_path_conditions(grid)
    return {"grid": grid, "conditions": conds}

# positions and number of B’s


if __name__ == "__main__":
    
    all_combos = itertools.combinations(positions, num_B)

    from tqdm import tqdm
    with ProcessPoolExecutor() as executor, open("boards_properties.jsonl", "w") as f:
        for result in tqdm(executor.map(process_grid, all_combos, chunksize=1000), total=total):
            json.dump(result, f)
            f.write("\n")
