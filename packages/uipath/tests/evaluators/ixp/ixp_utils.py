"""Golden-fixture models and builders, ported from ixp-platform
uipath_mls_user_model_store/tests/ixp_utils.py (pydantic v2). The JSON
fixtures themselves are byte-for-byte copies from ixp-platform tests/data/.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

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
    FieldF1ScoreQuality,
    FieldNumIndicators,
    Indicators,
    IxpDocumentMetrics,
    IxpDocumentsMetrics,
    IxpLevelMetrics,
    IxpMetrics,
    IxpSummaryMetrics,
    LatencyMetrics,
    PredictionAndGroundTruth,
    ProjectIndicators,
    ProjectScoreQuality,
    RawIxpMetrics,
    RawIxpMetricsFromMoon,
)
from uipath.eval.evaluators.ixp.moon import (
    CaptureConfidence,
    RawCapture,
    RawCaptures,
    RawCommentCaptures,
    RawMoonField,
    RawMoonValue,
)
from uipath.eval.evaluators.ixp.ranged_value import RangedValue

DATA_DIR = Path(__file__).parent / "data"


def get_ixp_metrics_test_case_paths() -> list[Path]:
    return sorted(DATA_DIR.glob("ixp_metrics_test_case_*.json"))


def get_ixp_metrics_from_moon_test_case_paths() -> list[Path]:
    return sorted(DATA_DIR.glob("from_moon_ixp_metrics_test_case_*.json"))


class ApiBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PredictionAndGroundTruthTestCase(ApiBaseModel):
    test_comment_index: int = Field(...)
    field_group_name: str = Field(...)
    i_extraction: int = Field(...)
    field_id: str = Field(...)
    predicted_value: str | None = Field(...)
    ground_truth_value: str | None = Field(...)
    is_match: bool = Field(...)
    confidence: float | None = Field(...)


class IxpDocumentMetricsTestCase(ApiBaseModel):
    field_error_rate: float = Field(...)


class IxpDocumentsMetricsTestCase(ApiBaseModel):
    mean_document_field_error_rate: float = Field(...)
    mean_num_pages_per_document: float | None = Field(...)
    documents_metrics: tuple[IxpDocumentMetricsTestCase, ...] = Field(...)


class ProjectScoreQualityTestCase(str, Enum):
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"
    EXCELLENT = "excellent"


class F1ScoreQualityTestCase(str, Enum):
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"


class LatencyMetricsTestCase(ApiBaseModel):
    p99: float = Field(...)
    p95: float = Field(...)
    p50: float = Field(...)


class FieldNumIndicatorsTestCase(ApiBaseModel):
    validated_fields: int = Field(...)
    insufficient_annotated_values: int = Field(...)
    poor_f1_score: int = Field(...)
    average_f1_score: int = Field(...)
    good_f1_score: int = Field(...)


class IndicatorsTestCase(ApiBaseModel):
    f1_score_quality: F1ScoreQualityTestCase = Field(...)
    field_num_indicators: FieldNumIndicatorsTestCase = Field(...)


TypeT = TypeVar("TypeT", bound=float | int)


class RangedValueTestCase(ApiBaseModel, Generic[TypeT]):
    value: TypeT = Field(...)
    variability: float | None = Field(...)


class IxpLevelMetricsTestCase(ApiBaseModel):
    f1_score: RangedValueTestCase[float] = Field(...)
    precision: RangedValueTestCase[float] = Field(...)
    recall: RangedValueTestCase[float] = Field(...)
    indicators: IndicatorsTestCase = Field(...)

    num_annotated_documents: int = Field(...)
    num_documents_with_errors: RangedValueTestCase[int] = Field()
    proportion_documents_with_errors: RangedValueTestCase[float] = Field(...)

    num_annotations: int = Field(...)
    num_annotated_values: int = Field(...)
    num_annotated_missing: int = Field(...)
    num_predictions: RangedValueTestCase[int] = Field(...)

    error_rate: RangedValueTestCase[float] = Field(...)
    error_rate_missing_value: float = Field(...)
    error_rate_excluding_missing: RangedValueTestCase[float] = Field(...)

    num_errors: RangedValueTestCase[int] = Field(...)
    num_value_errors: RangedValueTestCase[int] = Field(...)
    num_incorrect_predictions: RangedValueTestCase[int] = Field(...)
    num_extra_predictions: RangedValueTestCase[int] = Field(...)
    num_missed_predictions: RangedValueTestCase[int] = Field(...)
    num_correct_value_predictions: RangedValueTestCase[int] = Field(...)
    num_correct_missing_predictions: RangedValueTestCase[int] = Field(...)


class IxpMetricsTestCase(ApiBaseModel):
    field_groups_metrics: dict[str, IxpLevelMetricsTestCase] = Field(...)
    fields_metrics: dict[str, dict[str, IxpLevelMetricsTestCase]] = Field(...)


class ProjectIndicatorsTestCase(ApiBaseModel):
    project_score_quality: ProjectScoreQualityTestCase = Field(...)
    field_num_indicators: FieldNumIndicatorsTestCase = Field(...)


class IxpSummaryMetricsTestCase(ApiBaseModel):
    num_train_documents: int = Field(...)
    num_validated_documents: int = Field(...)
    project_score: float = Field(...)
    project_indicators: ProjectIndicatorsTestCase = Field(...)
    ixp_metrics: IxpMetricsTestCase = Field(...)
    latency_metrics: LatencyMetricsTestCase | None = Field(...)
    document_ids: tuple[str, ...] = Field(...)
    document_names: tuple[str, ...] = Field(...)
    documents_metrics: IxpDocumentsMetricsTestCase = Field(...)
    prediction_and_ground_truths: tuple[PredictionAndGroundTruthTestCase, ...] = Field(
        ...
    )


class RawMoonFieldTestCase(ApiBaseModel):
    value: str | None = Field(...)
    confidence: float = Field(...)


class RawCaptureTestCase(ApiBaseModel):
    fields: dict[str, RawMoonFieldTestCase] = Field(...)
    confidence: float = Field(...)


class RawCommentCapturesTestCase(ApiBaseModel):
    indices: tuple[int, ...] = Field(...)
    captures: tuple[tuple[RawCaptureTestCase, ...], ...] = Field(...)


class RawCapturesTestCase(ApiBaseModel):
    test_assigned: RawCommentCapturesTestCase = Field(...)
    test_predicted: RawCommentCapturesTestCase = Field(...)


class DocumentMetadataTestCase(ApiBaseModel):
    filename: str = Field(...)
    content_type: str = Field(...)
    num_pages: int | None = Field(...)


class RawIxpMetricsTestCase(ApiBaseModel):
    train_document_metadatas: tuple[DocumentMetadataTestCase, ...] = Field(...)
    test_document_metadatas: tuple[DocumentMetadataTestCase, ...] = Field(...)
    field_groups_extractions: dict[str, RawCapturesTestCase] = Field(...)


class RawIxpMetricsFromMoonTestCase(ApiBaseModel):
    num_train_documents: int = Field(...)
    num_test_documents: int = Field(...)
    field_groups_extractions: dict[str, RawCapturesTestCase] = Field(...)


class GetIxpMetricsTestCase(ApiBaseModel):
    title: str = Field(...)
    description: str = Field(...)
    field_group_name_to_field_ids: dict[str, tuple[str, ...]] = Field(...)
    document_ids: tuple[str, ...] = Field(...)
    raw: RawIxpMetricsTestCase = Field(...)
    expected: IxpSummaryMetricsTestCase | None = Field(...)


class GetIxpMetricsFromMoonTestCase(ApiBaseModel):
    title: str = Field(...)
    description: str = Field(...)
    field_group_name_to_field_ids: dict[str, tuple[str, ...]] = Field(...)
    document_ids: tuple[str, ...] = Field(...)
    raw: RawIxpMetricsFromMoonTestCase = Field(...)
    expected: IxpSummaryMetricsTestCase | None = Field(...)


def get_raw_ixp_metrics(test_case: RawIxpMetricsTestCase) -> RawIxpMetrics:
    return RawIxpMetrics(
        train_document_metadatas=tuple(
            _get_document_metadata(metadata)
            for metadata in test_case.train_document_metadatas
        ),
        test_document_metadatas=tuple(
            _get_document_metadata(metadata)
            for metadata in test_case.test_document_metadatas
        ),
        field_groups_extractions=FrozenDict(
            {
                LabelName(field_group_name): _get_raw_captures(raw_captures)
                for (
                    field_group_name,
                    raw_captures,
                ) in test_case.field_groups_extractions.items()
            }
        ),
    )


def get_raw_ixp_metrics_from_moon(
    test_case: RawIxpMetricsFromMoonTestCase,
) -> RawIxpMetricsFromMoon:
    return RawIxpMetricsFromMoon(
        _num_train_documents=test_case.num_train_documents,
        _num_test_documents=test_case.num_test_documents,
        field_groups_extractions=FrozenDict(
            {
                LabelName(field_group_name): _get_raw_captures(raw_captures)
                for (
                    field_group_name,
                    raw_captures,
                ) in test_case.field_groups_extractions.items()
            }
        ),
    )


def get_field_group_name_to_field_ids(
    field_group_name_to_field_ids: dict[str, tuple[str, ...]],
) -> FrozenDict[LabelName, tuple[ExtractionFieldId, ...]]:
    return FrozenDict(
        {
            LabelName(field_group_name): tuple(
                ExtractionFieldId(FieldId(field_id)) for field_id in field_ids
            )
            for (
                field_group_name,
                field_ids,
            ) in field_group_name_to_field_ids.items()
        }
    )


def get_ixp_summary_metrics(
    test_case: IxpSummaryMetricsTestCase | None,
) -> IxpSummaryMetrics | None:
    if test_case is None:
        return None
    return IxpSummaryMetrics(
        num_train_documents=test_case.num_train_documents,
        num_validated_documents=test_case.num_validated_documents,
        project_score=test_case.project_score,
        project_indicators=_get_project_indicators(test_case.project_indicators),
        ixp_metrics=_get_ixp_metrics(test_case.ixp_metrics),
        latency_metrics=(
            _get_latency_metrics(test_case.latency_metrics)
            if test_case.latency_metrics is not None
            else None
        ),
        document_ids=tuple(
            InternalCommentId(document_id) for document_id in test_case.document_ids
        ),
        document_names=test_case.document_names,
        documents_metrics=_get_document_metrics(test_case.documents_metrics),
        prediction_and_ground_truths=tuple(
            _get_prediction_and_ground_truth(prediction_and_ground_truth)
            for (prediction_and_ground_truth) in test_case.prediction_and_ground_truths
        ),
    )


def _get_prediction_and_ground_truth(
    test_case: PredictionAndGroundTruthTestCase,
) -> PredictionAndGroundTruth:
    return PredictionAndGroundTruth(
        test_comment_index=TestCommentIndex(test_case.test_comment_index),
        field_group_name=LabelName(test_case.field_group_name),
        i_extraction=test_case.i_extraction,
        field_id=ExtractionFieldId(FieldId(test_case.field_id)),
        predicted_value=test_case.predicted_value,
        ground_truth_value=test_case.ground_truth_value,
        is_match=test_case.is_match,
        confidence=test_case.confidence,
    )


def _get_document_metadata(
    test_case: DocumentMetadataTestCase,
) -> DocumentMetadata:
    return DocumentMetadata(
        filename=test_case.filename,
        content_type=test_case.content_type,
        num_pages=test_case.num_pages,
    )


def _get_raw_captures(test_case: RawCapturesTestCase) -> RawCaptures:
    return RawCaptures(
        train_assigned=RawCommentCaptures((), ()),
        train_dismissed=RawCommentCaptures((), ()),
        test_assigned=_get_raw_comment_captures(test_case.test_assigned),
        test_dismissed=RawCommentCaptures((), ()),
        test_predicted=_get_raw_comment_captures(test_case.test_predicted),
    )


def _get_raw_comment_captures(
    test_case: RawCommentCapturesTestCase,
) -> RawCommentCaptures[TestCommentIndex]:
    return RawCommentCaptures(
        indices=tuple(TestCommentIndex(index) for index in test_case.indices),
        captures=tuple(
            tuple(_get_raw_capture(capture) for capture in capture_tuple)
            for capture_tuple in test_case.captures
        ),
    )


def _get_raw_capture(test_case: RawCaptureTestCase) -> RawCapture:
    return RawCapture(
        fields=FrozenDict(
            {
                ExtractionFieldId(FieldId(field_id)): RawMoonField(
                    value=(
                        RawMoonValue(field.value) if field.value is not None else None
                    ),
                    confidence=field.confidence,
                )
                for field_id, field in test_case.fields.items()
            }
        ),
        confidence=CaptureConfidence(test_case.confidence),
    )


def _get_ixp_metrics(test_case: IxpMetricsTestCase) -> IxpMetrics:
    return IxpMetrics(
        field_groups_metrics=FrozenDict(
            {
                LabelName(field_group_name): _get_ixp_level_metrics(field_group_metrics)
                for (
                    field_group_name,
                    field_group_metrics,
                ) in test_case.field_groups_metrics.items()
            }
        ),
        fields_metrics=FrozenDict(
            {
                LabelName(field_group_name): FrozenDict(
                    {
                        ExtractionFieldId(FieldId(field_id)): _get_ixp_level_metrics(
                            field_metrics
                        )
                        for (
                            field_id,
                            field_metrics,
                        ) in field_metrics_dict.items()
                    }
                )
                for (
                    field_group_name,
                    field_metrics_dict,
                ) in test_case.fields_metrics.items()
            }
        ),
    )


def _get_ixp_level_metrics(
    test_case: IxpLevelMetricsTestCase,
) -> IxpLevelMetrics:
    return IxpLevelMetrics(
        f1_score=_get_ranged_value_float(test_case.f1_score),
        precision=_get_ranged_value_float(test_case.precision),
        recall=_get_ranged_value_float(test_case.recall),
        indicators=_get_indicators(test_case.indicators),
        num_annotated_documents=test_case.num_annotated_documents,
        num_documents_with_errors=_get_ranged_value_int(
            test_case.num_documents_with_errors
        ),
        proportion_documents_with_errors=_get_ranged_value_float(
            test_case.proportion_documents_with_errors
        ),
        num_annotations=test_case.num_annotations,
        num_annotated_values=test_case.num_annotated_values,
        num_annotated_missing=test_case.num_annotated_missing,
        num_predictions=_get_ranged_value_int(test_case.num_predictions),
        error_rate=_get_ranged_value_float(test_case.error_rate),
        error_rate_missing_value=test_case.error_rate_missing_value,
        error_rate_excluding_missing=_get_ranged_value_float(
            test_case.error_rate_excluding_missing
        ),
        num_errors=_get_ranged_value_int(test_case.num_errors),
        num_value_errors=_get_ranged_value_int(test_case.num_value_errors),
        num_incorrect_predictions=_get_ranged_value_int(
            test_case.num_incorrect_predictions
        ),
        num_extra_predictions=_get_ranged_value_int(test_case.num_extra_predictions),
        num_missed_predictions=_get_ranged_value_int(test_case.num_missed_predictions),
        num_correct_value_predictions=_get_ranged_value_int(
            test_case.num_correct_value_predictions
        ),
        num_correct_missing_predictions=_get_ranged_value_int(
            test_case.num_correct_missing_predictions
        ),
    )


def _get_ranged_value_int(
    test_case: RangedValueTestCase[int],
) -> RangedValue[int]:
    return RangedValue[int](value=test_case.value, variability=test_case.variability)


def _get_ranged_value_float(
    test_case: RangedValueTestCase[float],
) -> RangedValue[float]:
    return RangedValue[float](value=test_case.value, variability=test_case.variability)


def _get_project_indicators(
    test_case: ProjectIndicatorsTestCase,
) -> ProjectIndicators:
    return ProjectIndicators(
        project_score_quality=_get_project_score_quality(
            test_case.project_score_quality
        ),
        field_num_indicators=_get_field_num_indicators(test_case.field_num_indicators),
    )


def _get_project_score_quality(
    test_case: ProjectScoreQualityTestCase,
) -> ProjectScoreQuality:
    match test_case:
        case ProjectScoreQualityTestCase.POOR:
            return ProjectScoreQuality.POOR
        case ProjectScoreQualityTestCase.AVERAGE:
            return ProjectScoreQuality.AVERAGE
        case ProjectScoreQualityTestCase.GOOD:
            return ProjectScoreQuality.GOOD
        case ProjectScoreQualityTestCase.EXCELLENT:
            return ProjectScoreQuality.EXCELLENT
    raise AssertionError(test_case)


def _get_indicators(test_case: IndicatorsTestCase) -> Indicators:
    return Indicators(
        f1_score_quality=_get_f1_score_quality(test_case.f1_score_quality),
        field_num_indicators=_get_field_num_indicators(test_case.field_num_indicators),
    )


def _get_f1_score_quality(
    test_case: F1ScoreQualityTestCase,
) -> FieldF1ScoreQuality:
    match test_case:
        case F1ScoreQualityTestCase.POOR:
            return FieldF1ScoreQuality.POOR
        case F1ScoreQualityTestCase.AVERAGE:
            return FieldF1ScoreQuality.AVERAGE
        case F1ScoreQualityTestCase.GOOD:
            return FieldF1ScoreQuality.GOOD
    raise AssertionError(test_case)


def _get_field_num_indicators(
    test_case: FieldNumIndicatorsTestCase,
) -> FieldNumIndicators:
    return FieldNumIndicators(
        validated_fields=test_case.validated_fields,
        insufficient_annotated_values=test_case.insufficient_annotated_values,
        poor_f1_score=test_case.poor_f1_score,
        average_f1_score=test_case.average_f1_score,
        good_f1_score=test_case.good_f1_score,
    )


def _get_latency_metrics(test_case: LatencyMetricsTestCase) -> LatencyMetrics:
    return LatencyMetrics(p99=test_case.p99, p95=test_case.p95, p50=test_case.p50)


def _get_document_metrics(
    test_case: IxpDocumentsMetricsTestCase,
) -> IxpDocumentsMetrics:
    return IxpDocumentsMetrics(
        mean_document_field_error_rate=(test_case.mean_document_field_error_rate),
        mean_num_pages_per_document=test_case.mean_num_pages_per_document,
        document_metrics=tuple(
            IxpDocumentMetrics(field_error_rate=document_metrics.field_error_rate)
            for document_metrics in test_case.documents_metrics
        ),
    )
