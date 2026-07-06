"""Tests for the constants source of truth and its deprecated re-export.

``uipath.platform.constants`` is the single source of truth.
``uipath.platform.common.constants`` is a deprecated shim that re-exports it
and emits a FutureWarning. These tests pin the parity invariant (so the two can
never drift — same name, different value) and the deprecation behavior.
"""

import importlib
import sys
import warnings


def _public_names(module) -> set[str]:
    return {name for name in dir(module) if not name.startswith("_")}


def _import_shim():
    """Import the deprecated shim with its FutureWarning suppressed."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return importlib.import_module("uipath.platform.common.constants")


def test_shim_reexports_canonical_with_no_drift():
    canonical = importlib.import_module("uipath.platform.constants")
    shim = _import_shim()

    canonical_names = _public_names(canonical)

    # Every canonical constant is re-exported with an identical value.
    missing = sorted(n for n in canonical_names if not hasattr(shim, n))
    assert not missing, f"shim missing constants: {missing}"

    drift = sorted(
        n for n in canonical_names if getattr(shim, n) != getattr(canonical, n)
    )
    assert not drift, f"value drift between shim and canonical for: {drift}"


def test_shim_adds_nothing_of_its_own():
    """The shim must not define constants absent from the canonical module,
    otherwise it would no longer be the single source of truth."""
    canonical = importlib.import_module("uipath.platform.constants")
    shim = _import_shim()

    extra = sorted(_public_names(shim) - _public_names(canonical))
    assert not extra, f"shim defines names not in canonical module: {extra}"


def test_shim_emits_future_warning():
    sys.modules.pop("uipath.platform.common.constants", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("uipath.platform.common.constants")

    shim_warnings = [
        w
        for w in caught
        if issubclass(w.category, FutureWarning)
        and "uipath.platform.common.constants" in str(w.message)
        and "uipath.platform.constants" in str(w.message)
    ]
    assert len(shim_warnings) == 1, (
        f"expected exactly one deprecation FutureWarning, got {len(shim_warnings)}: "
        f"{[str(w.message) for w in caught]}"
    )
