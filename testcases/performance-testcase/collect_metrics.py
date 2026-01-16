#!/usr/bin/env python3
"""Collect performance metrics and upload to Azure Blob Storage."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_timing_metrics(artifacts_dir: str = "artifacts") -> dict:
    """Load timing metrics from instrumentation files.

    Returns timing breakdown:
    - User code time (from main.py instrumentation)
    - Total execution time (from py-spy speedscope profile)
    - Framework overhead (calculated as total - user code)
    """
    artifacts_path = Path(artifacts_dir)

    # Load user code timing (instrumented in main.py)
    user_timing_path = artifacts_path / "user_code_timing.json"
    user_code_time = 0

    if user_timing_path.exists():
        try:
            with open(user_timing_path, "r", encoding="utf-8") as f:
                user_timing = json.load(f)
                user_code_time = user_timing.get("user_code_time_seconds", 0)
        except json.JSONDecodeError:
            pass

    # Extract total execution time from py-spy speedscope profile
    profile_path = artifacts_path / "profile.json"
    total_time = 0
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                speedscope_data = json.load(f)
                # Get weights from first profile (main process)
                profiles = speedscope_data.get("profiles", [])
                if profiles:
                    weights = profiles[0].get("weights", [])
                    # Sum all weights (in microseconds) to get total time
                    total_time_us = sum(weights)
                    total_time = total_time_us / 1_000_000  # Convert to seconds
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    # Calculate framework overhead
    framework_overhead = total_time - user_code_time

    # Calculate percentages
    user_percentage = (user_code_time / total_time * 100) if total_time > 0 else 0
    framework_percentage = (framework_overhead / total_time * 100) if total_time > 0 else 0

    return {
        "total_time_seconds": round(total_time, 3),
        "total_time_ms": round(total_time * 1000, 2),
        "user_code_time": {
            "time_ms": round(user_code_time * 1000, 2),
            "time_seconds": round(user_code_time, 6),
            "percentage": round(user_percentage, 2)
        },
        "framework_overhead": {
            "time_ms": round(framework_overhead * 1000, 2),
            "time_seconds": round(framework_overhead, 3),
            "percentage": round(framework_percentage, 2)
        }
    }


def load_memory_metrics(artifacts_dir: str = "artifacts") -> dict:
    """Load memory metrics from memray stats output."""
    memory_stats_path = Path(artifacts_dir) / "memory_stats.json"
    if not memory_stats_path.exists():
        return {}

    try:
        with open(memory_stats_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    if not Path(file_path).exists():
        return 0
    return Path(file_path).stat().st_size


def collect_metrics(
    artifacts_dir: str = "artifacts",
    framework: str | None = None,
    testcase: str | None = None,
) -> dict:
    """Collect all performance metrics from artifacts directory.

    Args:
        artifacts_dir: Directory containing profile artifacts
        framework: Framework discriminator (uipath, uipath-langgraph, uipath-llamaindex)
                  If None, auto-detects from FRAMEWORK env var or defaults to 'uipath'
        testcase: Testcase name (defaults to TESTCASE env var or current directory name)
    """
    artifacts_path = Path(artifacts_dir)

    # Auto-detect framework if not specified
    if framework is None:
        framework = os.getenv("FRAMEWORK", "uipath")

    # Auto-detect testcase from current directory if not specified
    if testcase is None:
        testcase = os.getenv("TESTCASE", Path.cwd().name)

    # Load timing metrics (user code + total execution)
    timing_metrics = load_timing_metrics(artifacts_dir)

    # Load memory metrics (from memray)
    memory_metrics = load_memory_metrics(artifacts_dir)

    # Get artifact file sizes
    file_sizes = {
        "profile_json": get_file_size(str(artifacts_path / "profile.json")),
        "user_code_timing_json": get_file_size(str(artifacts_path / "user_code_timing.json")),
        "memory_bin": get_file_size(str(artifacts_path / "memory.bin")),
        "memory_stats_json": get_file_size(str(artifacts_path / "memory_stats.json")),
    }

    # Build complete metrics object
    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "framework": framework,  # Discriminator: uipath, uipath-langgraph, uipath-llamaindex
        "testcase": testcase,
        "function": "main (echo function - minimal work)",
        "timing": timing_metrics,
        "memory": memory_metrics,
        "file_sizes": file_sizes,
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "ci": os.getenv("CI", "false"),
            "runner": os.getenv("RUNNER_OS", "unknown"),
            "github_run_id": os.getenv("GITHUB_RUN_ID", "local"),
            "github_sha": os.getenv("GITHUB_SHA", "unknown"),
            "branch": os.getenv("GITHUB_REF_NAME", "unknown"),
        },
    }

    return metrics


def save_metrics_json(metrics: dict, output_path: str = "artifacts/metrics.json"):
    """Save metrics to JSON file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"✓ Metrics saved to {output_path}")


