from typing import TypedDict


class CredentialsConnectionData(TypedDict):
    url: str
    body: str
    bearerToken: str


class UserAsset(TypedDict):
    Name: str
    Value: str
    ValueType: str
    StringValue: str
    BoolValue: bool
    IntValue: int
    CredentialUsername: str
    CredentialPassword: str
    ExternalName: str
    CredentialStoreId: int
    KeyValueList: list[dict[str, str]]
    ConnectionData: CredentialsConnectionData
    Id: int
