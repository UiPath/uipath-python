"""Where skill bundles come from: Orchestrator, or a local folder."""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from uipath.platform.common import (
    BaseService,
    FolderContext,
    UiPathApiConfig,
    UiPathExecutionContext,
    VersionMode,
)
from uipath.platform.common._folder_context import folder_path_header
from uipath.platform.common.retry import RETRYABLE_STATUS_CODES
from uipath.platform.errors import EnrichedException

from ._constants import (
    BUNDLE_ENDPOINT,
    DEFAULT_SOURCE_KIND,
    ENV_SKILLS_LOCAL_ROOT,
    ENV_SKILLS_SOURCE,
    LOOKUP_MAX_PAGES,
    LOOKUP_PAGE_SIZE,
    MAX_ARCHIVE_BYTES,
    MAX_ARCHIVE_ENTRIES,
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    SKILL_BUNDLES_ENDPOINT,
    SKILL_FILE_NAME,
    SKILLS_DIR_NAME,
)
from ._layout import (
    find_skill_md,
    is_plain_name,
    is_skill_md,
    iter_skill_files,
    read_bundle_version,
)
from ._skill_md import parse_skill_description
from .skills import FailureReason, Skill, SkillBundle, SkillBundleRef

logger = logging.getLogger(__name__)


class BundleSourceError(Exception):
    """A bundle could not be materialized; ``reason`` is the ``BundleFailure.reason`` to report."""

    def __init__(
        self, detail: str, *, reason: FailureReason = "source_unavailable"
    ) -> None:
        """Describe the failure.

        Args:
            detail: Human-readable context for logs and ``BundleFailure.detail``.
            reason: Why the bundle is skipped; ``source_unavailable`` by default.
        """
        super().__init__(detail)
        self.detail = detail
        self.reason: FailureReason = reason


class SkillBundleSource(Protocol):
    """Fetches a bound skill bundle and writes its skills into a folder."""

    name: str
    """Short label for telemetry: ``local`` | ``orchestrator``."""

    async def materialize(self, ref: SkillBundleRef, dest: Path) -> SkillBundle:
        """Write the bundle's skills under ``dest/<skill>/`` and describe what was written.

        ``dest`` is created even when the bundle has no usable skill. On an
        error, what was written so far is left under ``dest`` for the caller to
        remove.

        Args:
            ref: The bound bundle; ``ref.lookup_name`` selects what to fetch.
            dest: The bundle folder the caller owns. It does not exist yet or is
                empty when this is called, and the caller removes it on
                failure. A leftover ``dest/<skill>`` folder is taken for an
                earlier skill of this bundle and shadows the real one.

        Returns:
            The resolved version and the skills written under ``dest``.

        Raises:
            BundleSourceError: The bundle cannot be used; its ``reason`` says
                why (``not_found``, ``version_not_found``, ``invalid``,
                ``forbidden``, ``too_large`` or ``source_unavailable``).
        """
        ...

    async def aclose(self) -> None:
        """Release what the source holds open, such as HTTP clients."""
        ...


