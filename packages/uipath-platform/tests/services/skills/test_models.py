"""Tests for skill bundle models and the skills manifest."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pydantic import ValidationError

from uipath.platform.skills import (
    BundleFailure,
    InvokedBy,
    Skill,
    SkillBundle,
    SkillBundleRef,
    SkillSet,
    VersionMode,
)
from uipath.platform.skills._constants import MANIFEST_FILE_NAME

BACKSLASH = chr(92)
NUL = chr(0)
UNSAFE_NAMES = ["", ".", "..", "a/b", "a" + BACKSLASH + "b", "c:", ".hidden"]
UNSAFE_NAMES += ["a" + NUL + "b"]


def _fixture_set(root: Path | None, *, owns_root: bool = False) -> SkillSet:
    """The two fixture bundles as a set; ``root`` is where they were copied to."""
    finance = SkillBundle(
        ref=SkillBundleRef(
            name="finance", version_mode=VersionMode.PINNED, version="3"
        ),
        version="3",
        skills=[
            Skill(
                name="invoice-triage",
                description="Triage invoices",
                files=["SKILL.md", "reference/vendors.md"],
            ),
            Skill(name="vendor-lookup", description="Look up\n  a vendor "),
        ],
    )
    ops = SkillBundle(
        ref=SkillBundleRef(name="ops"),
        version="1",
        skills=[
            Skill(
                name="vendor-lookup",
                description="Ops vendor lookup",
                files=["SKILL.md"],
            )
        ],
    )
    return SkillSet(
        source="local", bundles=[finance, ops], root=root, owns_root=owns_root
    )


# --- SkillBundleRef ---


def test_a_ref_parses_camel_case_and_defaults_to_latest() -> None:
    ref = SkillBundleRef.model_validate(
        {"name": "finance", "folderPath": "Shared/Skills", "version": "3"}
    )
    assert (ref.folder_path, ref.version_mode, ref.version) == (
        "Shared/Skills",
        VersionMode.LATEST,
        None,
    )
    assert (ref.key, ref.lookup_name) == ("skillBundle.finance", "finance")


@pytest.mark.parametrize(
    "values",
    [
        {"name": "finance", "versionMode": "pinned"},
        *({"name": n} for n in [*UNSAFE_NAMES, " finance", MANIFEST_FILE_NAME]),
        {"name": "finance", "sourceName": "a/b"},
    ],
)
def test_an_invalid_ref_is_rejected(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SkillBundleRef.model_validate(values)


# --- Skill and SkillBundle ---


@pytest.mark.parametrize("name", UNSAFE_NAMES)
def test_a_skill_name_must_be_one_folder(name: str) -> None:
    with pytest.raises(ValidationError, match="single folder name"):
        Skill(name=name, description="d")


@pytest.mark.parametrize(
    "path",
    [
        "",
        "../../../secret.txt",
        "reference/../SKILL.md",
        "reference" + BACKSLASH + "vendors.md",
        ".hidden/notes.md",
        "/etc/passwd",
        "reference//vendors.md",
        "c:/vendors.md",
        "reference/a" + NUL + "b.md",
    ],
)
def test_a_skill_file_must_stay_inside_the_skill_folder(path: str) -> None:
    with pytest.raises(ValidationError, match="escapes the skill folder"):
        Skill(name="invoice-triage", description="d", files=["SKILL.md", path])


def test_a_bundle_has_a_virtual_root_and_a_label() -> None:
    bundle = SkillBundle(ref=SkillBundleRef(name="finance"), version="3", skills=[])
    assert (bundle.virtual_root, bundle.label) == ("/skills/finance/", "finance v3")


# --- Lookup and prompt ---


def test_names_find_and_skill_at_keep_same_named_skills_apart() -> None:
    skills = _fixture_set(root=None)
    finance, ops = skills.bundles
    assert skills.names() == [
        "finance/invoice-triage",
        "finance/vendor-lookup",
        "ops/vendor-lookup",
    ]
    assert skills.find("finance/vendor-lookup") == (finance, finance.skills[1])
    assert skills.find("ops/vendor-lookup") == (ops, ops.skills[0])
    for missing in ["finance/nope", "nope/vendor-lookup", "vendor-lookup", ""]:
        assert skills.find(missing) is None
    assert skills.skill_at("/skills/ops/vendor-lookup/SKILL.md") == (
        ops,
        ops.skills[0],
    )
    # A relative path is read from the root, as a virtual filesystem does.
    assert skills.skill_at("skills/finance/vendor-lookup/SKILL.md") == (
        finance,
        finance.skills[1],
    )
    for path in [
        "/skills/finance/nope/SKILL.md",
        "/skills/finance/invoice-triage/reference/vendors.md",
        "/notes.md",
    ]:
        assert skills.skill_at(path) is None


def test_the_prompt_section_lists_every_skill_on_one_line() -> None:
    section = _fixture_set(root=None).prompt_section()
    lines = section.splitlines()
    assert lines[0] == "## Skills"
    assert "`<bundle>/<skill>`" in section
    assert lines[-3:] == [
        "- **finance/invoice-triage** (bundle v3): Triage invoices",
        "- **finance/vendor-lookup** (bundle v3): Look up a vendor",
        "- **ops/vendor-lookup** (bundle v1): Ops vendor lookup",
    ]


def test_the_prompt_section_is_empty_without_skills() -> None:
    hollow = SkillBundle(ref=SkillBundleRef(name="hollow"), version="2", skills=[])
    assert SkillSet(source="local", bundles=[]).prompt_section() == ""
    assert SkillSet(source="local", bundles=[hollow]).prompt_section() == ""


# --- Manifest ---


def test_the_manifest_round_trips_without_the_root(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    failure = BundleFailure(
        ref=SkillBundleRef(name="missing"), reason="not_found", detail="404"
    )
    manifest = _fixture_set(root=skills_dir, owns_root=True)
    manifest.failures = [failure]
    manifest.save(skills_dir)

    raw = (skills_dir / MANIFEST_FILE_NAME).read_bytes()
    assert b"\r" not in raw
    data = json.loads(raw)
    # The layout the advanced harness reads (uipath-agents-python#829).
    assert set(data) == {"source", "bundles", "failures"}
    assert data["bundles"][0]["ref"] == {
        "name": "finance",
        "folderPath": None,
        "versionMode": "pinned",
        "version": "3",
        "sourceName": None,
    }
    assert data["bundles"][0]["skills"][0] == {
        "name": "invoice-triage",
        "description": "Triage invoices",
        "files": ["SKILL.md", "reference/vendors.md"],
    }
    loaded = SkillSet.load(skills_dir)
    assert loaded is not None
    assert (loaded.bundles, loaded.failures) == (manifest.bundles, [failure])
    assert (loaded.root, loaded.owns_root) == (skills_dir, False)


def test_load_ignores_root_keys_inside_the_manifest(tmp_path: Path) -> None:
    _fixture_set(root=None).save(tmp_path)
    path = tmp_path / MANIFEST_FILE_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(
        json.dumps({**data, "root": "/elsewhere", "owns_root": True}), encoding="utf-8"
    )
    loaded = SkillSet.load(tmp_path)
    assert loaded is not None
    assert (loaded.root, loaded.owns_root) == (tmp_path, False)


def test_load_without_a_manifest_or_with_a_bad_one(tmp_path: Path) -> None:
    assert SkillSet.load(tmp_path) is None
    (tmp_path / MANIFEST_FILE_NAME).write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        SkillSet.load(tmp_path)


# --- read ---


def test_read_returns_a_listed_file_without_a_span(
    root: Path, exporter: InMemorySpanExporter, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        text = _fixture_set(root).read("finance/invoice-triage", "reference/vendors.md")
    expected = root / "finance" / "invoice-triage" / "reference" / "vendors.md"
    assert text == expected.read_text(encoding="utf-8")
    assert exporter.get_finished_spans() == ()
    assert caplog.text == ""


@pytest.mark.parametrize("invoked_by", ["model", "user"])
def test_reading_skill_md_records_one_load_span(
    root: Path, exporter: InMemorySpanExporter, invoked_by: InvokedBy
) -> None:
    _fixture_set(root).save(root)
    loaded = SkillSet.load(root)
    assert loaded is not None
    text = loaded.read("ops/vendor-lookup", invoked_by=invoked_by)
    assert text.startswith("---\nname: vendor-lookup\n")
    [span] = exporter.get_finished_spans()
    assert span.name == "Skill load - ops/vendor-lookup"
    attributes = dict(span.attributes or {})
    assert attributes["skill.version"] == "1"
    assert attributes["skill.invoked_by"] == invoked_by
    assert attributes["skill.bytes"] == len(text.encode("utf-8"))


def test_read_drops_a_bom_and_replaces_undecodable_bytes(
    root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    skill_md = root / "ops" / "vendor-lookup" / "SKILL.md"
    skill_md.write_bytes(b"\xef\xbb\xbf---\nname: vendor-lookup\n---\n# V\n")
    vendors = root / "finance" / "invoice-triage" / "reference" / "vendors.md"
    vendors.write_bytes(b"ACME \xff Corp\n")
    skills = _fixture_set(root)
    assert skills.read("ops/vendor-lookup") == "---\nname: vendor-lookup\n---\n# V\n"
    with caplog.at_level(logging.WARNING):
        text = skills.read("finance/invoice-triage", "reference/vendors.md")
    assert text == "ACME \ufffd Corp\n"
    assert "not valid UTF-8" in caplog.text


@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("finance/nope", "SKILL.md"),
        ("nope/vendor-lookup", "SKILL.md"),
        # bundle.json exists one level up, but the skill does not list it.
        ("finance/invoice-triage", "../bundle.json"),
        # On disk, but finance/vendor-lookup lists no files at all.
        ("finance/vendor-lookup", "SKILL.md"),
    ],
)
def test_read_rejects_an_unknown_skill_or_an_unlisted_file(
    root: Path, name: str, path: str
) -> None:
    skills = _fixture_set(root)
    with pytest.raises(KeyError):
        skills.read(name, path)


# --- cleanup ---


def test_cleanup_removes_only_an_owned_root(tmp_path: Path) -> None:
    owned, supplied = tmp_path / "owned", tmp_path / "supplied"
    (owned / "finance").mkdir(parents=True)
    supplied.mkdir()
    owner = SkillSet(source="local", bundles=[], root=owned, owns_root=True)
    borrower = SkillSet(source="local", bundles=[], root=supplied)
    gone = SkillSet(source="local", bundles=[], root=tmp_path / "gone", owns_root=True)
    for skills in (owner, borrower, gone, owner):
        skills.cleanup()
    assert not owned.exists()
    assert supplied.is_dir()
    for skills in (owner, borrower, gone):
        assert (skills.root, skills.owns_root) == (None, False)


def test_read_without_a_root_raises_and_records_nothing(
    root: Path, exporter: InMemorySpanExporter
) -> None:
    manifest_only = _fixture_set(root=None)
    with pytest.raises(RuntimeError, match="not materialized"):
        manifest_only.read("finance/invoice-triage")
    skills = _fixture_set(root, owns_root=True)
    skills.cleanup()
    assert not root.exists()
    with pytest.raises(RuntimeError, match="cleaned up"):
        skills.read("finance/invoice-triage")
    assert exporter.get_finished_spans() == ()


def test_cleanup_warns_when_the_root_cannot_be_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def refuse(path: object, *args: object, **kwargs: object) -> None:
        raise OSError("busy")

    monkeypatch.setattr(shutil, "rmtree", refuse)
    skills = SkillSet(source="local", bundles=[], root=tmp_path, owns_root=True)
    with caplog.at_level(logging.WARNING):
        skills.cleanup()
    assert "busy" in caplog.text
    assert tmp_path.is_dir()
    assert (skills.root, skills.owns_root) == (None, False)
