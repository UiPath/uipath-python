from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CredentialsConnectionData(BaseModel):
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
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: Optional[str] = Field(default=None, alias="Name")
    value: Optional[str] = Field(default=None, alias="Value")
    value_type: Optional[str] = Field(default=None, alias="ValueType")
    string_value: Optional[str] = Field(default=None, alias="StringValue")
    bool_value: Optional[bool] = Field(default=None, alias="BoolValue")
    int_value: Optional[int] = Field(default=None, alias="IntValue")
    credential_username: Optional[str] = Field(default=None, alias="CredentialUsername")
    credential_password: Optional[str] = Field(default=None, alias="CredentialPassword")
    external_name: Optional[str] = Field(default=None, alias="ExternalName")
    credential_store_id: Optional[int] = Field(default=None, alias="CredentialStoreId")
    key_value_list: Optional[List[Dict[str, str]]] = Field(
        default=None, alias="KeyValueList"
    )
    connection_data: Optional[CredentialsConnectionData] = Field(
        default=None, alias="ConnectionData"
    )
    id: Optional[int] = Field(default=None, alias="Id")

    @property
    def display_value(self) -> str:
        """Safe display value that masks secrets and credentials.

        Returns "***" for Secret and Credential asset types to prevent
        accidental exposure in logs or CLI output.
        """
        if self.value_type in ("Secret", "Credential"):
            return "***"
        return str(self.value) if self.value is not None else "None"

    def __repr__(self) -> str:
        """Override repr to prevent accidental secret exposure in logs."""
        return (
            f"UserAsset(name={self.name!r}, "
            f"value_type={self.value_type!r}, "
            f"value={self.display_value!r})"
        )

    def __str__(self) -> str:
        """Override str for user-friendly display that masks secrets."""
        return f"UserAsset '{self.name}' ({self.value_type}): {self.display_value}"


class Asset(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    key: Optional[str] = Field(default=None, alias="Key")
    description: Optional[str] = Field(default=None, alias="Description")
    name: Optional[str] = Field(default=None, alias="Name")
    value: Optional[str] = Field(default=None, alias="Value")
    value_type: Optional[str] = Field(default=None, alias="ValueType")
    string_value: Optional[str] = Field(default=None, alias="StringValue")
    bool_value: Optional[bool] = Field(default=None, alias="BoolValue")
    int_value: Optional[int] = Field(default=None, alias="IntValue")
    credential_username: Optional[str] = Field(default=None, alias="CredentialUsername")
    credential_password: Optional[str] = Field(default=None, alias="CredentialPassword")
    external_name: Optional[str] = Field(default=None, alias="ExternalName")
    credential_store_id: Optional[int] = Field(default=None, alias="CredentialStoreId")

    @property
    def display_value(self) -> str:
        """Safe display value that masks secrets and credentials.

        Returns "***" for Secret and Credential asset types to prevent
        accidental exposure in logs or CLI output.
        """
        if self.value_type in ("Secret", "Credential"):
            return "***"
        return str(self.value) if self.value is not None else "None"

    def __repr__(self) -> str:
        """Override repr to prevent accidental secret exposure in logs."""
        return (
            f"Asset(name={self.name!r}, "
            f"value_type={self.value_type!r}, "
            f"value={self.display_value!r})"
        )

    def __str__(self) -> str:
        """Override str for user-friendly display that masks secrets."""
        return f"Asset '{self.name}' ({self.value_type}): {self.display_value}"
