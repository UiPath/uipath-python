"""Runnable proof that the dataset-level evaluators work on realistic data.

Five scenarios exercise the framework end-to-end at the SDK layer (no
worker, no backend). Each prints the headline score plus a confusion
matrix table, so the math is inspectable rather than a passing-test
binary signal.

Run::

    cd packages/uipath
    uv run python examples/dataset_evaluators_demo.py
"""

from __future__ import annotations

import json
from typing import Iterable

from uipath.eval.evaluators._aggregator_specs import (
    FScoreAggregatorSpec,
    PrecisionAggregatorSpec,
    RecallAggregatorSpec,
)
from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification
from uipath.eval.evaluators.classification_dataset_evaluators import (
    ClassificationDetails,
)
from uipath.eval.evaluators.dataset_evaluator_factory import build_dataset_evaluator
from uipath.eval.models.models import EvaluationResultDto, NumericEvaluationResult

# ─── helpers ──────────────────────────────────────────────────────────────────


def make_result(expected: str, actual: str) -> EvaluationResultDto:
    """Build a single per-datapoint EvaluationResultDto.

    Models what an upstream classification evaluator would produce after running
    on one datapoint: score is 1.0 if the labels match, 0.0 otherwise, with the
    expected/actual labels carried in the justification.
    """
    score = 1.0 if expected.lower() == actual.lower() else 0.0
    justification = BaseEvaluatorJustification(expected=expected, actual=actual)
    return EvaluationResultDto(score=score, details=justification.model_dump())


def materialize_pairs(pairs: Iterable[tuple[str, str]]) -> list[EvaluationResultDto]:
    """Build a list of EvaluationResultDto from (expected, actual) pairs."""
    return [make_result(e, a) for e, a in pairs]


def print_header(title: str) -> None:
    """Print a section header banner."""
    print()
    print("═" * 78)
    print(f" {title}")
    print("═" * 78)


def print_confusion(details: ClassificationDetails) -> None:
    """Pretty-print the confusion matrix as a table."""
    classes = details.classes
    cell_width = max(7, max(len(c) for c in classes) + 1)
    header = (
        " " * cell_width
        + " │ "
        + " │ ".join(c.center(cell_width) for c in classes)
        + " │  ← expected"
    )
    print(header)
    print("─" * len(header))
    for predicted_idx, predicted_label in enumerate(classes):
        row_cells = [
            str(details.confusion_matrix[predicted_idx][expected_idx]).rjust(cell_width)
            for expected_idx in range(len(classes))
        ]
        print(predicted_label.ljust(cell_width) + " │ " + " │ ".join(row_cells) + " │")
    print(" " * cell_width + "↑ predicted")


def print_per_class(details: ClassificationDetails) -> None:
    """One-row-per-class table of TP/TN/FP/FN + the metric."""
    label_w = max(len("class"), max(len(c) for c in details.classes))
    metric = details.metric
    header = f"  {'class'.ljust(label_w)}  │  TP  TN  FP  FN  support  {metric}"
    print(header)
    print("  " + "─" * (len(header) - 2))
    for cls, m in details.per_class.items():
        print(
            f"  {cls.ljust(label_w)}  │  "
            f"{m.tp:>2}  {m.tn:>2}  {m.fp:>2}  {m.fn:>2}  {m.support:>7}  "
            f"{m.value:.3f}"
        )


def report(
    title: str,
    result: NumericEvaluationResult,
    *,
    show_json_tail: bool = False,
) -> None:
    """Render one scenario's result block."""
    print_header(title)
    assert isinstance(result.details, ClassificationDetails)
    d = result.details
    print(
        f"  metric = {d.metric}   average = {d.average}   "
        f"score (headline) = {result.score:.4f}"
    )
    print(
        f"  micro = {d.micro:.4f}   macro = {d.macro:.4f}   "
        f"scored = {d.n_scored}/{d.n_total}   skipped = {d.n_skipped}"
    )
    print()
    print_confusion(d)
    print()
    print_per_class(d)
    if show_json_tail:
        print()
        print("  ── wire JSON (matches frontend zod schema) ──")
        payload = d.model_dump(by_alias=True)
        print(
            "  "
            + json.dumps(
                {k: payload[k] for k in ("metric", "average", "micro", "macro")},
                indent=2,
            ).replace("\n", "\n  ")
        )


# ─── scenarios ────────────────────────────────────────────────────────────────


def scenario_1_balanced_three_class() -> None:
    """Intent recognition over book/cancel/reschedule. Every class gets 2 right, 1 wrong."""
    pairs = [
        ("book", "book"),
        ("book", "book"),
        ("book", "cancel"),
        ("cancel", "cancel"),
        ("cancel", "cancel"),
        ("cancel", "reschedule"),
        ("reschedule", "reschedule"),
        ("reschedule", "reschedule"),
        ("reschedule", "book"),
    ]
    spec = PrecisionAggregatorSpec(
        classes=["book", "cancel", "reschedule"], averaging="macro"
    )
    evaluator = build_dataset_evaluator(spec, source_evaluator="intent_match")
    report(
        "Scenario 1 — Balanced 3-class (intent recognition)\n"
        "  Each class: 2 TP, 1 FP, 1 FN. Symmetric setup → macro = micro = 2/3.",
        evaluator.evaluate(materialize_pairs(pairs)),
        show_json_tail=True,
    )


