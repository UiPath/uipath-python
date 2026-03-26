"""Unit tests for migrated buckets CLI commands.

Tests cover:
- Command structure and existence
- Provenance tracking for auto-generated, overridden, and manual commands
- Backward compatibility with original CLI interface
- Command signatures and options
"""

import click
from click.testing import CliRunner

from uipath._cli._utils._service_cli_generator import GeneratorType
from uipath._cli.services.cli_buckets import buckets

__all__ = [
    "TestBucketsMigrationStructure",
    "TestBucketsProvenance",
    "TestBucketsBackwardCompatibility",
    "TestBucketsCommandSignatures",
]


class TestBucketsMigrationStructure:
    """Test that buckets CLI has correct structure after migration."""

    def test_buckets_group_exists(self):
        """Test that buckets group is created."""
        assert buckets is not None
        assert buckets.name == "buckets"

    def test_standard_crud_commands_exist(self):
        """Test that standard CRUD commands are present."""
        command_names = [cmd.name for cmd in buckets.commands.values()]

        # Auto-generated commands
        assert "list" in command_names
        assert "create" in command_names
        assert "delete" in command_names
        assert "exists" in command_names

        # Overridden command
        assert "retrieve" in command_names

    def test_files_nested_group_exists(self):
        """Test that files nested group is present."""
        command_names = [cmd.name for cmd in buckets.commands.values()]
        assert "files" in command_names

        files_group = buckets.commands["files"]
        assert isinstance(files_group, click.Group)
        files_command_names = [cmd.name for cmd in files_group.commands.values()]

        # All file commands should be present
        assert "list" in files_command_names
        assert "search" in files_command_names
        assert "upload" in files_command_names
        assert "download" in files_command_names
        assert "delete" in files_command_names
        assert "exists" in files_command_names

    def test_total_command_count(self):
        """Test that we have expected number of commands."""
        # 5 bucket commands + 1 files group
        assert len(buckets.commands) == 6

        # 6 file commands
        files_group = buckets.commands["files"]
        assert isinstance(files_group, click.Group)
        assert len(files_group.commands) == 6


class TestBucketsProvenance:
    """Test provenance tracking for migrated commands."""

    def test_auto_generated_list_command_provenance(self):
        """Test that list command has correct auto-generated provenance."""
        list_cmd = buckets.commands["list"]

        assert hasattr(list_cmd, "__provenance__")
        provenance = list_cmd.__provenance__

        assert provenance["generator"] == GeneratorType.AUTO.value
        assert provenance["service_name"] == "buckets"
        assert provenance["resource_type"] == "Bucket"
        assert provenance["command_function"] == "list_cmd"

    def test_auto_generated_create_command_provenance(self):
        """Test that create command has correct auto-generated provenance."""
        create_cmd = buckets.commands["create"]

        assert hasattr(create_cmd, "__provenance__")
        provenance = create_cmd.__provenance__

        assert provenance["generator"] == GeneratorType.AUTO.value
        assert provenance["service_name"] == "buckets"
        assert provenance["resource_type"] == "Bucket"
        assert provenance["command_function"] == "create_cmd"

    def test_auto_generated_delete_command_provenance(self):
        """Test that delete command has correct override provenance."""
        delete_cmd = buckets.commands["delete"]

        assert hasattr(delete_cmd, "__provenance__")
        provenance = delete_cmd.__provenance__

        assert provenance["generator"] == GeneratorType.OVERRIDE.value
        assert provenance["service_name"] == "buckets"
        assert provenance["resource_type"] == "Bucket"
        assert provenance["original_generator"] == GeneratorType.AUTO.value

    def test_auto_generated_exists_command_provenance(self):
        """Test that exists command has correct auto-generated provenance."""
        exists_cmd = buckets.commands["exists"]

        assert hasattr(exists_cmd, "__provenance__")
        provenance = exists_cmd.__provenance__

        assert provenance["generator"] == GeneratorType.AUTO.value
        assert provenance["service_name"] == "buckets"
        assert provenance["resource_type"] == "Bucket"
        assert provenance["command_function"] == "exists_cmd"

    def test_overridden_retrieve_command_provenance(self):
        """Test that retrieve command has correct override provenance."""
        retrieve_cmd = buckets.commands["retrieve"]

        assert hasattr(retrieve_cmd, "__provenance__")
        provenance = retrieve_cmd.__provenance__

        assert provenance["generator"] == GeneratorType.OVERRIDE.value
        assert provenance["service_name"] == "buckets"
        assert provenance["resource_type"] == "Bucket"
        assert "original_generator" in provenance
        assert provenance["original_generator"] == GeneratorType.AUTO.value

    def test_manual_files_nested_group_provenance(self):
        """Test that files nested group has correct manual provenance."""
        files_group = buckets.commands["files"]

        assert hasattr(files_group, "__provenance__")
        provenance = files_group.__provenance__

        assert provenance["generator"] == GeneratorType.MANUAL.value
        assert provenance["service_name"] == "buckets"
        assert provenance["type"] == "nested_group"


