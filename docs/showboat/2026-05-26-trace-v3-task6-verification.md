# Trace V3 Migration — Task 6: Final Lint, Type-Check & Integration Verification

*2026-05-26T19:45:13Z by Showboat 0.6.1*
<!-- showboat-id: 5d2c3a50-3854-4e03-ab87-5c0fd86004f7 -->

Ruff lint check on uipath-platform — verifies no style violations after StrEnum migration.

```bash
cd /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath-platform && uv run ruff check . && uv run ruff format --check . && echo 'uipath-platform lint: PASSED' 2>&1
```

```output
All checks passed!
187 files already formatted
uipath-platform lint: PASSED
```

Ruff lint check on uipath (main package) — includes tracing files updated in Tasks 4–5.

```bash
cd /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath && uv run ruff check . && uv run ruff format --check . && echo 'uipath lint: PASSED' 2>&1
```

```output
All checks passed!
290 files already formatted
uipath lint: PASSED
```

mypy type check on uipath-platform — verifies StrEnum field types in UiPathSpan and otel_span_to_uipath_span().

```bash
cd /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath-platform && uv run mypy src tests 2>&1 | tail -5
```

```output
Success: no issues found in 187 source files
```

mypy type check on uipath — verifies SpanStatus import refactor in _otel_exporters.py and _live_tracking_processor.py.

```bash
cd /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath && uv run mypy src tests 2>&1 | tail -5
```

```output
Success: no issues found in 286 source files
```

Full test suite for uipath-platform — 1212 tests covering span utils, enum serialization, and all service tests.

```bash
cd /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath-platform && uv run pytest --tb=short -q 2>&1 | tail -10
```

```output
--------------------------------------------------------------------------------------------------------------
TOTAL                                                                            9187   1091  88.12%
=========================== short test summary info ============================
SKIPPED [1] tests/services/test_llm_integration.py:59: Failed to get access token. Check your credentials.
SKIPPED [1] tests/services/test_llm_integration.py:77: Failed to get access token. Check your credentials.
SKIPPED [1] tests/services/test_llm_integration.py:104: Failed to get access token. Check your credentials.
SKIPPED [1] tests/services/test_uipath_llm_integration.py:42: Failed to get access token. Check your credentials.
SKIPPED [1] tests/services/test_uipath_llm_integration.py:66: Failed to get access token. Check your credentials.
SKIPPED [1] tests/services/test_uipath_llm_integration.py:121: Failed to get access token. Check your credentials.
SKIPPED [1] tests/services/test_uipath_llm_integration.py:177: Failed to get access token. Check your credentials.
```

Full test suite for uipath (main package) — includes TestV3EndToEnd integration test verifying string enums reach v3 URL.

```bash
cd /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath && uv run pytest --no-cov -q 2>&1 | tail -3
```

```output
    model_fields = getattr(data[0], "model_fields", None)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

Integration test confirming the v3 contract: string enums in payload, v3/spans URL.

```bash
uv run pytest tests/tracing/test_otel_exporters.py::TestV3EndToEnd -v --no-cov 2>&1
```

```output
============================= test session starts ==============================
platform darwin -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/sakshar.thakkar/repos/u-trace-v3-migration/packages/uipath
configfile: pyproject.toml
plugins: anyio-4.12.1, mock-3.15.1, httpx-0.36.0, timeout-2.4.0, trio-0.8.0, asyncio-1.3.0, cov-7.0.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 1 item

tests/tracing/test_otel_exporters.py .                                   [100%]

============================== 1 passed in 0.02s ===============================
```
