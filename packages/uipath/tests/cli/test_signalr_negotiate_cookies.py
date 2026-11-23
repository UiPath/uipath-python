import asyncio

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer
from pysignalr.client import SignalRClient

RECORD_SEPARATOR = "\x1e"


async def test_websocket_upgrade_sends_the_negotiate_cookie() -> None:
    upgrade_cookies: list[str | None] = []

    async def negotiate(request: web.Request) -> web.Response:
        response = web.json_response({"connectionId": "conn-1", "negotiateVersion": 0})
        response.set_cookie("affinity", "backend-1")
        return response

    async def websocket(request: web.Request) -> web.WebSocketResponse:
        upgrade_cookies.append(request.headers.get("Cookie"))
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            if message.type == WSMsgType.TEXT and '"protocol"' in message.data:
                await ws.send_str("{}" + RECORD_SEPARATOR)
        return ws

    app = web.Application()
    app.router.add_post("/hub/negotiate", negotiate)
    app.router.add_get("/hub", websocket)
    server = TestServer(app)
    await server.start_server()

    # aiohttp's default cookie jar ignores cookies from IP-address hosts.
    url = str(server.make_url("/hub")).replace("127.0.0.1", "localhost")
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
        await server.close()

    assert upgrade_cookies == ["affinity=backend-1"]
