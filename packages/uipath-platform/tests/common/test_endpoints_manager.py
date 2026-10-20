import pytest

from uipath.platform.common._endpoints_manager import EndpointManager


@pytest.mark.parametrize("service", ["", "agenthub", "orchestrator"])
def test_vendor_decisions_endpoint_is_always_agenthub(
    monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    monkeypatch.setenv("UIPATH_LLM_SERVICE", service)

    assert (
        EndpointManager.get_vendor_decisions_endpoint()
        == "agenthub_/llm/raw/vendor/{vendor}/model/{model}/decisions"
    )


def test_vendor_completion_endpoint_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UIPATH_LLM_SERVICE", "agenthub")

    assert (
        EndpointManager.get_vendor_endpoint()
        == "agenthub_/llm/raw/vendor/{vendor}/model/{model}/completions"
    )
