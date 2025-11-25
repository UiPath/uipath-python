

from .constants import HEADER_FOLDER_KEY, HEADER_FOLDER_PATH

def header_folder(
    folder_key: str | None, folder_path: str | None
) -> dict[str, str]:
    if folder_key is not None and folder_path is not None:
        raise ValueError("Only one of folder_key or folder_path can be provided")

    headers = {}
    if folder_key is not None and folder_key != "":
        headers[HEADER_FOLDER_KEY] = folder_key
    if folder_path is not None and folder_path != "":
        headers[HEADER_FOLDER_PATH] = folder_path

    return headers
