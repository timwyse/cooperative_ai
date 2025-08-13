# %%
import os
from together import Together
from constants import DEEPSEEK, QWEN_2_7B, LLAMA_3_3B

client = Together(api_key=os.environ.get("TOGETHER_API_KEY"))

# Example: Chat model query
response = client.chat.completions.create(
    model=QWEN_2_7B.value,
    messages=[{"role": "user", "content": "Tell me fun things to do in New York"}],
)
print(response.choices[0].message.content)
# %%

# %%
