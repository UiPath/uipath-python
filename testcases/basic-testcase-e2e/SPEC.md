# E2E Test Specification

## Overview

End-to-end tests that validate the full lifecycle of a coded agent:
1. Create folder in Orchestrator (for isolated package feed)
2. Pack agent as NuGet package
3. Publish package to folder's feed
4. Create process
5. Run job
6. Validate output
7. Cleanup folder

## Trigger

- Runs on PRs with `build:dev` label (called from `publish-dev.yml` after SDK is published)
- Manual dispatch with version override
- Only runs for testcases matching `*-e2e` pattern

## Workflow Structure

```
┌─────────────────────────────────────────────────────────────┐
│  publish-dev.yml (trigger: PR with build:dev label)         │
├─────────────────────────────────────────────────────────────┤
│  1. Build and publish SDK to TestPyPI                       │
│  2. Calculate SDK version range                             │
│  3. Call e2e_tests.yml with version range                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  e2e_tests.yml (reusable workflow)                          │
├─────────────────────────────────────────────────────────────┤
│  Inputs:                                                    │
│    - sdk_version_range: ">=2.2.21.dev1...,<2.2.21.dev1..."  │
│  Jobs:                                                      │
│    - discover-e2e-testcases                                 │
│    - e2e-tests (matrix: testcase × environment)             │
│    - summarize-e2e-results                                  │
└─────────────────────────────────────────────────────────────┘
```

**Files:**
- `.github/workflows/publish-dev.yml` - Publishes SDK, then calls E2E tests
- `.github/workflows/e2e_tests.yml` - Reusable workflow with E2E logic

## SDK Version Strategy

Uses deterministic version range based on PR number to pick up dev builds from TestPyPI.

**Version format** (from `publish-dev.yml`):
```
{base_version}.dev1{PR_5digits}{RUN_4digits}
```

**Example**: PR #123, run #1 → `2.2.21.dev1001230001`

**Range for PR #123**:
```
>=2.2.21.dev1001230000,<2.2.21.dev1001240000
```

This ensures E2E tests use the SDK version from the same PR.

## Folder Strategy

Each test run creates a temporary folder in Orchestrator **before** publishing:
```
E2E_{GITHUB_RUN_ID}_{TIMESTAMP}
```

The folder must exist before `uipath publish` so packages upload to the folder's feed.

Folder is deleted after test completion (success or failure).

## Package Versioning

Agent package uses timestamp-based version:
```
0.0.1.{YYYYMMDDHHMMSS}
```

This ensures unique versions for each run without conflicts.

## Environment Matrix

Tests run across environments:
- `alpha`
- `cloud`
- `staging`

Each environment uses corresponding secrets:
- `{ENV}_TEST_CLIENT_ID`
- `{ENV}_TEST_CLIENT_SECRET`
- `{ENV}_BASE_URL`

## Test Flow

```
┌─────────────────────────────────────────────────────────────┐
│  e2e_tests.yml (reusable workflow)                          │
├─────────────────────────────────────────────────────────────┤
│  Input: sdk_version_range                                   │
│  1. Discover *-e2e testcases                                │
│  2. For each testcase × environment:                        │
│     a. Update pyproject.toml with SDK version range         │
│     b. Run run.sh                                           │
│     c. Run validate_output.sh                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  run.sh                                                     │
├─────────────────────────────────────────────────────────────┤
│  1. Generate package version (timestamp)                    │
│  2. Update pyproject.toml with version                      │
│  3. uv sync                                                 │
│  4. uipath auth (generates .env with tokens)                │
│  5. python src/orchestrator.py setup    ← Create folder     │
│  6. uipath init                                             │
│  7. uipath pack --nolock                                    │
│  8. uipath publish --folder $FOLDER_NAME                    │
│  9. python src/orchestrator.py run      ← Run job & poll    │
│  10. python src/orchestrator.py cleanup ← Delete folder     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  orchestrator.py setup                                      │
├─────────────────────────────────────────────────────────────┤
│  1. Load tokens from .env                                   │
│  2. Create temporary folder                                 │
│  3. Export FOLDER_NAME and FOLDER_ID to .env                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  orchestrator.py run                                        │
├─────────────────────────────────────────────────────────────┤
│  1. Load tokens and folder info from .env                   │
│  2. Create process in folder                                │
│  3. Start job with input args                               │
│  4. Poll until job completes                                │
│  5. Save job output to __uipath/output.json                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  orchestrator.py cleanup                                    │
├─────────────────────────────────────────────────────────────┤
│  1. Load tokens and folder info from .env                   │
│  2. Delete folder (removes packages, processes, jobs)       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  assert.py (via validate_output.sh)                         │
├─────────────────────────────────────────────────────────────┤
│  1. Check .uipath/*.nupkg exists                            │
│  2. Check __uipath/output.json exists                       │
│  3. Assert job status == "successful"                       │
│  4. Assert job state == "Successful"                        │
│  5. Validate output fields                                  │
└─────────────────────────────────────────────────────────────┘
```

