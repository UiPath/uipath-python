import datetime
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from dateutil import parser as dateutil_parser

from ._compat import (
    ChoiceFieldFlag,
    Currency,
    FieldChoice,
    FieldChoiceName,
    ThreeDateDisambiguation,
    TwoDateDisambiguation,
    normalize_all_spaces,
)

from .extraction import (
    AmountExtraction,
    BoolExtraction,
    ChoiceExtraction,
    DateExtraction,
    FieldValuePrediction,
    MonetaryExtraction,
)

__all__ = (
    "value_to_finite_decimal",
    "process_amount_field_value",
    "process_bool_field_value",
    "process_monetary_field_value",
    "process_date_field_value",
    "process_choice_field_value",
)


def value_to_finite_decimal(raw_value: str) -> Decimal | None:
    """Value to Finite Decimal

    Convert a string value to a Decimal. Returns `None` if the value is
    not a valid decimal or is infinite.
    """
    try:
        decimal_value = Decimal(raw_value)
        if decimal_value.is_finite():
            return decimal_value
    except (InvalidOperation, ValueError):
        pass

    _log.debug("Cannot convert value to finite decimal.")
    return None


def process_bool_field_value(
    raw_value: str, true_formatted: str | None, false_formatted: str | None
) -> FieldValuePrediction | None:
    normalized_value = normalize_all_spaces(raw_value).lower()
    if normalized_value == "true":
        formatted = true_formatted if true_formatted is not None else "True"
        value = True
    elif normalized_value == "false":
        formatted = false_formatted if false_formatted is not None else "False"
        value = False
    else:
        _log.debug("Cannot convert bool value to extraction.")
        return None

    return FieldValuePrediction(formatted, BoolExtraction(value))


def process_amount_field_value(raw_value: str) -> FieldValuePrediction | None:
    return (
        # Convert scientific to standard form decimal with `:f`
        FieldValuePrediction(formatted=f"{amount.amount:f}", extraction=amount)
        if (amount := _process_raw_amount(raw_value)) is not None
        else None
    )


def process_monetary_field_value(
    raw_value: str,
) -> FieldValuePrediction | None:
    # TODO(TIANLINXU312)[RE-4364]  Monetary field value should
    # consider more amount expressions from different countries
    # Remove any currency symbols
    normalized_value = normalize_all_spaces(raw_value)
    raw_currency, raw_amount = _get_raw_currency_amount(
        _RX_CURRENCY_SYMBOL.sub("", normalized_value)
    )
    formatted_currency = (
        _process_currency(raw_currency) if raw_currency is not None else None
    )
    amount_extraction = (
        _process_raw_amount(raw_amount) if raw_amount is not None else None
    )

    if amount_extraction is not None or formatted_currency is not None:
        extraction = MonetaryExtraction(
            currency=formatted_currency, amount=amount_extraction
        )
        return FieldValuePrediction(
            formatted=_format_monetary_extraction(
                raw_value=raw_value, extraction=extraction
            ),
            extraction=extraction,
        )

    _log.debug("Cannot convert monetary value to extraction.")
    return None


def process_date_field_value(
    raw_value: str,
    two_ambiguity: TwoDateDisambiguation | None,
    three_ambiguity: ThreeDateDisambiguation | None,
) -> FieldValuePrediction | None:
    # 1. Normalize raw field value
    # Remove leading and trailing whitespace and deduplicate whitespace
    # Also remove leading and trailing parens
    normalized_value = normalize_all_spaces(raw_value).strip("()")

    # 2. check if the field value is of ISO format with both date and time or
    # with date only
    matched_date_time_extraction = _process_iso_date_time(normalized_value)
    if matched_date_time_extraction is not None:
        formatted = _format_date_extraction(
            raw_value, matched_date_time_extraction
        )
        return FieldValuePrediction(
            formatted=formatted, extraction=matched_date_time_extraction
        )

    # 3. check if the field value is of three disambiguity format
    if three_ambiguity is not None:
        matched_three_ambiguity = _process_three_disambiguity_date(
            normalized_value, three_ambiguity
        )
        if matched_three_ambiguity is not None:
            formatted = _format_date_extraction(
                raw_value, matched_three_ambiguity
            )
            return FieldValuePrediction(
                formatted=formatted, extraction=matched_three_ambiguity
            )

    # 4. check if the field value is of two disambiguity format
    if two_ambiguity is not None:
        matched_two_ambiguity = _process_two_disambiguity_date(
            normalized_value, two_ambiguity
        )
        if matched_two_ambiguity is not None:
            formatted = _format_date_extraction(
                raw_value, matched_two_ambiguity
            )
            return FieldValuePrediction(
                formatted=formatted, extraction=matched_two_ambiguity
            )

    # 5. Try to parse with general datetime parser if we're not ambiguous
    if (
        two_ambiguity is TwoDateDisambiguation.AS_MISSING
        or three_ambiguity is ThreeDateDisambiguation.AS_MISSING
    ):
        return None

    matched_unknown = _process_unknown_datetime(normalized_value)
    if matched_unknown is not None:
        formatted = _format_date_extraction(raw_value, matched_unknown)
        return FieldValuePrediction(
            formatted=formatted, extraction=matched_unknown
        )

    _log.debug("Cannot convert date value to extraction.")
    return None


