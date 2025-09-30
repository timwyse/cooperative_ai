# schemas.py

MOVE_DECISION_SCHEMA = {
    "name": "grid_move",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {"type": "string", "enum": ["move", "n"]},
            # Required always; content rules:
            # - if decision == "move": must be "r,c"
            # - if decision == "n":    must be "" (empty)
            "move": {
                "type": "string",
                "pattern": r"^(?:-?\d+\s*,\s*-?\d+)?$"
            }
        },
        "required": ["decision", "move"]
    },
    "strict": True
}



# JSON Schema used for OpenAI Structured Outputs
TRADE_PROPOSAL_SCHEMA = {
    "name": "trade_proposal",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "resources_to_offer": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "color": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 0}
                    },
                    "required": ["color", "quantity"]
                }
            },
            "resources_to_receive": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "color": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 0}
                    },
                    "required": ["color", "quantity"]
                }
            }
        },
        "required": ["resources_to_offer", "resources_to_receive"]
    },
    "strict": True
}

ANTHROPIC_MOVE_TOOL = {
    "name": "submit_move",
    "description": "Choose next move or 'n' if no valid move toward goal.",
    "input_schema": MOVE_DECISION_SCHEMA["schema"],
}

ANTHROPIC_TRADE_TOOL = {
    "name": "propose_trade",
    "description": "Propose resources to offer and receive.",
    "input_schema": TRADE_PROPOSAL_SCHEMA["schema"],
}


YES_NO_SCHEMA = {
    "name": "yes_no",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "answer": {"type": "string", "enum": ["yes", "no"]},
            "rationale": {"type": "string", "maxLength": 400}
        },
        # IMPORTANT: OpenAI structured outputs requires ALL properties to be in `required`
        "required": ["answer", "rationale"]
    },
    "strict": True
}

ANTHROPIC_YESNO_TOOL = {
    "name": "accept_trade",
    "description": "Answer yes or no to the proposed trade, with a brief justification.",
    "input_schema": YES_NO_SCHEMA["schema"],
}
