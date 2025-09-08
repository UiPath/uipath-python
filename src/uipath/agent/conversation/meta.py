"""Meta events allow additional extensible data."""

from pydantic import BaseModel, ConfigDict


class UiPathConversationMetaEvent(BaseModel):
    """Arbitrary metadata events in the conversation schema."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )
