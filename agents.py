from collections import namedtuple

### AGENTS - add more below as needed
## Pricing per million output tokens
# https://openai.com/api/pricing/
# https://api.together.ai/models
# https://docs.claude.com/en/docs/about-claude/pricing
Agent = namedtuple("Agent", ["name", "value", "api"])
HUMAN = Agent(name="human", value=None, api=None)
# NANO = Agent(name="4.1 nano", value="gpt-4.1-nano-2025-04-14", api='open_ai') # $0.40 
MINI = Agent(name="4.1 mini", value="gpt-4.1-mini", api='open_ai') # $1.60 
GPT_5 = Agent(name="GPT-5", value="gpt-5", api='open_ai') # $10 
FOUR_1 = Agent(name="GPT 4.1", value="gpt-4.1", api='open_ai') # $8 
FOUR_0 = Agent(name="GPT 4o", value="gpt-4o", api='open_ai') # $10 
DEEPSEEK_V3 = Agent(name="DeepSeek_R1", value="deepseek-ai/DeepSeek-V3", api='together') # $1.25
# QWEN_2_7B = Agent(name="QWEN_25_7B", value="Qwen/Qwen2.5-7B-Instruct-Turbo", api='together') # $0.30 
QWEN_480B = Agent(name="QWEN_480B", value="Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8", api='together') # $0.6
# LLAMA_3_3B = Agent(name="Llama_3_3B", value="meta-llama/Llama-3.2-3B-Instruct-Turbo", api='together')# $0.06
LLAMA_405B = Agent(name="Llama_405B", value="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo", api='together')# $3.5
SONNET_4 = Agent(name="Claude_Sonnet_4", value="claude-sonnet-4-20250514", api='anthropic') # $15 
HAIKU_3_5 = Agent(name="Claude_Haiku_3.5", value="claude-3-5-haiku-20241022", api='anthropic') # $4

