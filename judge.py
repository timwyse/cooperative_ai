import json

from openai import OpenAI

from constants import OPENAI_API_KEY, POINTS_FOR_WIN

JUDGE_SYSTEM_PROMPT = "You are a judge whose goal is to summaries a contract created between two players. Your response must only include the contract, nothing else."

class Judge:
    def __init__(self, model="gpt-4o", temperature=1):
        self.model = model
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.temperature = temperature

    def format_conversation_for_contract(self, conversation, players, history_pov=0):

        conversation_formatted = conversation[1:]
        conversation_formatted = ", \n".join([f"{entry['role']}: {entry['content']} \n" for entry in conversation_formatted])

        if history_pov == 0:
            conversation_formatted = conversation_formatted.replace("user:", "player 1:").replace("assistant:", "player 0:")
        elif history_pov == 1:
            conversation_formatted = conversation_formatted.replace("user:", "player 0:").replace("assistant:", "player 1:")
        
        return conversation_formatted
        
    def create_contract(self, conversation_formatted, type='strict'):

    

        if type == 'strict':
            contract_type_instructions = """Each entry should specify the tile coordinate, the giving player, the receiving player, and the resource color.  
Make sure to read the entire discussion, and determine for each player which tiles they are asking for resources for, and what the other player is asking for in return. If the players don't specify the color of a tile, you can leave it blank or put "unknown".

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
"giver": "Player 0",
"receiver": "Player 1",
"color": "Red"
}},
"(2, 2)": {{
"giver": "Player 0",
"receiver": "Player 1",
"color": "Blue"
}}
}}
"""
        elif type == 'contract_for_finishing':
            contract_type_instructions = """Each entry should should specify how many points each player will give the other player if they reach their goal. The maximum points a player can give the other player is {POINTS_FOR_WIN} points. If a player picks a value higher than this, reduce it to {POINTS_FOR_WIN}.
If a player is not giving any points to the other player, this should be specified as 0 points.

The JSON format must be:  
{{
"player_0_reaches_goal": {{
"giver": "Player 0",
"receiver": "Player 1",
"amount": "<Points>"
}},
"player_1_reaches_goal": {{
"giver": "Player 1",
"receiver": "Player 0",
"amount": "<Points>"
}}
}}

Example:
{{
"player_0_reaches_goal": {{
"giver": "Player 0",
"receiver": "Player 1",
"amount": "6"
}},
"player_1_reaches_goal": {{
"giver": "Player 1",
"receiver": "Player 0",
"amount": "0"
}}
}}

"""
        judge_message = f"""
You are a judge in a Colored Trails negotiation.  
Two players (Player 0 and Player 1) have discussed a possible contract to trade resources. Here is there discussion: 

Discussion:
"{conversation_formatted}"

Your task:
1. If no agreement has been reached, reply with exactly:
"N".  

2. Otherwise, read the discussion and output a summary of the contract as valid JSON only, with no extra explanation or text. {contract_type_instructions}
"""

        judge_conversation = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": judge_message}
        ]

        contract = self.get_completion(judge_conversation)
        contract = contract.replace("```", "").replace("json", "")

        if contract.lower() == 'n':
            print("Judge determined that a contract was not established")
            return None
        

        try:
            contract = json.loads(contract)
            return contract
        except json.JSONDecodeError as e:
            print("⚠️ Failed to parse JSON:", e)
            print(f"contrct put forward by judge: {contract}")

    def get_completion(self, messages, max_completion_tokens=1000):
        response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=messages,
                max_completion_tokens=max_completion_tokens)
        return response.choices[0].message.content.strip().lower()    
    
    def format_contract_for_player(self, contract, player):
        if not isinstance(contract, dict):
            raise ValueError("Contract must be a dictionary.")

        # Determine the replacements based on the player's ID
        if player.id == '0':
            giver_replace = "you"
            receiver_replace = "the other player"
        elif player.id == '1':
            giver_replace = "the other player"
            receiver_replace = "you"
        else:
            raise ValueError("Invalid player ID.")

        # Iterate over the dictionary and replace values
        formatted_contract = {}
        for base_key, nested_dic in contract.items():
            formatted_contract[base_key] = {
                "giver": nested_dic["giver"].lower().replace("player 0", giver_replace).replace("player_0", giver_replace).replace("player 1", receiver_replace).replace("player_1", receiver_replace),
                "receiver": nested_dic["receiver"].lower().replace("player 0", giver_replace).replace("player_0", giver_replace).replace("player 1", receiver_replace).replace("player_1", receiver_replace)
            }
                
            if "amount" in nested_dic:
                formatted_contract[base_key]["amount"] = min(int(nested_dic["amount"]), POINTS_FOR_WIN)  # Cap the amount at POINTS_FOR_WIN
            if "color" in nested_dic:
                formatted_contract[base_key]["color"] = nested_dic["color"]  # Keep the color unchanged
            

        return formatted_contract
    
    def check_if_move_is_in_contract(self, player, move, contract):
        message_for_judge = f"""
You are a judge in a Colored Trails game, a 2-D grid game where players spend resources to move onto tiles. 
The two players have negotiated an agreement that specifies which tiles one player will cover (pay for) on behalf of the other. 

Here is the negotiation:
{contract}

Task:
1. First, check whether the players clearly agreed on specific tiles that one will cover for the other. 
   - If there is no clear agreement, reply with "N" and nothing else. 

2. If there is a clear agreement, consider the following move:
   - Player: {player.name}
   - Tile: {move}

   Answer: 
   - If this tile is NOT in the contract, reply with "N".
   - If this tile is in the contract **but** {player.name} is the **giver** of a color for this tile, reply with "N".  
   - If this tile is in the contract **and** {player.name} is the **receiver** of a color for this tile, reply with "Y". 

IMPORTANT RULES:  
- You may reason internally about the move and the contract.  
- Your final output must be exactly one letter, either "Y" or "N". No other text.
"""
        response = self.get_completion(
                [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": message_for_judge}
                ],
                max_completion_tokens=10
            ).strip().upper()

        if response == 'Y':
            print(f"Judge determined that move {move} by {player.name} is covered by the contract.")
            return True
        elif response == 'N':
            print(f"Judge determined that move {move} by {player.name} is NOT covered by the contract.")
            return False
        else:
            print(f"⚠️ Judge returned unexpected response: {response}. Treating as 'N'.")
            return False
        
    
JUDGE = Judge()