def process_choice_field_value(
    raw_value: str,
    choices: tuple[FieldChoice, ...],
    flags: frozenset[ChoiceFieldFlag],
) -> FieldValuePrediction | None:
    if len(raw_value) == 0:
        _log.warning("Extracted choice value is empty.")
        return None

    normalized_value = normalize_all_spaces(raw_value).lower()
    for choice in choices:
        lowercase_synonyms = {synonym.lower() for synonym in choice.synonyms}
        if (
            normalized_value == choice.name.lower()
            or normalized_value in lowercase_synonyms
        ):
            return FieldValuePrediction(
                formatted=choice.name,
                extraction=ChoiceExtraction(name=choice.name),
            )
    if ChoiceFieldFlag.ALLOW_OUT_OF_DOMAIN in flags:
        return FieldValuePrediction(
            formatted=raw_value,
            extraction=ChoiceExtraction(name=FieldChoiceName(raw_value)),
        )
    else:
        _log.debug("Cannot convert choice value to extraction.")
        return FieldValuePrediction(
            formatted=raw_value, extraction=ChoiceExtraction(name=None)
        )


_RX_CURRENCY_SYMBOL = re.compile("[$₣ƒ₴₭₺£₨₮₩¥€]")


def _process_raw_amount(raw_value: str) -> AmountExtraction | None:
    # Strip whitepsace, currency symbols and commas
    normalized_value = normalize_all_spaces(raw_value).replace(",", "")
    amount = _RX_CURRENCY_SYMBOL.sub("", normalized_value)

    decimal_value = value_to_finite_decimal(amount)
    if decimal_value is not None:
        return AmountExtraction(amount=decimal_value)
    else:
        _log.debug("Cannot convert amount value to extraction.")
        return None


def _process_currency(raw_value: str) -> Currency | None:
    try:
        return Currency[raw_value.strip().upper()]
    # AttributeError for `upper`
    except (KeyError, AttributeError):
        return None


def _format_monetary_extraction(
    raw_value: str, extraction: MonetaryExtraction
) -> str:
    """Format Monetary Extraction

    Represent monetary extractions as `<optional_amount> <optional_currency_code>`
    E.g. `12.11 USD` or `12.11` or `USD`
    If both currency and amount are missing we return the raw value.
    """
    if extraction.amount is None and extraction.currency is None:
        return raw_value

    formatted_amount = (
        extraction.amount.amount if extraction.amount is not None else ""
    )
    formatted_currency = (
        extraction.currency.name if extraction.currency is not None else ""
    )
    separator = (
        " "
        if extraction.currency is not None and extraction.amount is not None
        else ""
    )

    return f"{formatted_amount}{separator}{formatted_currency}"


# Match a currency code or a value in either order where one or both
# may be missing
_RX_MONEY = re.compile(
    r"((?P<pre_currency>[a-zA-Z]{1,4})\s*(?P<post_amount>[\d\.\s\-\,]*)|"
    r"(?P<pre_amount>[\d\.\s\-\,]*)(?P<post_currency>[a-zA-Z]{1,4})|"
    r"(?P<solo_amount>[\d\.\s\-\,]*)|"
    r"(?P<solo_currency>[a-zA-Z]{1,4}))"
)


class _CurrencyAmount(NamedTuple):
    raw_currency: str | None
    raw_amount: str | None


