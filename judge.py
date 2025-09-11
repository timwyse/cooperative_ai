import json

from openai import OpenAI

from constants import OPENAI_API_KEY


class Judge:
    def __init__(self, model="gpt-4o", temperature=1):
        self.model = model
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.temperature = temperature

    def format_conversation_for_contract(self, conversation, players, history_pov=0):

        conversation_formatted = conversation[1:]
        conversation_formatted = ", \n".join([f"{entry['role']}. {entry['content']} \n" for entry in conversation_formatted])

        if history_pov == 0:
            conversation_formatted = conversation_formatted.replace("user:", "player 0:").replace("assistant:", "player 1:")
        elif history_pov == 1:
            conversation_formatted = conversation_formatted.replace("user:", "player 1:").replace("assistant:", "player 0:")
        
        return conversation_formatted
        
    def create_contract(self, conversation_formatted):

        judge_system_prompt = "You are a judge whose goal is to summaries a contract created between two players. Your response must only include the contract, nothing else."
        
        judge_message = f"""
You are a judge in a Colored Trails negotiation.  
Two players (Player 0 and Player 1) have discussed a possible contract to trade resources. Here is there discussion: 

Discussion:
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

        judge_conversation = [
        {"role": "system", "content": judge_system_prompt},
            {"role": "user", "content": judge_message}
        ]

        contract = self.get_completion(judge_conversation)
        contract = contract.replace("```", "").replace("json", "")

        if contract.lower() == 'n':
            print("Judge determined that a contract was not established")
            return None
        

        try:
            contract = json.loads(contract)
            print(contract)
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
        if player.id == '0':
            return contract.lower().replace("player 0", "you").replace("player 1", "the other player")
        elif player.id == '1':
            return contract.lower().replace("player 1", "you").replace("player 0", "the other player")
    
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
        for tile, details in contract.items():
            formatted_contract[tile] = {
                "giver": details["giver"].lower().replace("player 0", giver_replace).replace("player 1", receiver_replace),
                "receiver": details["receiver"].lower().replace("player 0", giver_replace).replace("player 1", receiver_replace),
                "color": details["color"]  # Keep the color unchanged
            }

        return formatted_contract
       
JUDGE = Judge()