#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running evaluations with custom evaluator..."
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/legacy.json --no-report --output-file legacy.json
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/default.json --no-report --output-file default.json
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/multi-model.json --no-report --output-file multi-model.json
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/trajectory-multi-model.json --no-report --output-file trajectory-multi-model.json
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/faithfulness-multi-model.json --no-report --output-file faithfulness-multi-model.json
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/context-precision-multi-model.json --no-report --output-file context-precision-multi-model.json

echo "Test completed successfully!"