def scenario_2_imbalanced_two_class() -> None:
    """Rare-positive case — why macro vs micro matters."""
    pairs: list[tuple[str, str]] = []
    pairs += [("negative", "negative")] * 13
    pairs += [("negative", "positive")] * 3
    pairs += [("positive", "positive")] * 2
    pairs += [("positive", "negative")] * 2

    results = materialize_pairs(pairs)
    classes = ["positive", "negative"]

    macro = build_dataset_evaluator(
        PrecisionAggregatorSpec(classes=classes, averaging="macro"),
        source_evaluator="positive_match",
    )
    micro = build_dataset_evaluator(
        PrecisionAggregatorSpec(classes=classes, averaging="micro"),
        source_evaluator="positive_match",
    )
    report(
        "Scenario 2a — Imbalanced 2-class, MACRO precision\n"
        "  Rare positive class. Macro averages per-class, so the rare class\n"
        "  having precision = 2/(2+3) = 0.40 drags the score down.",
        macro.evaluate(results),
    )
    report(
        "Scenario 2b — Same data, MICRO precision\n"
        "  Pools TP/FP across classes. In a 2-class case this equals accuracy.",
        micro.evaluate(results),
    )


def scenario_3_precision_vs_recall_vs_f() -> None:
    """Same dataset, three different metrics — show they diverge on asymmetric data."""
    pairs = [
        ("yes", "yes"),
        ("yes", "yes"),
        ("no", "yes"),
        ("no", "yes"),
        ("no", "no"),
        ("no", "no"),
        ("yes", "no"),
    ]
    results = materialize_pairs(pairs)
    classes = ["yes", "no"]

    evaluators = {
        "Scenario 3a — Precision on a recall-favourable dataset": build_dataset_evaluator(
            PrecisionAggregatorSpec(classes=classes, averaging="macro"),
            source_evaluator="yes_match",
        ),
        "Scenario 3b — Recall (same data — note 'yes' recall is 1.0)": build_dataset_evaluator(
            RecallAggregatorSpec(classes=classes, averaging="macro"),
            source_evaluator="yes_match",
        ),
        "Scenario 3c — F1 (harmonic mean of P and R)": build_dataset_evaluator(
            FScoreAggregatorSpec(classes=classes, averaging="macro", f_value=1.0),
            source_evaluator="yes_match",
        ),
        "Scenario 3d — F2 (β=2 weighs recall higher — score moves toward recall)": build_dataset_evaluator(
            FScoreAggregatorSpec(classes=classes, averaging="macro", f_value=2.0),
            source_evaluator="yes_match",
        ),
    }
    for title, evaluator in evaluators.items():
        report(title, evaluator.evaluate(results))


def scenario_4_skipped_datapoints() -> None:
    """Show how malformed / out-of-vocab data is reported, not silently dropped."""
    results = [
        make_result("cat", "cat"),
        make_result("dog", "dog"),
        make_result("cat", "platypus"),
        make_result("zebra", "cat"),
        EvaluationResultDto(score=1.0, details="bare string — no justification"),
        EvaluationResultDto(score=0.0, details={"unrelated": "shape"}),
    ]
    evaluator = build_dataset_evaluator(
        PrecisionAggregatorSpec(classes=["cat", "dog"], averaging="macro"),
        source_evaluator="any_match",
    )
    report(
        "Scenario 4 — Skipped datapoints (out-of-vocab + malformed details)\n"
        "  6 datapoints in, 2 scored, 4 skipped. Skip counts surface in the\n"
        "  report so you can tell whether a low score is a real signal or\n"
        "  just sparse data.",
        evaluator.evaluate(results),
    )


def scenario_5_realistic_intent_classifier() -> None:
    """A larger, more interesting 4-class dataset — uneven per-class performance."""
    pairs = [
        *[("book", "book")] * 10,
        ("book", "cancel"),
        *[("cancel", "cancel")] * 6,
        ("cancel", "book"),
        ("cancel", "modify"),
        ("reschedule", "reschedule"),
        ("reschedule", "reschedule"),
        ("reschedule", "modify"),
        ("reschedule", "modify"),
        ("modify", "modify"),
        ("modify", "reschedule"),
    ]
    results = materialize_pairs(pairs)
    classes = ["book", "cancel", "reschedule", "modify"]
    macro_f1 = build_dataset_evaluator(
        FScoreAggregatorSpec(classes=classes, averaging="macro", f_value=1.0),
        source_evaluator="intent_match",
    )
    report(
        "Scenario 5 — Realistic 4-class intent classifier\n"
        "  Uneven per-class performance. Macro F1 surfaces 'reschedule' and\n"
        "  'modify' weakness; micro F1 would have hidden it under 'book' wins.",
        macro_f1.evaluate(results),
    )


def main() -> None:
    """Run every scenario sequentially."""
    scenario_1_balanced_three_class()
    scenario_2_imbalanced_two_class()
    scenario_3_precision_vs_recall_vs_f()
    scenario_4_skipped_datapoints()
    scenario_5_realistic_intent_classifier()
    print()
    print("Done. All scenarios computed from real evaluator code.")


if __name__ == "__main__":
    main()