class TestBucketsBackwardCompatibility:
    """Test backward compatibility of migrated commands."""

    def test_list_command_help_accessible(self):
        """Test that list command help is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["list", "--help"])

        assert result.exit_code == 0
        assert "List" in result.output or "list" in result.output.lower()

    def test_create_command_has_description_option(self):
        """Test that create command has --description option."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["create", "--help"])

        assert result.exit_code == 0
        assert "Create" in result.output or "create" in result.output.lower()
        assert "--description" in result.output

    def test_retrieve_command_has_name_and_key_options(self):
        """Test that retrieve command has both --name and --key options."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["retrieve", "--help"])

        assert result.exit_code == 0
        assert "Retrieve" in result.output or "retrieve" in result.output.lower()
        assert "--name" in result.output
        assert "--key" in result.output

    def test_delete_command_has_confirmation_options(self):
        """Test that delete command has --confirm and --dry-run options."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["delete", "--help"])

        assert result.exit_code == 0
        assert "Delete" in result.output or "delete" in result.output.lower()
        assert "--confirm" in result.output
        assert "--dry-run" in result.output

    def test_exists_command_help_accessible(self):
        """Test that exists command help is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["exists", "--help"])

        assert result.exit_code == 0
        # Exists command should have help text
        assert len(result.output) > 0

    def test_files_list_command_accessible(self):
        """Test that files list command is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["files", "list", "--help"])

        assert result.exit_code == 0
        assert "List" in result.output or "list" in result.output.lower()
        assert "bucket" in result.output.lower()

    def test_files_search_command_accessible(self):
        """Test that files search command is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["files", "search", "--help"])

        assert result.exit_code == 0
        assert "Search" in result.output or "search" in result.output.lower()

    def test_files_upload_command_accessible(self):
        """Test that files upload command is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["files", "upload", "--help"])

        assert result.exit_code == 0
        assert "Upload" in result.output or "upload" in result.output.lower()

    def test_files_download_command_accessible(self):
        """Test that files download command is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["files", "download", "--help"])

        assert result.exit_code == 0
        assert "Download" in result.output or "download" in result.output.lower()

    def test_files_delete_command_accessible(self):
        """Test that files delete command is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["files", "delete", "--help"])

        assert result.exit_code == 0
        assert "Delete" in result.output or "delete" in result.output.lower()

    def test_files_exists_command_accessible(self):
        """Test that files exists command is accessible."""
        runner = CliRunner()
        result = runner.invoke(buckets, ["files", "exists", "--help"])

        assert result.exit_code == 0
        # Exists command should have help text
        assert len(result.output) > 0


class TestBucketsCommandSignatures:
    """Test that command signatures match expectations."""

    def test_list_command_has_standard_options(self):
        """Test list command has standard service options."""
        list_cmd = buckets.commands["list"]
        option_names = [param.name for param in list_cmd.params]

        # Standard service options
        assert "folder_path" in option_names
        assert "folder_key" in option_names
        assert "format" in option_names
        assert "output" in option_names

        # List-specific options
        assert "limit" in option_names
        assert "offset" in option_names

    def test_create_command_has_required_parameters(self):
        """Test create command has name and description parameters."""
        create_cmd = buckets.commands["create"]
        option_names = [param.name for param in create_cmd.params]

        assert "name" in option_names  # Positional argument
        assert "description" in option_names
        assert "folder_path" in option_names
        assert "folder_key" in option_names
        assert "format" in option_names
        assert "output" in option_names

    def test_retrieve_command_has_dual_options(self):
        """Test retrieve command has both --name and --key options."""
        retrieve_cmd = buckets.commands["retrieve"]
        option_names = [param.name for param in retrieve_cmd.params]

        # Dual identifier options
        assert "name" in option_names
        assert "key" in option_names

        # Standard service options
        assert "folder_path" in option_names
        assert "folder_key" in option_names
        assert "format" in option_names
        assert "output" in option_names

    def test_delete_command_has_confirmation_parameters(self):
        """Test delete command has confirmation and dry-run parameters."""
        delete_cmd = buckets.commands["delete"]
        option_names = [param.name for param in delete_cmd.params]

        assert "name" in option_names
        assert "confirm" in option_names
        assert "dry_run" in option_names
        assert "folder_path" in option_names
        assert "folder_key" in option_names

    def test_exists_command_has_name_parameter(self):
        """Test exists command has name parameter."""
        exists_cmd = buckets.commands["exists"]
        option_names = [param.name for param in exists_cmd.params]

        assert "name" in option_names
        assert "folder_path" in option_names
        assert "folder_key" in option_names

    def test_files_list_has_bucket_name_and_options(self):
        """Test files list command has bucket_name and filtering options."""
        files_group = buckets.commands["files"]
        assert isinstance(files_group, click.Group)
        list_files_cmd = files_group.commands["list"]
        option_names = [param.name for param in list_files_cmd.params]

        assert "bucket_name" in option_names
        assert "prefix" in option_names
        assert "limit" in option_names
        assert "offset" in option_names
        assert "fetch_all" in option_names

    def test_files_upload_has_required_paths(self):
        """Test files upload command has local_path and remote_path."""
        files_group = buckets.commands["files"]
        assert isinstance(files_group, click.Group)
        upload_cmd = files_group.commands["upload"]
        option_names = [param.name for param in upload_cmd.params]

        assert "bucket_name" in option_names
        assert "local_path" in option_names
        assert "remote_path" in option_names

    def test_files_download_has_required_paths(self):
        """Test files download command has remote_path and local_path."""
        files_group = buckets.commands["files"]
        assert isinstance(files_group, click.Group)
        download_cmd = files_group.commands["download"]
        option_names = [param.name for param in download_cmd.params]

        assert "bucket_name" in option_names
        assert "remote_path" in option_names
        assert "local_path" in option_names
