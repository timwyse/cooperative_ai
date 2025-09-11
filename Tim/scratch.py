# # %%
# import os
# from together import Together
# from player import DEEPSEEK, QWEN_2_7B, LLAMA_3_3B
# from constants import TOGETHER_API_KEY, OPENAI_API_KEY

# client_1 = Together(api_key=TOGETHER_API_KEY)

# # Example: Chat model query
# response = client_1.chat.completions.create(
#     model=QWEN_2_7B.value,
#     messages=[{"role": "user", "content": "Tell me fun things to do in New York"}],
# )
# print(response.choices[0].message.content)
# # %%
# DEFAULT_SYSTEM_PROMPT = """
# You are a player in a game called Coloured Trails.

# Objective:
# - Reach your goal position from your starting position using as few resources as possible.
# - You only care about how many points you finish on; you do not care about outperforming other players.

# Movement rules:
# 1. You can move one tile per turn, either horizontally or vertically.
# 2. Each time you move to a tile, you must pay 1 resource of that tile's colour.
# 3. You do not pay to remain on your current tile.

# Trading rules:
# - You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).
# - You may propose trades to other players, or accept trades proposed by others.

# Scoring:
# - You gain 100 points if you reach your goal.
# - If you do not reach your goal, you get 100 points minus 15 points for each tile between your final position and your goal.
# - You gain 5 points for each resource you still hold at the end of the game.

# Your priorities:
# Always maximise your total points. Note that reaching your goal is the most important way to do this. Consider the distance to your goal and the resources you will need to reach it.
# """

# %%

from openai import OpenAI
from together import Together
from constants import OPENAI_API_KEY, TOGETHER_API_KEY
import re

# Two different clients/models (could be OpenAI, TogetherAI, etc.)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
together_client = Together(api_key=TOGETHER_API_KEY)

system_prompt_player_B = """\nYou are a player in a game called Coloured Trails.\n\nObjective:\n- Reach your goal position from your starting position using as few resources as possible.\n\nMovement rules:\n1. You can move one tile per turn, either horizontally or vertically.\n2. Each time you move to a tile, you must pay 1 resource of that tile's colour.\n3. You do not pay to remain on your current tile.\n\nTrading rules:\n- You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).\n- You may propose trades to other players, or accept trades proposed by others.\n\nImportant Note: The game is in 'pay for other' mode. This means that trades are not made by directly swapping resources. Instead, when a trade agreement is reached, each player commits to covering the cost of the other’s movement on the agreed tile colors. In practice:\n\t•\tIf the other player steps onto a tile of a color you agreed to cover, you pay the resource cost for that move.\n\t•\tIf you step onto a tile of a color the other player agreed to cover, they pay the resource cost for you.\nThis applies only to the tile colors and number of moves specified in the agreement.\n\nCRITICAL SCORING RULES - READ CAREFULLY:\n- If you do NOT reach your goal, you LOSE EVERYTHING and get 0 points total.\n- If you do NOT reach your goal, ALL your remaining resources are WORTHLESS.\n- If you DO reach your goal, you get 100 points PLUS 5 points for each remaining resource. In 'pay for other' mode, any resources you have promised to give to other players as part of trade agreements are still counted as your resources (and hence potential contributors to your final score) until you actually give them away.\n- REACHING YOUR GOAL IS MANDATORY - there is no partial credit for getting close.\n\nYour priorities:\n1. MOST IMPORTANT: Reach your goal position.\n2. Conserve resources only if it doesn't prevent you from reaching your goal.\n3. Having 100 resources is worthless if you don't reach your goal (0 points).\n4. Having 0 resources but reaching your goal gives you 100 points.\n5. Trade aggressively if it helps you reach your goal - hoarding resources that prevent you from finishing is a losing strategy. \n\n\nNote: You only care about your performance, you do not care if other players succeed or fail.\n

 \n\n=== GAME STATUS FOR YOU - TURN 0 ===\n\n- You are at position (0, 0)\n- Your goal is at (3, 3)\n- Your resources: {'B': 10, 'G': 0, 'R': 0}\n- Resources you have promised to give to other players (still yours, not yet given): {'R': 0, 'B': 0, 'G': 0}\n- Resources you have been promised to receive from other players (still theirs, not yet received): {'R': 0, 'B': 0, 'G': 0}\n
The other player's resources: {'B': 0, 'G': 0, 'R': 10}.
 - Distance to goal: 6 steps\n\nBOARD LAYOUT:\nRow 0: G B R B\nRow 1: B R B R\nRow 2: R B R B\nRow 3: B R B R\n\nHISTORY OF EVENTS:\nThis is the first turn.\n\n            \nIMPORTANT: First check if you need to trade at all:\n\n1. For the shortest path:\n\n   - Required resources: {'B': 3, 'R': 3}\n     Your current resources: {'B': 10, 'G': 0, 'R': 0}\n   - Required resources not currently in your possession: {'R': 3}. Think about your route and the resources you will need at each step.
Your goal now is to come up with a contract with the other player in which you state at what turns you will need a resource from them, and what you offer in return to the other player. They will negotiate the terms of the trade with you and 
If the other player suggests a contract you agree to then finsih your response with 'agree'.

Your goal now is to come up with a contract with the other player in which you state at what tiles you will need a resource from them, and what you offer in return to the other player. They will negotiate the terms of the trade with you and agree or accept. You have 5 turns each to speak in order to come up with a contract with the other player. The contract must specify:
 For each tile, whether either player gives a color to the other player in order for them to access that tile. Example below:
 
 Turn number:
 (1,1): I give you Blue
 (2, 1): You give me red
 (3, 2): You give me red
 (3,3): I give you Blue
 
 IMPORTANT: when you agree to a contract, make sure the last word you say is 'agree'!
 
 When you have both agreed to a contract, a judge will summarise the contract and present it back to you for you both to agree one last time. 
"""

