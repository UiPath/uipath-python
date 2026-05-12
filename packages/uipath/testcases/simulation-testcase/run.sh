#!/bin/bash
set -e

TESTCASE_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_DIR="$(cd "$TESTCASE_DIR/../../samples/runtime-simulations-agent" && pwd)"

echo "Syncing testcase dependencies (local editable uipath)..."
uv sync --project "$TESTCASE_DIR"

UIPATH_BIN="$TESTCASE_DIR/.venv/bin/uipath"

# Run auth and agent from the sample dir so credentials are stored and read
# from the same location.
cd "$SAMPLE_DIR"

echo "Authenticating with UiPath..."
"$UIPATH_BIN" auth \
    --client-id="$CLIENT_ID" \
    --client-secret="$CLIENT_SECRET" \
    --base-url="$BASE_URL"

echo "Running agent with simulation..."
"$UIPATH_BIN" run main \
    -f input.json \
    --simulation "$(cat simulation.json)" 2>&1 | tee "$TESTCASE_DIR/run.log"

# Copy the runtime output file back to the testcase dir for assert.py
mkdir -p "$TESTCASE_DIR/__uipath"
cp "$SAMPLE_DIR/__uipath/output.json" "$TESTCASE_DIR/__uipath/output.json"
