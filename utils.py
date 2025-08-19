from collections import Counter

def freeze(obj):
    """Recursively convert dicts/lists into hashable, order-independent tuples."""
    if isinstance(obj, dict):
        return tuple(sorted((k, freeze(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(freeze(v) for v in obj)
    else:
        return obj
