"""Tests for applying ``skillBundle`` resource overwrites to a bundle reference."""

import logging
from typing import Any

import pytest

from uipath.platform.common import ResourceOverwrite, ResourceOverwriteParser
from uipath.platform.common._bindings import GenericResourceOverwrite
from uipath.platform.skills import SkillBundleRef, VersionMode
from uipath.platform.skills._overwrites import apply_skill_bundle_overwrite


def _ctx(entries: dict[str, dict[str, Any]]) -> dict[str, ResourceOverwrite]:
    return {k: ResourceOverwriteParser.parse(k, v) for k, v in entries.items()}


def _entry(**fields: Any) -> dict[str, Any]:
    """A full overwrite entry: ``finance`` pinned to v3 in ``Shared/Skills``."""
    return {
        "name": "finance",
        "folderPath": "Shared/Skills",
        "versionMode": "pinned",
        "version": "3",
        **fields,
    }


def _pinned(**overrides: Any) -> SkillBundleRef:
    """A design-time ref: ``finance`` pinned to v3 in ``Shared/Skills``."""
    values: dict[str, Any] = {
        "name": "finance",
        "folderPath": "Shared/Skills",
        "versionMode": "pinned",
        "version": "3",
    }
    values.update(overrides)
    return SkillBundleRef.model_validate(values)


@pytest.mark.parametrize(
    ("entries", "version"),
    [
        (
            {
                "skillBundle.finance": _entry(version="1"),
                "skillBundle.finance.Shared/Skills": _entry(version="2"),
            },
            "2",
        ),
        ({"skillBundle.finance": _entry(version="5")}, "5"),
        ({"skillBundle.finance.Shared/Skills": _entry(version="6")}, "6"),
    ],
    ids=["folder-key-wins", "bare-key", "folder-key-alone"],
)
def test_the_most_specific_key_applies(
    entries: dict[str, dict[str, Any]], version: str
) -> None:
    out = apply_skill_bundle_overwrite(_pinned(), _ctx(entries))
    assert (out.folder_path, out.version) == ("Shared/Skills", version)


def test_a_dotted_bundle_name_gets_its_overwrite() -> None:
    ref = SkillBundleRef(name="my.bundle", version_mode=VersionMode.PINNED, version="1")
    out = apply_skill_bundle_overwrite(
        ref,
        _ctx({"skillBundle.my.bundle": _entry(name="my.bundle", version="4")}),
    )
    assert (out.name, out.folder_path, out.version) == (
        "my.bundle",
        "Shared/Skills",
        "4",
    )


def test_an_overwrite_replaces_everything_but_the_name() -> None:
    ref = _pinned()
    out = apply_skill_bundle_overwrite(
        ref,
        _ctx(
            {
                "skillBundle.finance": {
                    "name": "finance-eu",
                    "folderPath": "Prod",
                    "versionMode": "latest",
                },
                "process.Other": {"name": "x", "folderPath": "y"},
            }
        ),
    )
    assert (out.name, out.lookup_name, out.key) == (
        "finance",
        "finance-eu",
        "skillBundle.finance",
    )
    assert (out.folder_path, out.version_mode, out.version) == (
        "Prod",
        VersionMode.LATEST,
        None,
    )
    assert ref == _pinned()


def test_an_overwrite_matching_the_declared_ref_changes_nothing() -> None:
    out = apply_skill_bundle_overwrite(
        _pinned(), _ctx({"skillBundle.finance": _entry()})
    )
    assert out == _pinned()
    assert out.source_name is None


@pytest.mark.parametrize(
    "overwrites",
    [
        None,
        {},
        _ctx({"skillBundle.ops": _entry(name="ops", version="9")}),
        _ctx({"skillBundle.finance.Other": _entry(version="8")}),
        _ctx({"asset.finance": {"name": "B", "folderPath": "F"}}),
        {
            "skillBundle.finance": GenericResourceOverwrite(
                resource_type="asset", name="B", folder_path="F"
            )
        },
    ],
    ids=[
        "no-context",
        "empty",
        "other-bundle",
        "other-folder",
        "other-kind",
        "wrong-type-under-key",
    ],
)
def test_nothing_matching_returns_the_ref_itself(
    overwrites: dict[str, ResourceOverwrite] | None,
) -> None:
    ref = _pinned()
    assert apply_skill_bundle_overwrite(ref, overwrites) is ref


def test_a_folder_key_is_not_tried_for_a_ref_without_a_folder() -> None:
    ref = SkillBundleRef(name="finance")
    ows = _ctx({"skillBundle.finance.Shared/Skills": _entry(version="8")})
    assert apply_skill_bundle_overwrite(ref, ows) is ref


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (
            {"skillBundle.finance": _entry(name="../x")},
            "Ignoring invalid skillBundle overwrite 'skillBundle.finance' for "
            "'finance': Value error, a skill bundle name must be a single folder name",
        ),
        (
            {
                "skillBundle.finance.Shared/Skills": _entry(name="../x"),
                "skillBundle.finance": _entry(version="5"),
            },
            "Ignoring invalid skillBundle overwrite 'skillBundle.finance.Shared/Skills' "
            "for 'finance': Value error, a skill bundle name must be a single folder "
            "name; the less specific key 'skillBundle.finance' was not tried",
        ),
    ],
    ids=["unsafe-name", "invalid-folder-key"],
)
def test_an_invalid_overwrite_is_ignored_with_one_warning(
    caplog: pytest.LogCaptureFixture,
    entries: dict[str, dict[str, Any]],
    message: str,
) -> None:
    ref = _pinned(versionMode="latest", version=None)
    with caplog.at_level(logging.WARNING):
        assert apply_skill_bundle_overwrite(ref, _ctx(entries)) is ref
    assert [r.getMessage() for r in caplog.records] == [message]