class LocalFolderBundleSource:
    """Bundles laid out as ``<root>/<bundle>/<skill>/SKILL.md``, with an optional ``bundle.json``.

    Meant for dev runs and Agent Builder debug copies. Symbolic links are not
    followed: a linked bundle folder is refused, and linked skill folders and
    files are left out. The copy runs on the event loop without yielding, so
    the caller's time limit does not interrupt it; ``MAX_BUNDLE_BYTES`` bounds
    it instead.
    """

    name = "local"

    def __init__(self, root: Path) -> None:
        """Serve bundles from ``root``.

        Args:
            root: The folder holding one subfolder per bundle.
        """
        self.root = root

    async def materialize(self, ref: SkillBundleRef, dest: Path) -> SkillBundle:
        """Copy ``<root>/<ref.lookup_name>/`` skills into ``dest``.

        A pinned version that differs from the folder's is loaded anyway, with a
        warning: local folders hold one version only. Hidden folders and folders
        without a ``SKILL.md`` are not skills; the name is matched in any case
        and copied as ``SKILL.md``. A skill whose ``SKILL.md`` is too
        large or not UTF-8 is skipped with a warning. Inside a skill, hidden files,
        symbolic links and files over ``MAX_FILE_BYTES`` are skipped. On an
        error, what was written so far is left under ``dest`` for the caller to
        remove.

        Args:
            ref: The bound bundle.
            dest: The bundle folder the caller owns. It does not exist yet or is
                empty when this is called, and the caller removes it on
                failure. It is created here, so a bundle without a usable skill
                still has its folder.

        Returns:
            The folder's version and the copied skills, sorted by folder name.

        Raises:
            BundleSourceError: ``not_found`` if ``root`` has no folder for the
                bundle, ``invalid`` if that folder is a symbolic link,
                ``too_large`` if the copied files exceed ``MAX_BUNDLE_BYTES``,
                ``source_unavailable`` if the bundle folder cannot be read or
                ``dest`` cannot be written.
        """
        bundle_dir = self.root / ref.lookup_name
        try:
            if bundle_dir.is_symlink():
                raise BundleSourceError(
                    f"{bundle_dir} is a symbolic link; links are not followed",
                    reason="invalid",
                )
            if not bundle_dir.is_dir():
                raise BundleSourceError(f"no folder {bundle_dir}", reason="not_found")
            version = read_bundle_version(bundle_dir)
            if ref.version_mode is VersionMode.PINNED and ref.version != version:
                logger.warning(
                    "Skill bundle '%s' is pinned to version %s but the local folder is %s; loading it anyway",
                    ref.name,
                    ref.version,
                    version,
                )
            dest.mkdir(parents=True, exist_ok=True)
            skills = _copy_bundle_skills(ref.name, bundle_dir, dest)
        except OSError as e:
            raise BundleSourceError(
                f"cannot read or copy bundle '{ref.name}': {e}"
            ) from e
        else:
            return SkillBundle(ref=ref, version=version, skills=skills)

    async def aclose(self) -> None:
        """Nothing to release."""


def _copy_bundle_skills(bundle: str, bundle_dir: Path, dest: Path) -> list[Skill]:
    """Copy each skill folder of ``bundle_dir`` into ``dest``, sorted by folder name.

    Hidden folders and folders without a ``SKILL.md`` are not skills. A skill
    whose ``SKILL.md`` is too large or not UTF-8 is skipped with a warning.

    Raises:
        BundleSourceError: ``too_large`` once the copied files exceed
            ``MAX_BUNDLE_BYTES``.
        OSError: A file cannot be read or written.
    """
    budget = _ByteBudget(bundle)
    skills: list[Skill] = []
    for skill_dir in sorted(bundle_dir.iterdir(), key=lambda p: p.name):
        skill_md_path = find_skill_md(skill_dir)
        if skill_md_path is None:
            continue
        try:
            skill_md = _read_skill_md(skill_md_path)
        except _SkipSkill as e:
            logger.warning(
                "Skipping skill '%s' in bundle '%s': %s", skill_dir.name, bundle, e
            )
            continue
        skills.append(
            _copy_skill(
                bundle,
                skill_dir,
                skill_md_path.name,
                skill_md,
                dest / skill_dir.name,
                budget,
            )
        )
    return skills


class _SkipSkill(Exception):
    """Leave one skill out of the bundle; the message says why."""


class _ByteBudget:
    """Running total of bytes copied for one bundle, capped at ``MAX_BUNDLE_BYTES``."""

    def __init__(self, bundle: str) -> None:
        self.bundle = bundle
        self.used = 0

    def spend(self, size: int) -> None:
        self.used += size
        if self.used > MAX_BUNDLE_BYTES:
            raise BundleSourceError(
                f"skill bundle '{self.bundle}' is over {MAX_BUNDLE_BYTES} bytes",
                reason="too_large",
            )

    def refund(self, size: int) -> None:
        self.used -= size


def _read_skill_md(path: Path) -> str:
    """The source ``SKILL.md`` text, checked before anything is copied.

    Raises:
        _SkipSkill: If the file is too large or cannot be read as UTF-8.
    """
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise _SkipSkill(f"unusable {SKILL_FILE_NAME}: over {MAX_FILE_BYTES} bytes")
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        raise _SkipSkill(f"unusable {SKILL_FILE_NAME}: {e}") from e


