import os
from functools import cached_property
from typing import Optional

from pathlib import Path

from pydantic import BaseModel

class Config(BaseModel):
    base_url: str
    secret: str

class ConfigurationManager:
    """Singleton configuration manager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @cached_property
    def bindings_file_path(self) -> Path:
        from uipath._utils.constants import UIPATH_BINDINGS_FILE
        return Path(UIPATH_BINDINGS_FILE)

    @cached_property
    def config_file_path(self) -> Path:
        from uipath._utils.constants import ENV_JOB_KEY, UIPATH_CONFIG_FILE

        if not os.getenv(ENV_JOB_KEY, None):
            return Path(UIPATH_CONFIG_FILE)
        return Path("__uipath") / UIPATH_CONFIG_FILE

    @cached_property
    def project_id(self) -> Optional[str]:
        from uipath._utils.constants import ENV_UIPATH_PROJECT_ID

        return os.getenv(ENV_UIPATH_PROJECT_ID, None)

    @cached_property
    def is_studio_project(self) -> bool:
        from uipath._utils.constants import ENV_UIPATH_PROJECT_ID

        return os.getenv(ENV_UIPATH_PROJECT_ID, None) is not None
