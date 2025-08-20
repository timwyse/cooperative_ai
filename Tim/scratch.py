# %%
import os
from together import Together
from player import DEEPSEEK, QWEN_2_7B, LLAMA_3_3B

client = Together(api_key=os.environ.get("TOGETHER_API_KEY"))

# Example: Chat model query
response = client.chat.completions.create(
    model=QWEN_2_7B.value,
    messages=[{"role": "user", "content": "Tell me fun things to do in New York"}],
)
print(response.choices[0].message.content)
# %%
from collections import Counter, deque
from typing import List, Tuple, Dict, Any, Optional

Grid = List[List[str]]      # 2D array of color strings, e.g. [["R","G"],["B","R"]]
Pos = Tuple[int, int]       # (row, col)
Path = List[Pos]            # list of positions, including start and goal

def _neighbors(pos: Pos, rows: int, cols: int) -> List[Pos]:
    r, c = pos
    nbrs = []
    if r > 0: nbrs.append((r-1, c))
    if r < rows-1: nbrs.append((r+1, c))
    if c > 0: nbrs.append((r, c-1))
    if c < cols-1: nbrs.append((r, c+1))
    return nbrs

def _path_colors(path: Path, grid: Grid) -> List[str]:
    """Colors paid along a path; you pay when you move ONTO a tile, i.e. path[1:]."""
    return [grid[r][c] for (r, c) in path[1:]]

def _shortfall_for_colors(colors: List[str], resources: Dict[str, int]) -> int:
    need = Counter(colors)
    have = Counter(resources)
    return sum(max(0, need[c] - have.get(c, 0)) for c in need)

def _enumerate_paths(
    grid: Grid,
    start: Pos,
    goal: Pos,
    allow_revisit: bool = False,
    max_steps: Optional[int] = None
) -> List[Path]:
    """Enumerate paths from start to goal.
       - If allow_revisit=False (default), generates all simple paths (no revisits).
       - If allow_revisit=True, allows revisits but caps exploration by max_steps.
    """
    rows, cols = len(grid), len(grid[0])
    paths: List[Path] = []

    if allow_revisit:
        if max_steps is None:
            max_steps = rows * cols * 2  # sane default
        q = deque([[start]])
        while q:
            p = q.popleft()
            if len(p) - 1 > max_steps:
                continue
            last = p[-1]
            if last == goal:
                paths.append(p)
                # keep exploring; longer-but-valid paths might still be ranked (but usually lower)
            for nb in _neighbors(last, rows, cols):
                q.append(p + [nb])
        return paths

    # Simple paths (no revisits) via DFS
    def dfs(curr: Pos, visited: set, path: Path):
        if curr == goal:
            paths.append(path[:])
            return
        for nb in _neighbors(curr, rows, cols):
            if nb not in visited:
                visited.add(nb)
                path.append(nb)
                dfs(nb, visited, path)
                path.pop()
                visited.remove(nb)

    dfs(start, {start}, [start])
    return paths

def top_n_paths(
    grid: Grid,
    start: Pos,
    goal: Pos,
    resources: Dict[str, int],
    n: int,
    allow_revisit: bool = False,
    max_steps: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return up to n best paths sorted by:
       1) resource shortfall ascending
       2) path length descending
       Each result item includes: path, length, shortfall, required_counts, resources.
    """
    all_paths = _enumerate_paths(grid, start, goal, allow_revisit, max_steps)
    scored = []
    for p in all_paths:
        colors = _path_colors(p, grid)
        shortfall = _shortfall_for_colors(colors, resources)
        scored.append({
            "path": p,
            "length": len(p) - 1,
            "shortfall": shortfall,
            "required_counts": dict(Counter(colors)),
            "resources": dict(resources),
        })
    scored.sort(key=lambda x: (x["shortfall"], x["length"]))
    return scored[:n]
# %%
grid=[['R', 'R', 'G'],
      ['G', 'R', 'G'],
      ['R','G', 'R']]
start = (0, 0)
goal  = (2, 2)
resources = {"R": 6, "G": 0}

best = top_n_paths(grid, start, goal, resources, n=3)  # simple paths on a 2x2
for i, item in enumerate(best, 1):
    print(i, item)
# %%
