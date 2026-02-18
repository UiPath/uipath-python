"""Tests for the AST-based call graph builder."""

import textwrap

import pytest

from uipath.functions.graph_builder import build_call_graph


@pytest.fixture
def project_dir(tmp_path):
    """Create a small multi-file project for testing."""
    # main.py — the entrypoint
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        from helpers import process_data
        from utils import format_output

        def main(input):
            result = process_data(input)
            return format_output(result)
        """)
    )

    # helpers.py — calls into a deeper utility
    (tmp_path / "helpers.py").write_text(
        textwrap.dedent("""\
        from deep import transform

        def process_data(data):
            return transform(data)

        def unused_function():
            pass
        """)
    )

    # utils.py — leaf function
    (tmp_path / "utils.py").write_text(
        textwrap.dedent("""\
        def format_output(data):
            return str(data)
        """)
    )

    # deep.py — deeper than default depth
    (tmp_path / "deep.py").write_text(
        textwrap.dedent("""\
        def transform(data):
            return data
        """)
    )

    return tmp_path


def test_basic_graph_structure(project_dir):
    """Entrypoint node and its direct callees are discovered."""
    graph = build_call_graph(
        str(project_dir / "main.py"),
        "main",
        project_dir=str(project_dir),
        max_depth=3,
    )

    node_names = {n.name for n in graph.nodes}

    # Should contain main, process_data, format_output, transform
    assert "main" in node_names
    assert "process_data" in node_names
    assert "format_output" in node_names
    assert "transform" in node_names

    # unused_function should NOT appear
    assert "unused_function" not in node_names


def test_node_ids_are_file_line(project_dir):
    """Node IDs must follow the file:line format for breakpoints."""
    graph = build_call_graph(
        str(project_dir / "main.py"),
        "main",
        project_dir=str(project_dir),
    )

    for node in graph.nodes:
        parts = node.id.rsplit(":", 1)
        assert len(parts) == 2, f"Node ID '{node.id}' is not in file:line format"
        assert parts[1].isdigit(), f"Line part of '{node.id}' is not a number"


def test_edges_connect_caller_to_callee(project_dir):
    """Edges should go from caller to callee."""
    graph = build_call_graph(
        str(project_dir / "main.py"),
        "main",
        project_dir=str(project_dir),
    )

    id_to_name = {n.id: n.name for n in graph.nodes}
    edge_pairs = {(id_to_name[e.source], id_to_name[e.target]) for e in graph.edges}

    assert ("main", "process_data") in edge_pairs
    assert ("main", "format_output") in edge_pairs
    assert ("process_data", "transform") in edge_pairs


def test_max_depth_limits_recursion(project_dir):
    """Setting max_depth=1 should only include the entrypoint and its direct calls."""
    graph = build_call_graph(
        str(project_dir / "main.py"),
        "main",
        project_dir=str(project_dir),
        max_depth=1,
    )

    node_names = {n.name for n in graph.nodes}

    assert "main" in node_names
    assert "process_data" in node_names
    assert "format_output" in node_names
    # transform is 2 levels deep, should be excluded
    assert "transform" not in node_names


def test_no_duplicates_on_repeated_calls(tmp_path):
    """A function called multiple times should appear as one node."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        def helper():
            pass

        def main():
            helper()
            helper()
            helper()
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    names = [n.name for n in graph.nodes]
    assert names.count("helper") == 1
    # But there can be multiple edges (one per call site)


def test_local_function_calls(tmp_path):
    """Functions defined in the same file are resolved."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        def step_a():
            pass

        def step_b():
            step_a()

        def main():
            step_b()
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    node_names = {n.name for n in graph.nodes}
    assert node_names == {"main", "step_b", "step_a"}


def test_async_functions(tmp_path):
    """Async function definitions and await calls are handled."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        async def helper():
            pass

        async def main():
            await helper()
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    node_names = {n.name for n in graph.nodes}
    assert node_names == {"main", "helper"}


def test_external_calls_ignored(tmp_path):
    """Calls to external/unknown functions produce no nodes."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        import json

        def main(data):
            return json.dumps(data)
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    assert len(graph.nodes) == 1
    assert graph.nodes[0].name == "main"
    assert len(graph.edges) == 0


def test_missing_function_returns_empty_graph(tmp_path):
    """If the entrypoint function doesn't exist, return an empty graph."""
    (tmp_path / "main.py").write_text("def other(): pass\n")

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_relative_import(tmp_path):
    """Relative imports (from .module import func) are resolved."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    (pkg / "main.py").write_text(
        textwrap.dedent("""\
        from .helpers import do_work

        def main():
            do_work()
        """)
    )
    (pkg / "helpers.py").write_text(
        textwrap.dedent("""\
        def do_work():
            pass
        """)
    )

    graph = build_call_graph(
        str(pkg / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    node_names = {n.name for n in graph.nodes}
    assert "main" in node_names
    assert "do_work" in node_names


def test_node_id_uses_last_body_line(tmp_path):
    """Node ID should point to the last statement in the function body."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        def main(input):
            x = input.get("value", 10)
            y = x * 2
            return {"result": y}
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    # Last body line is "return {"result": y}" at line 4
    assert node.id == "main.py:4"


def test_node_id_last_line_with_docstring(tmp_path):
    """Docstring should not affect the last body line calculation."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        def main(input):
            \"\"\"This is a docstring.\"\"\"
            x = 1
            y = 2
            return x + y
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    # Last body line is "return x + y" at line 5
    assert node.id == "main.py:5"


def test_module_attribute_call(tmp_path):
    """import module; module.func() pattern is resolved."""
    (tmp_path / "mymod.py").write_text(
        textwrap.dedent("""\
        def compute():
            pass
        """)
    )
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        import mymod

        def main():
            mymod.compute()
        """)
    )

    graph = build_call_graph(
        str(tmp_path / "main.py"),
        "main",
        project_dir=str(tmp_path),
    )

    node_names = {n.name for n in graph.nodes}
    assert "compute" in node_names
