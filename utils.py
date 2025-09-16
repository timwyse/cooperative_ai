from collections import Counter

from constants import POINTS_FOR_WIN, POINTS_FOR_EXTRA_RESOURCE

def freeze(obj):
    """Recursively convert dicts/lists into hashable, order-independent tuples."""
    if isinstance(obj, dict):
        return tuple(sorted((k, freeze(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(freeze(v) for v in obj)
    else:
        return obj

def calculate_score(player):
    """Calculate the score for a player based on their resources and whether they finished."""
    if player.has_finished():
        return POINTS_FOR_WIN + POINTS_FOR_EXTRA_RESOURCE * sum(dict(player.resources).values())
    else:
        return 0