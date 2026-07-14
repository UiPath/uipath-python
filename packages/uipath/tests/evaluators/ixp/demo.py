"""Sample runs of the ported IXP Measure scoring core.

1. A worked example ("Line Items", 3 annotated rows, 2 predicted rows) —
   asserts the expected numbers: group F1 = 5/7, per-field
   F1 = 0.80 / 0.50 / 0.80, project score 0.70 → GOOD.
2. A few golden fixtures, scored and printed as a metric grid.

Run from packages/uipath:
    uv run python -m tests.evaluators.ixp.demo
"""

from __future__ import annotations

import math

from uipath.eval.evaluators.ixp._compat import (
    ExtractionFieldId,
    FieldId,
    FrozenDict,
    InternalCommentId,
    LabelName,
    TestCommentIndex,
)
from uipath.eval.evaluators.ixp.ixp import (
    DocumentMetadata,
    IxpSummaryMetrics,
    ProjectScoreQuality,
    RawIxpMetrics,
    _raw_ixp_metrics_to_summary,
)
from uipath.eval.evaluators.ixp.moon import (
    CaptureConfidence,
    RawCapture,
    RawCaptures,
    RawCommentCaptures,
    RawMoonField,
    RawMoonValue,
)

DESCRIPTION = ExtractionFieldId(FieldId("00000000000000aa"))
QTY = ExtractionFieldId(FieldId("00000000000000bb"))
AMOUNT = ExtractionFieldId(FieldId("00000000000000cc"))
LINE_ITEMS = LabelName("Line Items")


def _capture(values: dict[ExtractionFieldId, str | None]) -> RawCapture:
    return RawCapture(
        fields=FrozenDict(
            {
                field_id: RawMoonField(
                    value=RawMoonValue(value) if value is not None else None,
                    confidence=1.0,
                )
                for field_id, value in values.items()
            }
        ),
        confidence=CaptureConfidence(1.0),
    )


def worked_example() -> IxpSummaryMetrics:
    """One document; annotator marked 3 rows, the model predicted 2."""
    annotated = (
        _capture({DESCRIPTION: "Widget A", QTY: "2", AMOUNT: "10.00"}),  # A1
        _capture({DESCRIPTION: "Widget B", QTY: "1", AMOUNT: "5.00"}),  # A2
        _capture({DESCRIPTION: "Shipping", QTY: None, AMOUNT: "3.50"}),  # A3
    )
    predicted = (
        _capture({DESCRIPTION: "Widget B", QTY: "1", AMOUNT: "5.00"}),  # P1
        _capture({DESCRIPTION: "Widget A", QTY: "3", AMOUNT: "10.00"}),  # P2
    )
    raw = RawIxpMetrics(
        train_document_metadatas=(),
        test_document_metadatas=(
            DocumentMetadata(
                filename="invoice_0001.pdf", content_type="pdf", num_pages=1
            ),
        ),
        field_groups_extractions=FrozenDict(
            {
                LINE_ITEMS: RawCaptures(
                    train_assigned=RawCommentCaptures((), ()),
                    train_dismissed=RawCommentCaptures((), ()),
                    test_assigned=RawCommentCaptures(
                        indices=(TestCommentIndex(0),), captures=(annotated,)
                    ),
                    test_dismissed=RawCommentCaptures((), ()),
                    test_predicted=RawCommentCaptures(
                        indices=(TestCommentIndex(0),), captures=(predicted,)
                    ),
                )
            }
        ),
    )
    summary = _raw_ixp_metrics_to_summary(
        field_group_name_to_field_ids=FrozenDict(
            {LINE_ITEMS: (DESCRIPTION, QTY, AMOUNT)}
        ),
        document_ids=(InternalCommentId("abcdef0123456789"),),
        raw=raw,
        field_id_to_inherits_from={},
    )
    assert summary is not None
    return summary


def print_summary(summary: IxpSummaryMetrics, title: str) -> None:
    print(f"\n=== {title} ===")
    print(
        f"project score: {summary.project_score:.4f}"
        f"  quality: {summary.project_indicators.project_score_quality.name}"
    )
    for group_name, group in summary.ixp_metrics.field_groups_metrics.items():
        print(
            f"  field group {group_name!r}: "
            f"P={group.precision.value:.4f} R={group.recall.value:.4f} "
            f"F1={group.f1_score.value:.4f} "
            f"errors={group.num_errors.value} "
            f"annotated={group.num_annotations}"
        )
    for group_fields in summary.ixp_metrics.fields_metrics.values():
        for field_id, field in group_fields.items():
            print(
                f"    field {field_id}: "
                f"P={field.precision.value:.4f} R={field.recall.value:.4f} "
                f"F1={field.f1_score.value:.4f} "
                f"({field.indicators.f1_score_quality.name})"
            )


def main() -> None:
    summary = worked_example()
    print_summary(summary, "worked example: Line Items")

    group = summary.ixp_metrics.field_groups_metrics[LINE_ITEMS]
    assert math.isclose(group.f1_score.value, 5 / 7)
    assert math.isclose(summary.project_score, 0.70)
    assert summary.project_indicators.project_score_quality is ProjectScoreQuality.GOOD
    print("\nall expected numbers reproduced: F1=5/7≈0.71, project=0.70 → GOOD")

    # score a few golden fixtures end to end and show their grids
    from tests.evaluators.ixp.ixp_utils import (
        GetIxpMetricsTestCase,
        get_field_group_name_to_field_ids,
        get_ixp_metrics_test_case_paths,
        get_raw_ixp_metrics,
    )

    interesting = [
        path
        for path in get_ixp_metrics_test_case_paths()
        if any(
            tag in path.name
            for tag in (
                "005_one_correctly_predicted",
                "012_two_annotated_one_predicted_correctly_one_wrongly",
                "028_sufficient_annotations",
            )
        )
    ]
    for path in interesting:
        test_case = GetIxpMetricsTestCase.model_validate_json(path.read_text())
        fixture_summary = _raw_ixp_metrics_to_summary(
            field_group_name_to_field_ids=get_field_group_name_to_field_ids(
                test_case.field_group_name_to_field_ids
            ),
            document_ids=tuple(
                InternalCommentId(document_id) for document_id in test_case.document_ids
            ),
            raw=get_raw_ixp_metrics(test_case.raw),
            field_id_to_inherits_from={},
        )
        if fixture_summary is None:
            print(f"\n=== fixture {path.name}: no metrics (empty corpus) ===")
        else:
            print_summary(fixture_summary, f"fixture {path.name}")


if __name__ == "__main__":
    main()
