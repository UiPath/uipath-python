from unittest.mock import MagicMock, patch

import pytest

from uipath._utils._infer_bindings import infer_bindings


@pytest.fixture
def mock_read_resource_overwrites():
    with patch("uipath._utils._infer_bindings.read_resource_overwrites") as mock:
        yield mock


class TestBindingsInference:
    def test_infer_bindings_overwrites_name_and_folder_path(
        self, mock_read_resource_overwrites
    ):
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = ("new_name", "new_folder")
        mock_read_resource_overwrites.return_value = mock_cm

        @infer_bindings(resource_type="bucket")
        def dummy_func(name, folder_path):
            return name, folder_path

        result = dummy_func("old_name", "old_folder")
        assert result == ("new_name", "new_folder")
        mock_read_resource_overwrites.assert_called_once_with(
            "bucket", "old_name", "old_folder"
        )

    def test_infer_bindings_skips_when_no_name_and_folder_path(
        self, mock_read_resource_overwrites
    ):
        @infer_bindings(resource_type="bucket")
        def dummy_func(other_arg):
            return other_arg

        result = dummy_func("some_value")
        assert result == "some_value"
        mock_read_resource_overwrites.assert_not_called()

    def test_infer_bindings_only_name_present(self, mock_read_resource_overwrites):
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = ("new_name", None)
        mock_read_resource_overwrites.return_value = mock_cm

        @infer_bindings(resource_type="asset")
        def dummy_func(name, folder_path=None):
            return name, folder_path

        result = dummy_func("old_name")
        assert result == ("new_name", None)
        mock_read_resource_overwrites.assert_called_once_with("asset", "old_name", None)
