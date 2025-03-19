from typing import Optional

import numpy as np
import pytest
from langchain_community.cache import SQLiteCache
from langchain_community.callbacks import get_openai_callback
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, ValidationError

from uipath_langchain.chat import (
    UiPathAzureChatOpenAI,
    UiPathNormalizedChatModel,
)
from uipath_langchain.embeddings import (
    UiPathAzureOpenAIEmbeddings,
    UiPathOpenAIEmbeddings,
)


def test_cached_call(cached_llmgw_calls: Optional[SQLiteCache]):
    model = UiPathAzureChatOpenAI(cache=cached_llmgw_calls)
    messages = [
        SystemMessage(content="How much is 2 + 2?"),
        HumanMessage(content="Respond with JUST THE ANSWER."),
    ]
    response = model.invoke(messages)
    assert "4" in response.content, f"Expected '4' in response, got: {response.content}"


def test_cached_call_tokens(cached_llmgw_calls: Optional[SQLiteCache]):
    model = UiPathAzureChatOpenAI(cache=cached_llmgw_calls)
    messages = [
        SystemMessage(content="How much is 2 + 2?"),
        HumanMessage(content="Respond with JUST THE ANSWER."),
    ]
    with get_openai_callback() as cb:
        _ = model.invoke(messages)
        total_tokens = cb.total_tokens
    assert total_tokens >= 20, f"Expected more than 20 tokens, got: {total_tokens}"


def test_normalized_cached_call(cached_llmgw_calls: Optional[SQLiteCache]):
    model = UiPathNormalizedChatModel(
        model="anthropic.claude-3-5-sonnet-20240620-v1:0", cache=cached_llmgw_calls
    )
    messages = [
        SystemMessage(content="How much is 2 + 2?"),
        HumanMessage(content="Respond with JUST THE ANSWER."),
    ]
    response = model.invoke(messages)
    assert "4" in response.content, f"Expected '4' in response, got: {response.content}"


def test_normalized_cached_call_tokens(cached_llmgw_calls: Optional[SQLiteCache]):
    model = UiPathNormalizedChatModel(
        model="anthropic.claude-3-5-sonnet-20240620-v1:0", cache=cached_llmgw_calls
    )
    messages = [
        SystemMessage(content="How much is 2 + 2?"),
        HumanMessage(content="Respond with JUST THE ANSWER."),
    ]
    with get_openai_callback() as cb:
        _ = model.invoke(messages)
        total_tokens = cb.total_tokens
    assert total_tokens >= 20, f"Expected more than 20 tokens, got: {total_tokens}"


def test_tool_call(cached_llmgw_calls: Optional[SQLiteCache]):
    @tool
    def get_first_letter(input):
        """
        Returns the first letter of the input
        """
        return input[0]

    model = UiPathAzureChatOpenAI(cache=cached_llmgw_calls).bind_tools(
        [get_first_letter]
    )
    messages = [
        SystemMessage(content="What is the first letter of the word 'apple'?"),
    ]
    response = model.invoke(messages)
    assert hasattr(response, "tool_calls"), (
        "The response should have a 'tool_calls' attribute"
    )
    tool_call = response.tool_calls[0]
    assert tool_call["name"] == "get_first_letter", (
        f"Expected tool call to 'get_first_letter', got: {tool_call['name']}"
    )
    assert tool_call["args"].get("input") == "apple", (
        f"Expected input to be 'apple', got: {tool_call['args'].get('input')}"
    )


def test_structured_output_call(cached_llmgw_calls: Optional[SQLiteCache]):
    class CitySize(BaseModel):
        """City and its size."""

        city: str
        size: int

    model = UiPathAzureChatOpenAI(cache=cached_llmgw_calls).with_structured_output(
        CitySize
    )
    messages = [
        SystemMessage(
            content="What is the capital of France and what is its area in square meters?"
        ),
    ]
    response = model.invoke(messages)
    try:
        city_size = CitySize.model_validate(response)
        assert city_size.city == "Paris", (
            f"Expected city to be 'Paris', got: {city_size.city}"
        )
        assert city_size.size > 0, (
            f"Expected size to be greater than 0, got: {city_size.size}"
        )
    except ValidationError as exc:
        pytest.fail(f"The response was not in the correct format: {exc}")


def test_embedding_call(cached_embedder: Optional[Embeddings]):
    if not cached_embedder:
        cached_embedder = UiPathOpenAIEmbeddings(model="text-embedding-3-large")
    data = [
        "Test input pneumonoultramicroscopicsilicovolcanoconiosis",
        "Another test input",
    ]
    embeds = cached_embedder.embed_documents(data)
    try:
        arr = np.array(embeds)
    except Exception as exc:
        pytest.fail(f"Failed to convert embeddings to numpy array: {exc}")
    assert arr.shape == (2, 3072), f"Expected shape (2, 3072), got: {arr.shape}"


def test_custom_embedding_call(cached_embedder: Optional[Embeddings]):
    if not cached_embedder:
        cached_embedder = UiPathAzureOpenAIEmbeddings(model="text-embedding-3-large")
    data = [
        "Test input pneumonoultramicroscopicsilicovolcanoconiosis",
        "Another test input",
    ]
    embeds = cached_embedder.embed_documents(data)
    try:
        arr = np.array(embeds)
    except Exception as exc:
        pytest.fail(f"Failed to convert embeddings to numpy array: {exc}")
    assert arr.shape == (2, 3072), f"Expected shape (2, 3072), got: {arr.shape}"
