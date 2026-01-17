# Performance Testcase

This testcase measures the **framework overhead** of `uipath run` by profiling a minimal function that does almost no work. This helps identify performance bottlenecks in the CLI, runtime, and platform infrastructure.

## What It Does

1. **Runs a minimal function** ([main.py](main.py)) that only performs basic string operations
2. **Profiles with py-spy** (speedscope format) to capture execution timing
3. **Profiles memory usage** with Python's tracemalloc
4. **Collects performance metrics** including:
   - Total execution time
   - Time spent in user function vs framework overhead
   - Time spent in imports/module loading
   - Memory usage (peak and current)
   - File sizes of profiling artifacts
5. **Uploads metrics to Azure Blob Storage** for historical tracking and analysis

## Test Function

```python
def main(input: EchoIn) -> EchoOut:
    result = []
    for _ in range(input.repeat):
        line = input.message
        if input.prefix:
            line = f"{input.prefix}: {line}"
        result.append(line)
    return EchoOut(message="\n".join(result))
```

This function is deliberately minimal to isolate framework overhead.

## Metrics Collected

The testcase generates a `metrics.json` file with:

```json
{
  "timestamp": "2026-01-15T10:30:45.123456+00:00",
  "framework": "uipath",
  "testcase": "performance-testcase",
  "function": "main (echo function - minimal work)",
  "timing": {
    "total_time_seconds": 2.456,
    "total_time_ms": 2456.78,
    "user_function": {
      "time_ms": 12.34,
      "time_seconds": 0.012,
      "percentage": 0.50
    },
    "framework_overhead": {
      "time_ms": 412.89,
      "time_seconds": 0.413,
      "percentage": 16.81
    },
    "import_time": {
      "time_ms": 2031.55,
      "time_seconds": 2.032,
      "percentage": 82.69
    },
    "sample_count": 24567,
    "unique_frames": 245
  },
  "memory": {
    "current_bytes": 45678912,
    "peak_bytes": 52341256,
    "current_mb": 43.56,
    "peak_mb": 49.91
  },
  "execution_time_seconds": 2.458,
  "file_sizes": {
    "profile_json": 123456,
    "memory_profile_json": 5678
  },
  "environment": {
    "python_version": "3.11.0",
    "platform": "linux",
    "ci": "true",
    "runner": "Linux",
    "github_run_id": "12345",
    "github_sha": "abc123",
    "branch": "main"
  }
}
```

### Key Metrics Explained

- **framework**: Framework discriminator (`uipath`, `uipath-langgraph`, or `uipath-llamaindex`)
- **timing.total_time_seconds**: Total execution time from start to finish
- **timing.user_function**: Time spent executing the user's `main()` function
- **timing.framework_overhead**: Time spent in framework code (excluding imports)
- **timing.import_time**: Time spent loading Python modules
- **memory.peak_mb**: Peak memory usage during execution
- **memory.current_mb**: Memory usage at the end of execution
- **execution_time_seconds**: Wall-clock time measured by tracemalloc

## Artifacts Generated

