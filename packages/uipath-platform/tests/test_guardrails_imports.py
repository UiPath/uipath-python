import subprocess
import sys


def test_guardrails_model_compatibility_export() -> None:
    from uipath.platform.guardrails import NumberParameterValue
    from uipath.platform.guardrails.guardrails import (
        NumberParameterValue as CompatibilityNumberParameterValue,
    )

    assert CompatibilityNumberParameterValue is NumberParameterValue


def test_internal_guardrails_service_import_does_not_load_public_package() -> None:
    script = """
import sys
import uipath.platform._guardrails_service

assert "uipath.platform.guardrails" not in sys.modules
assert "uipath.platform.guardrails.decorators" not in sys.modules
"""

    subprocess.run([sys.executable, "-c", script], check=True)
