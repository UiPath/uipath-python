"""Tests for the ``skillBundle`` resource overwrite type and its parsing."""

from typing import Any, get_args

import pytest
from pydantic import ValidationError

from uipath.platform.common import (
    ConnectionResourceOverwrite,
    EntityResourceOverwrite,
    GenericResourceOverwrite,
    ResourceOverwriteParser,
    SkillBundleResourceOverwrite,
)
from uipath.platform.skills import VersionMode


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
    assert "isEnabled" not in ow.model_dump(by_alias=True)


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
def test_an_incomplete_entry_is_rejected(missing_or_blank: dict[str, Any]) -> None:
    entry = {**_FULL, **missing_or_blank}
    entry = {k: v for k, v in entry.items() if v is not None}
    with pytest.raises(ValidationError):
        ResourceOverwriteParser.parse("skillBundle.finance", entry)


def test_the_version_mode_literal_matches_skills_version_mode() -> None:
    annotation = SkillBundleResourceOverwrite.model_fields["version_mode"].annotation
    assert set(get_args(annotation)) == {mode.value for mode in VersionMode}


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
