# schemas.py

MOVE_DECISION_SCHEMA = {
    "name": "grid_move",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 1000},
            "want_to_move": {"type": "boolean"},
            # Required always; content rules:
            # - if want_to_move == true: must be "r,c"
            # - if want_to_move == false: must be "" (empty)
            "move": {
                "type": "string",
                "pattern": r"^(?:-?\d+\s*,\s*-?\d+)?$"
            }
        },
        "required": ["rationale", "want_to_move", "move"]
    },
    "strict": True
}

ANTHROPIC_MOVE_TOOL = {
    "name": "submit_move",
    "description": "Choose next move or indicate you don't want to move.",
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
            "chips_to_offer": {
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
            "chips_to_receive": {
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



# For trade responses
TRADE_RESPONSE_SCHEMA = {
    "name": "trade_response",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 500},
            "accept_trade": {"type": "boolean"}
        },
        # IMPORTANT: OpenAI structured outputs requires ALL properties to be in `required`
        "required": ["rationale", "accept_trade"]
    },
    "strict": True
}

ANTHROPIC_TRADE_RESPONSE_TOOL = {
    "name": "trade_response",
    "description": "Decide whether to accept or reject the proposed trade.",
    "input_schema": TRADE_RESPONSE_SCHEMA["schema"],
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

# For pay4partner arrangement responses
PAY4PARTNER_ARRANGEMENT_SCHEMA = {
    "name": "pay4partner_arrangement",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 500},
            "accept_p4p_arrangement": {"type": "boolean"}
        },
        "required": ["rationale", "accept_p4p_arrangement"]
    },
    "strict": True
}

ANTHROPIC_PAY4PARTNER_ARRANGEMENT_TOOL = {
    "name": "pay4partner_arrangement",
    "description": "Decide whether to accept or reject the pay4partner arrangement.",
    "input_schema": PAY4PARTNER_ARRANGEMENT_SCHEMA["schema"],
}

# For pay4partner honor promise (when asked to pay)
PAY4PARTNER_HONOR_SCHEMA = {
    "name": "pay4partner_honor",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 500},
            "honor_p4p_agreement": {"type": "boolean"}
        },
        "required": ["rationale", "honor_p4p_agreement"]
    },
    "strict": True
}

ANTHROPIC_PAY4PARTNER_HONOR_TOOL = {
    "name": "pay4partner_honor",
    "description": "Decide whether to honor the pay4partner agreement and pay for the partner's move.",
    "input_schema": PAY4PARTNER_HONOR_SCHEMA["schema"],
}

# Generic boolean answer schema (kept for judge and any other generic uses)
BOOLEAN_ANSWER_SCHEMA = {
    "name": "boolean_answer",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rationale": {"type": "string", "maxLength": 500},
            "answer": {"type": "boolean"}
        },
        "required": ["rationale", "answer"]
    },
    "strict": True
}

ANTHROPIC_BOOLEAN_ANSWER_TOOL = {
    "name": "boolean_answer",
    "description": "Answer true or false to the question, with a brief justification.",
    "input_schema": BOOLEAN_ANSWER_SCHEMA["schema"],
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
