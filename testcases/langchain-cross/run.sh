#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Run init..."
uv run uipath init

echo "Packing agent..."
uv run uipath pack

echo "Run agent with input from cli"
uv run uipath run agent '{"topic": "Weather and Technology"}'

echo "Running agent again with empty UIPATH_JOB_KEY..."
export UIPATH_JOB_KEY=""
uv run uipath run agent --trace-file .uipath/traces.jsonl '{"topic": "Weather and Technology"}' >> local_run_output.log