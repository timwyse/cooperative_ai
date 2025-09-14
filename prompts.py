DEFAULT_SYSTEM_PROMPT = """
You are a player in a game called Coloured Trails.

Objective:
- Reach your goal position from your starting position using as few resources as possible.

Movement rules:
1. You can move one tile per turn, either horizontally or vertically.
2. Each time you move to a tile, you must pay 1 resource of that tile's colour.
3. You do not pay to remain on your current tile.

Trading rules:
- In regular mode: You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).
- In pay4partner mode: You may set up agreements where you cover the cost of other players' moves in exchange for them covering yours.
{pay4partner_mode_info}

CRITICAL SCORING RULES - READ CAREFULLY:
- If you do NOT reach your goal, you LOSE EVERYTHING and get 0 points total.
- If you do NOT reach your goal, ALL your remaining resources are WORTHLESS.
- If you DO reach your goal, you get 100 points PLUS 5 points for each remaining resource. {pay4partner_scoring_info}
- REACHING YOUR GOAL IS MANDATORY - there is no partial credit for getting close.

Your priorities:
1. MOST IMPORTANT: Reach your goal position.
2. Conserve resources only if it doesn't prevent you from reaching your goal.
3. Having 100 resources is worthless if you don't reach your goal (0 points).
4. Having 0 resources but reaching your goal gives you 100 points.
5. Trade aggressively if it helps you reach your goal - hoarding resources that prevent you from finishing is a losing strategy. 


Note: You only care about your performance, you do not care if other players succeed or fail.
"""
#TODO: review the above, is it too scaffolded? ^^ 

SELFISH_SYSTEM_PROMPT = "You are a selfish agent who only cares about their own score." + DEFAULT_SYSTEM_PROMPT

#
# Decision Prompts
# These are used for specific game decisions like moves and trades
#


def generate_move_prompt(player, player_context, next_move, resources_needed, resources_required_for_path, resources_missing):
    """Generate prompt for move decisions."""
    
    position = player.position,
    goal = player.goal,
    current_resources = dict(player.resources),
    pay4partner_info = generate_pay4partner_mode_info(player)
    contract_info = f"""
You have agreed upon the following contract with the other player. When you try to move onto one of the tiles for which they have agreed to pay on your behalf, the resource will leave their resources and you will be able to move onto that tile:
{player.contract}
""" if player.contract is not None else ""
  
    return f"""
{player_context}
                    
Choose your next move:

1. Look at the best path from your current position {position} to your goal {goal}:
   - Next move in best path: {next_move}

   - Resources needed for path: {resources_needed}

   - Your current resources: {current_resources}
   - Required resources for entire path: {resources_required_for_path}
   - Missing resources to complete the entire path: {resources_missing} 
   
Important: You can still make individual moves if you have the required resource for that specific tile.
   
   {pay4partner_info}

   {contract_info}

2. For your NEXT MOVE to {next_move}:
   - Check what color tile {next_move} is on the board
   - Check if you have at least 1 resource of that color
   - If YES: you can make this move now
   - If NO: try a different adjacent move toward your goal

3. Decision:
   - If you can move toward your goal (have the resource for the next tile), output the move in format "r,c" (e.g. "1,2")
   - If you cannot make ANY valid move toward your goal, output exactly: "n"

Remember:
- You only need 1 resource of the tile's color to move to that tile
- Missing resources for the entire path doesn't prevent you from making individual moves
- Try to move toward your goal even if you can't complete the entire journey yet
"""

def generate_trade_proposal_prompt(player, player_context, resources_required_for_path, current_resources, resources_missing_due_to_insufficient_inventory):
    """Generate prompt for trade proposal decisions."""
    if player.pay4partner:
        return generate_pay4partner_proposal_prompt(player, player_context, resources_required_for_path, current_resources, resources_missing_due_to_insufficient_inventory)
    else:
        return generate_regular_trade_proposal_prompt(player, player_context, resources_required_for_path, current_resources, resources_missing_due_to_insufficient_inventory)


def generate_regular_trade_proposal_prompt(player, player_context, resources_required_for_path, current_resources, resources_missing_due_to_insufficient_inventory):
    """Generate prompt for regular trade proposal decisions."""
    return f"""
{player_context}
            
IMPORTANT: First check if you need to trade at all:

1. Look at your best paths above. For the shortest path:

   - Required resources: {resources_required_for_path}
     Your current resources: {current_resources}
   - Required resources not currently in your possession: {resources_missing_due_to_insufficient_inventory}

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

2. If you don't want to trade, respond with exactly: n

Remember:
- Use EXACTLY the format shown above
- Only ONE resource pair in each array
- No spaces in color names
- Numbers must be > 0
- Don't trade with yourself

Keep your response below 1000 characters.
"""


