import os

import pytest

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.llm_gateway_service import (
    ChatModels,
    EmbeddingModels,
    UiPathOpenAIService,
)


def get_env_var(name: str) -> str:
    """Get environment variable or skip test if not present."""
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"Environment variable {name} is not set")
    return value


class TestLLMIntegration:
    @pytest.fixture
    def llm_service(self):
        """Create an OpenAIService instance with environment variables."""
        base_url = get_env_var("UIPATH_URL")
        api_key = get_env_var("UIPATH_ACCESS_TOKEN")

        config = Config(base_url=base_url, secret=api_key)
        execution_context = ExecutionContext()
        return UiPathOpenAIService(config=config, execution_context=execution_context)

    @pytest.mark.asyncio
    async def test_embeddings_real(self, llm_service):
        """Test the embeddings function with a real API call."""
        input_text = "This is a test for embedding a sentence."

        # Make the actual API call
        result = await llm_service.embeddings(input=input_text)

        # Validate the response
        assert result is not None
        assert hasattr(result, "data")
        assert len(result.data) > 0
        assert hasattr(result.data[0], "embedding")
        assert len(result.data[0].embedding) > 0
        assert hasattr(result, "model")
        assert hasattr(result, "usage")
        assert result.usage.prompt_tokens > 0

    @pytest.mark.asyncio
    async def test_embeddings_usage_real(self, llm_service):
        """Test the embeddings_usage function with a real API call."""
        input_text = "Testing the embedding usage endpoint."

        # Make the actual API call
        result = await llm_service.embeddings_usage(input=input_text)

        # Validate the response
        assert result is not None
        assert hasattr(result, "encoding")
        assert hasattr(result, "prompt_tokens")
        assert result.prompt_tokens > 0

    @pytest.mark.asyncio
    async def test_chat_completions_real(self, llm_service):
        """Test the chat_completions function with a real API call."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ]

        # Make the actual API call
        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=50,
            temperature=0.7,
        )

        # Validate the response
        assert result is not None
        assert hasattr(result, "id")
        assert hasattr(result, "choices")
        assert len(result.choices) > 0
        assert hasattr(result.choices[0], "message")
        assert hasattr(result.choices[0].message, "content")
        assert result.choices[0].message.content.strip() != ""
        assert hasattr(result, "usage")
        assert result.usage.prompt_tokens > 0

    @pytest.mark.asyncio
    async def test_chat_completions_usage_real(self, llm_service):
        """Test the chat_completions_usage function with a real API call."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ]

        # Make the actual API call
        result = await llm_service.chat_completions_usage(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=50,
            temperature=0.7,
        )

        # Validate the response
        assert result is not None
        assert hasattr(result, "encoding")
        assert hasattr(result, "prompt_tokens")
        assert result.prompt_tokens > 0
        assert isinstance(result.prompt_tokens, int)
        assert isinstance(result.encoding, str)
        assert len(result.encoding) > 0

    @pytest.mark.asyncio
    async def test_embeddings_with_custom_model_real(self, llm_service):
        """Test the embeddings function with a custom model."""
        input_text = "Testing embeddings with a different model."

        # Make the actual API call with a specific embedding model
        result = await llm_service.embeddings(
            input=input_text, embedding_model=EmbeddingModels.text_embedding_3_large
        )

        # Validate the response
        assert result is not None
        assert hasattr(result, "data")
        assert len(result.data) > 0
        assert hasattr(result.data[0], "embedding")
        assert len(result.data[0].embedding) > 0
        assert result.model == "text-embedding-3-large"
