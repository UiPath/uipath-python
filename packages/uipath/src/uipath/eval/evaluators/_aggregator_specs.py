"""Aggregator specs embedded in per-datapoint classification evaluator configs.

Each aggregator is a run-level metric (precision / recall / f-score) attached
to a classification evaluator. Classes are declared once on the parent evaluator
config — every aggregator on the same evaluator operates on the same class
vocabulary, so the field is not repeated per spec. Only the metric-shape fields
(``averaging`` and, for fscore, ``f_value``) live on the spec itself.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _AggregatorSpecBase(BaseModel):
    """Shared pydantic config for every aggregator variant."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PrecisionAggregatorSpec(_AggregatorSpecBase):
    """Run-level precision aggregator (multiclass, micro or macro averaged)."""

    type: Literal["precision"] = "precision"
    averaging: Literal["macro", "micro"]


class RecallAggregatorSpec(_AggregatorSpecBase):
    """Run-level recall aggregator (multiclass, micro or macro averaged)."""

    type: Literal["recall"] = "recall"
    averaging: Literal["macro", "micro"]


class FScoreAggregatorSpec(_AggregatorSpecBase):
    """Run-level F-beta aggregator (multiclass, micro or macro averaged)."""

    type: Literal["fscore"] = "fscore"
    averaging: Literal["macro", "micro"]
    f_value: float = Field(default=1.0, gt=0)


AggregatorSpec = Annotated[
    Union[PrecisionAggregatorSpec, RecallAggregatorSpec, FScoreAggregatorSpec],
    Field(discriminator="type"),
]
