# LLMs and Embeddings

UiPath provides pre-configured LLM and embedding classes that handle authentication, routing, and configuration automatically, allowing you to focus on building your agents. You do not need to add API keys from OpenAI, AWS, or Google, usage of these models will consume `Agent Units` on your account.

## UiPathOpenAI

The `UiPathOpenAI` class is a pre-configured Azure OpenAI client that routes requests through UiPath.

### Available Models

The following OpenAI models are available through the `OpenAIModel` enum:

- `GPT_4_1_2025_04_14`
- `GPT_4_1_MINI_2025_04_14`
- `GPT_4_1_NANO_2025_04_14`
- `GPT_4O_2024_05_13`
- `GPT_4O_2024_08_06`
- `GPT_4O_2024_11_20`
- `GPT_4O_MINI_2024_07_18` (default)
- `O3_MINI_2025_01_31`
- `TEXT_DAVINCI_003`

### Basic Usage

```
from uipath_llamaindex.llms import UiPathOpenAI
from llama_index.core.llms import ChatMessage

# Create an LLM instance with default settings
llm = UiPathOpenAI()

# Create chat messages
messages = [
    ChatMessage(
        role="system", content="You are a pirate with colorful personality."
    ),
    ChatMessage(role="user", content="Hello"),
]

# Generate a response
response = llm.chat(messages)
print(response)
```

### Custom Model Configuration

```
from uipath_llamaindex.llms import UiPathOpenAI, OpenAIModel

# Use a specific model
llm = UiPathOpenAI(model=OpenAIModel.GPT_4_1_2025_04_14)

# Or use a model string directly
llm = UiPathOpenAI(model="gpt-4.1-2025-04-14")
```

## UiPathOpenAIEmbedding

The `UiPathOpenAIEmbedding` class provides text embedding capabilities using OpenAI's embedding models through UiPath.

### Available Embedding Models

The following embedding models are available through the `OpenAIEmbeddingModel` enum:

- `TEXT_EMBEDDING_ADA_002` (default)
- `TEXT_EMBEDDING_3_LARGE`

### Basic Usage

```
from uipath_llamaindex.embeddings import UiPathOpenAIEmbedding

# Create an embedding model instance
embed_model = UiPathOpenAIEmbedding()

# Get embeddings for a single text
result = embed_model.get_text_embedding("the quick brown fox jumps over the lazy dog")
print(f"Embedding dimension: {len(result)}")
```

### Batch Embeddings

```
from uipath_llamaindex.embeddings import UiPathOpenAIEmbedding

embed_model = UiPathOpenAIEmbedding()

# Get embeddings for multiple texts
texts = [
    "Hello world",
    "How are you?",
    "This is a test"
]

embeddings = embed_model.get_text_embedding_batch(texts)
print(f"Number of embeddings: {len(embeddings)}")
```

## UiPathChatBedrock and UiPathChatBedrockConverse

`UiPathChatBedrock` and `UiPathChatBedrockConverse` provide access to AWS Bedrock models through UiPath using the Invoke API and Converse API respectively.

### Installation

These classes require additional dependencies. Install them with:

```
pip install uipath-llamaindex[bedrock]
# or using uv:
uv add 'uipath-llamaindex[bedrock]'
```

### Example Usage

```
from uipath_llamaindex.llms.bedrock import UiPathChatBedrockConverse
from uipath_llamaindex.llms import BedrockModel
from llama_index.core.llms import ChatMessage

# Create an LLM instance with default settings
llm = UiPathChatBedrockConverse()

# Or use a specific model
llm = UiPathChatBedrockConverse(model=BedrockModel.anthropic_claude_sonnet_4_5)

# Create chat messages
messages = [
    ChatMessage(role="user", content="Hello"),
]

# Generate a response
response = llm.chat(messages)
print(response)
```

Similarly, `UiPathChatBedrock` can be used with the Invoke API:

```
from uipath_llamaindex.llms.bedrock import UiPathChatBedrock
from uipath_llamaindex.llms import BedrockModel

llm = UiPathChatBedrock(model=BedrockModel.anthropic_claude_sonnet_4)
```

Currently, the following models can be used (this list can be updated in the future):

- `anthropic.claude-3-7-sonnet-20250219-v1:0`, `anthropic.claude-sonnet-4-20250514-v1:0`, `anthropic.claude-sonnet-4-5-20250929-v1:0`, `anthropic.claude-haiku-4-5-20251001-v1:0`

## UiPathVertex

`UiPathVertex` provides access to Google Vertex AI (Gemini) models through UiPath.

### Installation

This class requires additional dependencies. Install them with:

```
pip install uipath-llamaindex[vertex]
# or using uv:
uv add 'uipath-llamaindex[vertex]'
```

### Example Usage

```
from uipath_llamaindex.llms.vertex import UiPathVertex
from uipath_llamaindex.llms import GeminiModel
from llama_index.core.llms import ChatMessage

# Create an LLM instance with default settings
llm = UiPathVertex()

# Or use a specific model
llm = UiPathVertex(model=GeminiModel.gemini_2_5_pro)

# Create chat messages
messages = [
    ChatMessage(role="user", content="Hello"),
]

# Generate a response
response = llm.chat(messages)
print(response)
```

Currently, the following models can be used (this list can be updated in the future):

- `gemini-2.0-flash-001`, `gemini-2.5-flash`, `gemini-2.5-pro`

## Integration with LlamaIndex

These classes integrate seamlessly with LlamaIndex components:

### Using with Agents

```
import asyncio
from llama_index.core.agent.workflow import ReActAgent
from uipath_llamaindex.llms import UiPathOpenAI, OpenAIModel

def multiply(a: int, b: int) -> int:
    """Multiply two integers and returns the result integer"""
    return a * b


def add(a: int, b: int) -> int:
    """Add two integers and returns the result integer"""
    return a + b

# Create agent with UiPath LLM
agent = ReActAgent(
    tools=[multiply, add],
    llm=UiPathOpenAI(model=OpenAIModel.GPT_4_1_2025_04_14))

async def main():
    handler = agent.run("What is 2+(2*4)?")
    response = await handler

asyncio.run(main())
```

### Using with VectorStoreIndex

```
from llama_index.core import VectorStoreIndex, Document
from uipath_llamaindex.llms import UiPathOpenAI
from uipath_llamaindex.embeddings import UiPathOpenAIEmbedding

# Create documents
documents = [
    Document(text="This is a sample document about artificial intelligence."),
    Document(text="Machine learning is a subset of AI that focuses on algorithms."),
]

# Create index with UiPath models
index = VectorStoreIndex.from_documents(
    documents,
    embed_model=UiPathOpenAIEmbedding()
)

# Create query engine with UiPath LLM
query_engine = index.as_query_engine(
    llm=UiPathOpenAI(model=OpenAIModel.GPT_4_1_2025_04_14)
)

response = query_engine.query("What is machine learning?")
```

Warning

Please note that you may get errors related to data residency, as some models are not available on all regions.

Example: `[Enforced Region] No model configuration found for product uipath-python-sdk in EU`.
