"""Tests for picking the skill bundle source from ``UIPATH_SKILLS_SOURCE``."""

import logging
from pathlib import Path

import pytest

from uipath.platform.common import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.skills._sources import (
    BundleSourceError,
    LocalFolderBundleSource,
    OrchestratorBundleSource,
    get_bundle_source,
)
from uipath.platform.skills.skills import SkillBundleRef


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.delenv("UIPATH_SKILLS_SOURCE", raising=False)
    monkeypatch.delenv("UIPATH_SKILLS_LOCAL_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


@pytest.mark.parametrize("value", [None, "", "  ", " Orchestrator "])
def test_orchestrator_is_the_default(
    env: pytest.MonkeyPatch,
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    caplog: pytest.LogCaptureFixture,
    value: str | None,
) -> None:
    if value is not None:
        env.setenv("UIPATH_SKILLS_SOURCE", value)
    with caplog.at_level(logging.WARNING):
        source = get_bundle_source(config, execution_context)
    assert isinstance(source, OrchestratorBundleSource)
    assert source.name == "orchestrator"
    assert (source.config, source.execution_context) == (config, execution_context)
    assert not caplog.records


def test_orchestrator_reads_a_fresh_execution_context_when_given_none(
    env: pytest.MonkeyPatch,
) -> None:
    source = get_bundle_source(None, None)
    assert isinstance(source, OrchestratorBundleSource)
    assert source.config is None
    assert isinstance(source.execution_context, UiPathExecutionContext)


async def test_orchestrator_without_configuration_skips_the_bundle(
    env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = get_bundle_source(None, None)
    with pytest.raises(BundleSourceError, match="no UiPath configuration") as info:
        await source.materialize(SkillBundleRef(name="finance"), tmp_path / "d")
    assert info.value.reason == "source_unavailable"
    assert not (tmp_path / "d").exists()
    await source.aclose()


@pytest.mark.parametrize("value", ["local", " Local "])
def test_local_reads_skills_under_cwd(
    env: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    env.setenv("UIPATH_SKILLS_SOURCE", value)
    source = get_bundle_source(None, None)
    assert isinstance(source, LocalFolderBundleSource)
    assert source.root.resolve() == (tmp_path / "skills").resolve()


def test_the_local_root_can_be_set(env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env.setenv("UIPATH_SKILLS_SOURCE", "local")
    env.setenv("UIPATH_SKILLS_LOCAL_ROOT", str(tmp_path / "elsewhere"))
    source = get_bundle_source(None, None)
    assert isinstance(source, LocalFolderBundleSource)
    assert source.root == tmp_path / "elsewhere"


@pytest.mark.parametrize("value", ["s3", "mock"])
def test_an_unknown_value_falls_back_to_the_default_with_a_warning(
    env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, value: str
) -> None:
    env.setenv("UIPATH_SKILLS_SOURCE", value)
    with caplog.at_level(logging.WARNING):
        source = get_bundle_source(None, None)
    assert isinstance(source, OrchestratorBundleSource)
    assert repr(value) in caplog.text
