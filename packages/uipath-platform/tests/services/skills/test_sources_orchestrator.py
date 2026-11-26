"""Tests for ``OrchestratorBundleSource``: lookup, versions, errors and archive safety."""

import io
import logging
import struct
import zipfile
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform.common import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.constants import (
    ENV_FOLDER_KEY,
    ENV_FOLDER_PATH,
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
)
from uipath.platform.skills import SkillBundleRef, VersionMode, _sources
from uipath.platform.skills._constants import MAX_FILE_BYTES
from uipath.platform.skills._sources import BundleSourceError, OrchestratorBundleSource

API = "https://test.uipath.com/org/tenant/orchestrator_/api"
KEY = "6f1c2c1e-0000-4000-8000-000000000001"
DIGEST = "sha256:" + "ab" * 32
FOLDER = "Shared/Skills"

FILES = {
    "bundle.json": b'{"version": 3}',
    "invoice-triage/SKILL.md": b"---\nname: invoice-triage\ndescription: Triage invoices\n---\nSteps",
    "invoice-triage/reference/vendors.md": b"Globex",
    "vendor-lookup/SKILL.md": b"---\ndescription: Find vendors\n---\n",
}


def _zip(
    files: dict[str, bytes],
    symlinks: dict[str, str] | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
    encrypted: tuple[str, ...] = (),
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
        for name, target in (symlinks or {}).items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777 << 16) | 0x20
            zf.writestr(info, target)
        for name in encrypted:
            zf.getinfo(name).flag_bits |= 0x1
    return buffer.getvalue()


def _damage_entry(archive: bytes, name: str) -> bytes:
    """Flip the first data bytes of ``name``, leaving the zip's directory intact."""
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        info = zf.getinfo(name)
    data = bytearray(archive)
    header = info.header_offset
    name_len, extra_len = struct.unpack("<HH", data[header + 26 : header + 30])
    start = header + 30 + name_len + extra_len
    for i in range(start, start + min(8, info.compress_size)):
        data[i] ^= 0x5A
    return bytes(data)


NON_ASCII = "invoice-triage/reference/café.md"


def _require_zip_version(archive: bytes, version: int) -> bytes:
    """Set the zip version that each central directory record says it needs."""
    data = bytearray(archive)
    start = data.find(b"PK\x01\x02")
    while start != -1:
        struct.pack_into("<H", data, start + 6, version)
        start = data.find(b"PK\x01\x02", start + 4)
    return bytes(data)


def _break_utf8_name(archive: bytes, *, central: bool) -> bytes:
    """Make ``NON_ASCII`` invalid UTF-8 in its local header, and in the central directory when ``central``."""
    return archive.replace("é".encode(), b"\xff\xfe", -1 if central else 1)


def _shift_central_directory(archive: bytes, by: int) -> bytes:
    """Move the central directory offset in the end record by ``by`` bytes."""
    data = bytearray(archive)
    end = data.rfind(b"PK\x05\x06")
    (offset,) = struct.unpack_from("<I", data, end + 16)
    struct.pack_into("<I", data, end + 16, offset + by)
    return bytes(data)


def _manifest(
    files: dict[str, bytes], version: int = 3, digest: str = DIGEST
) -> dict[str, object]:
    return {
        "version": version,
        "digest": digest,
        "entries": [
            {"path": path, "hash": "sha256:" + "0" * 64, "size": len(content)}
            for path, content in files.items()
        ],
    }


def _lookup_url(name: str, skip: int = 0) -> str:
    return f"{API}/skill-bundles?search={quote(name)}&skip={skip}&take=100"


def _version_url(version: str) -> str:
    return f"{API}/bundles/{KEY}/versions/{quote(version, safe='')}"


def _mock_bundle(
    httpx_mock: HTTPXMock,
    *,
    files: dict[str, bytes] = FILES,
    archive: bytes | None = None,
    version: str = "latest",
    folder_header: tuple[str, str] = (HEADER_FOLDER_PATH, FOLDER),
    items: list[dict[str, object]] | None = None,
) -> None:
    headers = {folder_header[0]: folder_header[1]}
    httpx_mock.add_response(
        url=_lookup_url("finance"),
        match_headers=headers,
        json={
            "items": items
            if items is not None
            else [
                {"key": "6f1c2c1e-0000-4000-8000-000000000099", "name": "finance-ap"},
                {"key": KEY, "name": "finance", "latestVersion": 3},
            ]
        },
    )
    httpx_mock.add_response(
        url=_version_url(version), match_headers=headers, json=_manifest(files)
    )
    httpx_mock.add_response(
        url=_version_url(DIGEST) + "/archive",
        match_headers=headers,
        content=archive if archive is not None else _zip(files),
    )


