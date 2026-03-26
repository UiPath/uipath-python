#!/usr/bin/env python3
"""Tests for detect_publishable_packages.py."""

import json
import os
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

from detect_publishable_packages import (
    get_all_packages,
    main,
    version_exists_on_pypi,
)


@pytest.fixture()
def packages_dir(tmp_path: Path):
    """Create a fake packages directory with pyproject.toml files."""
    pkg_a = tmp_path / "packages" / "pkg-a"
    pkg_a.mkdir(parents=True)
    (pkg_a / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "1.0.0"\n'
    )

    pkg_b = tmp_path / "packages" / "pkg-b"
    pkg_b.mkdir(parents=True)
    (pkg_b / "pyproject.toml").write_text(
        '[project]\nname = "pkg-b"\nversion = "2.0.0"\n'
    )

    # Directory without pyproject.toml — should be ignored
    no_toml = tmp_path / "packages" / "no-toml"
    no_toml.mkdir(parents=True)

    # Directory with pyproject.toml missing version — should be ignored
    no_version = tmp_path / "packages" / "no-version"
    no_version.mkdir(parents=True)
    (no_version / "pyproject.toml").write_text("[project]\n")

    return tmp_path


class TestGetAllPackages:
    def test_detects_packages(self, packages_dir: Path):
        with mock.patch(
            "detect_publishable_packages.Path",
            side_effect=lambda p: packages_dir / p if p == "packages" else Path(p),
        ):
            packages = get_all_packages()

        assert len(packages) == 2
        names = {p["name"] for p in packages}
        assert names == {"pkg-a", "pkg-b"}

    def test_returns_correct_fields(self, packages_dir: Path):
        with mock.patch(
            "detect_publishable_packages.Path",
            side_effect=lambda p: packages_dir / p if p == "packages" else Path(p),
        ):
            packages = get_all_packages()

        pkg_a = next(p for p in packages if p["name"] == "pkg-a")
        assert pkg_a["directory"] == "pkg-a"
        assert pkg_a["version"] == "1.0.0"


class TestVersionExistsOnPypi:
    def test_returns_true_when_version_exists(self):
        mock_response = mock.MagicMock()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            assert version_exists_on_pypi("some-package", "1.0.0") is True

    def test_returns_false_when_404(self):
        error = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None  # type: ignore[arg-type]
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            assert version_exists_on_pypi("some-package", "9.9.9") is False

    def test_returns_false_on_other_http_error(self):
        error = urllib.error.HTTPError(
            url="", code=500, msg="Server Error", hdrs=None, fp=None  # type: ignore[arg-type]
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            assert version_exists_on_pypi("some-package", "1.0.0") is False

    def test_returns_true_on_network_error(self):
        with mock.patch(
            "urllib.request.urlopen", side_effect=ConnectionError("no network")
        ):
            assert version_exists_on_pypi("some-package", "1.0.0") is True


class TestMain:
    def test_publishes_new_versions_only(self, packages_dir: Path):
        def mock_pypi(name: str, version: str) -> bool:
            # pkg-a 1.0.0 exists, pkg-b 2.0.0 does not
            return name == "pkg-a" and version == "1.0.0"

        with (
            mock.patch(
                "detect_publishable_packages.Path",
                side_effect=lambda p: packages_dir / p if p == "packages" else Path(p),
            ),
            mock.patch(
                "detect_publishable_packages.version_exists_on_pypi",
                side_effect=mock_pypi,
            ),
        ):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                output_file = f.name

            try:
                os.environ["GITHUB_OUTPUT"] = output_file
                main()

                with open(output_file) as f:
                    content = f.read()

                assert "packages=" in content
                assert "count=" in content

                # Parse the output
                lines = content.strip().split("\n")
                packages_line = next(l for l in lines if l.startswith("packages="))
                count_line = next(l for l in lines if l.startswith("count="))

                packages = json.loads(packages_line.split("=", 1)[1])
                count = int(count_line.split("=", 1)[1])

                assert packages == ["pkg-b"]
                assert count == 1
            finally:
                os.unlink(output_file)
                os.environ.pop("GITHUB_OUTPUT", None)

    def test_nothing_to_publish(self, packages_dir: Path):
        with (
            mock.patch(
                "detect_publishable_packages.Path",
                side_effect=lambda p: packages_dir / p if p == "packages" else Path(p),
            ),
            mock.patch(
                "detect_publishable_packages.version_exists_on_pypi",
                return_value=True,
            ),
        ):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                output_file = f.name

            try:
                os.environ["GITHUB_OUTPUT"] = output_file
                main()

                with open(output_file) as f:
                    content = f.read()

                packages_line = next(
                    l for l in content.strip().split("\n") if l.startswith("packages=")
                )
                count_line = next(
                    l for l in content.strip().split("\n") if l.startswith("count=")
                )

                assert json.loads(packages_line.split("=", 1)[1]) == []
                assert int(count_line.split("=", 1)[1]) == 0
            finally:
                os.unlink(output_file)
                os.environ.pop("GITHUB_OUTPUT", None)
