#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running evaluations with custom evaluator..."
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/legacy.json --no-report --output-file legacy.json
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/default.json --no-report --output-file default.json

echo "Test completed successfully!"
