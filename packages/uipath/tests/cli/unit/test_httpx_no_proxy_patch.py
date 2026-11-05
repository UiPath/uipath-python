import logging
import os

import httpx
import pytest

from uipath._cli._utils import _httpx_no_proxy_patch
from uipath._cli._utils._httpx_no_proxy_patch import remove_unsupported_no_proxy_entries
from uipath.platform.common import get_httpx_client_kwargs


@pytest.fixture(autouse=True)
def proxy_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("HTTPS_PROXY", "http://10.0.6.4:3128/")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    return monkeypatch


@pytest.mark.parametrize(
    "value, expected",
    [
        ("localhost,10.0.0.0/8,fc00::/7,.svc", "localhost,10.0.0.0/8,.svc"),
        ("localhost, fe80::/10 ,::1", "localhost,::1"),
        ("127.0.0.1,[::1],[::1]:8080,[fc00::]/7", "127.0.0.1"),
        ("localhost,::1,fc00::1,10.0.0.0/8,host/path", None),
    ],
)
def test_removes_entries_httpx_cannot_parse(
    proxy_env: pytest.MonkeyPatch, value: str, expected: str | None
) -> None:
    proxy_env.setenv("NO_PROXY", value)

    remove_unsupported_no_proxy_entries()

    assert os.environ["NO_PROXY"] == (expected or value)
    httpx.Client(**get_httpx_client_kwargs()).close()


def test_cleans_lowercase_variable(proxy_env: pytest.MonkeyPatch) -> None:
    proxy_env.setenv("no_proxy", "localhost,fc00::/7")

    remove_unsupported_no_proxy_entries()

    assert os.environ["no_proxy"] == "localhost"
    httpx.Client(**get_httpx_client_kwargs()).close()


def test_logs_removed_entries(
    proxy_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    proxy_env.setenv("NO_PROXY", "localhost,fc00::/7")
    logger = logging.getLogger(_httpx_no_proxy_patch.__name__)
    logger.addHandler(caplog.handler)
    try:
        remove_unsupported_no_proxy_entries()
    finally:
        logger.removeHandler(caplog.handler)

    assert "Removed fc00::/7 from NO_PROXY" in caplog.text
