UiPath LLM Gateway Services.

This module provides services for interacting with UiPath's LLM (Large Language Model) Gateway, offering both OpenAI-compatible and normalized API interfaces for chat completions and embeddings.

The module includes:

- UiPathOpenAIService: OpenAI-compatible API for chat completions and embeddings
- UiPathLlmChatService: UiPath's normalized API with advanced features like tool calling
- ChatModels: Constants for available chat models
- EmbeddingModels: Constants for available embedding models

Classes:

| Name                   | Description                                         |
| ---------------------- | --------------------------------------------------- |
| `ChatModels`           | Container for supported chat model identifiers      |
| `EmbeddingModels`      | Container for supported embedding model identifiers |
| `UiPathOpenAIService`  | Service using OpenAI-compatible API format          |
| `UiPathLlmChatService` | Service using UiPath's normalized API format        |

## ChatModels

Available chat models for LLM Gateway services.

This class provides constants for the supported chat models that can be used with both UiPathOpenAIService and UiPathLlmChatService.

## EmbeddingModels

Available embedding models for LLM Gateway services.

This class provides constants for the supported embedding models that can be used with the embeddings functionality.

## UiPathLlmChatService

Service for calling UiPath's normalized LLM Gateway API.

This service provides access to Large Language Model capabilities through UiPath's normalized LLM Gateway API. Unlike the OpenAI-compatible service, this service uses UiPath's standardized API format and supports advanced features like tool calling, function calling, and more sophisticated conversation control.

The normalized API provides a consistent interface across different underlying model providers and includes enhanced features for enterprise use cases.

### chat_completions

```
chat_completions(
    messages,
    model=ChatModels.gpt_4_1_mini_2025_04_14,
    max_tokens=4096,
    temperature=0,
    n=1,
    frequency_penalty=0,
    presence_penalty=0,
    top_p=1,
    top_k=None,
    tools=None,
    tool_choice=None,
    response_format=None,
    api_version=NORMALIZED_API_VERSION,
)
```

Generate chat completions using UiPath's normalized LLM Gateway API.

This method provides advanced conversational AI capabilities with support for tool calling, function calling, and sophisticated conversation control parameters. It uses UiPath's normalized API format for consistent behavior across different model providers.

Parameters:

| Name                | Type                                               | Description                                                                                                                                                                                                                                                                                     | Default                   |
| ------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `messages`          | `List[Dict[str, str]]`                             | List of message dictionaries with 'role' and 'content' keys. The supported roles are 'system', 'user', and 'assistant'. System messages set the behavior/context, user messages are from the human, and assistant messages are from the AI.                                                     | *required*                |
| `model`             | `str`                                              | The model to use for chat completion. Defaults to ChatModels.gpt_4_1_mini_2025_04_14. Available models are defined in the ChatModels class.                                                                                                                                                     | `gpt_4_1_mini_2025_04_14` |
| `max_tokens`        | `int`                                              | Maximum number of tokens to generate in the response. Defaults to 4096. Higher values allow longer responses.                                                                                                                                                                                   | `4096`                    |
| `temperature`       | `float`                                            | Temperature for sampling, between 0 and 1. Lower values (closer to 0) make output more deterministic and focused, higher values make it more creative and random. Defaults to 0.                                                                                                                | `0`                       |
| `n`                 | `int`                                              | Number of chat completion choices to generate for each input. Defaults to 1. Higher values generate multiple alternative responses.                                                                                                                                                             | `1`                       |
| `frequency_penalty` | `float`                                            | Penalty for token frequency between -2.0 and 2.0. Positive values reduce repetition of frequent tokens. Defaults to 0.                                                                                                                                                                          | `0`                       |
| `presence_penalty`  | `float`                                            | Penalty for token presence between -2.0 and 2.0. Positive values encourage discussion of new topics. Defaults to 0.                                                                                                                                                                             | `0`                       |
| `top_p`             | `float`                                            | Nucleus sampling parameter between 0 and 1. Controls diversity by considering only the top p probability mass. Defaults to 1.                                                                                                                                                                   | `1`                       |
| `top_k`             | `int`                                              | Nucleus sampling parameter. Controls diversity by considering only the top k most probable tokens. Defaults to None.                                                                                                                                                                            | `None`                    |
| `tools`             | `Optional[List[ToolDefinition]]`                   | List of tool definitions that the model can call. Tools enable the model to perform actions or retrieve information beyond text generation. Defaults to None.                                                                                                                                   | `None`                    |
| `tool_choice`       | `Optional[ToolChoice]`                             | Controls which tools the model can call. Can be "auto" (model decides), "none" (no tools), or a specific tool choice. Defaults to None.                                                                                                                                                         | `None`                    |
| `response_format`   | `Optional[Union[Dict[str, Any], type[BaseModel]]]` | An object specifying the format that the model must output. Can be either: - A dictionary with response format configuration (traditional format) - A Pydantic BaseModel class (automatically converted to JSON schema) Used to enable JSON mode or other structured outputs. Defaults to None. | `None`                    |
| `api_version`       | `str`                                              | The normalized API version to use. Defaults to NORMALIZED_API_VERSION.                                                                                                                                                                                                                          | `NORMALIZED_API_VERSION`  |

