#!/bin/bash
set -e

echo "=== E2E Test: Eval Spans Verification ==="

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running evaluations with trace capture..."
# Run eval with trace file to capture spans
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/default.json \
    --no-report \
    --trace-file __uipath/traces.jsonl

echo "Test completed successfully!"
