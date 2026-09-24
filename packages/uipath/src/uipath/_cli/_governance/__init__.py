"""CLI-side governance helpers.

Host-only glue that turns provider responses into inputs the runtime
consumes. Owns the YAML → `PolicyIndex` compiler (the runtime
layer stays format-agnostic and only accepts a compiled index).

Public helpers:

- `build_policy_index_from_yaml()` — parse a YAML policy pack (as
  returned by `GovernancePolicyProvider.get_policy_async()`) into
  a `uipath.runtime.governance.native.PolicyIndex`.
"""

from .yaml_index import build_policy_index_from_yaml

__all__ = ["build_policy_index_from_yaml"]