def _get_raw_currency_amount(raw: str) -> _CurrencyAmount:
    # Remove leading and trailing whitespace to simplify regex
    match = _RX_MONEY.match(raw.strip())
    if match is None:
        return _CurrencyAmount(None, None)

    groups: dict[str, str] = match.groupdict()

    if (pre_currency := groups.get("pre_currency")) is not None:
        raw_currency: str | None = pre_currency
    elif (post_currency := groups.get("post_currency")) is not None:
        raw_currency = post_currency
    else:
        raw_currency = groups.get("solo_currency")

    if (pre_amount := groups.get("pre_amount")) is not None:
        raw_amount: str | None = pre_amount
    elif (post_amount := groups.get("post_amount")) is not None:
        raw_amount = post_amount
    else:
        raw_amount = groups.get("solo_amount")

    return _CurrencyAmount(raw_currency, raw_amount)


_RX_DATE_SEPARATOR_STR = "[-./]"
_RX_TIME_SEPARATOR_STR = "[:.]"

# Component strings, including missing as X or x
_RX_YYYY_YEAR_STR = r"(?P<yyyy>[0-9]{4}|x{4}|X{4})"
_RX_YY_YEAR_STR = r"(?P<yy>[0-9]{2}|x{2}|X{2})"
_RX_MONTH_STR = r"(?P<month>0[1-9]|1[0-2]|x{2}|X{2})"
_RX_DAY_STR = r"(?P<day>0[1-9]|[1-2][0-9]|3[0-1]|x{2}|X{2})"
_RX_HOUR_STR = r"(?P<hour>[0-1][0-9]|2[0-4]|x{2}|X{2})"
_RX_MINUTE_STR = r"(?P<minute>[0-5][0-9]|x{2}|X{2})"
_RX_SECOND_STR = r"(?P<second>[0-5][0-9]|x{2}|X{2})"
_RX_MICRO_SECOND_STR = r"(:?\.[0-9]{1,6})?"

_RX_ISO_DATE_PATTERN_STR = _RX_DATE_SEPARATOR_STR.join(
    [_RX_YYYY_YEAR_STR, _RX_MONTH_STR, _RX_DAY_STR]
)
_RX_ISO_TIME_PATTERN_STR = _RX_TIME_SEPARATOR_STR.join(
    [_RX_HOUR_STR, _RX_MINUTE_STR, _RX_SECOND_STR + _RX_MICRO_SECOND_STR]
)
# ISO timezone - optionally 'Z', ±[hh]:[mm]', '±[hh][mm]', or '±[hh]'
_RX_TIMEZONE_STR = r"(?:[zZ]|[+-][0-9]{2}:?(:?[0-5][0-9])?)?"
_RX_ISO_DATE_TIME_PATTERN_STR = (
    f"^({_RX_ISO_DATE_PATTERN_STR})[ T]({_RX_ISO_TIME_PATTERN_STR})"
    f"{_RX_TIMEZONE_STR}$"
)
_RX_ISO_DATE_TIME_PATTERN = re.compile(_RX_ISO_DATE_TIME_PATTERN_STR)

# Don't constrain to start or end of string so we can parse cases
# where we have incorrect prefix / suffix.
# E.g."2024-02-01T00" or "T01:02:03Z"
_RX_ISO_DATE_PATTERN = re.compile(_RX_ISO_DATE_PATTERN_STR)
_RX_ISO_TIME_PATTERN = re.compile(_RX_ISO_TIME_PATTERN_STR)

_RX_THREE_AS_DD_MM_YY = re.compile(
    _RX_DATE_SEPARATOR_STR.join(
        ["^" + _RX_DAY_STR, _RX_MONTH_STR, _RX_YY_YEAR_STR + "$"]
    )
)
_RX_THREE_AS_MM_DD_YY = re.compile(
    _RX_DATE_SEPARATOR_STR.join(
        ["^" + _RX_MONTH_STR, _RX_DAY_STR, _RX_YY_YEAR_STR + "$"]
    )
)
_RX_THREE_AS_YY_MM_DD = re.compile(
    _RX_DATE_SEPARATOR_STR.join(
        ["^" + _RX_YY_YEAR_STR, _RX_MONTH_STR, _RX_DAY_STR + "$"]
    )
)

