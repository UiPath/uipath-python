"""Pydantic models for uipath.json configuration file."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class BaseModelWithDefaultConfig(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        populate_by_name=True,
        extra="allow",
    )


class RuntimeOptions(BaseModelWithDefaultConfig):
    """Runtime behavior configuration."""

    is_conversational: bool = Field(
        default=False,
        alias="isConversational",
        description="Enable conversational mode for the runtime",
    )


class DesignOptions(BaseModelWithDefaultConfig):
    """Design-time configuration and preferences."""


class PackOptions(BaseModelWithDefaultConfig):
    """File inclusion and exclusion settings for packaging."""

    file_extensions_included: list[str] = Field(
        default_factory=list,
        alias="fileExtensionsIncluded",
        description="File extensions to include in the package",
    )
    files_included: list[str] = Field(
        default_factory=list,
        alias="filesIncluded",
        description="Specific files to include in the package",
    )
    files_excluded: list[str] = Field(
        default_factory=list,
        alias="filesExcluded",
        description="Specific files to exclude from the package",
    )
    directories_excluded: list[str] = Field(
        default_factory=list,
        alias="directoriesExcluded",
        description="Directories to exclude from the package",
    )
    include_uv_lock: bool = Field(
        default=True,
        alias="includeUvLock",
        description="Whether to include uv.lock file in the package",
    )


class UiPathJsonConfig(BaseModelWithDefaultConfig):
    """Configuration file for UiPath projects."""

    schema_: str = Field(
        default="https://cloud.uipath.com/draft/2024-12/uipath",
        alias="$schema",
        description="Reference to the JSON schema for editor support",
    )
    runtime_options: RuntimeOptions = Field(
        default_factory=RuntimeOptions,
        alias="runtimeOptions",
        description="Runtime behavior configuration",
    )
    design_options: DesignOptions | None = Field(
        default=None,
        alias="designOptions",
        description="Design-time configuration and preferences",
    )
    pack_options: PackOptions = Field(
        default_factory=PackOptions,
        alias="packOptions",
        description="File inclusion and exclusion settings for packaging",
    )
    functions: dict[str, str] = Field(
        default_factory=dict,
        description="Entrypoint definitions for pure Python scripts. "
        "Each key is an entrypoint name, and each value is a path in format 'file_path:function_name'",
    )

    def to_json_string(self, indent: int = 2) -> str:
        """Export to JSON string with proper formatting."""
        return self.model_dump_json(
            by_alias=True,
            exclude_none=True,
            indent=indent,
        )

    @classmethod
    def create_default(cls) -> "UiPathJsonConfig":
        """Create a default configuration instance."""
        return cls(
            runtime_options=RuntimeOptions(is_conversational=False),
            pack_options=PackOptions(
                file_extensions_included=[],
                files_included=[],
                files_excluded=[],
                directories_excluded=[],
                include_uv_lock=True,
            ),
            functions={},
        )

    @classmethod
    def load_from_file(cls, file_path: str = "uipath.json") -> "UiPathJsonConfig":
        """Load configuration from a JSON file."""
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return cls.create_default()

        with open(path) as f:
            data = json.load(f)

        return cls.model_validate(data)

    def save_to_file(self, file_path: Path) -> None:
        """Save configuration to a JSON file."""
        with open(file_path, "w") as f:
            f.write(self.to_json_string())
