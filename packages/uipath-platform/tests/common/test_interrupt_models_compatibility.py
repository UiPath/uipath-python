import importlib
import subprocess
import sys
import warnings

# TODO: Remove these tests with the compatibility bridge in the next breaking-change release.
INTERRUPT_MODEL_NAMES = (
    "CreateBatchTransform",
    "CreateDeepRag",
    "CreateDeepRagRaw",
    "CreateEphemeralIndex",
    "CreateEphemeralIndexRaw",
    "CreateEscalation",
    "CreateTask",
    "DocumentExtraction",
    "DocumentExtractionValidation",
    "InvokeProcess",
    "InvokeProcessRaw",
    "InvokeSystemAgent",
    "WaitBatchTransform",
    "WaitDeepRag",
    "WaitDeepRagRaw",
    "WaitDocumentExtraction",
    "WaitDocumentExtractionValidation",
    "WaitEphemeralIndex",
    "WaitEphemeralIndexRaw",
    "WaitEscalation",
    "WaitIntegrationEvent",
    "WaitJob",
    "WaitJobRaw",
    "WaitSystemAgent",
    "WaitTask",
    "WaitUntil",
)


def _run_python(source: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_compatibility_exports_are_canonical_objects():
    canonical = importlib.import_module(
        "uipath.platform.resume_triggers.interrupt_models"
    )
    common = importlib.import_module("uipath.platform.common")
    legacy = importlib.import_module("uipath.platform.common.interrupt_models")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for name in INTERRUPT_MODEL_NAMES:
            assert getattr(legacy, name) is getattr(canonical, name)
            assert getattr(common, name) is getattr(canonical, name)

    assert set(INTERRUPT_MODEL_NAMES) == set(legacy.__all__)
    assert set(INTERRUPT_MODEL_NAMES) <= set(common.__all__)


def test_importing_common_does_not_load_resume_triggers_or_warn():
    _run_python(
        """
import sys
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import uipath.platform.common

assert "uipath.platform.resume_triggers" not in sys.modules
assert "uipath.platform.resume_triggers.interrupt_models" not in sys.modules
assert not [item for item in caught if issubclass(item.category, DeprecationWarning)]
"""
    )


def test_legacy_first_import_is_cycle_safe_and_warns():
    _run_python(
        """
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    from uipath.platform.common.interrupt_models import WaitUntil as legacy_direct
    from uipath.platform.common import WaitUntil as legacy_root
    from uipath.platform.resume_triggers import WaitUntil as canonical

assert canonical is legacy_root is legacy_direct
compatibility_warnings = [
    item
    for item in caught
    if issubclass(item.category, DeprecationWarning)
    and "uipath.platform.resume_triggers" in str(item.message)
]
assert compatibility_warnings
"""
    )
