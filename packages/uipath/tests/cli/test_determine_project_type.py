from uipath._cli._utils._common import determine_project_type
from uipath._cli.models.runtime_schema import EntryPoint


def _make_entrypoint(type: str) -> EntryPoint:
    return EntryPoint(
        file_path="test",
        unique_id="00000000-0000-0000-0000-000000000000",
        type=type,
        input={"type": "object", "properties": {}},
        output={"type": "string"},
    )


class TestDetermineProjectType:
    def test_empty_entrypoints_returns_function(self) -> None:
        assert determine_project_type([]) == "function"

    def test_single_agent_entrypoint(self) -> None:
        assert determine_project_type([_make_entrypoint("agent")]) == "agent"

    def test_single_function_entrypoint(self) -> None:
        assert determine_project_type([_make_entrypoint("function")]) == "function"

    def test_multiple_same_type(self) -> None:
        entrypoints = [_make_entrypoint("agent"), _make_entrypoint("agent")]
        assert determine_project_type(entrypoints) == "agent"

    def test_mixed_types_returns_first(self) -> None:
        entrypoints = [_make_entrypoint("agent"), _make_entrypoint("function")]
        assert determine_project_type(entrypoints) == "agent"

    def test_mixed_types_returns_first_function(self) -> None:
        entrypoints = [_make_entrypoint("function"), _make_entrypoint("agent")]
        assert determine_project_type(entrypoints) == "function"

    def test_mixed_types_logs_warning(self, capsys) -> None:
        entrypoints = [_make_entrypoint("agent"), _make_entrypoint("function")]
        determine_project_type(entrypoints)
        captured = capsys.readouterr()
        assert "Mixed entrypoint types detected: [agent, function]" in captured.out
        assert '"agent"' in captured.out
        assert "We recommend using a single type for all entrypoints" in captured.out

    def test_same_types_no_warning(self, capsys) -> None:
        entrypoints = [_make_entrypoint("agent"), _make_entrypoint("agent")]
        determine_project_type(entrypoints)
        captured = capsys.readouterr()
        assert "Mixed entrypoint types detected" not in captured.out
