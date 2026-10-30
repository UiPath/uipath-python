"""Tests for the local-folder skill bundle source."""

import asyncio
import logging
import shutil
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from uipath.platform.skills import _sources
from uipath.platform.skills._layout import iter_skill_files
from uipath.platform.skills._sources import BundleSourceError, LocalFolderBundleSource
from uipath.platform.skills.skills import SkillBundle, SkillBundleRef

HEALTHY = ["invoice-triage", "vendor-lookup"]
COPYFILE = f"{_sources.__name__}.shutil.copyfile"


def _add_skill(root: Path, name: str, content: bytes) -> None:
    (root / "finance" / name).mkdir()
    (root / "finance" / name / "SKILL.md").write_bytes(content)


async def _materialize(root: Path, dest: Path, **ref: object) -> SkillBundle:
    values = {"name": "finance", **ref}
    return await LocalFolderBundleSource(root).materialize(
        SkillBundleRef.model_validate(values), dest
    )


async def _names(root: Path, dest: Path) -> list[str]:
    return [s.name for s in (await _materialize(root, dest)).skills]


# --- What is copied ---


async def test_a_bundle_is_copied_with_its_version_and_descriptions(
    root: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "run" / "skills" / "finance"
    bundle = await _materialize(root, dest, versionMode="pinned", version="3")
    assert bundle.version == "3"
    assert [s.name for s in bundle.skills] == HEALTHY
    triage = bundle.skills[0]
    assert triage.files == ["SKILL.md", "reference/vendors.md"]
    assert triage.description.startswith("Classify an incoming invoice")
    assert (dest / "invoice-triage" / "reference" / "vendors.md").is_file()
    assert not (dest / "bundle.json").exists()


async def test_a_pinned_version_the_folder_lacks_loads_anyway_with_a_warning(
    root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        bundle = await _materialize(
            root, tmp_path / "d", versionMode="pinned", version="99"
        )
    assert bundle.version == "3"
    assert "pinned to version 99" in caplog.text


async def test_a_source_name_retargets_the_lookup(root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "d"
    bundle = await _materialize(root, dest, sourceName="ops")
    assert (bundle.ref.name, bundle.version) == ("finance", "1")
    assert [s.name for s in bundle.skills] == ["vendor-lookup"]
    assert bundle.skills[0].description.startswith("(ops copy)")
    assert not (dest / "invoice-triage").exists()


async def test_only_skill_folders_and_visible_files_are_copied(
    root: Path, tmp_path: Path
) -> None:
    finance = root / "finance"
    (finance / "notes").mkdir()
    (finance / "notes" / "readme.txt").write_text("x")
    _add_skill(root, ".hidden", b"---\ndescription: x\n---\n")
    triage = finance / "invoice-triage"
    (triage / ".git").mkdir()
    (triage / ".git" / "config").write_text("x")
    (triage / "reference" / ".notes.md").write_text("x")
    dest = tmp_path / "d"
    bundle = await _materialize(root, dest)
    assert [s.name for s in bundle.skills] == HEALTHY
    assert bundle.skills[0].files == ["SKILL.md", "reference/vendors.md"]
    assert sorted(p.name for p in dest.iterdir()) == HEALTHY
    assert not (dest / "invoice-triage" / ".git").exists()


async def test_skills_are_ordered_by_code_point(root: Path, tmp_path: Path) -> None:
    # Windows path ordering would ignore case.
    _add_skill(root, "Zeta", b"---\ndescription: z\n---\n")
    _add_skill(root, "alpha", b"---\ndescription: a\n---\n")
    assert await _names(root, tmp_path / "d") == ["Zeta", "alpha", *HEALTHY]


async def test_a_bundle_without_a_usable_skill_still_gets_its_folder(
    root: Path, tmp_path: Path
) -> None:
    (root / "empty").mkdir()
    bundle = await _materialize(root, tmp_path / "d", name="empty")
    assert bundle.skills == []
    assert (tmp_path / "d").is_dir()


async def test_copied_files_are_writable(root: Path, tmp_path: Path) -> None:
    source_file = root / "finance" / "vendor-lookup" / "SKILL.md"
    source_file.chmod(0o444)
    try:
        await _materialize(root, tmp_path / "d")
    finally:
        source_file.chmod(0o644)
    (tmp_path / "d" / "vendor-lookup" / "SKILL.md").write_text("ok", encoding="utf-8")


async def test_a_lower_case_skill_md_is_copied_as_skill_md(
    root: Path, tmp_path: Path
) -> None:
    (root / "finance" / "lower").mkdir()
    (root / "finance" / "lower" / "skill.md").write_bytes(
        b"---\ndescription: lower\n---\n"
    )
    (root / "finance" / "lower" / "notes.md").write_text("x", encoding="utf-8")
    dest = tmp_path / "d"
    bundle = await _materialize(root, dest)
    lower = next(s for s in bundle.skills if s.name == "lower")
    assert (lower.description, lower.files) == ("lower", ["SKILL.md", "notes.md"])
    assert sorted(p.name for p in (dest / "lower").iterdir()) == [
        "SKILL.md",
        "notes.md",
    ]


async def test_a_second_spelling_of_skill_md_is_left_out(
    root: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A case-sensitive file system can hold SKILL.md and skill.md side by
    # side; fake that listing so the test runs on Windows and macOS too.
    def with_a_second_spelling(skill_dir: Path) -> list[str]:
        files = iter_skill_files(skill_dir)
        return [files[0], "skill.md", *files[1:]]

    monkeypatch.setattr(f"{_sources.__name__}.iter_skill_files", with_a_second_spelling)
    with caplog.at_level(logging.WARNING):
        bundle = await _materialize(root, tmp_path / "d")
    for skill in bundle.skills:
        assert skill.files[0] == "SKILL.md"
        assert "skill.md" not in skill.files
    assert "the skill already has SKILL.md" in caplog.text


# --- What is skipped ---


async def test_an_oversized_file_is_skipped(
    root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (root / "finance" / "invoice-triage" / "big.bin").write_bytes(
        b"0" * (512 * 1024 + 1)
    )
    with caplog.at_level(logging.WARNING):
        bundle = await _materialize(root, tmp_path / "d")
    assert "big.bin" not in bundle.skills[0].files
    assert not (tmp_path / "d" / "invoice-triage" / "big.bin").exists()
    assert "Skipping invoice-triage/big.bin in bundle 'finance'" in caplog.text


@pytest.mark.parametrize(
    "skill_md",
    [
        b"---\ndescription: x\n---\n" + b"0" * (512 * 1024),
        b"---\ndescription: caf\xe9\n---\n",
    ],
    ids=["oversized", "not-utf8"],
)
async def test_an_unusable_skill_md_skips_only_that_skill(
    root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture, skill_md: bytes
) -> None:
    _add_skill(root, "bad", skill_md)
    with caplog.at_level(logging.WARNING):
        assert await _names(root, tmp_path / "d") == HEALTHY
    assert not (tmp_path / "d" / "bad").exists()
    assert "Skipping skill 'bad' in bundle 'finance'" in caplog.text


# --- Errors ---


async def test_an_unknown_bundle_is_not_found(root: Path, tmp_path: Path) -> None:
    with pytest.raises(BundleSourceError) as info:
        await _materialize(root, tmp_path / "d", name="ghost")
    assert info.value.reason == "not_found"
    assert not (tmp_path / "d").exists()


async def test_a_bundle_over_the_size_limit_is_too_large(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_sources, "MAX_BUNDLE_BYTES", 10)
    with pytest.raises(BundleSourceError) as info:
        await _materialize(root, tmp_path / "d")
    assert info.value.reason == "too_large"


@pytest.mark.parametrize("failing", ["iterdir", "copyfile"])
async def test_a_filesystem_error_is_source_unavailable(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    def denied(*args: object) -> Iterator[Path]:
        raise PermissionError(13, "Permission denied")

    if failing == "iterdir":
        monkeypatch.setattr(Path, "iterdir", denied)
    else:
        monkeypatch.setattr(COPYFILE, denied)
    with pytest.raises(BundleSourceError) as info:
        await _materialize(root, tmp_path / "d")
    assert info.value.reason == "source_unavailable"
    assert "finance" in info.value.detail
    assert isinstance(info.value.__cause__, PermissionError)


# --- The worker thread ---


async def test_the_copy_runs_off_the_event_loop(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = shutil.copyfile

    def slow(src: Path, dst: Path) -> object:
        time.sleep(0.1)
        return real(src, dst)

    monkeypatch.setattr(COPYFILE, slow)
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    try:
        assert await _names(root, tmp_path / "d") == HEALTHY
    finally:
        task.cancel()
    # Three files at 0.1 s each; a blocked loop would have ticked once.
    assert ticks >= 5


async def test_cancelling_stops_the_copy_before_the_next_file(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = shutil.copyfile
    started = threading.Event()
    copied: list[str] = []

    def slow(src: Path, dst: Path) -> object:
        started.set()
        time.sleep(0.2)
        copied.append(Path(dst).name)
        return real(src, dst)

    monkeypatch.setattr(COPYFILE, slow)
    task = asyncio.create_task(_names(root, tmp_path / "d"))
    await asyncio.to_thread(started.wait)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The file in flight finished before materialize returned; no other started.
    assert len(copied) == 1
    await asyncio.sleep(0.3)
    assert len(copied) == 1
