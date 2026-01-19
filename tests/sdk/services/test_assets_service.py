from unittest.mock import Mock, patch

import pytest
from pytest_httpx import HTTPXMock

from uipath._utils.constants import HEADER_USER_AGENT
from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common.paging import PagedResult
from uipath.platform.orchestrator import Asset, UserAsset
from uipath.platform.orchestrator._assets_service import AssetsService


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
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
            config: UiPathApiConfig,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=UiPathExecutionContext(),
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

    class TestListAssets:
        def test_list_assets(
            self,
            httpx_mock: HTTPXMock,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            config: UiPathApiConfig,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=UiPathExecutionContext(),
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered?$skip=0&$top=100",
                status_code=200,
                json={
                    "value": [
                        {
                            "Key": "asset-key-1",
                            "Name": "Asset 1",
                            "Value": "value-1",
                            "ValueType": "Text",
                        },
                        {
                            "Key": "asset-key-2",
                            "Name": "Asset 2",
                            "Value": "value-2",
                            "ValueType": "Text",
                        },
                    ]
                },
            )

            result = service.list()

            assert isinstance(result, PagedResult)
            assert len(result.items) == 2
            assert all(isinstance(asset, Asset) for asset in result.items)
            assert result.items[0].key == "asset-key-1"
            assert result.items[0].name == "Asset 1"
            assert result.items[1].key == "asset-key-2"
            assert result.items[1].name == "Asset 2"
            assert result.skip == 0
            assert result.top == 100
            assert result.has_more is False  # 2 items < 100 top

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.list/{version}"
            )

        def test_list_assets_with_filter_and_orderby(
            self,
            httpx_mock: HTTPXMock,
            base_url: str,
            org: str,
            tenant: str,
            config: UiPathApiConfig,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=UiPathExecutionContext(),
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered?$skip=0&$top=100&$filter=ValueType eq 'Text'&$orderby=Name asc",
                status_code=200,
                json={
                    "value": [
                        {
                            "Key": "asset-key-1",
                            "Name": "Text Asset",
                            "ValueType": "Text",
                        },
                    ]
                },
            )

            result = service.list(filter="ValueType eq 'Text'", orderby="Name asc")

            assert len(result.items) == 1
            assert result.items[0].name == "Text Asset"

        @pytest.mark.anyio
        async def test_list_assets_async(
            self,
            httpx_mock: HTTPXMock,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            config: UiPathApiConfig,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=UiPathExecutionContext(),
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered?$skip=0&$top=100",
                status_code=200,
                json={
                    "value": [
                        {
                            "Key": "asset-key-1",
                            "Name": "Asset 1",
                            "Value": "value-1",
                        },
                    ]
                },
            )

            result = await service.list_async()

            assert isinstance(result, PagedResult)
            assert len(result.items) == 1
            assert result.items[0].key == "asset-key-1"
            assert result.items[0].name == "Asset 1"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AssetsService.list_async/{version}"
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
        config: UiPathApiConfig,
    ) -> None:
        with pytest.raises(ValueError):
            monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
            service = AssetsService(
                config=config,
                execution_context=UiPathExecutionContext(),
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
            service._execution_context = UiPathExecutionContext()

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
            service._execution_context = UiPathExecutionContext()

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
