import pytest

from uipath._utils import resource_override
from uipath._utils._bindings import (
    ResourceOverwrite,
    ResourceOverwritesContext,
    _resource_overwrites,
)


class TestBindingsInference:
    def test_infer_bindings_overwrites_name_and_folder_path(self):
        """Test that infer_bindings overwrites both name and folder_path when context is set."""
        overwrites = {
            "bucket.old_name.old_folder": ResourceOverwrite(
                overwrite_name="new_name", overwrite_folder_path="new_folder"
            )
        }

        @resource_override(resource_type="bucket")
        def dummy_func(name, folder_path):
            return name, folder_path

        # Set the context variable
        token = _resource_overwrites.set(overwrites)
        try:
            result = dummy_func("old_name", "old_folder")
            assert result == ("new_name", "new_folder")
        finally:
            _resource_overwrites.reset(token)

    def test_infer_bindings_overwrites_without_folder_path(self):
        """Test that infer_bindings overwrites when key doesn't include folder_path."""
        overwrites = {
            "bucket.old_name": ResourceOverwrite(
                overwrite_name="new_name", overwrite_folder_path="new_folder"
            )
        }

        @resource_override(resource_type="bucket")
        def dummy_func(name, folder_path):
            return name, folder_path

        # Set the context variable
        token = _resource_overwrites.set(overwrites)
        try:
            result = dummy_func("old_name", "old_folder")
            assert result == ("new_name", "new_folder")
        finally:
            _resource_overwrites.reset(token)

    def test_infer_bindings_skips_when_no_context(self):
        """Test that infer_bindings doesn't overwrite when context variable is not set."""

        @resource_override(resource_type="bucket")
        def dummy_func(name, folder_path):
            return name, folder_path

        result = dummy_func("old_name", "old_folder")
        assert result == ("old_name", "old_folder")

    def test_infer_bindings_skips_when_no_matching_overwrite(self):
        """Test that infer_bindings doesn't overwrite when no matching key exists."""
        overwrites = {
            "bucket.different_name": ResourceOverwrite(
                overwrite_name="new_name", overwrite_folder_path="new_folder"
            )
        }

        @resource_override(resource_type="bucket")
        def dummy_func(name, folder_path):
            return name, folder_path

        # Set the context variable
        token = _resource_overwrites.set(overwrites)
        try:
            result = dummy_func("old_name", "old_folder")
            assert result == ("old_name", "old_folder")
        finally:
            _resource_overwrites.reset(token)

    def test_infer_bindings_only_name_present(self):
        """Test that infer_bindings works when only name parameter is present."""
        overwrites = {
            "asset.old_name": ResourceOverwrite(
                overwrite_name="new_name", overwrite_folder_path="new_folder"
            )
        }

        @resource_override(resource_type="asset")
        def dummy_func(name, folder_path=None):
            return name, folder_path

        # Set the context variable
        token = _resource_overwrites.set(overwrites)
        try:
            result = dummy_func("old_name")
            assert result == ("new_name", "new_folder")
        finally:
            _resource_overwrites.reset(token)

    def test_infer_bindings_prefers_specific_folder_path_key(self):
        """Test that infer_bindings prefers the more specific key with folder_path."""
        overwrites = {
            "bucket.my_bucket": ResourceOverwrite(
                overwrite_name="generic_name", overwrite_folder_path="generic_folder"
            ),
            "bucket.my_bucket.specific_folder": ResourceOverwrite(
                overwrite_name="specific_name", overwrite_folder_path="specific_folder"
            ),
        }

        @resource_override(resource_type="bucket")
        def dummy_func(name, folder_path):
            return name, folder_path

        # Set the context variable
        token = _resource_overwrites.set(overwrites)
        try:
            result = dummy_func("my_bucket", "specific_folder")
            assert result == ("specific_name", "specific_folder")
        finally:
            _resource_overwrites.reset(token)


