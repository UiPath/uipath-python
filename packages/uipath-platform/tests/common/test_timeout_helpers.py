import pytest
from uipath.core.triggers import (
    UIPATH_METADATA_KEY,
    UiPathResumeTriggerName,
    UiPathResumeTriggerType,
)

from uipath.platform.common import (
    UiPathResumeMetadata,
    UiPathTimeoutError,
    assert_no_timeout,
    get_resume_metadata,
    is_timeout,
)


def test_is_timeout_detects_timeout_metadata() -> None:
    value = {
        UIPATH_METADATA_KEY: {
            "triggerType": "Timer",
            "triggerName": "Timer",
        },
        "value": None,
    }

    assert is_timeout(value) is True


def test_get_resume_metadata_returns_typed_metadata() -> None:
    value = {
        UIPATH_METADATA_KEY: {
            "triggerType": "Timer",
            "triggerName": "Timer",
        },
        "resumeTime": "2026-07-07T12:00:00Z",
    }

    metadata = get_resume_metadata(value)

    assert isinstance(metadata, UiPathResumeMetadata)
    assert metadata.trigger_type == UiPathResumeTriggerType.TIMER
    assert metadata.trigger_name == UiPathResumeTriggerName.TIMER


def test_get_resume_metadata_returns_none_without_metadata() -> None:
    assert get_resume_metadata({"result": "done"}) is None
    assert get_resume_metadata("done") is None


def test_get_resume_metadata_returns_none_for_invalid_metadata() -> None:
    value = {
        UIPATH_METADATA_KEY: {
            "triggerType": "NotARealTrigger",
            "triggerName": "Timer",
        },
    }

    assert get_resume_metadata(value) is None


def test_is_timeout_ignores_non_timer_metadata() -> None:
    value = {
        UIPATH_METADATA_KEY: {
            "triggerType": "Job",
            "triggerName": "Job",
        },
        "value": {"jobKey": "job-1"},
    }

    assert is_timeout(value) is False


def test_is_timeout_ignores_user_timed_out_fields() -> None:
    assert is_timeout({"timedOut": True}) is False
    assert is_timeout("timeout") is False


def test_assert_no_timeout_returns_original_value() -> None:
    value = {"result": "done"}

    assert assert_no_timeout(value) is value


def test_assert_no_timeout_raises_with_resume_value() -> None:
    value = {
        UIPATH_METADATA_KEY: {
            "triggerType": "Timer",
            "triggerName": "Timer",
        },
        "value": {"jobKey": "job-1"},
    }

    with pytest.raises(UiPathTimeoutError) as exc_info:
        assert_no_timeout(value)

    assert exc_info.value.value is value
