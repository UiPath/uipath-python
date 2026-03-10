#!/usr/bin/env python3
"""Tests for check_version_uniqueness.py."""

import os
import urllib.error
from unittest import mock

import pytest

from check_version_uniqueness import (
    get_package_info,
    main,
    version_exists_on_pypi,
)


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

    def test_returns_none_on_server_error(self):
        error = urllib.error.HTTPError(
            url="", code=500, msg="Server Error", hdrs=None, fp=None  # type: ignore[arg-type]
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            assert version_exists_on_pypi("some-package", "1.0.0") is None

    def test_returns_none_on_network_error(self):
        with mock.patch(
            "urllib.request.urlopen", side_effect=ConnectionError("no network")
        ):
            assert version_exists_on_pypi("some-package", "1.0.0") is None


class TestGetPackageInfo:
    def test_reads_name_and_version(self, tmp_path):
        pkg = tmp_path / "packages" / "my-pkg"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text(
            '[project]\nname = "my-pkg"\nversion = "1.2.3"\n'
        )
        with mock.patch(
            "check_version_uniqueness.Path",
            side_effect=lambda p: tmp_path / p if p == "packages" else __import__("pathlib").Path(p),
        ):
            assert get_package_info("my-pkg") == ("my-pkg", "1.2.3")

    def test_returns_none_for_missing_file(self):
        assert get_package_info("nonexistent-package-xyz") is None


class TestMain:
    def _run(self, changed, package_info, pypi_result):
        patches = [
            mock.patch("check_version_uniqueness.get_changed_packages", return_value=changed),
            mock.patch("check_version_uniqueness.get_package_info", side_effect=lambda d: package_info.get(d)),
            mock.patch("check_version_uniqueness.version_exists_on_pypi", return_value=pypi_result),
        ]
        with patches[0], patches[1], patches[2]:
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            return main()

    def test_passes_when_version_not_on_pypi(self):
        assert self._run(["my-pkg"], {"my-pkg": ("my-pkg", "2.0.0")}, False) == 0

    def test_fails_when_version_exists_on_pypi(self):
        assert self._run(["my-pkg"], {"my-pkg": ("my-pkg", "2.0.0")}, True) == 1

    def test_fails_on_network_error(self):
        assert self._run(["my-pkg"], {"my-pkg": ("my-pkg", "2.0.0")}, None) == 1

    def test_no_changed_packages(self):
        assert self._run([], {}, False) == 0

    def test_fails_when_version_unchanged_but_on_pypi(self):
        """The key scenario: code changed, version not bumped, already on PyPI."""
        assert self._run(["my-pkg"], {"my-pkg": ("my-pkg", "1.0.0")}, True) == 1

    def test_multiple_packages_one_conflict(self):
        def pypi_check(name, version):
            return name == "pkg-a"

        with (
            mock.patch("check_version_uniqueness.get_changed_packages", return_value=["pkg-a", "pkg-b"]),
            mock.patch(
                "check_version_uniqueness.get_package_info",
                side_effect=lambda d: {"pkg-a": ("pkg-a", "1.0.0"), "pkg-b": ("pkg-b", "2.0.0")}.get(d),
            ),
            mock.patch("check_version_uniqueness.version_exists_on_pypi", side_effect=pypi_check),
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 1
