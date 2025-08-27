from collections import namedtuple

### AGENTS - add more below as needed
# https://openai.com/api/pricing/
# https://api.together.ai/models
Agent = namedtuple("Agent", ["name", "value", "api"])
HUMAN = Agent(name="human", value=None, api=None)
NANO = Agent(name="4.1 nano", value="gpt-4.1-nano-2025-04-14", api='open_ai') # $0.40 per million output tokens
MINI = Agent(name="4.1 mini", value="gpt-4.1-mini", api='open_ai') # $1.60 per million output tokens
FOUR_1 = Agent(name="4.1", value="gpt-4.1", api='open_ai') # $8 per million output tokens
FOUR_0 = Agent(name="4o", value="gpt-4o", api='open_ai') # $10 per million output tokens
DEEPSEEK = Agent(name="DeepSeek_R1", value="deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free", api='together') # free, but slow/ limited
QWEN_2_7B = Agent(name="QWEN_25_7B", value="Qwen/Qwen2.5-7B-Instruct-Turbo", api='together') # $0.30 per million output tokens
LLAMA_3_3B = Agent(name="Llama_3_3B", value="meta-llama/Llama-3.2-3B-Instruct-Turbo", api='together')# $0.06 per output million tokens
