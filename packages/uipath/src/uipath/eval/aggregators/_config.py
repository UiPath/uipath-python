"""Pydantic models for `aggregate.json` and its per-aggregator entries.

Shape on disk:

    {
      "aggregators": [
        {
          "function": "precision",
          "average": "macro",
          "classes": ["book", "cancel", "reschedule"]
        },
        {"function": "fscore", "beta": 1.0, "average": "macro",
         "classes": ["book", "cancel", "reschedule"]}
      ]
    }

Each entry is fully self-describing — there is no top-level shared
config. Duplicate entries for the same function name are allowed (e.g.
two `fscore` entries with different `beta`) and produce distinct output
keys via `AggregatorConfig.output_key()`.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

AverageMode = Literal["macro", "micro", "weighted"]


class AggregatorConfig(BaseModel):
    """One entry under `aggregators` in `aggregate.json`."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    function: str = Field(description="Registered function name (e.g. 'precision').")
    classes: Optional[list[str]] = Field(
        default=None,
        description="Class vocabulary. When omitted, inferred from observation labels.",
    )
    average: AverageMode = Field(
        default="macro",
        description="How to combine per-class numbers: macro / micro / weighted.",
    )
    positive_class: Optional[str] = Field(
        default=None,
        description="Positive class for binary scoring. Ignored when `average` is set.",
    )
    beta: float = Field(
        default=1.0,
        description="F-score beta. Only consulted by `fscore`.",
    )

    def output_key(self) -> str:
        """Stable key for this aggregator in the output `aggregations` block.

        Two distinct configs for the same function must get distinct keys so
        duplicate functions in `aggregate.json` don't collide. `fscore@beta=2.0`,
        `precision@average=micro`, etc.
        """
        qualifiers: list[str] = []
        if self.function == "fscore" and self.beta != 1.0:
            qualifiers.append(f"beta={self.beta}")
        if self.average != "macro":
            qualifiers.append(f"average={self.average}")
        if self.positive_class is not None:
            qualifiers.append(f"positiveClass={self.positive_class}")
        return (
            self.function
            if not qualifiers
            else f"{self.function}@{','.join(qualifiers)}"
        )


class AggregateConfig(BaseModel):
    """Top-level shape of `aggregate.json`."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    aggregators: list[AggregatorConfig]
