#!/usr/bin/env python3
"""Profile memory usage and total execution time during agent execution."""

import json
import subprocess
import sys
import time
from pathlib import Path


def profile_agent_execution():
    """Run the agent and measure total execution time.

    Note: Memory profiling of subprocesses requires psutil which adds overhead.
    For now, we focus on accurate timing measurement.
    """
    print("Starting performance profiling...")

    # Record total execution start time
    total_start_time = time.perf_counter()

    # Run the agent and measure total time
    try:
        result = subprocess.run(
            [
                "uv", "run", "uipath", "run", "main",
                '{"message": "abc", "repeat": 2, "prefix": "xyz"}'
            ],
            capture_output=True,
            text=True,
            check=True
        )
        success = True
        error = None
    except subprocess.CalledProcessError as e:
        success = False
        error = str(e)
        result = e

    # Record total execution end time
    total_end_time = time.perf_counter()
    total_execution_time = total_end_time - total_start_time

    # Build metrics
    metrics = {
        "total_execution_time_seconds": round(total_execution_time, 3),
        "success": success,
        "error": error
    }

    # Save metrics
    output_path = Path("artifacts/total_execution.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"✓ Performance profile saved to {output_path}")
    print(f"  Total execution time: {metrics['total_execution_time_seconds']}s")

    return metrics


if __name__ == "__main__":
    try:
        profile_agent_execution()
    except Exception as e:
        print(f"⚠️  Performance profiling failed: {e}", file=sys.stderr)
        sys.exit(1)