def _copy_skill(
    bundle: str,
    skill_dir: Path,
    skill_md_name: str,
    skill_md: str,
    dest: Path,
    budget: _ByteBudget,
) -> Skill:
    """Copy a skill folder, skipping hidden and oversized files; ``SKILL.md`` is listed first.

    ``skill_md_name`` is the source spelling of ``SKILL.md`` (``skill.md``, for
    instance); it is written as ``SKILL.md`` so readers find it by the usual
    name, and any other spelling next to it is left out.
    """
    files: list[str] = []
    for rel in iter_skill_files(skill_dir):
        if is_skill_md(rel) and rel != skill_md_name:
            logger.warning(
                "Skipping %s/%s in bundle '%s': the skill already has %s",
                skill_dir.name,
                rel,
                bundle,
                skill_md_name,
            )
            continue
        path = skill_dir / rel
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            logger.warning(
                "Skipping %s/%s in bundle '%s': over %d bytes",
                skill_dir.name,
                rel,
                bundle,
                MAX_FILE_BYTES,
            )
            continue
        budget.spend(size)
        written = SKILL_FILE_NAME if rel == skill_md_name else rel
        target = dest / written
        target.parent.mkdir(parents=True, exist_ok=True)
        # Content only: copy2 would carry read-only bits into the bundle folder.
        shutil.copyfile(path, target)
        files.append(written)
    return Skill(
        name=skill_dir.name,
        description=parse_skill_description(skill_md),
        files=files,
    )


# --- Orchestrator ---

_VERSION_NUMBER = re.compile(r"[0-9]+")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_LATEST = "latest"
_FOLDER_NOT_FOUND = "1100"
_FILE_TYPE_MASK = 0o170000
_SYMLINK = 0o120000
_ENCRYPTED_FLAG = 0x1
_READABLE_COMPRESSION = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)


class _ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    size: int = 0


class _Manifest(BaseModel):
    """The parts of a bundle version's manifest this source reads."""

    model_config = ConfigDict(extra="ignore")

    version: int
    digest: str
    entries: list[_ManifestEntry] = Field(default_factory=list)


class OrchestratorBundleSource:
    """Bundles from Orchestrator, looked up by name in a folder.

    A bundle is found by its exact name in ``ref.folder_path``, or in the job's
    folder when the reference has none. ``pinned`` asks for ``ref.version`` (a
    version number, a tag or a ``sha256:`` digest), ``latest`` for the newest
    published version. The version's manifest is read first, so a version over
    the download limit is refused before anything is downloaded. The archive is
    then fetched by the manifest's digest, so its files are exactly the ones the
    manifest lists, even when ``latest`` moves in between. The archive is
    unpacked into a temporary folder and copied into the bundle folder with the
    same rules as ``LocalFolderBundleSource``.
    """

    name = "orchestrator"

    def __init__(
        self, config: UiPathApiConfig | None, execution_context: UiPathExecutionContext
    ) -> None:
        """Keep what the API calls need; the HTTP clients are created on first use.

        Args:
            config: Base URL and access token, or ``None`` when the caller has none.
            execution_context: The job's execution context, for the default folder.
        """
        self.config = config
        self.execution_context = execution_context
        self._api: _SkillBundlesApi | None = None

    async def materialize(self, ref: SkillBundleRef, dest: Path) -> SkillBundle:
        """Fetch ``ref`` from Orchestrator and write its skills under ``dest/<skill>/``.

        Args:
            ref: The bound bundle; ``ref.lookup_name`` is the name looked up.
            dest: The bundle folder the caller owns. It does not exist yet or is
                empty when this is called, and the caller removes it on
                failure.

        Returns:
            The resolved version number, its digest and the copied skills.

        Raises:
            BundleSourceError: ``not_found`` when the folder or the bundle does not
                exist, ``version_not_found`` when the bundle exists but the
                version does not exist, ``forbidden`` when access is denied,
                ``too_large`` past the download or copy limits, ``invalid`` for a
                malformed reference, manifest or archive, ``source_unavailable``
                when Orchestrator cannot be reached, still fails after the SDK's
                retries, or there is no configuration to call it with.
        """
        api = self._client()
        version = _version_segment(ref)
        headers = api.headers_for(ref)
        key = await api.find(ref.lookup_name, headers)
        manifest = await api.manifest(key, version, headers)
        _check_download_size(ref.name, manifest)
        archive = await api.archive(key, manifest.digest, headers)
        # Unpacked on the event loop: the size limits bound it, and only the
        # HTTP calls above need the caller's time limit.
        skills = _unpack_and_copy(ref.name, archive, dest)
        return SkillBundle(
            ref=ref,
            version=str(manifest.version),
            digest=manifest.digest,
            skills=skills,
        )

    def _client(self) -> _SkillBundlesApi:
        if self.config is None:
            raise BundleSourceError("no UiPath configuration to call Orchestrator with")
        if self._api is None:
            self._api = _SkillBundlesApi(self.config, self.execution_context)
        return self._api

    async def aclose(self) -> None:
        """Close the HTTP clients, if any were created."""
        api, self._api = self._api, None
        if api is not None:
            await api.aclose()