Returns:

| Name             | Type | Description                                                                                                                  |
| ---------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------- |
| `ChatCompletion` |      | The chat completion response containing the generated message(s), tool calls (if any), usage statistics, and other metadata. |

Examples:

```
# Basic conversation
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the weather like today?"}
]
response = await service.chat_completions(messages)

# Conversation with tool calling
tools = [
    ToolDefinition(
        function=FunctionDefinition(
            name="get_weather",
            description="Get current weather for a location",
            parameters=ParametersDefinition(
                type="object",
                properties={
                    "location": PropertyDefinition(
                        type="string",
                        description="City name"
                    )
                },
                required=["location"]
            )
        )
    )
]
response = await service.chat_completions(
    messages,
    tools=tools,
    tool_choice="auto",
    max_tokens=500
)

# Advanced parameters for creative writing
response = await service.chat_completions(
    messages,
    temperature=0.8,
    top_p=0.9,
    frequency_penalty=0.3,
    presence_penalty=0.2,
    n=3  # Generate 3 alternative responses
)

# Using Pydantic model for structured response
from pydantic import BaseModel

class Country(BaseModel):
    name: str
    capital: str
    languages: list[str]

response = await service.chat_completions(
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Respond with structured JSON."},
        {"role": "user", "content": "Tell me about Canada."}
    ],
    response_format=Country,  # Pass BaseModel directly
    max_tokens=1000
)
)
```

Note

This service uses UiPath's normalized API format which provides consistent behavior across different underlying model providers and enhanced enterprise features.

## UiPathOpenAIService

Service for calling UiPath's LLM Gateway using OpenAI-compatible API.

This service provides access to Large Language Model capabilities through UiPath's LLM Gateway, including chat completions and text embeddings. It uses the OpenAI-compatible API format and is suitable for applications that need direct OpenAI API compatibility.

### chat_completions

```
chat_completions(
    messages,
    model=ChatModels.gpt_4_1_mini_2025_04_14,
    max_tokens=4096,
    temperature=0,
    response_format=None,
    api_version=API_VERSION,
)
```

Generate chat completions using UiPath's LLM Gateway service.

This method provides conversational AI capabilities by sending a series of messages to a language model and receiving a generated response. It supports multi-turn conversations and various OpenAI-compatible models.

Parameters:

