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

from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification
from uipath.eval.evaluators.classification_dataset_evaluators import (
    ClassificationDetails,
    FScoreDatasetEvaluator,
    FScoreDatasetEvaluatorConfig,
    PrecisionDatasetEvaluator,
    PrecisionDatasetEvaluatorConfig,
    RecallDatasetEvaluator,
    RecallDatasetEvaluatorConfig,
)
from uipath.eval.models.models import EvaluationResultDto, NumericEvaluationResult


# ─── helpers ──────────────────────────────────────────────────────────────────


def make_result(expected: str, actual: str) -> EvaluationResultDto:
    """Build a single per-datapoint EvaluationResultDto.

    Models what an upstream ExactMatch evaluator would produce after running
    on one datapoint: score is 1.0 if the labels match, 0.0 otherwise, with
    the expected/actual labels carried in the justification.
    """
    score = 1.0 if expected.lower() == actual.lower() else 0.0
    justification = BaseEvaluatorJustification(expected=expected, actual=actual)
    return EvaluationResultDto(score=score, details=justification.model_dump())


def materialize_pairs(pairs: Iterable[tuple[str, str]]) -> list[EvaluationResultDto]:
    return [make_result(e, a) for e, a in pairs]


def print_header(title: str) -> None:
    print()
    print("═" * 78)
    print(f" {title}")
    print("═" * 78)


def print_confusion(details: ClassificationDetails) -> None:
    """Pretty-print the confusion matrix as a table."""
    classes = details.classes
    cell_width = max(7, max(len(c) for c in classes) + 1)
    header = " " * cell_width + " │ " + " │ ".join(c.center(cell_width) for c in classes) + " │  ← expected"
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
        # Just show a snippet to keep output focused.
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
        ("book", "cancel"),  # FN_book, FP_cancel
        ("cancel", "cancel"),
        ("cancel", "cancel"),
        ("cancel", "reschedule"),  # FN_cancel, FP_reschedule
        ("reschedule", "reschedule"),
        ("reschedule", "reschedule"),
        ("reschedule", "book"),  # FN_reschedule, FP_book
    ]
    results = materialize_pairs(pairs)
    evaluator = PrecisionDatasetEvaluator(
        PrecisionDatasetEvaluatorConfig(
            id="precision_intent",
            name="precision_intent",
            source_evaluator="intent_match",
            classes=["book", "cancel", "reschedule"],
            average="macro",
        )
    )
    report(
        "Scenario 1 — Balanced 3-class (intent recognition)\n"
        "  Each class: 2 TP, 1 FP, 1 FN. Symmetric setup → macro = micro = 2/3.",
        evaluator.evaluate(results),
        show_json_tail=True,
    )


def scenario_2_imbalanced_two_class() -> None:
    """Rare-positive case — why macro vs micro matters.

    20 datapoints. Only 4 are actually positive (the rare class). A weak
    classifier could trivially get high accuracy by predicting "negative"
    everywhere — micro precision masks that, macro doesn't.
    """
    pairs: list[tuple[str, str]] = []
    # 16 true negatives where the classifier said "negative" (correct).
    pairs += [("negative", "negative")] * 13
    # 3 false positives — classifier hallucinated "positive" on actual negatives.
    pairs += [("negative", "positive")] * 3
    # 2 true positives.
    pairs += [("positive", "positive")] * 2
    # 2 false negatives — classifier missed real positives.
    pairs += [("positive", "negative")] * 2

    results = materialize_pairs(pairs)
    classes = ["positive", "negative"]

    macro = PrecisionDatasetEvaluator(
        PrecisionDatasetEvaluatorConfig(
            id="p_macro",
            name="precision (macro)",
            source_evaluator="positive_match",
            classes=classes,
            average="macro",
        )
    )
    micro = PrecisionDatasetEvaluator(
        PrecisionDatasetEvaluatorConfig(
            id="p_micro",
            name="precision (micro)",
            source_evaluator="positive_match",
            classes=classes,
            average="micro",
        )
    )
    report(
        "Scenario 2a — Imbalanced 2-class, MACRO precision\n"
        "  Rare positive class. Macro averages per-class, so the rare class\n"
        "  having precision = 2/(2+3) = 0.40 drags the score down.",
        macro.evaluate(results),
    )
    report(
        "Scenario 2b — Same data, MICRO precision\n"
        "  Pools TP/FP across classes. In a 2-class case this equals accuracy.\n"
        "  Notice macro << micro — that's the bias you'd miss with micro alone.",
        micro.evaluate(results),
    )


