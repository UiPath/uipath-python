import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

import pytest
from aiohttp import WSCloseCode, WSMsgType, web
from aiohttp.test_utils import TestServer
from pysignalr.client import SignalRClient

from uipath._cli._debug import _bridge
from uipath._cli._debug._bridge import SignalRDebugBridge
from uipath.runtime import UiPathRuntimeResult, UiPathRuntimeStatus

RECORD_SEPARATOR = "\x1e"


class _Hub:
    def __init__(self) -> None:
        self.upgrade_cookies: list[str | None] = []
        self.invocations: list[dict[str, Any]] = []

    async def negotiate(self, request: web.Request) -> web.Response:
        response = web.json_response({"connectionId": "conn-1", "negotiateVersion": 0})
        response.set_cookie("affinity", "backend-1")
        return response

    async def websocket(self, request: web.Request) -> web.WebSocketResponse:
        self.upgrade_cookies.append(request.headers.get("Cookie"))
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue
            for record in filter(None, message.data.split(RECORD_SEPARATOR)):
                frame = json.loads(record)
                if "protocol" in frame:
                    await ws.send_str("{}" + RECORD_SEPARATOR)
                elif frame.get("type") == 1:
                    self.invocations.append(frame)
                    if "invocationId" in frame:
                        completion = {
                            "type": 3,
                            "invocationId": frame["invocationId"],
                            "error": "command rejected",
                        }
                        await ws.send_str(json.dumps(completion) + RECORD_SEPARATOR)
        return ws


@pytest.fixture
async def hub() -> AsyncIterator[tuple[_Hub, str]]:
    state = _Hub()
    app = web.Application()
    app.router.add_post("/hub/negotiate", state.negotiate)
    app.router.add_get("/hub", state.websocket)
    server = TestServer(app)
    await server.start_server()
    # aiohttp's default cookie jar ignores cookies from IP-address hosts.
    yield state, str(server.make_url("/hub")).replace("127.0.0.1", "localhost")
    await server.close()


async def test_websocket_upgrade_sends_the_negotiate_cookie(
    hub: tuple[_Hub, str],
) -> None:
    state, url = hub
    client = SignalRClient(url, connection_timeout=1)
    opened = asyncio.Event()

    async def on_open() -> None:
        opened.set()

    client.on_open(on_open)
    run_task = asyncio.create_task(client.run())
    try:
        await asyncio.wait_for(opened.wait(), timeout=5)
    finally:
        run_task.cancel()
        await asyncio.gather(run_task, return_exceptions=True)

    assert state.upgrade_cookies == ["affinity=backend-1"]


