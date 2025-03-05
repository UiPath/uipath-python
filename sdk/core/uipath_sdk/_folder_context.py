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
        if self._folder_key is not None:
            return {HEADER_FOLDER_KEY: self._folder_key}
        elif self._folder_path is not None:
            return {HEADER_FOLDER_PATH: self._folder_path}
        else:
            raise ValueError(
                f"Folder key or path is not set ({ENV_FOLDER_KEY} or {ENV_FOLDER_PATH})"
            )
