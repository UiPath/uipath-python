"""Unit tests for ServiceMetadata Pydantic models.

Tests cover:
- CreateParameter model creation and immutability
- DeleteCommandConfig defaults
- ExistsCommandConfig configuration
- ServiceMetadata model creation
- ServiceMetadata validators and defaults
- Type validation
- Model immutability (frozen=True)
"""

import pytest
from pydantic import ValidationError

from uipath._cli._utils._service_metadata import (
    CreateParameter,
    DeleteCommandConfig,
    ExistsCommandConfig,
    ServiceMetadata,
)

__all__ = [
    "TestCreateParameter",
    "TestDeleteCommandConfig",
    "TestExistsCommandConfig",
    "TestServiceMetadata",
    "TestServiceMetadataValidation",
    "TestServiceMetadataRealWorldExamples",
]


class TestCreateParameter:
    """Test CreateParameter model."""

    def test_create_parameter_minimal(self):
        """Test creating parameter with minimal fields."""
        param = CreateParameter(type="str")

        assert param.type == "str"
        assert param.required is False  # Default
        assert param.help == ""  # Default
        assert param.default is None  # Default
        assert param.option_name is None  # Default

    def test_create_parameter_full(self):
        """Test creating parameter with all fields."""
        param = CreateParameter(
            type="int",
            required=True,
            help="A number parameter",
            default=42,
            option_name="num",
        )

        assert param.type == "int"
        assert param.required is True
        assert param.help == "A number parameter"
        assert param.default == 42
        assert param.option_name == "num"

    def test_create_parameter_immutable(self):
        """Test that CreateParameter is immutable (frozen=True)."""
        param = CreateParameter(type="str", help="Original")

        with pytest.raises((ValidationError, AttributeError)):
            param.help = "Modified"  # type: ignore[misc]  # Testing that this raises

    def test_create_parameter_different_types(self):
        """Test creating parameters with different types."""
        str_param = CreateParameter(type="str")
        int_param = CreateParameter(type="int")
        bool_param = CreateParameter(type="bool")
        float_param = CreateParameter(type="float")

        assert str_param.type == "str"
        assert int_param.type == "int"
        assert bool_param.type == "bool"
        assert float_param.type == "float"


class TestDeleteCommandConfig:
    """Test DeleteCommandConfig model."""

    def test_delete_command_config_defaults(self):
        """Test default values for delete configuration."""
        config = DeleteCommandConfig()

        assert config.confirmation_required is True
        assert config.dry_run_supported is True
        assert config.confirmation_prompt is None

    def test_delete_command_config_custom(self):
        """Test custom delete configuration."""
        config = DeleteCommandConfig(
            confirmation_required=False,
            dry_run_supported=False,
            confirmation_prompt="Are you sure?",
        )

        assert config.confirmation_required is False
        assert config.dry_run_supported is False
        assert config.confirmation_prompt == "Are you sure?"

    def test_delete_command_config_immutable(self):
        """Test that DeleteCommandConfig is immutable."""
        config = DeleteCommandConfig()

        with pytest.raises((ValidationError, AttributeError)):
            config.confirmation_required = False  # type: ignore[misc]  # Testing that this raises


class TestExistsCommandConfig:
    """Test ExistsCommandConfig model."""

    def test_exists_command_config_defaults(self):
        """Test default values for exists configuration."""
        config = ExistsCommandConfig()

        assert config.identifier_arg_name == "name"
        assert config.return_format == "dict"

    def test_exists_command_config_custom(self):
        """Test custom exists configuration."""
        config = ExistsCommandConfig(
            identifier_arg_name="key",
            return_format="bool",
        )

        assert config.identifier_arg_name == "key"
        assert config.return_format == "bool"

    def test_exists_command_config_immutable(self):
        """Test that ExistsCommandConfig is immutable."""
        config = ExistsCommandConfig()

        with pytest.raises((ValidationError, AttributeError)):
            config.identifier_arg_name = "id"  # type: ignore[misc]  # Testing that this raises


