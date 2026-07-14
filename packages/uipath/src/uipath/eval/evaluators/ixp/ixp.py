from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from statistics import mean

from . import _compat as proto
from ._compat import (
    BuiltinEntityDefId,
    ExtractionFieldId,
    FrozenDict,
    InternalCommentId,
    LabelName,
    PRPrediction,
    TestCommentIndex,
    round_like_javascript,
)
from .moon import (
    DocumentCaptureMatch,
    MoonDocumentIntentCaptures,
    RawCapture,
    RawCaptures,
    RawMoonMetrics,
    match_captures,
)
from .ranged_value import RangedValue

# NOTE: !! IMPORTANT !!
#
# Modifying the logic to convert raw metrics into summary metrics will require
# you to update the cache version in `metadata_store` in
# `_user_model_summary_metrics_cache_key` since summary metrics get cached.
#
# To ensure these errors get caught more easily also please DO NOT ADD ANY
# DEFAULT FIELDS to any of the types in this file.
#
# NOTE: !! IMPORTANT !!


__all__ = (
    "MINIMUM_ANNOTATED_VALUES_FOR_SUFFICIENT_DATA",
    "START_FIELD_F1_SCORE_QUALITY_GOOD",
    "START_FIELD_F1_SCORE_QUALITY_AVERAGE",
    "START_PROJECT_SCORE_QUALITY_AVERAGE",
    "START_PROJECT_SCORE_QUALITY_EXCELLENT",
    "START_PROJECT_SCORE_QUALITY_GOOD",
    "FieldF1ScoreQuality",
    "RawIxpMetrics",
    "DocumentMetadata",
    "Indicators",
    "IxpLevelMetrics",
    "IxpSummaryMetrics",
    "PredictionAndGroundTruth",
    "ProjectScoreQuality",
)


@dataclass(slots=True, frozen=True)
class RawIxpMetrics:
    train_document_metadatas: tuple[DocumentMetadata, ...]
    test_document_metadatas: tuple[DocumentMetadata, ...]
    field_groups_extractions: FrozenDict[LabelName, RawCaptures]

    @staticmethod
    def empty() -> RawIxpMetrics:
        return RawIxpMetrics(
            train_document_metadatas=(),
            test_document_metadatas=(),
            field_groups_extractions=FrozenDict(),
        )

    def num_train_documents(self) -> int:
        return len(self.train_document_metadatas)

    def num_test_documents(self) -> int:
        return len(self.test_document_metadatas)

    def is_empty(self) -> bool:
        return (
            len(self.test_document_metadatas) == 0
            and len(self.field_groups_extractions) == 0
            and len(self.train_document_metadatas) == 0
        )


@dataclass(slots=True, frozen=True)
class RawIxpMetricsFromMoon:
    _num_train_documents: int
    _num_test_documents: int
    field_groups_extractions: FrozenDict[LabelName, RawCaptures]

    @staticmethod
    def empty() -> RawIxpMetricsFromMoon:
        return RawIxpMetricsFromMoon(
            _num_train_documents=0,
            _num_test_documents=0,
            field_groups_extractions=FrozenDict(),
        )

    @staticmethod
    def from_moon(raw_moon: RawMoonMetrics) -> RawIxpMetricsFromMoon:
        return RawIxpMetricsFromMoon(
            _num_train_documents=raw_moon.num_train_documents,
            _num_test_documents=raw_moon.num_test_documents,
            field_groups_extractions=FrozenDict(
                {
                    field_group_name: raw_intent.captures
                    for (
                        field_group_name,
                        raw_intent,
                    ) in raw_moon.raw_intents.items()
                }
            ),
        )

    def num_train_documents(self) -> int:
        return self._num_train_documents

    def num_test_documents(self) -> int:
        return self._num_test_documents


@dataclass(slots=True, frozen=True)
class DocumentMetadata:
    filename: str
    content_type: str
    num_pages: int | None


@dataclass(slots=True, frozen=True)
class IxpSummaryMetrics:
    num_train_documents: int
    num_validated_documents: int
    project_score: float
    project_indicators: ProjectIndicators
    ixp_metrics: IxpMetrics
    latency_metrics: LatencyMetrics | None
    document_names: tuple[str, ...]
    document_ids: tuple[InternalCommentId, ...]
    documents_metrics: IxpDocumentsMetrics
    prediction_and_ground_truths: tuple[PredictionAndGroundTruth, ...]


@dataclass(slots=True, frozen=True)
class ProjectIndicators:
    project_score_quality: ProjectScoreQuality
    field_num_indicators: FieldNumIndicators


@dataclass(slots=True, frozen=True)
class IxpMetrics:
    field_groups_metrics: FrozenDict[LabelName, IxpLevelMetrics]
    fields_metrics: FrozenDict[
        LabelName, FrozenDict[ExtractionFieldId, IxpLevelMetrics]
    ]


@dataclass(slots=True, frozen=True)
class IxpLevelMetrics:
    f1_score: RangedValue[float]
    precision: RangedValue[float]
    recall: RangedValue[float]
    indicators: Indicators

    num_annotated_documents: int
    num_documents_with_errors: RangedValue[int]
    proportion_documents_with_errors: RangedValue[float]

    num_annotations: int
    num_annotated_values: int
    num_annotated_missing: int
    num_predictions: RangedValue[int]

    error_rate: RangedValue[float]
    error_rate_missing_value: float
    error_rate_excluding_missing: RangedValue[float]

    num_errors: RangedValue[int]
    num_value_errors: RangedValue[int]
    num_incorrect_predictions: RangedValue[int]
    num_extra_predictions: RangedValue[int]
    num_missed_predictions: RangedValue[int]
    num_correct_value_predictions: RangedValue[int]
    num_correct_missing_predictions: RangedValue[int]


