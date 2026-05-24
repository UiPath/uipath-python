"""Aggregator specs attached to per-datapoint evaluator configs.

An aggregator is run-level — it consumes the per-datapoint results of an
evaluator after the eval set finishes. The aggregator itself does not run in
the Python runtime; this module just defines the config shape so the downstream
consumer (the C# backend) can pick it up via the evaluator's stored config.

Today the only aggregator is `classification`, which compares each datapoint's
expected vs. predicted class to build a confusion matrix and precision/recall/
F-score metrics.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ClassificationAggregatorSpec(BaseModel):
    """Configuration for a classification aggregator.

    Attached to a per-datapoint evaluator (e.g. ExactMatch) to mark that the
    evaluator's results should be aggregated into classification metrics. The
    classes list defines the exhaustive label space; the C# layer scans each
    datapoint's expected output for the first class that matches.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: Literal["classification"] = "classification"
    classes: list[str]


# Union of all supported aggregator specs. Add new variants here.
AggregatorSpec = ClassificationAggregatorSpec