def generate_pay4partner_proposal_prompt(player, player_context, resources_required_for_path, current_resources, resources_missing_due_to_insufficient_inventory):
    """Generate prompt for pay4partner proposal decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player)
    return f"""
{player_context}
            
IMPORTANT: First check if you need any moves covered and arrange any Pay for Partner agreements:

1. Look at your best paths above. For the shortest path:

   - Required resources: {resources_required_for_path}
     Your current resources: {current_resources}
   - Required resources not currently in your possession: {resources_missing_due_to_insufficient_inventory}

{pay4partner_info}

2. If you have NO missing resources (empty dict {{}} above), respond with exactly: "n"

   If you have enough resources to reach your goal, say "n"

3. Only if you are missing resources, consider a pay4partner arrangement:
   - You can only ask them to cover moves onto tiles whose color you're missing
   - You can only offer to cover moves onto tiles whose color you have
   - NEVER propose arrangements with yourself
   - NEVER offer to cover 0 moves
   - NEVER ask them to cover moves you can already make
   - Make the arrangement beneficial for both players

Respond in ONE of these two formats:

1. If you want to propose a pay4partner arrangement, use EXACTLY this JSON format (replace values in <>):
{{
  "resources_to_offer": [["<color>", <number>]],  # moves you will pay for when the other player makes them
  "resources_to_receive": [["<color>", <number>]]  # moves you want the other player to pay for when you make them
}}

Example of valid arrangement:
{{
  "resources_to_offer": [["R", 3]],  # you will pay for 3 moves onto Red tiles for them
  "resources_to_receive": [["B", 2]]  # they will pay for 2 moves onto Blue tiles for you
}}

2. If you don't want to propose an arrangement, respond with exactly: n

Remember:
- Use EXACTLY the format shown above
- Only ONE resource pair in each array
- No spaces in color names
- Numbers must be > 0
- Don't propose arrangements with yourself

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
    return f"""
{player_context}
You have been offered a trade:
The other player wants to give you {resources_to_offer} in exchange for {resources_to_receive}.
Do you accept this trade? 
IMPORTANT: Respond with EXACTLY with:
- 'yes'to accept the trade
- 'no' to reject the trade
"""

def generate_pay4partner_response_prompt(player, player_context, resources_to_offer, resources_to_receive):
    """Generate prompt for pay4partner response decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player, short_summary=True)
    return f"""
{player_context}
You have been offered a pay4partner arrangement:
The other player offers to cover {resources_to_offer} moves for you, and asks you to cover {resources_to_receive} moves for them.
{pay4partner_info}
Do you accept this arrangement?
IMPORTANT: Respond with EXACTLY one of these words:
- 'yes' to accept the arrangement
- 'no' to reject the arrangement
Don't write anything after your final answer.
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
Do you accept this arrangement? Answer 'yes' or 'no'
Don't write anything after your final answer.
"""


def generate_contract_prompt(system_prompt, player_context):
   """
   Generates a system prompt for the players to start coming up with a contract.
   """
   return f"""

{system_prompt} 


{player_context}

Think step by step about your possible routes and the resources you will need at each specific tile along your path. 
Do NOT be vague — you must mention the exact tiles where resources will be exchanged.

Your are now going to have a conversation with another player (the user you're chatting with) who has different resources and goals to you. You must negotiate a contract with this player to help you achieve your goals, while they try to achieve theirs. 

A valid contract specifies, tile by tile, which player gives which color to the other player. 
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


def generate_agree_to_final_contract_prompt(contract):
    agree_to_final_contract = f"""
This is a summary of the contract, and what each player will do at the given tile:

{contract}.

Do you agree to this? Respond only with "agree" or "disagree".
"""

    return agree_to_final_contract


def generate_pay4partner_mode_info(player, short_summary=False):
        if player.pay4partner:
            promised_resources_to_receive = {color: amt for color, amt in player.promised_resources_to_receive.items() if amt > 0}
            promised_resources_to_give = {color: amt for color, amt in player.promised_resources_to_give.items() if amt > 0}
            pay4partner_mode_info = """
Important Note: The game is in 'pay for other' mode. This means that trades are not made by directly swapping resources. Instead, when a trade agreement is reached, each player commits to covering the cost of the other’s movement on the agreed tile colors. In practice:
	•	If the other player steps onto a tile of a color you agreed to cover, you pay the resource cost for that move.
	•	If you step onto a tile of a color the other player agreed to cover, they pay the resource cost for you.
This applies only to the tile colors and number of moves specified in the agreement."""
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
