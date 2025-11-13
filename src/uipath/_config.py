import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class Config(BaseModel):
    base_url: str
    secret: str


class ConfigurationManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def bindings_file_path(self) -> Path:
        from uipath._utils.constants import UIPATH_BINDINGS_FILE

        return Path(UIPATH_BINDINGS_FILE)

    @property
    def config_file_name(self) -> str:
        from uipath._utils.constants import UIPATH_CONFIG_FILE

        return UIPATH_CONFIG_FILE

    @property
    def project_id(self) -> Optional[str]:
        from uipath._utils.constants import ENV_UIPATH_PROJECT_ID

        return os.getenv(ENV_UIPATH_PROJECT_ID, None)

    @property
    def folder_key(self) -> Optional[str]:
        from uipath._utils.constants import ENV_FOLDER_KEY

        return os.getenv(ENV_FOLDER_KEY, None)

    @property
    def is_studio_project(self) -> bool:
        return self.project_id is not None

    @property
    def job_key(self) -> Optional[str]:
        from uipath._utils.constants import ENV_JOB_KEY

        return os.getenv(ENV_JOB_KEY, None)

    @property
    def has_legacy_eval_folder(self) -> bool:
        from uipath._utils.constants import LEGACY_EVAL_FOLDER

        eval_path = Path(os.getcwd()) / LEGACY_EVAL_FOLDER
        return eval_path.exists() and eval_path.is_dir()

    @property
    def has_eval_folder(self) -> bool:
        from uipath._utils.constants import EVALS_FOLDER

        coded_eval_path = Path(os.getcwd()) / EVALS_FOLDER
        return coded_eval_path.exists() and coded_eval_path.is_dir()

    @property
    def entry_points_file_path(self) -> Path:
        from uipath._utils.constants import ENTRY_POINTS_FILE

        return Path(ENTRY_POINTS_FILE)


UiPathConfig = ConfigurationManager()
