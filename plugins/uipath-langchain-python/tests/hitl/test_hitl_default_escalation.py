import json
import os
import os.path
import shutil
import sqlite3
import uuid

from click.testing import CliRunner
from pytest_httpx import HTTPXMock
from uipath._utils.constants import ENV_FOLDER_KEY

from tests.hitl.conftest import get_file_path
from uipath_langchain._cli.cli_run import langgraph_run_middleware


def get_org_scoped_url(base_url):
    return base_url.rsplit("/", 1)[0]


class TestHitlDefaultEscalation:
    """Test class for default escalation functionality."""

    def test_agent(
        self,
        runner: CliRunner,
        temp_dir: str,
        httpx_mock: HTTPXMock,
        setup_test_env: None,
    ) -> None:
        script_name = "api_trigger_hitl.py"
        script_file_path = get_file_path(script_name)

        config_file_name = "uipath-default-escalation.json"
        config_file_path = get_file_path(config_file_name)

        langgraph_config_file_name = "langgraph.json"
        langgraph_config_file_path = get_file_path(langgraph_config_file_name)
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Copy the API trigger test file to our temp directory

            shutil.copy(script_file_path, "hitl.py")
            shutil.copy(config_file_path, "uipath.json")
            shutil.copy(langgraph_config_file_path, langgraph_config_file_name)

            # mock app creation
            base_url = os.getenv(
                "UIPATH_URL", "https://cloud.uipath.com/organization/tenant"
            )
            action_key = uuid.uuid4()

            # Mock UiPath API responses for default escalation action creation
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
                                "deploymentFolder": {"key": os.getenv(ENV_FOLDER_KEY)},
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

            # First execution: creates default escalation trigger and stores it in database
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

                # Check the escalation trigger data (uses Task type with default escalation config)
                cursor.execute("SELECT * FROM __uipath_resume_triggers")
                triggers = cursor.fetchall()
                assert len(triggers) == 1
                _, type, key, folder_path, folder_key, payload, _ = triggers[0]
                assert type == "Task"
                assert folder_path == folder_key is None
                assert payload == "interrupt message"
            finally:
                if conn:
                    conn.close()

            # Mock response for resume scenario: human response from escalation action
            httpx_mock.add_response(
                url=f"{base_url}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey={key}",
                json={
                    "id": 1,
                    "title": "Action Required: Report Review",
                    "data": {"Answer": "human response"},
                },
            )

            # Second execution: resume from stored trigger and fetch human response
            result = langgraph_run_middleware("agent", "{}", True)

            assert result.error_message is None
            assert result.should_continue is False

            # Verify final output contains the escalation response
            with open("__uipath/output.json", "r") as f:
                output = f.read()
            json_output = json.loads(output)
            assert json_output["output"] == {"message": "human response"}

            # Verify execution log shows successful escalation action creation
            with open("__uipath/execution.log", "r") as f:
                output = f.read()

            assert "Action created successfully" in output
            assert key in output
