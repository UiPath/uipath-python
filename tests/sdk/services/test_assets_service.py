from unittest.mock import Mock, patch

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

    class TestRequestKwargs:
        """Test that all methods pass the correct kwargs to request/request_async."""

        def test_retrieve_passes_all_kwargs(
            self, service: AssetsService, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """Test that retrieve passes all kwargs to request."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "value": [{"key": "test-key", "name": "Test", "value": "test-value"}]
            }

            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service._execution_context = ExecutionContext()

            with patch.object(
                service, "request", return_value=mock_response
            ) as mock_request:
                service.retrieve(name="Test")

                mock_request.assert_called_once()
                call_kwargs = mock_request.call_args

                # Verify all expected kwargs are present
                assert "url" in call_kwargs.kwargs
                assert "params" in call_kwargs.kwargs
                assert "json" in call_kwargs.kwargs
                assert "content" in call_kwargs.kwargs
                assert "headers" in call_kwargs.kwargs

                # Verify positional arg (method)
                assert call_kwargs.args[0] == "GET"

        @pytest.mark.anyio
        async def test_retrieve_async_passes_all_kwargs(
            self, service: AssetsService, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """Test that retrieve_async passes all kwargs to request_async."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "value": [{"key": "test-key", "name": "Test", "value": "test-value"}]
            }

            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service._execution_context = ExecutionContext()

            with patch.object(
                service, "request_async", return_value=mock_response
            ) as mock_request:
                await service.retrieve_async(name="Test")

                mock_request.assert_called_once()
                call_kwargs = mock_request.call_args

                # Verify all expected kwargs are present
                assert "url" in call_kwargs.kwargs
                assert "params" in call_kwargs.kwargs
                assert "json" in call_kwargs.kwargs
                assert "content" in call_kwargs.kwargs
                assert "headers" in call_kwargs.kwargs

                # Verify positional arg (method)
                assert call_kwargs.args[0] == "GET"

        def test_retrieve_credential_passes_all_kwargs(
            self, service: AssetsService
        ) -> None:
            """Test that retrieve_credential passes all kwargs to request."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "id": 1,
                "name": "Test",
                "credential_password": "secret",
            }

            with patch.object(
                service, "request", return_value=mock_response
            ) as mock_request:
                service.retrieve_credential(name="Test")

                mock_request.assert_called_once()
                call_kwargs = mock_request.call_args

                # Verify all expected kwargs are present
                assert "url" in call_kwargs.kwargs
                assert "params" in call_kwargs.kwargs
                assert "json" in call_kwargs.kwargs
                assert "content" in call_kwargs.kwargs
                assert "headers" in call_kwargs.kwargs

                # Verify positional arg (method)
                assert call_kwargs.args[0] == "POST"

        @pytest.mark.anyio
        async def test_retrieve_credential_async_passes_all_kwargs(
            self, service: AssetsService
        ) -> None:
            """Test that retrieve_credential_async passes all kwargs to request_async."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "id": 1,
                "name": "Test",
                "credential_password": "secret",
            }

            with patch.object(
                service, "request_async", return_value=mock_response
            ) as mock_request:
                await service.retrieve_credential_async(name="Test")

                mock_request.assert_called_once()
                call_kwargs = mock_request.call_args

                # Verify all expected kwargs are present
                assert "url" in call_kwargs.kwargs
                assert "params" in call_kwargs.kwargs
                assert "json" in call_kwargs.kwargs
                assert "content" in call_kwargs.kwargs
                assert "headers" in call_kwargs.kwargs

                # Verify positional arg (method)
                assert call_kwargs.args[0] == "POST"

        def test_update_passes_all_kwargs(self, service: AssetsService) -> None:
            """Test that update passes all kwargs to request."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "id": 1,
                "name": "Test",
                "value": "updated",
            }

            asset = UserAsset(name="Test", value="updated")

            with patch.object(
                service, "request", return_value=mock_response
            ) as mock_request:
                service.update(robot_asset=asset)

                mock_request.assert_called_once()
                call_kwargs = mock_request.call_args

                # Verify all expected kwargs are present
                assert "url" in call_kwargs.kwargs
                assert "params" in call_kwargs.kwargs
                assert "json" in call_kwargs.kwargs
                assert "content" in call_kwargs.kwargs
                assert "headers" in call_kwargs.kwargs

                # Verify positional arg (method)
                assert call_kwargs.args[0] == "POST"

        @pytest.mark.anyio
        async def test_update_async_passes_all_kwargs(
            self, service: AssetsService
        ) -> None:
            """Test that update_async passes all kwargs to request_async."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "id": 1,
                "name": "Test",
                "value": "updated",
            }

            asset = UserAsset(name="Test", value="updated")

            with patch.object(
                service, "request_async", return_value=mock_response
            ) as mock_request:
                await service.update_async(robot_asset=asset)

                mock_request.assert_called_once()
                call_kwargs = mock_request.call_args

                # Verify all expected kwargs are present
                assert "url" in call_kwargs.kwargs
                assert "params" in call_kwargs.kwargs
                assert "json" in call_kwargs.kwargs
                assert "content" in call_kwargs.kwargs
                assert "headers" in call_kwargs.kwargs

                # Verify positional arg (method)
                assert call_kwargs.args[0] == "POST"
