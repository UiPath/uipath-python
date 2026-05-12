#!/bin/bash
set -e

TESTCASE_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_DIR="$(cd "$TESTCASE_DIR/../../samples/runtime-simulations-agent" && pwd)"

echo "Syncing testcase dependencies (local editable uipath)..."
uv sync --project "$TESTCASE_DIR"

UIPATH_BIN="$TESTCASE_DIR/.venv/bin/uipath"

# Run auth and agent from the sample dir so credentials are stored and read
# from the same location. Output and log are written back to the testcase dir.
cd "$SAMPLE_DIR"

echo "Authenticating with UiPath..."
"$UIPATH_BIN" auth \
    --client-id="$CLIENT_ID" \
    --client-secret="$CLIENT_SECRET" \
    --base-url="$BASE_URL"

echo "Running agent with simulation..."
mkdir -p "$TESTCASE_DIR/__uipath"
"$UIPATH_BIN" run main \
    -f input.json \
    --simulation "$(cat simulation.json)" \
    --output-file "$TESTCASE_DIR/__uipath/output.json" 2>&1 | tee "$TESTCASE_DIR/run.log"