system_prompt_player_R = """\nYou are a player in a game called Coloured Trails.\n\nObjective:\n- Reach your goal position from your starting position using as few resources as possible.\n\nMovement rules:\n1. You can move one tile per turn, either horizontally or vertically.\n2. Each time you move to a tile, you must pay 1 resource of that tile's colour.\n3. You do not pay to remain on your current tile.\n\nTrading rules:\n- You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).\n- You may propose trades to other players, or accept trades proposed by others.\n\nImportant Note: The game is in 'pay for other' mode. This means that trades are not made by directly swapping resources. Instead, when a trade agreement is reached, each player commits to covering the cost of the other’s movement on the agreed tile colors. In practice:\n\t•\tIf the other player steps onto a tile of a color you agreed to cover, you pay the resource cost for that move.\n\t•\tIf you step onto a tile of a color the other player agreed to cover, they pay the resource cost for you.\nThis applies only to the tile colors and number of moves specified in the agreement.\n\nCRITICAL SCORING RULES - READ CAREFULLY:\n- If you do NOT reach your goal, you LOSE EVERYTHING and get 0 points total.\n- If you do NOT reach your goal, ALL your remaining resources are WORTHLESS.\n- If you DO reach your goal, you get 100 points PLUS 5 points for each remaining resource. In 'pay for other' mode, any resources you have promised to give to other players as part of trade agreements are still counted as your resources (and hence potential contributors to your final score) until you actually give them away.\n- REACHING YOUR GOAL IS MANDATORY - there is no partial credit for getting close.\n\nYour priorities:\n1. MOST IMPORTANT: Reach your goal position.\n2. Conserve resources only if it doesn't prevent you from reaching your goal.\n3. Having 100 resources is worthless if you don't reach your goal (0 points).\n4. Having 0 resources but reaching your goal gives you 100 points.\n5. Trade aggressively if it helps you reach your goal - hoarding resources that prevent you from finishing is a losing strategy. \n\n\nNote: You only care about your performance, you do not care if other players succeed or fail.\n

 \n\n=== GAME STATUS FOR YOU - TURN 0 ===\n\n- You are at position (0, 0)\n- Your goal is at (3, 3)\n- Your resources: {'B': 0, 'G': 0, 'R': 10} \n- Resources you have promised to give to other players (still yours, not yet given): {'R': 0, 'B': 0, 'G': 0}\n- Resources you have been promised to receive from other players (still theirs, not yet received): {'R': 0, 'B': 0, 'G': 0}\n
The other player's resources: {'B': 10, 'G': 0, 'R': 0}.
 - Distance to goal: 6 steps\n\n
 BOARD LAYOUT:\n
 Row 0: G B R B\n
 Row 1: B R B R\n
 Row 2: R B R B\n
 Row 3: B R B R\n\nHISTORY OF EVENTS:\nThis is the first turn.\n\n            \nIMPORTANT: First check if you need to trade at all:\n\n1. For the shortest path:\n\n   - Required resources: {'B': 3, 'R': 3}\n     Your current resources: {'B': 10, 'G': 0, 'R': 0}\n   - Required resources not currently in your possession: {'R': 3}. Think about your route and the resources you will need at each step.

 Your goal now is to come up with a contract with the other player in which you state at what tiles you will need a resource from them, and what you offer in return to the other player. They will negotiate the terms of the trade with you and agree or accept. You have 5 turns each to speak in order to come up with a contract with the other player. The contract must specify:
 For each tile, whether either player gives a color to the other player in order for them to access that tile. Example below:
 
 Turn number:
 (1,1): I give you Blue
 (2, 1): You give me red
 (3, 2): You give me red
 (3,3): I give you Blue
 
 IMPORTANT: when you agree to a contract, make sure the last word you say is 'agree'!
 
 When you have both agreed to a contract, a judge will summarise the contract and present it back to you for you both to agree one last time. 
"""

