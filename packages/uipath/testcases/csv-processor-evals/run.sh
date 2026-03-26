#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Running evaluations with custom evaluators..."
uv run uipath eval main ../../samples/csv-processor/evaluations/eval-sets/file-input-tests-local.json --no-report --output-file file-input-tests-local.json

echo "Running assertions..."
uv run python src/assert.py

echo "Test completed successfully!"
