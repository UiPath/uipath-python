"""Tests for case-insensitive eval id handling (PC-4688).

Eval sets exported by some tools emit uppercase GUID ids. The backend
canonicalizes GUIDs to lowercase, so any case-sensitive correlation on the
runtime side (selection, span/cache keying) silently fails to match. These
tests pin the fix: GUID ids are normalized to lowercase at ingestion and
selection is casing-agnostic.
"""

from typing import Any

from uipath.eval.models.evaluation_set import (
    EvaluationItem,
    EvaluationSet,
    LegacyEvaluationItem,
)

UPPER_GUID = "B063907C-76AB-4B0A-88A3-EC0FB40698B8"
LOWER_GUID = "b063907c-76ab-4b0a-88a3-ec0fb40698b8"


def _make_item(eval_id: str) -> dict[str, Any]:
    return {
        "id": eval_id,
        "name": "item",
        "inputs": {"x": 1},
        "evaluationCriterias": {},
    }


def test_evaluation_item_normalizes_uppercase_guid_id():
    """An uppercase GUID id is stored in canonical lowercase form."""
    item = EvaluationItem.model_validate(_make_item(UPPER_GUID))
    assert item.id == LOWER_GUID


def test_legacy_evaluation_item_normalizes_uppercase_guid_id():
    """LegacyEvaluationItem also normalizes uppercase GUID ids."""
    item = LegacyEvaluationItem.model_validate(
        {
            "id": UPPER_GUID,
            "name": "item",
            "inputs": {"x": 1},
            "expectedOutput": {},
            "evalSetId": "set-1",
            "createdAt": "2025-01-01T00:00:00.000Z",
            "updatedAt": "2025-01-01T00:00:00.000Z",
        }
    )
    assert item.id == LOWER_GUID


def test_non_guid_id_is_left_unchanged():
    """Non-GUID ids (e.g. slugs) keep their original value and casing."""
    item = EvaluationItem.model_validate(_make_item("Test-Eval-1"))
    assert item.id == "Test-Eval-1"


def test_extract_selected_evals_matches_regardless_of_caller_casing():
    """Selecting by an uppercase GUID matches a normalized stored id."""
    eval_set = EvaluationSet.model_validate(
        {
            "id": "set-1",
            "name": "set",
            "evaluations": [_make_item(LOWER_GUID), _make_item("other-id")],
        }
    )
    eval_set.extract_selected_evals([UPPER_GUID])
    assert [e.id for e in eval_set.evaluations] == [LOWER_GUID]
