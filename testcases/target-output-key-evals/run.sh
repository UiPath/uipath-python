#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running target-output-key evaluations..."
uv run uipath eval main ../../samples/multi-output-agent/evaluations/eval-sets/target-output-key.json --no-report --output-file target-output-key.json

echo "Test completed successfully!"
