"""Integration tests for context-grounding CLI commands.

These tests verify end-to-end functionality of the context-grounding service
commands, including proper context handling, error messages, and output formatting.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath.platform.context_grounding import (
    ContextGroundingIndex,
    ContextGroundingQueryResponse,
)
from uipath.platform.errors import IngestionInProgressException


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
        yield client_instance


def _make_index(name="my-index", status="Completed", description="Test index"):
    """Helper: build a mock ContextGroundingIndex.

    Uses spec=ContextGroundingIndex so MagicMock is not mistaken for an
    Iterator by format_output (MagicMock implements __iter__ by default).
    in_progress_ingestion() returns False by default (ingestion complete).
    """
    index = MagicMock(spec=ContextGroundingIndex)
    index.id = "test-index-id"
    index.name = name
    index.last_ingestion_status = status
    index.last_ingested = None
    index.description = description
    index.in_progress_ingestion.return_value = False
    index.model_dump.return_value = {
        "name": name,
        "last_ingestion_status": status,
        "description": description,
    }
    return index


def _make_result(source="doc.pdf", page="1", content="Some content", score=0.95):
    """Helper: build a mock ContextGroundingQueryResponse.

    Uses spec=ContextGroundingQueryResponse for the same reason as _make_index.
    """
    result = MagicMock(spec=ContextGroundingQueryResponse)
    result.source = source
    result.page_number = page
    result.content = content
    result.score = score
    result.model_dump.return_value = {
        "source": source,
        "page_number": page,
        "content": content,
        "score": score,
    }
    return result


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_list_basic(self, runner, mock_client, mock_env_vars):
        """list returns all indexes in a folder."""
        mock_client.context_grounding.list.return_value = [
            _make_index(name="index-one", status="Completed"),
            _make_index(name="index-two", status="Queued"),
        ]

        result = runner.invoke(
            cli,
            ["context-grounding", "list", "--folder-path", "Shared"],
        )

        assert result.exit_code == 0
        assert "index-one" in result.output
        assert "index-two" in result.output
        # table columns projected
        assert "last_ingestion_status" in result.output
        assert "last_ingested" in result.output
        # raw fields not in table
        assert "data_source" not in result.output
        mock_client.context_grounding.list.assert_called_once_with(
            folder_path="Shared",
            folder_key=None,
        )

    def test_list_json_format(self, runner, mock_client, mock_env_vars):
        """list with --format json emits JSON."""
        mock_client.context_grounding.list.return_value = [
            _make_index(name="index-one"),
        ]

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "list",
                "--folder-path",
                "Shared",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert "index-one" in result.output

    def test_list_empty(self, runner, mock_client, mock_env_vars):
        """list with no indexes returns empty output gracefully."""
        mock_client.context_grounding.list.return_value = []

        result = runner.invoke(
            cli,
            ["context-grounding", "list", "--folder-path", "Shared"],
        )

        assert result.exit_code == 0

    def test_list_with_folder_key(self, runner, mock_client, mock_env_vars):
        """list passes folder_key when --folder-key is provided."""
        mock_client.context_grounding.list.return_value = []
        folder_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        result = runner.invoke(
            cli,
            ["context-grounding", "list", "--folder-key", folder_key],
        )

        assert result.exit_code == 0
        mock_client.context_grounding.list.assert_called_once_with(
            folder_path=None,
            folder_key=folder_key,
        )


# ---------------------------------------------------------------------------


class TestRetrieveCommand:
    def test_retrieve_basic(self, runner, mock_client, mock_env_vars):
        """retrieve returns index details."""
        mock_client.context_grounding.retrieve.return_value = _make_index()

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code == 0
        assert "my-index" in result.output
        mock_client.context_grounding.retrieve.assert_called_once_with(
            name="my-index",
            folder_path="Shared",
            folder_key=None,
        )

    def test_retrieve_json_format(self, runner, mock_client, mock_env_vars):
        """retrieve with --format json emits JSON."""
        mock_client.context_grounding.retrieve.return_value = _make_index()

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert "my-index" in result.output

    def test_retrieve_missing_index_flag_fails(self, runner, mock_env_vars):
        """retrieve without --index shows usage error."""
        result = runner.invoke(
            cli, ["context-grounding", "retrieve", "--folder-path", "Shared"]
        )

        assert result.exit_code != 0
        assert "index" in result.output.lower() or "missing" in result.output.lower()

    def test_retrieve_not_found(self, runner, mock_client, mock_env_vars):
        """retrieve surfaces a clean not-found error (SDK bare Exception)."""
        mock_client.context_grounding.retrieve.side_effect = Exception(
            "ContextGroundingIndex not found"
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index",
                "no-such-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_retrieve_not_found_http_404(self, runner, mock_client, mock_env_vars):
        """retrieve surfaces a clean not-found error (HTTPStatusError 404)."""
        from unittest.mock import MagicMock

        from httpx import HTTPStatusError, Request, Response

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 404
        mock_client.context_grounding.retrieve.side_effect = HTTPStatusError(
            "404", request=MagicMock(spec=Request), response=mock_response
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index",
                "no-such-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_retrieve_with_folder_key(self, runner, mock_client, mock_env_vars):
        """retrieve passes folder_key when --folder-key is provided."""
        mock_client.context_grounding.retrieve.return_value = _make_index()
        folder_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "retrieve",
                "--index",
                "my-index",
                "--folder-key",
                folder_key,
            ],
        )

        assert result.exit_code == 0
        mock_client.context_grounding.retrieve.assert_called_once_with(
            name="my-index",
            folder_path=None,
            folder_key=folder_key,
        )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearchCommand:
    def test_search_basic(self, runner, mock_client, mock_env_vars):
        """search returns results table."""
        mock_client.context_grounding.search.return_value = [
            _make_result(
                source="invoice.pdf", content="Pay within 30 days", score=0.92
            ),
            _make_result(source="policy.pdf", content="Approval required", score=0.85),
        ]

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "process an invoice",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code == 0
        assert "invoice.pdf" in result.output
        assert "policy.pdf" in result.output
        mock_client.context_grounding.search.assert_called_once_with(
            name="my-index",
            query="process an invoice",
            number_of_results=10,
            threshold=None,
            folder_path="Shared",
            folder_key=None,
        )

    def test_search_with_limit_option(self, runner, mock_client, mock_env_vars):
        """--limit N is forwarded to the SDK as number_of_results."""
        mock_client.context_grounding.search.return_value = [
            _make_result(content="Short answer"),
        ]

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "payment terms",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--limit",
                "3",
            ],
        )

        assert result.exit_code == 0
        mock_client.context_grounding.search.assert_called_once_with(
            name="my-index",
            query="payment terms",
            number_of_results=3,
            threshold=None,
            folder_path="Shared",
            folder_key=None,
        )

    def test_search_json_format_no_truncation(self, runner, mock_client, mock_env_vars):
        """JSON output contains full content, not truncated."""
        long_content = "x" * 300
        mock_client.context_grounding.search.return_value = [
            _make_result(content=long_content),
        ]

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "query",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert long_content in result.output

    def test_search_table_format_truncates_content(
        self, runner, mock_client, mock_env_vars
    ):
        """Table output shows score/source/page/content only; content truncated at 120 chars."""
        long_content = "A" * 200
        mock_client.context_grounding.search.return_value = [
            _make_result(source="doc.pdf", page="3", content=long_content, score=0.92),
        ]

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "query",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0
        # content is truncated
        assert long_content not in result.output
        assert "…" in result.output
        # only human-readable columns rendered
        assert "score" in result.output
        assert "source" in result.output
        assert "page_number" in result.output
        assert "doc.pdf" in result.output
        # raw fields not present in table
        assert "metadata" not in result.output
        assert "reference" not in result.output

    def test_search_empty_results(self, runner, mock_client, mock_env_vars):
        """search with no results prints a helpful message and exits 0.

        Note: the message is emitted via click.echo(..., err=True) so it goes to
        stderr. CliRunner mixes stderr into result.output by default, which is why
        the assertion below works. If this runner were created with mix_stderr=False
        the assertion would need to check result.stderr instead.
        """
        mock_client.context_grounding.search.return_value = []

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "unknown query",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code == 0
        # message goes to stderr; CliRunner mixes stderr into output by default
        assert "no results" in result.output.lower()

    def test_search_ingestion_in_progress_error(
        self, runner, mock_client, mock_env_vars
    ):
        """search surfaces a clean error when index is being ingested."""
        mock_client.context_grounding.search.side_effect = IngestionInProgressException(
            index_name="my-index"
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "query",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert (
            "ingested" in result.output.lower() or "ingestion" in result.output.lower()
        )

    def test_search_not_found(self, runner, mock_client, mock_env_vars):
        """search surfaces a clean not-found error for missing index."""
        mock_client.context_grounding.search.side_effect = Exception(
            "ContextGroundingIndex not found"
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "query",
                "--index",
                "no-such-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_search_missing_index_flag_fails(self, runner, mock_env_vars):
        """search without --index shows usage error."""
        result = runner.invoke(
            cli, ["context-grounding", "search", "query", "--folder-path", "Shared"]
        )

        assert result.exit_code != 0
        assert "index" in result.output.lower() or "missing" in result.output.lower()

    def test_search_missing_query_fails(self, runner, mock_env_vars):
        """search without QUERY positional arg shows usage error."""
        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0

    def test_search_with_folder_key(self, runner, mock_client, mock_env_vars):
        """search passes folder_key when --folder-key is provided."""
        mock_client.context_grounding.search.return_value = [_make_result()]
        folder_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "search",
                "query",
                "--index",
                "my-index",
                "--folder-key",
                folder_key,
            ],
        )

        assert result.exit_code == 0
        mock_client.context_grounding.search.assert_called_once_with(
            name="my-index",
            query="query",
            number_of_results=10,
            threshold=None,
            folder_path=None,
            folder_key=folder_key,
        )


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


class TestIngestCommand:
    def test_ingest_basic(self, runner, mock_client, mock_env_vars):
        """ingest triggers ingestion and prints confirmation."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index
        mock_client.context_grounding.ingest_data.return_value = None

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code == 0
        assert "my-index" in result.output
        mock_client.context_grounding.ingest_data.assert_called_once_with(
            index=index,
            folder_path="Shared",
            folder_key=None,
        )

    def test_ingest_already_in_progress_fast_fail(
        self, runner, mock_client, mock_env_vars
    ):
        """ingest fails fast (no HTTP call) when retrieve shows ingestion in progress."""
        index = _make_index(status="In Progress")
        index.in_progress_ingestion.return_value = True
        mock_client.context_grounding.retrieve.return_value = index

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "already" in result.output.lower() or "ingested" in result.output.lower()
        mock_client.context_grounding.ingest_data.assert_not_called()

    def test_ingest_already_in_progress(self, runner, mock_client, mock_env_vars):
        """ingest surfaces a clean error when the API reports 409 (race condition)."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index
        mock_client.context_grounding.ingest_data.side_effect = (
            IngestionInProgressException(index_name="my-index", search_operation=False)
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "already" in result.output.lower() or "ingested" in result.output.lower()

    def test_ingest_not_found(self, runner, mock_client, mock_env_vars):
        """ingest surfaces a clean not-found error."""
        mock_client.context_grounding.retrieve.side_effect = Exception(
            "ContextGroundingIndex not found"
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index",
                "no-such-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_ingest_index_has_no_id(self, runner, mock_client, mock_env_vars):
        """ingest raises a clean error if the retrieved index has no ID (avoids silent no-op)."""
        index = _make_index()
        index.id = None
        mock_client.context_grounding.retrieve.return_value = index

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
        )

        assert result.exit_code != 0
        assert "no id" in result.output.lower() or "cannot" in result.output.lower()
        mock_client.context_grounding.ingest_data.assert_not_called()

    def test_ingest_with_folder_key(self, runner, mock_client, mock_env_vars):
        """ingest passes folder_key when --folder-key is provided."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index
        mock_client.context_grounding.ingest_data.return_value = None
        folder_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "ingest",
                "--index",
                "my-index",
                "--folder-key",
                folder_key,
            ],
        )

        assert result.exit_code == 0
        mock_client.context_grounding.retrieve.assert_called_once_with(
            name="my-index",
            folder_path=None,
            folder_key=folder_key,
        )
        mock_client.context_grounding.ingest_data.assert_called_once_with(
            index=index,
            folder_path=None,
            folder_key=folder_key,
        )

    def test_ingest_missing_index_flag_fails(self, runner, mock_env_vars):
        """ingest without --index shows usage error."""
        result = runner.invoke(
            cli, ["context-grounding", "ingest", "--folder-path", "Shared"]
        )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteCommand:
    def test_delete_with_confirm(self, runner, mock_client, mock_env_vars):
        """delete --confirm removes the index without prompting."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index
        mock_client.context_grounding.delete_index.return_value = None

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--confirm",
            ],
        )

        assert result.exit_code == 0
        assert "my-index" in result.output
        mock_client.context_grounding.delete_index.assert_called_once_with(
            index=index,
            folder_path="Shared",
            folder_key=None,
        )

    def test_delete_dry_run(self, runner, mock_client, mock_env_vars):
        """delete --dry-run prints what would be deleted without deleting."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "would delete" in result.output.lower()
        mock_client.context_grounding.delete_index.assert_not_called()

    def test_delete_prompts_without_confirm(self, runner, mock_client, mock_env_vars):
        """delete without --confirm or --dry-run prompts the user; 'n' cancels."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()
        mock_client.context_grounding.delete_index.assert_not_called()

    def test_delete_prompts_yes_deletes(self, runner, mock_client, mock_env_vars):
        """delete without --confirm but answering 'y' at the prompt deletes the index."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index
        mock_client.context_grounding.delete_index.return_value = None

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
            ],
            input="y\n",
        )

        assert result.exit_code == 0
        mock_client.context_grounding.delete_index.assert_called_once()

    def test_delete_with_folder_key(self, runner, mock_client, mock_env_vars):
        """delete passes folder_key when --folder-key is provided."""
        index = _make_index()
        mock_client.context_grounding.retrieve.return_value = index
        mock_client.context_grounding.delete_index.return_value = None
        folder_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "my-index",
                "--folder-key",
                folder_key,
                "--confirm",
            ],
        )

        assert result.exit_code == 0
        mock_client.context_grounding.retrieve.assert_called_once_with(
            name="my-index",
            folder_path=None,
            folder_key=folder_key,
        )
        mock_client.context_grounding.delete_index.assert_called_once_with(
            index=index,
            folder_path=None,
            folder_key=folder_key,
        )

    def test_delete_index_has_no_id(self, runner, mock_client, mock_env_vars):
        """delete raises a clean error if the retrieved index has no ID (avoids silent no-op)."""
        index = _make_index()
        index.id = None
        mock_client.context_grounding.retrieve.return_value = index

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "my-index",
                "--folder-path",
                "Shared",
                "--confirm",
            ],
        )

        assert result.exit_code != 0
        assert "no id" in result.output.lower() or "cannot" in result.output.lower()
        mock_client.context_grounding.delete_index.assert_not_called()

    def test_delete_not_found(self, runner, mock_client, mock_env_vars):
        """delete surfaces a clean not-found error."""
        mock_client.context_grounding.retrieve.side_effect = Exception(
            "ContextGroundingIndex not found"
        )

        result = runner.invoke(
            cli,
            [
                "context-grounding",
                "delete",
                "--index",
                "no-such-index",
                "--folder-path",
                "Shared",
                "--confirm",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_delete_missing_index_flag_fails(self, runner, mock_env_vars):
        """delete without --index shows usage error."""
        result = runner.invoke(
            cli, ["context-grounding", "delete", "--folder-path", "Shared", "--confirm"]
        )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# help text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_group_help(self, runner):
        """context-grounding group has correct help text."""
        result = runner.invoke(cli, ["context-grounding", "--help"])

        assert result.exit_code == 0
        assert "retrieve" in result.output
        assert "search" in result.output
        assert "ingest" in result.output
        assert "delete" in result.output

    def test_search_help(self, runner):
        """search command exposes all expected options."""
        result = runner.invoke(cli, ["context-grounding", "search", "--help"])

        assert result.exit_code == 0
        assert "--index" in result.output
        assert "--limit" in result.output
        assert "--folder-path" in result.output
        assert "--folder-key" in result.output
        assert "--format" in result.output

    def test_retrieve_help(self, runner):
        """retrieve command exposes --index and folder options."""
        result = runner.invoke(cli, ["context-grounding", "retrieve", "--help"])

        assert result.exit_code == 0
        assert "--index" in result.output
        assert "--folder-path" in result.output

    def test_delete_help(self, runner):
        """delete command exposes --confirm and --dry-run."""
        result = runner.invoke(cli, ["context-grounding", "delete", "--help"])

        assert result.exit_code == 0
        assert "--confirm" in result.output
        assert "--dry-run" in result.output
