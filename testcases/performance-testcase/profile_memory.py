#!/usr/bin/env python3
"""Profile memory usage during agent execution."""

import json
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path


def profile_agent_execution():
    """Run the agent with memory profiling enabled."""
    print("Starting memory profiling...")

    # Start tracking memory allocations
    tracemalloc.start()
    start_time = time.perf_counter()

    # Record initial memory snapshot
    snapshot_start = tracemalloc.take_snapshot()

    # Run the agent
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

    # Record final memory snapshot
    end_time = time.perf_counter()
    snapshot_end = tracemalloc.take_snapshot()

    # Get peak memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Calculate memory difference
    top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')

    # Extract top memory allocations
    top_allocations = []
    for stat in top_stats[:10]:
        top_allocations.append({
            "file": str(stat.traceback.format()[0]) if stat.traceback else "unknown",
            "size_bytes": stat.size,
            "size_diff_bytes": stat.size_diff,
            "count": stat.count,
            "count_diff": stat.count_diff
        })

    # Build metrics
    metrics = {
        "execution_time_seconds": round(end_time - start_time, 3),
        "memory": {
            "current_bytes": current,
            "peak_bytes": peak,
            "current_mb": round(current / 1024 / 1024, 2),
            "peak_mb": round(peak / 1024 / 1024, 2),
        },
        "top_allocations": top_allocations,
        "success": success,
        "error": error
    }

    # Save metrics
    output_path = Path("artifacts/memory_profile.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"✓ Memory profile saved to {output_path}")
    print(f"  Execution time: {metrics['execution_time_seconds']}s")
    print(f"  Peak memory: {metrics['memory']['peak_mb']} MB")
    print(f"  Current memory: {metrics['memory']['current_mb']} MB")

    return metrics


if __name__ == "__main__":
    try:
        profile_agent_execution()
    except Exception as e:
        print(f"⚠️  Memory profiling failed: {e}", file=sys.stderr)
        sys.exit(1)
