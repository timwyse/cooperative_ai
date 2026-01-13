# ai_adapter.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic
from openai import OpenAI
from together import Together

from constants import ANTHROPIC_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY, OPENROUTER_API_KEY


class ModelAdapter:
    """
    One class for OpenAI / Anthropic / Together:
      - chat_completion(): free-text chat
      - structured(): provider-agnostic structured output

    Usage:
      # free text
      text = adapter.chat_completion(messages, max_completion_tokens=1000)

      # structured
      #  OpenAI/Together/OpenRouter: pass a JSON Schema *payload* (the actual "schema" dict)
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
        elif model_api == "openrouter":
            self.client = OpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )
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

        if self.model_api in ("open_ai", "openrouter"):
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
    def _validate_json_against_schema(self, parsed: Dict[str, Any], schema_or_tool: Dict[str, Any]) -> None:
        """Validate parsed JSON against the provided schema."""
        if "schema" not in schema_or_tool:
            return

        schema = schema_or_tool["schema"]
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        # Check required fields
        for field in required:
            if field not in parsed:
                raise ValueError(f"Missing required field: {field}")
            
        # Check enum values if any
        for field, spec in properties.items():
            if field in parsed and "enum" in spec:
                if parsed[field] not in spec["enum"]:
                    raise ValueError(f"Invalid value for {field}: {parsed[field]}")

    def _extract_json_from_text(self, raw: str) -> Tuple[Dict[str, Any], str]:
        """Extract and parse JSON from text that might contain other content."""
        import re
        json_matches = re.findall(r'\{[^{}]*\}', raw)
        if not json_matches:
            raise ValueError("No JSON-like content found in response")
        
        # Try each match
        for potential_json in json_matches:
            try:
                # Clean up the JSON string
                potential_json = potential_json.replace("'", '"')  # Replace single quotes
                potential_json = re.sub(r'(?<!\\)\\n', r'\\n', potential_json)  # Escape newlines
                
                parsed = json.loads(potential_json)
                return parsed, potential_json
            except json.JSONDecodeError:
                continue
        
        raise ValueError("Could not parse any JSON from matches")

    def _make_api_call_with_retries(
        self,
        messages: List[Dict[str, str]],
        schema_or_tool: Dict[str, Any],
        max_tokens: int,
        response_format: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
        """Make API call with retries and JSON validation."""
        max_retries = 3
        last_error = None
        last_raw = None

        for attempt in range(max_retries):
            try:
                # Make API call
                if attempt > 0:
                    print(f"Retrying API call (attempt {attempt + 1}/{max_retries})...")
                
                # Handle different APIs
                if self.model_api in ("open_ai", "openrouter"):
                    resp = self.client.chat.completions.create(
                        model=self.model_name,
                        temperature=self.temperature,
                        messages=messages,
                        max_completion_tokens=max_tokens,
                        response_format=response_format,
                    )
                else:  # Together
                    resp = self.client.chat.completions.create(
                        model=self.model_name,
                        temperature=self.temperature,
                        messages=messages,
                        max_tokens=max_tokens,
                        response_format=response_format,
                    )
                
                raw = resp.choices[0].message.content
                last_raw = raw  # Save for error reporting

                try:
                    # First try direct JSON parsing
                    parsed = json.loads(raw)
                    self._validate_json_against_schema(parsed, schema_or_tool)
                    return parsed, raw
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON
                    parsed, potential_json = self._extract_json_from_text(raw)
                    self._validate_json_against_schema(parsed, schema_or_tool)
                    return parsed, potential_json

            except Exception as e:
                last_error = e
                if attempt == max_retries - 1:  # Last attempt failed
                    error_msg = f"Failed to get valid JSON response after {max_retries} attempts. Last error: {str(last_error)}"
                    if last_raw:
                        error_msg += f"\nLast raw response: {last_raw}"
                    raise ValueError(error_msg)
                print(f"Attempt {attempt + 1} failed with error: {e}, retrying...")

    def structured(
        self,
        messages: List[Dict[str, str]],
        schema_or_tool: Dict[str, Any],
        max_tokens: int = 1000,
    ) -> Tuple[Dict[str, Any], str]:
        """
        - Anthropic: pass a *tool def* like ANTHROPIC_*_TOOL (with 'name' and 'input_schema').
                     Returns (parsed_dict, raw_json_str).
        - OpenAI/Together: pass the *JSON Schema payload* (the actual schema dict).
                           Returns (parsed_dict, raw_json_str_of_response).
        """
        if self.model_api == "anthropic":
            # Treat schema_or_tool as a Claude tool definition
            system_text = "\n".join(m["content"] for m in messages if m["role"] == "system")
            msgs_wo_system = [m for m in messages if m["role"] != "system"]

            max_retries = 3
            last_error = None
            last_parsed = None
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        print(f"Retrying Anthropic API call (attempt {attempt + 1}/{max_retries})...")
                    
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
                            last_parsed = parsed
                            
                            # Validate we got a non-empty response with required fields
                            if not parsed or not isinstance(parsed, dict):
                                raise ValueError(f"Empty or invalid tool response: {parsed}")
                            
                            # Check required fields from input_schema
                            input_schema = schema_or_tool.get("input_schema", {})
                            required_fields = input_schema.get("required", [])
                            missing = [f for f in required_fields if f not in parsed]
                            if missing:
                                raise ValueError(f"Missing required fields {missing} in response: {parsed}")
                            
                            raw_text = json.dumps(parsed)
                            return parsed, raw_text
                    
                    raise RuntimeError("Claude did not return the expected tool call.")
                    
                except Exception as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        error_msg = f"Anthropic structured call failed after {max_retries} attempts. Last error: {last_error}"
                        if last_parsed:
                            error_msg += f"\nLast parsed response: {last_parsed}"
                        raise RuntimeError(error_msg)
                    print(f"Attempt {attempt + 1} failed: {e}")

        # OpenAI / Together / OpenRouter: treat schema_or_tool as JSON Schema payload
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
        return self._make_api_call_with_retries(messages, schema_or_tool, max_tokens, response_format)

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