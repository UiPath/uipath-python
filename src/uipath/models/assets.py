from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CredentialsConnectionData(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
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
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
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
