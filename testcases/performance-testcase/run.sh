#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo "Installing profiling tools and Azure SDK..."
uv add py-spy azure-storage-blob

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Run init..."
uv run uipath init

echo "Packing agent..."
uv run uipath pack

echo "Creating artifacts directory..."
mkdir -p artifacts

echo "Run agent with py-spy profiling (speedscope JSON with timing data)"
uv run py-spy record --subprocesses -f speedscope -o artifacts/profile.json -- uv run uipath run main '{"message": "abc", "repeat": 2, "prefix": "xyz"}'

echo "Run agent with memory profiling using tracemalloc"
uv run python profile_memory.py

echo "Collecting performance metrics and uploading to Azure..."
uv run python collect_metrics.py
