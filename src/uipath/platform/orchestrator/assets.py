"""Models for UiPath Orchestrator Assets."""

from pydantic import BaseModel, ConfigDict, Field

class CredentialsConnectionData(BaseModel):
    """Model representing connection data for credentials."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    url: str
    body: str
    bearer_token: str = Field(alias="bearerToken")

class UserAsset(BaseModel):
    """Model representing a user asset."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: str | None = Field(default=None, alias="Name")
    value: str | None = Field(default=None, alias="Value")
    value_type: str | None = Field(default=None, alias="ValueType")
    string_value: str | None = Field(default=None, alias="StringValue")
    bool_value: bool | None = Field(default=None, alias="BoolValue")
    int_value: int | None = Field(default=None, alias="IntValue")
    credential_username: str | None = Field(default=None, alias="CredentialUsername")
    credential_password: str | None = Field(default=None, alias="CredentialPassword")
    external_name: str | None = Field(default=None, alias="ExternalName")
    credential_store_id: int | None = Field(default=None, alias="CredentialStoreId")
    key_value_list: list[dict[str, str]] | None = Field(
        default=None, alias="KeyValueList"
    )
    connection_data: CredentialsConnectionData | None = Field(
        default=None, alias="ConnectionData"
    )
    id: int | None = Field(default=None, alias="Id")

class Asset(BaseModel):
    """Model representing an orchestrator asset."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    key: str | None = Field(default=None, alias="Key")
    description: str | None = Field(default=None, alias="Description")
    name: str | None = Field(default=None, alias="Name")
    value: str | None = Field(default=None, alias="Value")
    value_type: str | None = Field(default=None, alias="ValueType")
    string_value: str | None = Field(default=None, alias="StringValue")
    bool_value: bool | None = Field(default=None, alias="BoolValue")
    int_value: int | None = Field(default=None, alias="IntValue")
    credential_username: str | None = Field(default=None, alias="CredentialUsername")
    credential_password: str | None = Field(default=None, alias="CredentialPassword")
    external_name: str | None = Field(default=None, alias="ExternalName")
    credential_store_id: int | None = Field(default=None, alias="CredentialStoreId")
