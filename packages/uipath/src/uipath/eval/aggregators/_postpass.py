"""In-process post-pass that applies aggregator config to per-datapoint results.

Two ways aggregator config reaches `compute_aggregations`:

  1. **Self-declared by the evaluator** — each result row's `details` carries
     an `aggregators` list. The harvester picks up the first occurrence per
     evaluator (config is identical across datapoints for a given evaluator
     by construction). This is how the cloud `--aggregate-only` post-pass
     works — no separate config channel.

  2. **Global CLI override** — `--aggregate-config '<json>'` provides a
     single aggregator list applied uniformly to every evaluator with
     observations. Wins over self-declared configs. Used by standalone
     `uipath eval` for ad-hoc experimentation.

Transports that call this module:

  * `apply_to_output_file(...)` — local CLI flow: read eval-out.json,
    compute, merge under `aggregations`, write back to disk.

  * The cloud `--aggregate-only` mode wraps observations + configs in a
    minimal eval-output shape and calls `compute_aggregations(None, output)`
    directly (no override), then ships the result via the reporter.

This keeps the math in one place (`compute_aggregations`); each transport
just decides where the input observations come from and where the output
goes.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from ._base import Observation
from ._config import AggregateConfig, AggregatorConfig
from ._registry import get_function

logger = logging.getLogger(__name__)


# Categorical safety gate. When observations don't look like a small,
# bounded label set, skip aggregation entirely — macro precision over 1000
# unique sentences is meaningless. The gate returns `{}` so the transport
# layers can detect "nothing to write" the same way they do for no
# observations at all.
_MAX_DISTINCT_LABELS = 20
_MAX_LABEL_LENGTH = 64
_MIN_OBSERVATIONS = 2


def compute_aggregations(
    aggregate_config_json: str | None,
    eval_output: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Run aggregators over per-datapoint observations.

    When `aggregate_config_json` is provided, it's used as a global override
    applied uniformly to every evaluator with observations (CLI ergonomic).
    When `None`, each evaluator's self-declared `aggregators` config (carried
    in the result `details`) drives its own aggregation — different evaluator
    types can declare different policies.

    Returns `{evaluatorId: {functionKey: value}}` — empty when there are
    no qualifying observations (none harvested, gate tripped, or evaluator
    declared no aggregators in self-declared mode).
    """
    observations_by_evaluator, configs_by_evaluator = _harvest(eval_output)
    if not observations_by_evaluator:
        return {}

    global_override: list[AggregatorConfig] | None = None
    if aggregate_config_json is not None:
        global_override = AggregateConfig.model_validate_json(
            aggregate_config_json
        ).aggregators

    aggregations: dict[str, dict[str, float]] = {}
    for evaluator_id, observations in observations_by_evaluator.items():
        if not _passes_categorical_gate(observations):
            logger.info(
                "Skipping aggregation for evaluator %s — observations don't"
                " look categorical (gate: <=%d distinct labels, <=%d chars).",
                evaluator_id,
                _MAX_DISTINCT_LABELS,
                _MAX_LABEL_LENGTH,
            )
            continue

        if global_override is not None:
            specs = global_override
        else:
            raw_specs = configs_by_evaluator.get(evaluator_id, [])
            if not raw_specs:
                # No self-declared config and no override — evaluator opts
                # out of aggregation. Common for non-categorical types
                # (LLM judge, trajectory) that don't emit `aggregators`.
                continue
            specs = [AggregatorConfig.model_validate(s) for s in raw_specs]

        per_evaluator: dict[str, float] = {}
        for spec in specs:
            per_evaluator[spec.output_key()] = _run_one(spec, observations)
        if per_evaluator:
            aggregations[evaluator_id] = per_evaluator

    return aggregations


def apply_to_output_file(
    aggregate_config_json: str | None,
    eval_output_path: str | Path,
) -> dict[str, dict[str, float]]:
    """Local-CLI transport: read the eval output file, compute, merge,.

    write back. Returns the same aggregations dict that was merged in.

    `aggregate_config_json` may be None — in which case self-declared
    aggregator configs from each result's `details` drive the post-pass.
    """
    path = Path(eval_output_path)
    eval_output = json.loads(path.read_text(encoding="utf-8"))

    aggregations = compute_aggregations(aggregate_config_json, eval_output)
    if not aggregations:
        logger.info(
            "No aggregable observations in %s — skipping aggregation merge.",
            path,
        )
        return aggregations

    eval_output["aggregations"] = aggregations
    path.write_text(json.dumps(eval_output, indent=2), encoding="utf-8")
    logger.info(
        "Aggregations written to %s for %d evaluator(s).",
        path,
        len(aggregations),
    )
    return aggregations


def _run_one(cfg: AggregatorConfig, observations: list[Observation]) -> float:
    func = get_function(cfg.function)
    return func.compute(cfg, observations)


def _harvest(
    eval_output: dict[str, Any],
) -> tuple[dict[str, list[Observation]], dict[str, list[dict[str, Any]]]]:
    """Walk the eval output and return per-evaluator observations and the.

    self-declared aggregator configs (first occurrence per evaluator wins).

    UiPathEvalOutput emits the per-datapoint rows under camelCase
    `evaluationSetResults` (via model_dump(by_alias=True)). The CLI writes
    this same shape to --output-file. The cloud aggregate-only mode builds
    a minimal envelope of the same shape from harvested DB rows.
    """
    obs_by_eval: dict[str, list[Observation]] = defaultdict(list)
    cfg_by_eval: dict[str, list[dict[str, Any]]] = {}

    rows = eval_output.get("evaluationSetResults") or []
    for run in rows:
        for result_row in run.get("evaluationRunResults") or []:
            evaluator = result_row.get("evaluatorName") or result_row.get("evaluatorId")
            if not evaluator:
                continue
            details = _parse_details_dict(
                (result_row.get("result") or {}).get("details")
            )
            if details is None:
                continue

            obs = _details_to_observation(details)
            if obs is not None:
                obs_by_eval[evaluator].append(obs)

            specs = details.get("aggregators")
            if specs and isinstance(specs, list) and evaluator not in cfg_by_eval:
                cfg_by_eval[evaluator] = specs

    return dict(obs_by_eval), cfg_by_eval


def _parse_details_dict(details: Any) -> dict[str, Any] | None:
    if details is None:
        return None
    if isinstance(details, str):
        try:
            parsed = json.loads(details)
        except json.JSONDecodeError:
            return None
    else:
        parsed = details
    if not isinstance(parsed, dict):
        return None
    return parsed


def _details_to_observation(details: dict[str, Any]) -> Observation | None:
    expected = details.get("expected")
    actual = details.get("actual")
    if expected is None and actual is None:
        return None
    return Observation(expected=expected, actual=actual)


def _passes_categorical_gate(observations: list[Observation]) -> bool:
    """Return True iff observations look like a small bounded categorical.

    label set. The gate keeps the panel from displaying meaningless macro
    metrics over freeform string comparisons.
    """
    if len(observations) < _MIN_OBSERVATIONS:
        return False
    distinct: set[str] = set()
    for obs in observations:
        for label in (obs.expected, obs.actual):
            if label is None:
                continue
            label_str = str(label)
            if len(label_str) > _MAX_LABEL_LENGTH:
                return False
            distinct.add(label_str)
            if len(distinct) > _MAX_DISTINCT_LABELS:
                return False
    return True
