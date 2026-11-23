"""The SDK service that resolves, downloads and exposes an agent's skill bundles.

``SkillsService.load_all`` turns the bundle references an agent declares into a
``SkillSet`` on disk: the run's ``skillBundle.<name>`` resource overwrites are
applied first, each bundle is fetched from the configured source under a
per-bundle time budget, and whatever cannot be resolved is reported in
``SkillSet.failures`` and on the ``Skill bundles resolved`` span instead of
failing the run.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import logging
import shutil
import tempfile
from collections.abc import Coroutine, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from opentelemetry.trace import Span

from uipath.platform.common import (
    BaseService,
    FolderContext,
    UiPathApiConfig,
    UiPathExecutionContext,
)

from ._constants import BUNDLE_RESOLVE_TIMEOUT_SECONDS, MANIFEST_FILE_NAME
from ._overwrites import (
    InvalidSkillBundleOverwrite,
    apply_skill_bundle_overwrite,
    current_overwrites,
)
from ._sources import (
    BundleSourceError,
    SkillBundleSource,
    configured_source_kind,
    get_bundle_source,
)
from ._telemetry import (
    bundles_resolved_span,
    record_bundle_failed,
    record_bundles_resolved,
)
from .skills import (
    BundleFailure,
    FailureReason,
    SkillBundle,
    SkillBundleRef,
    SkillSet,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TEMP_PREFIX = "uipath-skills-"
"""Prefix of the temp folder ``load_all`` creates when no destination is given."""


class SkillsService(FolderContext, BaseService):
    """Resolve the skill bundles an agent is bound to and expose their skills to agent code.

    Each bundle is ``pinned`` to a version or follows the ``latest`` one. Deploy-time
    overrides (``skillBundle.<name>`` resource overwrites) are applied before fetching.
    A bundle that cannot be resolved is reported, never raised, by ``load_all``.

    Where the bundles come from is chosen by ``UIPATH_SKILLS_SOURCE``: a local
    folder (the default) or the Orchestrator Skills API, a placeholder until
    that API ships. The ``*_async`` methods are preferred; each
    synchronous twin runs its async method to completion, on a worker thread
    when an event loop is already running in the calling thread.
    """

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        """Create the service.

        Args:
            config: Base URL and access token for the Skills API.
            execution_context: The job's execution context.
        """
        super().__init__(config=config, execution_context=execution_context)

    async def load_all_async(
        self,
        refs: Sequence[SkillBundleRef],
        *,
        destination: Path | None = None,
        source: SkillBundleSource | None = None,
    ) -> SkillSet:
        """Resolve ``refs`` in order, write each bundle under ``<root>/<name>/`` and describe the set.

        The run's ``skillBundle.<name>`` resource overwrites are applied to each
        reference first; an invalid one fails its bundle as ``invalid`` rather
        than falling back to the declared reference. Every bundle gets ``BUNDLE_RESOLVE_TIMEOUT_SECONDS`` of
        wall clock; after the first timeout the remaining bundles are skipped
        without being tried. A bundle that fails is reported in
        ``SkillSet.failures`` and as a ``skill.bundle.failed`` event on the
        ``Skill bundles resolved`` span; nothing here fails the run, though
        cancellation still propagates. Nothing the SDK did not write is ever
        removed. After an error, cancellation included, the bundle folders
        written so far are removed again, and an owned temp root is removed
        whole.

        Args:
            refs: The bundles the agent is bound to. With none, nothing is
                fetched, no span is emitted and the set has no ``root``; a
                ``destination`` that holds only an earlier load's bundles is
                cleared.
            destination: The folder to write into, which the set does not own.
                It may be missing, empty, or hold only what an earlier load
                wrote there, as its manifest lists; that is removed first. When
                it holds anything else, or is a file or a symbolic link, every
                bundle fails as ``invalid`` and nothing in it changes.
                ``SkillSet.cleanup`` removes only what this call wrote there. By
                default a temp folder is created that the set owns and
                ``cleanup`` removes.
            source: Where bundles come from; by default the one
                ``UIPATH_SKILLS_SOURCE`` selects. It is closed before this
                returns.

        Returns:
            The resolved bundles and the failures. ``root`` is set only when at
            least one bundle resolved; an owned temp folder is removed otherwise.
        """
        refs = list(refs)
        if not refs:
            return await _empty_set(destination, source)
        try:
            with bundles_resolved_span() as span:
                result, root = await self._resolve(span, refs, destination, source)
        except Exception as e:
            logger.exception(
                "Skill bundles could not be materialized; continuing without skills"
            )
            return _unexpected_failure(refs, e)
        owns_root = destination is None
        if not result.bundles or root is None:
            if owns_root and root is not None:
                _remove_tree(root)
            return result
        result.root = root
        result.owns_root = owns_root
        result._wrote_bundles = True
        return result

    def load_all(
        self,
        refs: Sequence[SkillBundleRef],
        *,
        destination: Path | None = None,
        source: SkillBundleSource | None = None,
    ) -> SkillSet:
        """Resolve and download ``refs``; see ``load_all_async``.

        ``load_all_async`` is preferred. This runs it to completion, on a
        worker thread when an event loop is already running in this thread;
        the resource-overwrite context of the calling thread still applies.
        Called from a running loop, it blocks the caller for up to the
        per-bundle budget per bundle.

        Args:
            refs: The bundles the agent is bound to.
            destination: The folder to write into, not owned by the set; see
                ``load_all_async``. By default an owned temp folder.
            source: Where bundles come from; by default the one
                ``UIPATH_SKILLS_SOURCE`` selects. It is closed before this
                returns.

        Returns:
            The resolved bundles and the failures.
        """
        return _run_sync(
            self.load_all_async(refs, destination=destination, source=source)
        )

    async def _resolve(
        self,
        span: Span,
        refs: list[SkillBundleRef],
        destination: Path | None,
        source: SkillBundleSource | None,
    ) -> tuple[SkillSet, Path | None]:
        """Resolve ``refs`` into ``destination``, or into a temp root created here.

        Returns the set and the root it was written to, ``None`` when no root
        could be created. An owned temp root is removed if anything raises.
        """
        if destination is not None:
            return await self._resolve_into(
                span, refs, destination, source
            ), destination
        try:
            root = Path(tempfile.mkdtemp(prefix=_TEMP_PREFIX))
        except OSError as e:
            # A full or unwritable temp dir is reported like any other setup
            # failure; the run continues without skills.
            source_name = _source_name(source)
            if source is not None:
                await _close_source(source)
            failed = _fail_all(
                span,
                source_name,
                refs,
                reason="source_unavailable",
                detail=f"cannot create the skills folder: {e}",
            )
            return failed, None
        try:
            return await self._resolve_into(span, refs, root, source), root
        except BaseException:
            _remove_tree(root)
            raise

    async def _resolve_into(
        self,
        span: Span,
        refs: list[SkillBundleRef],
        root: Path,
        source: SkillBundleSource | None,
    ) -> SkillSet:
        """Prepare ``root``, build the source when none was given, materialize, and close the source.

        A caller-supplied ``source`` is closed on every path, a refused
        ``root`` included.
        """
        try:
            problem = _prepare_destination(root)
            if problem is not None:
                return _fail_all(
                    span, _source_name(source), refs, reason="invalid", detail=problem
                )
            if source is None:
                # get_bundle_source raises when the configured source cannot be
                # built. That is a configuration problem, not a reason to fail
                # the run and not a reason to silently read another source
                # instead: report every bundle and continue.
                try:
                    source = get_bundle_source(self._config, self._execution_context)
                except Exception as e:
                    return _fail_all(
                        span,
                        configured_source_kind(),
                        refs,
                        reason="source_unavailable",
                        detail=f"skills source unavailable: {e!r}",
                    )
            return await _materialize_with(span, source, refs, root)
        finally:
            if source is not None:
                await _close_source(source)


async def _materialize_with(
    span: Span,
    source: SkillBundleSource,
    refs: list[SkillBundleRef],
    root: Path,
) -> SkillSet:
    """Materialize ``refs`` in order into the empty ``root``, then write the manifest.

    The manifest is written only when at least one bundle resolved; the caller
    decides what happens to ``root`` otherwise. On an error, cancellation
    included, the bundle folders and manifest written so far are removed.
    """
    overwrites = current_overwrites()
    bundles: list[SkillBundle] = []
    failures: list[BundleFailure] = []
    seen: set[str] = set()
    timed_out = False
    try:
        for declared in refs:
            failure: BundleFailure | None = None
            try:
                ref = apply_skill_bundle_overwrite(declared, overwrites)
            except InvalidSkillBundleOverwrite as e:
                ref = declared
                failure = BundleFailure(ref=ref, reason="invalid", detail=str(e))
            dest = root / ref.name
            if failure is None:
                if ref.name.casefold() in seen or dest.exists():
                    # A second reference would write into the first one's folder and
                    # shadow or mix its skills; the first reference wins. ``root``
                    # started empty, so an existing ``dest`` is an earlier bundle of
                    # this run under a name the filesystem folds together with this one
                    # (case, or Unicode normalization) that ``casefold`` did not catch.
                    failure = BundleFailure(
                        ref=ref,
                        reason="invalid",
                        detail="repeated bundle name; the first reference was kept",
                    )
                elif timed_out:
                    failure = BundleFailure(
                        ref=ref,
                        reason="source_unavailable",
                        detail="skipped: skills source timed out",
                    )
                else:
                    bundle, failure, timed_out = await _materialize_one(
                        source, ref, dest
                    )
                    if bundle is not None:
                        bundles.append(bundle)
            seen.add(ref.name.casefold())
            if failure is not None:
                failures.append(failure)
                record_bundle_failed(span, failure)
        _warn_duplicate_skill_names(bundles)
        result = SkillSet(source=source.name, bundles=bundles, failures=failures)
        record_bundles_resolved(span, result)
        if bundles:
            result.save(root)
        return result
    except BaseException:
        for bundle in bundles:
            _remove_tree(root / bundle.ref.name)
        try:
            (root / MANIFEST_FILE_NAME).unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Could not remove %s: %s", root / MANIFEST_FILE_NAME, e)
        raise


async def _materialize_one(
    source: SkillBundleSource, ref: SkillBundleRef, dest: Path
) -> tuple[SkillBundle | None, BundleFailure | None, bool]:
    """One bundle under the time budget: the bundle, or its failure and whether the budget ran out.

    A failed bundle's partial folder is removed, cancellation included.
    """
    deadline = asyncio.timeout(BUNDLE_RESOLVE_TIMEOUT_SECONDS)
    try:
        async with deadline:
            return await source.materialize(ref, dest), None, False
    except Exception as e:
        timed_out = deadline.expired()
        _remove_tree(dest)
        return None, _failure_for(ref, e, timed_out=timed_out), timed_out
    except BaseException:
        _remove_tree(dest)
        raise


async def _empty_set(
    destination: Path | None, source: SkillBundleSource | None
) -> SkillSet:
    """The set for an agent that binds no bundle: nothing fetched, no span, no temp folder.

    A caller ``destination`` that holds only an earlier load's bundles is
    cleared, so bundles the agent no longer binds do not stay readable; anything
    else in it is left alone. A caller-supplied source is closed.
    """
    if destination is not None:
        _prepare_destination(destination)
    source_name = _source_name(source)
    if source is not None:
        await _close_source(source)
    return SkillSet(source=source_name, bundles=[], failures=[])


def _unexpected_failure(refs: list[SkillBundleRef], error: Exception) -> SkillSet:
    """Every bundle reported ``source_unavailable`` after an error nothing else handled."""
    return SkillSet(
        source=configured_source_kind(),
        bundles=[],
        failures=[
            BundleFailure(
                ref=ref,
                reason="source_unavailable",
                detail=f"unexpected error: {error!r}",
            )
            for ref in refs
        ],
    )


def _source_name(source: SkillBundleSource | None) -> str:
    """The telemetry name of ``source``, or of the configured one when none was given."""
    return source.name if source is not None else configured_source_kind()


async def _close_source(source: SkillBundleSource) -> None:
    """Close ``source``; a failure is a warning, never a reason to fail the run."""
    try:
        await source.aclose()
    except Exception as e:
        logger.warning("Closing the skills source %s failed: %r", source.name, e)


def _fail_all(
    span: Span,
    source_name: str,
    refs: list[SkillBundleRef],
    *,
    reason: FailureReason,
    detail: str,
) -> SkillSet:
    """Report every bundle as skipped for one shared cause; nothing was materialized."""
    failures = [BundleFailure(ref=ref, reason=reason, detail=detail) for ref in refs]
    for failure in failures:
        record_bundle_failed(span, failure)
    result = SkillSet(source=source_name, bundles=[], failures=failures)
    record_bundles_resolved(span, result)
    return result


def _failure_for(
    ref: SkillBundleRef, error: Exception, *, timed_out: bool
) -> BundleFailure:
    if timed_out:
        return BundleFailure(
            ref=ref,
            reason="source_unavailable",
            detail=f"timed out after {BUNDLE_RESOLVE_TIMEOUT_SECONDS}s",
        )
    if isinstance(error, BundleSourceError):
        return BundleFailure(ref=ref, reason=error.reason, detail=error.detail)
    # A source bug must not take the run down.
    return BundleFailure(ref=ref, reason="source_unavailable", detail=repr(error))


def _prepare_destination(root: Path) -> str | None:
    """Make ``root`` ready for this run's bundles; why it cannot be, or ``None``.

    ``root`` may be missing, empty, or hold only what an earlier ``load_all``
    wrote there, which is removed first. Anything else is left untouched.
    """
    if root.is_symlink():
        return f"destination {root} is a symbolic link"
    if not root.exists():
        return None
    if not root.is_dir():
        return f"destination {root} is not a folder"
    try:
        if not any(root.iterdir()):
            return None
        previous = _previous_load(root)
        if previous is None:
            return f"destination {root} is not empty"
        logger.info("Removing the skill bundles an earlier load left in %s", root)
        for bundle in previous.bundles:
            _remove_tree(root / bundle.ref.name)
        (root / MANIFEST_FILE_NAME).unlink(missing_ok=True)
        if any(root.iterdir()):
            return f"destination {root} could not be cleared"
    except OSError as e:
        return f"destination {root} cannot be read: {e}"
    return None


def _previous_load(root: Path) -> SkillSet | None:
    """The earlier set whose manifest is in ``root``, when it accounts for everything there.

    Every folder and file under ``root`` must be the manifest or one it lists:
    a bundle folder, a skill folder, a skill file or a folder holding one. A
    missing or unreadable manifest, a symbolic link or any other entry gives
    ``None``, so nothing an earlier load did not write is ever removed.
    """
    try:
        previous = SkillSet.load(root)
    except ValueError:
        return None
    if previous is None:
        return None
    files = {MANIFEST_FILE_NAME}
    folders: set[str] = set()
    for bundle in previous.bundles:
        folders.add(bundle.ref.name)
        for skill in bundle.skills:
            skill_dir = PurePosixPath(bundle.ref.name, skill.name)
            folders.add(str(skill_dir))
            for name in skill.files:
                file = skill_dir / name
                files.add(str(file))
                folders.update(
                    str(parent)
                    for parent in file.parents
                    if parent != PurePosixPath(".")
                )
    for path in root.rglob("*"):
        if path.is_symlink():
            return None
        rel = path.relative_to(root).as_posix()
        if rel not in (folders if path.is_dir() else files):
            return None
    return previous


def _remove_tree(path: Path) -> None:
    """Delete a folder this call created; a warning when anything is left behind.

    A symlink is not followed: ``rmtree`` refuses it, so it stays.
    """
    shutil.rmtree(path, ignore_errors=True)
    if path.is_symlink() or path.exists():
        logger.warning("Could not remove %s", path)


def _warn_duplicate_skill_names(bundles: list[SkillBundle]) -> None:
    """Name collisions are legal (the prompt qualifies names) but worth a line in the job log."""
    seen: dict[str, str] = {}
    for bundle in bundles:
        for skill in bundle.skills:
            if skill.name in seen:
                logger.warning(
                    "Skill '%s' exists in bundles '%s' and '%s'; both are available "
                    "to the model as '%s/%s' and '%s/%s'",
                    skill.name,
                    seen[skill.name],
                    bundle.ref.name,
                    seen[skill.name],
                    skill.name,
                    bundle.ref.name,
                    skill.name,
                )
            seen[skill.name] = bundle.ref.name


def _run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run ``coro`` to completion from synchronous code.

    Uses ``asyncio.run`` when no event loop runs in this thread; otherwise runs it on a
    worker thread with a copy of the current context, so the resource-overwrite ContextVar
    (and the OpenTelemetry context) are visible to the coroutine.

    Args:
        coro: The coroutine to run; it is always consumed.

    Returns:
        The coroutine's result.

    Raises:
        BaseException: Whatever the coroutine raised.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    context = contextvars.copy_context()

    def run_in_context() -> T:
        return context.run(asyncio.run, coro)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="uipath-skills"
    ) as pool:
        try:
            future = pool.submit(run_in_context)
        except RuntimeError:
            # The interpreter is shutting down and no thread will run it.
            coro.close()
            raise
        return future.result()


__all__ = ["SkillsService"]
