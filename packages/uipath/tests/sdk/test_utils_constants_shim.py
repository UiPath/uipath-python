"""Regression tests for the uipath._utils.constants deprecation shim.

The shim re-exports from uipath.platform.constants (the source of truth) and emits
a FutureWarning so external consumers can migrate. Internal callsites are
already on the canonical path; these tests pin the shim's behavior so it keeps
working for downstream code.
"""

import importlib
import sys
import warnings


def _reload_shim():
    """Force a fresh import of the shim so FutureWarning re-fires."""
    sys.modules.pop("uipath._utils.constants", None)
    return importlib.import_module("uipath._utils.constants")


def test_shim_emits_future_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _reload_shim()

    shim_warnings = [
        w
        for w in caught
        if issubclass(w.category, FutureWarning)
        and "uipath._utils.constants" in str(w.message)
        and "uipath.platform.constants" in str(w.message)
    ]
    assert len(shim_warnings) == 1, (
        f"expected exactly one shim FutureWarning, got {len(shim_warnings)}: "
        f"{[str(w.message) for w in caught]}"
    )


def test_shim_re_exports_canonical_symbols():
    shim = _reload_shim()
    canonical = importlib.import_module("uipath.platform.constants")

    # Sample a representative set: env vars, headers, mixed-case symbols,
    # file constants, data-source magic strings.
    sample = [
        "DOTENV_FILE",
        "ENV_BASE_URL",
        "ENV_TENANT_ID",
        "HEADER_INTERNAL_TENANT_ID",
        "HEADER_INTERNAL_ACCOUNT_ID",
        "HEADER_USER_AGENT",
        "LLMV3Mini_REQUEST",
        "LLMV4_REQUEST",
        "NativeV1_REQUEST",
        "COMMUNITY_agents_SUFFIX",
        "PYTHON_CONFIGURATION_FILE",
        "ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE_REQUEST",
    ]
    for name in sample:
        assert hasattr(shim, name), f"shim missing {name}"
        assert hasattr(canonical, name), f"canonical missing {name}"
        assert getattr(shim, name) == getattr(canonical, name), (
            f"value drift for {name}: shim={getattr(shim, name)!r} "
            f"canonical={getattr(canonical, name)!r}"
        )


def test_shim_does_not_leak_warnings_module_via_star_import():
    """The shim binds `warnings` under a private alias to keep it out of
    `from uipath._utils.constants import *`."""
    _reload_shim()
    ns: dict[str, object] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec("from uipath._utils.constants import *", ns)
    assert "warnings" not in ns
    assert "_warnings" not in ns
