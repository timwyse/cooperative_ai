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

{trading_rules}
{pay4partner_mode_info} 
- You may propose trades to other players, or accept / reject trades proposed by others.
- You may chat with the opponent at any moment.

CRITICAL SCORING RULES - READ CAREFULLY:
- If you do NOT reach your goal position, you LOSE EVERYTHING and get 0 points total.
- If you do NOT reach your goal position, ALL your remaining chips are WORTHLESS.
- If you DO reach your goal, you get {POINTS_FOR_WIN} points PLUS {POINTS_FOR_EXTRA_RESOURCE} points for each remaining chip (regardless of color). 

- REACHING YOUR GOAL IS MANDATORY - there is no partial credit for getting close.

Note: You have to reach your goal point, this is your ultimate goal. The secondary goal is to have as many chips as you can. You should not care about other players' performance. 

Coordinates: (ROW, COLUMN)

""".format(
    POINTS_FOR_WIN=POINTS_FOR_WIN,
    POINTS_FOR_EXTRA_RESOURCE=POINTS_FOR_EXTRA_RESOURCE,
    trading_rules="{trading_rules}",
    pay4partner_mode_info="{pay4partner_mode_info}",
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

def generate_trade_system_info(player):
    if not player.pay4partner:
        trading_rules = """- You are in 'regular' mode: You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for nothing, etc.)."""
    else:
        trading_rules = """- You are in 'pay for other' mode: You may set up agreements where you cover the cost of other players' moves when they move onto a tile of a resource you have, in exchange for them covering you."""
    return trading_rules

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

1. Consider your best path from your current position {position} to your goal {goal}:
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
- Try to move toward your goal even if you don't have all the resources to complete the entire journey yet

IMPORTANT: use EXACTLY this JSON format (replace values in <>):
- Your rationale: Explain your reasoning for your next move
- Your next move in "r,c" format (e.g. "1,2")
- "n" if you cannot make any valid move toward your goal


{{
  "rationale": "First explain your reasoning: Why do you want to move (or not move) to this particular place on the board? How will it fit with your later moves? How does this help you reach your goal?",
  "decision": <either "move" or "n">,
  "move": <if decision is "move", the move in "r,c" format (e.g. "1,2"); if decision is "n", this should be an empty string "">
}}

Example of valid move:
{{
  "rationale": "i am at (0, 0).  \nmy goal is at (3, 3).  \ni have: {{'b': 10, 'g': 1, 'r': 0}}\n\ngiven my resources, \n(0,0) → (1,0) → (2,0) → (3,0) → (3,1) → (3,2) → (3,3)  \ncorresponding tile colours for each step:  \nrow 0: (0,0) = g (starting spot), (1,0) = b, (2,0) = r  (3,0) = b, (3,1)=b, (3,2)=b, (3,3)=g seems like a good plan. \n\nfirst step: move to (1,0), which is colour **b**.  \ni have **10** blue resources.\n\ncheck other adjacent moves from (0,0) to be safe: \n(0,1) = r, which I don't have any of, so let's stick with my first plan, moving to (1,0).",
  "decision": "move",
  "move": "1,0"
  }}

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

1. Consider your best path to your goal. Think about the required resources and missing resources (if any){extra_context}.

2. If you have enough of the required resources to reach your goal, say "n"

3. Only if you are missing resources needed to reach your goal, consider a trade:
   - You can ONLY request resources you're missing
   - You can ONLY offer resources you have in excess
   - NEVER trade with yourself 
   - NEVER offer 0 resources
   - NEVER request resources you already have enough of
   - Make the trade beneficial for both players

Think step by step about your situation. First analyze your position and needs, then make your decision using ONE of these two formats:

1. If you want to make a trade with the other player, use EXACTLY this JSON format (replace values in <>):
{{
  "rationale": "First explain your reasoning: Why do you want to trade? Why these specific resources and quantities? How does this help you reach your goal?",
  "want_to_trade": true,
  "resources_to_offer": [
    {{
      "color": "<color>",
      "quantity": <number>
    }}
  ],
  "resources_to_receive": [
    {{
      "color": "<color>",
      "quantity": <number>
    }}
  ]
}}

Example of valid trade:
{{
  "rationale": "I need blue resources to reach my goal efficiently. I have excess red resources that I won't need for my path. Trading 3 red for 2 blue helps me take a shorter path while still having enough resources left.",
  "want_to_trade": true,
  "resources_to_offer": [
    {{
      "color": "R",
      "quantity": 3
    }}
  ],
  "resources_to_receive": [
    {{
      "color": "B",
      "quantity": 2
    }}
  ]
}}

2. If you don't want to trade, use EXACTLY this JSON format:
{{
  "rationale": "Explain why you don't want to trade. Do you have all the resources you need? Is there no beneficial trade possible?",
  "want_to_trade": false
}}

Example of no trade:
{{
  "rationale": "I don't need to trade because there is a path to my goal that I can take using only my current resources.",
  "want_to_trade": false
}}

Remember:
- Use EXACTLY the format shown above. It should be JSON using double quotes only. Do not include comments or Python-style dicts.
- Only ONE resource pair in each array
- No spaces in color names
- Numbers must be > 0
- Don't trade with yourself
- Explain your reasoning in the rationale field

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

Think step by step about whether to accept this trade. Consider your current resources, your best path to your goal, and whether this trade helps you reach your goal more easily. Also consider whether the trade results in having more resources left over after reaching your goal, and hence a higher score.

Once you have decided, use this EXACT JSON format:

{{
  "rationale": "Your thinking process and reasoning for accepting or rejecting this trade",
  "answer": "yes" or "no"
}}

