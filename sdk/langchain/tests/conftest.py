import logging
import os
from typing import Generator

import pytest
from langchain.embeddings import CacheBackedEmbeddings
from langchain.globals import set_llm_cache
from langchain.storage import LocalFileStore
from langchain_community.cache import SQLiteCache

from uipath_langchain.embeddings import UiPathOpenAIEmbeddings
from uipath_langchain.utils._settings import uipath_cached_paths_settings


@pytest.fixture(autouse=True)
def setup_test_env():
    """Fixture to set up test environment variables."""
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv())


@pytest.fixture(scope="session")
def cached_llmgw_calls() -> Generator[SQLiteCache | None, None, None]:
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
def cached_embedder() -> Generator[CacheBackedEmbeddings | None, None, None]:
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
