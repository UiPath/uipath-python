#!/usr/bin/env python3
"""Tests for check_dependency_version_bumps.py."""

from unittest import mock

from check_dependency_version_bumps import (
    PackageInfo,
    check,
    normalize_name,
    parse_requirement,
    version_key,
)


def pkg(name: str, version: str, dependencies: list[str] | None = None) -> PackageInfo:
    return PackageInfo(
        dir=name,
        name=name,
        version=version,
        dependencies=dependencies or [],
    )


class TestVersionKey:
    def test_numeric_components(self):
        assert version_key("0.5.18") == (0, 5, 18)

    def test_compares_numerically_not_lexically(self):
        # The trap a string compare would fall into: "0.5.8" > "0.5.17".
        assert version_key("0.5.17") > version_key("0.5.8")

    def test_strips_prerelease_suffix(self):
        assert version_key("0.5.18rc1") == (0, 5, 18)


class TestNormalizeName:
    def test_case_and_separators_equivalent(self):
        assert normalize_name("UiPath_Core") == normalize_name("uipath-core")
        assert normalize_name("uipath.core") == "uipath-core"


class TestParseRequirement:
    def test_extracts_name_and_lower_bound(self):
        assert parse_requirement("uipath-core>=0.5.8, <0.6.0") == ("uipath-core", "0.5.8")

    def test_no_lower_bound(self):
        assert parse_requirement("click") == ("click", None)
        assert parse_requirement("httpx<1.0") == ("httpx", None)

    def test_whitespace_after_operator(self):
        assert parse_requirement("uipath-core >= 0.5.8") == ("uipath-core", "0.5.8")


class TestCheck:
    def _packages(self) -> dict[str, PackageInfo]:
        return {
            "uipath-core": pkg("uipath-core", "0.5.18"),
            "uipath-platform": pkg(
                "uipath-platform", "0.1.60", ["uipath-core>=0.5.8, <0.6.0"]
            ),
            "uipath": pkg(
                "uipath",
                "2.10.74",
                [
                    "uipath-core>=0.5.8, <0.6.0",
                    "uipath-platform>=0.1.59, <0.2.0",
                    "click>=8.3.1",
                ],
            ),
        }

    def test_passes_when_only_dependency_changed(self):
        # uipath-core changed alone -> dependents not touched, nothing to enforce.
        assert check(self._packages(), {"uipath-core"}) == []

    def test_passes_when_only_dependent_changed(self):
        assert check(self._packages(), {"uipath"}) == []

    def test_fails_when_co_changed_without_min_bump(self):
        # uipath-core bumped to 0.5.18 but uipath still pins >=0.5.8.
        violations = check(self._packages(), {"uipath-core", "uipath"})
        assert len(violations) == 1
        assert "uipath" in violations[0]
        assert "0.5.18" in violations[0]

    def test_passes_when_min_raised_to_new_version(self):
        packages = self._packages()
        packages["uipath"]["dependencies"] = [
            "uipath-core>=0.5.18, <0.6.0",
            "click>=8.3.1",
        ]
        assert check(packages, {"uipath-core", "uipath"}) == []

    def test_passes_when_min_already_above_new_version(self):
        packages = self._packages()
        packages["uipath"]["dependencies"] = ["uipath-core>=0.6.0, <0.7.0"]
        assert check(packages, {"uipath-core", "uipath"}) == []

    def test_fails_when_no_lower_bound_on_co_changed_dep(self):
        packages = self._packages()
        packages["uipath"]["dependencies"] = ["uipath-core"]
        violations = check(packages, {"uipath-core", "uipath"})
        assert len(violations) == 1
        assert "no '>=' lower bound" in violations[0]

    def test_external_dependencies_are_ignored(self):
        # click is not an internal package, so it is never in scope.
        assert check(self._packages(), {"uipath"}) == []

    def test_transitive_chain_each_edge_enforced(self):
        # All three changed: uipath must bump core AND platform; platform must bump core.
        packages = self._packages()
        violations = check(packages, {"uipath-core", "uipath-platform", "uipath"})
        # uipath->core (stale), uipath->platform (0.1.59 < 0.1.60), platform->core (stale)
        assert len(violations) == 3

    def test_no_self_reference(self):
        packages = {"uipath": pkg("uipath", "2.0.0", ["uipath>=1.0.0"])}
        assert check(packages, {"uipath"}) == []


class TestMain:
    def _run(self, packages: dict[str, PackageInfo], changed: list[str]) -> int:
        from check_dependency_version_bumps import main

        with (
            mock.patch("check_dependency_version_bumps.get_all_packages", return_value=packages),
            mock.patch("check_dependency_version_bumps.get_changed_packages", return_value=changed),
        ):
            return main()

    def test_returns_zero_when_compliant(self):
        packages = {
            "uipath-core": pkg("uipath-core", "0.5.18"),
            "uipath": pkg("uipath", "2.0.0", ["uipath-core>=0.5.18, <0.6.0"]),
        }
        assert self._run(packages, ["uipath-core", "uipath"]) == 0

    def test_returns_one_on_violation(self):
        packages = {
            "uipath-core": pkg("uipath-core", "0.5.18"),
            "uipath": pkg("uipath", "2.0.0", ["uipath-core>=0.5.8, <0.6.0"]),
        }
        assert self._run(packages, ["uipath-core", "uipath"]) == 1

    def test_returns_zero_when_no_changes(self):
        assert self._run({"uipath-core": pkg("uipath-core", "0.5.18")}, []) == 0