class TestResourceOverwritesContext:
    """Test that ResourceOverwritesContext works correctly with infer_bindings."""

    @pytest.mark.anyio
    async def test_context_with_simple_async_function(self):
        """Test ResourceOverwritesContext with a simple async function."""

        async def get_overwrites():
            return {
                "asset.test_asset": ResourceOverwrite(
                    overwrite_name="overwritten_asset",
                    overwrite_folder_path="overwritten_folder",
                )
            }

        @resource_override(resource_type="asset")
        def retrieve_asset(name, folder_path=None):
            return name, folder_path

        async with ResourceOverwritesContext(get_overwrites) as ctx:
            # Verify context reports the correct count
            assert ctx.overwrites_count == 1

            # Verify infer_bindings applies the overwrites
            result = retrieve_asset("test_asset", "original_folder")
            assert result == ("overwritten_asset", "overwritten_folder")

        # Verify context is cleaned up after exiting
        result_after = retrieve_asset("test_asset", "original_folder")
        assert result_after == ("test_asset", "original_folder")

    @pytest.mark.anyio
    async def test_context_with_lambda(self):
        """Test ResourceOverwritesContext with a lambda (as used in CLI code)."""

        class MockClient:
            async def get_resource_overwrites(self):
                return {
                    "bucket.my_bucket": ResourceOverwrite(
                        overwrite_name="prod_bucket",
                        overwrite_folder_path="prod_folder",
                    )
                }

        client = MockClient()

        @resource_override(resource_type="bucket")
        def use_bucket(name, folder_path):
            return name, folder_path

        async with ResourceOverwritesContext(
            lambda: client.get_resource_overwrites()
        ) as ctx:
            assert ctx.overwrites_count == 1
            result = use_bucket("my_bucket", "dev_folder")
            assert result == ("prod_bucket", "prod_folder")

    @pytest.mark.anyio
    async def test_context_with_read_from_file_pattern(self):
        """Test ResourceOverwritesContext with file reading pattern."""

        async def read_resource_overwrites_from_file(directory=None):
            """Simulates reading from a file."""
            return {
                "process.my_process": ResourceOverwrite(
                    overwrite_name="overwritten_process",
                    overwrite_folder_path="overwritten_folder",
                )
            }

        @resource_override(resource_type="process")
        def start_process(name, folder_path):
            return name, folder_path

        async with ResourceOverwritesContext(
            lambda: read_resource_overwrites_from_file("/some/path")
        ) as ctx:
            assert ctx.overwrites_count == 1
            result = start_process("my_process", "default_folder")
            assert result == ("overwritten_process", "overwritten_folder")

    @pytest.mark.anyio
    async def test_context_with_multiple_overwrites(self):
        """Test ResourceOverwritesContext with multiple resource overwrites."""

        async def get_overwrites():
            return {
                "asset.asset1": ResourceOverwrite(
                    overwrite_name="new_asset1", overwrite_folder_path="folder1"
                ),
                "asset.asset2": ResourceOverwrite(
                    overwrite_name="new_asset2", overwrite_folder_path="folder2"
                ),
                "bucket.bucket1.specific": ResourceOverwrite(
                    overwrite_name="new_bucket1", overwrite_folder_path="new_specific"
                ),
            }

        @resource_override(resource_type="asset")
        def get_asset(name, folder_path):
            return name, folder_path

        @resource_override(resource_type="bucket")
        def get_bucket(name, folder_path):
            return name, folder_path

        async with ResourceOverwritesContext(get_overwrites) as ctx:
            assert ctx.overwrites_count == 3

            # Test first asset
            result1 = get_asset("asset1", "old_folder")
            assert result1 == ("new_asset1", "folder1")

            # Test second asset
            result2 = get_asset("asset2", "old_folder")
            assert result2 == ("new_asset2", "folder2")

            # Test bucket with specific folder path
            result3 = get_bucket("bucket1", "specific")
            assert result3 == ("new_bucket1", "new_specific")

    @pytest.mark.anyio
    async def test_context_with_empty_overwrites(self):
        """Test ResourceOverwritesContext with no overwrites."""

        async def get_overwrites():
            return {}

        @resource_override(resource_type="asset")
        def get_asset(name, folder_path):
            return name, folder_path

        async with ResourceOverwritesContext(get_overwrites) as ctx:
            assert ctx.overwrites_count == 0

            # Should not modify anything
            result = get_asset("test_asset", "test_folder")
            assert result == ("test_asset", "test_folder")

    @pytest.mark.anyio
    async def test_context_nested_function_calls(self):
        """Test that overwrites work with nested function calls."""

        async def get_overwrites():
            return {
                "asset.config_asset": ResourceOverwrite(
                    overwrite_name="prod_config", overwrite_folder_path="prod"
                ),
                "bucket.data_bucket": ResourceOverwrite(
                    overwrite_name="prod_data", overwrite_folder_path="prod"
                ),
            }

        @resource_override(resource_type="asset")
        def get_config(name, folder_path):
            return name, folder_path

        @resource_override(resource_type="bucket")
        def get_data(name, folder_path):
            return name, folder_path

        def process_data():
            """Function that calls multiple inferred functions."""
            config = get_config("config_asset", "dev")
            data = get_data("data_bucket", "dev")
            return config, data

        async with ResourceOverwritesContext(get_overwrites):
            config_result, data_result = process_data()
            assert config_result == ("prod_config", "prod")
            assert data_result == ("prod_data", "prod")

    @pytest.mark.anyio
    async def test_context_cleanup_after_exception(self):
        """Test that context is properly cleaned up even after an exception."""

        async def get_overwrites():
            return {
                "asset.test": ResourceOverwrite(
                    overwrite_name="overwritten", overwrite_folder_path="overwritten"
                )
            }

        @resource_override(resource_type="asset")
        def get_asset(name, folder_path):
            return name, folder_path

        try:
            async with ResourceOverwritesContext(get_overwrites):
                # Verify overwrites are active
                result = get_asset("test", "original")
                assert result == ("overwritten", "overwritten")

                # Raise an exception
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify context was cleaned up despite the exception
        result_after = get_asset("test", "original")
        assert result_after == ("test", "original")
