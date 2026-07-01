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
- :data:`MODEL_TEXT_CAP` / :func:`join_within_cap` / :func:`stringify` /
  :func:`coerce_args` – shared payload helpers so every plugin caps and
  coerces the blob it hands the evaluator identically.
"""

from .evaluator import EvaluatorProtocol
from .payload import MODEL_TEXT_CAP, coerce_args, join_within_cap, stringify

__all__ = [
    "EvaluatorProtocol",
    "MODEL_TEXT_CAP",
    "coerce_args",
    "join_within_cap",
    "stringify",
]
