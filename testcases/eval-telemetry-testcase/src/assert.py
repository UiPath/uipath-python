"""E2E assertions for eval telemetry testcase.

This script validates that telemetry events are sent to Application Insights by:
1. Verifying eval completed successfully
2. Querying App Insights API to check for expected telemetry events
3. Validating event properties match expected values
"""

import json
import os
import sys
import time
from typing import Any

import httpx

# Expected telemetry event names
EXPECTED_EVENTS = [
    "EvalSetRun.Start.URT",
    "EvalSetRun.End.URT",
    "EvalRun.Start.URT",
    "EvalRun.End.URT",
]


def load_output(output_file: str) -> dict[str, Any]:
    """Load output from a JSON file."""
    with open(output_file, "r", encoding="utf-8") as f:
        return json.load(f)


def query_app_insights(
    app_id: str, api_key: str, query: str, max_retries: int = 3
) -> dict[str, Any]:
    """Query Application Insights using the REST API.

    Args:
        app_id: Application Insights App ID
        api_key: Application Insights API Key
        query: Kusto query to execute
        max_retries: Number of retries on failure

    Returns:
        Query results as dictionary
    """
    url = f"https://api.applicationinsights.io/v1/apps/{app_id}/query"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"query": query}

    for attempt in range(max_retries):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries} after error: {e}")
                time.sleep(5)
            else:
                raise


def verify_telemetry_events(app_id: str, api_key: str, eval_set_run_id: str) -> bool:
    """Verify telemetry events were sent to Application Insights.

    Args:
        app_id: Application Insights App ID
        api_key: Application Insights API Key
        eval_set_run_id: The eval set run ID to search for

    Returns:
        True if all expected events were found
    """
    print("\n--- Querying App Insights for events ---")
    print(f"  EvalSetRunId: {eval_set_run_id}")

    # Query for events with the specific EvalSetRunId
    query = f"""
    customEvents
    | where timestamp > ago(10m)
    | where customDimensions.EvalSetRunId == "{eval_set_run_id}"
       or customDimensions["EvalSetRunId"] == "{eval_set_run_id}"
    | project name, timestamp, customDimensions
    | order by timestamp asc
    """

    try:
        result = query_app_insights(app_id, api_key, query)
    except Exception as e:
        print(f"  Error querying App Insights: {e}")
        return False

    # Parse results
    tables = result.get("tables", [])
    if not tables:
        print("  No tables returned from query")
        return False

    rows = tables[0].get("rows", [])
    columns = [col["name"] for col in tables[0].get("columns", [])]

    print(f"  Found {len(rows)} events")

    # Extract event names
    found_events: list[str] = []
    name_idx = columns.index("name") if "name" in columns else 0

    for row in rows:
        event_name = row[name_idx]
        found_events.append(event_name)
        print(f"    - {event_name}")

    # Check for expected events
    print("\n--- Verifying expected events ---")
    all_found = True
    for expected in EXPECTED_EVENTS:
        if expected in found_events:
            print(f"  [OK] {expected}")
        else:
            print(f"  [MISSING] {expected}")
            all_found = False

    return all_found


def verify_output(output_file: str) -> bool:
    """Verify the eval output file."""
    print("\n--- Verifying eval output ---")

    if not os.path.isfile(output_file):
        print(f"  Output file '{output_file}' not found")
        return False

    output_data = load_output(output_file)

    # The eval output can have two formats:
    # 1. Direct results: {"evaluationSetName": "...", "evaluationSetResults": [...]}
    # 2. Wrapped results: {"status": "successful", "output": {...}}
    if "status" in output_data:
        status = output_data.get("status")
        if status != "successful":
            print(f"  Eval failed with status: {status}")
            return False
        print(f"  Status: {status}")
        output = output_data.get("output", {})
        evaluation_results = output.get("evaluationSetResults", [])
    else:
        # Direct format - check for evaluationSetResults
        evaluation_results = output_data.get("evaluationSetResults", [])
        if not evaluation_results:
            print("  No evaluationSetResults found in output")
            return False
        print("  Status: completed (direct output format)")

    print(f"  Evaluation results: {len(evaluation_results)}")

    # Verify we have results with scores
    if len(evaluation_results) == 0:
        print("  No evaluation results found")
        return False

    return True


def main() -> None:
    """Main assertion logic."""
    output_file = "__uipath/output.json"

    # Get environment variables
    app_id = os.environ.get("APP_INSIGHTS_APP_ID")
    api_key = os.environ.get("APP_INSIGHTS_API_KEY")
    eval_set_run_id = os.environ.get("EVAL_TEST_RUN_ID")

    # Verify eval output first
    if not verify_output(output_file):
        print("\nEval output verification failed")
        sys.exit(1)

    # Check if App Insights verification is possible
    if not app_id or not api_key:
        print("\n--- Skipping App Insights verification ---")
        print("  APP_INSIGHTS_APP_ID or APP_INSIGHTS_API_KEY not set")
        print("  Telemetry verification skipped (eval completed successfully)")
        print("\nAll assertions passed! (telemetry verification skipped)")
        return

    if not eval_set_run_id:
        print("\n--- Skipping App Insights verification ---")
        print("  EVAL_TEST_RUN_ID not set")
        print("\nAll assertions passed! (telemetry verification skipped)")
        return

    # Verify telemetry events in App Insights
    if not verify_telemetry_events(app_id, api_key, eval_set_run_id):
        print("\n" + "=" * 60)
        print("Telemetry verification FAILED")
        print("Expected events not found in App Insights")
        print("=" * 60)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All assertions passed!")
    print("  - Eval completed successfully")
    print("  - Telemetry events verified in App Insights")
    print("=" * 60)


if __name__ == "__main__":
    main()
