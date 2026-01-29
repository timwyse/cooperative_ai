# %%
import openai

def get_gpt_response(system_prompt, user_prompt, model="gpt-4.1"):
    client = openai.OpenAI()  # Assumes your API key is set in the environment
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=256
    )
    return response.choices[0].message.content


# %%
system_prompt = """\nYou are a player in a game called Modified Coloured Trails.\n\nObjective:\n- Reach your goal position from your starting position.\n- To have as many chips as possible at the end of the game. \n\nMovement rules:\n1. You can move one tile per turn, either horizontally or vertically.\n2. Each time you move to a tile, you must pay 1 chip of that tile's colour.\n3. You do not pay to remain on your current tile.\n\nTrading rules:\n\n- You are in 'regular' mode: You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for nothing, etc.).\n \n- You may propose trades to other players, or accept / reject trades proposed by others.\n- You may chat with the opponent at any moment.\n\nCRITICAL SCORING RULES - READ CAREFULLY:\n- If you do NOT reach your goal position, you LOSE EVERYTHING and get 0 points total.\n- If you do NOT reach your goal position, ALL your remaining chips are WORTHLESS.\n- If you DO reach your goal, you get 20 points PLUS 5 points for each remaining chip (regardless of color). \n\n- REACHING YOUR GOAL IS MANDATORY - there is no partial credit for getting close.\n\nNote: You have to reach your goal point, this is your ultimate goal. The secondary goal is to have as many chips as you can. You should not care about other players' performance. \n\nCoordinates: (ROW, COLUMN)\n\n"""
user =  """\n\n=== GAME STATUS FOR YOU - TURN 6 ===\n\n- You are at position (2, 3)\n- Your goal is at (3, 3). \n- Your resources: {'B': 0, 'G': 1, 'R': 7}\n\n\n\n- Considering potential paths to your goal: shorter paths require less resources, but a longer path for which you don't need to trade is also a strong option (as a backup plan or negotiation tool, but it means you finish with less resources than if you take the shorter path). A short path that you don't need to trade for is ideal, and your negotiation strategy should reflect this.\n\n- The other player's goal is also (3, 3). Note that because the other player likely has different resources to you, their best path to the goal may be different to yours.\n- The other player's resources: {'B': 4, 'G': 1, 'R': 0}\n- The other player is at position (3, 1)\n\nBOARD LAYOUT: \nRow 0: G B R R\nRow 1: B R B R\nRow 2: B R R B\nRow 3: B B R G\n\nHISTORY OF EVENTS:\n\nRecent turn history:\n\n=== TURN 1 ===\nMOVE: You moved from (0, 1) to (0, 2)\nMOVE: The other player moved from (1, 0) to (2, 0)\n\nPOSITIONS:\n- You: at (0, 2), resources: {'B': 0, 'G': 1, 'R': 9}\n- The other player: at (2, 0), resources: {'B': 7, 'G': 1, 'R': 0}\n---\n\n=== TURN 2 ===\nMOVE: You moved from (0, 2) to (0, 3)\nMOVE: The other player moved from (2, 0) to (3, 0)\n\nPOSITIONS:\n- You: at (0, 3), resources: {'B': 0, 'G': 1, 'R': 8}\n- The other player: at (3, 0), resources: {'B': 6, 'G': 1, 'R': 0}\n---\n\n=== TURN 3 ===\nMOVE: You moved from (0, 3) to (1, 3)\nMOVE: The other player moved from (3, 0) to (3, 1)\n\nPOSITIONS:\n- You: at (1, 3), resources: {'B': 0, 'G': 1, 'R': 7}\n- The other player: at (3, 1), resources: {'B': 5, 'G': 1, 'R': 0}\n---\n\n=== TURN 4 ===\nMOVE: You did not move\n\nPOSITIONS:\n- You: at (1, 3), resources: {'B': 0, 'G': 1, 'R': 7}\n- The other player: at (3, 1), resources: {'B': 5, 'G': 1, 'R': 0}\n---\n\n=== TURN 5 ===\nMOVE: You moved from (1, 3) to (2, 3)\nMOVE: The other player did not move\n\nPOSITIONS:\n- You: at (2, 3), resources: {'B': 0, 'G': 1, 'R': 7}\n- The other player: at (3, 1), resources: {'B': 4, 'G': 1, 'R': 0}\n\n\n\nAdditionally, you have agreed upon the following contract with the other player. When you try to move onto one of the tiles for which they have agreed to pay on your behalf, the resource will leave their resources and you will be able to move onto that tile:\n{'(0, 1)': {'giver': 'the other player', 'receiver': 'you', 'color': 'B'}, '(2, 3)': {'giver': 'the other player', 'receiver': 'you', 'color': 'B'}, '(0, 2)': {'giver': 'you', 'receiver': 'the other player', 'color': 'R'}, '(0, 3)': {'giver': 'you', 'receiver': 'the other player', 'color': 'R'}, '(1, 3)': {'giver': 'you', 'receiver': 'the other player', 'color': 'R'}}\n\nThus if you move onto one of these tiles, you do not need to have the resource in your inventory to move onto that tile, nor do you need to trade for it. The same is true for the other player.\n\n\nYou have been offered a trade:\nThe other player wants to give you [('B', 3)] in exchange for [('R', 1)].\n\nThink step by step about whether to accept this trade. Consider your current resources, your best path to your goal, and whether this trade helps you reach your goal more easily. Also consider whether the trade results in having more resources left over after reaching your goal, and hence a higher score.\n\nOnce you have decided, use this EXACT JSON format:\n\n{\n  \"rationale\": \"Your thinking process and reasoning for accepting or rejecting this trade\",\n  \"answer\": \"yes\" or \"no\"\n}\n\nExample of accepting a trade:\n{\n  \"rationale\": \"This trade gives me 2 blue resources which I need for my optimal path, and I can afford to give up 3 red resources since I have excess. This will help me reach my goal faster.\",\n  \"answer\": \"yes\"\n}\n\nExample of rejecting a trade:\n{\n  \"rationale\": \"This trade doesn't help me reach my goal efficiently. I would lose resources I need for my path and gain resources I don't need. I can reach my goal without this trade.\",\n  \"answer\": \"no\"\n}\n\nKeep your response below 500 tokens.\n"""


