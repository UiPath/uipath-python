from typing import TypedDict, cast

from ._base_service import BaseService


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


class RobotAssetsService(BaseService):
    def retrieve(
        self,
        assetName: str,
        robotKey: str,
    ) -> UserAsset:
        return cast(
            UserAsset,
            self.client.post(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey",
                data={
                    "assetName": assetName,
                    "robotKey": robotKey,
                    "supportsCredentialsProxyDisconnected": True,
                },
            ).json(),
        )

    def update(
        self,
        robotKey: str,
        robotAsset: UserAsset,
    ) -> None:
        self.client.post(
            "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey",
            data={
                "robotKey": robotKey,
                "robotAsset": robotAsset,
            },
        )