@dataclass(slots=True, frozen=True)
class Indicators:
    f1_score_quality: FieldF1ScoreQuality
    field_num_indicators: FieldNumIndicators


@dataclass(slots=True, frozen=True)
class FieldNumIndicators:
    validated_fields: int
    insufficient_annotated_values: int
    poor_f1_score: int
    average_f1_score: int
    good_f1_score: int

    @staticmethod
    def new_for_field(
        num_annotated_values: int, f1_score_quality: FieldF1ScoreQuality
    ) -> FieldNumIndicators:
        return FieldNumIndicators(
            validated_fields=1,
            insufficient_annotated_values=(
                num_annotated_values
                < MINIMUM_ANNOTATED_VALUES_FOR_SUFFICIENT_DATA
            ),
            poor_f1_score=int(f1_score_quality is FieldF1ScoreQuality.POOR),
            average_f1_score=int(
                f1_score_quality is FieldF1ScoreQuality.AVERAGE
            ),
            good_f1_score=int(f1_score_quality is FieldF1ScoreQuality.GOOD),
        )

    @staticmethod
    def sum(summands: Iterable[FieldNumIndicators]) -> FieldNumIndicators:
        summands_tuple = tuple(summands)
        return FieldNumIndicators(
            validated_fields=sum(
                summand.validated_fields for summand in summands_tuple
            ),
            insufficient_annotated_values=sum(
                summand.insufficient_annotated_values
                for summand in summands_tuple
            ),
            poor_f1_score=sum(
                summand.poor_f1_score for summand in summands_tuple
            ),
            average_f1_score=sum(
                summand.average_f1_score for summand in summands_tuple
            ),
            good_f1_score=sum(
                summand.good_f1_score for summand in summands_tuple
            ),
        )


@dataclass(slots=True, frozen=True)
class ProjectScoreMinimums:
    for_average_project_score: float
    for_good_project_score: float
    for_excellent_project_score: float


class ProjectScoreQuality(Enum):
    POOR = proto.PROJECT_SCORE_QUALITY_POOR
    AVERAGE = proto.PROJECT_SCORE_QUALITY_AVERAGE
    GOOD = proto.PROJECT_SCORE_QUALITY_GOOD
    EXCELLENT = proto.PROJECT_SCORE_QUALITY_EXCELLENT

    @staticmethod
    def from_project_score(project_score: float) -> ProjectScoreQuality:
        rounded_project_score = round_like_javascript(
            project_score, _ROUNDING_PLACES_FOR_QUALITY
        )
        if rounded_project_score >= START_PROJECT_SCORE_QUALITY_EXCELLENT:
            return ProjectScoreQuality.EXCELLENT
        if rounded_project_score >= START_PROJECT_SCORE_QUALITY_GOOD:
            return ProjectScoreQuality.GOOD
        if rounded_project_score >= START_PROJECT_SCORE_QUALITY_AVERAGE:
            return ProjectScoreQuality.AVERAGE
        return ProjectScoreQuality.POOR


START_PROJECT_SCORE_QUALITY_AVERAGE = 0.5
START_PROJECT_SCORE_QUALITY_GOOD = 0.7
START_PROJECT_SCORE_QUALITY_EXCELLENT = 0.85


class FieldF1ScoreQuality(Enum):
    POOR = proto.FIELD_F1_SCORE_QUALITY_POOR
    AVERAGE = proto.FIELD_F1_SCORE_QUALITY_AVERAGE
    GOOD = proto.FIELD_F1_SCORE_QUALITY_GOOD

    @staticmethod
    def from_f1_score(f1_score: float) -> FieldF1ScoreQuality:
        rounded_f1_score = round_like_javascript(
            f1_score, _ROUNDING_PLACES_FOR_QUALITY
        )
        if rounded_f1_score >= START_FIELD_F1_SCORE_QUALITY_GOOD:
            return FieldF1ScoreQuality.GOOD
        if rounded_f1_score >= START_FIELD_F1_SCORE_QUALITY_AVERAGE:
            return FieldF1ScoreQuality.AVERAGE
        return FieldF1ScoreQuality.POOR


MINIMUM_ANNOTATED_VALUES_FOR_SUFFICIENT_DATA = 10
START_FIELD_F1_SCORE_QUALITY_AVERAGE = 0.5
START_FIELD_F1_SCORE_QUALITY_GOOD = 0.7


@dataclass(slots=True, frozen=True)
class LatencyMetrics:
    p99: float
    p95: float
    p50: float


@dataclass(slots=True, frozen=True)
class IxpDocumentsMetrics:
    mean_document_field_error_rate: float
    mean_num_pages_per_document: float | None
    document_metrics: tuple[IxpDocumentMetrics, ...]


@dataclass(slots=True, frozen=True)
class IxpDocumentMetrics:
    field_error_rate: float