| File | Format | Purpose |
|------|--------|---------|
| `profile.json` | Speedscope JSON | CPU profiling data with timing information - view at [speedscope.app](https://speedscope.app) |
| `memory_profile.json` | JSON | Memory profiling data with peak/current usage and top allocations |
| `metrics.json` | JSON | Combined metrics (timing + memory) for Azure Data Explorer ingestion |

## Azure Blob Storage Setup

### 1. Create Storage Account

```bash
# Using Azure CLI
az storage account create \
  --name uipathperfmetrics \
  --resource-group uipath-performance \
  --location eastus \
  --sku Standard_LRS

# Create container
az storage container create \
  --name performance-metrics \
  --account-name uipathperfmetrics
```

### 2. Get Connection String

```bash
az storage account show-connection-string \
  --name uipathperfmetrics \
  --resource-group uipath-performance \
  --output tsv
```

### 3. Configure GitHub Secret

1. Go to repository Settings → Secrets and variables → Actions
2. Add new secret: `AZURE_STORAGE_CONNECTION_STRING`
3. Paste the connection string from step 2

### Blob Naming Convention

Metrics are uploaded with hierarchical names including the framework discriminator:

```
{framework}/{branch}/{github_run_id}/{timestamp}_metrics.json
```

Example:
```
uipath/main/12345678/20260115_103045_metrics.json
uipath-langgraph/main/12345679/20260115_110230_metrics.json
uipath-llamaindex/feature/optimize-imports/12345680/20260115_112015_metrics.json
```

This allows:
- **Comparing frameworks** (uipath vs uipath-langgraph vs uipath-llamaindex)
- Tracking metrics over time
- Comparing branches within the same framework
- Correlating with CI runs

## Running Locally

### Prerequisites

```bash
# Install dependencies
uv add py-spy azure-storage-blob

# Set environment variables
export CLIENT_ID="your-client-id"
export CLIENT_SECRET="your-client-secret"
export BASE_URL="https://cloud.uipath.com/your-org"
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."

# Optional: Set framework discriminator (defaults to "uipath")
# export FRAMEWORK="uipath"  # or "uipath-langgraph" or "uipath-llamaindex"
```

### Run Test

```bash
cd testcases/performance-testcase
bash run.sh
```

**Note**: The `FRAMEWORK` environment variable defaults to `uipath`. For testing other frameworks:
```bash
export FRAMEWORK="uipath-langgraph"
bash run.sh
```

### View Results

```bash
# View combined metrics
cat artifacts/metrics.json | jq

# View timing breakdown
cat artifacts/metrics.json | jq '.timing'

# View memory usage
cat artifacts/memory_profile.json | jq '.memory'

# Upload to speedscope.app for interactive timeline view
# Go to https://speedscope.app
# Load artifacts/profile.json
```

## CI/CD Integration

The testcase runs automatically in GitHub Actions across three environments:
- Alpha
- Staging
- Cloud (production)

Each run:
1. Profiles the agent execution
2. Collects metrics
3. Uploads to Azure Blob Storage
4. Uploads artifacts to GitHub Actions

### Workflow File

See [`.github/workflows/integration_tests.yml`](../../.github/workflows/integration_tests.yml)

## Azure Data Explorer (ADX) Ingestion

### Create ADX Table

```kql
.create table PerformanceMetrics (
    Timestamp: datetime,
    Testcase: string,
    Function: string,
    Framework: string,
    TotalTimeSeconds: real,
    UserFunctionTimeSeconds: real,
    UserFunctionPercentage: real,
    FrameworkOverheadSeconds: real,
    FrameworkOverheadPercentage: real,
    ImportTimeSeconds: real,
    ImportPercentage: real,
    SampleCount: int,
    UniqueFrames: int,
    PeakMemoryMB: real,
    CurrentMemoryMB: real,
    ExecutionTimeSeconds: real,
    ProfileSizeBytes: long,
    MemoryProfileSizeBytes: long,
    PythonVersion: string,
    Platform: string,
    CI: bool,
    RunnerOS: string,
    GitHubRunId: string,
    GitHubSHA: string,
    Branch: string
)
```

### Create Data Connection

```kql
.create table PerformanceMetrics ingestion json mapping 'PerformanceMetricsMapping'
```
```json
[
  {"column": "Timestamp", "path": "$.timestamp", "datatype": "datetime"},
  {"column": "Testcase", "path": "$.testcase", "datatype": "string"},
  {"column": "Function", "path": "$.function", "datatype": "string"},
  {"column": "Framework", "path": "$.framework", "datatype": "string"},
  {"column": "TotalTimeSeconds", "path": "$.timing.total_time_seconds", "datatype": "real"},
  {"column": "UserFunctionTimeSeconds", "path": "$.timing.user_function.time_seconds", "datatype": "real"},
  {"column": "UserFunctionPercentage", "path": "$.timing.user_function.percentage", "datatype": "real"},
  {"column": "FrameworkOverheadSeconds", "path": "$.timing.framework_overhead.time_seconds", "datatype": "real"},
  {"column": "FrameworkOverheadPercentage", "path": "$.timing.framework_overhead.percentage", "datatype": "real"},
  {"column": "ImportTimeSeconds", "path": "$.timing.import_time.time_seconds", "datatype": "real"},
  {"column": "ImportPercentage", "path": "$.timing.import_time.percentage", "datatype": "real"},
  {"column": "SampleCount", "path": "$.timing.sample_count", "datatype": "int"},
  {"column": "UniqueFrames", "path": "$.timing.unique_frames", "datatype": "int"},
  {"column": "PeakMemoryMB", "path": "$.memory.peak_mb", "datatype": "real"},
  {"column": "CurrentMemoryMB", "path": "$.memory.current_mb", "datatype": "real"},
  {"column": "ExecutionTimeSeconds", "path": "$.execution_time_seconds", "datatype": "real"},
  {"column": "ProfileSizeBytes", "path": "$.file_sizes.profile_json", "datatype": "long"},
  {"column": "MemoryProfileSizeBytes", "path": "$.file_sizes.memory_profile_json", "datatype": "long"},
  {"column": "PythonVersion", "path": "$.environment.python_version", "datatype": "string"},
  {"column": "Platform", "path": "$.environment.platform", "datatype": "string"},
  {"column": "CI", "path": "$.environment.ci", "datatype": "bool"},
  {"column": "RunnerOS", "path": "$.environment.runner", "datatype": "string"},
  {"column": "GitHubRunId", "path": "$.environment.github_run_id", "datatype": "string"},
  {"column": "GitHubSHA", "path": "$.environment.github_sha", "datatype": "string"},
  {"column": "Branch", "path": "$.environment.branch", "datatype": "string"}
]
```

### Setup Event Grid Ingestion

```bash
# Create data connection from Blob Storage to ADX
az kusto data-connection event-grid create \
  --cluster-name uipath-performance-cluster \
  --database-name PerformanceDB \
  --data-connection-name blob-ingestion \
  --resource-group uipath-performance \
  --storage-account-resource-id "/subscriptions/.../uipathperfmetrics" \
  --event-hub-resource-id "/subscriptions/.../eventhub" \
  --consumer-group '$Default' \
  --table-name PerformanceMetrics \
  --mapping-rule-name PerformanceMetricsMapping \
  --data-format json \
  --blob-storage-event-type Microsoft.Storage.BlobCreated
```

### Query Metrics in ADX

```kql
// View recent metrics for a specific framework
PerformanceMetrics
| where Timestamp > ago(7d) and Framework == "uipath"
| project Timestamp, Framework, Branch, TotalTimeSeconds, ImportPercentage, PeakMemoryMB, UserFunctionPercentage
| order by Timestamp desc

// Compare frameworks - execution time breakdown
PerformanceMetrics
| where Timestamp > ago(30d) and Branch == "main"
| summarize
    AvgTotalTime = avg(TotalTimeSeconds),
    AvgUserFunctionTime = avg(UserFunctionTimeSeconds),
    AvgFrameworkOverhead = avg(FrameworkOverheadSeconds),
    AvgImportTime = avg(ImportTimeSeconds),
    AvgPeakMemoryMB = avg(PeakMemoryMB)
  by Framework
| order by AvgTotalTime desc

// Compare branches within a framework
PerformanceMetrics
| where Timestamp > ago(30d) and Framework == "uipath"
| summarize
    AvgTotalTime = avg(TotalTimeSeconds),
    AvgImportPct = avg(ImportPercentage),
    AvgFrameworkPct = avg(FrameworkOverheadPercentage)
  by Branch
| order by AvgTotalTime desc

// Trend over time for a framework - import percentage
PerformanceMetrics
| where Branch == "main" and Framework == "uipath"
| summarize ImportPct = avg(ImportPercentage) by bin(Timestamp, 1d)
| render timechart

// Compare all three frameworks side by side
PerformanceMetrics
| where Timestamp > ago(7d) and Branch == "main"
| summarize
    AvgTotalTime = avg(TotalTimeSeconds),
    AvgUserFunctionPct = avg(UserFunctionPercentage),
    AvgFrameworkPct = avg(FrameworkOverheadPercentage),
    AvgImportPct = avg(ImportPercentage),
    AvgPeakMemoryMB = avg(PeakMemoryMB)
  by Framework
| order by AvgTotalTime desc

// Memory usage trend
PerformanceMetrics
| where Branch == "main" and Framework == "uipath"
| summarize AvgMemory = avg(PeakMemoryMB) by bin(Timestamp, 1d)
| render timechart
```

## Troubleshooting

### Metrics not uploading

1. Check `AZURE_STORAGE_CONNECTION_STRING` is set:
   ```bash
   echo $AZURE_STORAGE_CONNECTION_STRING
   ```

2. Verify storage account exists and is accessible:
   ```bash
   az storage container list \
     --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
   ```

3. Check script output for error messages

### Profile files empty or missing

1. Ensure py-spy is installed: `pip show py-spy`
2. Check process permissions (py-spy needs ptrace access on Linux)
3. Verify `uv run uipath run` executes successfully

### Timing metrics seem off

Timing metrics are extracted from speedscope profile data:
- **User function time**: Samples where stack contains `main` from testcases directory
- **Import time**: Samples where stack contains `_find_and_load` or `_load_unlocked`
- **Framework overhead**: All other samples (excluding imports and user function)

The percentages should add up to 100%. If they don't, check that the speedscope JSON is valid.

### Memory profiling failed

Memory profiling uses Python's `tracemalloc` which may fail if:
1. The subprocess can't be executed
2. Insufficient permissions
3. Python crashes during execution

Check the error output from `profile_memory.py` for details.

## Related Files

- [collect_metrics.py](collect_metrics.py) - Metrics collection script (parses speedscope and memory data)
- [profile_memory.py](profile_memory.py) - Memory profiling script using tracemalloc
- [main.py](main.py) - Minimal test function
- [run.sh](run.sh) - Test runner with profiling commands
- [../../.github/workflows/integration_tests.yml](../../.github/workflows/integration_tests.yml) - CI workflow

## Future Enhancements

- [ ] Add more granular timing breakdowns (e.g., HTTP requests, database queries)
- [ ] Track process startup time separately
- [ ] Measure network latency to UiPath services
- [ ] Compare performance across Python versions
- [ ] Add alerting for performance regressions (e.g., >10% slowdown)
- [ ] Generate performance regression reports in PRs
