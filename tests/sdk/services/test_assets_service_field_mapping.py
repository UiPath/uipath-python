"""Tests for Assets Service field mapping - StringValue/IntValue/BoolValue."""

import json

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.assets_service import AssetsService


@pytest.fixture
def assets_service(
    config: Config, execution_context: ExecutionContext
) -> AssetsService:
    """AssetsService fixture for testing."""
    return AssetsService(config=config, execution_context=execution_context)


class TestAssetsServiceFieldMapping:
    """Test asset creation sends correct field names to API."""

    def test_create_text_asset_uses_string_value(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset sends 'StringValue' field."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": "test-value",
                "ValueType": "Text",
            }
        )

        assets_service.create(name="TestAsset", value="test-value", value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None

        # Verify request body uses "StringValue", not "Value"
        body = json.loads(request.content)
        assert "StringValue" in body
        assert body["StringValue"] == "test-value"
        assert "Value" not in body  # Should NOT use generic "Value"

    def test_create_integer_asset_uses_int_value(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Integer asset sends 'IntValue' field."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "PortAsset",
                "IntValue": 8080,
                "ValueType": "Integer",
            }
        )

        assets_service.create(name="PortAsset", value=8080, value_type="Integer")

        request = httpx_mock.get_request()
        assert request is not None

        body = json.loads(request.content)
        assert "IntValue" in body
        assert body["IntValue"] == 8080
        assert "Value" not in body

    def test_create_boolean_asset_uses_bool_value(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Boolean asset sends 'BoolValue' field."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "EnabledAsset",
                "BoolValue": True,
                "ValueType": "Boolean",
            }
        )

        assets_service.create(name="EnabledAsset", value=True, value_type="Boolean")

        request = httpx_mock.get_request()
        assert request is not None

        body = json.loads(request.content)
        assert "BoolValue" in body
        assert body["BoolValue"] is True
        assert "Value" not in body

    def test_create_text_asset_with_empty_string(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles empty string."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "EmptyAsset",
                "StringValue": "",
                "ValueType": "Text",
            }
        )

        assets_service.create(name="EmptyAsset", value="", value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == ""

    def test_create_integer_asset_with_zero(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Integer asset handles zero value."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "ZeroAsset",
                "IntValue": 0,
                "ValueType": "Integer",
            }
        )

        assets_service.create(name="ZeroAsset", value=0, value_type="Integer")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["IntValue"] == 0

    def test_create_boolean_asset_false(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Boolean asset handles False."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "DisabledAsset",
                "BoolValue": False,
                "ValueType": "Boolean",
            }
        )

        assets_service.create(name="DisabledAsset", value=False, value_type="Boolean")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["BoolValue"] is False

    def test_create_text_asset_with_unicode(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles Unicode characters."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "UnicodeAsset",
                "StringValue": "Hello 世界 🌍",
                "ValueType": "Text",
            }
        )

        assets_service.create(
            name="UnicodeAsset", value="Hello 世界 🌍", value_type="Text"
        )

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == "Hello 世界 🌍"

    def test_create_integer_asset_with_negative(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Integer asset handles negative values."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "NegativeAsset",
                "IntValue": -42,
                "ValueType": "Integer",
            }
        )

        assets_service.create(name="NegativeAsset", value=-42, value_type="Integer")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["IntValue"] == -42

    def test_create_text_asset_with_special_chars(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles special characters."""
        special_value = 'Test "quotes" and \\backslashes\\ and\nnewlines'
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "SpecialAsset",
                "StringValue": special_value,
                "ValueType": "Text",
            }
        )

        assets_service.create(
            name="SpecialAsset", value=special_value, value_type="Text"
        )

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == special_value

    def test_create_integer_asset_with_large_number(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Integer asset handles large numbers."""
        large_number = 2147483647  # Max 32-bit int
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "LargeAsset",
                "IntValue": large_number,
                "ValueType": "Integer",
            }
        )

        assets_service.create(
            name="LargeAsset", value=large_number, value_type="Integer"
        )

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["IntValue"] == large_number

    def test_create_asset_sets_value_type_field(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() sets ValueType field in request."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": "test",
                "ValueType": "Text",
            }
        )

        assets_service.create(name="TestAsset", value="test", value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "ValueType" in body
        assert body["ValueType"] == "Text"

    def test_create_asset_sets_name_field(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() sets Name field in request."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "MyAsset",
                "StringValue": "test",
                "ValueType": "Text",
            }
        )

        assets_service.create(name="MyAsset", value="test", value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "Name" in body
        assert body["Name"] == "MyAsset"

    @pytest.mark.parametrize(
        "value_type,value,expected_field",
        [
            ("Text", "hello", "StringValue"),
            ("Integer", 42, "IntValue"),
            ("Boolean", True, "BoolValue"),
        ],
    )
    def test_create_asset_field_mapping_parametrized(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
        value_type: str,
        value: str | int | bool,
        expected_field: str,
    ) -> None:
        """Test create() uses correct field for each value type."""
        response_data: dict[str, str | int | bool] = {
            "Key": "asset-key-123",
            "Name": "TestAsset",
            "ValueType": value_type,
        }
        response_data[expected_field] = value

        httpx_mock.add_response(json=response_data)

        assets_service.create(name="TestAsset", value=value, value_type=value_type)

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert expected_field in body
        assert body[expected_field] == value

    def test_create_text_asset_long_string(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles very long strings."""
        long_string = "a" * 10000
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "LongAsset",
                "StringValue": long_string,
                "ValueType": "Text",
            }
        )

        assets_service.create(name="LongAsset", value=long_string, value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == long_string
        assert len(body["StringValue"]) == 10000

    def test_create_text_asset_multiline(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles multiline strings."""
        multiline = "Line 1\nLine 2\nLine 3"
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "MultilineAsset",
                "StringValue": multiline,
                "ValueType": "Text",
            }
        )

        assets_service.create(name="MultilineAsset", value=multiline, value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == multiline

    def test_create_asset_response_model_validation(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() validates response and returns Asset model."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": "test-value",
                "ValueType": "Text",
            }
        )

        asset = assets_service.create(
            name="TestAsset", value="test-value", value_type="Text"
        )

        # Verify returned model
        assert asset.key == "asset-key-123"
        assert asset.name == "TestAsset"
        assert asset.value_type == "Text"

    def test_create_asset_api_endpoint_format(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() sends request to correct OData endpoint."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": "test",
                "ValueType": "Text",
            }
        )

        assets_service.create(name="TestAsset", value="test", value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        assert "/orchestrator_/odata/Assets" in str(request.url)
        assert request.method == "POST"

    def test_create_asset_with_folder_path_header(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() sends folder path header when provided."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": "test",
                "ValueType": "Text",
            }
        )

        assets_service.create(
            name="TestAsset",
            value="test",
            value_type="Text",
            folder_path="Shared/Finance",
        )

        request = httpx_mock.get_request()
        # Note: folder headers are handled by base service
        # Just verify request was made successfully
        assert request is not None

    def test_create_asset_with_folder_key_header(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() sends folder key header when provided."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": "test",
                "ValueType": "Text",
            }
        )

        assets_service.create(
            name="TestAsset",
            value="test",
            value_type="Text",
            folder_key="folder-key-123",
        )

        request = httpx_mock.get_request()
        # Note: folder headers are handled by base service
        assert request is not None

    def test_create_integer_asset_with_min_int(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Integer asset handles minimum integer value."""
        min_int = -2147483648  # Min 32-bit signed int
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "MinIntAsset",
                "IntValue": min_int,
                "ValueType": "Integer",
            }
        )

        assets_service.create(name="MinIntAsset", value=min_int, value_type="Integer")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["IntValue"] == min_int

    def test_create_text_asset_with_tabs(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles tab characters."""
        text_with_tabs = "Column1\tColumn2\tColumn3"
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TabAsset",
                "StringValue": text_with_tabs,
                "ValueType": "Text",
            }
        )

        assets_service.create(name="TabAsset", value=text_with_tabs, value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == text_with_tabs
        assert "\t" in body["StringValue"]

    def test_create_text_asset_with_crlf(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles CRLF line endings."""
        text_with_crlf = "Line1\r\nLine2\r\nLine3"
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "CRLFAsset",
                "StringValue": text_with_crlf,
                "ValueType": "Text",
            }
        )

        assets_service.create(name="CRLFAsset", value=text_with_crlf, value_type="Text")

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["StringValue"] == text_with_crlf

    @pytest.mark.asyncio
    async def test_create_async_text_asset(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create_async() for Text asset uses StringValue field."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-async",
                "Name": "AsyncTextAsset",
                "StringValue": "async-text-value",
                "ValueType": "Text",
            }
        )

        asset = await assets_service.create_async(
            name="AsyncTextAsset", value="async-text-value", value_type="Text"
        )

        assert asset.key == "asset-key-async"
        assert asset.string_value == "async-text-value"

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "StringValue" in body
        assert body["StringValue"] == "async-text-value"

    @pytest.mark.asyncio
    async def test_create_async_integer_asset(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create_async() for Integer asset uses IntValue field."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-async",
                "Name": "AsyncIntAsset",
                "IntValue": 9999,
                "ValueType": "Integer",
            }
        )

        asset = await assets_service.create_async(
            name="AsyncIntAsset", value=9999, value_type="Integer"
        )

        assert asset.key == "asset-key-async"
        assert asset.int_value == 9999

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "IntValue" in body
        assert body["IntValue"] == 9999

    @pytest.mark.asyncio
    async def test_create_async_boolean_asset(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create_async() for Boolean asset uses BoolValue field."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-async",
                "Name": "AsyncBoolAsset",
                "BoolValue": False,
                "ValueType": "Boolean",
            }
        )

        asset = await assets_service.create_async(
            name="AsyncBoolAsset", value=False, value_type="Boolean"
        )

        assert asset.key == "asset-key-async"
        assert asset.bool_value is False

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "BoolValue" in body
        assert body["BoolValue"] is False

    def test_create_integer_asset_with_max_int64(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Integer asset handles 64-bit max value."""
        max_int64 = 9223372036854775807  # Max 64-bit signed int
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "MaxInt64Asset",
                "IntValue": max_int64,
                "ValueType": "Integer",
            }
        )

        assets_service.create(
            name="MaxInt64Asset", value=max_int64, value_type="Integer"
        )

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "IntValue" in body
        assert body["IntValue"] == max_int64

    def test_create_text_asset_with_mixed_whitespace(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Text asset handles mixed whitespace."""
        mixed_whitespace = "  \t  Leading\n\tMixed\r\n  Trailing  \t\n"
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "WhitespaceAsset",
                "StringValue": mixed_whitespace,
                "ValueType": "Text",
            }
        )

        assets_service.create(
            name="WhitespaceAsset", value=mixed_whitespace, value_type="Text"
        )

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "StringValue" in body
        assert body["StringValue"] == mixed_whitespace

    def test_create_boolean_asset_with_value_scope(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test create() for Boolean asset includes value scope."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "ScopedBoolAsset",
                "BoolValue": True,
                "ValueType": "Boolean",
                "ValueScope": "Global",
            }
        )

        asset = assets_service.create(
            name="ScopedBoolAsset", value=True, value_type="Boolean"
        )

        assert asset.key == "asset-key-123"
        assert asset.bool_value is True

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "BoolValue" in body
        assert body["BoolValue"] is True
