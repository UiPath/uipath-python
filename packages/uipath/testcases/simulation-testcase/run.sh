#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Running agent with simulation..."
uv run uipath run main -f input.json --simulation "$(cat simulation.json)" 2>&1 | tee run.log
