from uipath.platform.common import ExecutionSourceContext, UiPathExecutionContext


def test_execution_source_none_by_default() -> None:
    assert UiPathExecutionContext().execution_source is None


def test_execution_source_set_within_context() -> None:
    ctx = UiPathExecutionContext()

    with ExecutionSourceContext("runtime"):
        assert ctx.execution_source == "runtime"

    assert ctx.execution_source is None


def test_execution_source_context_restores_previous_value() -> None:
    ctx = UiPathExecutionContext()

    with ExecutionSourceContext("eval"):
        assert ctx.execution_source == "eval"
        with ExecutionSourceContext("playground"):
            assert ctx.execution_source == "playground"
        assert ctx.execution_source == "eval"

    assert ctx.execution_source is None
