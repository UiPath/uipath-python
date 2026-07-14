"""Extraction value types, ported verbatim from
mls/internal/ixp_model/uipath_mls_ixp_model/extraction.py (the slice the
scoring math needs).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TypeAlias

from ._compat import Currency, FieldChoiceName


@dataclass(slots=True, weakref_slot=True, frozen=True)
class TextExtraction:
    pass


@dataclass(slots=True, weakref_slot=True, frozen=True)
class AmountExtraction:
    amount: Decimal


@dataclass(slots=True, weakref_slot=True, frozen=True)
class MonetaryExtraction:
    currency: "Currency | None"
    amount: "AmountExtraction | None"


@dataclass(slots=True, weakref_slot=True, frozen=True)
class DateExtraction:
    year: "int | None"
    month: "int | None"
    day: "int | None"

    hours: "int | None"
    minutes: "int | None"
    seconds: "int | None"

    nanoseconds: "int | None"

    iana_timezone: "str | None"


@dataclass(slots=True, weakref_slot=True, frozen=True)
class BoolExtraction:
    value: bool


@dataclass(slots=True, weakref_slot=True, frozen=True)
class ChoiceExtraction:
    name: "FieldChoiceName | None"


FieldExtraction: TypeAlias = (
    AmountExtraction
    | MonetaryExtraction
    | DateExtraction
    | BoolExtraction
    | TextExtraction
    | ChoiceExtraction
)


@dataclass(slots=True, weakref_slot=True, frozen=True)
class FieldValuePrediction:
    formatted: str
    extraction: FieldExtraction
