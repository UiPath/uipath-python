"""Tests for classifying eval execution errors as user vs runtime failures."""

from uipath.eval.runtime.runtime import _is_user_facing_error
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathRuntimeError,
)


def _make_error(category: UiPathErrorCategory) -> UiPathRuntimeError:
    return UiPathRuntimeError(
        UiPathErrorCode.FUNCTION_EXECUTION_ERROR,
        "Some failure",
        "details",
        category,
        include_traceback=False,
    )


def test_user_category_error_is_user_facing():
    assert _is_user_facing_error(_make_error(UiPathErrorCategory.USER)) is True


def test_system_category_error_is_not_user_facing():
    assert _is_user_facing_error(_make_error(UiPathErrorCategory.SYSTEM)) is False


def test_unknown_category_error_is_not_user_facing():
    assert _is_user_facing_error(_make_error(UiPathErrorCategory.UNKNOWN)) is False


def test_plain_exception_is_not_user_facing():
    assert _is_user_facing_error(ValueError("boom")) is False
