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
            "versionMode": "pinned",
            "version": "7",
            "isEnabled": True,
        },
    )
    assert (ow.name, ow.folder_path, ow.version_mode, ow.version) == (
        "finance-eu",
        "Prod/Skills",
        "pinned",
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


@pytest.mark.parametrize("version", [None, "4", ""])
def test_latest_carries_no_version(version: str | None) -> None:
    entry = {"name": "finance", "folderPath": "F", "versionMode": "latest"}
    ow = _parse("skillBundle.finance", {**entry, "version": version})
    assert (ow.version_mode, ow.version) == ("latest", None)


_FULL = {"name": "finance", "folderPath": "F", "versionMode": "pinned", "version": "7"}


@pytest.mark.parametrize(
    "missing_or_blank",
    [
        {"name": None},
        {"folderPath": None},
        {"versionMode": None},
        {"version": None},
        {"name": ""},
        {"folderPath": "  "},
        {"versionMode": ""},
        {"version": " "},
        {"versionMode": "cached"},
    ],
    ids=[
        "no-name",
        "no-folder",
        "no-version-mode",
        "pinned-without-version",
        "blank-name",
        "blank-folder",
        "blank-version-mode",
        "pinned-with-blank-version",
        "unknown-version-mode",
    ],
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
        ({"version": None}, "Value error, a pinned skill bundle needs a version"),
        ({"folderPath": None}, "folderPath: Field required"),
        (
            {"versionMode": "cached"},
            "versionMode: Input should be 'pinned' or 'latest'",
        ),
    ],
    ids=["pinned-without-version", "no-folder", "unknown-version-mode"],
)
def test_the_problem_names_the_field_and_the_rule(
    change: dict[str, Any], problem: str
) -> None:
    entry = {k: v for k, v in {**_FULL, **change}.items() if v is not None}
    assert _parse("skillBundle.finance", entry).problem == problem


def test_a_malformed_entry_of_another_kind_is_still_rejected() -> None:
    with pytest.raises(ValidationError):
        ResourceOverwriteParser.parse("asset.A", {"name": "B"})


def test_overwrites_and_references_share_one_version_mode() -> None:
    annotation = SkillBundleResourceOverwrite.model_fields["version_mode"].annotation
    assert annotation is VersionMode
    assert skills.VersionMode is VersionMode
    assert _parse("skillBundle.finance", _FULL).version_mode is VersionMode.PINNED


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
    with pytest.raises(ValidationError, match="needs a version"):
        SkillBundleResourceOverwrite(
            resource_type="skillBundle",
            name="finance",
            folder_path="Shared/Skills",
            version_mode=VersionMode.PINNED,
        )


def test_an_invalid_entry_keeps_only_its_problem() -> None:
    ow = SkillBundleResourceOverwrite.invalid("versionMode: bad")
    assert (ow.problem, ow.name, ow.folder_path, ow.version) == (
        "versionMode: bad",
        "",
        "",
        None,
    )