class TestServiceMetadata:
    """Test ServiceMetadata model."""

    def test_service_metadata_minimal(self):
        """Test creating metadata with minimal required fields."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        assert metadata.service_name == "test"
        assert metadata.service_attr == "test"
        assert metadata.resource_type == "Test"
        assert metadata.resource_plural == "Tests"  # Auto-generated
        assert metadata.create_params == {}  # Default
        assert isinstance(metadata.delete_cmd, DeleteCommandConfig)
        assert isinstance(metadata.exists_cmd, ExistsCommandConfig)

    def test_service_metadata_auto_plural(self):
        """Test that resource_plural is auto-generated from resource_type."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
        )

        assert metadata.resource_plural == "Buckets"

    def test_service_metadata_custom_plural(self):
        """Test specifying custom resource_plural."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Process",
            resource_plural="Processes",  # Custom (not "Processs")
        )

        assert metadata.resource_plural == "Processes"

    def test_service_metadata_with_create_params(self):
        """Test metadata with create parameters."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
            create_params={
                "description": CreateParameter(
                    type="str",
                    required=False,
                    help="Bucket description",
                ),
                "max_size": CreateParameter(
                    type="int",
                    required=False,
                    help="Maximum size in MB",
                    default=1000,
                ),
            },
        )

        assert len(metadata.create_params) == 2
        assert "description" in metadata.create_params
        assert "max_size" in metadata.create_params
        assert metadata.create_params["description"].type == "str"
        assert metadata.create_params["max_size"].type == "int"
        assert metadata.create_params["max_size"].default == 1000

    def test_service_metadata_immutable(self):
        """Test that ServiceMetadata is immutable."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        with pytest.raises((ValidationError, AttributeError)):
            metadata.service_name = "modified"  # type: ignore[misc]  # Testing that this raises

    def test_service_metadata_custom_delete_config(self):
        """Test metadata with custom delete configuration."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            delete_cmd=DeleteCommandConfig(
                confirmation_required=False,
                dry_run_supported=False,
            ),
        )

        assert metadata.delete_cmd.confirmation_required is False
        assert metadata.delete_cmd.dry_run_supported is False

    def test_service_metadata_custom_exists_config(self):
        """Test metadata with custom exists configuration."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            exists_cmd=ExistsCommandConfig(
                identifier_arg_name="key",
                return_format="bool",
            ),
        )

        assert metadata.exists_cmd.identifier_arg_name == "key"
        assert metadata.exists_cmd.return_format == "bool"


class TestServiceMetadataValidation:
    """Test ServiceMetadata validation methods."""

    def test_validate_types_valid(self):
        """Test validate_types() with valid types."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            create_params={
                "param1": CreateParameter(type="str"),
                "param2": CreateParameter(type="int"),
                "param3": CreateParameter(type="bool"),
            },
        )

        # Should not raise
        metadata.validate_types()

    def test_validate_types_invalid_raises(self):
        """Test validate_types() raises for invalid type."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            create_params={
                "invalid_param": CreateParameter(type="InvalidType"),
            },
        )

        with pytest.raises(ValueError) as exc_info:
            metadata.validate_types()

        error_msg = str(exc_info.value)
        assert "Invalid type 'InvalidType'" in error_msg
        assert "invalid_param" in error_msg
        assert "Valid types:" in error_msg

    def test_validate_types_multiple_invalid(self):
        """Test validate_types() with multiple invalid types."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            create_params={
                "param1": CreateParameter(type="str"),  # Valid
                "param2": CreateParameter(type="BadType"),  # Invalid
                "param3": CreateParameter(type="int"),  # Valid
            },
        )

        with pytest.raises(ValueError) as exc_info:
            metadata.validate_types()

        error_msg = str(exc_info.value)
        assert "BadType" in error_msg
        assert "param2" in error_msg


class TestServiceMetadataRealWorldExamples:
    """Test ServiceMetadata with real-world service examples."""

    def test_buckets_metadata(self):
        """Test metadata for buckets service."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
            create_params={
                "description": CreateParameter(
                    type="str",
                    required=False,
                    help="Bucket description",
                ),
            },
        )

        assert metadata.service_name == "buckets"
        assert metadata.resource_plural == "Buckets"
        assert "description" in metadata.create_params
        metadata.validate_types()  # Should not raise

    def test_assets_metadata(self):
        """Test metadata for assets service."""
        metadata = ServiceMetadata(
            service_name="assets",
            service_attr="assets",
            resource_type="Asset",
            create_params={
                "value": CreateParameter(
                    type="str",
                    required=True,
                    help="Asset value",
                ),
                "description": CreateParameter(
                    type="str",
                    required=False,
                    help="Asset description",
                ),
            },
        )

        assert metadata.service_name == "assets"
        assert len(metadata.create_params) == 2
        assert metadata.create_params["value"].required is True
        metadata.validate_types()  # Should not raise

    def test_queues_metadata(self):
        """Test metadata for queues service."""
        metadata = ServiceMetadata(
            service_name="queues",
            service_attr="queues",
            resource_type="Queue",
            create_params={
                "description": CreateParameter(
                    type="str",
                    required=False,
                    help="Queue description",
                ),
                "max_retries": CreateParameter(
                    type="int",
                    required=False,
                    help="Maximum retry attempts",
                    default=0,
                ),
            },
        )

        assert metadata.service_name == "queues"
        assert metadata.create_params["max_retries"].default == 0
        metadata.validate_types()  # Should not raise