class _SkillBundlesApi(FolderContext, BaseService):
    """The three Orchestrator calls behind ``OrchestratorBundleSource``."""

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def headers_for(self, ref: SkillBundleRef) -> dict[str, str]:
        """The folder header for ``ref``: its own folder, else the job's."""
        headers = (
            folder_path_header(ref.folder_path)
            if ref.folder_path
            else self.folder_headers
        )
        if not headers:
            raise BundleSourceError(
                f"skill bundle '{ref.name}' names no folder and the job has none",
                reason="invalid",
            )
        return headers

    async def find(self, name: str, headers: dict[str, str]) -> uuid.UUID:
        """The key of the bundle called ``name`` in the folder ``headers`` name.

        ``search`` matches part of a name, so the pages are filtered for the name
        itself: an exact match first, else a match that differs only in case.
        """
        wanted = name.casefold()
        matches: list[dict[str, object]] = []
        for page in range(LOOKUP_MAX_PAGES):
            body = await self._get_json(
                SKILL_BUNDLES_ENDPOINT,
                headers,
                step="bundle lookup",
                params={
                    "search": name,
                    "skip": page * LOOKUP_PAGE_SIZE,
                    "take": LOOKUP_PAGE_SIZE,
                },
            )
            items = body.get("items") if isinstance(body, dict) else None
            if not isinstance(items, list):
                raise BundleSourceError(
                    "bundle lookup returned no item list", reason="invalid"
                )
            matches += [
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get("name", "")).casefold() == wanted
            ]
            if len(items) < LOOKUP_PAGE_SIZE:
                break
        found = [m for m in matches if m.get("name") == name] or matches
        if not found:
            raise BundleSourceError(
                f"no skill bundle named '{name}' in the folder", reason="not_found"
            )
        if len(found) > 1:
            raise BundleSourceError(
                f"more than one skill bundle named '{name}' in the folder",
                reason="invalid",
            )
        try:
            return uuid.UUID(str(found[0].get("key")))
        except ValueError as e:
            raise BundleSourceError(
                f"skill bundle '{name}' has no valid key", reason="invalid"
            ) from e

    async def manifest(
        self, key: uuid.UUID, version: str, headers: dict[str, str]
    ) -> _Manifest:
        """The manifest of ``version``: its number, digest and file sizes."""
        body = await self._get_json(
            f"{BUNDLE_ENDPOINT.format(key=key)}/versions/{quote(version, safe='')}",
            headers,
            step="version manifest",
        )
        try:
            manifest = _Manifest.model_validate(body)
        except ValidationError as e:
            raise BundleSourceError(
                f"version manifest has an unexpected shape: {e.errors()[0]['msg']}",
                reason="invalid",
            ) from e
        if not _DIGEST.fullmatch(manifest.digest):
            raise BundleSourceError(
                "version manifest has no sha256 digest", reason="invalid"
            )
        return manifest

    async def archive(
        self, key: uuid.UUID, digest: str, headers: dict[str, str]
    ) -> bytes:
        """The zip of the version with ``digest``; its entries are the manifest paths."""
        response = await self._get(
            f"{BUNDLE_ENDPOINT.format(key=key)}/versions/{quote(digest, safe='')}/archive",
            {**headers, "Accept": "application/zip"},
            step="version archive",
        )
        if len(response.content) > MAX_ARCHIVE_BYTES:
            raise BundleSourceError(
                f"version archive is over {MAX_ARCHIVE_BYTES} bytes", reason="too_large"
            )
        return response.content

    async def _get_json(
        self,
        url: str,
        headers: dict[str, str],
        *,
        step: str,
        params: dict[str, str | int] | None = None,
    ) -> object:
        response = await self._get(url, headers, step=step, params=params)
        try:
            return response.json()
        except ValueError as e:
            raise BundleSourceError(f"{step} returned no JSON", reason="invalid") from e

    async def _get(
        self,
        url: str,
        headers: dict[str, str],
        *,
        step: str,
        params: dict[str, str | int] | None = None,
    ) -> httpx.Response:
        try:
            return await self.request_async(
                "GET", url, params=params, headers=dict(headers)
            )
        except EnrichedException as e:
            info = e.error_info
            message = info.message if info and info.message else "no message"
            code = info.error_code if info else None
            raise BundleSourceError(
                f"{step} returned HTTP {e.status_code}: {message}",
                reason=_reason_for(e.status_code, code, step),
            ) from e
        except httpx.HTTPError as e:
            raise BundleSourceError(f"{step} failed: {type(e).__name__}") from e


