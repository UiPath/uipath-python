from typing import TYPE_CHECKING

from ._endpoint import Endpoint
from ._logs import setup_logging
from ._request_override import header_folder
from ._request_spec import RequestSpec
from ._url import UiPathUrl
from ._user_agent import header_user_agent, user_agent_value
from .validation import validate_pagination_params

if TYPE_CHECKING:
    from uipath.platform.common import resource_override

__all__ = [
    "Endpoint",
    "setup_logging",
    "RequestSpec",
    "header_folder",
    "resource_override",
    "header_user_agent",
    "user_agent_value",
    "UiPathUrl",
    "validate_pagination_params",
]


# Re-exports too expensive to import with this package, and the module each one
# comes from. ``uipath.platform.common`` re-exports 71 names eagerly, so resolving
# ``resource_override`` pulls in httpx, pydantic, opentelemetry and the
# orchestrator services -- 576 modules. Importing it here put all of that on every
# ``uipath`` CLI invocation, ``--version`` included. It stays importable from this
# module because uipath-langchain imports it here.
_EXPORTS = {"resource_override": "uipath.platform.common"}


def __getattr__(name: str):
    """Import the module defining `name` the first time it is accessed."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    import importlib

    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    return sorted(__all__)
