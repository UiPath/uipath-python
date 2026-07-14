"""Minimal stand-ins for the ixp-platform / mls internals the scoring math
depends on. Every symbol here mirrors its upstream definition exactly where
behavior matters for metric parity (identity-compared enums, ID wrappers,
rounding, whitespace normalization); see the upstream paths in each section.

Do NOT "clean up" or modernize anything in this file: the shapes and edge
cases are contractual with ixp-platform's Measure page numbers, and parity
is pinned only by the golden fixtures in tests/evaluators/ixp. Any change
here must be mirrored upstream (which requires a metrics-cache version bump
there — see the note at the top of upstream metrics/ixp.py).
"""

import math
import re
from collections.abc import ItemsView, Iterable, Iterator, KeysView, Mapping, ValuesView
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Generic, NamedTuple, NewType, TypeVar, Union, overload

# --- reinfer_common/rounding.py (verbatim) ---


def round_to_significant_figures(target: float, num_figures: int) -> float:
    if target == 0.0:  # NOSONAR - upstream-faithful exact-zero check
        return 0.0
    return round(target, -int(math.floor(math.log10(abs(target)))) + (num_figures - 1))


def round_like_javascript(value: float, num_figures: int) -> float:
    """Rounds a float to `num_figures` decimal places like JavaScript or
    TypeScript would, rounding ties towards +infinity."""
    rounding_multiple = 10.0**num_figures
    return math.floor(rounding_multiple * value + 0.5) / rounding_multiple


# --- uipath_mls_common/normalize.py (regex module swapped for stdlib re) ---

# Upstream uses the third-party `regex` module, whose \s does NOT match the
# control chars U+001C-U+001F (FS/GS/RS/US); stdlib re's \s does. The class
# below is "whitespace except U+001C-U+001F" so interior occurrences are
# preserved exactly as upstream preserves them (leading/trailing ones are
# stripped by str.strip() on both sides).
_RX_ALL_WHITESPACE = re.compile(r"[^\S\x1c-\x1f]+")
_RX_ZERO_WIDTH_CHARACTERS = re.compile(
    "\\u180e|\\u200b|\\u200c|\\u200d|\\u2060|\\ufeff"
)


def normalize_all_spaces(text: str) -> str:
    safe_unicode = _RX_ZERO_WIDTH_CHARACTERS.sub("", text)
    return _RX_ALL_WHITESPACE.sub(" ", safe_unicode).strip()


# --- reinfer_common/frozendict.py (verbatim, minus typing overload notes) ---

KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")
SelfT = TypeVar("SelfT", bound="FrozenDict[Any, Any]")

MappingLike = Union[Mapping[KeyT, ValueT], Iterable[tuple[KeyT, ValueT]]]


class FrozenDict(Mapping[KeyT, ValueT], Generic[KeyT, ValueT]):
    __slots__ = ("_dict", "_hash")

    _dict: dict[KeyT, ValueT]
    _hash: "int | None"

    @overload
    def __new__(
        cls: type[SelfT], other: Mapping[KeyT, ValueT] = NotImplemented
    ) -> SelfT: ...

    @overload
    def __new__(
        cls: type[SelfT], other: Iterable[tuple[KeyT, ValueT]] = NotImplemented
    ) -> SelfT: ...

    def __new__(
        cls: type[SelfT], other: "MappingLike[KeyT, ValueT]" = NotImplemented
    ) -> SelfT:
        if other is NotImplemented:
            try:
                if isinstance(cls.__EMPTY, cls):  # type: ignore
                    return cls.__EMPTY  # type: ignore
            except AttributeError:
                pass
            return cls._init_empty()
        elif isinstance(other, cls):
            return other
        _dict: dict[KeyT, ValueT] = dict(other)
        if not _dict:
            try:
                if isinstance(cls.__EMPTY, cls):  # type: ignore
                    return cls.__EMPTY  # type: ignore
            except AttributeError:
                pass
            return cls._init_empty()
        this: SelfT = super().__new__(cls)
        this._dict = _dict
        this._hash = None
        return this

    def __getnewargs__(self) -> tuple[dict[KeyT, ValueT]]:
        return (self._dict,)

    def update(self: SelfT, other: "MappingLike[KeyT, ValueT]") -> SelfT:
        if not self._dict:
            new: SelfT = self.__class__(other)
            return new
        new_dict = dict(self._dict)
        new_dict.update(other)
        return self.__class__._make(new_dict)

    def discard(self: SelfT, key: KeyT) -> SelfT:
        if key not in self._dict:
            return self
        new_dict = dict(self._dict)
        del new_dict[key]
        return self.__class__._make(new_dict)

    def set(self: SelfT, key: KeyT, value: ValueT) -> SelfT:
        new_dict = dict(self._dict)
        new_dict[key] = value
        return self.__class__._make(new_dict)

    def items(self) -> ItemsView[KeyT, ValueT]:
        return self._dict.items()

    def keys(self) -> KeysView[KeyT]:
        return self._dict.keys()

    def values(self) -> ValuesView[ValueT]:
        return self._dict.values()

    def __getitem__(self, key: KeyT) -> ValueT:
        return self._dict[key]

    def __iter__(self) -> Iterator[KeyT]:
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._dict!r})"

    def __hash__(self) -> int:
        if self._hash is None:
            hash_value = 0
            for key, value in self._dict.items():
                hash_value ^= hash((key, value))
            self._hash = hash_value
            return hash_value
        return self._hash

    @classmethod
    def _make(cls: type[SelfT], _dict: dict[KeyT, ValueT]) -> SelfT:
        this: SelfT = super().__new__(cls)
        this._dict = _dict
        this._hash = None
        return this

    @classmethod
    def _init_empty(cls: type[SelfT]) -> SelfT:
        empty: SelfT = super().__new__(cls)
        empty._dict = {}
        empty._hash = 0
        cls.__EMPTY = empty  # type: ignore
        return empty


