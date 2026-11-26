import asyncio
import contextlib
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pysignalr.messages import CompletionMessage

from uipath._cli._debug import _bridge
from uipath._cli._debug._bridge import SignalRDebugBridge
from uipath.runtime import (
    UiPathBreakpointResult,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)


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


async def _seconds_to_disconnect(bridge: SignalRDebugBridge) -> float:
    loop = asyncio.get_running_loop()
    started = loop.time()
    await bridge.disconnect()
    return loop.time() - started


def _bridge_with(send: Any) -> SignalRDebugBridge:
    bridge = SignalRDebugBridge(hub_url="https://hub.example/signalr/robotdebug")
    bridge._client = AsyncMock(send=send)
    bridge._run_task = asyncio.create_task(asyncio.sleep(0))
    return bridge


def _completed() -> UiPathRuntimeResult:
    return UiPathRuntimeResult(status=UiPathRuntimeStatus.SUCCESSFUL)


async def test_a_send_the_connection_closes_under_does_not_hold_up_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_bridge, "SEND_ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 10.0)
    in_send = asyncio.Event()
    release_send = asyncio.Event()

    async def send(**_: Any) -> None:
        in_send.set()
        await release_send.wait()

    bridge = _bridge_with(send)
    emitting = asyncio.create_task(bridge.emit_execution_completed(_completed()))
    await in_send.wait()
    await bridge._handle_close()
    release_send.set()
    await emitting

    assert await _seconds_to_disconnect(bridge) < 5


@pytest.mark.parametrize(
    "failure", [RuntimeError("Connection is closed"), asyncio.CancelledError()]
)
async def test_a_send_that_fails_does_not_hold_up_disconnect(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    monkeypatch.setattr(_bridge, "SEND_ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 10.0)
    bridge = _bridge_with(AsyncMock(side_effect=failure))

    with contextlib.suppress(asyncio.CancelledError):
        await bridge.emit_execution_completed(_completed())

    assert await _seconds_to_disconnect(bridge) < 5


async def test_a_completion_for_a_cancelled_send_is_ignored() -> None:
    completion_handlers: list[Any] = []

    async def send(*, on_invocation: Any, **_: Any) -> None:
        completion_handlers.append(on_invocation)
        raise asyncio.CancelledError

    bridge = _bridge_with(send)
    with contextlib.suppress(asyncio.CancelledError):
        await bridge.emit_execution_completed(_completed())

    assert await completion_handlers[0](CompletionMessage(invocation_id="1")) is None


async def test_connect_sends_the_token_currently_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, token_renewal_running: None
) -> None:
    from unittest.mock import patch

    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "renewed-token")
    bridge = SignalRDebugBridge(
        hub_url="https://hub.example/signalr/robotdebug",
        access_token="startup-token",
        headers={"X-Keep": "yes"},
    )
    seen: dict[str, Any] = {}

    class FakeSignalRClient:
        def __init__(self, url: str, headers: dict[str, str]) -> None:
            seen["url"] = url
            seen["headers"] = headers
            self._on_open: Any = None

        def on(self, event: str, handler: Any) -> None:
            pass

        def on_open(self, handler: Any) -> None:
            self._on_open = handler

        def on_close(self, handler: Any) -> None:
            pass

        def on_error(self, handler: Any) -> None:
            pass

        async def run(self) -> None:
            await self._on_open()

    with patch("pysignalr.client.SignalRClient", FakeSignalRClient):
        await bridge.connect()

    assert seen["headers"]["Authorization"] == "Bearer renewed-token"
    assert seen["headers"]["X-Keep"] == "yes"
    assert bridge.access_token == "startup-token"
