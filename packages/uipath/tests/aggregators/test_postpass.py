"""Tests for the aggregator post-pass: compute_aggregations + apply_to_output_file."""

from __future__ import annotations

import json
import math
from pathlib import Path

from uipath.eval.aggregators import apply_to_output_file, compute_aggregations


def _config_json(aggregators: list[dict]) -> str:
    return json.dumps({"aggregators": aggregators})


def _eval_out(rows: list[tuple[str, str, str]]) -> dict:
    """rows = [(evaluatorName, expected, actual), ...]

    Field key matches what UiPathEvalOutput.model_dump(by_alias=True) emits
    (and what --output-file persists) so this fixture exercises the same
    shape the real harvester sees in production.
    """
    return {
        "evaluationSetResults": [
            {
                "evaluationName": f"dp-{i}",
                "evaluationRunResults": [
                    {
                        "evaluatorName": ev,
                        "result": {
                            "details": json.dumps({"expected": exp, "actual": act})
                        },
                    }
                ],
            }
            for i, (ev, exp, act) in enumerate(rows)
        ]
    }


# ---------------------------------------------------------------------------
# compute_aggregations — pure function, used by the cloud reporter
# ---------------------------------------------------------------------------


class TestComputeAggregations:
    def test_hca_shape(self) -> None:
        cfg = _config_json(
            [
                {"function": "precision", "classes": ["book", "cancel"]},
                {"function": "recall", "classes": ["book", "cancel"]},
                {"function": "fscore", "classes": ["book", "cancel"], "beta": 1.0},
            ]
        )
        eval_out = _eval_out(
            [
                ("ExactMatch", "book", "book"),
                ("ExactMatch", "book", "book"),
                ("ExactMatch", "book", "cancel"),
                ("ExactMatch", "book", "cancel"),
                ("ExactMatch", "book", "cancel"),
                ("ExactMatch", "book", "cancel"),
            ]
        )
        agg = compute_aggregations(cfg, eval_out)
        assert set(agg) == {"ExactMatch"}
        m = agg["ExactMatch"]
        assert math.isclose(m["precision"], 0.5, abs_tol=1e-9)
        assert math.isclose(m["recall"], 1 / 6, abs_tol=1e-9)
        assert math.isclose(m["fscore"], 0.25, abs_tol=1e-9)

    def test_multi_evaluator(self) -> None:
        cfg = _config_json([{"function": "precision", "classes": ["a", "b"]}])
        eval_out = _eval_out(
            [
                ("EvalA", "a", "a"),
                ("EvalA", "b", "b"),
                ("EvalB", "a", "b"),
                ("EvalB", "b", "a"),
            ]
        )
        agg = compute_aggregations(cfg, eval_out)
        assert set(agg) == {"EvalA", "EvalB"}
        assert agg["EvalA"]["precision"] == 1.0
        assert agg["EvalB"]["precision"] == 0.0

    def test_no_observations_returns_empty(self) -> None:
        cfg = _config_json([{"function": "precision", "classes": ["a"]}])
        eval_out = {
            "evaluationSetResults": [
                {
                    "evaluationName": "x",
                    "evaluationRunResults": [
                        {"evaluatorName": "Trajectory", "result": {"score": 1}}
                    ],
                }
            ]
        }
        assert compute_aggregations(cfg, eval_out) == {}

    def test_duplicate_function_disambiguated(self) -> None:
        cfg = _config_json(
            [
                {"function": "fscore", "classes": ["a", "b"], "beta": 1.0},
                {"function": "fscore", "classes": ["a", "b"], "beta": 2.0},
            ]
        )
        eval_out = _eval_out([("ExactMatch", "a", "a"), ("ExactMatch", "b", "a")])
        agg = compute_aggregations(cfg, eval_out)
        assert "fscore" in agg["ExactMatch"]
        assert "fscore@beta=2.0" in agg["ExactMatch"]


# ---------------------------------------------------------------------------
# apply_to_output_file — local-CLI transport wrapper
# ---------------------------------------------------------------------------


class TestApplyToOutputFile:
    def test_writes_aggregations_back_into_file(self, tmp_path: Path) -> None:
        cfg = _config_json(
            [
                {"function": "precision", "classes": ["book", "cancel"]},
                {"function": "recall", "classes": ["book", "cancel"]},
                {"function": "fscore", "classes": ["book", "cancel"], "beta": 1.0},
            ]
        )
        out = tmp_path / "eval-out.json"
        out.write_text(
            json.dumps(
                _eval_out(
                    [
                        ("ExactMatch", "book", "book"),
                        ("ExactMatch", "book", "book"),
                        ("ExactMatch", "book", "cancel"),
                        ("ExactMatch", "book", "cancel"),
                        ("ExactMatch", "book", "cancel"),
                        ("ExactMatch", "book", "cancel"),
                    ]
                )
            )
        )
        result = apply_to_output_file(cfg, out)

        merged = json.loads(out.read_text())
        assert "aggregations" in merged
        assert merged["aggregations"]["ExactMatch"]["precision"] == result["ExactMatch"]["precision"]
        assert math.isclose(merged["aggregations"]["ExactMatch"]["fscore"], 0.25, abs_tol=1e-9)

    def test_no_observations_silently_skips_file_write(self, tmp_path: Path) -> None:
        cfg = _config_json([{"function": "precision", "classes": ["a"]}])
        out = tmp_path / "eval-out.json"
        out.write_text(
            json.dumps(
                {
                    "evaluationSetResults": [
                        {
                            "evaluationName": "x",
                            "evaluationRunResults": [
                                {"evaluatorName": "Trajectory", "result": {"score": 1}}
                            ],
                        }
                    ]
                }
            )
        )
        result = apply_to_output_file(cfg, out)
        assert result == {}
        # No aggregations key added when nothing to compute.
        assert "aggregations" not in json.loads(out.read_text())

    def test_inferred_classes(self, tmp_path: Path) -> None:
        cfg = _config_json([{"function": "precision"}])  # no classes — auto-infer
        out = tmp_path / "eval-out.json"
        out.write_text(
            json.dumps(
                _eval_out([("ExactMatch", "yes", "yes"), ("ExactMatch", "no", "no")])
            )
        )
        apply_to_output_file(cfg, out)
        assert json.loads(out.read_text())["aggregations"]["ExactMatch"]["precision"] == 1.0
