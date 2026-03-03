#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo ""
echo "Running evaluations with input overrides..."
echo "Using eval set: src/input-overrides-eval-set.json"
echo "Using input overrides: src/input-overrides.json"
echo ""

# Create output directory
mkdir -p __uipath

# Read input overrides from JSON file
INPUT_OVERRIDES=$(cat src/input-overrides.json)

# Run evaluations with input overrides
uv run uipath eval main src/input-overrides-eval-set.json \
  --no-report \
  --output-file __uipath/output.json \
  --input-overrides "$INPUT_OVERRIDES"

echo ""
echo "Evaluations completed! Verifying results..."
echo ""

# Run assertion script to verify results
uv run python src/assert.py

echo ""
echo "✅ Input overrides integration test completed successfully!"
