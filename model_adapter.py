# model_adapter.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic
from openai import OpenAI
from together import Together

from constants import ANTHROPIC_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY

MAX_RETRIES = 3


class ModelAdapter:
    """
    Unified adapter for OpenAI, Anthropic, and Together APIs.
    
    Provides two main methods:
      - chat_completion(): free-text chat responses
      - structured(): JSON structured output with retries
    """

    def __init__(self, model_api: str, model_name: str, temperature: float):
        self.model_api = model_api
        self.model_name = model_name
        self.temperature = temperature
        self.client = self._create_client(model_api)

    @staticmethod
    def _create_client(model_api: str):
        clients = {
            "open_ai": lambda: OpenAI(api_key=OPENAI_API_KEY),
            "together": lambda: Together(api_key=TOGETHER_API_KEY),
            "anthropic": lambda: Anthropic(api_key=ANTHROPIC_API_KEY),
        }
        if model_api not in clients:
            raise ValueError(f"Unknown model_api: {model_api}")
        return clients[model_api]()

    @property
    def _is_anthropic(self) -> bool:
        return self.model_api == "anthropic"

    def _prepare_anthropic_messages(
        self, messages: List[Dict[str, str]]
    ) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """Extract system prompt and filter out system messages for Anthropic API."""
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        system_prompt = "\n".join(system_parts) if system_parts else None
        user_messages = [m for m in messages if m["role"] != "system"]
        return system_prompt, user_messages

    # Free-text chat completion
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_completion_tokens: int = 1000,
    ) -> str:
        """Generate a free-text response from the model."""
        if self._is_anthropic:
            return self._chat_anthropic(messages, max_completion_tokens)
        return self._chat_openai_compatible(messages, max_completion_tokens)

    def _chat_anthropic(
        self, messages: List[Dict[str, str]], max_tokens: int
    ) -> str:
        """Anthropic chat completion."""
        system_prompt, user_messages = self._prepare_anthropic_messages(messages)
        resp = self.client.messages.create(
            model=self.model_name,
            temperature=self.temperature,
            system=system_prompt,
            messages=user_messages,
            max_tokens=max_tokens,
        )
        texts = [
            block.text
            for block in resp.content
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(t.strip() for t in texts if t).strip()

    def _chat_openai_compatible(
        self, messages: List[Dict[str, str]], max_tokens: int
    ) -> str:
        """OpenAI and Together chat completion (compatible APIs)."""
        # Together uses 'max_tokens', OpenAI uses 'max_completion_tokens'
        token_param = "max_completion_tokens" if self.model_api == "open_ai" else "max_tokens"
        
        resp = self.client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            **{token_param: max_tokens},
        )
        content = resp.choices[0].message.content
        return content.strip() if isinstance(content, str) else content

    # -------------------------------------------------------------------------
    # Structured output (JSON schema / tool use)
    # -------------------------------------------------------------------------

    def structured(
        self,
        messages: List[Dict[str, str]],
        schema_or_tool: Dict[str, Any],
        max_tokens: int = 1000,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Get structured JSON output with automatic retries.
        
        Args:
            messages: Chat messages
            schema_or_tool: For Anthropic, a tool definition (with 'name' and 'input_schema').
                           For OpenAI/Together, a JSON Schema payload.
            max_tokens: Maximum tokens for response
            
        Returns:
            Tuple of (parsed_dict, raw_json_string)
        """
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    print(f"Retrying structured call (attempt {attempt + 1}/{MAX_RETRIES})...")
                return self._make_structured_call(messages, schema_or_tool, max_tokens)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    print(f"Attempt {attempt + 1} failed: {e}")
        
        raise RuntimeError(f"Structured call failed after {MAX_RETRIES} attempts: {last_error}")

    def _make_structured_call(
        self,
        messages: List[Dict[str, str]],
        schema_or_tool: Dict[str, Any],
        max_tokens: int,
    ) -> Tuple[Dict[str, Any], str]:
        """Single structured API call. Returns (parsed_dict, raw_json_string)."""
        if self._is_anthropic:
            return self._structured_anthropic(messages, schema_or_tool, max_tokens)
        return self._structured_openai_compatible(messages, schema_or_tool, max_tokens)

    def _structured_anthropic(
        self,
        messages: List[Dict[str, str]],
        tool: Dict[str, Any],
        max_tokens: int,
    ) -> Tuple[Dict[str, Any], str]:
        """Anthropic structured output via tool use."""
        system_prompt, user_messages = self._prepare_anthropic_messages(messages)
        
        resp = self.client.messages.create(
            model=self.model_name,
            temperature=self.temperature,
            system=system_prompt,
            messages=user_messages,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            max_tokens=max_tokens,
        )
        
        # Extract the tool response
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool["name"]:
                parsed = block.input
                return parsed, json.dumps(parsed)
        
        raise RuntimeError("Claude did not return the expected tool call.")

    def _structured_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        max_tokens: int,
    ) -> Tuple[Dict[str, Any], str]:
        """OpenAI and Together structured output via json_schema response format."""
        if "name" in schema and "schema" in schema:
            json_schema = {"name": schema["name"], "schema": schema["schema"]}
        else:
            json_schema = schema
        response_format = {"type": "json_schema", "json_schema": json_schema}
        
        # Together uses 'max_tokens', OpenAI uses 'max_completion_tokens'
        token_param = "max_completion_tokens" if self.model_api == "open_ai" else "max_tokens"
        
        resp = self.client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            response_format=response_format,
            **{token_param: max_tokens},
        )
        
        raw = resp.choices[0].message.content
        return json.loads(raw), raw

    @staticmethod
    def last_json_object(text: str) -> Optional[Dict[str, Any]]:
        matches = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
        if not matches:
            return None
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError:
            return None
