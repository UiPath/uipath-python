# mypy: disable-error-code="syntax"
import os
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings


class UiPathCachedPathsSettings(BaseSettings):
    cached_completion_db: str = Field(
        default=os.path.join(
            os.path.dirname(__file__), "tests", "tests_uipath_cache.db"
        ),
        alias="CACHED_COMPLETION_DB",
    )
    cached_embeddings_dir: str = Field(
        default=os.path.join(os.path.dirname(__file__), "tests", "cached_embeddings"),
        alias="CACHED_EMBEDDINGS_DIR",
    )


uipath_cached_paths_settings = UiPathCachedPathsSettings()
uipath_token_header: Optional[str] = None


class UiPathClientFactorySettings(BaseSettings):
    base_url: str = Field(default="", alias="UIPATH_BASE_URL")
    client_id: str = Field(default="", alias="UIPATH_CLIENT_ID")
    client_secret: str = Field(default="", alias="UIPATH_CLIENT_SECRET")


class UiPathClientSettings(BaseSettings):
    access_token: str = Field(default_factory=lambda: get_uipath_token_header())
    base_url: str = Field(default="", alias="UIPATH_BASE_URL")
    org_id: str = Field(default="", alias="UIPATH_ORGANIZATION_ID")
    tenant_id: str = Field(default="", alias="UIPATH_TENANT_ID")
    requesting_product: str = Field(default="", alias="UIPATH_REQUESTING_PRODUCT")
    requesting_feature: str = Field(default="", alias="UIPATH_REQUESTING_FEATURE")
    timeout_seconds: str = Field(default="120", alias="UIPATH_TIMEOUT_SECONDS")
    action_name: str = Field(default="DefaultActionName", alias="UIPATH_ACTION_NAME")
    action_id: str = Field(default="DefaultActionId", alias="UIPATH_ACTION_ID")


class UiPathEndpoints(Enum):
    NORMALIZED_COMPLETION_ENDPOINT = "llmgateway_/api/chat/completions"
    PASSTHROUGH_COMPLETION_ENDPOINT = "llmgateway_/openai/deployments/{model}/chat/completions?api-version={api_version}"
    EMBEDDING_ENDPOINT = (
        "llmgateway_/openai/deployments/{model}/embeddings?api-version={api_version}"
    )


def get_uipath_token_header(
    settings: Any = None,
) -> str:
    global uipath_token_header
    if not uipath_token_header:
        settings = settings or UiPathClientFactorySettings()
        url_get_token = f"{settings.base_url}/identity_/connect/token"
        token_credentials = dict(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            grant_type="client_credentials",
        )
        with httpx.Client() as client:
            res = client.post(url_get_token, data=token_credentials)
            res_json = res.json()
            uipath_token_header = res_json.get("access_token")

    return uipath_token_header or ""


async def get_token_header_async(
    settings: Any = None,
) -> str:
    global uipath_token_header
    if not uipath_token_header:
        settings = settings or UiPathClientFactorySettings()
        url_get_token = f"{settings.base_url}/identity_/connect/token"
        token_credentials = dict(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            grant_type="client_credentials",
        )

        with httpx.Client() as client:
            res_json = client.post(url_get_token, data=token_credentials).json()
            uipath_token_header = res_json.get("access_token")

    return uipath_token_header or ""
