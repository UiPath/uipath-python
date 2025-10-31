"""Unit tests for ServiceCLIGenerator.

Tests cover:
- Generator initialization and validation
- register() method creating CRUD commands
- Command generation for list, retrieve, create, delete, exists
- Parameter handling and type resolution
- Confirmation and dry-run support
- Error handling
- Provenance tracking
"""

import click
import pytest

from uipath._cli._utils._service_cli_generator import ServiceCLIGenerator
from uipath._cli._utils._service_metadata import (
    CreateParameter,
    DeleteCommandConfig,
    ExistsCommandConfig,
    ServiceMetadata,
)


class TestServiceCLIGeneratorInitialization:
    """Test ServiceCLIGenerator initialization."""

    def test_generator_initialization_valid_metadata(self):
        """Test generator initializes with valid metadata."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        assert generator.metadata == metadata
        assert isinstance(generator._command_names, set)
        assert len(generator._command_names) == 0  # No commands registered yet
        assert isinstance(generator._provenance, dict)

    def test_generator_initialization_with_create_params(self):
        """Test generator initializes with create parameters."""
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

        generator = ServiceCLIGenerator(metadata)

        assert generator.metadata == metadata
        assert "description" in generator.metadata.create_params

    def test_generator_initialization_validates_types(self):
        """Test generator validates parameter types during initialization."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            create_params={
                "invalid": CreateParameter(type="InvalidType", required=False),
            },
        )

        with pytest.raises(ValueError) as exc_info:
            ServiceCLIGenerator(metadata)

        error_msg = str(exc_info.value)
        assert "InvalidType" in error_msg
        assert "invalid" in error_msg


class TestServiceCLIGeneratorRegister:
    """Test register() method."""

    def test_register_creates_service_group(self):
        """Test that register creates a service group."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
        )

        generator = ServiceCLIGenerator(metadata)

        # Create parent group
        @click.group()
        def cli():
            pass

        # Register service
        service_group = generator.register(cli)

        # Verify group was created
        assert service_group is not None
        assert service_group.name == "buckets"
        assert service_group.help == "Manage Buckets"

        # Verify group was added to parent
        assert "buckets" in cli.commands

    def test_register_creates_crud_commands(self):
        """Test that register creates all CRUD commands."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Verify all CRUD commands were created
        assert "list" in service_group.commands
        assert "retrieve" in service_group.commands
        assert "create" in service_group.commands
        assert "delete" in service_group.commands
        assert "exists" in service_group.commands

    def test_register_tracks_command_names(self):
        """Test that register tracks generated command names."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        generator.register(cli)

        # Verify command names were tracked
        command_names = generator.get_command_names()
        assert "list" in command_names
        assert "retrieve" in command_names
        assert "create" in command_names
        assert "delete" in command_names
        assert "exists" in command_names


class TestGeneratedListCommand:
    """Test generated list command."""

    def test_list_command_has_correct_options(self):
        """Test list command has folder options."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        list_cmd = service_group.commands["list"]

        # Check that command has folder-path and folder-key options
        param_names = [p.name for p in list_cmd.params]
        assert "folder_path" in param_names
        assert "folder_key" in param_names

    def test_list_command_exists(self):
        """Test list command is created successfully."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
            resource_plural="Buckets",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        list_cmd = service_group.commands["list"]

        # Verify command exists and is callable
        assert list_cmd is not None
        assert callable(list_cmd.callback)


class TestGeneratedRetrieveCommand:
    """Test generated retrieve command."""

    def test_retrieve_command_has_name_argument(self):
        """Test retrieve command has NAME argument."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        retrieve_cmd = service_group.commands["retrieve"]

        # Check for NAME argument
        param_names = [p.name for p in retrieve_cmd.params]
        assert "name" in param_names

        # Verify it's an argument, not an option
        name_param = next(p for p in retrieve_cmd.params if p.name == "name")
        assert isinstance(name_param, click.Argument)

    def test_retrieve_command_has_folder_options(self):
        """Test retrieve command has folder options."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        retrieve_cmd = service_group.commands["retrieve"]

        param_names = [p.name for p in retrieve_cmd.params]
        assert "folder_path" in param_names
        assert "folder_key" in param_names


class TestGeneratedCreateCommand:
    """Test generated create command."""

    def test_create_command_has_name_argument(self):
        """Test create command has NAME argument."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        create_cmd = service_group.commands["create"]

        param_names = [p.name for p in create_cmd.params]
        assert "name" in param_names

    def test_create_command_has_custom_parameters(self):
        """Test create command includes custom parameters from metadata."""
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

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        create_cmd = service_group.commands["create"]

        param_names = [p.name for p in create_cmd.params]
        assert "description" in param_names
        assert "max_size" in param_names

    def test_create_command_parameter_types(self):
        """Test create command parameters have correct types."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            create_params={
                "count": CreateParameter(type="int", required=False),
                "enabled": CreateParameter(type="bool", required=False),
                "ratio": CreateParameter(type="float", required=False),
            },
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        create_cmd = service_group.commands["create"]

        # Find parameter objects
        count_param = next(p for p in create_cmd.params if p.name == "count")
        enabled_param = next(p for p in create_cmd.params if p.name == "enabled")
        ratio_param = next(p for p in create_cmd.params if p.name == "ratio")

        # Verify types (Click uses lowercase names - int=integer, bool=boolean)
        assert (
            count_param.type.name.lower() == "integer" or count_param.type.name == "INT"
        )
        assert enabled_param.type.name.lower() in ("bool", "boolean")
        assert ratio_param.type.name.lower() == "float"

    def test_create_command_required_parameters(self):
        """Test create command respects required flag."""
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

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        create_cmd = service_group.commands["create"]

        # Find parameter objects
        value_param = next(p for p in create_cmd.params if p.name == "value")
        description_param = next(
            p for p in create_cmd.params if p.name == "description"
        )

        # Verify required flags
        assert value_param.required is True
        assert description_param.required is False


class TestGeneratedDeleteCommand:
    """Test generated delete command."""

    def test_delete_command_has_name_argument(self):
        """Test delete command has NAME argument."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        delete_cmd = service_group.commands["delete"]

        param_names = [p.name for p in delete_cmd.params]
        assert "name" in param_names

    def test_delete_command_has_confirm_option_by_default(self):
        """Test delete command has --confirm option by default."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        delete_cmd = service_group.commands["delete"]

        param_names = [p.name for p in delete_cmd.params]
        assert "confirm" in param_names

    def test_delete_command_has_dry_run_option_by_default(self):
        """Test delete command has --dry-run option by default."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        delete_cmd = service_group.commands["delete"]

        param_names = [p.name for p in delete_cmd.params]
        assert "dry_run" in param_names

    def test_delete_command_without_confirmation(self):
        """Test delete command can disable confirmation."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            delete_cmd=DeleteCommandConfig(
                confirmation_required=False,
                dry_run_supported=True,
            ),
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        delete_cmd = service_group.commands["delete"]

        param_names = [p.name for p in delete_cmd.params]
        assert "confirm" not in param_names
        assert "dry_run" in param_names  # Still has dry-run

    def test_delete_command_without_dry_run(self):
        """Test delete command can disable dry-run."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            delete_cmd=DeleteCommandConfig(
                confirmation_required=True,
                dry_run_supported=False,
            ),
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        delete_cmd = service_group.commands["delete"]

        param_names = [p.name for p in delete_cmd.params]
        assert "confirm" in param_names
        assert "dry_run" not in param_names


