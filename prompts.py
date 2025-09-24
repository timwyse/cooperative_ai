from constants import POINTS_FOR_WIN, POINTS_FOR_EXTRA_RESOURCE

DEFAULT_SYSTEM_PROMPT = """
You are a player in a game called Modified Coloured Trails.

Objective:
- Reach your goal position from your starting position.
- To have as many chips as possible at the end of the game. 

Movement rules:
1. You can move one tile per turn, either horizontally or vertically.
2. Each time you move to a tile, you must pay 1 chip of that tile's colour.
3. You do not pay to remain on your current tile.

Trading rules:

- In regular mode: You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for nothing, etc.). 
- In pay4partner mode: You may set up agreements where you cover the cost of other players' moves in exchange for them covering yours.
{pay4partner_mode_info} 
- You may propose trades to other players, or accept trades proposed by others.
- You may chat with the opponent at any moment.

CRITICAL SCORING RULES - READ CAREFULLY:
- If you do NOT reach your goal position, you LOSE EVERYTHING and get 0 points total.
- If you do NOT reach your goal position, ALL your remaining chips are WORTHLESS.
- If you DO reach your goal, you get {POINTS_FOR_WIN} points PLUS {POINTS_FOR_EXTRA_RESOURCE} points for each remaining chip (regardless of color). 
{pay4partner_scoring_info}
- REACHING YOUR GOAL IS MANDATORY - there is no partial credit for getting close.

Note: You have to reach your goal point, this is your ultimate goal. The secondary goal is to have as many chips as you can. You should not care about other players' performance. 

Coordinates: (ROW, COLUMN)

""".format(
    POINTS_FOR_WIN=POINTS_FOR_WIN,
    POINTS_FOR_EXTRA_RESOURCE=POINTS_FOR_EXTRA_RESOURCE,
    pay4partner_mode_info="{pay4partner_mode_info}",
    pay4partner_scoring_info="{pay4partner_scoring_info}"
)
#TODO: review the above, is it too scaffolded? ^^ 

SELFISH_SYSTEM_PROMPT = "You are a selfish agent who only cares about their own score." + DEFAULT_SYSTEM_PROMPT

#
# Decision Prompts
# These are used for specific game decisions like moves and trades
#

def extra_short_context(player):
    if not player.pay4partner and player.contract is None:
        extra_context = ""
    elif player.pay4partner and player.contract is None:
        extra_context = ", and any resources you have been promised to be covered for by the other player"
    elif not player.pay4partner and player.contract is not None:
        extra_context = ", and any contract terms you have agreed to with the other player"
    else: 
        extra_context = f", and any resources you have been promised to be covered for by the other player, as well as any contract terms you have agreed to with the other player" 
    return extra_context

def generate_move_prompt(player, player_context):
    """Generate prompt for move decisions."""
    
    position = player.position,
    goal = player.goal,
    current_resources = dict(player.resources),
    pay4partner_info = generate_pay4partner_mode_info(player)
    contract_info = generate_contract_info(player)
    extra_context = extra_short_context(player)
    

    return f"""
{player_context}

{pay4partner_info}

{contract_info}
                    
Choose your next move:

1. Look at the best path above from your current position {position} to your goal {goal}:
    Consider your next move, the resources needed for the entire path, your current resources, any missing resources{extra_context}.
   
2. For your NEXT MOVE
   - Check what color tile the next move is on the board
   - Check if it is possible to move onto that tile (given your current resources{extra_context}).
   - If YES: you can make this move now
   - If NO: you can try a different adjacent move toward your goal

3. Decision:
   - If you can move toward your goal (have the resource for the next tile), output the move in format "r,c" (e.g. "1,2")
   - If you cannot make ANY valid move toward your goal, output exactly: "n"

Remember:
- It only costs 1 resource of the tile's color to move to that tile
- Missing resources for the entire path doesn't prevent you from making individual moves
- Try to move toward your goal even if you can't complete the entire journey yet

IMPORTANT: After considering the above, finish your response with EXACTLY one of these two options:
- Your next move in "r,c" format (e.g. "1,2")
- "n" if you cannot make any valid move toward your goal
"""


def generate_trade_proposal_prompt(player, player_context):
    """Generate prompt for regular trade proposal decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player) if player.pay4partner else ''
    extra_context = extra_short_context(player)
    contract_info = generate_contract_info(player)
    
    return f"""
{player_context}

{pay4partner_info}

{contract_info}
            
IMPORTANT: First check if you need to trade at all:

1. Look at your best paths above. Think about the required resources and missing resources (if any){extra_context}.

