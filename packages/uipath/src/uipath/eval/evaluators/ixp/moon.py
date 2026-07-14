"""The capture-matching slice of ixp-platform's metrics/moon.py, ported
verbatim (attrs → dataclasses, scipy → .assignment). Only the symbols the IXP
scoring path needs are kept; the full-moon-summary / PR-curve machinery is
deliberately out of scope.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, NewType

from ._compat import (
    ENTITY_DEF_ID_DATE,
    ENTITY_DEF_ID_EXTRACTION_BOOLEAN,
    ENTITY_DEF_ID_EXTRACTION_CHOICE,
    ENTITY_DEF_ID_EXTRACTION_NUMBER,
    ENTITY_DEF_ID_MONEY,
    BuiltinEntityDefId,
    ChoiceFieldFlag,
    CommentIndex,
    ExtractionFieldId,
    FrozenDict,
    LabelName,
    TestCommentIndex,
    TrainCommentIndex,
)
from .assignment import linear_sum_assignment
from .data_type_utils import (
    process_amount_field_value as mls_process_amount_field_value,
    process_bool_field_value as mls_process_bool_field_value,
    process_choice_field_value as mls_process_choice_field_value,
    process_date_field_value as mls_process_date_field_value,
    process_monetary_field_value as mls_process_monetary_field_value,
)
from .extraction import FieldValuePrediction, TextExtraction

CaptureConfidence = NewType("CaptureConfidence", float)
RawMoonValue = NewType("RawMoonValue", str)

_EMPTY_INHERITS_FROM: tuple[BuiltinEntityDefId, ...] = ()


@dataclass(slots=True, frozen=True)
class RawMoonField:
    value: "RawMoonValue | None"
    confidence: float


@dataclass(slots=True, frozen=True)
class RawCapture:
    fields: FrozenDict[ExtractionFieldId, RawMoonField]
    confidence: CaptureConfidence


@dataclass(slots=True, frozen=True)
class RawCommentCaptures(Generic[CommentIndex]):
    indices: tuple[CommentIndex, ...]
    captures: tuple[tuple[RawCapture, ...], ...]

    def num_captures(self) -> int:
        return sum(len(captures) for captures in self.captures)


@dataclass(slots=True, frozen=True)
class RawCaptures:
    train_assigned: RawCommentCaptures[TrainCommentIndex]
    train_dismissed: RawCommentCaptures[TrainCommentIndex]

    test_assigned: RawCommentCaptures[TestCommentIndex]
    test_dismissed: RawCommentCaptures[TestCommentIndex]
    test_predicted: RawCommentCaptures[TestCommentIndex]


@dataclass(slots=True)
class RawMoonIntent:
    # upstream: metrics/labels.py RawLabel; the IXP path never reads it, so it
    # stays opaque here
    label: Any
    captures: RawCaptures


@dataclass(slots=True)
class RawMoonMetrics:
    raw_intents: FrozenDict[LabelName, RawMoonIntent]
    num_train_documents: int
    num_test_documents: int

    @staticmethod
    def empty() -> "RawMoonMetrics":
        return RawMoonMetrics(
            num_train_documents=0,
            num_test_documents=0,
            raw_intents=FrozenDict(),
        )


def get_field_value_prediction(
    inherits_from: tuple[BuiltinEntityDefId, ...], value: str
) -> "FieldValuePrediction | None":
    if ENTITY_DEF_ID_EXTRACTION_BOOLEAN in inherits_from:
        return mls_process_bool_field_value(
            raw_value=value, true_formatted=None, false_formatted=None
        )
    elif ENTITY_DEF_ID_EXTRACTION_NUMBER in inherits_from:
        return mls_process_amount_field_value(raw_value=value)
    elif ENTITY_DEF_ID_MONEY in inherits_from:
        return mls_process_monetary_field_value(raw_value=value)
    elif ENTITY_DEF_ID_DATE in inherits_from:
        return mls_process_date_field_value(
            raw_value=value, two_ambiguity=None, three_ambiguity=None
        )
    elif ENTITY_DEF_ID_EXTRACTION_CHOICE in inherits_from:
        return mls_process_choice_field_value(
            raw_value=value,
            choices=(),
            flags=frozenset({ChoiceFieldFlag.ALLOW_OUT_OF_DOMAIN}),
        )
    return FieldValuePrediction(formatted=value, extraction=TextExtraction())


MoonDocumentIntentCaptures = tuple[tuple[RawCapture, ...], ...]


@dataclass(slots=True, frozen=True)
class _MatchedField:
    predicted: "RawMoonValue | None"
    assigned: "RawMoonValue | None"
    confidence: "float | None"
    inherits_from: tuple[BuiltinEntityDefId, ...]

    def is_correct(self) -> bool:
        return moon_extractions_are_equal(
            self.predicted, self.assigned, self.inherits_from
        )


def moon_extractions_are_equal(
    predicted: "RawMoonValue | None",
    assigned: "RawMoonValue | None",
    inherits_from: tuple[BuiltinEntityDefId, ...],
) -> bool:
    if predicted is None and assigned is None:
        return True
    if predicted is None or assigned is None:
        return False
    if len(inherits_from) > 0:
        predicted_extraction = get_field_value_prediction(
            inherits_from, predicted
        )
        assigned_extraction = get_field_value_prediction(
            inherits_from, assigned
        )
        if (
            predicted_extraction is not None
            and assigned_extraction is not None
        ):
            if not (
                isinstance(predicted_extraction.extraction, TextExtraction)
                and isinstance(assigned_extraction.extraction, TextExtraction)
            ):
                return (
                    predicted_extraction.extraction
                    == assigned_extraction.extraction
                    or predicted == assigned
                )
    return predicted == assigned


@dataclass(slots=True, frozen=True)
class _MatchedCapture:
    fields: FrozenDict[ExtractionFieldId, _MatchedField]
    confidence: CaptureConfidence

    def is_perfect(self) -> bool:
        return all(field.is_correct() for field in self.fields.values())

    @staticmethod
    def from_raw_captures(
        predicted: RawCapture,
        assigned: RawCapture,
        field_id_to_inherits_from: Mapping[
            ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
        ],
    ) -> "_MatchedCapture":
        fields = {
            field_id: _MatchedField(
                predicted=field.value,
                assigned=(
                    assigned_field.value
                    if (assigned_field := assigned.fields.get(field_id))
                    is not None
                    else None
                ),
                confidence=field.confidence,
                inherits_from=field_id_to_inherits_from.get(
                    field_id, _EMPTY_INHERITS_FROM
                ),
            )
            for field_id, field in predicted.fields.items()
        }
        for field_id, field in assigned.fields.items():
            if field_id not in fields:
                fields[field_id] = _MatchedField(
                    predicted=None,
                    assigned=field.value,
                    confidence=None,
                    inherits_from=field_id_to_inherits_from.get(
                        field_id, _EMPTY_INHERITS_FROM
                    ),
                )

        return _MatchedCapture(
            fields=FrozenDict(fields), confidence=predicted.confidence
        )


@dataclass(slots=True, frozen=True)
class DocumentCaptureMatch:
    matched: tuple[_MatchedCapture, ...]
    unmatched_predicted: tuple[RawCapture, ...]
    unmatched_assigned: tuple[RawCapture, ...]


def match_captures(
    predicted: Sequence[RawCapture],
    assigned: Sequence[RawCapture],
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> DocumentCaptureMatch:
    exact_match_scores = [
        [
            _capture_similarity(
                predicted_capture, assigned_capture, field_id_to_inherits_from
            )
            for assigned_capture in assigned
        ]
        for predicted_capture in predicted
    ]

    if len(predicted) == 0 or len(assigned) == 0:
        predicted_indices: list[int] = []
        assigned_indices: list[int] = []
    else:
        predicted_indices, assigned_indices = linear_sum_assignment(
            exact_match_scores, maximize=True
        )

    return DocumentCaptureMatch(
        matched=tuple(
            _MatchedCapture.from_raw_captures(
                predicted[predicted_index],
                assigned[assigned_index],
                field_id_to_inherits_from,
            )
            for predicted_index, assigned_index in zip(
                predicted_indices, assigned_indices, strict=True
            )
        ),
        unmatched_predicted=tuple(
            predicted[unmatched_index]
            for unmatched_index in set(range(len(predicted))).difference(
                set(predicted_indices)
            )
        ),
        unmatched_assigned=tuple(
            assigned[unmatched_index]
            for unmatched_index in set(range(len(assigned))).difference(
                set(assigned_indices)
            )
        ),
    )


def _capture_similarity(
    predicted: RawCapture,
    assigned: RawCapture,
    field_id_to_inherits_from: Mapping[
        ExtractionFieldId, tuple[BuiltinEntityDefId, ...]
    ],
) -> float:
    # for empty captures, give score of 1 to other empty captures and 0 to
    # non-empty
    if len(predicted.fields) == 0:
        return 1.0 if len(assigned.fields) == 0 else 0.0
    # otherwise the score is the number of exactly matching fields
    return sum(
        1.0
        for field_id, predicted_field in predicted.fields.items()
        if (assigned_field := assigned.fields.get(field_id)) is not None
        and moon_extractions_are_equal(
            predicted_field.value,
            assigned_field.value,
            field_id_to_inherits_from.get(field_id, _EMPTY_INHERITS_FROM),
        )
    )
