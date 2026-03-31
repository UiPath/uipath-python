"""Integration tests for context-grounding CLI commands.

Tests verify end-to-end functionality of all context-grounding commands,
including proper option handling, error messages, and output formatting.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath.platform.context_grounding import ContextGroundingIndex


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Provide a mocked UiPath client."""
    with patch("uipath.platform._uipath.UiPath") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        client_instance.context_grounding = MagicMock()
        client_instance.attachments = MagicMock()
        yield client_instance


def _make_index(name="my-index", status="Completed", description="Test index"):
    """Build a mock ContextGroundingIndex."""
    index = MagicMock(spec=ContextGroundingIndex)
    index.id = "test-index-id"
    index.name = name
    index.last_ingestion_status = status
    index.last_ingested = None
    index.description = description
    index.folder_key = "test-folder-key"
    index.in_progress_ingestion.return_value = False
    index.model_dump.return_value = {
        "id": "test-index-id",
        "name": name,
        "last_ingestion_status": status,
        "description": description,
    }
    return index


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_list_basic(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.list_indexes.return_value = [
            _make_index(name="index-one"),
            _make_index(name="index-two"),
        ]
        result = runner.invoke(
            cli, ["context-grounding", "list", "--folder-path", "Shared"]
        )
        assert result.exit_code == 0
        assert "index-one" in result.output
        assert "index-two" in result.output
        mock_client.context_grounding.list_indexes.assert_called_once_with(
            folder_path="Shared", folder_key=None
        )

    def test_list_empty(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.list_indexes.return_value = []
        result = runner.invoke(
            cli, ["context-grounding", "list", "--folder-path", "Shared"]
        )
        assert result.exit_code == 0

    def test_list_with_folder_key(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.list_indexes.return_value = []
        fk = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = runner.invoke(cli, ["context-grounding", "list", "--folder-key", fk])
        assert result.exit_code == 0
        mock_client.context_grounding.list_indexes.assert_called_once_with(
            folder_path=None, folder_key=fk
        )


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------


class TestRetrieveCommand:
    def test_retrieve_by_name(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.return_value = _make_index()
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code == 0
        assert "my-index" in result.output
        mock_client.context_grounding.retrieve.assert_called_once_with(
            name="my-index", folder_path="Shared", folder_key=None
        )

    def test_retrieve_by_id(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve_by_id.return_value = {
            "id": "abc-123",
            "name": "ephemeral-index",
            "lastIngestionStatus": "Successful",
        }
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index-id",
                "abc-123",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.retrieve_by_id.assert_called_once()

    def test_retrieve_no_identifier_fails(self, runner, mock_env_vars):
        result = runner.invoke(cli, ["context-grounding", "retrieve"])
        assert result.exit_code != 0
        assert (
            "index-name" in result.output.lower() or "index-id" in result.output.lower()
        )

    def test_retrieve_both_identifiers_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            ["context-grounding", "retrieve", "--index-name", "X", "--index-id", "Y"],
        )
        assert result.exit_code != 0

    def test_retrieve_not_found(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.side_effect = LookupError("not found")
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index-name",
                "missing",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_retrieve_not_found_http_404(self, runner, mock_client, mock_env_vars):
        from httpx import HTTPStatusError, Request, Response

        resp = Response(404, request=Request("GET", "http://test"))
        mock_client.context_grounding.retrieve.side_effect = HTTPStatusError(
            "Not found", request=resp.request, response=resp
        )
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index-name",
                "missing",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreateCommand:
    def test_create_with_bucket_source(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.create_index.return_value = _make_index(
            name="new-index"
        )
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "create",
                "--index-name",
                "new-index",
                "--bucket-source",
                "my-bucket",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.create_index.assert_called_once()
        call_kwargs = mock_client.context_grounding.create_index.call_args[1]
        assert call_kwargs["name"] == "new-index"

    def test_create_both_sources_fails(self, runner, mock_env_vars, tmp_path):
        f = tmp_path / "config.json"
        f.write_text("{}")
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "create",
                "--index-name",
                "X",
                "--bucket-source",
                "B",
                "--source-file",
                str(f),
            ],
        )
        assert result.exit_code != 0
        assert (
            "cannot use both" in result.output.lower()
            or "choose one" in result.output.lower()
        )

    def test_create_no_source_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "create",
                "--index-name",
                "X",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code != 0

    def test_create_missing_index_name_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            ["context-grounding", "create", "--bucket-source", "B"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# create-ephemeral
# ---------------------------------------------------------------------------


class TestCreateEphemeralCommand:
    def test_create_ephemeral_basic(self, runner, mock_client, mock_env_vars, tmp_path):
        test_file = tmp_path / "doc.pdf"
        test_file.write_text("test content")

        import uuid

        mock_client.attachments.upload.return_value = uuid.uuid4()
        mock_client.context_grounding.create_ephemeral_index.return_value = _make_index(
            name="ephemeral"
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "create-ephemeral",
                "--usage",
                "DeepRAG",
                "--files",
                str(test_file),
            ],
        )
        assert result.exit_code == 0
        mock_client.attachments.upload.assert_called_once()
        mock_client.context_grounding.create_ephemeral_index.assert_called_once()

    def test_create_ephemeral_multiple_files(
        self, runner, mock_client, mock_env_vars, tmp_path
    ):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("a")
        f2.write_text("b")

        import uuid

        mock_client.attachments.upload.return_value = uuid.uuid4()
        mock_client.context_grounding.create_ephemeral_index.return_value = (
            _make_index()
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "create-ephemeral",
                "--usage",
                "BatchRAG",
                "--files",
                str(f1),
                "--files",
                str(f2),
            ],
        )
        assert result.exit_code == 0
        assert mock_client.attachments.upload.call_count == 2

    def test_create_ephemeral_missing_usage_fails(
        self, runner, mock_env_vars, tmp_path
    ):
        f = tmp_path / "doc.pdf"
        f.write_text("x")
        result = runner.invoke(
            cli,
            ["context-grounding", "create-ephemeral", "--files", str(f)],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# source-schema
# ---------------------------------------------------------------------------


class TestSourceSchemaCommand:
    def test_source_schema_all(self, runner):
        result = runner.invoke(cli, ["context-grounding", "source-schema"])
        assert result.exit_code == 0
        assert "google_drive" in result.output
        assert "onedrive" in result.output
        assert "dropbox" in result.output
        assert "confluence" in result.output
        assert "connection_id" in result.output

    def test_source_schema_specific_type(self, runner):
        result = runner.invoke(
            cli, ["context-grounding", "source-schema", "--type", "confluence"]
        )
        assert result.exit_code == 0
        assert "confluence" in result.output
        assert "space_id" in result.output
        assert "google_drive" not in result.output


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteCommand:
    def test_delete_with_confirm(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.return_value = _make_index()
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
                "--confirm",
            ],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.delete_by_name.assert_called_once_with(
            name="my-index", folder_path="Shared", folder_key=None
        )

    def test_delete_dry_run(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.return_value = _make_index()
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "would delete" in result.output.lower()
        mock_client.context_grounding.delete_by_name.assert_not_called()

    def test_delete_prompts_no_cancels(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.return_value = _make_index()
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
            ],
            input="n\n",
        )
        assert result.exit_code == 0
        mock_client.context_grounding.delete_by_name.assert_not_called()

    def test_delete_prompts_yes_deletes(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.return_value = _make_index()
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
            ],
            input="y\n",
        )
        assert result.exit_code == 0
        mock_client.context_grounding.delete_by_name.assert_called_once()

    def test_delete_not_found(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.retrieve.side_effect = LookupError("not found")
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index-name",
                "missing",
                "--folder-path",
                "Shared",
                "--confirm",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_delete_missing_index_name_fails(self, runner, mock_env_vars):
        result = runner.invoke(cli, ["context-grounding", "delete", "--confirm"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


class TestIngestCommand:
    def test_ingest_basic(self, runner, mock_client, mock_env_vars):
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code == 0
        assert "ingestion triggered" in result.output.lower()
        mock_client.context_grounding.ingest_by_name.assert_called_once_with(
            name="my-index", folder_path="Shared", folder_key=None
        )

    def test_ingest_missing_index_name_fails(self, runner, mock_env_vars):
        result = runner.invoke(cli, ["context-grounding", "ingest"])
        assert result.exit_code != 0

    def test_ingest_with_folder_key(self, runner, mock_client, mock_env_vars):
        fk = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index-name",
                "my-index",
                "--folder-key",
                fk,
            ],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.ingest_by_name.assert_called_once_with(
            name="my-index", folder_path=None, folder_key=fk
        )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearchCommand:
    def test_search_by_name(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.unified_search.return_value = []
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
                "--query",
                "revenue",
            ],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.unified_search.assert_called_once()
        call_kwargs = mock_client.context_grounding.unified_search.call_args[1]
        assert call_kwargs["name"] == "my-index"
        assert call_kwargs["query"] == "revenue"

    def test_search_with_limit(self, runner, mock_client, mock_env_vars):
        mock_client.context_grounding.unified_search.return_value = []
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "--index-name",
                "X",
                "--folder-path",
                "Shared",
                "--query",
                "test",
                "--limit",
                "3",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.context_grounding.unified_search.call_args[1]
        assert call_kwargs["number_of_results"] == 3

    def test_search_missing_query_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "--index-name",
                "X",
                "--folder-path",
                "Shared",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# deep-rag start
# ---------------------------------------------------------------------------


class TestDeepRagStartCommand:
    def test_start_by_name(self, runner, mock_client, mock_env_vars):
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_result.model_dump.return_value = {"id": "task-123", "status": "Queued"}
        mock_client.context_grounding.start_deep_rag.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "deep-rag",
                "start",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
                "--task-name",
                "my-task",
                "--prompt",
                "Summarize",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.context_grounding.start_deep_rag.call_args[1]
        assert call_kwargs["name"] == "my-task"
        assert call_kwargs["index_name"] == "my-index"
        assert call_kwargs["index_id"] is None

    def test_start_by_id(self, runner, mock_client, mock_env_vars):
        mock_result = MagicMock()
        mock_result.id = "task-456"
        mock_result.model_dump.return_value = {"id": "task-456"}
        mock_client.context_grounding.start_deep_rag.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "deep-rag",
                "start",
                "--index-id",
                "idx-789",
                "--task-name",
                "my-task",
                "--prompt",
                "Summarize",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.context_grounding.start_deep_rag.call_args[1]
        assert call_kwargs["index_id"] == "idx-789"
        assert call_kwargs["index_name"] is None

    def test_start_no_index_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "deep-rag",
                "start",
                "--task-name",
                "T",
                "--prompt",
                "P",
            ],
        )
        assert result.exit_code != 0

    def test_start_both_index_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "deep-rag",
                "start",
                "--index-name",
                "X",
                "--index-id",
                "Y",
                "--task-name",
                "T",
                "--prompt",
                "P",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# deep-rag retrieve
# ---------------------------------------------------------------------------


class TestDeepRagRetrieveCommand:
    def test_retrieve(self, runner, mock_client, mock_env_vars):
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"id": "task-123", "status": "Successful"}
        mock_client.context_grounding.retrieve_deep_rag.return_value = mock_result

        result = runner.invoke(
            cli,
            ["context-grounding", "deep-rag", "retrieve", "--task-id", "task-123"],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.retrieve_deep_rag.assert_called_once_with(
            id="task-123"
        )

    def test_retrieve_missing_task_id_fails(self, runner, mock_env_vars):
        result = runner.invoke(cli, ["context-grounding", "deep-rag", "retrieve"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# batch-transform start
# ---------------------------------------------------------------------------


class TestBatchTransformStartCommand:
    def test_start_by_name(self, runner, mock_client, mock_env_vars, tmp_path):
        cols_file = tmp_path / "cols.json"
        cols_file.write_text(
            json.dumps([{"name": "entity", "description": "Entity name"}])
        )

        mock_result = MagicMock()
        mock_result.id = "bt-123"
        mock_result.model_dump.return_value = {"id": "bt-123"}
        mock_client.context_grounding.start_batch_transform.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "batch-transform",
                "start",
                "--index-name",
                "my-index",
                "--folder-path",
                "Shared",
                "--task-name",
                "my-task",
                "--prompt",
                "Extract entities",
                "--columns-file",
                str(cols_file),
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.context_grounding.start_batch_transform.call_args[1]
        assert call_kwargs["name"] == "my-task"
        assert call_kwargs["index_name"] == "my-index"

    def test_start_by_id(self, runner, mock_client, mock_env_vars, tmp_path):
        cols_file = tmp_path / "cols.json"
        cols_file.write_text(json.dumps([{"name": "col1", "description": "Col"}]))

        mock_result = MagicMock()
        mock_result.id = "bt-456"
        mock_result.model_dump.return_value = {"id": "bt-456"}
        mock_client.context_grounding.start_batch_transform.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "batch-transform",
                "start",
                "--index-id",
                "idx-789",
                "--task-name",
                "my-task",
                "--prompt",
                "Extract",
                "--columns-file",
                str(cols_file),
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.context_grounding.start_batch_transform.call_args[1]
        assert call_kwargs["index_id"] == "idx-789"
        assert call_kwargs["index_name"] is None

    def test_start_no_index_fails(self, runner, mock_env_vars, tmp_path):
        cols_file = tmp_path / "cols.json"
        cols_file.write_text("[]")
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "batch-transform",
                "start",
                "--task-name",
                "T",
                "--prompt",
                "P",
                "--columns-file",
                str(cols_file),
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# batch-transform retrieve
# ---------------------------------------------------------------------------


class TestBatchTransformRetrieveCommand:
    def test_retrieve(self, runner, mock_client, mock_env_vars):
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"id": "bt-123", "status": "Successful"}
        mock_client.context_grounding.retrieve_batch_transform.return_value = (
            mock_result
        )

        result = runner.invoke(
            cli,
            ["context-grounding", "batch-transform", "retrieve", "--task-id", "bt-123"],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.retrieve_batch_transform.assert_called_once_with(
            id="bt-123"
        )


# ---------------------------------------------------------------------------
# batch-transform download
# ---------------------------------------------------------------------------


class TestBatchTransformDownloadCommand:
    def test_download(self, runner, mock_client, mock_env_vars, tmp_path):
        out_file = str(tmp_path / "result.csv")
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "batch-transform",
                "download",
                "--task-id",
                "bt-123",
                "--output-file",
                out_file,
            ],
        )
        assert result.exit_code == 0
        mock_client.context_grounding.download_batch_transform_result.assert_called_once_with(
            id="bt-123", destination_path=out_file
        )
        assert "downloaded" in result.output.lower()

    def test_download_missing_output_file_fails(self, runner, mock_env_vars):
        result = runner.invoke(
            cli,
            ["context-grounding", "batch-transform", "download", "--task-id", "bt-123"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# help text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_group_help(self, runner):
        result = runner.invoke(cli, ["context-grounding", "--help"])
        assert result.exit_code == 0
        assert "Two index types" in result.output
        assert "Regular" in result.output
        assert "Ephemeral" in result.output
        for cmd in [
            "list",
            "retrieve",
            "create",
            "create-ephemeral",
            "delete",
            "ingest",
            "search",
            "source-schema",
            "deep-rag",
            "batch-transform",
        ]:
            assert cmd in result.output

    def test_retrieve_help(self, runner):
        result = runner.invoke(cli, ["context-grounding", "retrieve", "--help"])
        assert result.exit_code == 0
        assert "--index-name" in result.output
        assert "--index-id" in result.output

    def test_deep_rag_start_help(self, runner):
        result = runner.invoke(
            cli, ["context-grounding", "deep-rag", "start", "--help"]
        )
        assert result.exit_code == 0
        assert "--index-name" in result.output
        assert "--index-id" in result.output
        assert "--task-name" in result.output
        assert "--prompt" in result.output

    def test_batch_transform_start_help(self, runner):
        result = runner.invoke(
            cli, ["context-grounding", "batch-transform", "start", "--help"]
        )
        assert result.exit_code == 0
        assert "--columns-file" in result.output
        assert "--task-name" in result.output
