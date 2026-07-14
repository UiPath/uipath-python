"""Sample runs of the ported IXP Measure scoring core.

1. The worked example from the design wiki ("Line Items", 3 annotated rows,
   2 predicted rows) — asserts the documented numbers: group F1 ≈ 0.71,
   per-field F1 = 0.80 / 0.50 / 0.80, project score 0.70 → GOOD.
2. A couple of golden fixtures, scored and printed as a metric grid.

Run:
    cd packages/uipath/tests/evaluators/ixp
    uv run --no-project --python 3.12 --with pydantic --with python-dateutil \
        python demo.py
"""

from __future__ import annotations

import math

from ixp_utils import (  # noqa: E402 (does the sys.path setup for `ixp`)
    GetIxpMetricsTestCase,
    get_field_group_name_to_field_ids,
    get_ixp_metrics_test_case_paths,
    get_raw_ixp_metrics,
)

from ixp._compat import (
    ExtractionFieldId,
    FieldId,
    FrozenDict,
    InternalCommentId,
    LabelName,
    TestCommentIndex,
)
from ixp.ixp import (
    DocumentMetadata,
    IxpSummaryMetrics,
    ProjectScoreQuality,
    RawIxpMetrics,
    _raw_ixp_metrics_to_summary,
)
from ixp.moon import (
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


def wiki_worked_example() -> IxpSummaryMetrics:
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
    for group_name, group_fields in summary.ixp_metrics.fields_metrics.items():
        for field_id, field in group_fields.items():
            print(
                f"    field {field_id}: "
                f"P={field.precision.value:.4f} R={field.recall.value:.4f} "
                f"F1={field.f1_score.value:.4f} "
                f"({field.indicators.f1_score_quality.name})"
            )


def main() -> None:
    summary = wiki_worked_example()
    print_summary(summary, "wiki worked example: Line Items")

    group = summary.ixp_metrics.field_groups_metrics[LINE_ITEMS]
    field_f1s = {
        field_id: metrics.f1_score.value
        for field_id, metrics in summary.ixp_metrics.fields_metrics[
            LINE_ITEMS
        ].items()
    }
    # the wiki's documented numbers: TP=5 FP=1 FN=3
    assert math.isclose(group.precision.value, 5 / 6), group.precision.value
    assert math.isclose(group.recall.value, 5 / 8), group.recall.value
    assert math.isclose(group.f1_score.value, 5 / 7), group.f1_score.value
    assert math.isclose(field_f1s[DESCRIPTION], 0.80), field_f1s
    assert math.isclose(field_f1s[QTY], 0.50), field_f1s
    assert math.isclose(field_f1s[AMOUNT], 0.80), field_f1s
    assert math.isclose(summary.project_score, 0.70), summary.project_score
    assert (
        summary.project_indicators.project_score_quality
        is ProjectScoreQuality.GOOD
    )
    print("\nall wiki numbers reproduced: F1=5/7≈0.71, project=0.70 → GOOD")

    # score a few golden fixtures end to end and show their grids
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
        test_case = GetIxpMetricsTestCase.parse_file(path)
        summary = _raw_ixp_metrics_to_summary(
            field_group_name_to_field_ids=get_field_group_name_to_field_ids(
                test_case.field_group_name_to_field_ids
            ),
            document_ids=tuple(
                InternalCommentId(document_id)
                for document_id in test_case.document_ids
            ),
            raw=get_raw_ixp_metrics(test_case.raw),
            field_id_to_inherits_from={},
        )
        if summary is None:
            print(f"\n=== fixture {path.name}: no metrics (empty corpus) ===")
        else:
            print_summary(summary, f"fixture {path.name}")


if __name__ == "__main__":
    main()
