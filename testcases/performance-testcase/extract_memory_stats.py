#!/usr/bin/env python3
"""Extract memory statistics from memray binary output."""

import json
import subprocess
import sys
from pathlib import Path


def extract_memory_stats():
    """Extract memory stats from memray binary file using memray stats command."""
    print("Extracting memory stats from memray output...")

    memray_file = Path("artifacts/memory.bin")
    if not memray_file.exists():
        print(f"⚠️  Memray file not found: {memray_file}")
        return False

    try:
        # Run memray stats to get peak memory and total allocations
        result = subprocess.run(
            ["memray", "stats", str(memray_file)],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse the stats output
        # Format:
        # Total memory allocated: X.XX GB
        # Total allocations: X
        # Histogram of allocation size: ...
        # ...
        # High watermark: X.XX GB
        output_lines = result.stdout.split("\n")

        peak_memory_mb = 0
        total_allocations = 0

        for line in output_lines:
            if "High watermark" in line or "peak memory" in line.lower():
                # Extract memory value (could be in KB, MB, or GB)
                parts = line.split(":")
                if len(parts) >= 2:
                    value_str = parts[1].strip().split()[0]
                    try:
                        value = float(value_str)
                        # Check units
                        if "GB" in line:
                            peak_memory_mb = value * 1024
                        elif "MB" in line:
                            peak_memory_mb = value
                        elif "KB" in line:
                            peak_memory_mb = value / 1024
                    except ValueError:
                        pass

            if "Total allocations" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        total_allocations = int(parts[1].strip())
                    except ValueError:
                        pass

        # Save memory metrics
        memory_metrics = {
            "peak_mb": round(peak_memory_mb, 2),
            "total_allocations": total_allocations
        }

        output_path = Path("artifacts/memory_stats.json")
        with open(output_path, "w") as f:
            json.dump(memory_metrics, f, indent=2)

        print(f"✓ Memory stats saved to {output_path}")
        print(f"  Peak memory: {memory_metrics['peak_mb']} MB")
        print(f"  Total allocations: {memory_metrics['total_allocations']}")

        return True

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to extract memory stats: {e}")
        print(f"  stdout: {e.stdout}")
        print(f"  stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"⚠️  Error extracting memory stats: {e}")
        return False


if __name__ == "__main__":
    success = extract_memory_stats()
    sys.exit(0 if success else 1)