print(get_gpt_response(system_prompt, user))

# %%
### note how model can't recognise that this is a beneficial trade (The other player wants to give you [('B', 3)] in exchange for [('R', 1)].), it usually rejects it.


## independent: 0-19
## MD: 20-29, 40-49, 90-99
## Needy Player (Blue): 120-139

import anthropic

import anthropic

def get_claude_response(system_prompt, user_prompt, model="claude-2"):
    """
    Query an Anthropic Claude model using the Messages API.

    Args:
        system_prompt (str): The system prompt to set the context.
        user_prompt (str): The user input to query the model.
        model (str): The Claude model to use (e.g., "claude-2").

    Returns:
        str: The model's response.
    """
    client = anthropic.Client()  # Assumes your API key is set in the environment
    response = client.chat.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens_to_sample=500
    )
    return response["completion"]

# Example usage:
system_prompt = "You are a helpful assistant."
user_prompt = "What is the capital of France?"
print(get_claude_response(system_prompt, user_prompt))
# %%

model = "qwen/qwen3-235b-a22b-2507"
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://yourapp.example",
        "X-Title": "Your App Name",
    },
)

resp = client.chat.completions.create(
    model="qwen/qwen3-235b-a22b-2507",
    messages=[{"role": "user", "content": "Hello!"}],
    extra_body={
        "provider": {"order": ["together"], "allow_fallbacks": False}
    },
)

print(resp.choices[0].message.content)
# %%
import requests
import json
api_key=os.environ["OPENROUTER_API_KEY"],
response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
  },
  data=json.dumps({
    "model": "qwen/qwen3-235b-a22b-2507",
    "messages": [
      {
        "role": "user",
        "content": "What is the meaning of life?"
      }
    ]
  })
)
# %%
response.json()
# %%
api_key
# %%


model = "meta-llama/llama-3.1-405b-instruct"
from openai import OpenAI
from os import getenv

# gets API Key from environment variable OPENAI_API_KEY
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=getenv("OPENROUTER_API_KEY"),
)

resp = client.chat.completions.create(
  model=model,
  temperature=0.7,
  max_completion_tokens=256,
  messages=[
    {
      "role": "user",
      "content": "Say this is a test",
    },
  ],
)


content = resp.choices[0].message.content
print(content)
# %%

from openai import OpenAI

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=getenv("OPENROUTER_API_KEY"),
)

completion = client.chat.completions.create(
  
  model="meta-llama/llama-3.1-70b-instruct",
  messages=[
    {
      "role": "user",
      "content": "What is the meaning of life?"
    }
  ]
)
print(completion.choices[0].message.content)
# %%


