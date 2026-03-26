from typing import Any

from pydantic import TypeAdapter

from uipath._cli.models.uipath_json_schema import UiPathJsonConfig


def test_uipath_config_validation():
    # Arrange
    config: dict[str, Any] = {
        "$schema": "https://cloud.uipath.com/draft/2024-12/uipath",
        "runtimeOptions": {"isConversational": False},
        "designOptions": {"theme": "dark", "autoSave": True},
        "packOptions": {
            "fileExtensionsIncluded": [".py", ".json", ".yaml", ".md"],
            "filesIncluded": ["pyproject.toml", "README.md"],
            "filesExcluded": ["secret.env", ".env.local"],
            "directoriesExcluded": ["tests", "venv"],
            "includeUvLock": True,
        },
        "functions": {
            "main": "src/main.py:main",
            "process": "src/graph.py:run",
            "generateReport": "src/reporting.py:generate_report",
            "cleanup": "scripts/cleanup.py:cleanup_resources",
        },
    }

    # Act and Assert
    TypeAdapter(UiPathJsonConfig).validate_python(config)


def test_uipath_config_minimal():
    """Test minimal valid configuration."""
    # Arrange
    config = {
        "$schema": "https://cloud.uipath.com/draft/2024-12/uipath",
        "runtimeOptions": {"isConversational": False},
        "packOptions": {
            "fileExtensionsIncluded": [],
            "filesIncluded": [],
            "filesExcluded": [],
            "directoriesExcluded": [],
            "includeUvLock": True,
        },
        "functions": {},
    }

    # Act and Assert
    validated = TypeAdapter(UiPathJsonConfig).validate_python(config)
    assert validated.runtime_options.is_conversational is False
    assert validated.pack_options.include_uv_lock is True
    assert validated.functions == {}


def test_uipath_config_defaults():
    """Test that default values work correctly."""
    # Arrange
    config: dict[str, Any] = {}

    # Act
    validated = TypeAdapter(UiPathJsonConfig).validate_python(config)

    # Assert
    assert validated.schema_ == "https://cloud.uipath.com/draft/2024-12/uipath"
    assert validated.runtime_options.is_conversational is False
    assert validated.pack_options.include_uv_lock is True
    assert validated.functions == {}


def test_uipath_config_functions_validation():
    """Test functions field with various entrypoint formats."""
    # Arrange
    config = {
        "functions": {
            "main": "src/main.py:main",
            "process": "processor.py:process_data",
            "echo": "utils/echo.py:echo_function",
        }
    }

    # Act
    validated = TypeAdapter(UiPathJsonConfig).validate_python(config)

    # Assert
    assert len(validated.functions) == 3
    assert validated.functions["main"] == "src/main.py:main"
    assert validated.functions["process"] == "processor.py:process_data"
    assert validated.functions["echo"] == "utils/echo.py:echo_function"


def test_uipath_config_runtime_options():
    """Test runtime options variations."""
    # Arrange - conversational mode enabled
    config = {"runtimeOptions": {"isConversational": True}}

    # Act
    validated = TypeAdapter(UiPathJsonConfig).validate_python(config)

    # Assert
    assert validated.runtime_options.is_conversational is True


def test_uipath_config_pack_options():
    """Test pack options with various configurations."""
    # Arrange
    config = {
        "packOptions": {
            "fileExtensionsIncluded": [".py", ".md"],
            "filesIncluded": ["README.md", "LICENSE"],
            "filesExcluded": [".env", "secrets.json"],
            "directoriesExcluded": ["__pycache__", ".git"],
            "includeUvLock": False,
        }
    }

    # Act
    validated = TypeAdapter(UiPathJsonConfig).validate_python(config)

    # Assert
    assert validated.pack_options.file_extensions_included == [".py", ".md"]
    assert validated.pack_options.files_included == ["README.md", "LICENSE"]
    assert validated.pack_options.files_excluded == [".env", "secrets.json"]
    assert validated.pack_options.directories_excluded == ["__pycache__", ".git"]
    assert validated.pack_options.include_uv_lock is False


def test_uipath_config_to_json_string():
    """Test JSON serialization."""
    # Arrange
    config = UiPathJsonConfig.create_default()
    config.functions["test"] = "test.py:test_func"

    # Act
    json_output = config.to_json_string()

    # Assert
    assert '"$schema"' in json_output
    assert '"isConversational": false' in json_output
    assert '"includeUvLock": true' in json_output
    assert '"test": "test.py:test_func"' in json_output
