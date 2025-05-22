import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from uipath._utils._read_overwrites import OverwritesManager

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def mock_overwrites_file(tmp_path: Path) -> Path:
    overwrites_data = {
        "runtime": {
            "outputFile": "output.json",
            "internalArguments": {
                "resourceOverwrites": {
                    "asset.MyAsset": {
                        "name": "NewAssetName",
                        "folderPath": "Root/Dev/Assets",
                    },
                    "process.MyProcess": {
                        "name": "NewProcessName",
                        "folderPath": "Root/Dev/Processes",
                    },
                    "library.MyLibrary": {
                        "name": "NewLibraryName",
                        "folderPath": "Root/Dev/Libraries",
                    },
                }
            },
        }
    }

    file_path = tmp_path / "uipath.json"
    with open(file_path, "w") as f:
        json.dump(overwrites_data, f)

    return file_path


def test_get_overwrite_asset(
    mock_overwrites_file: Path, mocker: "MockerFixture"
) -> None:
    """Test getting an asset overwrite value.

    Args:
        mock_overwrites_file: Path to the mock overwrites file.
        mocker: Pytest mocker fixture.
    """
    print(f"Mock overwrites file: {mock_overwrites_file}")
    manager = OverwritesManager(mock_overwrites_file)
    result = manager.get_overwrite("asset", "MyAsset")
    assert result == ("NewAssetName", "Root/Dev/Assets")


def test_get_overwrite_process(mock_overwrites_file: Path) -> None:
    """Test getting a process overwrite value.

    Args:
        mock_overwrites_file: Path to the mock overwrites file.
        mocker: Pytest mocker fixture.
    """
    manager = OverwritesManager(mock_overwrites_file)
    result = manager.get_overwrite("process", "MyProcess")
    assert result == ("NewProcessName", "Root/Dev/Processes")


def test_get_overwrite_library(mock_overwrites_file: Path) -> None:
    """Test getting a library overwrite value.

    Args:
        mock_overwrites_file: Path to the mock overwrites file.
        mocker: Pytest mocker fixture.
    """
    manager = OverwritesManager(mock_overwrites_file)
    result = manager.get_overwrite("library", "MyLibrary")
    assert result == ("NewLibraryName", "Root/Dev/Libraries")


def test_get_overwrite_not_found(mock_overwrites_file: Path) -> None:
    """Test getting an overwrite value that doesn't exist.

    Args:
        mock_overwrites_file: Path to the mock overwrites file.
        mocker: Pytest mocker fixture.
    """
    manager = OverwritesManager(mock_overwrites_file)
    result = manager.get_overwrite("process", "NonexistentProcess")
    assert result is None


def test_get_overwrite_empty_file(tmp_path: Path) -> None:
    """Test getting an overwrite value from an empty file.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Pytest temporary path fixture.
    """
    file_path = tmp_path / "uipath.json"
    with open(file_path, "w") as f:
        json.dump({}, f)

    manager = OverwritesManager(file_path)
    result = manager.get_overwrite("process", "MyProcess")
    assert result is None


def test_get_overwrite_missing_file(tmp_path: Path) -> None:
    """Test getting an overwrite value when file doesn't exist.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Pytest temporary path fixture.
    """
    file_path = tmp_path / "nonexistent.json"
    manager = OverwritesManager(file_path)
    result = manager.get_overwrite("process", "MyProcess")
    assert result is None
