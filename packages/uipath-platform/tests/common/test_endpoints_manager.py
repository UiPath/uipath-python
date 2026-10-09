import pytest

from uipath.platform.common._endpoints_manager import EndpointManager


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        ("agenthub", "agenthub_/llm/raw/vendor/{vendor}/model/{model}/decisions"),
        (
            "orchestrator",
            "orchestrator_/llm/raw/vendor/{vendor}/model/{model}/decisions",
        ),
    ],
)
def test_vendor_decisions_endpoint_follows_the_llm_service(
    monkeypatch: pytest.MonkeyPatch, service: str, expected: str
) -> None:
    monkeypatch.setenv("UIPATH_LLM_SERVICE", service)

    assert EndpointManager.get_vendor_decisions_endpoint() == expected


def test_vendor_completion_endpoint_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UIPATH_LLM_SERVICE", "agenthub")

    assert (
        EndpointManager.get_vendor_endpoint()
        == "agenthub_/llm/raw/vendor/{vendor}/model/{model}/completions"
    )
