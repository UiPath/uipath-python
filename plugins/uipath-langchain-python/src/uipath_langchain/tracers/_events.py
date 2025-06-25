from typing import Any, Dict, List, Literal, Optional

RUN_TYPE_T = Literal[
    "tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"
]


class CustomTraceEvents:
    UIPATH_TRACE_FUNCTION_CALL = "__uipath_trace_function_call"


class FunctionCallEventData:
    def __init__(
        self,
        function_name: str,
        event_type: str,
        inputs: Dict[str, Any],
        call_uuid: str,
        output: Any,
        error: Optional[str] = None,
        run_type: Optional[RUN_TYPE_T] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.function_name = function_name
        self.event_type = event_type
        self.inputs = inputs
        self.call_uuid = call_uuid
        self.output = output
        self.error = error
        self.run_type = run_type or "chain"
        self.tags = tags
        self.metadata = metadata
