from collections import Counter

def compute_best_routes(grid, start_pos, goal_pos, resources):
    """
    Returns two routes:
    1) fewest_resources_needed_path
    2) shortest_path_with_fewest_resources_needed
    """

    def _neighbors(pos, rows, cols):
        r, c = pos
        if r > 0: yield (r - 1, c)
        if r < rows - 1: yield (r + 1, c)
        if c > 0: yield (r, c - 1)
        if c < cols - 1: yield (r, c + 1)

    def _path_colors(path, grid):
        # pay when you move ONTO a tile, i.e. path[1:]
        return [grid.get_color(r, c) for (r, c) in path[1:]]

    def _enumerate_paths(grid, start, goal):
        rows = cols = grid.size
        paths = []

        def dfs(curr, visited, path):
            if curr == goal:
                paths.append(path[:]); return
            for nb in _neighbors(curr, rows, cols):
                if nb not in visited:
                    visited.add(nb); path.append(nb)
                    dfs(nb, visited, path)
                    path.pop(); visited.remove(nb)

        dfs(start, {start}, [start])
        return paths

    all_paths = _enumerate_paths(grid, start_pos, goal_pos)

    scored = []
    for p in all_paths:
        colors = _path_colors(p, grid)
        needed = Counter(colors)
        shortfall = {res: max(0, needed[res] - resources.get(res, 0)) for res in needed}
        shortfall = {res: amt for res, amt in shortfall.items() if amt > 0}
        scored.append({
            "path": p,
            "path_length_in_steps": len(p) - 1,
            "resources_required_for_path": dict(needed),
            "resources_missing_due_to_insufficient_inventory": shortfall,
        })

    fewest = sorted(
        scored,
        key=lambda x: (sum(x["resources_missing_due_to_insufficient_inventory"].values()),
                       x["path_length_in_steps"])
    )[0]

    shortest_with_fewest = sorted(
        scored,
        key=lambda x: (x["path_length_in_steps"],
                       sum(x["resources_missing_due_to_insufficient_inventory"].values()))
    )[0]

    return [fewest, shortest_with_fewest]
