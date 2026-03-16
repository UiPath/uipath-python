from os import environ as env
from typing import Any, Optional
from urllib.parse import quote

from uipath.platform.common.constants import (
    ENV_FOLDER_KEY,
    ENV_FOLDER_PATH,
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
    HEADER_FOLDER_PATH_ENCODED,
)

# All printable ASCII chars (0x20–0x7E) — passed to quote() so only
# non-ASCII bytes get percent-encoded while preserving spaces, slashes, etc.
_ASCII_PRINTABLE = "".join(chr(c) for c in range(0x20, 0x7F))


def _folder_path_header(folder_path: str) -> dict[str, str]:
    """Return the appropriate folder path header.

    Uses the encoded header variant with percent-encoding when the path
    contains non-ASCII characters, since HTTP headers require ASCII values.
    """
    try:
        folder_path.encode("ascii")
        return {HEADER_FOLDER_PATH: folder_path}
    except UnicodeEncodeError:
        return {HEADER_FOLDER_PATH_ENCODED: quote(folder_path, safe=_ASCII_PRINTABLE)}


def header_folder(
    folder_key: Optional[str], folder_path: Optional[str]
) -> dict[str, str]:
    if folder_key is not None and folder_path is not None:
        raise ValueError("Only one of folder_key or folder_path can be provided")

    headers = {}
    if folder_key is not None and folder_key != "":
        headers[HEADER_FOLDER_KEY] = folder_key
    if folder_path is not None and folder_path != "":
        headers.update(_folder_path_header(folder_path))

    return headers


class FolderContext:
    """Manages the folder context for UiPath automation resources.

    The FolderContext class handles information about the current folder in which
    automation resources (like processes, assets, etc.) are being accessed or modified.
    This is essential for organizing and managing resources in the UiPath Automation Cloud
    folder structure.
    """

    def __init__(self, **kwargs: Any) -> None:
        try:
            self._folder_key: str | None = env[ENV_FOLDER_KEY]
        except KeyError:
            self._folder_key = None

        try:
            self._folder_path: str | None = env[ENV_FOLDER_PATH]
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
                header (either folder key or folder path). If no folder header is
                set as environment variable, the function returns an empty dictionary.
        """
        if self._folder_key is not None:
            return {HEADER_FOLDER_KEY: self._folder_key}
        elif self._folder_path is not None:
            return _folder_path_header(self._folder_path)
        else:
            return {}
