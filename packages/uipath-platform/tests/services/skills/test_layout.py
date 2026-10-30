"""Tests for the on-disk bundle layout helpers."""

import logging
from pathlib import Path

import pytest

from uipath.platform.skills._layout import (
    find_skill_md,
    is_plain_name,
    iter_skill_files,
    read_bundle_version,
)


@pytest.mark.parametrize(
    ("content", "expected", "warns"),
    [
        (b'{"version": "3"}', "3", False),
        (b'{"version": 7}', "7", False),
        (b'{"version": null}', "local", False),
        (b'{"version": ""}', "local", False),
        (b"{}", "local", False),
        (None, "local", False),
        (b"{not json", "local", True),
        (b"[1, 2]", "local", True),
        (b'{"version": "\xff"}', "local", True),
    ],
)
def test_read_bundle_version(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    content: bytes | None,
    expected: str,
    warns: bool,
) -> None:
    if content is not None:
        (tmp_path / "bundle.json").write_bytes(content)
    with caplog.at_level(logging.WARNING):
        assert read_bundle_version(tmp_path) == expected
    assert ("bundle.json" in caplog.text) is warns


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("invoice-triage", True),
        ("my skill", True),
        ("v1.2", True),
        ("", False),
        (".", False),
        ("..", False),
        (".hidden", False),
        ("a/b", False),
        ("a" + chr(92) + "b", False),
        ("C:", False),
        ("a" + chr(0) + "b", False),
    ],
)
def test_is_plain_name(name: str, expected: bool) -> None:
    assert is_plain_name(name) is expected


def _is_case_sensitive(folder: Path) -> bool:
    probe = folder / "case-probe"
    probe.write_text("x", encoding="utf-8")
    try:
        return not (folder / "CASE-PROBE").exists()
    finally:
        probe.unlink()


def test_find_skill_md_matches_any_case(tmp_path: Path) -> None:
    for rel in ["ok/SKILL.md", "lower/skill.md", "mixed/Skill.MD", ".hidden/SKILL.md"]:
        (tmp_path / rel).parent.mkdir()
        (tmp_path / rel).write_text("x", encoding="utf-8")
    (tmp_path / "empty").mkdir()
    (tmp_path / "nested" / "SKILL.md").mkdir(parents=True)
    (tmp_path / "file.md").write_text("x", encoding="utf-8")
    found = {p.name: find_skill_md(p) for p in tmp_path.iterdir()}
    assert {k: v.name for k, v in found.items() if v is not None} == {
        "ok": "SKILL.md",
        "lower": "skill.md",
        "mixed": "Skill.MD",
    }


def test_find_skill_md_prefers_the_exact_name(tmp_path: Path) -> None:
    if not _is_case_sensitive(tmp_path):
        pytest.skip("the file system cannot hold two spellings of SKILL.md")
    for name in ["skill.md", "SKILL.md", "Skill.md"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
    found = find_skill_md(tmp_path)
    assert found is not None and found.name == "SKILL.md"


@pytest.mark.parametrize("skill_md", ["SKILL.md", "skill.md"])
def test_iter_skill_files_puts_skill_md_first_and_skips_hidden(
    tmp_path: Path, skill_md: str
) -> None:
    for rel in [skill_md, "a.md", "ref/b.md", ".secret", ".git/config", "ref/.c"]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    assert iter_skill_files(tmp_path) == [skill_md, "a.md", "ref/b.md"]