def upload_to_blob_storage(
    file_path: str,
    connection_string: str | None = None,
    container_name: str = "performance-metrics",
    blob_name: str | None = None,
) -> bool:
    """Upload file to Azure Blob Storage.

    Args:
        file_path: Path to file to upload
        connection_string: Azure Storage connection string (or uses AZURE_STORAGE_CONNECTION_STRING env var)
        container_name: Blob container name
        blob_name: Name for blob (defaults to filename with timestamp)

    Returns:
        True if upload succeeded, False otherwise
    """
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        print("⚠️  azure-storage-blob not installed. Run: pip install azure-storage-blob")
        return False

    connection_string = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("⚠️  AZURE_STORAGE_CONNECTION_STRING not set")
        return False

    if not Path(file_path).exists():
        print(f"⚠️  File not found: {file_path}")
        return False

    # Generate blob name with timestamp if not provided
    if blob_name is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = Path(file_path).name
        blob_name = f"{timestamp}_{filename}"

    try:
        # Create BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # Create container if it doesn't exist
        try:
            container_client = blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                blob_service_client.create_container(container_name)
                print(f"✓ Created container: {container_name}")
        except Exception as e:
            print(f"⚠️  Container check/creation warning: {e}")

        # Upload file
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=blob_name
        )

        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        blob_url = blob_client.url
        print(f"✓ Uploaded to Azure Blob Storage: {blob_url}")
        return True

    except Exception as e:
        print(f"⚠️  Upload failed: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Performance Metrics Collection")
    print("=" * 60)

    # Collect metrics
    print("\n📊 Collecting metrics...")
    metrics = collect_metrics()

    # Print summary
    print("\n📈 Metrics Summary:")
    print(f"  Framework: {metrics['framework']}")
    print(f"  Testcase: {metrics['testcase']}")

    # Timing metrics
    timing = metrics.get('timing', {})
    if timing:
        print(f"\n⏱️  Timing Metrics:")
        print(f"  Total execution time: {timing.get('total_time_seconds', 0)}s ({timing.get('total_time_ms', 0)}ms)")

        user_code = timing.get('user_code_time', {})
        print(f"  User code time: {user_code.get('time_seconds', 0)}s ({user_code.get('percentage', 0)}%)")

        framework = timing.get('framework_overhead', {})
        print(f"  Framework overhead: {framework.get('time_seconds', 0)}s ({framework.get('percentage', 0)}%)")

    # Memory metrics
    memory = metrics.get('memory', {})
    if memory:
        print(f"\n💾 Memory Metrics:")
        print(f"  Peak memory: {memory.get('peak_mb', 0)} MB")
        if 'total_allocations' in memory:
            print(f"  Total allocations: {memory.get('total_allocations', 0):,}")

    # Save metrics JSON
    print("\n💾 Saving metrics...")
    metrics_path = "artifacts/metrics.json"
    save_metrics_json(metrics, metrics_path)

    # Upload to Azure Blob Storage if connection string is available
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        print("\n☁️  Uploading to Azure Blob Storage...")

        # Generate blob name with metadata including framework discriminator
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        framework = metrics["framework"]
        branch = metrics["environment"]["branch"].replace("/", "_")
        run_id = metrics["environment"]["github_run_id"]
        blob_name = f"{framework}/{branch}/{run_id}/{timestamp}_metrics.json"

        upload_to_blob_storage(
            metrics_path,
            connection_string=connection_string,
            container_name="performance-metrics",
            blob_name=blob_name,
        )
    else:
        print("\n⚠️  AZURE_STORAGE_CONNECTION_STRING not set - skipping upload")
        print("   To enable upload, set environment variable:")
        print("   export AZURE_STORAGE_CONNECTION_STRING='DefaultEndpointsProtocol=...'")

    print("\n✅ Metrics collection complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