def scenario_3_precision_vs_recall_vs_f() -> None:
    """Same dataset, three different metrics — show they diverge on asymmetric data."""
    pairs = [
        ("yes", "yes"),
        ("yes", "yes"),
        ("no", "yes"),  # FP for yes
        ("no", "yes"),  # FP for yes
        ("no", "no"),
        ("no", "no"),
        ("yes", "no"),  # FN for yes
    ]
    results = materialize_pairs(pairs)
    classes = ["yes", "no"]

    p = PrecisionDatasetEvaluator(
        PrecisionDatasetEvaluatorConfig(
            id="p",
            name="precision",
            source_evaluator="yes_match",
            classes=classes,
            average="macro",
        )
    )
    r = RecallDatasetEvaluator(
        RecallDatasetEvaluatorConfig(
            id="r",
            name="recall",
            source_evaluator="yes_match",
            classes=classes,
            average="macro",
        )
    )
    f1 = FScoreDatasetEvaluator(
        FScoreDatasetEvaluatorConfig(
            id="f1",
            name="f1",
            source_evaluator="yes_match",
            classes=classes,
            average="macro",
            f_value=1.0,
        )
    )
    f2 = FScoreDatasetEvaluator(
        FScoreDatasetEvaluatorConfig(
            id="f2",
            name="f2",
            source_evaluator="yes_match",
            classes=classes,
            average="macro",
            f_value=2.0,
        )
    )
    report(
        "Scenario 3a — Precision on a recall-favourable dataset",
        p.evaluate(results),
    )
    report(
        "Scenario 3b — Recall (same data — note 'yes' recall is 1.0)",
        r.evaluate(results),
    )
    report(
        "Scenario 3c — F1 (harmonic mean of P and R)",
        f1.evaluate(results),
    )
    report(
        "Scenario 3d — F2 (β=2 weighs recall higher — score moves toward recall)",
        f2.evaluate(results),
    )


def scenario_4_skipped_datapoints() -> None:
    """Show how malformed / out-of-vocab data is reported, not silently dropped."""
    results = [
        make_result("cat", "cat"),
        make_result("dog", "dog"),
        make_result("cat", "platypus"),  # actual not in classes → skipped
        make_result("zebra", "cat"),  # expected not in classes → skipped
        EvaluationResultDto(score=1.0, details="bare string — no justification"),
        EvaluationResultDto(score=0.0, details={"unrelated": "shape"}),
    ]
    evaluator = PrecisionDatasetEvaluator(
        PrecisionDatasetEvaluatorConfig(
            id="precision_robustness",
            name="precision_robustness",
            source_evaluator="any_match",
            classes=["cat", "dog"],
            average="macro",
        )
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
        # 'book' is easy: classifier handles it well
        *[("book", "book")] * 10,
        ("book", "cancel"),
        # 'cancel' is medium: a few errors
        *[("cancel", "cancel")] * 6,
        ("cancel", "book"),
        ("cancel", "modify"),
        # 'reschedule' is hard: classifier confuses it with 'modify'
        ("reschedule", "reschedule"),
        ("reschedule", "reschedule"),
        ("reschedule", "modify"),
        ("reschedule", "modify"),
        # 'modify' is rare: only 2 cases, classifier gets one
        ("modify", "modify"),
        ("modify", "reschedule"),
    ]
    results = materialize_pairs(pairs)
    classes = ["book", "cancel", "reschedule", "modify"]
    macro_f1 = FScoreDatasetEvaluator(
        FScoreDatasetEvaluatorConfig(
            id="f1_4class",
            name="f1_4class",
            source_evaluator="intent_match",
            classes=classes,
            average="macro",
            f_value=1.0,
        )
    )
    report(
        "Scenario 5 — Realistic 4-class intent classifier\n"
        "  Uneven per-class performance. Macro F1 surfaces 'reschedule' and\n"
        "  'modify' weakness; micro F1 would have hidden it under 'book' wins.",
        macro_f1.evaluate(results),
    )


def main() -> None:
    scenario_1_balanced_three_class()
    scenario_2_imbalanced_two_class()
    scenario_3_precision_vs_recall_vs_f()
    scenario_4_skipped_datapoints()
    scenario_5_realistic_intent_classifier()
    print()
    print("Done. All scenarios computed from real evaluator code.")


if __name__ == "__main__":
    main()
