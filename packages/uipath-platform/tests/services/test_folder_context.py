"""Tests for folder path header encoding.

Non-ASCII characters in folder paths must be Base64-encoded (UTF-16LE)
and sent via the X-UIPATH-FolderPath-Encoded header, since HTTP headers
require ASCII values. The Orchestrator decodes this with
Convert.FromBase64String + Encoding.Unicode (UTF-16LE).
"""

from base64 import b64decode

import pytest

from uipath.platform.common._folder_context import (
    FolderContext,
    folder_path_header,
    header_folder,
)
from uipath.platform.common.constants import (
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
    HEADER_FOLDER_PATH_ENCODED,
)

# --- folder_path_header() ---


class TestFolderPathHeader:
    def test_ascii_path_uses_plain_header(self) -> None:
        headers = folder_path_header("MyFolder/SubFolder")
        assert headers == {HEADER_FOLDER_PATH: "MyFolder/SubFolder"}

    def test_non_ascii_path_uses_encoded_header(self) -> None:
        path = "VA\xa0Certificate"
        headers = folder_path_header(path)
        assert HEADER_FOLDER_PATH not in headers
        assert HEADER_FOLDER_PATH_ENCODED in headers

    def test_encoded_value_is_base64_utf16le(self) -> None:
        path = "Debug_Poétry Writer"
        headers = folder_path_header(path)
        value = headers[HEADER_FOLDER_PATH_ENCODED]
        decoded = b64decode(value).decode("utf-16-le")
        assert decoded == path

    def test_encoded_value_is_ascii_safe(self) -> None:
        headers = folder_path_header("VA\xa0Certificate/Poétry")
        headers[HEADER_FOLDER_PATH_ENCODED].encode("ascii")

    def test_round_trip_with_non_breaking_space(self) -> None:
        path = "VA\xa0Certificate of Eligibility Agent"
        headers = folder_path_header(path)
        decoded = b64decode(headers[HEADER_FOLDER_PATH_ENCODED]).decode("utf-16-le")
        assert decoded == path


# --- header_folder() ---


class TestHeaderFolder:
    def test_ascii_folder_path(self) -> None:
        headers = header_folder(None, "MyFolder/SubFolder")
        assert headers == {HEADER_FOLDER_PATH: "MyFolder/SubFolder"}

    def test_non_ascii_folder_path_uses_encoded_header(self) -> None:
        headers = header_folder(None, "VA\xa0Certificate")
        assert HEADER_FOLDER_PATH not in headers
        assert HEADER_FOLDER_PATH_ENCODED in headers

    def test_folder_key_returned_as_is(self) -> None:
        headers = header_folder("some-uuid-key", None)
        assert headers == {HEADER_FOLDER_KEY: "some-uuid-key"}

    def test_none_path_and_key_returns_empty(self) -> None:
        assert header_folder(None, None) == {}

    def test_both_key_and_path_raises(self) -> None:
        with pytest.raises(ValueError):
            header_folder("key", "path")


# --- FolderContext.folder_headers ---


class TestFolderContextHeaders:
    def test_non_ascii_folder_path_uses_encoded_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = "VA\xa0Certificate"
        monkeypatch.setenv("UIPATH_FOLDER_PATH", path)
        monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
        ctx = FolderContext()
        headers = ctx.folder_headers
        assert HEADER_FOLDER_PATH not in headers
        value = headers[HEADER_FOLDER_PATH_ENCODED]
        value.encode("ascii")
        assert b64decode(value).decode("utf-16-le") == path

    def test_ascii_folder_path_uses_plain_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "my-folder")
        monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
        ctx = FolderContext()
        assert ctx.folder_headers == {HEADER_FOLDER_PATH: "my-folder"}

    def test_folder_key_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "my-key")
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "my-path")
        ctx = FolderContext()
        assert ctx.folder_headers == {HEADER_FOLDER_KEY: "my-key"}

    def test_no_env_vars_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
        monkeypatch.delenv("UIPATH_FOLDER_PATH", raising=False)
        ctx = FolderContext()
        assert ctx.folder_headers == {}
