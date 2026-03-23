import logging
import os
from functools import cached_property
from pathlib import Path

logger = logging.getLogger(__name__)

from pydantic import BaseModel


class UiPathApiConfig(BaseModel):
    base_url: str
    secret: str


class ConfigurationManager:
    _instance = None
    studio_solution_id: str | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def bindings_file_path(self) -> Path:
        from uipath.platform.common.constants import UIPATH_BINDINGS_FILE

        return Path(UIPATH_BINDINGS_FILE)

    @property
    def config_file_path(self) -> Path:
        from uipath.platform.common.constants import (
            ENV_UIPATH_CONFIG_PATH,
            UIPATH_CONFIG_FILE,
        )

        return Path(os.environ.get(ENV_UIPATH_CONFIG_PATH, UIPATH_CONFIG_FILE))

    @property
    def config_file_name(self) -> str:
        from uipath.platform.common.constants import UIPATH_CONFIG_FILE

        return UIPATH_CONFIG_FILE

    @property
    def project_id(self) -> str | None:
        from uipath.platform.common.constants import ENV_UIPATH_PROJECT_ID

        return os.getenv(ENV_UIPATH_PROJECT_ID, None)

    @property
    def project_key(self) -> str | None:
        from uipath.platform.common.constants import ENV_PROJECT_KEY

        return os.getenv(ENV_PROJECT_KEY, None)

    @property
    def tenant_name(self) -> str | None:
        from uipath.platform.common.constants import ENV_TENANT_NAME

        return os.getenv(ENV_TENANT_NAME, None)

    @property
    def tenant_id(self) -> str | None:
        from uipath.platform.common.constants import ENV_TENANT_ID

        return os.getenv(ENV_TENANT_ID, None)

    @property
    def organization_id(self) -> str | None:
        from uipath.platform.common.constants import ENV_ORGANIZATION_ID

        return os.getenv(ENV_ORGANIZATION_ID, None)

    @property
    def base_url(self) -> str | None:
        from uipath.platform.common.constants import ENV_BASE_URL

        return os.getenv(ENV_BASE_URL, None)

    @property
    def folder_key(self) -> str | None:
        from uipath.platform.common.constants import ENV_FOLDER_KEY

        return os.getenv(ENV_FOLDER_KEY, None)

    @property
    def folder_path(self) -> str | None:
        from uipath.platform.common.constants import ENV_FOLDER_PATH

        return os.getenv(ENV_FOLDER_PATH, None)

    @property
    def process_uuid(self) -> str | None:
        from uipath.platform.common.constants import ENV_UIPATH_PROCESS_UUID

        return os.getenv(ENV_UIPATH_PROCESS_UUID, None)

    @property
    def trace_id(self) -> str | None:
        from uipath.platform.common.constants import ENV_UIPATH_TRACE_ID

        return os.getenv(ENV_UIPATH_TRACE_ID, None)

    @property
    def process_version(self) -> str | None:
        from uipath.platform.common.constants import ENV_UIPATH_PROCESS_VERSION

        return os.getenv(ENV_UIPATH_PROCESS_VERSION, None)

    @property
    def is_studio_project(self) -> bool:
        return self.project_id is not None

    @property
    def job_key(self) -> str | None:
        from uipath.platform.common.constants import ENV_JOB_KEY

        return os.getenv(ENV_JOB_KEY, None)

    @property
    def has_legacy_eval_folder(self) -> bool:
        from uipath.platform.common.constants import LEGACY_EVAL_FOLDER

        eval_path = Path(os.getcwd()) / LEGACY_EVAL_FOLDER
        return eval_path.exists() and eval_path.is_dir()

    @property
    def has_eval_folder(self) -> bool:
        from uipath.platform.common.constants import EVALS_FOLDER

        coded_eval_path = Path(os.getcwd()) / EVALS_FOLDER
        return coded_eval_path.exists() and coded_eval_path.is_dir()

    @property
    def entry_points_file_path(self) -> Path:
        from uipath.platform.common.constants import ENTRY_POINTS_FILE

        return Path(ENTRY_POINTS_FILE)

    @property
    def uiproj_file_path(self) -> Path:
        from uipath.platform.common.constants import UIPROJ_FILE

        return Path(UIPROJ_FILE)

    @property
    def studio_metadata_file_path(self) -> Path:
        from uipath.platform.common.constants import STUDIO_METADATA_FILE

        return Path(".uipath", STUDIO_METADATA_FILE)

    @property
    def licensing_context(self) -> str | None:
        return self._read_internal_argument("licensingContext")

    @property
    def is_rooted_to_debug_job(self) -> bool:
        """Whether this job, which may be a deployed process, is rooted to a debug session (e.g. Maestro solution debug)."""
        return self._read_internal_argument("isDebug") is True

    @property
    def is_tracing_enabled(self) -> bool:
        from uipath.platform.common.constants import ENV_TRACING_ENABLED

        return os.getenv(ENV_TRACING_ENABLED, "true").lower() == "true"

    def log_config(self) -> None:
        """Log the current configuration values at INFO level."""
        logger.info(
            "UiPathConfig: project_id=%s, folder_key=%s, folder_path=%s, "
            "base_url=%s, tenant_id=%s, organization_id=%s, job_key=%s, "
            "process_uuid=%s, process_version=%s",
            self.project_id,
            self.folder_key,
            self.folder_path,
            self.base_url,
            self.tenant_id,
            self.organization_id,
            self.job_key,
            self.process_uuid,
            self.process_version,
        )

    def _read_internal_argument(self, key: str) -> str | None:
        internal_args = self._internal_arguments
        return internal_args.get(key) if internal_args else None

    @cached_property
    def _internal_arguments(self) -> dict[str, str] | None:
        import json

        try:
            with open(self.config_file_path, "r") as f:
                data = json.load(f)
                return data.get("runtime", {}).get("internalArguments")
        except (FileNotFoundError, json.JSONDecodeError):
            return None


UiPathConfig = ConfigurationManager()
