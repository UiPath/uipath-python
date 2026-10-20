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
