DEFAULT_SYSTEM_PROMPT = """
You are a player in a game called Coloured Trails.

Objective:
- Reach your goal position from your starting position using as few resources as possible.

Movement rules:
1. You can move one tile per turn, either horizontally or vertically.
2. Each time you move to a tile, you must pay 1 resource of that tile's colour.
3. You do not pay to remain on your current tile.

Trading rules:
- You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).
- You may propose trades to other players, or accept trades proposed by others.
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

def generate_move_prompt(player_context, position, goal, next_move, resources_needed, current_resources, resources_required_for_path, resources_missing, pay4partner_info=""):
    """Generate prompt for move decisions."""
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

def generate_trade_proposal_prompt(player_context, resources_required_for_path, current_resources, resources_missing_due_to_insufficient_inventory, pay4partner_info=""):
    """Generate prompt for trade proposal decisions."""
    return f"""
{player_context}
            
IMPORTANT: First check if you need to trade at all:

1. Look at your best paths above. For the shortest path:

   - Required resources: {resources_required_for_path}
     Your current resources: {current_resources}
   - Required resources not currently in your possession: {resources_missing_due_to_insufficient_inventory}

{pay4partner_info}

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

def generate_trade_response_prompt(player_context, resources_to_offer, resources_to_receive, pay4partner_info=""):
    """Generate prompt for trade response decisions."""
    return f"""
{player_context}
You have been offered a trade:
The other player wants to give you {resources_to_offer} in exchange for {resources_to_receive}. {pay4partner_info}
Do you accept this trade? Answer 'yes' or 'no'.
"""

def generate_pay4partner_prompt(player_context, pay4partner_info, color, agreements):
    """Generate prompt for pay4partner decisions."""
    return f"""
{player_context}
Recall the 'pay for other' mode rules:
{pay4partner_info}

You have been asked by the other player to cover their movement cost onto a tile of color {color} as part of a previous trade agreement. Here are your past aggreements with this player:
{agreements}
Do you agree to pay a {color} resource to cover the other player? Although you previously agreed to this with the other player, it is not mandatory. Remember that you are trying to maximise your points. List your options and the pros and cons of each, and finish your response with 'yes' if you agree to pay or 'no' if you want to keep those resources.
"""