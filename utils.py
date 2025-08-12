from collections import Counter

def freeze(obj):
    """Recursively convert dicts/lists into hashable, order-independent tuples."""
    if isinstance(obj, dict):
        return tuple(sorted((k, freeze(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(freeze(v) for v in obj)
    else:
        return obj

def check_for_repeated_states(game_states, n_repeats=3):
    """Check if the game has entered a repeated state."""
    hashable_states = [freeze(state) for state in game_states]
    state_counter = Counter(hashable_states)
    most_common_item, count = state_counter.most_common(1)[0]
    if count == n_repeats:
        print(f"Current game state has occurred {count} times, finishing the game.")
        return True
    elif count == n_repeats - 1:
        print(f"Current game state has occurred {count} times, game will stop if this occurs again.")
        return False
    else:
        return False
