# ai_adapter.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic
from openai import OpenAI
from together import Together

from constants import ANTHROPIC_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY


class ModelAdapter:
    """
    One class for OpenAI / Anthropic / Together:
      - chat_completion(): free-text chat
      - structured(): provider-agnostic structured output

    Usage:
      # free text
      text = adapter.chat_completion(messages, max_completion_tokens=1000)

      # structured
      #  OpenAI/Together: pass a JSON Schema *payload* (the actual "schema" dict)
      #  Anthropic: pass a *tool definition* (with tool name + input_schema)
      parsed, raw = adapter.structured(messages, schema_or_tool, max_tokens=1000)
    """

    def __init__(self, model_api: str, model_name: str, temperature: float):
        self.model_api = model_api
        self.model_name = model_name
        self.temperature = temperature

        if model_api == "open_ai":
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        elif model_api == "together":
            self.client = Together(api_key=TOGETHER_API_KEY)
        elif model_api == "anthropic":
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unknown model_api: {model_api}")

    # -------------------- Free-text --------------------
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_completion_tokens: int = 1000,
    ) -> str:
        if self.model_api == "anthropic":
            system_prompt = "\n".join(m["content"] for m in messages if m["role"] == "system")
            msg_wo_sys = [m for m in messages if m["role"] != "system"]
            resp = self.client.messages.create(
                model=self.model_name,
                temperature=self.temperature,
                system=(system_prompt or None),
                messages=msg_wo_sys,
                max_tokens=max_completion_tokens,
            )
            texts = []
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    texts.append(block.text)
            return "\n".join(t.strip() for t in texts if t).strip()

        if self.model_api == "open_ai":
            resp = self.client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                messages=messages,
                max_completion_tokens=max_completion_tokens,
            )
            content = resp.choices[0].message.content
            return content.strip() if isinstance(content, str) else content

        # Together
        resp = self.client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            max_tokens=max_completion_tokens,
        )
        return resp.choices[0].message.content.strip()

    # -------------------- Structured --------------------
    def structured(
        self,
        messages: List[Dict[str, str]],
        schema_or_tool: Dict[str, Any],
        max_tokens: int = 1000,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Provider-agnostic structured call:

        - Anthropic: pass a *tool def* like ANTHROPIC_*_TOOL (with 'name' and 'input_schema').
                     Returns (parsed_dict, raw_json_str).
        - OpenAI/Together: pass the *JSON Schema payload* (the actual schema dict).
                           Returns (parsed_dict, raw_json_str_of_response).
        """
        if self.model_api == "anthropic":
            # Treat schema_or_tool as a Claude tool definition
            system_text = "\n".join(m["content"] for m in messages if m["role"] == "system")
            msgs_wo_system = [m for m in messages if m["role"] != "system"]

            resp = self.client.messages.create(
                model=self.model_name,
                temperature=self.temperature,
                system=system_text or None,
                messages=msgs_wo_system,
                tools=[schema_or_tool],
                tool_choice={"type": "tool", "name": schema_or_tool["name"]},
                max_tokens=max_tokens,
            )
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == schema_or_tool["name"]:
                    parsed = block.input
                    raw_text = json.dumps(parsed)
                    return parsed, raw_text
            raise RuntimeError("Claude did not return the expected tool call.")

        # OpenAI / Together: treat schema_or_tool as JSON Schema payload
        # For OpenAI, we need to include the name field in the json_schema
        if "name" in schema_or_tool and "schema" in schema_or_tool:
            # Full schema object with name and schema - extract name and schema
            json_schema = {
                "name": schema_or_tool["name"],
                "schema": schema_or_tool["schema"]
            }
        else:
            # Just the schema part
            json_schema = schema_or_tool
        
        response_format = {"type": "json_schema", "json_schema": json_schema}

        if self.model_api == "open_ai":
            resp = self.client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                messages=messages,
                max_completion_tokens=max_tokens,
                response_format=response_format,
            )
            raw = resp.choices[0].message.content
            parsed = json.loads(raw)
            return parsed, raw

        # Together
        resp = self.client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        raw = resp.choices[0].message.content
        parsed = json.loads(raw)
        return parsed, raw

    # -------- Utility --------
    @staticmethod
    def last_json_object(text: str) -> Optional[Dict[str, Any]]:
        import re
        matches = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
        if not matches:
            return None
        try:
            return json.loads(matches[-1])
        except Exception:
            return None
