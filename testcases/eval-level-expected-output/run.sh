#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running eval-level expectedOutput evaluations (deterministic evaluators)..."
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/eval-level-expected-output.json --no-report --output-file eval-level-expected-output.json

echo "Running eval-level expectedOutput evaluations (LLM judge)..."
uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/eval-level-expected-output-llm-judge.json --no-report --output-file eval-level-expected-output-llm-judge.json

echo "Test completed successfully!"
