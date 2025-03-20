import logging
import os
from os import environ as env
from typing import Generator, Optional

import httpx
import pytest
from langchain.embeddings import CacheBackedEmbeddings
from langchain.globals import set_llm_cache
from langchain.storage import LocalFileStore
from langchain_community.cache import SQLiteCache

from uipath_langchain.embeddings import UiPathOpenAIEmbeddings
from uipath_langchain.utils._settings import uipath_cached_paths_settings


def get_token():
    url_get_token = f"{env.get('UIPATH_URL', '').rstrip('/')}/identity_/connect/token"

    token_credentials = {
        "client_id": env.get("UIPATH_CLIENT_ID"),
        "client_secret": env.get("UIPATH_CLIENT_SECRET"),
        "grant_type": "client_credentials",
    }

    try:
        with httpx.Client() as client:
            response = client.post(url_get_token, data=token_credentials)
            response.raise_for_status()
            res_json = response.json()
            token = res_json.get("access_token")

            if not token:
                pytest.skip("Authentication token is empty or missing")
    except (httpx.HTTPError, ValueError, KeyError) as e:
        pytest.skip(f"Failed to obtain authentication token: {str(e)}")

    return token


@pytest.fixture(autouse=True)
def setup_test_env():
    env["UIPATH_ACCESS_TOKEN"] = get_token()


@pytest.fixture(scope="session")
def cached_llmgw_calls() -> Generator[Optional[SQLiteCache], None, None]:
    if not os.environ.get("UIPATH_TESTS_CACHE_LLMGW"):
        yield None
    else:
        logging.info("Setting up LLMGW cache")
        db_path = uipath_cached_paths_settings.cached_completion_db
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        cache = SQLiteCache(database_path=db_path)
        set_llm_cache(cache)
        yield cache
    set_llm_cache(None)
    return


@pytest.fixture(scope="session")
def cached_embedder() -> Generator[Optional[CacheBackedEmbeddings], None, None]:
    if not os.environ.get("UIPATH_TESTS_CACHE_LLMGW"):
        yield None
    else:
        logging.info("Setting up embeddings cache")
        model = "text-embedding-3-large"
        embedder = CacheBackedEmbeddings.from_bytes_store(
            underlying_embeddings=UiPathOpenAIEmbeddings(model=model),
            document_embedding_cache=LocalFileStore(
                uipath_cached_paths_settings.cached_embeddings_dir
            ),
            namespace=model,
        )
        yield embedder
    return
