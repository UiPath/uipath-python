from typing import Iterator, Optional, Tuple

import pytest

from uipath.platform.common._bindings import (
    GenericResourceOverwrite,
    _resource_overwrites,
    resource_override,
)

Folder = Tuple[str, Optional[str], Optional[str]]


@resource_override(resource_type="asset")
def retrieve(
    name: str, *, folder_key: Optional[str] = None, folder_path: Optional[str] = None
) -> Folder:
    return name, folder_key, folder_path


@resource_override(resource_type="asset")
async def retrieve_async(
    name: str, *, folder_key: Optional[str] = None, folder_path: Optional[str] = None
) -> Folder:
    return name, folder_key, folder_path


@pytest.fixture
def asset_overwrite() -> Iterator[None]:
    overwrite = GenericResourceOverwrite(
        resource_type="asset", name="ApiKey EU", folder_path="Finance/EU"
    )
    token = _resource_overwrites.set({"asset.ApiKey": overwrite})
    try:
        yield
    finally:
        _resource_overwrites.reset(token)


def test_bound_folder_replaces_a_folder_key(asset_overwrite: None) -> None:
    # Left beside the bound path, the key would name a second folder, which
    # header_folder() refuses.
    assert retrieve("ApiKey", folder_key="callers-key") == (
        "ApiKey EU",
        None,
        "Finance/EU",
    )


async def test_bound_folder_replaces_a_folder_key_async(asset_overwrite: None) -> None:
    assert await retrieve_async("ApiKey", folder_key="callers-key") == (
        "ApiKey EU",
        None,
        "Finance/EU",
    )


def test_folder_key_kept_without_a_matching_overwrite(asset_overwrite: None) -> None:
    assert retrieve("Other", folder_key="callers-key") == (
        "Other",
        "callers-key",
        None,
    )


def test_other_folder_parameters_are_left_alone() -> None:
    # A method whose overwrite targets a differently named folder (as Action
    # Center's app_folder_path) keeps its own folder_key.
    @resource_override(resource_type="app", folder_identifier="app_folder_path")
    def create(
        name: str,
        *,
        app_folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Folder:
        return name, folder_key, app_folder_path

    overwrite = GenericResourceOverwrite(
        resource_type="app", name="Approval EU", folder_path="Apps/EU"
    )
    token = _resource_overwrites.set({"app.Approval": overwrite})
    try:
        assert create("Approval", folder_key="task-folder") == (
            "Approval EU",
            "task-folder",
            "Apps/EU",
        )
    finally:
        _resource_overwrites.reset(token)
