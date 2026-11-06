"""Tests for ``SkillsService``: resolving bound skill bundles into a ``SkillSet``."""

import asyncio
import concurrent.futures
import inspect
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from uipath.platform.common import (
    ResourceOverwrite,
    ResourceOverwriteParser,
    UiPathApiConfig,
    UiPathExecutionContext,
)
from uipath.platform.common._bindings import _resource_overwrites
from uipath.platform.skills import (
    SkillBundle,
    SkillBundleRef,
    SkillSet,
    VersionMode,
    _skills_service,
    _sources,
)
from uipath.platform.skills._constants import MANIFEST_FILE_NAME
from uipath.platform.skills._skills_service import (
    SkillBundleLoadError,
    SkillsService,
    _run_sync,
)
from uipath.platform.skills._sources import BundleSourceError, LocalFolderBundleSource

# --- Helpers ---


def _ref(name: str, **kwargs: Any) -> SkillBundleRef:
    return SkillBundleRef(name=name, **kwargs)


def _ctx(entries: dict[str, dict[str, Any]]) -> dict[str, ResourceOverwrite]:
    return {k: ResourceOverwriteParser.parse(k, v) for k, v in entries.items()}


def _attrs(span_or_event: Any) -> Mapping[str, Any]:
    return span_or_event.attributes or {}


def _only_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    [span] = exporter.get_finished_spans()
    return span


def _failed_events(span: ReadableSpan) -> list[tuple[str, str, str]]:
    return [
        (
            _attrs(e)["skill.bundle.name"],
            _attrs(e)["skill.reason"],
            _attrs(e)["skill.detail"],
        )
        for e in span.events
        if e.name == "skill.bundle.failed"
    ]


def _temp_skill_roots(tmp_path: Path) -> set[Path]:
    """The ``uipath-skills-*`` folders the service created under ``tmp_path``."""
    return set(tmp_path.glob("uipath-skills-*"))


def _write_stale(dest: Path) -> Path:
    """A leftover bundle file and manifest from an earlier run."""
    stale = dest / "stale" / "x.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("x", encoding="utf-8")
    (dest / MANIFEST_FILE_NAME).write_text("{}", encoding="utf-8")
    return stale


