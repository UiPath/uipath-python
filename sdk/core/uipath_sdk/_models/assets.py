from typing import Dict, List, Optional

from pydantic import BaseModel


class CredentialsConnectionData(BaseModel):
    url: str
    body: str
    bearerToken: str


class UserAsset(BaseModel):
    Name: Optional[str] = None
    Value: Optional[str] = None
    ValueType: Optional[str] = None
    StringValue: Optional[str] = None
    BoolValue: Optional[bool] = None
    IntValue: Optional[int] = None
    CredentialUsername: Optional[str] = None
    CredentialPassword: Optional[str] = None
    ExternalName: Optional[str] = None
    CredentialStoreId: Optional[int] = None
    KeyValueList: Optional[List[Dict[str, str]]] = None
    ConnectionData: Optional[CredentialsConnectionData] = None
    Id: Optional[int] = None