import json
from pathlib import Path
from typing import Iterable

def trade_no_contract_mentions(log: dict) -> list[dict]:
    results: list[dict] = []

    game = log.get("game", {})
    turns = game.get("turns", {})

    keywords = [
        "contract",
        "agreement",
        "agreed",
        "judge",
        "tile_with_judge",
        "already agreed",
        "guarantees",
    ]

    for turn_str, turn_data in turns.items():
        try:
            turn_idx = int(turn_str)
        except (TypeError, ValueError):
            continue

        actions = turn_data.get("actions", []) or []
        for action in actions:
            if action.get("action_type") != "TRADE_PROPOSAL":
                continue

            parsed = (action.get("agent_response") or {}).get("parsed") or {}
            want_to_trade = parsed.get("want_to_trade", None)
            if want_to_trade is not False:
                continue

            rationale = parsed.get("rationale", "") or ""
            r_low = rationale.lower()
            mentions_contract = any(kw in r_low for kw in keywords)

            results.append(
                {
                    "turn": turn_idx,
                    "player": action.get("player"),
                    "want_to_trade": want_to_trade,
                    "rationale": rationale,
                    "mentions_contract": mentions_contract,
                }
            )

    return results


def iter_target_logs(root: Path) -> Iterable[Path]:
    target_contract_dirs = {
        "ctx1_fog00_p4pfalse_contract_tile_with_judge_implementation_selfish11",
        "ctx1_fog00_p4pfalse_contract_strict_selfish11",
    }

    for path in root.rglob("verbose*.json"):
        if not path.name.startswith("verbose"):
            continue

        parts = path.parts
        if "Mutual_Dependency" not in parts:
            continue

        contract_dir = None
        for p in parts:
            if p in target_contract_dirs:
                contract_dir = p
                break
        if contract_dir is None:
            continue

        yield path, contract_dir


def analyze_logs_for_no_trade_contract_reason(root: Path) -> None:
    # overall totals
    total_no_trade = 0
    total_with_contract_mention = 0

    # per-contract-dir totals
    per_contract = {}

    for path, contract_dir in iter_target_logs(root):
        with path.open("r", encoding="utf-8") as f:
            log = json.load(f)

        records = trade_no_contract_mentions(log)
        if not records:
            continue

        file_no_trade = len(records)
        file_with_contract = sum(r["mentions_contract"] for r in records)

        total_no_trade += file_no_trade
        total_with_contract_mention += file_with_contract

        # init per-contract bucket
        if contract_dir not in per_contract:
            per_contract[contract_dir] = {
                "no_trade": 0,
                "with_contract": 0,
                "files": 0,
            }
        per_contract[contract_dir]["no_trade"] += file_no_trade
        per_contract[contract_dir]["with_contract"] += file_with_contract
        per_contract[contract_dir]["files"] += 1

        print(f"\nFile: {path.relative_to(root)}")
        print(f"  contract_dir: {contract_dir}")
        print(f"  no-trade TRADE_PROPOSAL actions: {file_no_trade}")
        print(f"  of which mention contract:       {file_with_contract}")
        for r in records:
            mark = "YES" if r["mentions_contract"] else "NO "
            print(f"    [turn {r['turn']}, {r['player']}] contract_mention={mark}")
            print(f"      {r['rationale'][:200].replace('\\n',' ')}"
                  f"{'...' if len(r['rationale'])>200 else ''}")

    print("\n=== Overall summary ===")
    print(f"Total no-trade TRADE_PROPOSAL actions: {total_no_trade}")
    print(f"Total mentioning contract:            {total_with_contract_mention}")

    print("\n=== Per-contract summary ===")
    for contract_dir, stats in per_contract.items():
        n_no = stats["no_trade"]
        n_yes = stats["with_contract"]
        frac = n_yes / n_no if n_no else 0.0
        print(f"\nContract dir: {contract_dir}")
        print(f"  files with at least one no-trade: {stats['files']}")
        print(f"  no-trade actions:                 {n_no}")
        print(f"  mentioning contract:              {n_yes} ({frac:.2%})")


# Example usage from a notebook:
from pathlib import Path
root = Path("/Users/timwyse/cooperative_ai/public_logs/reduced_config_selfish_runs")
analyze_logs_for_no_trade_contract_reason(root)

# %%
