import os

from uipath.platform import UiPath


def test_list_folders():
    sdk = UiPath(
        base_url=os.environ["UIPATH_URL"],
        client_id=os.environ["UIPATH_CLIENT_ID"],
        client_assertion=os.environ["UIPATH_CLIENT_ASSERTION"],
        scope="OR.Folders.Read",
    )

    response = sdk.api_client.request(
        "GET", "/orchestrator_/odata/Folders", params={"$top": 1}
    )

    assert response.status_code == 200
