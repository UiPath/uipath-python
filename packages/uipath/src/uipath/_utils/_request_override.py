from base64 import b64encode
from typing import Optional

from .constants import HEADER_FOLDER_KEY, HEADER_FOLDER_PATH, HEADER_FOLDER_PATH_ENCODED


def folder_path_header(folder_path: str) -> dict[str, str]:
    """Return the appropriate folder path header.

    Uses the encoded header variant when the path contains non-ASCII
    characters, since HTTP headers require ASCII values. The Orchestrator
    expects Base64(UTF-16LE) in the encoded header.
    """
    try:
        folder_path.encode("ascii")
        return {HEADER_FOLDER_PATH: folder_path}
    except UnicodeEncodeError:
        encoded = b64encode(folder_path.encode("utf-16-le")).decode("ascii")
        return {HEADER_FOLDER_PATH_ENCODED: encoded}


def header_folder(
    folder_key: Optional[str], folder_path: Optional[str]
) -> dict[str, str]:
    if folder_key is not None and folder_path is not None:
        raise ValueError("Only one of folder_key or folder_path can be provided")

    headers = {}
    if folder_key is not None and folder_key != "":
        headers[HEADER_FOLDER_KEY] = folder_key
    if folder_path is not None and folder_path != "":
        headers.update(folder_path_header(folder_path))

    return headers