async def test_hub_side_send_error_reaches_the_error_handler(
    hub: tuple[_Hub, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    state, url = hub
    bridge = SignalRDebugBridge(hub_url=url)
    errors: list[Any] = []

    async def record_error(error: Any) -> None:
        errors.append(error)

    monkeypatch.setattr(bridge, "_handle_error", record_error)
    await bridge.connect()
    try:
        await bridge._send("OnExecutionStarted", {"job": "1"})
        for _ in range(50):
            if errors:
                break
            await asyncio.sleep(0.05)
    finally:
        await bridge.disconnect()

    assert state.invocations[0]["target"] == "SendCommand"
    assert "invocationId" in state.invocations[0]
    assert [error.error for error in errors] == ["command rejected"]


class _RelayHub:
    def __init__(
        self,
        *,
        acknowledges: bool = True,
        ends_connection: Literal["abort", "close_with_error"] | None = None,
    ) -> None:
        self.acknowledges = acknowledges
        self.ends_connection = ends_connection
        self.relayed: list[str] = []

    async def negotiate(self, request: web.Request) -> web.Response:
        return web.json_response({"connectionId": "conn-1", "negotiateVersion": 0})

    async def websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        dispatcher = asyncio.create_task(self._dispatch(ws, commands))
        try:
            async for message in ws:
                if message.type != WSMsgType.TEXT:
                    continue
                for record in filter(None, message.data.split(RECORD_SEPARATOR)):
                    frame = json.loads(record)
                    if "protocol" in frame:
                        await ws.send_str("{}" + RECORD_SEPARATOR)
                    elif frame.get("type") == 1 and self.ends_connection == "abort":
                        await ws.close(code=WSCloseCode.MESSAGE_TOO_BIG)
                    elif frame.get("type") == 1 and self.ends_connection:
                        close = {"type": 7, "error": "Connection closed with an error."}
                        await ws.send_str(json.dumps(close) + RECORD_SEPARATOR)
                        await ws.close()
                    elif frame.get("type") == 1:
                        commands.put_nowait(frame)
        finally:
            dispatcher.cancel()
            await asyncio.gather(dispatcher, return_exceptions=True)
        return ws

    async def _dispatch(
        self, ws: web.WebSocketResponse, commands: asyncio.Queue[dict[str, Any]]
    ) -> None:
        while True:
            frame = await commands.get()
            await asyncio.sleep(0.05)
            self.relayed.append(frame["arguments"][0])
            if self.acknowledges:
                completion = {"type": 3, "invocationId": frame["invocationId"]}
                await ws.send_str(json.dumps(completion) + RECORD_SEPARATOR)


@pytest.fixture
async def serve() -> AsyncIterator[Callable[[_RelayHub], Awaitable[str]]]:
    servers: list[TestServer] = []

    async def start(state: _RelayHub) -> str:
        app = web.Application()
        app.router.add_post("/hub/negotiate", state.negotiate)
        app.router.add_get("/hub", state.websocket)
        server = TestServer(app)
        await server.start_server()
        servers.append(server)
        return str(server.make_url("/hub"))

    yield start
    for server in servers:
        await server.close()


def _completed() -> UiPathRuntimeResult:
    return UiPathRuntimeResult(
        status=UiPathRuntimeStatus.SUCCESSFUL, output={"greeting": "Hello"}
    )


async def test_disconnect_waits_until_the_hub_relays_the_last_command(
    serve: Callable[[_RelayHub], Awaitable[str]],
) -> None:
    state = _RelayHub()
    bridge = SignalRDebugBridge(hub_url=await serve(state))
    await bridge.connect()

    await bridge.emit_execution_started()
    await bridge.emit_execution_completed(_completed())
    await bridge.disconnect()

    assert state.relayed == ["OnExecutionStarted", "OnExecutionCompleted"]


async def test_disconnect_stops_waiting_for_a_hub_that_never_acknowledges(
    serve: Callable[[_RelayHub], Awaitable[str]],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(_bridge, "SEND_ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 0.5)
    state = _RelayHub(acknowledges=False)
    bridge = SignalRDebugBridge(hub_url=await serve(state))
    await bridge.connect()

    await bridge.emit_execution_completed(_completed())
    _bridge.logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger=_bridge.__name__):
            await bridge.disconnect()
    finally:
        _bridge.logger.removeHandler(caplog.handler)

    assert state.relayed == ["OnExecutionCompleted"]
    assert "before the hub acknowledged 1 command(s)" in caplog.text


@pytest.mark.parametrize("ends_connection", ["abort", "close_with_error"])
async def test_disconnect_does_not_wait_on_a_connection_the_hub_ended(
    serve: Callable[[_RelayHub], Awaitable[str]],
    monkeypatch: pytest.MonkeyPatch,
    ends_connection: Literal["abort", "close_with_error"],
) -> None:
    monkeypatch.setattr(_bridge, "SEND_ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 10.0)
    state = _RelayHub(ends_connection=ends_connection)
    bridge = SignalRDebugBridge(hub_url=await serve(state))
    await bridge.connect()
    loop = asyncio.get_running_loop()
    started = loop.time()

    await bridge.emit_execution_completed(_completed())
    await bridge.disconnect()

    assert loop.time() - started < 5


async def test_a_command_the_hub_rejects_does_not_hold_up_disconnect(
    hub: tuple[_Hub, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_bridge, "SEND_ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 10.0)
    _, url = hub
    bridge = SignalRDebugBridge(hub_url=url)
    await bridge.connect()
    loop = asyncio.get_running_loop()
    started = loop.time()

    await bridge.emit_execution_completed(_completed())
    await bridge.disconnect()

    assert loop.time() - started < 5
