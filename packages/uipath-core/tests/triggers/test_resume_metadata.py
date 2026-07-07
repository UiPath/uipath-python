from uipath.core.triggers import (
    UiPathResumeMetadata,
    UiPathResumeTriggerName,
    UiPathResumeTriggerType,
)


def test_resume_metadata_accepts_trigger_aliases() -> None:
    metadata = UiPathResumeMetadata.model_validate(
        {
            "kind": "timeout",
            "triggerType": "Timer",
            "triggerName": "Timer",
        }
    )

    assert metadata.kind == "timeout"
    assert metadata.trigger_type == UiPathResumeTriggerType.TIMER
    assert metadata.trigger_name == UiPathResumeTriggerName.TIMER


def test_resume_metadata_accepts_field_names() -> None:
    metadata = UiPathResumeMetadata(
        trigger_type=UiPathResumeTriggerType.API,
        trigger_name=UiPathResumeTriggerName.API,
    )

    assert metadata.trigger_type == UiPathResumeTriggerType.API
    assert metadata.trigger_name == UiPathResumeTriggerName.API