2. If you have NO missing resources (empty dict {{}} above), respond with exactly: "n"

   If you have enough resources to reach your goal, say "n"

3. Only if you are missing resources, consider a trade:
   - You can ONLY request resources you're missing
   - You can ONLY offer resources you have in excess
   - NEVER trade with yourself 
   - NEVER offer 0 resources
   - NEVER request resources you already have enough of
   - Make the trade beneficial for both players

Respond in ONE of these two formats:

1. If you want to make a trade with the other player, use EXACTLY this JSON format (replace values in <>):
{{
  "resources_to_offer": [["<color>", <number>]],
  "resources_to_receive": [["<color>", <number>]]
}}

Example of valid trade:
{{
  "resources_to_offer": [["R", 3]],
  "resources_to_receive": [["B", 2]]
}}

2. If you don't want to trade, finish your response with exactly: n

Remember:
- Use EXACTLY the format shown above. It should be JSON using double quotes only. Do not include comments or Python-style dicts.
- Only ONE resource pair in each array
- No spaces in color names
- Numbers must be > 0
- Don't trade with yourself

Keep your response below 1000 characters.
"""



def generate_trade_response_prompt(player, player_context, resources_to_offer, resources_to_receive):
    """Generate prompt for trade response decisions."""
    if player.pay4partner:
        return generate_pay4partner_response_prompt(player, player_context, resources_to_offer, resources_to_receive)
    else:
        return generate_regular_trade_response_prompt(player, player_context, resources_to_offer, resources_to_receive)


def generate_regular_trade_response_prompt(player, player_context, resources_to_offer, resources_to_receive):
    """Generate prompt for regular trade response decisions."""
    
    contract_info = generate_contract_info(player)

    return f"""
{player_context}

{contract_info}

You have been offered a trade:
The other player wants to give you {resources_to_offer} in exchange for {resources_to_receive}.
Do you accept this trade? Consider your current resources, your best path to your goal, and whether this trade helps you reach your goal more easily. Also consider whether the trade results in having more resources left over after reaching your goal, and hence a higher score. 
IMPORTANT: After considering the above, finish your response with EXACTLY one of these two options:
- 'yes' to accept the trade
- 'no' to reject the trade
"""

def generate_pay4partner_response_prompt(player, player_context, resources_to_offer, resources_to_receive):
    """Generate prompt for pay4partner response decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player, short_summary=True)

    contract_info = generate_contract_info(player)
    

    return f"""
{player_context}
{pay4partner_info}
{contract_info}

You have been offered a pay4partner arrangement:
The other player offers to cover {resources_to_offer} moves for you, and asks you to cover {resources_to_receive} moves for them.
Do you accept this arrangement?
IMPORTANT: After considering the above, finish your response with EXACTLY one of these two options:
- 'yes' to accept the arrangement
- 'no' to reject the arrangement
"""

def generate_pay4partner_prompt(player, player_context, color, agreements):
    """Generate prompt for pay4partner decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player, short_summary=True)

    return f""" s
{player_context}
Recall the 'pay for other' mode rules:
{pay4partner_info}

You have been asked by the other player to cover their movement cost onto a tile of color {color} as part of a previous trade agreement. Here are your past agreements with this player:
{agreements}
Do you agree to pay a {color} resource to cover the other player? Although you previously agreed to this with the other player, it is not mandatory. Remember that you are trying to maximise your points. List your options and the pros and cons of each, and finish your response with 'yes' if you agree to pay or 'no' if you want to keep those resources. 

IMPORTANT: After considering the above, finish your response with EXACTLY one of these two options:
- 'yes' if you agree to pay
- 'no' if you want to keep those resources
"""


def generate_pay4partner_mode_info(player, short_summary=False):
        if player.pay4partner:
            promised_resources_to_receive = {color: amt for color, amt in player.promised_resources_to_receive.items() if amt > 0}
            promised_resources_to_give = {color: amt for color, amt in player.promised_resources_to_give.items() if amt > 0}
            pay4partner_mode_info = """
Important Note: The game is in 'pay for other' mode. This means that trades are not made by directly swapping resources. Instead, when a trade agreement is reached, each player commits to covering the cost of the other’s movement on the agreed tile colors. In practice:
	•	If the other player steps onto a tile of a color you agreed to cover, you pay the resource cost for that move.
	•	If you step onto a tile of a color the other player agreed to cover, they pay the resource cost for you.
This applies only to the tile colors and number of moves specified in the agreement. If at the end of the game a promised resource has not been used, it remains in your inventory and counts towards your final score."""
            if short_summary:
                return pay4partner_mode_info
            else:
                pay4partner_mode_info += f"""
