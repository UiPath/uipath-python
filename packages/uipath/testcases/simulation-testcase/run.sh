#!/bin/bash
set -e

TESTCASE_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_DIR="$(cd "$TESTCASE_DIR/../../samples/runtime-simulations-agent" && pwd)"

echo "Syncing testcase dependencies (local editable uipath)..."
uv sync --project "$TESTCASE_DIR"

echo "Authenticating with UiPath..."
uv run --project "$TESTCASE_DIR" uipath auth \
    --client-id="$CLIENT_ID" \
    --client-secret="$CLIENT_SECRET" \
    --base-url="$BASE_URL"

echo "Running agent with simulation..."
mkdir -p "$TESTCASE_DIR/__uipath"
cd "$SAMPLE_DIR"
"$TESTCASE_DIR/.venv/bin/uipath" run main \
    -f input.json \
    --simulation "$(cat simulation.json)" \
    --output-file "$TESTCASE_DIR/__uipath/output.json" 2>&1 | tee "$TESTCASE_DIR/run.log"
