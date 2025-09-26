
# %%


import pandas as pd
from itertools import islice


# Path to the JSONL file
jsonl_file = "board_finder/random_boards_and_properties_6_6.jsonl"
with open(jsonl_file, 'r') as f:
    df = pd.read_json(
        "".join(islice(f, 100)),  # take first 1000 lines
        lines=True
    )

# Expand the 'conditions' column into separate columns
conditions_df = pd.json_normalize(df['conditions'])

# Combine the original DataFrame with the expanded conditions DataFrame
df = pd.concat([df.drop(columns=['conditions']), conditions_df], axis=1)

# Display the formatted DataFrame
print(df.head())
# %%
df.columns
# %%
print(df.shape)
# %%
## doesn't doesn't
print(f"doesn't doesn't:{df[(df['B_10_path'] == True) & (df['R_10_path'] == True)].shape}")

# needs needs
print(f"needs needs: {df[
    (df['B_10_path'] == False) & (df['B_12_path'] == False) & (df['B_14_path'] == False) &
    (df['R_10_path'] == False) & (df['R_12_path'] == False) & (df['R_14_path'] == False)
].shape}")

# needs benefits
print(f" needs benefits: {df[
    (df['B_10_path'] == False) & (df['B_12_path'] == False) & (df['B_14_path'] == False) &
    (df['R_10_path'] == False) & ((df['R_12_path'] == True) | (df['R_14_path'] == True))
].shape}")

# needs doesn't
print(f" needs doesn't: {df[
    (df['B_10_path'] == False) & (df['B_12_path'] == False) & (df['B_14_path'] == False) &
    (df['R_10_path'] == True)
].shape}")

# benefits benefits
print(f"benefits benefits: {df[
    (df['B_10_path'] == False) & ((df['B_12_path'] == True) | (df['B_14_path'] == True)) &
    (df['R_10_path'] == False) & ((df['R_12_path'] == True) | (df['R_14_path'] == True))
].shape}")

# benefits doesn't
print(f"benefits doesn't: {df[
    (df['B_10_path'] == False) & ((df['B_12_path'] == True) | (df['B_14_path'] == True)) &
    (df['R_10_path'] == True)
].shape}")

# doesn't doesn't
print(f"doesn't doesn't: {df[
    (df['B_10_path'] == True) &
    (df['R_10_path'] == True)
].shape}")
# %%
# doesn't doesn't:(8055, 13)
# needs needs: (3509566, 13)
#  needs benefits: (5452, 13)
#  needs doesn't: (161890, 13)
# benefits benefits: (1, 13)
# benefits doesn't: (116, 13)
# doesn't doesn't: (8055, 13)
# %%

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'R', 'B', 'R', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'B', 'B', 'B', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'B', 'R'],
#  ['R', 'B', 'R', 'R', 'B', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]

# [['G', 'B', 'R', 'B', 'B', 'B'],
#  ['R', 'B', 'B', 'B', 'R', 'B'],
#  ['R', 'R', 'B', 'R', 'B', 'B'],
#  ['R', 'B', 'R', 'R', 'R', 'B'],
#  ['R', 'B', 'R', 'B', 'R', 'B'],
#  ['R', 'R', 'R', 'B', 'R', 'G']]
# %%
# needs benefits
df[
    (df['R_10_path'] == False) & (df['R_12_path'] == False) & (df['R_14_path'] == False) &
    (df['B_10_path'] == False) & ((df['B_12_path'] == True) | (df['B_14_path'] == True))
].iloc[:3]['grid'].to_clipboard()
# %%

# needs doesn't
df[
    (df['R_10_path'] == False) & (df['R_12_path'] == False) & (df['R_14_path'] == False) &
    (df['B_10_path'] == True)
].iloc[:3]['grid'].to_clipboard()
# %%
from anthropic import Anthropic
import os
key = os.getenv("ANTHROPIC_API_KEY")

client = Anthropic(api_key=key)  # or leave blank if using env var

# response = client.messages.create(
#     model="claude-3-5-sonnet-20240620",  # choose a Claude model
#     max_tokens=200,
#     messages=[
#         {"role": "user", "content": "Hello Claude, can you summarize how to use this API?"}
#     ]
# )

# print(response.content[0].text)
# %%
client.models.list(limit=20)



# %%
import re
import json

trade_proposal = """looking at my situation:\n- i'm at (0, 1) with resources: {'b': 13, 'g': 1, 'r': 0}\n- my best path requires: {'b': 3, 'r': 1, 'g': 1}\n- i'm missing: {'r': 1}\n\ni need 1 red chip to complete my optimal path. the other player has 13 red chips but needs blue chips (they have 0 blue). i have 13 blue chips, which is more than enough for my path (i only need 3).\n\nthis is a mutually beneficial trade - i can offer some of my excess blue chips for the 1 red chip i need.\n\n{\n  \"resources_to_offer\": [[\"b\", 2]],\n  \"resources_to_receive\": [[\"r\", 1]]\n}
"""

match = re.search(r"\{.*\}", trade_proposal, re.DOTALL)
if match:
    json_str = match.group(-1)
    try:
        trade_proposal = json.loads(json_str)

        # Fix common key errors
        if 'resources_to offer' in trade_proposal:
            trade_proposal['resources_to_offer'] = trade_proposal.pop('resources_to offer')
        if 'resources to offer' in trade_proposal:
            trade_proposal['resources_to_offer'] = trade_proposal.pop('resources to offer')
        if 'resources_to receive' in trade_proposal:
            trade_proposal['resources_to_receive'] = trade_proposal.pop('resources_to receive')
        if 'resources to receive' in trade_proposal:
            trade_proposal['resources_to_receive'] = trade_proposal.pop('resources to receive')
        
        # cleaned = self.clean_trade_proposal(trade_proposal, grid, game)
        # if cleaned:
        #     trade_proposal = cleaned
        #     if self.pay4partner:
        #         print(f"- Offering to cover: {trade_proposal['resources_to_offer']}")
        #         print(f"- Requesting to be covered for: {trade_proposal['resources_to_receive']}")
        #     else:
        #         print(f"- Offering: {trade_proposal['resources_to_offer']}")
        #         print(f"- Requesting: {trade_proposal['resources_to_receive']}")
        # else:
        #     print("- Invalid trade proposal")
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format in trade proposal: {e}"
        print(error_msg)
        
# %%

# %%
matches = re.findall(r'\{.*?\}', trade_proposal, re.DOTALL)


# %%
matches[-1]

# %%
trade_proposal_2 = """looking at my situation:\n- i'm at (0, 1) with resources: {'b': 13, 'g': 1, 'r': 0}\n- my best path requires: {'b': 3, 'r': 1, 'g': 1}\n- i'm missing: {'r': 1}\n\ni need 1 red chip to complete my optimal path. the other player has 13 red chips but needs blue chips (they have 0 blue). i have 13 blue chips, which is more than enough for my path (i only need 3).\n\nthis is a mutually beneficial trade - i can offer some of my excess blue chips for the 1 red chip i need.\n\n{\n  \"resources_to_offer\": [[\"b\", 2]],\n  \"resources_to_receive\": [[\"r\", 1]]\n}"""


matches = re.findall(r'\{.*\}', trade_proposal_2, re.DOTALL)
# %%
matches[-1]
# %%

def test_fn():
    x= {'a':1}
        
    inner(x)
    return x

def inner(x):
        x['a'] += 2
    
test_fn()
# %%