_RX_TWO_AS_DD_MM = re.compile(
    _RX_DATE_SEPARATOR_STR.join(["^" + _RX_DAY_STR, _RX_MONTH_STR + "$"])
)
_RX_TWO_AS_MM_DD = re.compile(
    _RX_DATE_SEPARATOR_STR.join(["^" + _RX_MONTH_STR, _RX_DAY_STR + "$"])
)
_RX_TWO_AS_MM_YY = re.compile(
    _RX_DATE_SEPARATOR_STR.join(["^" + _RX_MONTH_STR, _RX_YY_YEAR_STR + "$"])
)
_RX_TWO_AS_YY_MM = re.compile(
    _RX_DATE_SEPARATOR_STR.join(["^" + _RX_YY_YEAR_STR, _RX_MONTH_STR + "$"])
)


def _process_iso_date_time(field_value: str) -> DateExtraction | None:
    date_time_match = _RX_ISO_DATE_TIME_PATTERN.match(field_value)
    if date_time_match is not None:
        formatted_date = _match_to_raw_date(date_time_match)
        formatted_time = _match_to_raw_time(date_time_match)

        if (
            formatted_date.year is not None
            or formatted_date.month is not None
            or formatted_date.day is not None
        ) and _month_day_pair_is_valid(formatted_date):
            return DateExtraction(
                year=formatted_date.year,
                month=formatted_date.month,
                day=formatted_date.day,
                hours=formatted_time.hour,
                minutes=formatted_time.minute,
                seconds=formatted_time.second,
                nanoseconds=None,
                iana_timezone=None,
            )

    date_match = _RX_ISO_DATE_PATTERN.match(field_value)

    if date_match is not None:
        formatted_date = _match_to_raw_date(date_match)

        if (
            formatted_date.year is not None
            or formatted_date.month is not None
            or formatted_date.day is not None
        ) and _month_day_pair_is_valid(formatted_date):
            return DateExtraction(
                year=formatted_date.year,
                month=formatted_date.month,
                day=formatted_date.day,
                hours=None,
                minutes=None,
                seconds=None,
                nanoseconds=None,
                iana_timezone=None,
            )

    time_match = _RX_ISO_TIME_PATTERN.match(field_value)

    if time_match is not None:
        formatted_time = _match_to_raw_time(time_match)

        return DateExtraction(
            year=None,
            month=None,
            day=None,
            hours=formatted_time.hour,
            minutes=formatted_time.minute,
            seconds=formatted_time.second,
            nanoseconds=None,
            iana_timezone=None,
        )

    return None


def _process_three_disambiguity_date(
    field_value: str, three_ambiguity: ThreeDateDisambiguation
) -> DateExtraction | None:
    date_match = None
    if three_ambiguity is ThreeDateDisambiguation.AS_DD_MM_YY:
        date_match = _RX_THREE_AS_DD_MM_YY.match(field_value)
    if three_ambiguity is ThreeDateDisambiguation.AS_MM_DD_YY:
        date_match = _RX_THREE_AS_MM_DD_YY.match(field_value)
    if three_ambiguity is ThreeDateDisambiguation.AS_YY_MM_DD:
        date_match = _RX_THREE_AS_YY_MM_DD.match(field_value)

    formatted_date = _match_to_yy_raw_date(date_match)

    if (
        formatted_date.year is not None
        or formatted_date.month is not None
        or formatted_date.day is not None
    ) and _month_day_pair_is_valid(formatted_date):
        return DateExtraction(
            year=formatted_date.year,
            month=formatted_date.month,
            day=formatted_date.day,
            hours=None,
            minutes=None,
            seconds=None,
            nanoseconds=None,
            iana_timezone=None,
        )
    else:
        return None


def _process_two_disambiguity_date(
    field_value: str, two_ambiguity: TwoDateDisambiguation
) -> DateExtraction | None:
    date_match = None
    if two_ambiguity is TwoDateDisambiguation.AS_DD_MM:
        date_match = _RX_TWO_AS_DD_MM.match(field_value)
    if two_ambiguity is TwoDateDisambiguation.AS_MM_DD:
        date_match = _RX_TWO_AS_MM_DD.match(field_value)
    if two_ambiguity is TwoDateDisambiguation.AS_MM_YY:
        date_match = _RX_TWO_AS_MM_YY.match(field_value)
    if two_ambiguity is TwoDateDisambiguation.AS_YY_MM:
        date_match = _RX_TWO_AS_YY_MM.match(field_value)

    formatted_date = _match_to_yy_raw_date(date_match)

    if (
        formatted_date.year is not None
        or formatted_date.month is not None
        or formatted_date.day is not None
    ) and _month_day_pair_is_valid(formatted_date):
        return DateExtraction(
            year=formatted_date.year,
            month=formatted_date.month,
            day=formatted_date.day,
            hours=None,
            minutes=None,
            seconds=None,
            nanoseconds=None,
            iana_timezone=None,
        )
    else:
        return None


