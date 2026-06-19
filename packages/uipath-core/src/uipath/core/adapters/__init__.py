"""Generic adapter contracts for framework integrations.

This package holds only the abstract contracts — concrete adapter
implementations live in framework-specific plugin packages (e.g.
``uipath-langchain``, ``uipath-openai``) that target the framework they
integrate with. Plugin packages register their concrete adapters with
the global :class:`AdapterRegistry` via the
``uipath.governance.adapters`` entry-point group.

Public surface:

- :class:`BaseAdapter` – abstract base every adapter inherits from.
- :class:`GovernedAgentBase` – proxy base for governed agent wrappers.
- :class:`EvaluatorProtocol` – structural protocol the adapter expects
  from any policy evaluator.
- :class:`AdapterRegistry` – ordered list of adapters that resolves
  the first match for a given agent.
"""

from .base import BaseAdapter, GovernedAgentBase
from .evaluator import EvaluatorProtocol
from .registry import (
    AdapterRegistry,
    get_adapter_registry,
    reset_adapter_registry,
)

__all__ = [
    "BaseAdapter",
    "GovernedAgentBase",
    "EvaluatorProtocol",
    "AdapterRegistry",
    "get_adapter_registry",
    "reset_adapter_registry",
]
