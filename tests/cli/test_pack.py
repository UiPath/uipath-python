# type: ignore
import json
import os
import zipfile

from click.testing import CliRunner
from utils.project_details import ProjectDetails
from utils.uipath_json import UiPathJson

import uipath._cli.cli_pack as cli_pack
from uipath._cli import cli


def create_bindings_file():
    """Helper to create a default bindings.json file for tests."""
    bindings_content = {"version": "2.0", "resources": []}
    with open("bindings.json", "w") as f:
        json.dump(bindings_content, f, indent=4)


class TestPack:
    """Test pack command."""

    def test_pack_project_creation(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test project packing scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files for packing
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0
            assert os.path.exists(
                f".uipath/{project_details.name}.{project_details.version}.nupkg"
            )

    def test_pyproject_missing_description(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test project packing scenarios."""
        project_details.description = None
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                "pyproject.toml is missing the required field: project.description."
                in result.output
            )

    def test_pyproject_missing_authors(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test project packing scenarios."""
        project_details.authors = None
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                """Project authors cannot be empty. Please specify authors in pyproject.toml:\n    authors = [{ name = "John Doe" }]"""
                in result.output
            )

    def test_pyproject_missing_requires_python(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        project_details.requires_python = None
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                "'requires-python' field cannot be empty. Please specify it in pyproject.toml"
                in result.output
            )

    def test_pyproject_missing_project_name(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        project_details.name = ""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                "Project name cannot be empty. Please specify a name in pyproject.toml."
                in result.output
            )

    def test_pyproject_invalid_name(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        project_details.name = "project < name"
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert """Project name contains invalid character: '<'""" in result.output

    def test_pyproject_invalid_description(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        project_details.description = "invalid project description &"
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                """Project description contains invalid character: '&'"""
                in result.output
            )

    def test_pack_without_uipath_json(
        self, runner: CliRunner, temp_dir: str, project_details: ProjectDetails
    ) -> None:
        """Test packing when uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            create_bindings_file()
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                "uipath.json not found. Please run `uipath init` in the project directory."
                in result.output
            )

    def test_pack_without_pyproject_toml(
        self, runner: CliRunner, temp_dir: str, uipath_json_legacy: UiPathJson
    ) -> None:
        """Test packing when pyproject.toml is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            create_bindings_file()
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert "pyproject.toml not found" in result.output

    def test_generate_operate_file(
        self, runner: CliRunner, temp_dir: str, uipath_json_legacy: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            create_bindings_file()
            operate_data = cli_pack.generate_operate_file(
                json.loads(uipath_json_legacy.to_json())["entryPoints"]
            )
            assert (
                operate_data["$schema"]
                == "https://cloud.uipath.com/draft/2024-12/entry-point"
            )
            assert operate_data["main"] == uipath_json_legacy.entry_points[0].file_path
            assert (
                operate_data["contentType"] == uipath_json_legacy.entry_points[0].type
            )
            assert operate_data["targetFramework"] == "Portable"
            assert operate_data["targetRuntime"] == "python"
            assert operate_data["runtimeOptions"] == {
                "requiresUserInteraction": False,
                "isAttended": False,
            }

    def test_generate_bindings_content(
        self, runner: CliRunner, temp_dir: str, uipath_json_legacy: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""
        entrypoints_data = cli_pack.generate_entrypoints_file(
            json.loads(uipath_json_legacy.to_json())["entryPoints"]
        )
        assert (
            entrypoints_data["$schema"]
            == "https://cloud.uipath.com/draft/2024-12/entry-point"
        )
        assert entrypoints_data["$id"] == "entry-points.json"
        assert (
            entrypoints_data["entryPoints"]
            == json.loads(uipath_json_legacy.to_json())["entryPoints"]
        )

    def test_package_descriptor_content(
        self, runner: CliRunner, temp_dir: str, uipath_json_legacy: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""
        expected_files = {
            "operate.json": "content/operate.json",
            "entry-points.json": "content/entry-points.json",
            "bindings.json": "content/bindings_v2.json",
        }
        for entry in uipath_json_legacy.entry_points:
            expected_files[entry.file_path] = entry.file_path
        content = cli_pack.generate_package_descriptor_content(
            json.loads(uipath_json_legacy.to_json())["entryPoints"]
        )
        assert (
            content["$schema"]
            == "https://cloud.uipath.com/draft/2024-12/package-descriptor"
        )
        assert len(content["files"]) == 3 + len(uipath_json_legacy.entry_points)
        assert content["files"] == expected_files

    def test_include_file_extensions(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test generating operate.json and its content."""
        xml_file_name = "test.xml"
        sh_file_name = "test.sh"
        md_file_name = "README.md"
        binary_file_name = "script.exe"
        binary_file_not_included = "report.xlsx"

        # Binary content for the exe file (simulating a simple executable)
        binary_content = b"\x4d\x5a\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00\xb8\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x00\x00\x00"

        uipath_json_legacy.settings.file_extensions_included = [".xml", ".exe"]
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open(xml_file_name, "w") as f:
                f.write("<root><child>text</child></root>")
            with open(sh_file_name, "w") as f:
                f.write("#bin/sh\n echo 1")
            with open(md_file_name, "w") as f:
                f.write(".md file content")
            with open(binary_file_name, "wb") as f:  # Write binary file
                f.write(binary_content)
            with open(binary_file_not_included, "w") as f:
                f.write("---")
            result = runner.invoke(cli, ["pack", "./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert f"content/{xml_file_name}" in z.namelist()
                assert f"content/{sh_file_name}" not in z.namelist()
                assert f"content/{md_file_name}" in z.namelist()
                assert f"content/{binary_file_not_included}" not in z.namelist()
                assert f"content/{binary_file_name}" in z.namelist()
                assert "content/pyproject.toml" in z.namelist()
                # Verify binary content is not corrupted
                extracted_binary_content = z.read(f"content/{binary_file_name}")
                assert extracted_binary_content == binary_content, (
                    "Binary file content was corrupted during packing"
                )

    def test_include_files(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test generating operate.json and its content."""
        file_to_add = "file_to_add.xml"
        random_file = "random_file.xml"
        uipath_json_legacy.settings.files_included = [f"{file_to_add}"]
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open(file_to_add, "w") as f:
                f.write("<root><child>text</child></root>")
            with open(random_file, "w") as f:
                f.write("<root><child>text</child></root>")
            result = runner.invoke(cli, ["pack", "./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert f"content/{file_to_add}" in z.namelist()
                assert f"content/{random_file}" not in z.namelist()

    def test_include_subdir_files(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test generating operate.json and its content."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            os.mkdir("subdir")
            with open("subdir/should_be_included.py", "w") as f:
                f.write('print("This file should be included in the .nupkg")')
            result = runner.invoke(cli, ["pack", "./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert "content/subdir/should_be_included.py" in z.namelist()

    def test_successful_pack(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test error handling in pack command."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            for entry in uipath_json_legacy.entry_points:
                with open(f"{entry.file_path}.py", "w") as f:
                    f.write("#agent content")
            result = runner.invoke(cli, ["pack", "./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert result.exit_code == 0
                for entry in uipath_json_legacy.entry_points:
                    assert f"content/{entry.file_path}.py" in z.namelist()
                assert "Packaging project" in result.output
                assert f"Name       : {project_details.name}" in result.output
                assert f"Version    : {project_details.version}" in result.output
                assert f"Description: {project_details.description}" in result.output
                authors_dict = {
                    author["name"]: author for author in project_details.authors
                }
                assert f"Authors    : {', '.join(authors_dict.keys())}" in result.output
                assert "Project successfully packaged." in result.output

    def test_dependencies_version_formats(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that all dependency version formats are parsed correctly and included in operate.json."""

        # Update project details with comprehensive dependency examples
        project_details.dependencies = [
            # Simple package name
            "click",
            # Single version constraints
            "django>=4.0",
            "flask==2.3.0",
            "numpy>1.20.0",
            "pandas<=2.0.0",
            "scipy<1.11.0",
            "matplotlib~=3.5.0",
            "pytest!=7.1.0",
            # Complex version constraints
            "tensorflow>=2.10.0,<2.13.0",
            "torch>=1.12.0,<=1.13.1",
            # Package with extras
            "requests[security]>=2.28.0",
            "sqlalchemy[postgresql,mysql]>=1.4.0",
            # Environment markers (should be stripped)
            "pywin32>=227; sys_platform=='win32'",
            "uvloop>=0.17.0; python_version>='3.8' and sys_platform!='win32'",
            # Complex combination
            "cryptography[ssh]>=3.4.8,<4.0.0; python_version>='3.7'",
            # Edge cases
            "some-package_with.dots_and-dashes>=1.0.0",
            "CamelCasePackage==2.1.0",
        ]

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create entry point files
            for entry in uipath_json_legacy.entry_points:
                with open(f"{entry.file_path}.py", "w") as f:
                    f.write("# agent content")

            # Run pack command
            result = runner.invoke(cli, ["pack", "./"])

            # Assert pack was successful
            assert result.exit_code == 0, f"Pack failed with output: {result.output}"
            assert "Project successfully packaged." in result.output

            # Verify package was created
            package_path = (
                f".uipath/{project_details.name}.{project_details.version}.nupkg"
            )
            assert os.path.exists(package_path)

            # Extract and verify operate.json content
            with zipfile.ZipFile(package_path, "r") as z:
                # Read operate.json
                operate_content = z.read("content/operate.json").decode("utf-8")
                operate_data = json.loads(operate_content)

                # Verify dependencies exist in operate.json
                assert "dependencies" in operate_data, (
                    "Dependencies should be present in operate.json"
                )

                dependencies = operate_data["dependencies"]

                # Expected parsed dependencies (name -> version_spec)
                expected_dependencies = {
                    # Simple package name
                    "click": "*",
                    # Single version constraints
                    "django": ">=4.0",
                    "flask": "==2.3.0",
                    "numpy": ">1.20.0",
                    "pandas": "<=2.0.0",
                    "scipy": "<1.11.0",
                    "matplotlib": "~=3.5.0",
                    "pytest": "!=7.1.0",
                    # Complex version constraints
                    "tensorflow": ">=2.10.0,<2.13.0",
                    "torch": ">=1.12.0,<=1.13.1",
                    # Package with extras (extras should be stripped)
                    "requests": ">=2.28.0",
                    "sqlalchemy": ">=1.4.0",
                    # Environment markers (markers should be stripped)
                    "pywin32": ">=227",
                    "uvloop": ">=0.17.0",
                    # Complex combination (extras and markers stripped)
                    "cryptography": ">=3.4.8,<4.0.0",
                    # Edge cases
                    "some-package_with.dots_and-dashes": ">=1.0.0",
                    "CamelCasePackage": "==2.1.0",
                }

                # Verify all expected dependencies are present
                for package_name, expected_version in expected_dependencies.items():
                    assert package_name in dependencies, (
                        f"Package '{package_name}' should be in dependencies"
                    )
                    actual_version = dependencies[package_name]
                    assert actual_version == expected_version, (
                        f"Package '{package_name}' should have version '{expected_version}', "
                        f"but got '{actual_version}'"
                    )

                # Verify no unexpected dependencies
                for package_name in dependencies:
                    assert package_name in expected_dependencies, (
                        f"Unexpected package '{package_name}' found in dependencies"
                    )

                # Verify specific edge cases
                assert len(dependencies) == len(expected_dependencies), (
                    f"Expected {len(expected_dependencies)} dependencies, "
                    f"but got {len(dependencies)}"
                )

                # Test that environment markers were properly stripped
                assert "pywin32" in dependencies
                assert dependencies["pywin32"] == ">=227"

                # Test that extras were properly stripped but version preserved
                assert "sqlalchemy" in dependencies
                assert dependencies["sqlalchemy"] == ">=1.4.0"

                # Test complex version constraints are preserved
                assert "tensorflow" in dependencies
                assert dependencies["tensorflow"] == ">=2.10.0,<2.13.0"

                # Verify operate.json structure is still correct
                assert (
                    operate_data["$schema"]
                    == "https://cloud.uipath.com/draft/2024-12/entry-point"
                )
                assert "projectId" in operate_data
                assert operate_data["targetRuntime"] == "python"
                assert operate_data["targetFramework"] == "Portable"

    def test_nupkg_contains_all_necessary_files(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("uv.lock", "w") as f:
                f.write("# uv.lock content")
            for entry in uipath_json_legacy.entry_points:
                with open(f"{entry.file_path}.py", "w") as f:
                    f.write("# agent content")

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            nupkg_path = (
                f".uipath/{project_details.name}.{project_details.version}.nupkg"
            )
            assert os.path.exists(nupkg_path)

            # List of expected files in the package
            expected_files = [
                "content/uipath.json",
                "content/pyproject.toml",
                "content/operate.json",
                "content/entry-points.json",
                "content/bindings_v2.json",
                "content/uv.lock",
            ]

            for entry in uipath_json_legacy.entry_points:
                expected_files.append(f"content/{entry.file_path}.py")

            with zipfile.ZipFile(nupkg_path, "r") as z:
                actual_files = set(z.namelist())
                for expected in expected_files:
                    assert expected in actual_files, f"Missing {expected} in nupkg"

    def test_no_uv_lock_with_nolock(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("uv.lock", "w") as f:
                f.write("# uv.lock content")
            for entry in uipath_json_legacy.entry_points:
                with open(f"{entry.file_path}.py", "w") as f:
                    f.write("# agent content")

            result = runner.invoke(cli, ["pack", "./", "--nolock"])
            assert result.exit_code == 0

            nupkg_path = (
                f".uipath/{project_details.name}.{project_details.version}.nupkg"
            )
            assert os.path.exists(nupkg_path)

            with zipfile.ZipFile(nupkg_path, "r") as z:
                actual_files = set(z.namelist())
                assert "content/uv.lock" not in actual_files, (
                    "uv.lock should not be in nupkg when --nolock is used"
                )

    def test_files_excluded(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that files mentioned in filesExcluded are excluded from the package."""
        json_file_to_exclude = "config.json"
        json_file_to_include = "other.json"

        # Set up exclusions
        uipath_json_legacy.settings.files_excluded = [json_file_to_exclude]

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create files - .json files are included by default
            with open(json_file_to_exclude, "w") as f:
                f.write('{"should": "be excluded"}')
            with open(json_file_to_include, "w") as f:
                f.write('{"should": "be included"}')

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                # Excluded file should not be present
                assert f"content/{json_file_to_exclude}" not in z.namelist()
                # Other JSON file should still be present
                assert f"content/{json_file_to_include}" in z.namelist()

    def test_files_excluded_takes_precedence_over_included(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that filesExcluded takes precedence over filesIncluded."""
        conflicting_file = "conflicting.txt"

        # Set up both inclusion and exclusion for the same file
        uipath_json_legacy.settings.files_included = [conflicting_file]
        uipath_json_legacy.settings.files_excluded = [conflicting_file]

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create the conflicting file
            with open(conflicting_file, "w") as f:
                f.write("This file should be excluded despite being in filesIncluded")

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                # File should be excluded (exclusion takes precedence)
                assert f"content/{conflicting_file}" not in z.namelist()

    def test_filename_vs_path_exclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that filename exclusion only affects root directory, path exclusion affects specific paths."""
        # Exclude root config.json and specific path subdir2/settings.json
        uipath_json_legacy.settings.files_excluded = [
            "config.json",
            "subdir2/settings.json",
        ]

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create directories
            os.mkdir("subdir1")
            os.mkdir("subdir2")

            # Create files with same names in different locations
            with open("config.json", "w") as f:  # Root - should be excluded
                f.write('{"root": "config"}')
            with open("subdir1/config.json", "w") as f:  # Subdir - should be included
                f.write('{"subdir1": "config"}')
            with open("subdir2/config.json", "w") as f:  # Subdir - should be included
                f.write('{"subdir2": "config"}')

            with open("settings.json", "w") as f:  # Root - should be included
                f.write('{"root": "settings"}')
            with open("subdir1/settings.json", "w") as f:  # Subdir - should be included
                f.write('{"subdir1": "settings"}')
            with open(
                "subdir2/settings.json", "w"
            ) as f:  # Specific path - should be excluded
                f.write('{"subdir2": "settings"}')

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                # Filename exclusion: only affects root directory
                assert "content/config.json" not in z.namelist()  # Root excluded
                assert "content/subdir1/config.json" in z.namelist()  # Subdir included
                assert "content/subdir2/config.json" in z.namelist()  # Subdir included

                # Path exclusion: only affects specific path
                assert "content/settings.json" in z.namelist()  # Root included
                assert (
                    "content/subdir1/settings.json" in z.namelist()
                )  # Different path included
                assert (
                    "content/subdir2/settings.json" not in z.namelist()
                )  # Specific path excluded

    def test_filename_vs_path_inclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that filename inclusion only affects root directory, path inclusion affects specific paths."""
        # Include root data.txt and specific path subdir2/config.txt
        uipath_json_legacy.settings.files_included = ["data.txt", "subdir1/config.txt"]

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create directories
            os.mkdir("subdir1")
            os.mkdir("subdir2")

            # Create .txt files (not included by default extension)
            with open("data.txt", "w") as f:  # Root - should be included by filename
                f.write("root data")
            with open("subdir1/data.txt", "w") as f:  # Subdir - should NOT be included
                f.write("subdir1 data")
            with open(
                "subdir2/data.txt", "w"
            ) as f:  # Different subdir - should NOT be included
                f.write("subdir2 data")

            with open("config.txt", "w") as f:  # Root - should NOT be included
                f.write("root config")
            with open(
                "subdir1/config.txt", "w"
            ) as f:  # Specific path - should be included
                f.write("subdir1 config")
            with open(
                "subdir2/config.txt", "w"
            ) as f:  # Different path - should NOT be included
                f.write("subdir2 config")

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                # Filename inclusion: only affects root directory
                assert "content/data.txt" in z.namelist()  # Root included
                assert (
                    "content/subdir1/data.txt" not in z.namelist()
                )  # Subdir not included
                assert (
                    "content/subdir2/data.txt" not in z.namelist()
                )  # Subdir not included

                # Path inclusion: only affects specific path
                assert "content/config.txt" not in z.namelist()  # Root not included
                assert (
                    "content/subdir1/config.txt" in z.namelist()
                )  # Specific path included
                assert (
                    "content/subdir2/config.txt" not in z.namelist()
                )  # Different path not included

    def test_directory_name_vs_path_exclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that directory exclusion by name only affects root level, by path affects specific paths."""
        # Exclude root-level "temp" directory and specific path "tests/old"
        uipath_json_legacy.settings.directories_excluded = ["temp", "tests/old"]

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create directory structure
            os.makedirs("temp")  # Root level - should be excluded
            os.makedirs("src/temp")  # Nested - should be included
            os.makedirs("tests/old")  # Specific path - should be excluded
            os.makedirs("tests/new")  # Different path - should be included
            os.makedirs("old")  # Root level - should be included

            # Create JSON files in each directory (included by default)
            with open("temp/config.json", "w") as f:
                f.write('{"location": "root temp"}')
            with open("src/temp/config.json", "w") as f:
                f.write('{"location": "src temp"}')
            with open("tests/old/config.json", "w") as f:
                f.write('{"location": "tests old"}')
            with open("tests/new/config.json", "w") as f:
                f.write('{"location": "tests new"}')
            with open("old/config.json", "w") as f:
                f.write('{"location": "root old"}')

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                # Directory name exclusion: only affects root level
                assert (
                    "content/temp/config.json" not in z.namelist()
                )  # Root temp excluded
                assert (
                    "content/src/temp/config.json" in z.namelist()
                )  # Nested temp included

                # Directory path exclusion: only affects specific path
                assert (
                    "content/tests/old/config.json" not in z.namelist()
                )  # Specific path excluded
                assert (
                    "content/tests/new/config.json" in z.namelist()
                )  # Different path included
                assert "content/old/config.json" in z.namelist()  # Root old included

    def test_bindings_v2_naming_in_nupkg(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that bindings.json is named bindings_v2.json in the .nupkg."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files for packing
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create bindings.json with some test resources
            bindings_content = {
                "version": "2.0",
                "resources": [
                    {
                        "resource": "asset",
                        "key": "test-asset",
                        "value": {
                            "name": {
                                "defaultValue": "test-asset",
                                "isExpression": False,
                                "displayName": "Asset Name",
                            }
                        },
                        "metadata": {
                            "BindingsVersion": "2.2",
                            "ActivityName": "retrieve",
                        },
                    }
                ],
            }
            with open("bindings.json", "w") as f:
                json.dump(bindings_content, f, indent=4)

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            nupkg_path = (
                f".uipath/{project_details.name}.{project_details.version}.nupkg"
            )
            assert os.path.exists(nupkg_path)

            with zipfile.ZipFile(nupkg_path, "r") as z:
                # Verify bindings file is named bindings_v2.json in the package
                assert "content/bindings_v2.json" in z.namelist()

                # Verify the content is correct
                bindings_v2_content = z.read("content/bindings_v2.json").decode("utf-8")
                bindings_v2_data = json.loads(bindings_v2_content)

                assert bindings_v2_data["version"] == "2.0"
                assert len(bindings_v2_data["resources"]) == 1
                assert bindings_v2_data["resources"][0]["resource"] == "asset"
                assert bindings_v2_data["resources"][0]["key"] == "test-asset"

    def test_evals_and_evaluations_directories_excluded(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test that evals and evaluations directories are excluded from the nupkg."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            os.makedirs("evals")
            os.makedirs("evaluations")
            os.makedirs("other_dir")

            with open("evals/test_eval.json", "w") as f:
                f.write('{"eval": "data"}')
            with open("evaluations/test_evaluation.json", "w") as f:
                f.write('{"evaluation": "data"}')
            with open("other_dir/included.json", "w") as f:
                f.write('{"should": "be included"}')

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 0

            nupkg_path = (
                f".uipath/{project_details.name}.{project_details.version}.nupkg"
            )
            assert os.path.exists(nupkg_path)

            with zipfile.ZipFile(nupkg_path, "r") as z:
                assert "content/evals/test_eval.json" not in z.namelist()
                assert "content/evaluations/test_evaluation.json" not in z.namelist()
                assert "content/other_dir/included.json" in z.namelist()