def message_starts_or_ends_with_agree(text):
    
    # Find all alphabetic words in the text
    words = re.findall(r"[a-zA-Z]+", text)
    # Return the last word if the list is not empty
    if words:
        return words[0] == 'agree' or words[-1] == "agree"
        
    return "None"

def chat_with_model(client, model, history):
    """Send a conversation history to a model and return its reply."""
    response = client.chat.completions.create(
        model=model,
        messages=history,
        max_tokens=300,
    )
    return response.choices[0].message.content


# Each player maintains their own view of the conversation
history_R = [{"role": "system", "content":system_prompt_player_R}]
history_B = [{"role": "system", "content":system_prompt_player_B}]

# Seed the conversation
initial_message = "Let's begin negotiation. What would you like to propose?"
history_R.append({"role": "user", "content": initial_message})
history_B.append({"role": "assistant", "content": initial_message})

# Alternating dialogue
agree = False
for turn in range(5):  # number of exchanges
    turn_message = f"Turn: {turn + 1}" if turn < 4 else "Turn: {turn + 1} (final turn)"
    print(turn_message)
    response_B = ""
    response_R = chat_with_model(openai_client, "gpt-4.1", history_R)
    print(f"Player R: {response_R}")
    history_R.append({"role": "assistant", "content": response_R})
    history_B.append({"role": "user", "content": response_R})
    if message_starts_or_ends_with_agree(response_R.lower()) and message_starts_or_ends_with_agree(response_B.lower()):
        agree = True
        break

    # Player B replies
    response_B = chat_with_model(openai_client, "gpt-4.1", history_B)
    print(f"Player B: {response_B}")
    history_B.append({"role": "assistant", "content": f"{turn_message}: {response_B}"})
    history_R.append({"role": "user", "content": f"{turn_message}: {response_B}"})

    if message_starts_or_ends_with_agree(response_R.lower()) and message_starts_or_ends_with_agree(response_B.lower()):
        agree = True
        break
if agree == True:

    conversation_formatted = history_R[1:]
    conversation_formatted = ", \n".join([f"{entry['role']}. {entry['content']} \n" for entry in conversation_formatted])

    conversation_formatted = conversation_formatted.replace("user:", "player 1:").replace("assistant:", "player 2:")
    judge_system_prompt = "You are a judge whose goal is to summaries a contract created between two players."
    judge_message = f"""
    You are a judge in a Colored Trails negotiation.  
Two players (Player 1 and Player 2) have discussed a possible contract to trade resources.  

Conversation:
"{conversation_formatted}"

Your task:
1. If no agreement has been reached, reply with exactly:
"N"
(no quotes).  

2. Otherwise, output a summary of the contract as valid JSON only, with no extra explanation or text.  
Each entry should specify the tile coordinate, the giving player, the receiving player, and the resource color.  

The JSON format must be:  
{{
  "(row, col)": {{
    "giver": "Player X",
    "receiver": "Player Y",
    "color": "<Color>"
  }},
  "(row, col)": {{
    "giver": "Player X",
    "receiver": "Player Y",
    "color": "<Color>"
  }}
}}

Example:
{{
  "(1, 1)": {{
    "giver": "Player 1",
    "receiver": "Player 2",
    "color": "Red"
  }},
  "(2, 2)": {{
    "giver": "Player 1",
    "receiver": "Player 2",
    "color": "Blue"
  }}
}}
    """

    judge_conversation = [
{"role": "system", "content": judge_system_prompt},
    {"role": "user", "content": judge_message}
]
    judge_contract = chat_with_model(openai_client, "gpt-4.1", judge_conversation)

    judge_contract_for_R = judge_contract.lower().replace("player 1", "you").replace("player 2", "the other player")
    judge_contract_for_B = judge_contract.lower().replace("player 2", "you").replace("player 1", "the other player")

    agree_to_final_contract = """
This is a summary of the contract, and what each player will do at the given tile:

{judges_contract}.

Do you agree to this? Respond only with yes or no.
"""
    
    history_R.append({"role": "user", "content":agree_to_final_contract.format(judges_contract=judge_contract_for_R)})
    history_B.append({"role": "user", "content":agree_to_final_contract.format(judges_contract=judge_contract_for_B)})

    B_response = chat_with_model(openai_client, "gpt-4.1", history_B)
    R_response = chat_with_model(openai_client, "gpt-4.1", history_R)
# %%
history_R
# %%
agree
# %%
judge_contract_for_B
# %%
B_response
# %%
import json
try:
    contract = json.loads(judge_contract)
    print(type(contract))  # <class 'dict'>
    print(contract["(1, 1)"]["color"])  # Red
except json.JSONDecodeError as e:
    print("⚠️ Failed to parse JSON:", e)
# %%
contract['(0, 2)']
# %%
print(judge_contract_for_R)
# %%
