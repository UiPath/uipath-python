"""Unit tests for CLI validators.

Tests validation functions for folder paths, UUIDs, resource names,
and mutual exclusion constraints.
"""

import click
import pytest

from uipath._cli._utils._validators import (
    validate_folder_path,
    validate_mutually_exclusive,
    validate_resource_name,
    validate_uuid,
)


class TestValidateFolderPath:
    """Tests for validate_folder_path function."""

    def test_validate_folder_path_valid_simple(self):
        """Test validation of a simple valid folder path."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        result = validate_folder_path(ctx, param, "Shared")

        assert result == "Shared"

    def test_validate_folder_path_valid_nested(self):
        """Test validation of nested folder path."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        result = validate_folder_path(ctx, param, "Shared/Production/MyFolder")

        assert result == "Shared/Production/MyFolder"

    def test_validate_folder_path_none(self):
        """Test validation with None value."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        result = validate_folder_path(ctx, param, None)

        assert result is None

    def test_validate_folder_path_empty_string(self):
        """Test validation with empty string (should be allowed)."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        result = validate_folder_path(ctx, param, "")

        assert result == ""

    def test_validate_folder_path_invalid_leading_slash(self):
        """Test validation fails with leading slash."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_folder_path(ctx, param, "/Shared")

        assert "should not start or end with '/'" in str(exc_info.value)

    def test_validate_folder_path_invalid_trailing_slash(self):
        """Test validation fails with trailing slash."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_folder_path(ctx, param, "Shared/")

        assert "should not start or end with '/'" in str(exc_info.value)

    def test_validate_folder_path_invalid_both_slashes(self):
        """Test validation fails with both leading and trailing slashes."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--folder-path"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_folder_path(ctx, param, "/Shared/Production/")

        assert "should not start or end with '/'" in str(exc_info.value)


class TestValidateUuid:
    """Tests for validate_uuid function."""

    def test_validate_uuid_valid_lowercase(self):
        """Test validation of valid UUID in lowercase."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        result = validate_uuid(ctx, param, "a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6")

        assert result == "a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6"

    def test_validate_uuid_valid_uppercase(self):
        """Test validation of valid UUID in uppercase."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        result = validate_uuid(ctx, param, "A1B2C3D4-E5F6-47A8-B9C0-D1E2F3A4B5C6")

        assert result == "A1B2C3D4-E5F6-47A8-B9C0-D1E2F3A4B5C6"

    def test_validate_uuid_valid_mixed_case(self):
        """Test validation of valid UUID in mixed case."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        result = validate_uuid(ctx, param, "A1b2C3d4-E5f6-47a8-B9c0-D1e2F3a4B5c6")

        assert result == "A1b2C3d4-E5f6-47a8-B9c0-D1e2F3a4B5c6"

    def test_validate_uuid_none(self):
        """Test validation with None value."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        result = validate_uuid(ctx, param, None)

        assert result is None

    def test_validate_uuid_invalid_format_no_hyphens(self):
        """Test validation fails with UUID without hyphens."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_uuid(ctx, param, "a1b2c3d4e5f647a8b9c0d1e2f3a4b5c6")

        assert "not a valid UUID" in str(exc_info.value)
        assert "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" in str(exc_info.value)

    def test_validate_uuid_invalid_format_wrong_positions(self):
        """Test validation fails with hyphens in wrong positions."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_uuid(ctx, param, "a1b2-c3d4e5f6-47a8-b9c0-d1e2f3a4b5c6")

        assert "not a valid UUID" in str(exc_info.value)

    def test_validate_uuid_invalid_too_short(self):
        """Test validation fails with too short UUID."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_uuid(ctx, param, "a1b2c3d4-e5f6-47a8-b9c0")

        assert "not a valid UUID" in str(exc_info.value)

    def test_validate_uuid_invalid_too_long(self):
        """Test validation fails with too long UUID."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_uuid(ctx, param, "a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6-extra")

        assert "not a valid UUID" in str(exc_info.value)

    def test_validate_uuid_invalid_non_hex_characters(self):
        """Test validation fails with non-hex characters."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_uuid(ctx, param, "g1h2i3j4-k5l6-m7n8-o9p0-q1r2s3t4u5v6")

        assert "not a valid UUID" in str(exc_info.value)

    def test_validate_uuid_invalid_empty_string(self):
        """Test validation fails with empty string."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--key"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_uuid(ctx, param, "")

        assert "not a valid UUID" in str(exc_info.value)


class TestValidateResourceName:
    """Tests for validate_resource_name function."""

    def test_validate_resource_name_valid_simple(self):
        """Test validation of simple valid resource name."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        result = validate_resource_name(ctx, param, "my-bucket")

        assert result == "my-bucket"

    def test_validate_resource_name_valid_with_spaces(self):
        """Test validation of resource name with spaces."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        result = validate_resource_name(ctx, param, "My Bucket Name")

        assert result == "My Bucket Name"

    def test_validate_resource_name_valid_with_underscores(self):
        """Test validation of resource name with underscores."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        result = validate_resource_name(ctx, param, "my_bucket_name")

        assert result == "my_bucket_name"

    def test_validate_resource_name_valid_with_numbers(self):
        """Test validation of resource name with numbers."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        result = validate_resource_name(ctx, param, "bucket123")

        assert result == "bucket123"

    def test_validate_resource_name_none(self):
        """Test validation with None value."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        result = validate_resource_name(ctx, param, None)

        assert result is None

    def test_validate_resource_name_invalid_empty(self):
        """Test validation fails with empty string."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "")

        assert "cannot be empty" in str(exc_info.value)

    def test_validate_resource_name_invalid_whitespace_only(self):
        """Test validation fails with whitespace only."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "   ")

        assert "cannot be empty" in str(exc_info.value)

    def test_validate_resource_name_invalid_less_than(self):
        """Test validation fails with < character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "bucket<name")

        assert "invalid character" in str(exc_info.value)
        assert "<" in str(exc_info.value)

    def test_validate_resource_name_invalid_greater_than(self):
        """Test validation fails with > character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "bucket>name")

        assert "invalid character" in str(exc_info.value)
        assert ">" in str(exc_info.value)

    def test_validate_resource_name_invalid_colon(self):
        """Test validation fails with : character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "bucket:name")

        assert "invalid character" in str(exc_info.value)
        assert ":" in str(exc_info.value)

    def test_validate_resource_name_invalid_quote(self):
        """Test validation fails with \" character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, 'bucket"name')

        assert "invalid character" in str(exc_info.value)
        assert '"' in str(exc_info.value)

    def test_validate_resource_name_invalid_pipe(self):
        """Test validation fails with | character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "bucket|name")

        assert "invalid character" in str(exc_info.value)
        assert "|" in str(exc_info.value)

    def test_validate_resource_name_invalid_question_mark(self):
        """Test validation fails with ? character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "bucket?name")

        assert "invalid character" in str(exc_info.value)
        assert "?" in str(exc_info.value)

    def test_validate_resource_name_invalid_asterisk(self):
        """Test validation fails with * character."""
        ctx = click.Context(click.Command("test"))
        param = click.Option(["--name"])

        with pytest.raises(click.BadParameter) as exc_info:
            validate_resource_name(ctx, param, "bucket*name")

        assert "invalid character" in str(exc_info.value)
        assert "*" in str(exc_info.value)


