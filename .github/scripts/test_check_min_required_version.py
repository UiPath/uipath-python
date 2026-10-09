#!/usr/bin/env python3
"""Tests for check_min_required_version.py."""

from unittest import mock

from check_min_required_version import (
    check_min_versions,
    main,
    parse_min_version,
)


class TestParseMinVersion:
    def test_extracts_min_version(self):
        assert parse_min_version("uipath-core>=0.5.4, <0.6.0", "uipath-core") == "0.5.4"

    def test_extracts_min_version_no_upper_bound(self):
        assert parse_min_version("uipath-core>=0.5.4", "uipath-core") == "0.5.4"

    def test_returns_none_for_different_package(self):
        assert parse_min_version("uipath-core>=0.5.4", "uipath-platform") is None

    def test_returns_none_for_no_min_version(self):
        assert parse_min_version("uipath-core==0.5.4", "uipath-core") is None

    def test_handles_whitespace(self):
        assert (
            parse_min_version("  uipath-core>=1.2.3, <2.0.0  ", "uipath-core")
            == "1.2.3"
        )


class TestCheckMinVersions:
    def _make_pyproject(self, name, version, dependencies=None):
        data = {"project": {"name": name, "version": version}}
        if dependencies is not None:
            data["project"]["dependencies"] = dependencies
        return data

    def test_passes_when_min_version_matches(self, tmp_path):
        core = self._make_pyproject("uipath-core", "0.5.7")
        platform = self._make_pyproject(
            "uipath-platform", "0.1.4", ["uipath-core>=0.5.7, <0.6.0"]
        )

        with (
            mock.patch(
                "check_min_required_version.read_pyproject",
                side_effect=lambda d: {
                    "uipath-core": core,
                    "uipath-platform": platform,
                }.get(d),
            ),
            mock.patch(
                "check_min_required_version.PACKAGES_DIR",
                tmp_path,
            ),
        ):
            # Create fake package dirs
            (tmp_path / "uipath-core").mkdir()
            (tmp_path / "uipath-core" / "pyproject.toml").touch()
            (tmp_path / "uipath-platform").mkdir()
            (tmp_path / "uipath-platform" / "pyproject.toml").touch()

            errors = check_min_versions({"uipath-core", "uipath-platform"})
            assert errors == []

    def test_fails_when_min_version_outdated(self, tmp_path):
        core = self._make_pyproject("uipath-core", "0.5.7")
        platform = self._make_pyproject(
            "uipath-platform", "0.1.4", ["uipath-core>=0.5.4, <0.6.0"]
        )

        with (
            mock.patch(
                "check_min_required_version.read_pyproject",
                side_effect=lambda d: {
                    "uipath-core": core,
                    "uipath-platform": platform,
                }.get(d),
            ),
            mock.patch(
                "check_min_required_version.PACKAGES_DIR",
                tmp_path,
            ),
        ):
            (tmp_path / "uipath-core").mkdir()
            (tmp_path / "uipath-core" / "pyproject.toml").touch()
            (tmp_path / "uipath-platform").mkdir()
            (tmp_path / "uipath-platform" / "pyproject.toml").touch()

            errors = check_min_versions({"uipath-core", "uipath-platform"})
            assert len(errors) == 1
            assert "uipath-core>=0.5.4" in errors[0]
            assert "uipath-core>=0.5.7" in errors[0]

    def test_skips_when_dependency_not_changed(self, tmp_path):
        core = self._make_pyproject("uipath-core", "0.5.7")
        platform = self._make_pyproject(
            "uipath-platform", "0.1.4", ["uipath-core>=0.5.4, <0.6.0"]
        )

        with (
            mock.patch(
                "check_min_required_version.read_pyproject",
                side_effect=lambda d: {
                    "uipath-core": core,
                    "uipath-platform": platform,
                }.get(d),
            ),
            mock.patch(
                "check_min_required_version.PACKAGES_DIR",
                tmp_path,
            ),
        ):
            (tmp_path / "uipath-core").mkdir()
            (tmp_path / "uipath-core" / "pyproject.toml").touch()
            (tmp_path / "uipath-platform").mkdir()
            (tmp_path / "uipath-platform" / "pyproject.toml").touch()

            # Only platform changed, core not changed — should pass
            errors = check_min_versions({"uipath-platform"})
            assert errors == []

    def test_multiple_violations(self, tmp_path):
        core = self._make_pyproject("uipath-core", "0.5.7")
        platform = self._make_pyproject(
            "uipath-platform", "0.1.4", ["uipath-core>=0.5.2, <0.6.0"]
        )
        uipath = self._make_pyproject(
            "uipath",
            "2.10.26",
            ["uipath-core>=0.5.2, <0.6.0", "uipath-platform>=0.1.0, <0.2.0"],
        )

        pyprojects = {
            "uipath-core": core,
            "uipath-platform": platform,
            "uipath": uipath,
        }

        with (
            mock.patch(
                "check_min_required_version.read_pyproject",
                side_effect=lambda d: pyprojects.get(d),
            ),
            mock.patch(
                "check_min_required_version.PACKAGES_DIR",
                tmp_path,
            ),
        ):
            for name in pyprojects:
                (tmp_path / name).mkdir()
                (tmp_path / name / "pyproject.toml").touch()

            errors = check_min_versions({"uipath-core", "uipath-platform", "uipath"})
            # platform has outdated core dep, uipath has outdated core and platform deps
            assert len(errors) == 3


class TestMain:
    def test_no_changed_packages(self):
        with mock.patch(
            "check_min_required_version.get_changed_packages", return_value=set()
        ):
            assert main() == 0

    def test_passes_when_versions_correct(self):
        with (
            mock.patch(
                "check_min_required_version.get_changed_packages",
                return_value={"uipath-core", "uipath-platform"},
            ),
            mock.patch(
                "check_min_required_version.check_min_versions",
                return_value=[],
            ),
        ):
            assert main() == 0

    def test_fails_when_versions_outdated(self):
        with (
            mock.patch(
                "check_min_required_version.get_changed_packages",
                return_value={"uipath-core", "uipath-platform"},
            ),
            mock.patch(
                "check_min_required_version.check_min_versions",
                return_value=["some error"],
            ),
        ):
            assert main() == 1
