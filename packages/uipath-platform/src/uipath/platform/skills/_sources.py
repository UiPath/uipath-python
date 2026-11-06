"""Where skill bundles come from: a local folder, or the Orchestrator Skills API once it ships."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Protocol

from uipath.platform.common import UiPathApiConfig, UiPathExecutionContext

from ._constants import (
    DEFAULT_SOURCE_KIND,
    ENV_SKILLS_LOCAL_ROOT,
    ENV_SKILLS_SOURCE,
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    SKILL_FILE_NAME,
    SKILLS_DIR_NAME,
)
from ._layout import find_skill_md, is_skill_md, iter_skill_files, read_bundle_version
from ._skill_md import parse_skill_description
from .skills import FailureReason, Skill, SkillBundle, SkillBundleRef, VersionMode

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
            dest: The bundle folder the caller owns. It must not exist yet or be
                empty: the caller resets it before calling and removes it on
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

    Meant for dev runs and Agent Builder debug copies: symlinked files are
    followed and copied like regular files. The copy runs on a worker thread,
    so it neither blocks the event loop nor outlives the caller's time budget
    by more than one file.
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
        large or not UTF-8 is skipped with a warning. Inside a skill, hidden files
        and files over ``MAX_FILE_BYTES`` are skipped. On an error, what was
        written so far is left under ``dest`` for the caller to remove.

        When the caller is cancelled or its timeout fires, the copy stops before
        its next file and this returns only once the worker thread has stopped,
        so nothing is written into ``dest`` after the caller removes it.

        Args:
            ref: The bound bundle.
            dest: The bundle folder the caller owns. It must not exist yet or be
                empty: the caller resets it before calling and removes it on
                failure. It is created here, so a bundle without a usable skill
                still has its folder.

        Returns:
            The folder's version and the copied skills, sorted by folder name.

        Raises:
            BundleSourceError: ``not_found`` if ``root`` has no folder for the
                bundle, ``too_large`` if the copied files exceed
                ``MAX_BUNDLE_BYTES``, ``source_unavailable`` if the bundle folder
                cannot be read or ``dest`` cannot be written.
        """
        stop = threading.Event()
        copy = asyncio.ensure_future(
            asyncio.to_thread(self._materialize, ref, dest, stop)
        )
        try:
            return await asyncio.shield(copy)
        except BaseException:
            stop.set()
            # Shielded, so the thread is waited for even though this task was
            # cancelled; it stops within one file.
            await asyncio.wait([copy])
            raise

    def _materialize(
        self, ref: SkillBundleRef, dest: Path, stop: threading.Event
    ) -> SkillBundle:
        """``materialize`` on the worker thread; ``stop`` ends it before the next file."""
        bundle_dir = self.root / ref.lookup_name
        try:
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
            budget = _ByteBudget(ref.name)
            skills: list[Skill] = []
            for skill_dir in sorted(bundle_dir.iterdir(), key=lambda p: p.name):
                _check(stop)
                skill_md_path = find_skill_md(skill_dir)
                if skill_md_path is None:
                    continue
                try:
                    skill_md = _read_skill_md(skill_md_path)
                except _SkipSkill as e:
                    logger.warning(
                        "Skipping skill '%s' in bundle '%s': %s",
                        skill_dir.name,
                        ref.name,
                        e,
                    )
                    continue
                skills.append(
                    _copy_skill(
                        ref.name,
                        skill_dir,
                        skill_md_path.name,
                        skill_md,
                        dest / skill_dir.name,
                        budget,
                        stop,
                    )
                )
        except OSError as e:
            raise BundleSourceError(
                f"cannot read or copy bundle '{ref.name}': {e}"
            ) from e
        else:
            return SkillBundle(ref=ref, version=version, skills=skills)

    async def aclose(self) -> None:
        """Nothing to release."""


class _SkipSkill(Exception):
    """Leave one skill out of the bundle; the message says why."""


class _Stopped(Exception):
    """The caller gave up on the copy; nothing more is written."""


def _check(stop: threading.Event) -> None:
    if stop.is_set():
        raise _Stopped()


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
    stop: threading.Event,
) -> Skill:
    """Copy a skill folder, skipping hidden and oversized files; ``SKILL.md`` is listed first.

    ``skill_md_name`` is the source spelling of ``SKILL.md`` (``skill.md``, for
    instance); it is written as ``SKILL.md`` so readers find it by the usual
    name, and any other spelling next to it is left out.
    """
    files: list[str] = []
    for rel in iter_skill_files(skill_dir):
        _check(stop)
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


class OrchestratorBundleSource:
    """Bundles from the Orchestrator Skills API. A placeholder until the API ships.

    Every bundle is reported as ``source_unavailable``, so selecting
    ``UIPATH_SKILLS_SOURCE=orchestrator`` today runs the agent without skills.
    """

    name = "orchestrator"

    def __init__(
        self, config: UiPathApiConfig | None, execution_context: UiPathExecutionContext
    ) -> None:
        """Keep what the Skills API calls will need.

        Args:
            config: Base URL and access token, or ``None`` when the caller has none.
            execution_context: The job's execution context, for the default folder.
        """
        self.config = config
        self.execution_context = execution_context

    async def materialize(self, ref: SkillBundleRef, dest: Path) -> SkillBundle:
        """Report the bundle as unavailable until the Skills API ships.

        Once it ships: resolve ``ref.lookup_name`` in ``ref.folder_path`` at the
        pinned or latest version, write ``dest/<skill>/...`` within the same
        limits as ``LocalFolderBundleSource``, and raise ``BundleSourceError``
        with the matching ``reason`` for API errors.

        Raises:
            BundleSourceError: Always, ``source_unavailable``.
        """
        raise BundleSourceError("the Orchestrator Skills API is not available yet")

    async def aclose(self) -> None:
        """Nothing to release yet."""


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

    ``local`` (the default) reads ``UIPATH_SKILLS_LOCAL_ROOT``, else
    ``./skills``. ``orchestrator`` is the Skills API placeholder, which skips
    every bundle until the API ships. An unknown value falls back to ``local``
    with a warning.

    Args:
        config: The SDK configuration the Orchestrator source will call the
            Skills API with; ``None`` when the caller has none.
        context: The job's execution context; a fresh one is read from the
            environment when ``None``.

    Returns:
        A source the caller closes with ``aclose`` when done.
    """
    kind = configured_source_kind()
    if kind == "orchestrator":
        return OrchestratorBundleSource(config, context or UiPathExecutionContext())
    if kind != "local":
        logger.warning(
            "Unknown %s=%r; loading skill bundles from the local folder",
            ENV_SKILLS_SOURCE,
            kind,
        )
    return LocalFolderBundleSource(
        Path(os.environ.get(ENV_SKILLS_LOCAL_ROOT) or Path.cwd() / SKILLS_DIR_NAME)
    )
