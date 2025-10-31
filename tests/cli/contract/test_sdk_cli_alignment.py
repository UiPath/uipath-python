"""Contract tests to ensure CLI stays aligned with SDK.

These tests catch:
- SDK adds new required parameter → CLI missing option
- SDK renames parameter → CLI option mismatch
- SDK removes parameter → CLI has orphaned option
"""

import inspect
from typing import Any, Optional, Set

import click
import pytest

# Global CLI options that don't map to SDK parameters (or are handled globally)
CLI_GLOBALS = {"format", "output", "folder_path", "folder_key", "debug"}
PAGINATION_OPTIONS = {"limit", "offset", "page_size", "fetch_all"}
# CLI-only options for UX/safety (don't map to SDK params)
CLI_ONLY_OPTIONS = {"confirm", "dry_run"}

# SDK parameters that are exposed as global CLI options
# These appear in SDK methods but are handled by common_service_options decorator
SDK_COMMON_PARAMS = {"folder_path", "folder_key"}


def get_cli_option_names(cmd: click.Command) -> Set[str]:
    """Extract parameter names from a Click command (options AND arguments).

    Args:
        cmd: Click command to inspect

    Returns:
        Set of parameter names (normalized with underscores)
    """
    return {
        param.name.replace("-", "_")
        for param in cmd.params
        if isinstance(param, (click.Option, click.Argument)) and param.name is not None
    }


def get_sdk_param_names(method) -> Set[str]:
    """Extract parameter names from SDK method signature.

    Args:
        method: SDK method to inspect

    Returns:
        Set of parameter names
    """
    sig = inspect.signature(method)
    return {
        name for name in sig.parameters if name not in ["self", "cls", "args", "kwargs"]
    }


def assert_cli_sdk_alignment(
    cli_command: click.Command,
    sdk_method: Any,
    *,
    exclude_cli: Optional[Set[str]] = None,
    exclude_sdk: Optional[Set[str]] = None,
    param_mappings: Optional[dict[str, str]] = None,
) -> None:
    """Assert that CLI command options align with SDK method parameters.

    This is the core contract test that prevents drift between CLI and SDK.

    Args:
        cli_command: Click command to check
        sdk_method: SDK method to compare against
        exclude_cli: CLI options to ignore (beyond globals)
        exclude_sdk: SDK parameters to ignore
        param_mappings: Dict mapping CLI param names to SDK param names
                       e.g., {'bucket_name': 'name', 'remote_path': 'blob_file_path'}

    Raises:
        AssertionError: If parameters don't align
    """
    exclude_cli = (
        (exclude_cli or set()) | CLI_GLOBALS | PAGINATION_OPTIONS | CLI_ONLY_OPTIONS
    )
    exclude_sdk = (exclude_sdk or set()) | SDK_COMMON_PARAMS
    param_mappings = param_mappings or {}

    cli_params = get_cli_option_names(cli_command) - exclude_cli
    sdk_params = get_sdk_param_names(sdk_method) - exclude_sdk

    # Apply parameter name mappings (CLI → SDK)
    # Replace CLI param names with their SDK equivalents for comparison
    cli_params_normalized = set(cli_params)
    for cli_name, sdk_name in param_mappings.items():
        if cli_name in cli_params:
            cli_params_normalized.remove(cli_name)  # Remove CLI name
            cli_params_normalized.add(sdk_name)  # Add SDK name

    # Check for missing CLI options (SDK params not in CLI)
    missing_in_cli = sdk_params - cli_params_normalized
    assert not missing_in_cli, (
        f"CLI command '{cli_command.name}' missing options for SDK parameters: {missing_in_cli}\n"
        f"  SDK method: {sdk_method.__qualname__}\n"
        f"  SDK params: {sdk_params}\n"
        f"  CLI params: {cli_params}\n"
        f"  CLI params (normalized): {cli_params_normalized}"
    )

    # This catches typos or when SDK parameters are removed/renamed
    orphaned_in_cli = cli_params_normalized - sdk_params
    assert not orphaned_in_cli, (
        f"CLI command '{cli_command.name}' has orphaned options not in SDK: {orphaned_in_cli}\n"
        f"  SDK method: {sdk_method.__qualname__}\n"
        f"  SDK params: {sdk_params}\n"
        f"  CLI params (normalized): {cli_params_normalized}\n"
        f"  Hint: Check for typos in CLI option names or SDK parameter removals"
    )


# Parameter mappings: CLI param name → SDK param name
# Used when CLI uses more user-friendly names than SDK
PARAM_MAPPINGS = {
    "buckets_files_download": {
        "bucket_name": "name",
        "remote_path": "blob_file_path",
        "local_path": "destination_path",
    },
    "buckets_files_upload": {
        "bucket_name": "name",
        "local_path": "source_path",
        "remote_path": "blob_file_path",
    },
    "buckets_files_delete": {
        "bucket_name": "name",
        "file_path": "blob_file_path",
    },
    "buckets_files_exists": {
        "bucket_name": "name",
        "file_path": "blob_file_path",
    },
    "buckets_files_list": {
        "bucket_name": "name",
    },
    "buckets_files_search": {
        "bucket_name": "name",
        "pattern": "file_name_glob",
    },
    "buckets_create": {
        "name": "name",  # CLI argument 'name' maps to SDK 'name'
    },
    "buckets_exists": {
        "name": "name",  # CLI argument 'name' maps to SDK 'name'
    },
}