@pytest.fixture(autouse=True)
def no_job_folder(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.delenv(ENV_FOLDER_KEY, raising=False)
    monkeypatch.delenv(ENV_FOLDER_PATH, raising=False)
    return monkeypatch


@pytest.fixture
async def source(config: UiPathApiConfig, execution_context: UiPathExecutionContext):
    source = OrchestratorBundleSource(config, execution_context)
    yield source
    await source.aclose()


def _ref(**overrides: object) -> SkillBundleRef:
    return SkillBundleRef.model_validate(
        {"name": "finance", "folderPath": FOLDER, **overrides}
    )


async def test_latest_is_resolved_and_written_to_the_bundle_folder(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock)

    bundle = await source.materialize(_ref(), tmp_path / "finance")

    assert (bundle.version, bundle.digest) == ("3", DIGEST)
    assert [(s.name, s.description, s.files) for s in bundle.skills] == [
        (
            "invoice-triage",
            "Triage invoices",
            ["SKILL.md", "reference/vendors.md"],
        ),
        ("vendor-lookup", "Find vendors", ["SKILL.md"]),
    ]
    dest = tmp_path / "finance"
    assert (
        dest / "invoice-triage" / "reference" / "vendors.md"
    ).read_bytes() == b"Globex"
    assert not (dest / "bundle.json").exists()


@pytest.mark.parametrize("version", ["3", "release-1.2", DIGEST])
async def test_a_pinned_version_is_asked_for_as_given(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    version: str,
) -> None:
    _mock_bundle(httpx_mock, version=version)

    bundle = await source.materialize(
        _ref(versionMode="pinned", version=version), tmp_path / "finance"
    )

    assert bundle.version == "3"


@pytest.mark.parametrize(
    "version", ["../x", "latest", "lateſt", "a b", "x/y", "-1", ".hidden"]
)
async def test_an_unsafe_pinned_version_is_refused_before_any_request(
    source: OrchestratorBundleSource, tmp_path: Path, version: str
) -> None:
    with pytest.raises(BundleSourceError) as info:
        await source.materialize(
            _ref(versionMode="pinned", version=version), tmp_path / "finance"
        )

    assert info.value.reason == "invalid"


@pytest.mark.parametrize(
    ("env", "header"),
    [
        ((ENV_FOLDER_PATH, "Shared"), (HEADER_FOLDER_PATH, "Shared")),
        ((ENV_FOLDER_KEY, "f-key"), (HEADER_FOLDER_KEY, "f-key")),
    ],
)
async def test_the_job_folder_is_used_when_the_reference_names_none(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    httpx_mock: HTTPXMock,
    no_job_folder: pytest.MonkeyPatch,
    tmp_path: Path,
    env: tuple[str, str],
    header: tuple[str, str],
) -> None:
    no_job_folder.setenv(*env)
    _mock_bundle(httpx_mock, folder_header=header)
    source = OrchestratorBundleSource(config, execution_context)
    try:
        bundle = await source.materialize(_ref(folderPath=None), tmp_path / "finance")
    finally:
        await source.aclose()

    assert bundle.version == "3"


async def test_a_reference_without_any_folder_is_invalid(
    source: OrchestratorBundleSource, tmp_path: Path
) -> None:
    with pytest.raises(BundleSourceError, match="names no folder") as info:
        await source.materialize(_ref(folderPath=None), tmp_path / "finance")

    assert info.value.reason == "invalid"


async def test_a_name_that_only_partly_matches_is_not_found(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(
        url=_lookup_url("finance"),
        json={"items": [{"key": KEY, "name": "finance-ap"}]},
    )

    with pytest.raises(BundleSourceError, match="no skill bundle named") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "not_found"


async def test_a_match_that_differs_only_in_case_is_used(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock, items=[{"key": KEY, "name": "Finance"}])

    bundle = await source.materialize(_ref(), tmp_path / "finance")

    assert bundle.version == "3"


async def test_two_matches_that_differ_only_in_case_are_ambiguous(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(
        url=_lookup_url("finance"),
        json={
            "items": [
                {"key": KEY, "name": "Finance"},
                {"key": "6f1c2c1e-0000-4000-8000-000000000002", "name": "FINANCE"},
            ]
        },
    )

    with pytest.raises(BundleSourceError, match="more than one") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


async def test_the_lookup_reads_further_pages(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(
        url=_lookup_url("finance", skip=0),
        json={
            "items": [
                {"key": f"6f1c2c1e-0000-4000-8000-{i:012d}", "name": f"finance-{i}"}
                for i in range(100)
            ]
        },
    )
    httpx_mock.add_response(
        url=_lookup_url("finance", skip=100),
        json={"items": [{"key": KEY, "name": "finance"}]},
    )
    httpx_mock.add_response(url=_version_url("latest"), json=_manifest(FILES))
    httpx_mock.add_response(url=_version_url(DIGEST) + "/archive", content=_zip(FILES))

    bundle = await source.materialize(_ref(), tmp_path / "finance")

    assert bundle.version == "3"


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (401, {"message": "no"}, "forbidden"),
        (403, {"message": "no"}, "forbidden"),
        (400, {"message": "Folder does not exist", "errorCode": 1100}, "not_found"),
        (400, {"message": "bad request", "errorCode": 1}, "invalid"),
    ],
)
async def test_lookup_errors_map_to_a_reason(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    status: int,
    body: dict[str, object],
    reason: str,
) -> None:
    httpx_mock.add_response(url=_lookup_url("finance"), status_code=status, json=body)

    with pytest.raises(BundleSourceError) as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == reason
    assert f"HTTP {status}" in info.value.detail
    assert "secret" not in info.value.detail


async def test_a_missing_version_is_version_not_found(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(
        url=_lookup_url("finance"), json={"items": [{"key": KEY, "name": "finance"}]}
    )
    httpx_mock.add_response(
        url=_version_url("9"), status_code=404, json={"message": "No such version"}
    )

    with pytest.raises(BundleSourceError, match="No such version") as info:
        await source.materialize(
            _ref(versionMode="pinned", version="9"), tmp_path / "finance"
        )

    assert info.value.reason == "version_not_found"


@pytest.mark.parametrize("status", [408, 429, 503])
async def test_a_status_the_sdk_retries_is_source_unavailable_after_the_retries(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    status: int,
) -> None:
    httpx_mock.add_response(
        url=_lookup_url("finance"),
        status_code=status,
        headers={"Retry-After": "0"},
        json={"message": "busy"},
        is_reusable=True,
    )

    with pytest.raises(BundleSourceError) as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "source_unavailable"
    assert f"HTTP {status}" in info.value.detail
    assert len(httpx_mock.get_requests()) > 1


async def test_a_network_error_is_source_unavailable(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_exception(httpx.ReadError("connection reset"))

    with pytest.raises(BundleSourceError, match="ReadError") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "source_unavailable"


async def test_a_version_over_the_download_limit_is_refused_before_the_archive(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_sources, "MAX_ARCHIVE_BYTES", 10)
    httpx_mock.add_response(
        url=_lookup_url("finance"), json={"items": [{"key": KEY, "name": "finance"}]}
    )
    httpx_mock.add_response(url=_version_url("latest"), json=_manifest(FILES))

    with pytest.raises(BundleSourceError) as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "too_large"


async def test_a_manifest_without_a_digest_is_invalid(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(
        url=_lookup_url("finance"), json={"items": [{"key": KEY, "name": "finance"}]}
    )
    httpx_mock.add_response(
        url=_version_url("latest"), json=_manifest(FILES, digest="v3")
    )

    with pytest.raises(BundleSourceError, match="digest") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


@pytest.mark.parametrize(
    "entry", ["../evil.md", "/etc/evil.md", "a\\..\\evil.md", "a//b.md"]
)
async def test_an_archive_entry_outside_the_bundle_is_refused(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path, entry: str
) -> None:
    files = {**FILES, entry: b"x"}
    _mock_bundle(httpx_mock, files=files)

    with pytest.raises(BundleSourceError, match="not a relative path") as info:
        await source.materialize(_ref(), tmp_path / "work" / "finance")

    assert info.value.reason == "invalid"
    assert not (tmp_path / "evil.md").exists()
    assert not (tmp_path / "work" / "evil.md").exists()


async def test_symbolic_links_and_hidden_files_are_left_out(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    files = {**FILES, ".DS_Store": b"x", "invoice-triage/.secret": b"x"}
    archive = _zip(files, symlinks={"invoice-triage/link.md": "/etc/passwd"})
    _mock_bundle(httpx_mock, files=files, archive=archive)

    with caplog.at_level(logging.WARNING):
        bundle = await source.materialize(_ref(), tmp_path / "finance")

    assert bundle.skills[0].files == ["SKILL.md", "reference/vendors.md"]
    assert "symbolic link invoice-triage/link.md" in caplog.text


async def test_oversized_files_are_skipped_like_the_local_source(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    big = b"x" * (MAX_FILE_BYTES + 10)
    files = {
        **FILES,
        "invoice-triage/reference/huge.csv": big,
        "giant/SKILL.md": b"---\ndescription: d\n---\n" + big,
    }
    _mock_bundle(httpx_mock, files=files)

    with caplog.at_level(logging.WARNING):
        bundle = await source.materialize(_ref(), tmp_path / "finance")

    assert [s.name for s in bundle.skills] == ["invoice-triage", "vendor-lookup"]
    assert "reference/huge.csv" not in bundle.skills[0].files
    assert "Skipping skill 'giant'" in caplog.text
    assert "huge.csv" in caplog.text


async def test_an_archive_that_unpacks_past_the_limit_is_too_large(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_sources, "MAX_ARCHIVE_BYTES", 2000)
    files = {"a/SKILL.md": b"---\ndescription: d\n---\n" + b"0" * 5000}
    archive = _zip(files)
    assert len(archive) < 2000
    _mock_bundle(httpx_mock, files={"a/SKILL.md": b"small"}, archive=archive)

    with pytest.raises(BundleSourceError, match="unpacks to over") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "too_large"


async def test_an_archive_that_is_not_a_zip_is_invalid(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock, archive=b"not a zip")

    with pytest.raises(BundleSourceError, match="not a zip") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


async def test_a_write_error_reports_the_reason_without_the_local_path(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock)
    dest = tmp_path / "finance"
    dest.write_text("not a folder", encoding="utf-8")

    with pytest.raises(BundleSourceError) as info:
        await source.materialize(_ref(), dest)

    detail = info.value.detail
    assert info.value.reason == "source_unavailable"
    assert detail.startswith("cannot write skill bundle 'finance': ")
    assert str(tmp_path) not in detail
    assert "Errno" not in detail and "WinError" not in detail


@pytest.mark.parametrize(
    "compression",
    [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED],
    ids=["stored", "deflated"],
)
async def test_a_damaged_archive_entry_is_invalid(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    compression: int,
) -> None:
    archive = _damage_entry(
        _zip(FILES, compression=compression), "invoice-triage/reference/vendors.md"
    )
    _mock_bundle(httpx_mock, archive=archive)

    with pytest.raises(BundleSourceError, match="is damaged") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


@pytest.mark.parametrize(
    ("archive", "detail"),
    [
        (_require_zip_version(_zip(FILES), 100), "cannot be read as a zip file"),
        (
            _break_utf8_name(_zip({**FILES, NON_ASCII: b"x"}), central=True),
            "cannot be read as a zip file",
        ),
        (
            _break_utf8_name(_zip({**FILES, NON_ASCII: b"x"}), central=False),
            "is damaged",
        ),
        (_shift_central_directory(_zip(FILES), 1000), "is damaged"),
    ],
    ids=[
        "needs-zip-version-10",
        "name-not-utf-8",
        "local-header-name-not-utf-8",
        "central-directory-offset-too-large",
    ],
)
async def test_an_archive_zipfile_cannot_read_is_invalid(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    archive: bytes,
    detail: str,
) -> None:
    _mock_bundle(httpx_mock, archive=archive)

    with pytest.raises(BundleSourceError, match=detail) as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


async def test_an_encrypted_archive_entry_is_invalid(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock, archive=_zip(FILES, encrypted=("vendor-lookup/SKILL.md",)))

    with pytest.raises(BundleSourceError, match="is encrypted") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


async def test_an_archive_entry_with_another_compression_is_invalid(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock, archive=_zip(FILES, compression=zipfile.ZIP_BZIP2))

    with pytest.raises(BundleSourceError, match="compression method 12") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


@pytest.mark.parametrize(
    "files",
    [
        {"a": b"x", "a/SKILL.md": b"---\ndescription: d\n---\n"},
        {"a/SKILL.md": b"---\ndescription: d\n---\n", "a": b"x"},
    ],
    ids=["file-then-folder", "folder-then-file"],
)
async def test_an_entry_with_the_path_of_another_is_invalid(
    source: OrchestratorBundleSource,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    files: dict[str, bytes],
) -> None:
    _mock_bundle(httpx_mock, files=files)

    with pytest.raises(BundleSourceError, match="conflicts with another entry") as info:
        await source.materialize(_ref(), tmp_path / "finance")

    assert info.value.reason == "invalid"


async def test_a_source_that_was_never_used_closes_cleanly(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> None:
    source = OrchestratorBundleSource(config, execution_context)
    await source.aclose()
    await source.aclose()


async def test_a_ref_pinned_by_digest_keeps_its_name_and_reports_the_number(
    source: OrchestratorBundleSource, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_bundle(httpx_mock, version=DIGEST)
    ref = SkillBundleRef(
        name="finance",
        folder_path=FOLDER,
        version_mode=VersionMode.PINNED,
        version=DIGEST,
    )

    bundle = await source.materialize(ref, tmp_path / "finance")

    assert (bundle.ref, bundle.version, bundle.digest) == (ref, "3", DIGEST)
