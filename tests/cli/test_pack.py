# type: ignore
import json
import os
import zipfile

from click.testing import CliRunner
from utils.project_details import ProjectDetails
from utils.uipath_json import UiPathJson

import uipath._cli.cli_pack as cli_pack
from uipath._cli.cli_pack import pack


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

            result = runner.invoke(pack, ["./"])
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

            result = runner.invoke(pack, ["./"])
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

            result = runner.invoke(pack, ["./"])
            assert result.exit_code == 1
            assert (
                """Project authors cannot be empty. Please specify authors in pyproject.toml:\n    authors = [{ name = "John Doe" }]"""
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

            result = runner.invoke(pack, ["./"])
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

            result = runner.invoke(pack, ["./"])
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

            result = runner.invoke(pack, ["./"])
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
            result = runner.invoke(pack, ["./"])
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

            result = runner.invoke(pack, ["./"])
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
        uipath_json.settings.file_extensions_included = [".xml"]
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open(xml_file_name, "w") as f:
                f.write("<root><child>text</child></root>")
            with open(sh_file_name, "w") as f:
                f.write("#bin/sh\n echo 1")
            result = runner.invoke(pack, ["./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert f"content/{xml_file_name}" in z.namelist()
                assert f"content/{sh_file_name}" not in z.namelist()

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
            result = runner.invoke(pack, ["./"])

            assert result.exit_code == 0
            with zipfile.ZipFile(
                f".uipath/{project_details.name}.{project_details.version}.nupkg", "r"
            ) as z:
                assert f"content/{file_to_add}" in z.namelist()
                assert f"content/{random_file}" not in z.namelist()

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
            result = runner.invoke(pack, ["./"])

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
