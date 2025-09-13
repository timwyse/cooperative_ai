#!/usr/bin/env bash
set -euo pipefail

# Usage: ./print-latest-log.sh [LOGS_DIR]
LOGS_DIR="${1:-logs}"

# Require jq
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required (https://stedolan.github.io/jq/)" >&2
  exit 1
fi

# Find the lexicographically latest verbose log JSON
LATEST=$(find "$LOGS_DIR" -type f -name 'verbose_log_*.json' 2>/dev/null | sort | tail -n 1)

if [[ -z "$LATEST" ]]; then
  echo "No files matching $LOGS_DIR/**/verbose_log_*.json" >&2
  exit 1
fi

echo "Parsing: $LATEST" >&2
jq -r '
  .. | objects
  | select(has("user_prompt") or has("agent_response"))
  | [
      ( .timestamp // "" ),
      ( .action // "" ),
      ( if has("user_prompt")    then "\n--- user_prompt ---\n"    + .user_prompt    else "" end ),
      ( if has("agent_response") then "\n--- agent_response ---\n" + (.agent_response // "null") else "" end )
    ]
  | join("\n")
  | select(length>0)
  | . + "\n\n==============================\n"
' "$LATEST"