## Orchestrator API Calls

### Setup Phase
```
POST /odata/Folders
  → Create folder with DisplayName, ProvisionType=Manual
  → Returns folder ID
```

### Publish Phase (via uipath CLI)
```
uipath publish --folder <folder_name>
  → Uploads .nupkg to folder's package feed
```

### Run Phase
```
GET /odata/Packages?$filter=Id eq '{name}'
  → Get package version

POST /odata/Processes
  → Create process with PackageIdentifier, PackageVersion, EntryPointPath

POST /odata/Jobs/UiPath.Server.Configuration.OData.StartJobs
  → Start job with ReleaseKey, InputArguments

GET /odata/Jobs({id})
  → Poll job state until terminal (Successful, Faulted, etc.)
```

### Cleanup Phase
```
DELETE /odata/Folders({id})
  → Deletes folder and all contents
```

## Files

| File | Purpose |
|------|---------|
| `.github/workflows/publish-dev.yml` | Publishes SDK, then calls E2E tests |
| `.github/workflows/e2e_tests.yml` | Reusable E2E workflow (called by publish-dev) |
| `testcases/basic-testcase-e2e/run.sh` | Test runner script |
| `testcases/basic-testcase-e2e/src/orchestrator.py` | Orchestrator client (setup/run/cleanup) |
| `testcases/basic-testcase-e2e/src/assert.py` | Output validation |
| `testcases/basic-testcase-e2e/main.py` | Agent entry point |
| `testcases/basic-testcase-e2e/pyproject.toml` | Package config |
| `testcases/common/validate_output.sh` | Shared validation runner |

## Environment Variables

**From CI** (secrets):
- `CLIENT_ID` - OAuth client ID
- `CLIENT_SECRET` - OAuth client secret
- `BASE_URL` - Environment base URL
- `GITHUB_RUN_ID` - Unique run identifier

**Generated by `uipath auth`** (.env):
- `UIPATH_ACCESS_TOKEN` - Bearer token
- `UIPATH_URL` - Full URL with account/tenant

**Generated by `orchestrator.py setup`** (.env):
- `E2E_FOLDER_NAME` - Created folder name
- `E2E_FOLDER_ID` - Created folder ID

## Input/Output

**Agent Input** (job start):
```json
{
  "message": "Hello from E2E test",
  "repeat": 3,
  "prefix": "E2E"
}
```

**Expected Agent Output** (`main.py` → EchoOut):
```json
{
  "message": "E2E: Hello from E2E test\nE2E: Hello from E2E test\nE2E: Hello from E2E test"
}
```

**Job Output File** (`__uipath/output.json`):
```json
{
  "status": "successful",
  "job_id": 12345,
  "job_key": "...",
  "state": "Successful",
  "info": null,
  "output": {
    "message": "E2E: Hello from E2E test\n..."
  }
}
```

## Dependencies

**pyproject.toml**:
```toml
[project]
dependencies = [
  "uipath>=2.2.0",       # SDK (version updated by workflow)
  "httpx>=0.27.0",       # HTTP client for Orchestrator API
  "python-dotenv>=1.0.0" # Load .env tokens
]

[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
explicit = true

[tool.uv.sources]
uipath = { index = "testpypi" }  # Added by workflow for dev versions
```

## Error Handling

- Cleanup runs even on failure (trap in run.sh)
- On failure, `orchestrator.py run` saves error to `__uipath/output.json`
- `assert.py` provides clear failure messages
- Folder cleanup is idempotent (ignores "not found" errors)

## Future Improvements

- [ ] Add retry logic for transient failures
- [ ] Support custom input args per testcase
- [ ] Add trace validation using `common/trace_assert.py`
- [ ] Parallel job execution for performance
- [ ] Skip cleanup flag for debugging (`E2E_SKIP_CLEANUP=1`)