class TestGeneratedExistsCommand:
    """Test generated exists command."""

    def test_exists_command_has_name_argument(self):
        """Test exists command has NAME argument."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        exists_cmd = service_group.commands["exists"]

        param_names = [p.name for p in exists_cmd.params]
        assert "name" in param_names

    def test_exists_command_custom_identifier(self):
        """Test exists command with custom identifier argument."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
            exists_cmd=ExistsCommandConfig(
                identifier_arg_name="key",
                return_format="bool",
            ),
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)
        exists_cmd = service_group.commands["exists"]

        param_names = [p.name for p in exists_cmd.params]
        assert "key" in param_names


class TestProvenance:
    """Test provenance tracking."""

    def test_get_command_names_returns_all_commands(self):
        """Test get_command_names returns all generated commands."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        generator.register(cli)

        command_names = generator.get_command_names()

        assert "list" in command_names
        assert "retrieve" in command_names
        assert "create" in command_names
        assert "delete" in command_names
        assert "exists" in command_names
        assert len(command_names) == 5

    def test_get_provenance_returns_command_info(self):
        """Test get_provenance returns command metadata."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        generator.register(cli)

        provenance = generator.get_provenance("list")

        assert provenance is not None
        assert provenance["generator"] == "ServiceCLIGenerator"
        assert provenance["service_name"] == "buckets"
        assert provenance["resource_type"] == "Bucket"
        assert "command_function" in provenance

    def test_get_provenance_returns_none_for_unknown_command(self):
        """Test get_provenance returns None for unknown command."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        provenance = generator.get_provenance("unknown")

        assert provenance is None


class TestAdvancedFeatures:
    """Test advanced features: add_nested_group, override_command, collision detection."""

    def test_add_nested_group_success(self):
        """Test adding a custom nested group successfully."""
        metadata = ServiceMetadata(
            service_name="buckets",
            service_attr="buckets",
            resource_type="Bucket",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Create custom nested group
        @click.group()
        def file_group():
            """File operations"""
            pass

        @file_group.command("upload")
        def upload():
            """Upload a file"""
            pass

        # Add nested group
        generator.add_nested_group(service_group, "file", file_group)

        # Verify nested group was added
        assert "file" in service_group.commands
        assert "file" in generator.get_command_names()

        # Verify provenance
        provenance = generator.get_provenance("file")
        assert provenance is not None
        assert provenance["generator"] == "manual"
        assert provenance["type"] == "nested_group"

    def test_add_nested_group_collision_with_generated_command(self):
        """Test that adding nested group with existing name raises error."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Try to add nested group with name that conflicts
        @click.group()
        def list_group():
            """Custom list"""
            pass

        with pytest.raises(ValueError) as exc_info:
            generator.add_nested_group(service_group, "list", list_group)

        error_msg = str(exc_info.value)
        assert "Cannot add nested group 'list'" in error_msg
        assert "conflicts with auto-generated command" in error_msg

    def test_override_command_success(self):
        """Test overriding an auto-generated command successfully."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Create custom command
        @click.command("list")
        def custom_list():
            """Custom list implementation"""
            pass

        # Override the auto-generated list command
        generator.override_command(service_group, "list", custom_list)

        # Verify command was overridden
        assert "list" in service_group.commands
        list_cmd = service_group.commands["list"]
        # The command should be the custom_command Click object
        assert list_cmd == custom_list

        # Verify provenance shows override
        provenance = generator.get_provenance("list")
        assert provenance is not None
        assert provenance["generator"] == "manual_override"
        assert provenance["original_generator"] == "ServiceCLIGenerator"

    def test_override_command_nonexistent(self):
        """Test that overriding nonexistent command raises error."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        @click.command("nonexistent")
        def custom_cmd():
            pass

        with pytest.raises(ValueError) as exc_info:
            generator.override_command(service_group, "nonexistent", custom_cmd)

        error_msg = str(exc_info.value)
        assert "Cannot override command 'nonexistent'" in error_msg
        assert "does not exist" in error_msg

    def test_override_command_non_generated(self):
        """Test that overriding non-generated command raises error."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Add a manual nested group first
        @click.group()
        def file_group():
            """File operations"""
            pass

        generator.add_nested_group(service_group, "file", file_group)

        # Try to override the manually added group
        @click.command("file")
        def custom_file():
            pass

        with pytest.raises(ValueError) as exc_info:
            generator.override_command(service_group, "file", custom_file)

        error_msg = str(exc_info.value)
        assert "Cannot override command 'file'" in error_msg
        assert "not an auto-generated command" in error_msg

    def test_validate_no_collisions_success(self):
        """Test collision validation with no collisions."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Check commands that don't collide
        errors = generator.validate_no_collisions(service_group, ["custom1", "custom2"])

        assert errors == []

    def test_validate_no_collisions_with_conflicts(self):
        """Test collision validation detects conflicts."""
        metadata = ServiceMetadata(
            service_name="test",
            service_attr="test",
            resource_type="Test",
        )

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Check commands that do collide
        errors = generator.validate_no_collisions(
            service_group, ["list", "retrieve", "custom"]
        )

        assert len(errors) == 2
        assert "Command 'list' conflicts" in errors[0]
        assert "Command 'retrieve' conflicts" in errors[1]


class TestRealWorldExamples:
    """Test generator with real-world service examples."""

    def test_buckets_service_metadata(self):
        """Test generator with buckets service metadata."""
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

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Verify group created
        assert service_group.name == "buckets"

        # Verify all commands exist
        assert "list" in service_group.commands
        assert "retrieve" in service_group.commands
        assert "create" in service_group.commands
        assert "delete" in service_group.commands
        assert "exists" in service_group.commands

        # Verify create has description parameter
        create_cmd = service_group.commands["create"]
        param_names = [p.name for p in create_cmd.params]
        assert "description" in param_names

    def test_assets_service_metadata(self):
        """Test generator with assets service metadata."""
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

        generator = ServiceCLIGenerator(metadata)

        @click.group()
        def cli():
            pass

        service_group = generator.register(cli)

        # Verify create has value and description parameters
        create_cmd = service_group.commands["create"]
        param_names = [p.name for p in create_cmd.params]
        assert "value" in param_names
        assert "description" in param_names

        # Verify value is required
        value_param = next(p for p in create_cmd.params if p.name == "value")
        assert value_param.required is True
