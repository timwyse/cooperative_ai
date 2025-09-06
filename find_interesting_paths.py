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

# open file to stream results in JSON Lines format
with open("boards_and_properties.jsonl", "w") as f:
    for i, combo in enumerate(itertools.combinations(positions, num_B), start=1):
        grid = [[None]*N for _ in range(N)]
        
        # place fixed 'G'
        for (r,c), v in fixed.items():
            grid[r][c] = v

        # place 'B'
        for (r,c) in combo:
            grid[r][c] = 'B'

        # place 'R' in the rest
        for (r,c) in positions:
            if grid[r][c] is None:
                grid[r][c] = 'R'

        # check path conditions
        conds = check_path_conditions(grid)

        # dump grid and path condition flags as JSON line
        json.dump({"grid": grid, "conditions": conds}, f)
        f.write("\n")

        # progress update every 100,000
        if i % 100_000 == 0:
            print(f"Written {i}/{total} configurations...")
