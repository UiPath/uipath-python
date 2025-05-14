import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.assets_service import AssetsService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models import UserAsset
from uipath.models.assets import Asset


@pytest.fixture
def service(
    config: Config, execution_context: ExecutionContext, monkeypatch: pytest.MonkeyPatch
) -> AssetsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return AssetsService(config=config, execution_context=execution_context)


class TestAssetsService:
    class TestRetrieveAsset:
        def test_retrieve_robot_asset(
            self,
            httpx_mock: HTTPXMock,
            service: AssetsService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey",
                status_code=200,
                json={"id": 1, "name": "Test Asset", "value": "test-value"},
            )

            asset = service.retrieve(name="Test Asset")

            assert isinstance(asset, UserAsset)
            assert asset.id == 1
            assert asset.name == "Test Asset"
            assert asset.value == "test-value"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "POST"
            assert (
                sent_request.url
                == f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
            )

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.retrieve/{version}"
            )

        def test_retrieve_asset(
            self,
            httpx_mock: HTTPXMock,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            config: Config,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=ExecutionContext(),
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered?$filter=Name eq 'Test Asset'&$top=1",
                status_code=200,
                json={
                    "value": [
                        {
                            "key": "asset-key",
                            "name": "Test Asset",
                            "value": "test-value",
                        }
                    ]
                },
            )

            asset = service.retrieve(name="Test Asset")

            assert isinstance(asset, Asset)
            assert asset.key == "asset-key"
            assert asset.name == "Test Asset"
            assert asset.value == "test-value"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert (
                sent_request.url
                == f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered?%24filter=Name+eq+%27Test+Asset%27&%24top=1"
            )

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.retrieve/{version}"
            )

    def test_retrieve_credential(
        self,
        httpx_mock: HTTPXMock,
        service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey",
            status_code=200,
            json={
                "id": 1,
                "name": "Test Credential",
                "credential_username": "test-user",
                "credential_password": "test-password",
            },
        )

        credential = service.retrieve_credential(name="Test Credential")

        assert credential == "test-password"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.retrieve_credential/{version}"
        )

    def test_retrieve_credential_user_asset(
        self,
        service: AssetsService,
        monkeypatch: pytest.MonkeyPatch,
        config: Config,
    ) -> None:
        with pytest.raises(ValueError):
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=ExecutionContext(),
            )
            service.retrieve_credential(name="Test Credential")

    async def test_retrieve_credential_async(
        self,
        httpx_mock: HTTPXMock,
        service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Test asynchronously retrieving a credential asset."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey",
            status_code=200,
            json={
                "id": 1,
                "name": "Test Credential",
                "credential_username": "test-user",
                "credential_password": "test-password",
            },
        )

        credential = await service.retrieve_credential_async(name="Test Credential")

        assert credential == "test-password"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.retrieve_credential_async/{version}"
        )

    def test_update(
        self,
        httpx_mock: HTTPXMock,
        service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey",
            status_code=200,
            json={"id": 1, "name": "Test Asset", "value": "updated-value"},
        )

        asset = UserAsset(name="Test Asset", value="updated-value")
        response = service.update(robot_asset=asset)

        assert response == {"id": 1, "name": "Test Asset", "value": "updated-value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.update/{version}"
        )

    @pytest.mark.anyio
    async def test_update_async(
        self,
        httpx_mock: HTTPXMock,
        service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey",
            status_code=200,
            json={"id": 1, "name": "Test Asset", "value": "updated-value"},
        )

        asset = UserAsset(name="Test Asset", value="updated-value")
        response = await service.update_async(robot_asset=asset)

        assert response == {"id": 1, "name": "Test Asset", "value": "updated-value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.update_async/{version}"
        )