def _version_segment(ref: SkillBundleRef) -> str:
    """The ``{version}`` path segment for ``ref``, checked before it reaches a URL."""
    if ref.version_mode is VersionMode.LATEST:
        return _LATEST
    version = ref.version or ""
    if (
        _VERSION_NUMBER.fullmatch(version)
        or _DIGEST.fullmatch(version)
        or (_TAG.fullmatch(version) and version.casefold() != _LATEST)
    ):
        return version
    raise BundleSourceError(
        f"pinned version {version!r} of skill bundle '{ref.name}' is not a version "
        "number, a tag or a sha256 digest",
        reason="invalid",
    )


def _reason_for(status: int, error_code: str | None, step: str) -> FailureReason:
    """The ``BundleFailure.reason`` for an HTTP error status.

    A status the SDK retries (408, 429 and some 5xx) is ``source_unavailable``.
    """
    if status in (401, 403):
        return "forbidden"
    if status == 404:
        return "not_found" if step == "bundle lookup" else "version_not_found"
    if status == 400 and error_code == _FOLDER_NOT_FOUND:
        return "not_found"
    if 400 <= status < 500 and status not in RETRYABLE_STATUS_CODES:
        return "invalid"
    return "source_unavailable"


def _check_download_size(bundle: str, manifest: _Manifest) -> None:
    """Refuse a version whose manifest is over the download limits."""
    if len(manifest.entries) > MAX_ARCHIVE_ENTRIES:
        raise BundleSourceError(
            f"skill bundle '{bundle}' has over {MAX_ARCHIVE_ENTRIES} files",
            reason="too_large",
        )
    total = sum(max(entry.size, 0) for entry in manifest.entries)
    if total > MAX_ARCHIVE_BYTES:
        raise BundleSourceError(
            f"skill bundle '{bundle}' is over {MAX_ARCHIVE_BYTES} bytes",
            reason="too_large",
        )


def _unpack_and_copy(bundle: str, archive: bytes, dest: Path) -> list[Skill]:
    """Unpack ``archive`` into a temporary folder, then copy its skills into ``dest``."""
    try:
        with tempfile.TemporaryDirectory(prefix="uipath-skill-bundle-") as tmp:
            staging = Path(tmp)
            _unpack(bundle, archive, staging)
            dest.mkdir(parents=True, exist_ok=True)
            return _copy_bundle_skills(bundle, staging, dest)
    except OSError as e:
        raise BundleSourceError(
            f"cannot write skill bundle '{bundle}': {e.strerror or type(e).__name__}"
        ) from e