Example of accepting a trade:
{{
  "rationale": "This trade gives me 2 blue resources which I need for my optimal path, and I can afford to give up 3 red resources since I have excess. This will help me reach my goal faster.",
  "answer": "yes"
}}

Example of rejecting a trade:
{{
  "rationale": "This trade doesn't help me reach my goal efficiently. I would lose resources I need for my path and gain resources I don't need. I can reach my goal without this trade.",
  "answer": "no"
}}

Keep your response below 500 tokens.
"""

def generate_pay4partner_response_prompt(player, player_context, resources_to_offer, resources_to_receive):
    """Generate prompt for pay4partner response decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player, short_summary=True)

    contract_info = generate_contract_info(player)
    

    return f"""
{player_context}
{pay4partner_info}
{contract_info}

You have been offered a 'pay for other' arrangement:
The other player offers to cover {resources_to_offer} moves for you, and asks you to cover {resources_to_receive} moves for them.
Do you accept this arrangement?
IMPORTANT: After considering the above, finish your response with EXACTLY one of these two options:
- 'yes' to accept the arrangement
- 'no' to reject the arrangement
"""

def generate_pay4partner_prompt(player, player_context, color, agreements):
    """Generate prompt for pay4partner decisions."""
    pay4partner_info = generate_pay4partner_mode_info(player, short_summary=True)

    return f"""
{player_context}
Recall the 'pay for other' mode rules:
{pay4partner_info}

You have been asked by the other player to cover their movement cost onto a tile of color {color} as part of a previous trade agreement. Here are your past agreements with this player:
{agreements}

Think step by step about whether to agree to pay for the other player's move. Consider your current resources, your goal, and whether honoring this agreement helps you in the long run. Remember that you are trying to maximize your points.

Once you have decided, use this EXACT JSON format:

{{
  "rationale": "Your thinking process and reasoning for agreeing or refusing to pay",
  "answer": "yes" or "no"
}}

Example of agreeing to pay:
{{
  "rationale": "I have enough {color} resources and honoring this agreement maintains trust for future cooperation. This helps both of us reach our goals.",
  "answer": "yes"
}}

Example of refusing to pay:
{{
  "rationale": "I need to conserve my {color} resources for my own path to the goal. The agreement was made but my survival comes first.",
  "answer": "no"
}}
"""

def generate_pay4partner_mode_info(player, short_summary=False):
    if player.pay4partner:
        promised_resources_to_receive = {color: amt for color, amt in player.promised_resources_to_receive.items() if amt > 0}
        promised_resources_to_give = {color: amt for color, amt in player.promised_resources_to_give.items() if amt > 0}
        pay4partner_mode_info = """
Important Note: The game is in 'pay for other' mode. This means that trades are not made by directly swapping resources. Instead, when a trade agreement is reached, each player commits to covering the cost of the other’s movement on the agreed tile colors. In practice:
•	If the other player steps onto a tile of a color you agreed to cover, you pay the resource cost for that move.
•	If you step onto a tile of a color the other player agreed to cover, they pay the resource cost for you.
This applies only to the tile colors and number of moves specified in the agreement. If at the end of the game a resource that you promised has not been used, it remains in your inventory and counts towards your final score. The same applies to resources promised to you by the other player."""
        if short_summary:
            return pay4partner_mode_info
        else:
            pay4partner_mode_info += f"""
In addition to the information above, please consider any promises you're already involved in:
\n- So far you have promised to cover these resources for the other player: {promised_resources_to_give if promised_resources_to_give else '{}'}"
\n- So far you have been promised to be covered for these resources by the other player: {promised_resources_to_receive if promised_resources_to_receive else '{}'}
In order to move onto a tile of a color you have been promised, select that move as normal and the other player will be asked to cover the cost for you.

IMPORTANT: After considering the above, finish your response with EXACTLY one of these two options:
- 'yes' if you agree to pay
- 'no' if you want to keep those resources
"""
    else:
        pay4partner_mode_info = ""
    return pay4partner_mode_info

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


def generate_tile_level_contract_prompt(system_prompt, player_context):
   """
   Generates a system prompt for the players to start coming up with a contract for paying for other player's tiles.
   """
   return f"""

{system_prompt} 


{player_context}

Think step by step about your possible routes and the resources you will need at each specific tile along your path. 
Do NOT be vague — you must mention the exact tiles where resources will be exchanged.

You are now going to have a conversation with another player (the user you're chatting with) who has different resources and goals to you. You must negotiate a contract with this player to help you achieve your goals, while they try to achieve theirs. Note that although this player appears as the 'user' in your chat, they are also an AI agent similar to you.

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


def generate_contract_for_finishing_prompt(system_prompt, player_context):
   """
   Generates a system prompt for the players to start coming up with a contract for paying for other player's tiles.
   """
   return f"""

{system_prompt} 


{player_context}

Think step by step about your possible routes and the resources you will need at each specific tile along your path. 
Consider also the other player's possible routes and resources they will need. Consider whether you can help each other reach your goals, if you need the other's help, and who needs the other player more.

Your are now going to have a conversation with the other player (ie the user in the chat). You must negotiate a contract with this player whereby you specify how many points you will give them if they help you reach your goal, and how many points they will give you if you help them reach their goal. Note that although this player appears as the 'user' in your chat, they are also an AI agent similar to you.

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

Do you agree to this contract? Answer in the following EXACT format:
{{
  "rationale": "Your thinking process and reasoning for agreeing or refusing to pay",
  "answer": "yes" or "no"
}}
"""

    return agree_to_final_contract


