"""Fixtures shared by the skills tests."""

import shutil
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

FIXTURES = Path(__file__).parents[1] / "tests_data" / "skills"
"""``tests/services/tests_data/skills``: bundles ``finance`` (v3) and ``ops`` (v1), both with ``vendor-lookup``."""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A writable copy of the fixture bundles at ``tmp_path/skills``."""
    shutil.copytree(FIXTURES, tmp_path / "skills")
    return tmp_path / "skills"


@pytest.fixture
def exporter(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Capture the spans the skills package emits."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        "uipath.platform.skills._telemetry._tracer", provider.get_tracer("test")
    )
    return exporter
