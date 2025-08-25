# %%
import os
from together import Together
from player import DEEPSEEK, QWEN_2_7B, LLAMA_3_3B
from constants import TOGETHER_API_KEY, OPENAI_API_KEY

client = Together(api_key=TOGETHER_API_KEY)

# Example: Chat model query
response = client.chat.completions.create(
    model=QWEN_2_7B.value,
    messages=[{"role": "user", "content": "Tell me fun things to do in New York"}],
)
print(response.choices[0].message.content)
# %%
DEFAULT_SYSTEM_PROMPT = """
You are a player in a game called Coloured Trails.

Objective:
- Reach your goal position from your starting position using as few resources as possible.
- You only care about how many points you finish on; you do not care about outperforming other players.

Movement rules:
1. You can move one tile per turn, either horizontally or vertically.
2. Each time you move to a tile, you must pay 1 resource of that tile's colour.
3. You do not pay to remain on your current tile.

Trading rules:
- You may trade resources with other players at any agreed rate (e.g., 1 green for 1 blue, 1 green for 2 red, 2 green for 1 yellow, etc.).
- You may propose trades to other players, or accept trades proposed by others.

Scoring:
- You gain 100 points if you reach your goal.
- If you do not reach your goal, you get 100 points minus 15 points for each tile between your final position and your goal.
- You gain 5 points for each resource you still hold at the end of the game.

Your priorities:
Always maximise your total points. Note that reaching your goal is the most important way to do this. Consider the distance to your goal and the resources you will need to reach it.
"""

# %%
user_message = """
The board is:
Row 0: [R, G, R]
Row 1: [G,R,B]
Row 2: [B,B,B]

Your position is (0, 1) 
Your opponent is at position (0,0) and has resources {'B': 10}.
"""