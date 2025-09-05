# type: ignore
import json
import os
import zipfile

from click.testing import CliRunner
from utils.project_details import ProjectDetails
from utils.uipath_json import UiPathJson

import uipath._cli.cli_pack as cli_pack
from uipath._cli import cli


class TestPack:
    """Test pack command."""

    def test_pack_project_creation(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
    ) -> None:
        """Test project packing scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files for packing
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

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
        uipath_json: UiPathJson,
    ) -> None:
        """Test project packing scenarios."""
        project_details.description = None
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

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
        uipath_json: UiPathJson,
    ) -> None:
        """Test project packing scenarios."""
        project_details.authors = None
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

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
        uipath_json: UiPathJson,
    ) -> None:
        project_details.requires_python = None
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

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
        uipath_json: UiPathJson,
    ) -> None:
        project_details.name = ""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

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
        uipath_json: UiPathJson,
    ) -> None:
        project_details.name = "project < name"
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert """Project name contains invalid character: '<'""" in result.output

    def test_pyproject_invalid_description(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
    ) -> None:
        project_details.description = "invalid project description &"
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

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
            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert (
                "uipath.json not found. Please run `uipath init` in the project directory."
                in result.output
            )

    def test_pack_without_pyproject_toml(
        self, runner: CliRunner, temp_dir: str, uipath_json: UiPathJson
    ) -> None:
        """Test packing when pyproject.toml is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())

            result = runner.invoke(cli, ["pack", "./"])
            assert result.exit_code == 1
            assert "pyproject.toml not found" in result.output

    def test_generate_operate_file(
        self, runner: CliRunner, temp_dir: str, uipath_json: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""

        operate_data = cli_pack.generate_operate_file(
            json.loads(uipath_json.to_json())["entryPoints"]
        )
        assert (
            operate_data["$schema"]
            == "https://cloud.uipath.com/draft/2024-12/entry-point"
        )
        assert operate_data["main"] == uipath_json.entry_points[0].file_path
        assert operate_data["contentType"] == uipath_json.entry_points[0].type
        assert operate_data["targetFramework"] == "Portable"
        assert operate_data["targetRuntime"] == "python"
        assert operate_data["runtimeOptions"] == {
            "requiresUserInteraction": False,
            "isAttended": False,
        }

    def test_generate_entrypoints_file(
        self, runner: CliRunner, temp_dir: str, uipath_json: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""
        bindings_data = cli_pack.generate_bindings_content()
        assert bindings_data["version"] == "2.0"
        assert bindings_data["resources"] == []

    def test_generate_bindings_content(
        self, runner: CliRunner, temp_dir: str, uipath_json: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""
        entrypoints_data = cli_pack.generate_entrypoints_file(
            json.loads(uipath_json.to_json())["entryPoints"]
        )
        assert (
            entrypoints_data["$schema"]
            == "https://cloud.uipath.com/draft/2024-12/entry-point"
        )
        assert entrypoints_data["$id"] == "entry-points.json"
        assert (
            entrypoints_data["entryPoints"]
            == json.loads(uipath_json.to_json())["entryPoints"]
        )

    def test_package_descriptor_content(
        self, runner: CliRunner, temp_dir: str, uipath_json: UiPathJson
    ) -> None:
        """Test generating operate.json and its content."""
        expected_files = {
            "operate.json": "content/operate.json",
            "entry-points.json": "content/entry-points.json",
            "bindings.json": "content/bindings_v2.json",
        }
        for entry in uipath_json.entry_points:
            expected_files[entry.file_path] = entry.file_path
        content = cli_pack.generate_package_descriptor_content(
            json.loads(uipath_json.to_json())["entryPoints"]
        )
        assert (
            content["$schema"]
            == "https://cloud.uipath.com/draft/2024-12/package-descriptor"
        )
        assert len(content["files"]) == 3 + len(uipath_json.entry_points)
        assert content["files"] == expected_files

    def test_include_file_extensions(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
    ) -> None:
        """Test generating operate.json and its content."""
        xml_file_name = "test.xml"
        sh_file_name = "test.sh"
        md_file_name = "README.md"
        binary_file_name = "script.exe"
        binary_file_not_included = "report.xlsx"

        # Binary content for the exe file (simulating a simple executable)
        binary_content = b"\x4d\x5a\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00\xb8\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x00\x00\x00"

        uipath_json.settings.file_extensions_included = [".xml", ".exe"]
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
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
        uipath_json: UiPathJson,
    ) -> None:
        """Test generating operate.json and its content."""
        file_to_add = "file_to_add.xml"
        random_file = "random_file.xml"
        uipath_json.settings.files_included = [f"{file_to_add}"]
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
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
        uipath_json: UiPathJson,
    ) -> None:
        """Test generating operate.json and its content."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
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
        uipath_json: UiPathJson,
    ) -> None:
        """Test error handling in pack command."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            for entry in uipath_json.entry_points:
                with open(f"{entry.file_path}.py", "w") as f:
                    f.write("#agent content")
            result = runner.invoke(cli, ["pack", "./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert result.exit_code == 0
                for entry in uipath_json.entry_points:
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
        uipath_json: UiPathJson,
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
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create entry point files
            for entry in uipath_json.entry_points:
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
        uipath_json: UiPathJson,
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("uv.lock", "w") as f:
                f.write("# uv.lock content")
            for entry in uipath_json.entry_points:
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

            for entry in uipath_json.entry_points:
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
        uipath_json: UiPathJson,
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("uv.lock", "w") as f:
                f.write("# uv.lock content")
            for entry in uipath_json.entry_points:
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
