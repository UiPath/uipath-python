#!/bin/bash
set -e

# Generate dynamic version with timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)
VERSION="0.0.1.${TIMESTAMP}"
echo "Using package version: $VERSION"

# Update version in pyproject.toml
sed -i "s/^version = .*/version = \"$VERSION\"/" pyproject.toml

echo "Current pyproject.toml:"
cat pyproject.toml

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

echo "Initializing project..."
uv run uipath init

echo "Packing agent with version $VERSION..."
uv run uipath pack --nolock

echo "Running E2E test (deploy, run job, validate)..."
uv run python src/deploy.py
