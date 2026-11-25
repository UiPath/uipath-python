"""Agent frameworks that scaffold projects for `uipath new`."""

from dataclasses import dataclass

from ..middlewares import MiddlewareFunc


@dataclass(frozen=True)
class AgentFramework:
    """An agent framework installed in this environment."""

    package: str
    """Package that provides it, and the value `--agent-framework` takes."""

    scaffold: MiddlewareFunc
    """Its `new` middleware."""
