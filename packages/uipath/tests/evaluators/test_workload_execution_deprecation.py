"""Tests for the ``AgentExecution`` -> ``WorkloadExecution`` deprecation shim.

The old name keeps working (re-exported from both ``uipath.eval.models`` and
``uipath.eval.models.models``) but must emit a ``DeprecationWarning`` and resolve
to ``WorkloadExecution``. Accessing any other unknown attribute must still raise
``AttributeError``.
"""

import importlib

import pytest

from uipath.eval.models import WorkloadExecution


@pytest.mark.parametrize(
    "module_path",
    ["uipath.eval.models", "uipath.eval.models.models"],
)
def test_agent_execution_alias_warns_and_resolves(module_path: str) -> None:
    """Accessing the legacy ``AgentExecution`` name warns and returns the new class."""
    module = importlib.import_module(module_path)

    with pytest.warns(DeprecationWarning, match="AgentExecution is deprecated"):
        legacy = module.AgentExecution

    assert legacy is WorkloadExecution


@pytest.mark.parametrize(
    "module_path",
    ["uipath.eval.models", "uipath.eval.models.models"],
)
def test_unknown_attribute_raises(module_path: str) -> None:
    """Unknown attributes still raise ``AttributeError`` via the module ``__getattr__``."""
    module = importlib.import_module(module_path)

    with pytest.raises(AttributeError, match="does_not_exist"):
        _ = module.does_not_exist
