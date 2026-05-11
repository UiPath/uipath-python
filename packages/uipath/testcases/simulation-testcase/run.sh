#!/bin/bash
set -e

SAMPLE_DIR="$(cd "$(dirname "$0")/../../samples/runtime-simulations-agent" && pwd)"

echo "Syncing sample dependencies..."
uv sync --project "$SAMPLE_DIR"

echo "Authenticating with UiPath..."
uv run --project "$SAMPLE_DIR" uipath auth \
    --client-id="$CLIENT_ID" \
    --client-secret="$CLIENT_SECRET" \
    --base-url="$BASE_URL"

echo "Running agent with simulation..."
uv run --project "$SAMPLE_DIR" uipath run main \
    -f "$SAMPLE_DIR/input.json" \
    --simulation "$(cat "$SAMPLE_DIR/simulation.json")" 2>&1 | tee run.log
