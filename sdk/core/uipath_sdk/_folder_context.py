from os import environ as env
from typing import Any, Optional

from dotenv import load_dotenv

from ._utils.constants import (
    ENV_FOLDER_KEY,
    ENV_FOLDER_PATH,
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
)

load_dotenv()


class FolderContext:
    """Manages the folder context for UiPath automation resources.

    The FolderContext class handles information about the current folder in which
    automation resources (like processes, assets, etc.) are being accessed or modified.
    This is essential for organizing and managing resources in the UiPath Automation Cloud
    folder structure.
    """

    def __init__(self, **kwargs: Any) -> None:
        try:
            self._folder_key: Optional[str] = env[ENV_FOLDER_KEY]
        except KeyError:
            self._folder_key = None

        try:
            self._folder_path: Optional[str] = env[ENV_FOLDER_PATH]
        except KeyError:
            self._folder_path = None

        super().__init__(**kwargs)

    @property
    def folder_headers(self) -> dict[str, str]:
        """Get the HTTP headers for folder-based API requests.

        Returns headers containing either the folder key or folder path,
        which are used to specify the target folder for API operations.
        The folder context is essential for operations that need to be
        performed within a specific folder in UiPath Automation Cloud.

        Returns:
            dict[str, str]: A dictionary containing the appropriate folder
                header (either folder key or folder path).

        Raises:
            ValueError: If neither folder key nor folder path is set in
                the environment.
        """
        if self._folder_key is not None:
            return {HEADER_FOLDER_KEY: self._folder_key}
        elif self._folder_path is not None:
            return {HEADER_FOLDER_PATH: self._folder_path}
        else:
            raise ValueError(
                f"Folder key or path is not set ({ENV_FOLDER_KEY} or {ENV_FOLDER_PATH})"
            )
