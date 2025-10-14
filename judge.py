import json

from anthropic import Anthropic
from openai import OpenAI

from agents import SONNET_4, FOUR_0
from constants import ANTHROPIC_API_KEY, OPENAI_API_KEY, POINTS_FOR_WIN
from model_adapter import ModelAdapter
from schemas import (STRICT_JUDGE_SCHEMA, ANTHROPIC_STRICT_JUDGE_TOOL, 
                     FINISHING_JUDGE_SCHEMA, ANTHROPIC_FINISHING_JUDGE_TOOL)
from utils import get_last_alphabetic_word

JUDGE_SYSTEM_PROMPT = "You are a judge whose goal is to summaries a contract created between two players. Your response must only include the contract, nothing else."

class Judge:
    def __init__(self, model=FOUR_0, temperature=1):
        self.model = model.value
        self.model_api = model.api
        if self.model_api == 'open_ai':
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        elif self.model_api == 'anthropic':
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.temperature = temperature
        self.api_llm_model = ModelAdapter(self.model_api, self.model, self.temperature)
        self.n_api_calls = 0

    def get_completion(self, messages, max_completion_tokens=1000):
        self.n_api_calls += 1
        if self.model_api == 'anthropic':
            try:
                system_prompt = ""
                for message in messages:
                    if message['role'] == 'system':
                        system_prompt += message['content'] + "\n"
                # Remove system messages from the list
                messages = [m for m in messages if m['role'] != 'system']   

                response = self.client.messages.create(model=self.model,
                                                    temperature=self.temperature,
                                                    messages=messages,
                                                    system=system_prompt,
                                                    max_tokens=max_completion_tokens)
                return response.content[0].text.strip().lower()
            except Exception as e:
                print(f"Error with Anthropic API: {e}")
                print(messages)
                raise e
        
        else:   
            response = self.client.chat.completions.create(model=self.model,
                                                           temperature=self.temperature,
                                                           messages=messages,
                                                           max_completion_tokens=max_completion_tokens)
            return response.choices[0].message.content.strip().lower()

    def _structured(self, messages, schema_or_tool, max_tokens=1000):
        """Wrapper for adapter.structured that increments n_api_calls."""
        self.n_api_calls += 1
        return self.api_llm_model.structured(messages, schema_or_tool=schema_or_tool, max_tokens=max_tokens)
    
    def format_conversation_for_contract(self, conversation, players, history_pov=0):

        conversation_formatted = conversation[1:]
        conversation_formatted = ", \n".join([f"{entry['role']}: {entry['content']} \n" for entry in conversation_formatted])

        if history_pov == 0:
            conversation_formatted = conversation_formatted.replace("user:", "player 1:").replace("assistant:", "player 0:")
        elif history_pov == 1:
            conversation_formatted = conversation_formatted.replace("user:", "player 0:").replace("assistant:", "player 1:")
        
        return conversation_formatted
        
    def create_contract(self, conversation_formatted, contract_type='strict'):

    
        if contract_type == 'strict':
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
        elif contract_type == 'contract_for_finishing':
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
        
        if contract_type == 'strict':
            schema_or_tool = ANTHROPIC_STRICT_JUDGE_TOOL if self.model_api == "anthropic" else STRICT_JUDGE_SCHEMA
        elif contract_type == 'contract_for_finishing':
            schema_or_tool = ANTHROPIC_FINISHING_JUDGE_TOOL if self.model_api == "anthropic" else FINISHING_JUDGE_SCHEMA
        
        contract_parsed, contract_raw = self._structured(judge_conversation, schema_or_tool=schema_or_tool, max_tokens=1000)
        
        # if contract.lower() == 'n':
        #     print("Judge determined that a contract was not established")
        #     return None
        
        if type(contract_parsed) == dict:
            return contract_parsed
            
        else:
            print("⚠️ Contract of wrong type:")
            print(f"contract put forward by judge: {contract_parsed}")
            if hasattr(self, 'logger'):
                self.logger.log_format_error(
                    "Judge",
                    "contract_json_parse_error",
                    {"error": 'structured_output_error', "raw_response": contract_parsed}
                )

    
    
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
                max_completion_tokens=1000
            ).strip().upper()
        response = get_last_alphabetic_word(response)  # Extract the last alphabetic word
        if response.lower() == 'y':
            print(f"Judge determined that move {move} by {player.name} is covered by the contract.")
            return True
        elif response.lower() == 'n':
            print(f"Judge determined that move {move} by {player.name} is NOT covered by the contract.")
            return False
        else:
            print(f"⚠️ Judge returned unexpected response: {response}. Treating as 'N'.")

            if hasattr(self, 'logger'):
                self.logger.log_format_error(
                    player.name,
                    "judge_move_cover_check_invalid_format",
                    {"raw_response": response, "move": move, "player": player.name}
                )

            return False
        
    
JUDGE = Judge(model=SONNET_4)