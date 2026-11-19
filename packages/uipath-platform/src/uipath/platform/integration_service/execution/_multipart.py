"""Multipart form of a connector call that uploads files."""

import json
from typing import Any, List, Optional, Sequence

from ..execution_types import (
    ExecuteFile,
)
from ._request import OCTET_STREAM, MultipartPart

_DEFAULT_BODY_PART_NAME = "body"
_DEFAULT_FILE_NAME = "file"


def validate_files(files: Sequence[ExecuteFile], caller: str) -> None:
    """Check the files of a call before anything is sent."""
    for file in files:
        if not isinstance(file, ExecuteFile):
            raise ValueError(f"every file passed to {caller} must be an ExecuteFile")
        if not file.name:
            raise ValueError(f"every file passed to {caller} needs a name")


def _file_part(file: ExecuteFile, file_name: str) -> MultipartPart:
    return (file.name, (file_name, file.content, file.content_type or OCTET_STREAM))


def build_multipart(
    files: Sequence[ExecuteFile], body: Any, body_part_name: Optional[str] = None
) -> List[MultipartPart]:
    """Build the multipart form of a connector call that uploads files.

    Each file is one part, and a non-empty body travels as a JSON part of its
    own, ahead of the files.
    """
    parts: List[MultipartPart] = []

    is_empty = body is None or (isinstance(body, (dict, list)) and len(body) == 0)
    if not is_empty:
        text = body if isinstance(body, str) else json.dumps(body)
        parts.append((body_part_name or _DEFAULT_BODY_PART_NAME, (None, text, None)))

    for file in files:
        parts.append(_file_part(file, file.file_name or _DEFAULT_FILE_NAME))
    return parts
