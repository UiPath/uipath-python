from typing import Any, Optional, Union

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph
from uipath._cli._runtime._contracts import UiPathRuntimeContext

from .._utils._graph import LangGraphConfig


class LangGraphRuntimeContext(UiPathRuntimeContext):
    """Context information passed throughout the runtime execution."""

    langgraph_config: Optional[LangGraphConfig] = None
    state_graph: Optional[StateGraph] = None
    output: Optional[Any] = None
    state: Optional[Any] = (
        None  # TypedDict issue, the actual type is: Optional[langgraph.types.StateSnapshot]
    )
    memory: Optional[AsyncSqliteSaver] = None
    langsmith_tracing_enabled: Union[str, bool, None] = False
    resume_triggers_table: str = "__uipath_resume_triggers"
