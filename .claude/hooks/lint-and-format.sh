#!/bin/bash

# Hook to automatically run ruff format and ruff check on Python files
# Reads JSON input from stdin containing tool information

# Read JSON input from stdin
INPUT=$(cat)

# Extract file_path from the JSON input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Exit if no file path or jq failed
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only process Python files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

echo "🔧 Auto-formatting and linting $FILE_PATH..."

# Run ruff format on the file (suppress errors)
uv run ruff format "$FILE_PATH" 2>/dev/null || true

# Run ruff check --fix on the file (suppress errors)
uv run ruff check --fix "$FILE_PATH" 2>/dev/null || true

echo "✅ Formatted and linted $FILE_PATH"

exit 0
