from collections import Counter
import re

from constants import POINTS_FOR_WIN, POINTS_FOR_EXTRA_RESOURCE

def freeze(obj):
    """Recursively convert dicts/lists into hashable, order-independent tuples."""
    if isinstance(obj, dict):
        return tuple(sorted((k, freeze(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(freeze(v) for v in obj)
    else:
        return obj

def calculate_scores(players):
    """Calculate the score for a player based on their resources and whether they finished."""
    def compute_individual_score(player):
        if player.has_finished():
            return POINTS_FOR_WIN + POINTS_FOR_EXTRA_RESOURCE * sum(dict(player.resources).values())
        else:
            return 0
    for player in players:
        player.score = compute_individual_score(player)
    
    if players[0].contract and players[0].contract_type == 'contract_for_finishing':
        contracts = list(players[0].contract.values())
        player_0 = next(p for p in players if p.id == '0')
        player_1 = next(p for p in players if p.id == '1')

        if player_0.has_finished():
            for contract in contracts:
                if contract['giver'] == 'you':
                    player_0.score -= min(int(contract['amount']), POINTS_FOR_WIN)
                    player_1.score += min(int(contract['amount']), POINTS_FOR_WIN)
        
        if player_1.has_finished():
            for contract in contracts:
                 if contract['receiver'] == 'you':
                    player_0.score += min(int(contract['amount']), POINTS_FOR_WIN)
                    player_1.score -= min(int(contract['amount']), POINTS_FOR_WIN)
        
    return {player.name: player.score for player in players}


def get_last_alphabetic_word(text):
    # Find all alphabetic words in the text
    words = re.findall(r"[a-zA-Z]+", text)
    # Return the last word if the list is not empty
    return words[-1] if words else None