"""Models for Remote A2A Agents in UiPath AgentHub.

.. warning::
    This module is experimental and subject to change.
    The Remote A2A feature is in preview and its API may change in future releases.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class RemoteA2aAgentFolder(BaseModel):
    """Folder information for a Remote A2A agent."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    key: Optional[str] = None
    display_name: Optional[str] = None
    fully_qualified_name: Optional[str] = None


class RemoteA2aAgent(BaseModel):
    """Model representing a Remote A2A agent in UiPath AgentHub.

    .. warning::
        This model is experimental and subject to change.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    agent_card_url: Optional[str] = None
    a2a_url: Optional[str] = Field(None, alias="a2aUrl")
    folder: Optional[RemoteA2aAgentFolder] = None
    headers: Optional[str] = None
    is_active: Optional[bool] = None
    cached_agent_card: Optional[Any] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