@dataclass(slots=True, frozen=True)
class PredictionAndGroundTruth:
    test_comment_index: TestCommentIndex
    field_group_name: LabelName
    i_extraction: int
    field_id: ExtractionFieldId
    predicted_value: str | None
    ground_truth_value: str | None
    is_match: bool
    confidence: float | None

    def document_sort_key(self) -> TestCommentIndex:
        return self.test_comment_index


def raw_ixp_metrics_to_summary(
    # Need order of field group names, so typed as `FrozenDict` not `Mapping`
    field_group_name_to_field_ids: FrozenDict[
        LabelName, tuple[ExtractionFieldId, ...]
    ],
    document_ids: Sequence[InternalCommentId],
    raw_ixp_metrics: RawIxpMetrics,
    raw_moon_metrics: RawMoonMetrics,
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> IxpSummaryMetrics | None:
    # Raw IXP metrics were empty in legacy (in `production` = before
    # 2025-12-03-16-38). For IXP-UCD, but not CM, the number of documents must
    # match the number of document ids. There's no way, however, to tell a
    # legacy IXP-UCD dataset from a CM moon dataset. The inequality condition
    # covers the edge case where, after 2025-12-03-16-38, a CM moon dataset has
    # some, but not all, of its test documents possessing attachments.
    return _raw_ixp_metrics_to_summary(
        field_group_name_to_field_ids=field_group_name_to_field_ids,
        document_ids=document_ids,
        raw=(
            RawIxpMetricsFromMoon.from_moon(raw_moon_metrics)
            if (
                raw_ixp_metrics.is_empty()
                or raw_ixp_metrics.num_test_documents() != len(document_ids)
            )
            else raw_ixp_metrics
        ),
        field_id_to_inherits_from=field_id_to_inherits_from,
    )


def _raw_ixp_metrics_to_summary(
    # Need order of field group names, so typed as `FrozenDict` not `Mapping`
    field_group_name_to_field_ids: FrozenDict[
        LabelName, tuple[ExtractionFieldId, ...]
    ],
    document_ids: Sequence[InternalCommentId],
    raw: RawIxpMetrics | RawIxpMetricsFromMoon,
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> IxpSummaryMetrics | None:
    num_documents = raw.num_test_documents()

    field_group_and_fields_metrics = _get_field_group_and_fields_metrics(
        field_group_name_to_field_ids,
        raw.field_groups_extractions,
        field_id_to_inherits_from,
    )
    if len(field_group_and_fields_metrics) == 0:
        return None
    field_groups_metrics = FrozenDict(
        {
            field_group_name: field_group_metrics.field_group
            for (
                field_group_name,
                field_group_metrics,
            ) in field_group_and_fields_metrics.items()
        }
    )
    fields_metrics = FrozenDict(
        {
            field_group_name: field_group_metrics.fields
            for (
                field_group_name,
                field_group_metrics,
            ) in field_group_and_fields_metrics.items()
        }
    )

    field_f1_scores = tuple(
        field_metric.f1_score.value
        for field_group_fields_metrics in fields_metrics.values()
        for field_metric in field_group_fields_metrics.values()
    )
    if len(field_f1_scores) == 0:
        return None

    project_score = mean(field_f1_scores)

    document_field_error_rates = _get_document_ordered_field_error_rates(
        num_documents=num_documents,
        field_groups_documents_metrics=tuple(
            field_group_metrics.documents
            for field_group_metrics in field_group_and_fields_metrics.values()
        ),
    )
    num_pages_per_document = (
        _get_num_pages_per_document(raw.test_document_metadatas)
        if isinstance(raw, RawIxpMetrics)
        else None
    )

    i_document_to_all_prediction_and_ground_truths: dict[
        TestCommentIndex, list[PredictionAndGroundTruth]
    ] = defaultdict(list)
    for (
        field_group_and_field_metrics
    ) in field_group_and_fields_metrics.values():
        for (
            i_document,
            document_prediction_and_ground_truths,
        ) in field_group_and_field_metrics.i_document_to_prediction_and_ground_truths.items():
            i_document_to_all_prediction_and_ground_truths[i_document].extend(
                document_prediction_and_ground_truths
            )

    return IxpSummaryMetrics(
        num_train_documents=raw.num_train_documents(),
        num_validated_documents=raw.num_test_documents(),
        project_score=project_score,
        project_indicators=ProjectIndicators(
            project_score_quality=ProjectScoreQuality.from_project_score(
                project_score
            ),
            field_num_indicators=FieldNumIndicators.sum(
                field_group_metrics.indicators.field_num_indicators
                for field_group_metrics in field_groups_metrics.values()
            ),
        ),
        ixp_metrics=IxpMetrics(
            field_groups_metrics=field_groups_metrics,
            fields_metrics=fields_metrics,
        ),
        latency_metrics=None,
        document_ids=tuple(document_ids),
        document_names=(
            tuple(
                document_metadata.filename
                for document_metadata in raw.test_document_metadatas
            )
            if isinstance(raw, RawIxpMetrics)
            else tuple(
                f"Document {i_document}"
                for i_document in range(1, num_documents + 1)
            )
        ),
        documents_metrics=IxpDocumentsMetrics(
            mean_document_field_error_rate=(
                mean(document_field_error_rates)
                if len(document_field_error_rates) > 0
                else 0.0
            ),  # As `else` should only occur if no documents
            mean_num_pages_per_document=(
                mean(num_pages_per_document)
                if (
                    num_pages_per_document is not None
                    and len(num_pages_per_document) > 0
                )
                else None
            ),
            document_metrics=tuple(
                IxpDocumentMetrics(field_error_rate=document_field_error_rate)
                for document_field_error_rate in document_field_error_rates
            ),
        ),
        prediction_and_ground_truths=tuple(
            prediction_and_ground_truth
            for i_document in sorted(
                i_document_to_all_prediction_and_ground_truths
            )
            for (
                prediction_and_ground_truth
            ) in i_document_to_all_prediction_and_ground_truths[i_document]
        ),
    )


def _get_field_group_and_fields_metrics(
    field_group_name_to_field_ids: FrozenDict[
        LabelName, tuple[ExtractionFieldId, ...]
    ],
    raw_field_groups_extractions: Mapping[LabelName, RawCaptures],
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> FrozenDict[LabelName, _FieldGroupAndFieldsMetrics]:
    field_group_and_fields_metrics: dict[
        LabelName, _FieldGroupAndFieldsMetrics
    ] = {}
    i_document_to_i_extraction: defaultdict[TestCommentIndex, int] = (
        defaultdict(lambda: -1)
    )
    for field_group_name in field_group_name_to_field_ids:
        raw_extractions = raw_field_groups_extractions.get(field_group_name)
        if raw_extractions is None or (
            raw_extractions.test_assigned.num_captures() == 0
            and raw_extractions.test_predicted.num_captures() == 0
        ):
            continue
        (
            field_group_and_fields_metrics[field_group_name],
            i_document_to_i_extraction,
        ) = _raw_field_group_to_metrics(
            i_document_to_i_extraction=i_document_to_i_extraction,
            field_group_name=field_group_name,
            field_ids=field_group_name_to_field_ids[field_group_name],
            raw_extractions=raw_extractions,
            field_id_to_inherits_from=field_id_to_inherits_from,
        )

    return FrozenDict(field_group_and_fields_metrics)


def _raw_field_group_to_metrics(
    i_document_to_i_extraction: defaultdict[TestCommentIndex, int],
    field_group_name: LabelName,
    field_ids: tuple[ExtractionFieldId, ...],
    raw_extractions: RawCaptures,
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> tuple[_FieldGroupAndFieldsMetrics, defaultdict[TestCommentIndex, int]]:
    document_indices, documents_matched_captures = _get_document_matches(
        raw_extractions, field_id_to_inherits_from
    )
    # Compute test set counts
    field_id_to_counts_by_document = _FieldToCountsByDocument.empty()
    num_annotated_documents = 0
    populated_field_ids: set[ExtractionFieldId] = set()
    i_document_to_prediction_and_ground_truths: dict[
        TestCommentIndex, list[PredictionAndGroundTruth]
    ] = defaultdict(list)
    for i_document, matched_captures in zip(
        document_indices, documents_matched_captures, strict=True
    ):
        num_annotated_documents += int(
            len(matched_captures.matched)
            + len(matched_captures.unmatched_assigned)
            > 0
        )

        document_true_positives = _get_field_id_to_int_defaultdict()
        document_true_negatives = _get_field_id_to_int_defaultdict()
        document_false_positive_and_negatives = (
            _get_field_id_to_int_defaultdict()
        )
        document_false_positive_onlys = _get_field_id_to_int_defaultdict()
        document_false_negative_onlys = _get_field_id_to_int_defaultdict()
        document_num_annotated_values = _get_field_id_to_int_defaultdict()
        document_num_annotated_missings = _get_field_id_to_int_defaultdict()

        for matched_capture in matched_captures.matched:
            i_document_to_i_extraction[i_document] += 1
            populated_field_ids.update(matched_capture.fields.keys())
            for field_id in field_ids:
                matched_field = matched_capture.fields.get(field_id)
                if matched_field is None:
                    continue
                is_match = False
                if matched_field.assigned is not None:
                    document_num_annotated_values[field_id] += 1
                else:
                    document_num_annotated_missings[field_id] += 1

                match (matched_field.assigned, matched_field.predicted):
                    case (None, None):
                        document_true_negatives[field_id] += 1
                        is_match = True
                    case (None, _):
                        document_false_positive_onlys[field_id] += 1
                    case (_, None):
                        document_false_negative_onlys[field_id] += 1
                    case (_, _) if matched_field.is_correct():
                        document_true_positives[field_id] += 1
                        is_match = True
                    case _:
                        document_false_positive_and_negatives[field_id] += 1
                i_document_to_prediction_and_ground_truths[i_document].append(
                    PredictionAndGroundTruth(
                        test_comment_index=i_document,
                        field_group_name=field_group_name,
                        i_extraction=i_document_to_i_extraction[i_document],
                        field_id=field_id,
                        predicted_value=matched_field.predicted,
                        ground_truth_value=matched_field.assigned,
                        is_match=is_match,
                        confidence=matched_field.confidence,
                    )
                )

        for predicted_capture in matched_captures.unmatched_predicted:
            i_document_to_i_extraction[i_document] += 1
            populated_field_ids.update(predicted_capture.fields.keys())
            for field_id in field_ids:
                predicted_field = predicted_capture.fields.get(field_id)
                if predicted_field is None:
                    continue
                if predicted_field.value is not None:
                    document_false_positive_onlys[field_id] += 1
                i_document_to_prediction_and_ground_truths[i_document].append(
                    PredictionAndGroundTruth(
                        test_comment_index=i_document,
                        field_group_name=field_group_name,
                        i_extraction=i_document_to_i_extraction[i_document],
                        field_id=field_id,
                        predicted_value=predicted_field.value,
                        ground_truth_value=None,
                        is_match=False,
                        confidence=predicted_field.confidence,
                    )
                )

        for assigned_capture in matched_captures.unmatched_assigned:
            i_document_to_i_extraction[i_document] += 1
            populated_field_ids.update(assigned_capture.fields.keys())
            for field_id in field_ids:
                assigned_field = assigned_capture.fields.get(field_id)
                if assigned_field is None:
                    continue
                if assigned_field.value is not None:
                    document_num_annotated_values[field_id] += 1
                    document_false_negative_onlys[field_id] += 1
                else:
                    document_num_annotated_missings[field_id] += 1
                i_document_to_prediction_and_ground_truths[i_document].append(
                    PredictionAndGroundTruth(
                        test_comment_index=i_document,
                        field_group_name=field_group_name,
                        i_extraction=i_document_to_i_extraction[i_document],
                        field_id=field_id,
                        predicted_value=None,
                        ground_truth_value=assigned_field.value,
                        is_match=False,
                        confidence=assigned_field.confidence,
                    )
                )

        field_id_to_counts_by_document = field_id_to_counts_by_document.new_with_appended(
            true_positives=document_true_positives,
            true_negatives=document_true_negatives,
            false_positive_and_negatives=document_false_positive_and_negatives,
            false_positive_onlys=document_false_positive_onlys,
            false_negative_onlys=document_false_negative_onlys,
            num_annotated_values=document_num_annotated_values,
            num_annotated_missings=document_num_annotated_missings,
        )

    # Get field metrics and field group metrics for the current field group
    fields_metrics = FrozenDict(
        {
            field_id: _get_ixp_level_metrics(
                counts_by_document=_CountsByDocument.new_for_field(
                    field_id_to_counts_by_document, field_id
                ),
                num_annotated_documents=num_annotated_documents,
                field_num_indicators=None,
            )
            for field_id in field_ids
            if field_id in populated_field_ids
        }
    )
    field_group_counts = _CountsByDocument.sum_over_fields(
        field_id_to_counts_by_document
    )
    field_group_metrics = _get_ixp_level_metrics(
        counts_by_document=field_group_counts,
        num_annotated_documents=num_annotated_documents,
        field_num_indicators=FieldNumIndicators.sum(
            field_metrics.indicators.field_num_indicators
            for field_metrics in fields_metrics.values()
        ),
    )
    return _FieldGroupAndFieldsMetrics(
        field_group=field_group_metrics,
        documents=_FieldGroupDocumentsMetrics(
            indices=document_indices,
            num_annotateds=field_group_counts.num_annotateds(),
            num_errors=field_group_counts.num_errors(),
        ),
        fields=fields_metrics,
        i_document_to_prediction_and_ground_truths=FrozenDict(
            {
                i_document: tuple(prediction_and_ground_truths)
                for (
                    i_document,
                    prediction_and_ground_truths,
                ) in i_document_to_prediction_and_ground_truths.items()
            }
        ),
    ), i_document_to_i_extraction


def _get_document_ordered_field_error_rates(
    num_documents: int,
    field_groups_documents_metrics: Sequence[_FieldGroupDocumentsMetrics],
) -> tuple[float, ...]:
    i_document_to_num_annotateds: dict[TestCommentIndex, int] = defaultdict(
        int
    )
    i_document_to_num_errors: dict[TestCommentIndex, int] = defaultdict(int)
    for field_group_documents_metrics in field_groups_documents_metrics:
        for i_document, num_annotated, num_errors in zip(
            field_group_documents_metrics.indices,
            field_group_documents_metrics.num_annotateds,
            field_group_documents_metrics.num_errors,
            strict=True,
        ):
            i_document_to_num_annotateds[i_document] += num_annotated
            i_document_to_num_errors[i_document] += num_errors
    field_error_rates: list[float] = []
    for document_index in range(num_documents):
        test_comment_index = TestCommentIndex(document_index)
        num_annotateds = i_document_to_num_annotateds.get(
            test_comment_index, 0
        )
        num_errors = i_document_to_num_errors.get(test_comment_index, 0)
        field_error_rates.append(
            num_errors / num_annotateds
            if num_annotateds > 0
            else _get_error_rate_zero_division_result(num_errors)
        )
    return tuple(field_error_rates)


def _get_num_pages_per_document(
    document_metadatas: Sequence[DocumentMetadata],
) -> tuple[int, ...] | None:
    num_pages_per_document: list[int] = []
    for document_metadata in document_metadatas:
        if document_metadata.num_pages is None:
            return None
        num_pages_per_document.append(document_metadata.num_pages)
    return tuple(num_pages_per_document)


def _get_document_matches(
    raw_extractions: RawCaptures,
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> tuple[tuple[TestCommentIndex, ...], tuple[DocumentCaptureMatch, ...]]:
    (document_indices, predicted_extractions, assigned_extractions) = (
        _raw_to_test_extractions(raw_extractions)
    )
    pr_predictions = []
    documents_matched_captures = []
    num_test_captures = 0
    for document_predicted, document_assigned in zip(
        predicted_extractions, assigned_extractions, strict=True
    ):
        matched_captures = match_captures(
            predicted=document_predicted,
            assigned=document_assigned,
            field_id_to_inherits_from=field_id_to_inherits_from,
        )
        documents_matched_captures.append(matched_captures)

        for matched_capture in matched_captures.matched:
            num_test_captures += 1
            pr_predictions.append(
                PRPrediction(
                    score=matched_capture.confidence,
                    assigned=matched_capture.is_perfect(),
                )
            )

        for predicted_capture in matched_captures.unmatched_predicted:
            pr_predictions.append(
                PRPrediction(
                    score=predicted_capture.confidence, assigned=False
                )
            )
        for _ in matched_captures.unmatched_assigned:
            num_test_captures += 1

    return (document_indices, tuple(documents_matched_captures))


def _get_ixp_level_metrics(
    counts_by_document: _CountsByDocument,
    num_annotated_documents: int,
    field_num_indicators: FieldNumIndicators | None,
) -> IxpLevelMetrics:
    field_num_errors = counts_by_document.num_errors()
    field_num_value_errors = counts_by_document.num_value_errors()
    field_documents_with_errors = tuple(
        1 if field_document_num_errors > 0 else 0
        for field_document_num_errors in field_num_errors
    )

    document_ones = counts_by_document.document_ones()

    field_pr_point = _IxpPRPoint.new(
        true_positives=counts_by_document.true_positives,
        false_positives=counts_by_document.false_positives(),
        false_negatives=counts_by_document.false_negatives(),
    )
    field_f1_score_quality = FieldF1ScoreQuality.from_f1_score(
        field_pr_point.f1_score.value
    )
    field_num_annotateds = counts_by_document.num_annotateds()
    num_missing_errors = sum(counts_by_document.num_annotated_missings)
    return IxpLevelMetrics(
        f1_score=field_pr_point.f1_score,
        precision=field_pr_point.precision,
        recall=field_pr_point.recall,
        indicators=Indicators(
            f1_score_quality=field_f1_score_quality,
            field_num_indicators=(
                FieldNumIndicators.new_for_field(
                    num_annotated_values=sum(
                        counts_by_document.num_annotated_values
                    ),
                    f1_score_quality=field_f1_score_quality,
                )
                if field_num_indicators is None
                else field_num_indicators
            ),
        ),
        num_annotated_documents=num_annotated_documents,
        num_documents_with_errors=RangedValue.from_sum(
            counts=field_documents_with_errors, reference_counts=document_ones
        ),
        proportion_documents_with_errors=RangedValue.from_mean(
            numerators=field_documents_with_errors,
            denominators=document_ones,
            # Case where no documents
            zero_division_result=0.0,
        ),
        num_annotations=sum(field_num_annotateds),
        num_annotated_values=sum(counts_by_document.num_annotated_values),
        num_annotated_missing=sum(counts_by_document.num_annotated_missings),
        num_predictions=RangedValue.from_sum(
            counts=counts_by_document.num_predictions(),
            reference_counts=field_num_annotateds,
        ),
        error_rate=RangedValue.from_mean(
            numerators=field_num_errors,
            denominators=field_num_annotateds,
            # Case where no annotations, implying any errors are all extra predictions
            zero_division_result=_get_error_rate_zero_division_result(
                sum(field_num_errors)
            ),
        ),
        error_rate_missing_value=(
            sum(counts_by_document.false_positive_onlys) / num_missing_errors
            if num_missing_errors > 0
            else 0.0
        ),
        error_rate_excluding_missing=RangedValue.from_mean(
            numerators=field_num_value_errors,
            denominators=counts_by_document.num_annotated_values,
            zero_division_result=_get_error_rate_zero_division_result(
                sum(field_num_value_errors)
            ),
        ),
        num_errors=RangedValue.from_sum(
            counts=field_num_errors, reference_counts=field_num_annotateds
        ),
        num_value_errors=RangedValue.from_sum(
            counts=field_num_value_errors,
            reference_counts=counts_by_document.num_annotated_values,
        ),
        num_incorrect_predictions=RangedValue.from_sum(
            counts=counts_by_document.false_positive_and_negatives,
            reference_counts=field_num_annotateds,
        ),
        num_extra_predictions=RangedValue.from_sum(
            counts=counts_by_document.false_positive_onlys,
            reference_counts=field_num_annotateds,
        ),
        num_missed_predictions=RangedValue.from_sum(
            counts=counts_by_document.false_negative_onlys,
            reference_counts=field_num_annotateds,
        ),
        num_correct_value_predictions=RangedValue.from_sum(
            counts=counts_by_document.true_positives,
            reference_counts=counts_by_document.num_annotated_values,
        ),
        num_correct_missing_predictions=RangedValue.from_sum(
            counts=counts_by_document.true_negatives,
            reference_counts=counts_by_document.num_annotated_missings,
        ),
    )


def _raw_to_test_extractions(
    raw_extractions: RawCaptures,
) -> tuple[
    tuple[TestCommentIndex, ...],
    MoonDocumentIntentCaptures,
    MoonDocumentIntentCaptures,
]:
    all_indices: set[TestCommentIndex] = set()
    predicted_captures_by_index: dict[
        TestCommentIndex, tuple[RawCapture, ...]
    ] = {}
    assigned_captures_by_index: dict[
        TestCommentIndex, tuple[RawCapture, ...]
    ] = {}
    for current_captures_by_index, current_raw_captures in (
        (predicted_captures_by_index, raw_extractions.test_predicted),
        (assigned_captures_by_index, raw_extractions.test_assigned),
    ):
        for comment_index, comment_captures in zip(
            current_raw_captures.indices,
            current_raw_captures.captures,
            strict=True,
        ):
            all_indices.add(comment_index)
            current_captures_by_index[comment_index] = comment_captures

    predicted_extractions: list[tuple[RawCapture, ...]] = []
    annotated_extractions: list[tuple[RawCapture, ...]] = []

    sorted_indices = sorted(all_indices)
    for comment_index in sorted_indices:
        for current_captures, current_capture_dict in (
            (predicted_extractions, predicted_captures_by_index),
            (annotated_extractions, assigned_captures_by_index),
        ):
            current_captures.append(
                current_capture_dict.get(comment_index, ())
            )
    return (
        tuple(sorted_indices),
        tuple(predicted_extractions),
        tuple(annotated_extractions),
    )


def _get_field_id_to_int_defaultdict() -> defaultdict[ExtractionFieldId, int]:
    return defaultdict(int)


def _get_error_rate_zero_division_result(numerator: int) -> float:
    return 0.0 if numerator == 0 else 1.0


@dataclass(slots=True, frozen=True)
class _IxpPRPoint:
    precision: RangedValue[float]
    recall: RangedValue[float]
    f1_score: RangedValue[float]

    @staticmethod
    def new(
        true_positives: Sequence[int],
        false_positives: Sequence[int],
        false_negatives: Sequence[int],
    ) -> _IxpPRPoint:
        """Assumes there is at least one annotation or one prediction in total"""
        num_predicted_values = tuple(
            true_positive + false_positive
            for true_positive, false_positive in zip(
                true_positives, false_positives, strict=True
            )
        )
        num_annotated_values = tuple(
            true_positive + false_negative
            for true_positive, false_negative in zip(
                true_positives, false_negatives, strict=True
            )
        )
        precision_f1_zero_division_result = (
            1.0 if sum(true_positives) == 0 else 0.0
        )
        return _IxpPRPoint(
            precision=RangedValue.from_mean(
                numerators=true_positives,
                denominators=num_predicted_values,
                zero_division_result=precision_f1_zero_division_result,
            ),
            recall=RangedValue.from_mean(
                numerators=true_positives,
                denominators=num_annotated_values,
                # No annotations implies perfect (empty) true positives
                zero_division_result=1.0,
            ),
            # F1 Score can also be written as:
            # num_true_positives /
            #       ( (num_predicted_values + num_annotated_values) / 2 )
            f1_score=RangedValue.from_mean(
                numerators=true_positives,
                denominators=tuple(
                    (num_predicted_value + num_annotated_value) / 2
                    for num_predicted_value, num_annotated_value in zip(
                        num_predicted_values, num_annotated_values, strict=True
                    )
                ),
                zero_division_result=precision_f1_zero_division_result,
            ),
        )


@dataclass(slots=True, frozen=True)
class _FieldGroupAndFieldsMetrics:
    field_group: IxpLevelMetrics
    documents: _FieldGroupDocumentsMetrics
    fields: FrozenDict[ExtractionFieldId, IxpLevelMetrics]
    i_document_to_prediction_and_ground_truths: FrozenDict[
        TestCommentIndex, tuple[PredictionAndGroundTruth, ...]
    ]


@dataclass(slots=True, frozen=True)
class _FieldGroupDocumentsMetrics:
    indices: tuple[TestCommentIndex, ...]
    num_annotateds: tuple[int, ...]
    num_errors: tuple[int, ...]

    def __post_init__(self) -> None:
        assert (
            len(self.indices)
            == len(self.num_annotateds)
            == len(self.num_errors)
        ), (
            f"num_documents: {len(self.indices)}, num_annotated: "
            f"{len(self.num_annotateds)} and num_errors: "
            f"{len(self.num_errors)} must be equal"
        )


@dataclass(slots=True, frozen=True)
class _FieldToCountsByDocument:
    true_positives: tuple[FrozenDict[ExtractionFieldId, int], ...]
    true_negatives: tuple[FrozenDict[ExtractionFieldId, int], ...]
    false_positive_and_negatives: tuple[
        FrozenDict[ExtractionFieldId, int], ...
    ]
    false_positive_onlys: tuple[FrozenDict[ExtractionFieldId, int], ...]
    false_negative_onlys: tuple[FrozenDict[ExtractionFieldId, int], ...]
    num_annotated_values: tuple[FrozenDict[ExtractionFieldId, int], ...]
    num_annotated_missings: tuple[FrozenDict[ExtractionFieldId, int], ...]

    @staticmethod
    def empty() -> _FieldToCountsByDocument:
        return _FieldToCountsByDocument(
            true_positives=(),
            true_negatives=(),
            false_positive_and_negatives=(),
            false_positive_onlys=(),
            false_negative_onlys=(),
            num_annotated_values=(),
            num_annotated_missings=(),
        )

    def new_with_appended(
        self,
        true_positives: Mapping[ExtractionFieldId, int],
        true_negatives: Mapping[ExtractionFieldId, int],
        false_positive_and_negatives: Mapping[ExtractionFieldId, int],
        false_positive_onlys: Mapping[ExtractionFieldId, int],
        false_negative_onlys: Mapping[ExtractionFieldId, int],
        num_annotated_values: Mapping[ExtractionFieldId, int],
        num_annotated_missings: Mapping[ExtractionFieldId, int],
    ) -> _FieldToCountsByDocument:
        return _FieldToCountsByDocument(
            true_positives=self.true_positives + (FrozenDict(true_positives),),
            true_negatives=self.true_negatives + (FrozenDict(true_negatives),),
            false_positive_and_negatives=self.false_positive_and_negatives
            + (FrozenDict(false_positive_and_negatives),),
            false_positive_onlys=self.false_positive_onlys
            + (FrozenDict(false_positive_onlys),),
            false_negative_onlys=self.false_negative_onlys
            + (FrozenDict(false_negative_onlys),),
            num_annotated_values=self.num_annotated_values
            + (FrozenDict(num_annotated_values),),
            num_annotated_missings=self.num_annotated_missings
            + (FrozenDict(num_annotated_missings),),
        )


@dataclass(slots=True, frozen=True)
class _CountsByDocument:
    true_positives: tuple[int, ...]
    true_negatives: tuple[int, ...]
    false_positive_and_negatives: tuple[int, ...]
    false_positive_onlys: tuple[int, ...]
    false_negative_onlys: tuple[int, ...]
    num_annotated_values: tuple[int, ...]
    num_annotated_missings: tuple[int, ...]

    @staticmethod
    def empty() -> _CountsByDocument:
        return _CountsByDocument(
            true_positives=(),
            true_negatives=(),
            false_positive_and_negatives=(),
            false_positive_onlys=(),
            false_negative_onlys=(),
            num_annotated_values=(),
            num_annotated_missings=(),
        )

    @staticmethod
    def new_for_field(
        field_to_counts_by_document: _FieldToCountsByDocument,
        field_id: ExtractionFieldId,
    ) -> _CountsByDocument:
        return _CountsByDocument(
            true_positives=_get_for_field_id(
                field_to_counts_by_document.true_positives, field_id
            ),
            true_negatives=_get_for_field_id(
                field_to_counts_by_document.true_negatives, field_id
            ),
            false_positive_and_negatives=_get_for_field_id(
                field_to_counts_by_document.false_positive_and_negatives,
                field_id,
            ),
            false_positive_onlys=_get_for_field_id(
                field_to_counts_by_document.false_positive_onlys, field_id
            ),
            false_negative_onlys=_get_for_field_id(
                field_to_counts_by_document.false_negative_onlys, field_id
            ),
            num_annotated_values=_get_for_field_id(
                field_to_counts_by_document.num_annotated_values, field_id
            ),
            num_annotated_missings=_get_for_field_id(
                field_to_counts_by_document.num_annotated_missings, field_id
            ),
        )

    @staticmethod
    def sum_over_fields(
        field_to_counts_by_document: _FieldToCountsByDocument,
    ) -> _CountsByDocument:
        return _CountsByDocument(
            true_positives=_sum_over_field(
                field_to_counts_by_document.true_positives
            ),
            true_negatives=_sum_over_field(
                field_to_counts_by_document.true_negatives
            ),
            false_positive_and_negatives=_sum_over_field(
                field_to_counts_by_document.false_positive_and_negatives
            ),
            false_positive_onlys=_sum_over_field(
                field_to_counts_by_document.false_positive_onlys
            ),
            false_negative_onlys=_sum_over_field(
                field_to_counts_by_document.false_negative_onlys
            ),
            num_annotated_values=_sum_over_field(
                field_to_counts_by_document.num_annotated_values
            ),
            num_annotated_missings=_sum_over_field(
                field_to_counts_by_document.num_annotated_missings
            ),
        )

    def false_positives(self) -> tuple[int, ...]:
        return _add_itemwise(
            self.false_positive_and_negatives, self.false_positive_onlys
        )

    def false_negatives(self) -> tuple[int, ...]:
        return _add_itemwise(
            self.false_positive_and_negatives, self.false_negative_onlys
        )

    def num_errors(self) -> tuple[int, ...]:
        return _add_itemwise(self.false_positives(), self.false_negative_onlys)

    def num_value_errors(self) -> tuple[int, ...]:
        return _add_itemwise(
            self.false_positive_and_negatives, self.false_negative_onlys
        )

    def num_annotateds(self) -> tuple[int, ...]:
        return _add_itemwise(
            self.num_annotated_values, self.num_annotated_missings
        )

    def num_predictions(self) -> tuple[int, ...]:
        return _add_itemwise(self.true_positives, self.false_positives())

    def document_ones(self) -> tuple[int, ...]:
        return tuple(1 for _ in self.true_positives)


def _sum_over_field(
    field_to_count_by_document: Sequence[Mapping[ExtractionFieldId, int]],
) -> tuple[int, ...]:
    return tuple(
        sum(field_to_count.values())
        for field_to_count in field_to_count_by_document
    )


def _get_for_field_id(
    field_id_to_counts: Sequence[Mapping[ExtractionFieldId, int]],
    field_id: ExtractionFieldId,
) -> tuple[int, ...]:
    return tuple(
        field_id_to_count.get(field_id, 0)
        for field_id_to_count in field_id_to_counts
    )


def _add_itemwise(ms: Sequence[int], ns: Sequence[int]) -> tuple[int, ...]:
    return tuple(m + n for m, n in zip(ms, ns, strict=True))


_ROUNDING_PLACES_FOR_QUALITY = 2