def _process_unknown_datetime(field_value: str) -> DateExtraction | None:
    # Try to parse an unknown datetime via dateutil
    # This has less flexibility (two / three ambiguity control)
    # But works with E.g. `23-Oct-2023`
    try:
        date = dateutil_parser.parse(field_value)
        return DateExtraction(
            year=date.year,
            month=date.month,
            day=date.day,
            hours=date.hour,
            minutes=date.minute,
            seconds=date.second,
            nanoseconds=None,
            iana_timezone=None,
        )
    except (dateutil_parser.ParserError, OverflowError):
        return None


class _RawDate(NamedTuple):
    year: int | None
    month: int | None
    day: int | None


class _RawTime(NamedTuple):
    hour: int | None
    minute: int | None
    second: int | None


def _match_to_yy_raw_date(match: re.Match[str] | None) -> _RawDate:
    if match is None:
        return _RawDate(None, None, None)

    group_dict = match.groupdict()
    year = group_dict.get("yy")
    month = group_dict.get("month")
    day = group_dict.get("day")
    return _RawDate(
        year=None if year is None else _format_yy_to_yyyy(year),
        month=_raw_datetime_value_to_int("xx", month),
        day=_raw_datetime_value_to_int("xx", day),
    )


def _match_to_raw_date(match: re.Match[str] | None) -> _RawDate:
    if match is None:
        return _RawDate(None, None, None)

    group_dict = match.groupdict()
    year = group_dict.get("yyyy", group_dict.get("yy"))
    month = group_dict.get("month")
    day = group_dict.get("day")

    return _RawDate(
        year=_raw_datetime_value_to_int("xxxx", year),
        month=_raw_datetime_value_to_int("xx", month),
        day=_raw_datetime_value_to_int("xx", day),
    )


def _match_to_raw_time(match: re.Match[str] | None) -> _RawTime:
    if match is None:
        return _RawTime(None, None, None)

    group_dict = match.groupdict()
    hour = group_dict.get("hour")
    minute = group_dict.get("minute")
    second = group_dict.get("second")

    return _RawTime(
        hour=_raw_datetime_value_to_int("xx", hour),
        minute=_raw_datetime_value_to_int("xx", minute),
        second=_raw_datetime_value_to_int("xx", second),
    )


def _raw_datetime_value_to_int(missing: str, raw_value: Any) -> int | None:
    if isinstance(raw_value, str) and raw_value.lower() == missing:
        return None
    return _safe_int_from_any(raw_value)


def _month_day_pair_is_valid(raw_date: _RawDate) -> bool:
    if raw_date.month is None or raw_date.day is None:
        return True
    year = (
        raw_date.year
        if raw_date.year is not None
        else datetime.date.today().year
    )
    try:
        datetime.date(year=year, month=raw_date.month, day=raw_date.day)
        return True
    except ValueError:
        return False


def _format_yy_to_yyyy(year: str) -> int | None:
    year_as_int = _safe_int_from_any(year)
    if year_as_int is None:
        return None

    if year_as_int >= 100:
        return year_as_int

    # If year is YY assume 20YY
    return 2000 + year_as_int


def _safe_int_from_any(raw: Any) -> int | None:
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _format_date_extraction(raw_value: str, extraction: DateExtraction) -> str:
    """Format Date Extraction

    Represent date extraction as an ISO-8601 date string, including the offset
    time.
    """
    # We can't represent this as a datetime so fall back to raw
    if (
        extraction.year is None
        or extraction.month is None
        or extraction.day is None
    ):
        return raw_value

    as_datetime_str = datetime.datetime(
        year=extraction.year,
        month=extraction.month,
        day=extraction.day,
        hour=(extraction.hours if extraction.hours is not None else 0),
        minute=(extraction.minutes if extraction.minutes is not None else 0),
        second=extraction.seconds if extraction.seconds is not None else 0,
        microsecond=(
            extraction.nanoseconds if extraction.nanoseconds is not None else 0
        ),
    ).isoformat()

    # Manually mark as Zulu / zero offset / UTC time.
    return f"{as_datetime_str}Z"


_log = logging.getLogger(__name__)