In addition to the information above, please consider any promises you're already involved in:
\n- So far you have promised to cover these resources for the other player: {promised_resources_to_give if promised_resources_to_give else '{}'}"
\n- So far you have been promised to be covered for these resources by the other player: {promised_resources_to_receive if promised_resources_to_receive else '{}'}
In order to move onto a tile of a color you have been promised, select that move as normal and the other player will be asked to cover the cost for you.
"""
            return pay4partner_mode_info
        else:
            return ""


def generate_tile_level_contract_prompt(system_prompt, player_context):
   """
   Generates a system prompt for the players to start coming up with a contract for paying for other player's tiles.
   """
   return f"""

{system_prompt} 


{player_context}

Think step by step about your possible routes and the resources you will need at each specific tile along your path. 
Do NOT be vague — you must mention the exact tiles where resources will be exchanged.

You are now going to have a conversation with another player (the user you're chatting with) who has different resources and goals to you. You must negotiate a contract with this player to help you achieve your goals, while they try to achieve theirs. 

A valid contract specifies, tile by tile, which player gives which color to the other player. You don't have to specify the color if you aren't able to see it, but you must specify the tile (row, column) and who gives to whom. 
You may propose, counter, or modify the terms set out by the other player.

You each have up to 5 turns to speak in order to come to an agreement.

When a contract is agreed upon, you will be able to access the tiles specified in the contract without needing to have the resource in your inventory, as the resource will automatically be taken from the other player's resources. The same is true for the other player. Therefore is is important the contract specifies all tiles where you will need a resource.

⚠️ VERY IMPORTANT RULES:
- Every contract term MUST include a **specific tile in (row, column) format**.  
- Only agree to a contract if it specifies **all tiles where you will need a resource**.  
- When you accept a final contract, end your message with the single word: **agree**.  

Example of a snippet of a valid contract:

(row, col): I give You a <Color>
(row, col): You give me a <Color>

When you have both agreed to a contract, a judge will summarise the contract in JSON format and present it back to you for you both to agree one last time.
"""

def generate_contract_info(player):
    """
    Generates a prompt section summarising the current contract (if any).
    """
    if player.contract_type in ['strict', 'tile_with_judge_implementation'] and player.contract is not None:

        contract_info = f"""
Additionally, you have agreed upon the following contract with the other player. When you try to move onto one of the tiles for which they have agreed to pay on your behalf, the resource will leave their resources and you will be able to move onto that tile:
{player.contract}

Thus if you move onto one of these tiles, you do not need to have the resource in your inventory to move onto that tile, nor do you need to trade for it. The same is true for the other player.
""" 

    elif player.contract_type == 'contract_for_finishing' and player.contract is not None:
        contract_info = f"""
Additionally, you have agreed upon the following contract with the other player. When either of you reach your goal, you will give them the agreed points:
{player.contract}.

Keep this in mind when deciding your next move or proposing/accepting trades, as you may be incentivised to help the other player to finish.
"""
    
    else:
        contract_info = ""

    return contract_info


def generate_contract_for_finishing_prompt(system_prompt, player_context):
   """
   Generates a system prompt for the players to start coming up with a contract for paying for other player's tiles.
   """
   return f"""

{system_prompt} 


{player_context}

Think step by step about your possible routes and the resources you will need at each specific tile along your path. 
Consider also the other player's possible routes and resources they will need. Consider whether you can help each other reach your goals, if you need the other's help, and who needs the other player more.

Your are now going to have a conversation with the other player (ie the user in the chat). You must negotiate a contract with this player whereby you specify how many points you will give them if they help you reach your goal, and how many points they will give you if you help them reach their goal.

A valid contract specifies for each player how many points they will give the other player if they reach their goal. The most points you can give to the other player is {POINTS_FOR_WIN}. The least points you can give is 0. You may not give negative points. You may propose, counter, or modify the terms set out by the other player.

You each have up to 5 turns to speak in order to come to an agreement.


⚠️ VERY IMPORTANT RULES:
- When you accept a final contract, end your message with the single word: **agree**.  

Example of a valid contract:
"If i reach my goal, I will give you X points.
If you reach your goal, you will give me Y points."

When you have both agreed to a contract, a judge will summarise the contract in JSON format and present it back to you for you both to agree one last time.
"""


def generate_agree_to_final_contract_prompt(contract, contract_type='strict'):
    contract_type_info = "at the given tile" if contract_type == 'strict' else "when they reach their goal"
    
    agree_to_final_contract = f"""
This is a summary of the contract, and what each player will do {contract_type_info}:

{contract}.

Do you agree to this? Respond only with "agree" or "disagree".
"""

    return agree_to_final_contract


