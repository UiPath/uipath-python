"""Generic adapter contracts for framework integrations.

This package holds only the abstract contracts — concrete adapter
implementations live in framework-specific plugin packages (e.g.
``uipath-langchain``, ``uipath-openai``). A framework plugin is the one
that knows its own native wiring seam (callback handler list, hook
registry, …) and installs governance there directly; uipath-core only
defines the protocol an evaluator must satisfy.

Public surface:

- :class:`EvaluatorProtocol` – structural protocol the framework
  plugin expects from any policy evaluator.
"""

from .evaluator import EvaluatorProtocol

__all__ = [
    "EvaluatorProtocol",
]
