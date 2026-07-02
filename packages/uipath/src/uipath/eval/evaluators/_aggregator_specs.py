"""Aggregator specs embedded in per-datapoint classification evaluator configs.

Each aggregator is a self-contained run-level metric (precision / recall /
f-score) attached to a classification evaluator. Specs do not share any
properties — each variant declares its own ``classes``, ``averaging``, and
(for fscore) ``f_value`` independently. This keeps each aggregator's contract
explicit at the JSON level: nothing is hoisted up to the evaluator and silently
applied to siblings.
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
    classes: list[str] = Field(..., min_length=1)
    averaging: Literal["macro", "micro"]


class RecallAggregatorSpec(_AggregatorSpecBase):
    """Run-level recall aggregator (multiclass, micro or macro averaged)."""

    type: Literal["recall"] = "recall"
    classes: list[str] = Field(..., min_length=1)
    averaging: Literal["macro", "micro"]


class FScoreAggregatorSpec(_AggregatorSpecBase):
    """Run-level F-beta aggregator (multiclass, micro or macro averaged)."""

    type: Literal["fscore"] = "fscore"
    classes: list[str] = Field(..., min_length=1)
    averaging: Literal["macro", "micro"]
    f_value: float = Field(default=1.0, gt=0)


AggregatorSpec = Annotated[
    Union[PrecisionAggregatorSpec, RecallAggregatorSpec, FScoreAggregatorSpec],
    Field(discriminator="type"),
]