# SDK parameters to exclude for specific commands
# Used when SDK has optional params that CLI doesn't expose
SDK_EXCLUSIONS = {
    "buckets_list": {"name"},  # CLI doesn't expose name filtering yet
    "buckets_retrieve": set(),  # All params exposed
    "buckets_create": {"identifier"},  # CLI doesn't expose identifier
    "buckets_delete": {"key"},  # CLI uses name, not key (yet)
    "buckets_exists": {"key"},  # CLI uses name, not key
    "buckets_files_download": {"key"},  # CLI uses name, not key
    "buckets_files_upload": {
        "key",
        "content",
        "content_type",
    },  # CLI uses name + file path
    "buckets_files_delete": {"key"},  # CLI uses name, not key
    "buckets_files_exists": {"key"},  # CLI uses name, not key
    "buckets_files_list": {"key"},  # CLI uses name, not key
    "buckets_files_search": {"key"},  # CLI uses name, not key
}


# Parameterized test for all service commands
@pytest.mark.parametrize(
    "service,command,sdk_class,sdk_method",
    [
        # Buckets - bucket operations
        ("buckets", "list", "BucketsService", "list"),
        ("buckets", "retrieve", "BucketsService", "retrieve"),
        ("buckets", "create", "BucketsService", "create"),
        ("buckets", "delete", "BucketsService", "delete"),
        ("buckets", "exists", "BucketsService", "exists"),
        # Buckets - file operations (nested under 'files' subgroup)
        ("buckets_files", "upload", "BucketsService", "upload"),
        ("buckets_files", "download", "BucketsService", "download"),
        ("buckets_files", "delete", "BucketsService", "delete_file"),
        ("buckets_files", "exists", "BucketsService", "exists_file"),
        ("buckets_files", "list", "BucketsService", "list_files"),
        ("buckets_files", "search", "BucketsService", "get_files"),
        # Phase 3 - Add as implemented
        # ('assets', 'retrieve', 'AssetsService', 'retrieve'),
        # ('queues', 'list_items', 'QueuesService', 'list_items'),
    ],
)
def test_service_command_params_match_sdk(service, command, sdk_class, sdk_method):
    """Verify CLI command options match SDK method parameters.

    This test runs on every commit to catch SDK/CLI drift early.
    """
    from uipath import _services
    from uipath._cli import services as cli_services

    # Get SDK class and method
    sdk_cls = getattr(_services, sdk_class)
    sdk_meth = getattr(sdk_cls, sdk_method)

    # Get CLI service group and command
    # Handle nested subgroups (e.g., "buckets_files")
    if "_" in service:
        # Nested subgroup (e.g., "buckets_files")
        parts = service.split("_")
        service_group = getattr(cli_services, parts[0])  # Get "buckets"
        subgroup = service_group.commands[parts[1]]  # Get "files" subgroup
        cli_cmd = subgroup.commands[command.replace("_", "-")]
    else:
        # Top-level service group
        service_group = getattr(cli_services, service)
        cli_cmd = service_group.commands[command.replace("_", "-")]

    # Get mappings and exclusions for this command
    mapping_key = f"{service}_{command}"
    param_mappings = PARAM_MAPPINGS.get(mapping_key, {})
    sdk_exclusions = SDK_EXCLUSIONS.get(mapping_key, set())

    # Run alignment check
    assert_cli_sdk_alignment(
        cli_cmd,
        sdk_meth,
        param_mappings=param_mappings,
        exclude_sdk=sdk_exclusions,
    )


def test_contract_test_infrastructure():
    """Meta-test to verify contract test infrastructure works.

    This ensures the contract test helpers themselves are working correctly.
    """

    # Create a simple test command
    @click.command()
    @click.option("--name")
    @click.option("--value")
    def test_cmd(name, value):
        pass

    # Create a matching method
    def test_method(self, name, value):
        pass

    # Should not raise
    assert_cli_sdk_alignment(test_cmd, test_method)


def test_contract_test_detects_missing_cli_option():
    """Meta-test to verify contract test detects missing CLI options."""

    # CLI command missing 'value' option
    @click.command()
    @click.option("--name")
    def test_cmd(name):
        pass

    # SDK method has both name and value
    def test_method(self, name, value):
        pass

    # Should raise assertion error
    with pytest.raises(AssertionError) as exc_info:
        assert_cli_sdk_alignment(test_cmd, test_method)

    assert "missing options" in str(exc_info.value).lower()
    assert "value" in str(exc_info.value)
