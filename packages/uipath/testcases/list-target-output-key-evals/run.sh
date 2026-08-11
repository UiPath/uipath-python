#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running list targetOutputKey evaluations..."
uv run uipath eval main ../../samples/list_target_output_key_test/evaluations/eval-sets/default.json --no-report --output-file default.json

echo "Test completed successfully!"
