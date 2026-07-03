import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "statement",
    [
        "from uipath.platform.identity import IdentityService",
        "from uipath.platform.external_applications import ExternalApplicationService",
        "from uipath.platform.common import TokenData",
        "from uipath.platform import UiPath",
        "import uipath.platform.constants",
    ],
)
def test_import_entry_points_are_cycle_free(statement: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", statement], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
