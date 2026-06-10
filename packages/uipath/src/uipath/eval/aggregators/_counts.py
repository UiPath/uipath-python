"""Shared TP/FP/FN counting used by precision, recall, and fscore.

Each function reduces a list of observations to per-class
true-positive / false-positive / false-negative counts, then derives its
metric from those. Centralising the counting here keeps the three
function implementations one-liners.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from ._base import Observation


@dataclass(frozen=True)
class ClassCounts:
    """TP/FP/FN/support for one class — enough to derive P/R/F."""

    tp: int
    fp: int
    fn: int
    support: int


def resolve_classes(
    explicit: list[str] | None, observations: list[Observation]
) -> list[str]:
    """Return the class vocabulary, preferring `explicit` over auto-inference.

    Auto-inference: distinct non-null `expected` values in order of first
    appearance. Keeps a stable iteration order across runs.
    """
    if explicit is not None:
        return list(explicit)
    seen: OrderedDict[str, None] = OrderedDict()
    for obs in observations:
        if obs.expected:
            seen.setdefault(obs.expected, None)
    return list(seen.keys())


def class_counts(
    classes: list[str], observations: list[Observation]
) -> dict[str, ClassCounts]:
    """For each configured class, count TP / FP / FN / support across observations.

    A datapoint contributes to TP/FP/FN only when both expected and actual
    resolve to one of the configured classes. Other rows (missing fields,
    out-of-vocab labels) do not contribute — they affect neither the
    numerator nor the denominator of any class's precision/recall.
    """
    out = {c: [0, 0, 0, 0] for c in classes}  # [tp, fp, fn, support]
    class_set = set(classes)
    for obs in observations:
        if obs.expected is None or obs.actual is None:
            continue
        exp = obs.expected
        act = obs.actual
        if exp not in class_set and act not in class_set:
            continue
        if exp in class_set:
            out[exp][3] += 1  # support
        if exp == act and exp in class_set:
            out[exp][0] += 1  # tp
        else:
            if act in class_set:
                out[act][1] += 1  # fp on the predicted class
            if exp in class_set:
                out[exp][2] += 1  # fn on the true class
    return {
        c: ClassCounts(tp=v[0], fp=v[1], fn=v[2], support=v[3]) for c, v in out.items()
    }


def macro_average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def weighted_average(values: list[float], weights: list[int]) -> float:
    total = sum(weights)
    return (
        sum(v * w for v, w in zip(values, weights, strict=False)) / total
        if total
        else 0.0
    )
