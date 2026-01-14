#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

uv add py-spy memray

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Run init..."
uv run uipath init

echo "Packing agent..."
uv run uipath pack

echo "Creating artifacts directory..."
mkdir -p artifacts

echo "Run agent with py-spy profiling (raw text format for LLM analysis)"
uv run py-spy record --subprocesses -f raw -o artifacts/cpu_profile.txt -- uv run uipath run main '{"message": "abc", "repeat": 2, "prefix": "xyz"}'

echo "Run agent with py-spy profiling (flamegraph SVG for visualization)"
uv run py-spy record --subprocesses -f flamegraph -o artifacts/cpu_profile.svg -- uv run uipath run main '{"message": "abc", "repeat": 2, "prefix": "xyz"}'

echo "Run agent with py-spy profiling (speedscope JSON for interactive viewing)"
uv run py-spy record --subprocesses -f speedscope -o artifacts/cpu_profile_speedscope.json -- uv run uipath run main '{"message": "abc", "repeat": 2, "prefix": "xyz"}'
