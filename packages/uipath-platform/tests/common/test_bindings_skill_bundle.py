"""Tests for the ``skillBundle`` resource overwrite type and its parsing."""

from typing import Any

import pytest
from pydantic import ValidationError

from uipath.platform import skills
from uipath.platform.common import (
    ConnectionResourceOverwrite,
    EntityResourceOverwrite,
    GenericResourceOverwrite,
    ResourceOverwriteParser,
    SkillBundleResourceOverwrite,
    VersionMode,
)


def _parse(key: str, entry: dict[str, Any]) -> SkillBundleResourceOverwrite:
    ow = ResourceOverwriteParser.parse(key, entry)
    assert isinstance(ow, SkillBundleResourceOverwrite)
    return ow


def test_a_full_entry_parses_with_its_identifiers() -> None:
    ow = _parse(
        "skillBundle.finance",
        {
            "name": "finance-eu",
            "folderPath": "Prod/Skills",
            "version": "7",
            "isEnabled": True,
        },
    )
    assert (ow.name, ow.folder_path, ow.version) == (
        "finance-eu",
        "Prod/Skills",
        "7",
    )
    assert (ow.resource_identifier, ow.folder_identifier) == (
        "finance-eu",
        "Prod/Skills",
    )
    assert ow.problem is None
    dumped = ow.model_dump(by_alias=True)
    assert "isEnabled" not in dumped
    assert "problem" not in dumped


_DIGEST = "sha256:" + "c0" * 32


@pytest.mark.parametrize("version", ["latest", "LATEST", "7", "reviewed", _DIGEST])
def test_the_version_is_kept_as_sent(version: str) -> None:
    entry = {"name": "finance", "folderPath": "F", "version": version}
    ow = _parse("skillBundle.finance", entry)
    assert (ow.version, ow.problem) == (version, None)


@pytest.mark.parametrize("version", [None, "", " "], ids=["missing", "empty", "blank"])
def test_an_entry_without_a_version_is_valid(version: str | None) -> None:
    # The shape of a debug overwrite inside a solution: name and folder only.
    entry = {"name": "finance", "folderPath": "F"}
    if version is not None:
        entry["version"] = version
    ow = _parse("skillBundle.finance", entry)
    assert (ow.version, ow.problem) == (None, None)


def test_a_version_mode_field_is_ignored() -> None:
    entry = {"name": "finance", "folderPath": "F", "versionMode": "pinned"}
    ow = _parse("skillBundle.finance", entry)
    assert (ow.version, ow.problem) == (None, None)
    assert "versionMode" not in ow.model_dump(by_alias=True)


_FULL = {"name": "finance", "folderPath": "F", "version": "7"}


@pytest.mark.parametrize(
    "missing_or_blank",
    [
        {"name": None},
        {"folderPath": None},
        {"name": ""},
        {"folderPath": "  "},
    ],
    ids=["no-name", "no-folder", "blank-name", "blank-folder"],
)
def test_an_incomplete_entry_parses_with_its_problem(
    missing_or_blank: dict[str, Any],
) -> None:
    # Kept, not rejected, so the loader fails the bundle instead of loading
    # the declared binding.
    entry = {**_FULL, **missing_or_blank}
    entry = {k: v for k, v in entry.items() if v is not None}
    ow = _parse("skillBundle.finance", entry)
    assert ow.problem
    assert "\n" not in ow.problem
    assert (ow.name, ow.folder_path, ow.version) == ("", "", None)


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"folderPath": None}, "folderPath: Field required"),
        (
            {"name": " "},
            "name: Value error, a skillBundle overwrite needs a non-blank name "
            "and folderPath",
        ),
    ],
    ids=["no-folder", "blank-name"],
)
def test_the_problem_names_the_field_and_the_rule(
    change: dict[str, Any], problem: str
) -> None:
    entry = {k: v for k, v in {**_FULL, **change}.items() if v is not None}
    assert _parse("skillBundle.finance", entry).problem == problem


def test_a_malformed_entry_of_another_kind_is_still_rejected() -> None:
    with pytest.raises(ValidationError):
        ResourceOverwriteParser.parse("asset.A", {"name": "B"})


def test_skills_and_common_export_one_version_mode() -> None:
    assert skills.VersionMode is VersionMode


@pytest.mark.parametrize(
    ("key", "entry", "kind"),
    [
        ("asset.A", {"name": "B", "folderPath": "F"}, GenericResourceOverwrite),
        ("entity.E", {"name": "E2", "folderPath": "F"}, EntityResourceOverwrite),
        (
            "connection.C",
            {"connectionId": "c-2", "folderKey": "fk"},
            ConnectionResourceOverwrite,
        ),
    ],
)
def test_other_kinds_still_parse_to_their_own_type(
    key: str, entry: dict[str, Any], kind: type
) -> None:
    assert isinstance(ResourceOverwriteParser.parse(key, entry), kind)


@pytest.mark.parametrize(
    ("key", "known"),
    [
        ("skillBundle.finance", True),
        ("skillBundle.finance.Shared/Skills", True),
        ("asset.A", True),
        ("entity.E", True),
        ("connection.c", True),
        ("weird.X", False),
        ("", False),
    ],
)
def test_the_parser_knows_the_kinds_it_has_a_model_for(key: str, known: bool) -> None:
    assert ResourceOverwriteParser.knows(key) is known


def test_constructing_an_invalid_entry_directly_raises() -> None:
    with pytest.raises(ValidationError, match="non-blank name"):
        SkillBundleResourceOverwrite(
            resource_type="skillBundle", name=" ", folder_path="Shared/Skills"
        )


def test_an_invalid_entry_keeps_only_its_problem() -> None:
    ow = SkillBundleResourceOverwrite.invalid("folderPath: bad")
    assert (ow.problem, ow.name, ow.folder_path, ow.version) == (
        "folderPath: bad",
        "",
        "",
        None,
    )