class TestValidateMutuallyExclusive:
    """Tests for validate_mutually_exclusive function."""

    def test_validate_mutually_exclusive_both_none(self):
        """Test validation passes when both parameters are None."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": None}
        param = click.Option(["--param"])

        result = validate_mutually_exclusive(ctx, param, None, "other_param")

        assert result is None

    def test_validate_mutually_exclusive_first_set(self):
        """Test validation passes when only first parameter is set."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": None}
        param = click.Option(["--param"])
        param.name = "param"

        result = validate_mutually_exclusive(ctx, param, "value1", "other_param")

        assert result == "value1"

    def test_validate_mutually_exclusive_second_set(self):
        """Test validation passes when only second parameter is set."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": "value2"}
        param = click.Option(["--param"])
        param.name = "param"

        result = validate_mutually_exclusive(ctx, param, None, "other_param")

        assert result is None

    def test_validate_mutually_exclusive_both_set_raises_error(self):
        """Test validation fails when both parameters are set."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": "value2"}
        param = click.Option(["--param"])
        param.name = "param"

        with pytest.raises(click.UsageError) as exc_info:
            validate_mutually_exclusive(ctx, param, "value1", "other_param")

        assert "mutually exclusive" in str(exc_info.value)
        assert "param" in str(exc_info.value)
        assert "other_param" in str(exc_info.value)
        assert "Provide only one" in str(exc_info.value)

    def test_validate_mutually_exclusive_with_empty_strings(self):
        """Test validation with empty strings (treated as set)."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": ""}
        param = click.Option(["--param"])
        param.name = "param"

        with pytest.raises(click.UsageError) as exc_info:
            validate_mutually_exclusive(ctx, param, "", "other_param")

        assert "mutually exclusive" in str(exc_info.value)

    def test_validate_mutually_exclusive_with_zero(self):
        """Test validation with zero value (treated as set)."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": 0}
        param = click.Option(["--param"])
        param.name = "param"

        with pytest.raises(click.UsageError) as exc_info:
            validate_mutually_exclusive(ctx, param, 0, "other_param")

        assert "mutually exclusive" in str(exc_info.value)

    def test_validate_mutually_exclusive_with_false(self):
        """Test validation with False value (treated as set)."""
        ctx = click.Context(click.Command("test"))
        ctx.params = {"other_param": False}
        param = click.Option(["--param"])
        param.name = "param"

        with pytest.raises(click.UsageError) as exc_info:
            validate_mutually_exclusive(ctx, param, False, "other_param")

        assert "mutually exclusive" in str(exc_info.value)