class FakeSource:
    """A source that writes a partial bundle, then raises or stalls per bundle name."""

    name = "fake"

    def __init__(
        self,
        errors: dict[str, BaseException] | None = None,
        delays: dict[str, float] | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.errors = errors or {}
        self.delays = delays or {}
        self.close_error = close_error
        self.closed = False
        self.requested: list[str] = []
        self.dests: list[Path] = []
        self.started = asyncio.Event()

    async def materialize(self, ref: SkillBundleRef, dest: Path) -> SkillBundle:
        self.requested.append(ref.lookup_name)
        self.dests.append(dest)
        dest.mkdir(parents=True)
        (dest / "partial.txt").write_text("x", encoding="utf-8")
        self.started.set()
        if ref.name in self.delays:
            await asyncio.sleep(self.delays[ref.name])
        if ref.name in self.errors:
            raise self.errors[ref.name]
        return SkillBundle(ref=ref, version="1", skills=[])

    async def aclose(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error

    @property
    def root(self) -> Path:
        [root] = {d.parent for d in self.dests}
        return root


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
    tests_data_path: Path,
    tmp_path: Path,
) -> SkillsService:
    # Owned temp roots land under tmp_path, so leak checks see only this test.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("UIPATH_SKILLS_SOURCE", "local")
    monkeypatch.setenv("UIPATH_SKILLS_LOCAL_ROOT", str(tests_data_path / "skills"))
    return SkillsService(config=config, execution_context=execution_context)


# --- Resolving ---


async def test_bundles_are_resolved_into_an_owned_temp_root(
    service: SkillsService, exporter: InMemorySpanExporter
) -> None:
    result = await service.load_all_async(
        [_ref("finance"), _ref("ops", version_mode=VersionMode.PINNED, version="1")]
    )
    root = result.root
    assert root is not None
    assert root.name.startswith("uipath-skills-")
    assert result.owns_root is True
    assert (result.source, result.failures) == ("local", [])
    assert [b.label for b in result.bundles] == ["finance v3", "ops v1"]
    assert (root / "finance" / "invoice-triage" / "reference" / "vendors.md").is_file()
    saved = SkillSet.load(root)
    assert saved is not None
    assert saved.bundles == result.bundles
    span = _only_span(exporter)
    assert span.name == "Skill bundles resolved"
    assert (_attrs(span)["skill.bundle.count"], _attrs(span)["skill.count"]) == (2, 3)
    result.cleanup()
    assert not root.exists()


async def test_the_context_overwrite_is_applied(service: SkillsService) -> None:
    token = _resource_overwrites.set(
        _ctx(
            {
                "skillBundle.finance": {
                    "name": "ops",
                    "folderPath": "Shared/Skills",
                    "versionMode": "latest",
                }
            }
        )
    )
    try:
        result = await service.load_all_async([_ref("finance")])
    finally:
        _resource_overwrites.reset(token)
    try:
        [bundle] = result.bundles
        assert (bundle.ref.name, bundle.ref.lookup_name) == ("finance", "ops")
        assert result.names() == ["finance/vendor-lookup"]
        assert result.root is not None
        assert not (result.root / "ops").exists()
    finally:
        result.cleanup()


async def test_a_caller_destination_is_reset_and_kept(
    service: SkillsService, tmp_path: Path
) -> None:
    dest = tmp_path / "run" / "skills"
    stale = _write_stale(dest)
    result = await service.load_all_async([_ref("finance")], destination=dest)
    assert (result.root, result.owns_root) == (dest, False)
    assert not stale.exists()
    loaded = SkillSet.load(dest)
    assert loaded is not None
    assert loaded.names() == result.names()
    result.cleanup()
    assert (dest / MANIFEST_FILE_NAME).is_file()


async def test_a_missing_bundle_is_reported_and_the_rest_continue(
    service: SkillsService, exporter: InMemorySpanExporter
) -> None:
    result = await service.load_all_async([_ref("ghost"), _ref("finance")])
    try:
        assert [b.ref.name for b in result.bundles] == ["finance"]
        assert [(f.ref.name, f.reason) for f in result.failures] == [
            ("ghost", "not_found")
        ]
        assert result.root is not None
        assert not (result.root / "ghost").exists()
        assert [e.name for e in _only_span(exporter).events] == [
            "skill.bundle.failed",
            "skill.bundle.resolved",
        ]
    finally:
        result.cleanup()


async def test_duplicate_skill_names_are_reported(
    service: SkillsService, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        result = await service.load_all_async([_ref("finance"), _ref("ops")])
    result.cleanup()
    assert (
        "Skill 'vendor-lookup' exists in bundles 'finance' and 'ops'; both are "
        "available to the model as 'finance/vendor-lookup' and 'ops/vendor-lookup'"
    ) in caplog.text


# --- No references ---


async def test_no_refs_gives_an_empty_set_without_a_span(
    service: SkillsService,
    exporter: InMemorySpanExporter,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    source = FakeSource(close_error=RuntimeError("close"))
    with caplog.at_level(logging.WARNING):
        result = await service.load_all_async([], source=source)
    assert result == SkillSet(source="fake", bundles=[], failures=[])
    assert result.root is None
    assert (source.closed, source.requested) == (True, [])
    assert "Closing the skills source fake failed" in caplog.text
    assert exporter.get_finished_spans() == ()
    assert _temp_skill_roots(tmp_path) == set()


async def test_no_refs_still_resets_a_caller_destination(
    service: SkillsService, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    dest = tmp_path / "skills"
    stale = _write_stale(dest)
    result = await service.load_all_async([], destination=dest)
    assert not stale.exists()
    assert not (dest / MANIFEST_FILE_NAME).exists()
    assert (result.bundles, result.root) == ([], None)
    # A destination that is a file cannot be reset; it is left alone.
    assert not dest.exists()
    dest.write_text("not a folder", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        result = await service.load_all_async([], destination=dest)
    assert result.root is None
    assert f"Could not remove {dest}" in caplog.text
    assert dest.read_text(encoding="utf-8") == "not a folder"


# --- Failures ---


async def test_a_failed_bundle_leaves_no_partial_folder(
    service: SkillsService,
) -> None:
    source = FakeSource(
        errors={
            "x": RuntimeError("boom"),
            "y": BundleSourceError("over budget", reason="too_large"),
        }
    )
    result = await service.load_all_async(
        [_ref("x"), _ref("y"), _ref("z")], source=source
    )
    try:
        assert [(f.ref.name, f.reason, f.detail) for f in result.failures] == [
            ("x", "source_unavailable", repr(RuntimeError("boom"))),
            ("y", "too_large", "over budget"),
        ]
        assert result.root is not None
        assert sorted(p.name for p in result.root.iterdir()) == [
            MANIFEST_FILE_NAME,
            "z",
        ]
        assert source.closed
    finally:
        result.cleanup()


async def test_nothing_resolving_removes_the_owned_temp_root(
    service: SkillsService,
) -> None:
    source = FakeSource(errors={"x": RuntimeError("boom")})
    result = await service.load_all_async([_ref("x")], source=source)
    assert (result.bundles, result.root, result.owns_root) == ([], None, False)
    assert not source.root.exists()
    assert result.prompt_section() == ""


async def test_a_slow_bundle_times_out_and_the_rest_are_skipped(
    service: SkillsService,
    monkeypatch: pytest.MonkeyPatch,
    exporter: InMemorySpanExporter,
) -> None:
    monkeypatch.setattr(_skills_service, "BUNDLE_RESOLVE_TIMEOUT_SECONDS", 0.05)
    source = FakeSource(delays={"slow": 1})
    result = await service.load_all_async(
        [_ref("fast"), _ref("slow"), _ref("after")], source=source
    )
    try:
        assert [b.ref.name for b in result.bundles] == ["fast"]
        assert source.requested == ["fast", "slow"]
        assert result.root is not None
        assert not (result.root / "slow").exists()
        assert _failed_events(_only_span(exporter)) == [
            ("slow", "source_unavailable", "timed out after 0.05s"),
            ("after", "source_unavailable", "skipped: skills source timed out"),
        ]
    finally:
        result.cleanup()


async def test_the_local_source_honours_the_time_budget(
    service: SkillsService,
    root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_skills_service, "BUNDLE_RESOLVE_TIMEOUT_SECONDS", 0.05)
    real = shutil.copyfile

    def slow(src: Path, dst: Path) -> object:
        time.sleep(0.2)
        return real(src, dst)

    monkeypatch.setattr(f"{_sources.__name__}.shutil.copyfile", slow)
    dest = tmp_path / "run"
    result = await service.load_all_async(
        [_ref("finance"), _ref("ops")],
        destination=dest,
        source=LocalFolderBundleSource(root),
    )
    assert result.bundles == []
    assert [(f.ref.name, f.detail) for f in result.failures] == [
        ("finance", "timed out after 0.05s"),
        ("ops", "skipped: skills source timed out"),
    ]
    # The stopped copy wrote nothing after the bundle folder was removed.
    await asyncio.sleep(0.3)
    assert not (dest / "finance").exists()


async def test_a_timeout_raised_by_the_source_does_not_skip_the_rest(
    service: SkillsService,
) -> None:
    source = FakeSource(errors={"a": TimeoutError("upstream")})
    result = await service.load_all_async([_ref("a"), _ref("b")], source=source)
    try:
        assert source.requested == ["a", "b"]
        assert [b.ref.name for b in result.bundles] == ["b"]
        assert [(f.ref.name, f.detail) for f in result.failures] == [
            ("a", repr(TimeoutError("upstream")))
        ]
    finally:
        result.cleanup()


async def test_a_source_that_cannot_be_built_fails_every_bundle(
    service: SkillsService,
    monkeypatch: pytest.MonkeyPatch,
    exporter: InMemorySpanExporter,
    tmp_path: Path,
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("no platform config")

    monkeypatch.setattr(_skills_service, "get_bundle_source", broken)
    monkeypatch.setenv("UIPATH_SKILLS_SOURCE", " Orchestrator ")
    dest = tmp_path / "skills"
    stale = _write_stale(dest)
    result = await service.load_all_async(
        [_ref("finance"), _ref("ops")], destination=dest
    )
    # The destination is reset before the source is built.
    assert not stale.exists()
    assert (result.bundles, result.root, result.source) == ([], None, "orchestrator")
    for failure in result.failures:
        assert failure.reason == "source_unavailable"
        assert failure.detail.startswith("skills source unavailable: RuntimeError(")
    span = _only_span(exporter)
    assert _attrs(span)["skill.source"] == "orchestrator"
    assert [e.name for e in span.events] == ["skill.bundle.failed"] * 2


async def test_a_temp_folder_that_cannot_be_created_skips_every_bundle(
    service: SkillsService,
    monkeypatch: pytest.MonkeyPatch,
    exporter: InMemorySpanExporter,
) -> None:
    def full(*args: Any, **kwargs: Any) -> str:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(tempfile, "mkdtemp", full)
    source = FakeSource()
    result = await service.load_all_async([_ref("finance"), _ref("ops")], source=source)
    assert (result.bundles, result.root) == ([], None)
    assert [(f.ref.name, f.reason) for f in result.failures] == [
        ("finance", "source_unavailable"),
        ("ops", "source_unavailable"),
    ]
    assert "cannot create the skills folder" in result.failures[0].detail
    assert (source.closed, source.requested) == (True, [])
    span = _only_span(exporter)
    assert _attrs(span)["skill.source"] == "fake"
    assert [e.name for e in span.events] == ["skill.bundle.failed"] * 2


async def test_a_failing_aclose_keeps_the_result(
    service: SkillsService, caplog: pytest.LogCaptureFixture
) -> None:
    source = FakeSource(close_error=RuntimeError("close"))
    with caplog.at_level(logging.WARNING):
        result = await service.load_all_async([_ref("x")], source=source)
    try:
        assert [b.ref.name for b in result.bundles] == ["x"]
        assert "Closing the skills source fake failed" in caplog.text
    finally:
        result.cleanup()


@pytest.mark.parametrize(
    "second",
    [_ref("x", version_mode=VersionMode.PINNED, version="2"), _ref("X")],
    ids=["same-name", "case-variant"],
)
async def test_a_repeated_bundle_name_is_invalid(
    service: SkillsService, second: SkillBundleRef
) -> None:
    source = FakeSource()
    result = await service.load_all_async([_ref("x"), second], source=source)
    try:
        assert source.requested == ["x"]
        assert [b.ref.name for b in result.bundles] == ["x"]
        assert [(f.ref, f.reason, f.detail) for f in result.failures] == [
            (second, "invalid", "repeated bundle name; the first reference was kept")
        ]
        assert result.root is not None
        assert (result.root / "x" / "partial.txt").is_file()
    finally:
        result.cleanup()


async def test_a_bundle_folder_that_already_exists_is_a_repeat(
    service: SkillsService,
) -> None:
    class AliasingSource(FakeSource):
        """Writes bundle ``x`` and, as a folded-name filesystem would, ``y`` too."""

        async def materialize(self, ref: SkillBundleRef, dest: Path) -> SkillBundle:
            bundle = await super().materialize(ref, dest)
            (dest.parent / "y").mkdir()
            return bundle

    source = AliasingSource()
    result = await service.load_all_async([_ref("x"), _ref("y")], source=source)
    try:
        assert source.requested == ["x"]
        assert [(f.ref.name, f.reason) for f in result.failures] == [("y", "invalid")]
    finally:
        result.cleanup()


# --- The root ---


async def test_a_destination_that_cannot_be_reset_fails_every_bundle(
    service: SkillsService, tmp_path: Path, exporter: InMemorySpanExporter
) -> None:
    dest = tmp_path / "skills"
    dest.write_text("not a folder", encoding="utf-8")
    source = FakeSource()
    result = await service.load_all_async(
        [_ref("x"), _ref("y")], destination=dest, source=source
    )
    assert (result.bundles, result.root) == ([], None)
    assert (source.requested, source.closed) == ([], True)
    assert _failed_events(_only_span(exporter)) == [
        ("x", "invalid", "stale files could not be removed"),
        ("y", "invalid", "stale files could not be removed"),
    ]
    assert dest.read_text(encoding="utf-8") == "not a folder"


async def test_a_symlinked_destination_is_not_followed(
    service: SkillsService, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "skills"
    _link_directory(target, link)
    result = await service.load_all_async([_ref("finance")], destination=link)
    assert (result.bundles, result.root) == ([], None)
    assert [(f.reason, f.detail) for f in result.failures] == [
        ("invalid", "stale files could not be removed")
    ]
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert os.path.lexists(link)


def _link_directory(target: Path, link: Path) -> None:
    """A symlink, or on Windows without the symlink privilege a junction."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError) as e:
        if sys.platform != "win32":
            pytest.skip(f"cannot create a directory symlink here: {e}")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


async def test_an_unexpected_error_leaves_no_skills_and_does_not_raise(
    service: SkillsService,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken_save(self: SkillSet, skills_dir: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(SkillSet, "save", broken_save)
    source = FakeSource()
    with caplog.at_level(logging.ERROR):
        result = await service.load_all_async(
            [_ref("finance"), _ref("ops")], source=source
        )
    assert (result.bundles, result.root) == ([], None)
    assert [(f.ref.name, f.reason, f.detail) for f in result.failures] == [
        ("finance", "source_unavailable", "unexpected error: OSError('disk full')"),
        ("ops", "source_unavailable", "unexpected error: OSError('disk full')"),
    ]
    assert "continuing without skills" in caplog.text
    assert source.closed
    assert not source.root.exists()


async def test_cancellation_removes_the_partial_bundle_and_propagates(
    service: SkillsService,
) -> None:
    source = FakeSource(delays={"x": 10})
    task = asyncio.create_task(service.load_all_async([_ref("x")], source=source))
    await source.started.wait()
    [dest] = source.dests
    assert (dest / "partial.txt").is_file()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not source.root.exists()
    assert source.closed


# --- load_async ---


async def test_load_async_returns_one_bundle(
    service: SkillsService, tmp_path: Path
) -> None:
    dest = tmp_path / "skills"
    pinned = await service.load_async(
        "ops", version_mode="pinned", version="1", destination=dest
    )
    assert [b.label for b in pinned.bundles] == ["ops v1"]
    assert (pinned.root, pinned.owns_root) == (dest, False)
    latest = await service.load_async("finance")
    assert latest.bundles[0].ref.version_mode is VersionMode.LATEST
    assert latest.owns_root is True
    assert latest.root is not None
    assert latest.root.parent == tmp_path
    latest.cleanup()
    assert _temp_skill_roots(tmp_path) == set()


async def test_load_async_raises_for_a_missing_bundle_and_leaves_no_temp_root(
    service: SkillsService, tmp_path: Path
) -> None:
    with pytest.raises(SkillBundleLoadError) as info:
        await service.load_async("ghost", folder_path="Shared/Skills")
    assert _temp_skill_roots(tmp_path) == set()
    failure = info.value.failure
    assert (failure.reason, failure.ref.name, failure.ref.folder_path) == (
        "not_found",
        "ghost",
        "Shared/Skills",
    )
    assert str(info.value).startswith("skill bundle 'ghost' not_found: ")


async def test_load_async_rejects_a_bad_reference(service: SkillsService) -> None:
    with pytest.raises(ValueError, match="needs a version"):
        await service.load_async("finance", version_mode="pinned")
    with pytest.raises(ValueError):
        await service.load_async("finance", version_mode="newest")


# --- Sync twins ---


def test_the_sync_twins_run_without_an_event_loop(
    service: SkillsService, tmp_path: Path
) -> None:
    result = service.load_all([_ref("finance")])
    assert result.names() == ["finance/invoice-triage", "finance/vendor-lookup"]
    result.cleanup()
    one = service.load("finance", destination=tmp_path / "skills")
    assert [b.label for b in one.bundles] == ["finance v3"]
    with pytest.raises(SkillBundleLoadError):
        service.load("ghost")
    assert _temp_skill_roots(tmp_path) == set()


async def test_load_all_from_a_running_loop_sees_the_context_overwrite(
    service: SkillsService,
) -> None:
    token = _resource_overwrites.set(
        _ctx(
            {
                "skillBundle.finance": {
                    "name": "ops",
                    "folderPath": "Shared/Skills",
                    "versionMode": "latest",
                }
            }
        )
    )
    try:
        result = service.load_all([_ref("finance")])
    finally:
        _resource_overwrites.reset(token)
    try:
        assert result.bundles[0].ref.lookup_name == "ops"
    finally:
        result.cleanup()


async def test_run_sync_from_a_loop_uses_another_thread_and_re_raises() -> None:
    async def where() -> int:
        return threading.get_ident()

    async def boom() -> None:
        raise ValueError("inside")

    assert _run_sync(where()) != threading.get_ident()
    failing = boom()
    with pytest.raises(ValueError, match="inside"):
        _run_sync(failing)


def test_run_sync_without_a_loop_stays_on_this_thread() -> None:
    async def where() -> int:
        return threading.get_ident()

    assert _run_sync(where()) == threading.get_ident()


async def test_run_sync_closes_the_coroutine_when_nothing_can_run_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(self: Any, fn: Any, /, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("cannot schedule new futures after interpreter shutdown")

    monkeypatch.setattr(concurrent.futures.ThreadPoolExecutor, "submit", refuse)

    async def never_runs() -> None:
        return None

    coro = never_runs()
    with pytest.raises(RuntimeError, match="interpreter shutdown"):
        _run_sync(coro)
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
