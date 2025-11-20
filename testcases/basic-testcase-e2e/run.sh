#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Run init..."
uv run uipath init

echo "Packing agent..."
uv run uipath pack --nolock

uv run uipath publish --folder "UIPATH_CODED_AGENTS_TESTING_AREA"

echo "Deploying agent..."
uv run ./src/deploy.py