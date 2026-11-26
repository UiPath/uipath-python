import pytest

from uipath._cli._utils._auth_header import with_current_access_token


def test_leaves_the_bearer_alone_when_no_renewal_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "changed")

    assert with_current_access_token({"Authorization": "Bearer old"}) == {
        "Authorization": "Bearer old"
    }


@pytest.mark.usefixtures("token_renewal_running")
def test_replaces_the_bearer_with_the_environment_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "renewed")
    headers = {"Authorization": "Bearer old", "X-Other": "kept"}

    result = with_current_access_token(headers)

    assert result == {"Authorization": "Bearer renewed", "X-Other": "kept"}
    assert headers["Authorization"] == "Bearer old", "the caller's dict is untouched"


@pytest.mark.usefixtures("token_renewal_running")
def test_keeps_the_bearer_when_the_variable_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)

    assert with_current_access_token({"Authorization": "Bearer old"}) == {
        "Authorization": "Bearer old"
    }


@pytest.mark.usefixtures("token_renewal_running")
def test_adds_nothing_when_no_bearer_was_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "renewed")

    assert with_current_access_token({"X-Other": "kept"}) == {"X-Other": "kept"}
