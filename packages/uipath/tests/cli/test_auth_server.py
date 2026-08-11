"""Security tests for the OAuth local callback server.

Covers GHSA-32xc-7x5c-8vmf: the `/set_token` and `/log` endpoints must reject
unauthenticated POSTs (no / wrong OAuth `state`), and the server must bind to
loopback only rather than all interfaces.
"""

import json
import os
import threading
import urllib.error
import urllib.request

from uipath._cli._auth._auth_server import HTTPServer

STATE = "LEGITIMATE_OAUTH_STATE_ABCDE12345"
CODE_VERIFIER = "LEGITIMATE_PKCE_CODE_VERIFIER"
DOMAIN = "cloud.uipath.com"

ATTACKER_PAYLOAD = {
    "access_token": "attacker-token",
    "refresh_token": "attacker-refresh",
    "expires_in": 3600,
    "token_type": "Bearer",
    "scope": "offline_access",
}


def _request(port, path, data, headers=None, method="POST"):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _post(port, path, body, headers=None):
    return _request(
        port,
        path,
        json.dumps(body).encode("utf-8"),
        {"Content-Type": "application/json", **(headers or {})},
    )


async def test_endpoints_reject_unauthenticated_posts(tmp_path, monkeypatch):
    """Only requests carrying the matching OAuth state are accepted.

    Exercises both /set_token and /log with missing, wrong, and valid state.
    """
    monkeypatch.chdir(tmp_path)

    # Binding happens in create_server; the listen socket is up before the
    # handler thread starts, so connections queue and no readiness sleep is
    # needed. redirect_uri/client_id are required by the GET (index.html) path.
    server = HTTPServer(
        port=0, redirect_uri="http://localhost/callback", client_id="test-client"
    )
    httpd = server.create_server(STATE, CODE_VERIFIER, DOMAIN)
    port = httpd.server_address[1]

    results = {}

    def client():
        # DNS rebinding
        results["rebind_get"] = _request(
            port, "/", None, {"Host": "not-localhost.com"}, method="GET"
        )
        results["rebind_post"] = _post(
            port,
            "/set_token",
            ATTACKER_PAYLOAD,
            {"X-Auth-State": STATE, "Host": "evil.com"},
        )
        # GET serves index.html with the OAuth params substituted in.
        results["get"] = _request(port, "/anything", None, method="GET")
        # /set_token: missing and wrong state are rejected.
        results["set_missing"] = _post(port, "/set_token", ATTACKER_PAYLOAD)
        results["set_wrong"] = _post(
            port, "/set_token", ATTACKER_PAYLOAD, {"X-Auth-State": "not-the-state"}
        )
        # Valid state but a non-JSON body -> graceful 400, not 500.
        results["set_malformed"] = _request(
            port, "/set_token", b"not json", {"X-Auth-State": STATE}
        )
        # Unknown path -> 404.
        results["unknown"] = _post(port, "/nope", {"x": 1}, {"X-Auth-State": STATE})
        # /log: missing and valid state.
        results["log_missing"] = _post(port, "/log", {"msg": "x"})
        results["log_valid"] = _post(
            port, "/log", {"msg": "x"}, {"X-Auth-State": STATE}
        )
        # Valid /set_token last, to capture the token and unblock start().
        results["set_valid"] = _post(
            port, "/set_token", {"access_token": "real"}, {"X-Auth-State": STATE}
        )

    t = threading.Thread(target=client, daemon=True)
    t.start()
    token_data = await server.start(STATE, CODE_VERIFIER, DOMAIN)
    t.join(timeout=5)

    # DNS rebinding: forged Host is rejected on both GET and POST.
    assert results["rebind_get"][0] == 403
    assert results["rebind_post"][0] == 403

    # GET returns the page with the real state injected, placeholder gone.
    assert results["get"][0] == 200
    assert STATE in results["get"][1]
    assert "__PY_REPLACE_EXPECTED_STATE__" not in results["get"][1]

    assert results["set_missing"][0] == 403
    assert results["set_wrong"][0] == 403
    assert results["set_malformed"][0] == 400
    assert results["unknown"][0] == 404
    assert results["log_missing"][0] == 403
    assert results["log_valid"][0] == 200
    assert results["set_valid"][0] == 200

    # Only the valid, state-bearing request was accepted.
    assert token_data == {"access_token": "real"}
    # The state-protected /log write happened for the valid request only.
    assert os.path.exists(tmp_path / ".uipath" / ".error_log")


def test_server_binds_to_loopback_only():
    server = HTTPServer(port=0)
    httpd = server.create_server(STATE, CODE_VERIFIER, DOMAIN)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()
