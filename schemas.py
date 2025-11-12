# schemas.py

MOVE_DECISION_SCHEMA = {
    "name": "grid_move",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 1000},
            "decision": {"type": "string", "enum": ["move", "n"]},
            # Required always; content rules:
            # - if decision == "move": must be "r,c"
            # - if decision == "n":    must be "" (empty)
            "move": {
                "type": "string",
                "pattern": r"^(?:-?\d+\s*,\s*-?\d+)?$"
            }
        },
        "required": ["rationale", "decision", "move"]
    },
    "strict": True
}

ANTHROPIC_MOVE_TOOL = {
    "name": "submit_move",
    "description": "Choose next move or 'n' if no valid move toward goal.",
    "input_schema": MOVE_DECISION_SCHEMA["schema"],
}


# JSON Schema used for OpenAI Structured Outputs
TRADE_PROPOSAL_SCHEMA = {
    "name": "trade_proposal",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 400},
            "want_to_trade": {"type": "boolean"},
            "resources_to_offer": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "color": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1}
                    },
                    "required": ["color", "quantity"]
                }
            },
            "resources_to_receive": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "color": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1}
                    },
                    "required": ["color", "quantity"]
                }
            }
        },
        "required": ["rationale", "want_to_trade"]
    },
    "strict": True
}

ANTHROPIC_TRADE_TOOL = {
    "name": "propose_trade",
    "description": "Propose a trade or respond with 'n' if you don't want to trade.",
    "input_schema": TRADE_PROPOSAL_SCHEMA["schema"],
}



YES_NO_SCHEMA = {
    "name": "yes_no",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 500},
            "answer": {"type": "string", "enum": ["yes", "no"]}
        },
        # IMPORTANT: OpenAI structured outputs requires ALL properties to be in `required`
        "required": ["rationale", "answer"]
    },
    "strict": True
}

ANTHROPIC_YESNO_TOOL = {
    "name": "yes_no",
    "description": "Answer yes or no to the proposed trade, with a brief justification.",
    "input_schema": YES_NO_SCHEMA["schema"],
}


STRICT_JUDGE_SCHEMA = {
    
    "name": "strict_judge",
    "schema": {
    "type": "object",
    "additionalProperties": False,
    "patternProperties": {
        # Keys must match the format "(row, col)"
        r"^\(\d+,\d+\)$": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "giver": {
                    "type": "string",
                    "pattern": r"^Player\s[0-9]+$"  # Matches "Player X" where X is a number
                },
                "receiver": {
                    "type": "string",
                    "pattern": r"^Player\s[0-9]+$"  # Matches "Player Y" where Y is a number
                },
                "color": {
                    "type": "string",
                    "minLength": 1  # Ensures the color is a non-empty string
                }
            },
            "required": ["giver", "receiver", "color"]
        }
    }
}
}

ANTHROPIC_STRICT_JUDGE_TOOL = {
    "name": "strict_judge",
    "description": "Summarise a contract based on a conversation between two players.",
    "input_schema": STRICT_JUDGE_SCHEMA["schema"],
}

FINISHING_JUDGE_SCHEMA = {
    "name": "finishing_judge",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
            # Keys must match the format "player_X_reaches_goal"
            r"^player_\d+_reaches_goal$": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "giver": {
                        "type": "string",
                        "pattern": r"^Player\s[0-9]+$"  # Matches "Player X" where X is a number
                    },
                    "receiver": {
                        "type": "string",
                        "pattern": r"^Player\s[0-9]+$"  # Matches "Player Y" where Y is a number
                    },
                    "amount": {
                        "type": "string",
                        "pattern": r"^\d+$",  # Matches a non-negative integer as a string
                        "minLength": 1  # Ensures the amount is not an empty string
                    }
                },
                "required": ["giver", "receiver", "amount"]
            }
        }
    }
}


ANTHROPIC_FINISHING_JUDGE_TOOL = {
    "name": "finishing_judge",
    "description": "Summarise a contract based on a conversation between two players.",
    "input_schema": FINISHING_JUDGE_SCHEMA["schema"],
}
