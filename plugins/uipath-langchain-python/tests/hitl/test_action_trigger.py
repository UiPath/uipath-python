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


def get_org_scoped_url(base_url: str):
    return base_url.rsplit("/", 1)[0]


class TestHitlActionTrigger:
    """Test class for Action trigger functionality."""

    def test_agent_action_trigger(
        self,
        runner: CliRunner,
        temp_dir: str,
        httpx_mock: HTTPXMock,
        setup_test_env: None,
    ) -> None:
        script_name = "action_trigger_hitl.py"
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
            base_url = os.getenv(
                "UIPATH_URL", "https://cloud.uipath.com/organization/tenant"
            )
            action_key = uuid.uuid4()

            # Mock UiPath API responses for action app creation
            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/tasks/AppTasks/CreateAppTask",
                json={
                    "id": 1,
                    "title": "Action Required: Report Review",
                    "key": f"{action_key}",
                },
            )

            httpx_mock.add_response(
                url=f"{get_org_scoped_url(base_url)}/apps_/default/api/v1/default/deployed-action-apps-schemas?search=HITL APP",
                text=json.dumps(
                    {
                        "deployed": [
                            {
                                "deploymentFolder": {
                                    "fullyQualifiedName": "app-folder-path"
                                },
                                "systemName": "HITL APP",
                                "actionSchema": {
                                    "key": "test-key",
                                    "inputs": [],
                                    "outputs": [],
                                    "inOuts": [],
                                    "outcomes": [],
                                },
                            }
                        ]
                    }
                ),
            )

            # First execution: creates action trigger and stores it in database
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

                # Check the first action trigger data
                cursor.execute("SELECT * FROM __uipath_resume_triggers")
                triggers = cursor.fetchall()
                assert len(triggers) == 1
                _, type, key, folder_key, folder_path, payload, _ = triggers[0]
                assert type == "Task"
                assert folder_path == "app-folder-path"
                assert folder_key is None
                assert "agent question" in payload
                assert "Action Required" in payload
            finally:
                if conn:
                    conn.close()

            # Mock response for first resume: human response from create action
            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey={key}",
                json={
                    "id": 1,
                    "title": "Action Required: Report Review",
                    "data": {"Answer": "human response from create action"},
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

                # Check the second trigger data (from wait action)
                cursor.execute("""SELECT * FROM __uipath_resume_triggers
                                  ORDER BY timestamp DESC
                                  """)
                triggers = cursor.fetchall()
                assert len(triggers) == 2
                _, type, key, folder_key, folder_path, payload, _ = triggers[0]
                assert type == "Task"
                assert folder_path is None
                assert folder_key is None
                assert "agent question from wait action" in payload
                assert key == "1662478a-65b4-4a09-8e22-d707e5bd64f3"
            finally:
                if conn:
                    conn.close()

            # Mock response for second resume: human response from wait action
            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey={key}",
                json={
                    "id": 1,
                    "title": "Action Required: Report Review",
                    "data": {"Answer": "human response from wait action"},
                },
            )

            # Third execution: resume from second trigger and complete
            result = langgraph_run_middleware("agent", "{}", True)
            assert result.error_message is None
            assert result.should_continue is False

            # Verify final output contains the last human response
            with open("__uipath/output.json", "r") as f:
                output = f.read()
            json_output = json.loads(output)
            assert json_output["output"] == {
                "message": "human response from wait action"
            }

            # Verify execution log contains both human responses
            with open("__uipath/execution.log", "r") as f:
                output = f.read()

            assert "Response from HITL action:" in output
            assert "human response from create action" in output