def _unpack(bundle: str, archive: bytes, staging: Path) -> None:
    """Write the archive's files under ``staging``, refusing anything outside it.

    The archive is ``invalid`` when it cannot be read as a zip file, or when an
    entry is not a relative path inside the bundle, is encrypted, uses a
    compression other than stored or deflated, is damaged, or conflicts with
    another entry (one path used as both a file and a folder, or used twice).
    The archive is in memory, so any error while opening it or reading an entry
    comes from its bytes, whatever exception ``zipfile`` raises for it.
    Hidden files and symbolic links are left out. Each file is cut at one byte
    over ``MAX_FILE_BYTES``, so the copy step still sees it as too large and
    skips it with its usual warning; the bytes written in all stay within
    ``MAX_ARCHIVE_BYTES``.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive))
    except Exception as e:
        raise BundleSourceError(
            f"skill bundle '{bundle}' archive cannot be read as a zip file: "
            f"{_zip_error(e)}",
            reason="invalid",
        ) from e
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise BundleSourceError(
                f"skill bundle '{bundle}' has over {MAX_ARCHIVE_ENTRIES} files",
                reason="too_large",
            )
        root = staging.resolve()
        written = 0
        for info in infos:
            if info.is_dir():
                continue
            name = info.filename
            parts = name.split("/")
            if "\\" in name or any(part in ("", ".", "..") for part in parts):
                raise BundleSourceError(
                    f"skill bundle '{bundle}' archive entry {name!r} is not a "
                    "relative path inside the bundle",
                    reason="invalid",
                )
            if not all(is_plain_name(part) for part in parts):
                continue
            if (info.external_attr >> 16) & _FILE_TYPE_MASK == _SYMLINK:
                logger.warning("Skipping symbolic link %s in bundle '%s'", name, bundle)
                continue
            if info.flag_bits & _ENCRYPTED_FLAG:
                raise BundleSourceError(
                    f"skill bundle '{bundle}' archive entry {name!r} is encrypted",
                    reason="invalid",
                )
            if info.compress_type not in _READABLE_COMPRESSION:
                raise BundleSourceError(
                    f"skill bundle '{bundle}' archive entry {name!r} uses compression "
                    f"method {info.compress_type}; only stored and deflated are read",
                    reason="invalid",
                )
            target = (staging / name).resolve()
            if root not in target.parents:
                raise BundleSourceError(
                    f"skill bundle '{bundle}' archive entry {name!r} leaves the bundle",
                    reason="invalid",
                )
            if target.exists():
                raise _path_conflict(bundle, name)
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except (FileExistsError, NotADirectoryError) as e:
                raise _path_conflict(bundle, name) from e
            written += _write_capped(bundle, zf, info, target, MAX_FILE_BYTES + 1)
            if written > MAX_ARCHIVE_BYTES:
                raise BundleSourceError(
                    f"skill bundle '{bundle}' unpacks to over {MAX_ARCHIVE_BYTES} bytes",
                    reason="too_large",
                )


def _write_capped(
    bundle: str, zf: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path, limit: int
) -> int:
    """Write at most ``limit`` bytes of ``info`` to ``target``; returns the bytes written.

    Any error while reading the entry (bad CRC, broken deflate stream, data cut
    short, a bad header or offset) makes the archive ``invalid``; a disk error
    while writing is left to the caller.
    """
    try:
        with zf.open(info) as source:
            data = source.read(limit)
    except Exception as e:
        raise BundleSourceError(
            f"skill bundle '{bundle}' archive entry {info.filename!r} is damaged: "
            f"{_zip_error(e)}",
            reason="invalid",
        ) from e
    target.write_bytes(data)
    return len(data)


def _zip_error(error: Exception) -> str:
    """The text of a ``zipfile`` error, or its type when it has none."""
    return str(error) or type(error).__name__


def _path_conflict(bundle: str, name: str) -> BundleSourceError:
    """The error for an entry whose path another entry already uses."""
    return BundleSourceError(
        f"skill bundle '{bundle}' archive entry {name!r} conflicts with another "
        "entry: a path cannot be both a file and a folder, or appear twice",
        reason="invalid",
    )


# --- Source selection ---


def configured_source_kind() -> str:
    """``UIPATH_SKILLS_SOURCE``, normalized; ``DEFAULT_SOURCE_KIND`` when unset or blank.

    Returns:
        The lower-cased value, which may be one ``get_bundle_source`` does not know.
    """
    return (
        os.environ.get(ENV_SKILLS_SOURCE) or ""
    ).strip().lower() or DEFAULT_SOURCE_KIND


def get_bundle_source(
    config: UiPathApiConfig | None, context: UiPathExecutionContext | None
) -> SkillBundleSource:
    """The bundle source named by ``UIPATH_SKILLS_SOURCE``.

    ``orchestrator`` (the default) fetches bundles from Orchestrator.
    ``local`` reads ``UIPATH_SKILLS_LOCAL_ROOT``, else ``./skills``. An unknown
    value falls back to the default with a warning.

    Args:
        config: The SDK configuration the Orchestrator source calls Orchestrator
            with; ``None`` when the caller has none.
        context: The job's execution context; a fresh one is read from the
            environment when ``None``.

    Returns:
        A source the caller closes with ``aclose`` when done.
    """
    kind = configured_source_kind()
    if kind not in ("local", "orchestrator"):
        logger.warning(
            "Unknown %s=%r; using the default source, %s",
            ENV_SKILLS_SOURCE,
            kind,
            DEFAULT_SOURCE_KIND,
        )
        kind = DEFAULT_SOURCE_KIND
    if kind == "orchestrator":
        return OrchestratorBundleSource(config, context or UiPathExecutionContext())
    return LocalFolderBundleSource(
        Path(os.environ.get(ENV_SKILLS_LOCAL_ROOT) or Path.cwd() / SKILLS_DIR_NAME)
    )
