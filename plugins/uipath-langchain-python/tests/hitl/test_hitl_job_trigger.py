import json
import os
import os.path
import shutil
import sqlite3
import uuid

from click.testing import CliRunner
from pytest_httpx import HTTPXMock

from tests.hitl.conftest import get_file_path
from uipath_langchain._cli.cli_run import langgraph_run_middleware


class TestHitlJobTrigger:
    """Test class for Job trigger functionality."""

    def test_agent_job_trigger(
        self,
        runner: CliRunner,
        temp_dir: str,
        httpx_mock: HTTPXMock,
        setup_test_env: None,
    ) -> None:
        script_name = "job_trigger_hitl.py"
        script_file_path = get_file_path(script_name)

        config_file_name = "uipath.json"
        config_file_path = get_file_path(config_file_name)

        langgraph_config_file_name = "langgraph.json"
        langgraph_config_file_path = get_file_path(langgraph_config_file_name)

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Copy the API trigger test file to our temp directory

            shutil.copy(script_file_path, "hitl.py")
            shutil.copy(config_file_path, config_file_name)
            shutil.copy(langgraph_config_file_path, "langgraph.json")

            # mock app creation
            base_url = os.getenv("UIPATH_URL")
            job_key = uuid.uuid4()

            # Mock UiPath API response for job creation
            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
                json={"value": [{"key": f"{job_key}", "Id": "123"}]},
            )

            # First execution: creates job trigger and stores it in database
            result = langgraph_run_middleware("agent", "{}", False)

            assert result.error_message is None

            # Verify that __uipath directory and state.db were created
            assert os.path.exists("__uipath")
            assert os.path.exists("__uipath/state.db")

            # Verify the state database contains trigger information
            conn = None
            try:
                conn = sqlite3.connect("__uipath/state.db")
                cursor = conn.cursor()

                cursor.execute("""
                                        SELECT name FROM sqlite_master
                                        WHERE type='table' AND name='__uipath_resume_triggers'
                                    """)
                tables = cursor.fetchall()
                assert len(tables) == 1

                # Check the first job trigger data
                cursor.execute("SELECT * FROM __uipath_resume_triggers")
                triggers = cursor.fetchall()
                assert len(triggers) == 1
                _, type, key, folder_key, folder_path, payload, _ = triggers[0]
                assert type == "Job"
                assert folder_path == "process-folder-path"
                assert folder_key is None
                assert "input_arg_1" in payload
                assert "value_1" in payload
            finally:
                if conn:
                    conn.close()

            # Mock response for first resume: job output arguments
            output_args_dict = {"output_arg_1": "response from invoke process"}
            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={key})",
                json={
                    "key": f"{job_key}",
                    "id": 123,
                    "output_arguments": json.dumps(output_args_dict),
                },
            )
            # Second execution: resume from first trigger
            result = langgraph_run_middleware("agent", "{}", True)
            assert result.error_message is None
            assert result.should_continue is False

            # Verify second trigger information
            conn = None
            try:
                conn = sqlite3.connect("__uipath/state.db")
                cursor = conn.cursor()

                cursor.execute("""
                                                    SELECT name FROM sqlite_master
                                                    WHERE type='table' AND name='__uipath_resume_triggers'
                                                """)
                tables = cursor.fetchall()
                assert len(tables) == 1

                # Check the second job trigger data (from wait job)
                cursor.execute("""SELECT * FROM __uipath_resume_triggers
                                  ORDER BY timestamp DESC
                                  """)
                triggers = cursor.fetchall()
                assert len(triggers) == 2
                _, type, key, folder_key, folder_path, payload, _ = triggers[0]
                assert type == "Job"
                assert folder_path is None
                assert folder_key is None
                assert "123" in payload
                assert key == "487d9dc7-30fe-4926-b5f0-35a956914042"
            finally:
                if conn:
                    conn.close()

            # Mock response for second resume: wait job output arguments
            output_args_dict = {"output_arg_2": "response from wait job"}

            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={key})",
                json={
                    "key": f"{job_key}",
                    "id": 123,
                    "output_arguments": json.dumps(output_args_dict),
                },
            )

            # Third execution: resume from second trigger and complete
            result = langgraph_run_middleware("agent", "{}", True)
            assert result.error_message is None
            assert result.should_continue is False

            # Verify final output contains the last job response
            with open("__uipath/output.json", "r") as f:
                output = f.read()
            json_output = json.loads(output)
            assert json_output["output"] == {"message": "response from wait job"}

            # Verify execution log contains both job responses
            with open("__uipath/execution.log", "r") as f:
                output = f.read()

            assert "Process output" in output
            assert "response from invoke process" in output
