"""Structural invariants for the canonical constants module.

Exercises ``uipath.platform.constants`` (the source of truth) directly.
Asserts structural contracts, not literal values — a literal-mirror test would
just restate the module.
"""

import uipath.platform.constants as constants


def _public_constants() -> dict[str, object]:
    return {n: getattr(constants, n) for n in dir(constants) if not n.startswith("_")}


def test_all_constants_are_non_empty_strings():
    for name, value in _public_constants().items():
        assert isinstance(value, str) and value, (
            f"{name} must be a non-empty string, got {value!r}"
        )


def test_no_duplicate_header_values():
    # Two header constants mapping to the same wire name is almost certainly a bug.
    headers = [v for n, v in _public_constants().items() if n.startswith("HEADER_")]
    assert len(headers) == len(set(headers)), "duplicate header wire names detected"
