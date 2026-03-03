"""UiPath resume trigger enums."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PropertyName(str, Enum):
    """UiPath trigger property names."""

    INTERNAL = "__internal"


class TriggerMarker(str, Enum):
    """UiPath trigger markers.

    These markers are used as properties of resume triggers objects for special handling at runtime.
    """

    NO_CONTENT = "NO_CONTENT"


def is_no_content_marker(value: Any) -> bool:
    """Check if a value is a NO_CONTENT trigger marker (dict or string form)."""
    if isinstance(value, dict):
        return value.get(PropertyName.INTERNAL.value) == TriggerMarker.NO_CONTENT.value
    if isinstance(value, str):
        return (
            PropertyName.INTERNAL.value in value
            and TriggerMarker.NO_CONTENT.value in value
        )
    return False


class ExternalTriggerType(str, Enum):
    """External trigger types."""

    DEEP_RAG = "deepRag"
    BATCH_RAG = "batchRag"
    IXP_EXTRACTION = "ixpExtraction"
    INDEX_INGESTION = "indexIngestion"
    IXP_VS_ESCALATION = "IxpVsEscalation"


class ExternalTrigger(BaseModel):
    """Model representing an external trigger entity."""

    type: ExternalTriggerType
    external_id: str = Field(alias="externalId")

    model_config = {
        "validate_by_name": True,
        "validate_by_alias": True,
    }
