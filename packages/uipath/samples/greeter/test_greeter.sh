#!/bin/bash

# Test script for greeter sample with mocked authentication
# This demonstrates the input simulation feature

echo "Testing greeter sample with simulated inputs..."
echo ""
echo "Note: This requires valid UiPath authentication for LLM calls."
echo "Set UIPATH_URL and UIPATH_ACCESS_TOKEN environment variables."
echo ""

# Check if auth is configured
if [ -z "$UIPATH_URL" ] || [ -z "$UIPATH_ACCESS_TOKEN" ]; then
    echo "⚠️  Authentication not configured."
    echo ""
    echo "To run this demo with real LLM input generation:"
    echo "  export UIPATH_URL=https://your-tenant.uipath.com"
    echo "  export UIPATH_ACCESS_TOKEN=your-token"
    echo ""
    echo "Or run: uipath auth"
    echo ""
    exit 1
fi

# Run the evaluation
uv run uipath eval main ./evaluations/eval-sets/simulated-input.json --output-file output.json

echo ""
echo "Results saved to output.json"
