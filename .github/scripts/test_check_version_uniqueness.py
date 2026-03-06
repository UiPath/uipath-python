#!/usr/bin/env python3
"""Tests for check_version_uniqueness.py."""

import os
import urllib.error
from unittest import mock

import pytest

from check_version_uniqueness import (
    get_base_version,
    get_package_version,
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


class TestGetPackageVersion:
    def test_reads_version(self, tmp_path):
        pkg = tmp_path / "packages" / "my-pkg"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text(
            '[project]\nname = "my-pkg"\nversion = "1.2.3"\n'
        )
        with mock.patch(
            "check_version_uniqueness.Path",
            side_effect=lambda p: tmp_path / p if p == "packages" else __import__("pathlib").Path(p),
        ):
            result = get_package_version("my-pkg")
        assert result == ("my-pkg", "1.2.3")

    def test_returns_none_for_missing_file(self):
        result = get_package_version("nonexistent-package-xyz")
        assert result is None


class TestGetBaseVersion:
    def test_reads_version_from_main(self):
        toml_content = '[project]\nname = "my-pkg"\nversion = "1.0.0"\n'
        result = mock.MagicMock()
        result.stdout = toml_content

        with mock.patch("subprocess.run", return_value=result):
            assert get_base_version("my-pkg") == "1.0.0"

    def test_returns_none_for_new_package(self):
        import subprocess

        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            assert get_base_version("new-pkg") is None


class TestMain:
    def test_passes_when_version_not_on_pypi(self):
        with (
            mock.patch(
                "check_version_uniqueness.get_changed_packages_auto",
                return_value=["my-pkg"],
            ),
            mock.patch(
                "check_version_uniqueness.get_package_version",
                return_value=("my-pkg", "2.0.0"),
            ),
            mock.patch(
                "check_version_uniqueness.get_base_version",
                return_value="1.0.0",
            ),
            mock.patch(
                "check_version_uniqueness.version_exists_on_pypi",
                return_value=False,
            ),
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 0

    def test_fails_when_version_exists_on_pypi(self):
        with (
            mock.patch(
                "check_version_uniqueness.get_changed_packages_auto",
                return_value=["my-pkg"],
            ),
            mock.patch(
                "check_version_uniqueness.get_package_version",
                return_value=("my-pkg", "2.0.0"),
            ),
            mock.patch(
                "check_version_uniqueness.get_base_version",
                return_value="1.0.0",
            ),
            mock.patch(
                "check_version_uniqueness.version_exists_on_pypi",
                return_value=True,
            ),
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 1

    def test_skips_unchanged_version(self):
        with (
            mock.patch(
                "check_version_uniqueness.get_changed_packages_auto",
                return_value=["my-pkg"],
            ),
            mock.patch(
                "check_version_uniqueness.get_package_version",
                return_value=("my-pkg", "1.0.0"),
            ),
            mock.patch(
                "check_version_uniqueness.get_base_version",
                return_value="1.0.0",
            ),
            mock.patch(
                "check_version_uniqueness.version_exists_on_pypi",
            ) as mock_pypi,
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 0
            mock_pypi.assert_not_called()

    def test_passes_on_network_error(self):
        with (
            mock.patch(
                "check_version_uniqueness.get_changed_packages_auto",
                return_value=["my-pkg"],
            ),
            mock.patch(
                "check_version_uniqueness.get_package_version",
                return_value=("my-pkg", "2.0.0"),
            ),
            mock.patch(
                "check_version_uniqueness.get_base_version",
                return_value="1.0.0",
            ),
            mock.patch(
                "check_version_uniqueness.version_exists_on_pypi",
                return_value=None,
            ),
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 0

    def test_no_changed_packages(self):
        with mock.patch(
            "check_version_uniqueness.get_changed_packages_auto",
            return_value=[],
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 0

    def test_new_package_not_on_main(self):
        with (
            mock.patch(
                "check_version_uniqueness.get_changed_packages_auto",
                return_value=["new-pkg"],
            ),
            mock.patch(
                "check_version_uniqueness.get_package_version",
                return_value=("new-pkg", "0.1.0"),
            ),
            mock.patch(
                "check_version_uniqueness.get_base_version",
                return_value=None,
            ),
            mock.patch(
                "check_version_uniqueness.version_exists_on_pypi",
                return_value=False,
            ),
        ):
            os.environ.pop("BASE_SHA", None)
            os.environ.pop("HEAD_SHA", None)
            assert main() == 0
