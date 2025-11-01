"""Live integration tests for UiPath SDK.

This package contains live integration tests that run against real UiPath Platform
APIs. These tests require valid credentials and are excluded from regular test runs
by default.

Prerequisites:
    - Valid UiPath credentials in .env or environment variables
    - UIPATH_URL, UIPATH_ACCESS_TOKEN configured
    - UIPATH_FOLDER_PATH (optional, defaults to 'Shared')

Usage:
    # Run all live tests (explicitly include them)
    pytest -m live -v tests/live

    # Run specific service tests
    pytest -m live_buckets -v tests/live

    # Live tests are EXCLUDED by default
    pytest -v  # Will NOT run live tests
"""
