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
from pathlib import Path
from typing import Any, TypeVar

from opentelemetry.trace import Span

from uipath.platform.common import (
    BaseService,
    FolderContext,
    UiPathApiConfig,
    UiPathExecutionContext,
)

from ._constants import BUNDLE_RESOLVE_TIMEOUT_SECONDS
from ._overwrites import apply_skill_bundle_overwrite, current_overwrites
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
    VersionMode,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TEMP_PREFIX = "uipath-skills-"
"""Prefix of the temp folder ``load_all`` creates when no destination is given."""


class SkillBundleLoadError(Exception):
    """``load``/``load_async`` could not resolve the one bundle it was asked for.

    Raised for every ``BundleFailure.reason``, not only ``not_found``.
    """

    def __init__(self, failure: BundleFailure) -> None:
        """Wrap the failure ``load_all`` would have reported.

        Args:
            failure: The bundle that could not be resolved, and why.
        """
        super().__init__(
            f"skill bundle '{failure.ref.name}' {failure.reason}: {failure.detail}"
        )
        self.failure = failure
        """The reported failure: ``ref``, ``reason`` and ``detail``."""


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
        reference first. Every bundle gets ``BUNDLE_RESOLVE_TIMEOUT_SECONDS`` of
        wall clock; after the first timeout the remaining bundles are skipped
        without being tried. A bundle that fails is reported in
        ``SkillSet.failures`` and as a ``skill.bundle.failed`` event on the
        ``Skill bundles resolved`` span; nothing here fails the run, though
        cancellation still propagates. The folder the bundles land in holds
        only this run's bundles plus the manifest: whatever was in
        ``destination`` before is removed first, on every call, before the
        source is even built. After an unexpected error a caller
        ``destination`` may hold partial files; an owned temp root is always
        removed.

        Args:
            refs: The bundles the agent is bound to. With none, nothing is
                fetched, no span is emitted and the set has no ``root``; a
                caller ``destination`` is still reset, so an agent that unbinds
                every bundle does not keep last run's files.
            destination: The folder to write into; it is reset first and the set
                does not own it, so ``SkillSet.cleanup`` leaves it alone. By
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
            destination: The folder to write into, reset first and not owned by
                the set; by default an owned temp folder.
            source: Where bundles come from; by default the one
                ``UIPATH_SKILLS_SOURCE`` selects. It is closed before this
                returns.

        Returns:
            The resolved bundles and the failures.
        """
        return _run_sync(
            self.load_all_async(refs, destination=destination, source=source)
        )

    async def load_async(
        self,
        name: str,
        *,
        folder_path: str | None = None,
        version_mode: str | VersionMode = VersionMode.LATEST,
        version: str | None = None,
        destination: Path | None = None,
    ) -> SkillSet:
        """Resolve and download one bundle, raising when it cannot be.

        The same resolution as ``load_all_async`` for a single reference,
        overwrites included. A bundle is addressed by name and folder path.
        The set holds exactly one bundle; use ``read()`` for its files and
        ``cleanup()`` when done (a caller-supplied ``destination`` is left
        alone).

        Args:
            name: The bundle name, as the agent declares it.
            folder_path: The bundle's folder path, or ``None`` for the job's
                folder.
            version_mode: ``"pinned"`` or ``"latest"`` (a ``VersionMode`` or its
                value).
            version: The version to pin; required for ``pinned``, dropped for
                ``latest``.
            destination: The folder to write into, reset first; by default a
                temp folder.

        Returns:
            A set with the one resolved bundle, its ``root`` set.

        Raises:
            SkillBundleLoadError: The bundle could not be resolved; its
                ``failure`` says why (``not_found``, ``version_not_found``,
                ``forbidden``, ``invalid``, ``too_large`` or
                ``source_unavailable``). Nothing is left on disk for an owned
                temp root.
            ValueError: ``version_mode`` is not a known mode, or the reference
                is invalid (a name that is not one plain folder name, or
                ``pinned`` without a ``version``).
        """
        ref = SkillBundleRef(
            name=name,
            folder_path=folder_path,
            version_mode=VersionMode(version_mode),
            version=version,
        )
        result = await self.load_all_async([ref], destination=destination)
        if result.failures:
            # With one reference and a failure there is no bundle, so an owned
            # temp root is already gone; this keeps that true should it change.
            result.cleanup()
            raise SkillBundleLoadError(result.failures[0])
        return result

    def load(
        self,
        name: str,
        *,
        folder_path: str | None = None,
        version_mode: str | VersionMode = VersionMode.LATEST,
        version: str | None = None,
        destination: Path | None = None,
    ) -> SkillSet:
        """Resolve and download one bundle; see ``load_async``.

        ``load_async`` is preferred. This runs it to completion, on a worker
        thread when an event loop is already running in this thread; called
        from a running loop, it blocks the caller for up to the per-bundle
        budget. A bundle is addressed by name and folder path. The set holds
        exactly one bundle; use ``read()`` for its files and ``cleanup()``
        when done (a caller-supplied ``destination`` is left alone).

        Args:
            name: The bundle name, as the agent declares it.
            folder_path: The bundle's folder path, or ``None`` for the job's
                folder.
            version_mode: ``"pinned"`` or ``"latest"``.
            version: The version to pin; required for ``pinned``.
            destination: The folder to write into, reset first; by default a
                temp folder.

        Returns:
            A set with the one resolved bundle, its ``root`` set.

        Raises:
            SkillBundleLoadError: As ``load_async`` raises it.
            ValueError: As ``load_async`` raises it.
        """
        return _run_sync(
            self.load_async(
                name,
                folder_path=folder_path,
                version_mode=version_mode,
                version=version,
                destination=destination,
            )
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
        """Reset ``root``, build the source when none was given, materialize, and close the source.

        A caller-supplied ``source`` is closed on every path, a failed reset
        included.
        """
        try:
            # The folder is reserved for materialized bundles, so nothing from
            # an earlier run (a bundle no longer bound, a stale manifest) may
            # survive. This runs before the source is built, so the reset
            # happens even when the source cannot be.
            if not _remove_tree(root):
                return _fail_all(
                    span,
                    _source_name(source),
                    refs,
                    reason="invalid",
                    detail="stale files could not be removed",
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
    """Materialize ``refs`` in order into the reset ``root``, then write the manifest.

    The manifest is written only when at least one bundle resolved; the caller
    decides what happens to ``root`` otherwise.
    """
    overwrites = current_overwrites()
    bundles: list[SkillBundle] = []
    failures: list[BundleFailure] = []
    seen: set[str] = set()
    timed_out = False
    for declared in refs:
        ref = apply_skill_bundle_overwrite(declared, overwrites)
        dest = root / ref.name
        failure: BundleFailure | None = None
        if ref.name.casefold() in seen or dest.exists():
            # A second reference would write into the first one's folder and
            # shadow or mix its skills; the first reference wins. ``root`` was
            # reset, so an existing ``dest`` is an earlier bundle of this run
            # under a name the filesystem folds together with this one (case,
            # or Unicode normalization) that ``casefold`` did not catch.
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
            bundle, failure, timed_out = await _materialize_one(source, ref, dest)
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

    A caller ``destination`` is still reset, so last run's bundles and manifest
    do not survive an agent that unbinds every bundle; a failed reset is logged
    by ``_remove_tree``. A caller-supplied source is closed.
    """
    if destination is not None:
        _remove_tree(destination)
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


def _remove_tree(path: Path) -> bool:
    """Delete ``path``; ``False``, with a warning, when anything is left behind.

    A symlink is not followed: ``rmtree`` refuses it, so it stays and the
    caller reports the folder as unusable instead of emptying its target.
    """
    shutil.rmtree(path, ignore_errors=True)
    # A dangling junction on Windows is neither a symlink nor existing here, so
    # it counts as removed; the source's later mkdir then fails on it and is
    # reported as source_unavailable.
    if path.is_symlink() or path.exists():
        logger.warning("Could not remove %s", path)
        return False
    return True


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


__all__ = ["SkillBundleLoadError", "SkillsService"]
