import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer
from pysignalr.client import SignalRClient

from uipath._cli._debug._bridge import SignalRDebugBridge

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
