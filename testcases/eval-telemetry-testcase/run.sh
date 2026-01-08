#!/bin/bash
set -e

echo "=== E2E Test: Eval Telemetry Integration ==="

# Validate required environment variables
if [ -z "$APPLICATIONINSIGHTS_CONNECTION_STRING" ]; then
    echo "Warning: APPLICATIONINSIGHTS_CONNECTION_STRING not set, telemetry won't be sent"
fi
if [ -z "$APP_INSIGHTS_APP_ID" ]; then
    echo "Warning: APP_INSIGHTS_APP_ID not set, skipping telemetry verification"
fi
if [ -z "$APP_INSIGHTS_API_KEY" ]; then
    echo "Warning: APP_INSIGHTS_API_KEY not set, skipping telemetry verification"
fi

echo "Syncing dependencies..."
uv sync

echo "Authenticating with UiPath..."
uv run uipath auth --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" --base-url="$BASE_URL"

# Generate a unique run ID to identify this test run's telemetry events
export EVAL_TEST_RUN_ID="e2e-test-$(date +%s)-$$"
echo "Test Run ID: $EVAL_TEST_RUN_ID"

echo "Running evaluations with telemetry enabled..."
# Run eval with telemetry explicitly enabled and App Insights connection string
UIPATH_TELEMETRY_ENABLED=true uv run uipath eval main ../../samples/calculator/evaluations/eval-sets/default.json \
    --no-report \
    --output-file __uipath/output.json \
    --eval-set-run-id "$EVAL_TEST_RUN_ID"

# Wait for telemetry to be ingested into App Insights
if [ -n "$APP_INSIGHTS_APP_ID" ] && [ -n "$APP_INSIGHTS_API_KEY" ]; then
    echo "Waiting for telemetry to be ingested (30 seconds)..."
    sleep 30
fi

echo "Test completed successfully!"
