import os

from uipath._cli._utils._project_files import files_to_include


class TestFilesToIncludeHiddenFiles:
    def test_hidden_files_are_excluded(self, tmp_path):
        project_dir = str(tmp_path)
        open(os.path.join(project_dir, "main.py"), "w").close()
        open(os.path.join(project_dir, ".hidden_file.py"), "w").close()
        open(os.path.join(project_dir, ".env"), "w").close()

        included, _ = files_to_include(None, project_dir, include_uv_lock=False)
        included_names = [f.file_name for f in included]

        assert "main.py" in included_names
        assert ".hidden_file.py" not in included_names
        assert ".env" not in included_names

    def test_hidden_files_in_subdirectory_are_excluded(self, tmp_path):
        project_dir = str(tmp_path)
        sub_dir = os.path.join(project_dir, "src")
        os.makedirs(sub_dir)
        open(os.path.join(sub_dir, "app.py"), "w").close()
        open(os.path.join(sub_dir, ".secret.json"), "w").close()

        included, _ = files_to_include(None, project_dir, include_uv_lock=False)
        included_names = [f.file_name for f in included]

        assert "app.py" in included_names
        assert ".secret.json" not in included_names


class TestFilesToIncludeExplicitHiddenPaths:
    """`packOptions.filesIncluded` must be honored even for dot-prefixed paths.

    Regression for the case where an explicit include living under a dot-prefixed
    directory (e.g. `.config/assets/x.md`) or a named dotfile (e.g.
    `.python-version`) was silently dropped: the dot-directory was pruned from
    `os.walk` and dotfiles were skipped before the inclusion logic ran, so
    `uipath pack` exited 0 with those always-include files missing.
    """

    def test_explicit_includes_under_dot_paths_are_packed(self, tmp_path):
        from uipath._cli.models.uipath_json_schema import PackOptions

        project_dir = str(tmp_path)

        # Explicit include inside a dot-prefixed directory.
        os.makedirs(os.path.join(project_dir, ".config", "assets"))
        open(os.path.join(project_dir, ".config", "assets", "asset.md"), "w").close()
        # Explicit dotfile include at the project root.
        open(os.path.join(project_dir, ".python-version"), "w").close()

        # Controls that must stay excluded (not listed in filesIncluded).
        os.makedirs(os.path.join(project_dir, ".git"))
        open(os.path.join(project_dir, ".git", "config.md"), "w").close()
        open(os.path.join(project_dir, ".secret.md"), "w").close()

        pack_options = PackOptions(
            filesIncluded=[".config/assets/asset.md", ".python-version"]
        )

        included, _ = files_to_include(pack_options, project_dir, include_uv_lock=False)
        rel_paths = {f.relative_path.replace(os.sep, "/") for f in included}

        assert ".config/assets/asset.md" in rel_paths
        assert ".python-version" in rel_paths
        # Hidden paths that were not explicitly included stay excluded.
        assert ".secret.md" not in rel_paths
        assert ".git/config.md" not in rel_paths