| Name              | Type                                               | Description                                                                                                                                                                                                                                                                                     | Default                   |
| ----------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `messages`        | `List[Dict[str, str]]`                             | List of message dictionaries with 'role' and 'content' keys. The supported roles are 'system', 'user', and 'assistant'. System messages set the behavior/context, user messages are from the human, and assistant messages are from the AI.                                                     | *required*                |
| `model`           | `str`                                              | The model to use for chat completion. Defaults to ChatModels.gpt_4_1_mini_2025_04_14. Available models are defined in the ChatModels class.                                                                                                                                                     | `gpt_4_1_mini_2025_04_14` |
| `max_tokens`      | `int`                                              | Maximum number of tokens to generate in the response. Defaults to 4096. Higher values allow longer responses.                                                                                                                                                                                   | `4096`                    |
| `temperature`     | `float`                                            | Temperature for sampling, between 0 and 1. Lower values (closer to 0) make output more deterministic and focused, higher values make it more creative and random. Defaults to 0.                                                                                                                | `0`                       |
| `response_format` | `Optional[Union[Dict[str, Any], type[BaseModel]]]` | An object specifying the format that the model must output. Can be either: - A dictionary with response format configuration (traditional format) - A Pydantic BaseModel class (automatically converted to JSON schema) Used to enable JSON mode or other structured outputs. Defaults to None. | `None`                    |
| `api_version`     | `str`                                              | The API version to use. Defaults to API_VERSION.                                                                                                                                                                                                                                                | `API_VERSION`             |

Returns:

| Name             | Type | Description                                                                                          |
| ---------------- | ---- | ---------------------------------------------------------------------------------------------------- |
| `ChatCompletion` |      | The chat completion response containing the generated message, usage statistics, and other metadata. |

Examples:

```
# Simple conversation
messages = [
    {"role": "system", "content": "You are a helpful Python programming assistant."},
    {"role": "user", "content": "How do I read a file in Python?"}
]
response = await service.chat_completions(messages)

# Multi-turn conversation with more tokens
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is machine learning?"},
    {"role": "assistant", "content": "Machine learning is a subset of AI..."},
    {"role": "user", "content": "Can you give me a practical example?"}
]
response = await service.chat_completions(
    messages,
    max_tokens=200,
    temperature=0.3
)

# Using Pydantic model for structured response
from pydantic import BaseModel

class Country(BaseModel):
    name: str
    capital: str
    languages: list[str]

response = await service.chat_completions(
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Respond with structured JSON."},
        {"role": "user", "content": "Tell me about Canada."}
    ],
    response_format=Country,  # Pass BaseModel directly
    max_tokens=1000
)
```

Note

The conversation history can be included to provide context to the model. Each message should have both 'role' and 'content' keys. When using a Pydantic BaseModel as response_format, it will be automatically converted to the appropriate JSON schema format for the LLM Gateway.

### embeddings

```
embeddings(
    input,
    embedding_model=EmbeddingModels.text_embedding_ada_002,
    openai_api_version=API_VERSION,
)
```

Generate text embeddings using UiPath's LLM Gateway service.

This method converts input text into dense vector representations that can be used for semantic search, similarity calculations, and other NLP tasks.

Parameters:

| Name                 | Type  | Description                                                                                                                                | Default                  |
| -------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| `input`              | `str` | The input text to embed. Can be a single sentence, paragraph, or document that you want to convert to embeddings.                          | *required*               |
| `embedding_model`    | `str` | The embedding model to use. Defaults to EmbeddingModels.text_embedding_ada_002. Available models are defined in the EmbeddingModels class. | `text_embedding_ada_002` |
| `openai_api_version` | `str` | The OpenAI API version to use. Defaults to API_VERSION.                                                                                    | `API_VERSION`            |

Returns:

| Name            | Type | Description                                                                                        |
| --------------- | ---- | -------------------------------------------------------------------------------------------------- |
| `TextEmbedding` |      | The embedding response containing the vector representation of the input text along with metadata. |

Examples:

```
# Basic embedding
embedding = await service.embeddings("Hello, world!")

# Using a specific model
embedding = await service.embeddings(
    "This is a longer text to embed",
    embedding_model=EmbeddingModels.text_embedding_3_large
)
```
