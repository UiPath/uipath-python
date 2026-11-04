import json
from typing import Any
from unittest.mock import AsyncMock

from uipath._cli._debug._bridge import SignalRDebugBridge
from uipath.runtime import UiPathBreakpointResult


async def _sent_breakpoint_hit(
    breakpoint_result: UiPathBreakpointResult,
) -> tuple[str, dict[str, Any]]:
    bridge = SignalRDebugBridge(hub_url="https://hub.example/signalr/robotdebug")
    hub_client = AsyncMock()
    bridge._client = hub_client

    await bridge.emit_breakpoint_hit(breakpoint_result)

    event_name, payload_json = hub_client.send.await_args.kwargs["arguments"]
    return event_name, json.loads(payload_json)


async def test_breakpoint_hit_carries_the_paused_function_start_line() -> None:
    sent = await _sent_breakpoint_hit(
        UiPathBreakpointResult(
            breakpoint_node="calc.py:7",
            breakpoint_type="before",
            current_state={"total": 6},
            next_nodes=[],
            metadata={"function_start_line": 5},
        )
    )

    assert sent == (
        "OnBreakpointHit",
        {
            "node": "calc.py:7",
            "type": "before",
            "state": {"total": 6},
            "nextNodes": [],
            "functionStartLine": 5,
        },
    )


async def test_breakpoint_hit_without_a_function_start_line_keeps_its_shape() -> None:
    sent = await _sent_breakpoint_hit(
        UiPathBreakpointResult(
            breakpoint_node="classify",
            breakpoint_type="after",
            current_state={"label": "spam"},
            next_nodes=["route"],
        )
    )

    assert sent == (
        "OnBreakpointHit",
        {
            "node": "classify",
            "type": "after",
            "state": {"label": "spam"},
            "nextNodes": ["route"],
        },
    )