# --- reinfer_store ID wrappers (NewTypes over str/int, upstream:
#     comment_ids.py, label.py, entity.py; metrics/entity.py) ---

InternalCommentId = NewType("InternalCommentId", str)
LabelName = NewType("LabelName", str)
FieldId = NewType("FieldId", str)
ExtractionFieldId = NewType("ExtractionFieldId", FieldId)
TrainCommentIndex = NewType("TrainCommentIndex", int)
TestCommentIndex = NewType("TestCommentIndex", int)
CommentIndex = TypeVar("CommentIndex", bound=int)


# --- reinfer_store/entity.py EntityDefId (minimal: hex id + builtin ctor) ---

_ENTITY_DEF_ID_HEX_SIZE = 16
_ENTITY_DEF_ID_FORMAT = f"0{_ENTITY_DEF_ID_HEX_SIZE}x"
_RX_ENTITY_DEF_ID = re.compile(r"^[0-9a-f]{%s}\Z" % _ENTITY_DEF_ID_HEX_SIZE)


@dataclass(frozen=True, slots=True)
class EntityDefId:
    hex_value: str

    def __post_init__(self) -> None:
        assert _RX_ENTITY_DEF_ID.match(self.hex_value), self

    @staticmethod
    def from_int(def_id_int: int) -> "EntityDefId":
        return EntityDefId(format(def_id_int, _ENTITY_DEF_ID_FORMAT))

    @staticmethod
    def builtin_from_int(def_id_int: int) -> "BuiltinEntityDefId":
        return BuiltinEntityDefId(EntityDefId.from_int(def_id_int))


BuiltinEntityDefId = NewType("BuiltinEntityDefId", EntityDefId)

# int values from reinfer_store proto entity.proto
ENTITY_DEF_ID_MONEY = EntityDefId.builtin_from_int(6)
ENTITY_DEF_ID_DATE = EntityDefId.builtin_from_int(7)
ENTITY_DEF_ID_EXTRACTION_NUMBER = EntityDefId.builtin_from_int(68)
ENTITY_DEF_ID_EXTRACTION_CHOICE = EntityDefId.builtin_from_int(69)
ENTITY_DEF_ID_EXTRACTION_BOOLEAN = EntityDefId.builtin_from_int(70)


# --- uipath_mls_common/currency.py (member names are the contract;
#     upstream values are proto ints, only identity is compared) ---

Currency = Enum(
    "Currency",
    "AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND "
    "BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU "
    "CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP "
    "GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES "
    "KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD "
    "MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR "
    "PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD "
    "SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS "
    "UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB "
    "XBC XBD XCD XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG ZWL",
)


# --- uipath_mls_taxonomy/data_type.py enums + FieldChoice ---

FieldChoiceName = NewType("FieldChoiceName", str)
FieldChoiceInstructions = NewType("FieldChoiceInstructions", str)


class TwoDateDisambiguation(Enum):
    AS_DD_MM = auto()
    AS_MM_DD = auto()
    AS_MM_YY = auto()
    AS_YY_MM = auto()
    AS_MISSING = auto()


class ThreeDateDisambiguation(Enum):
    AS_DD_MM_YY = auto()
    AS_MM_DD_YY = auto()
    AS_YY_MM_DD = auto()
    AS_MISSING = auto()


@dataclass(slots=True, weakref_slot=True, frozen=True)
class FieldChoice:
    name: FieldChoiceName
    formatted: str
    instructions: FieldChoiceInstructions
    synonyms: tuple[str, ...]


class ChoiceFieldFlag(Enum):
    APPEARS_VERBATIM = auto()
    ALLOW_OUT_OF_DOMAIN = auto()


# --- metrics/labels.py PRPrediction. Imported by ixp.py only to feed its
#     pr_predictions accumulator, which is built and never returned (dead
#     upstream too) — kept so the verbatim ixp.py body imports cleanly. ---


class PRPrediction(NamedTuple):
    score: float
    assigned: bool


# --- uipath_mls_user_model_store proto ixp.proto quality enum ints ---

PROJECT_SCORE_QUALITY_POOR = 1
PROJECT_SCORE_QUALITY_AVERAGE = 2
PROJECT_SCORE_QUALITY_GOOD = 3
PROJECT_SCORE_QUALITY_EXCELLENT = 4
FIELD_F1_SCORE_QUALITY_POOR = 1
FIELD_F1_SCORE_QUALITY_AVERAGE = 2
FIELD_F1_SCORE_QUALITY_GOOD = 3
