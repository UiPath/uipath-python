from os import environ as env
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


class FolderContext:
    def __init__(self, **kwargs: Any) -> None:
        try:
            self._folder_key: Optional[str] = env["UIPATH_FOLDER_KEY"]
        except KeyError:
            self._folder_key = None

        try:
            self._folder_path: Optional[str] = env["UIPATH_FOLDER_PATH"]
        except KeyError:
            self._folder_path = None

        super().__init__(**kwargs)

    @property
    def folder_headers(self) -> dict[str, str]:
        if self._folder_key is not None:
            return {"x-uipath-folderkey": self._folder_key}
        elif self._folder_path is not None:
            return {"X-uipath-folderpath": self._folder_path}
        else:
            raise ValueError(
                "Folder key or path is not set (UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH)"
            )
