# ai_adapter.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from openai import OpenAI
from together import Together

from constants import ANTHROPIC_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY


class ModelAdapter:
    """
    adapter around OpenAI / Anthropic / Together to keep Player lean.
    - Builds the appropriate client
    - Exposes chat_completion (free text or OpenAI structured outputs)
    - Exposes anthropic_structured (Claude tool call returning parsed dict)
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

    # -------------------- Public API --------------------

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_completion_tokens: int = 1000,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generic model call.
        - For OpenAI, if response_format is provided (e.g., structured outputs), it will be used.
        - Anthropic/Together paths ignore response_format here (Anthropic structured is handled via anthropic_structured).
        """
        if self.model_api == "anthropic":
            # Free text for Anthropic (structured handled via anthropic_structured)
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
            kwargs = {
                "model": self.model_name,
                "temperature": self.temperature,
                "messages": messages,
                "max_completion_tokens": max_completion_tokens,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            resp = self.client.chat.completions.create(**kwargs)
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

    def anthropic_structured(
        self,
        messages: List[Dict[str, str]],
        tool_def: Dict[str, Any],
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Ask Claude to return a single tool call matching tool_def.input_schema.
        Returns the tool 'input' dict (already parsed).
        """
        system_text = "\n".join(m["content"] for m in messages if m["role"] == "system")
        msgs_wo_system = [m for m in messages if m["role"] != "system"]

        resp = self.client.messages.create(
            model=self.model_name,
            temperature=self.temperature,
            system=system_text or None,
            messages=msgs_wo_system,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_def["name"]},
            max_tokens=max_tokens,
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_def["name"]:
                return block.input
        raise RuntimeError("Claude did not return the expected tool call.")

    # -------------------- Optional helpers --------------------

    @staticmethod
    def last_json_object(text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse the last JSON object from free text."""
        import re
        matches = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
        if not matches:
            return None
        try:
            return json.loads(matches[-1])
        except Exception:
            return None
