"""CLI-side governance helpers.

Host-only glue that turns provider responses into inputs the runtime
consumes. Owns the YAML → :class:`PolicyIndex` compiler (the runtime
layer stays format-agnostic and only accepts a compiled index).

Public helpers:

- :func:`build_policy_index_from_yaml` — parse a YAML policy pack (as
  returned by :meth:`GovernancePolicyProvider.get_policy_async`) into
  a :class:`uipath.runtime.governance.native.PolicyIndex`.
"""

from .yaml_index import build_policy_index_from_yaml

__all__ = ["build_policy_index_from_yaml"]
