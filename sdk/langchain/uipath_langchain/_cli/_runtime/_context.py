from typing import Any, Optional, Union

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph
from langgraph.types import StateSnapshot
from uipath_sdk._cli._runtime._contracts import ExecutionResult, RuntimeContext

from .._utils._graph import LangGraphConfig


class LangGraphRuntimeContext(RuntimeContext):
    """Context information passed throughout the runtime execution."""

    langgraph_config: Optional[LangGraphConfig] = None
    state_graph: Optional[StateGraph] = None
    output: Optional[Any] = None
    state: Optional[StateSnapshot] = None
    memory: Optional[AsyncSqliteSaver] = None
    result: Optional[ExecutionResult] = None
    langsmith_tracing_enabled: Union[str, bool, None] = False
    db_path: str = "uipath.db"
    resume_triggers_table: str = "__uipath_resume_triggers"
