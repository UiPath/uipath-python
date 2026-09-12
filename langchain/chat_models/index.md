# Chat Models

UiPath provides chat model classes for several providers (OpenAI via `UiPathAzureChatOpenAI`, Anthropic on AWS Bedrock via `UiPathChatAnthropicBedrock`, Google Vertex AI via `UiPathChatGoogleGenerativeAI`, and more), plus the generic `UiPathChat`. These are compatible with LangGraph as drop in replacements. You do not need to add tokens from OpenAI, Anthropic, or Google, usage of these chat models will consume `Agent Units` on your account.

## Available models

LLM models are served through the UiPath LLM Gateway and are subject to [AI Trust Layer](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/about-ai-trust-layer) policies, so the exact set of models available to you depends on your tenant configuration. List the models you can use with the `uipath` CLI:

```
$ uipath list-models
                                   Available LLM Models
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ AwsBedrock                               ┃ OpenAi                  ┃ VertexAi         ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ anthropic.claude-haiku-4-5-20251001-v1:0 │ gpt-4.1-2025-04-14      │ gemini-2.5-flash │
│ anthropic.claude-opus-4-7                │ gpt-4.1-mini-2025-04-14 │ gemini-2.5-pro   │
│ ...                                      │ ...                     │ ...              │
└──────────────────────────────────────────┴─────────────────────────┴──────────────────┘
```

Pick a model id from the relevant provider column and pass it to the matching chat model class:

```
from uipath_langchain.chat import (
    UiPathAzureChatOpenAI,
    UiPathChatAnthropicBedrock,
    UiPathChatGoogleGenerativeAI,
)

# AWS Bedrock (Anthropic) models
llm = UiPathChatAnthropicBedrock(model="anthropic.claude-haiku-4-5-20251001-v1:0")

# OpenAI models
llm = UiPathAzureChatOpenAI(model="gpt-4.1-mini-2025-04-14")

# Google Vertex AI models
llm = UiPathChatGoogleGenerativeAI(model="gemini-2.5-flash")
```

Passthrough vs normalized

The provider-specific classes (`UiPathAzureChatOpenAI`, `UiPathChatAnthropicBedrock`, `UiPathChatGoogleGenerativeAI`) are passthrough: requests and responses go directly to the provider API, so you get the provider's full, native feature set. `UiPathChat` is normalized: it exposes a single unified interface across providers at the cost of provider-specific capabilities. We recommend the passthrough classes.

## UiPathAzureChatOpenAI

`UiPathAzureChatOpenAI` can be used as a drop in replacement for `ChatOpenAI` or `AzureChatOpenAI`.

### Example usage

Here is a code that is using `ChatOpenAI`

```
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=4000,
    timeout=30,
    max_retries=2,
    # api_key="...",  # if you prefer to pass api key in directly instead of using env vars
    # base_url="...",
    # organization="...",
    # other params...
)
```

You can simply change `ChatOpenAi` with `UiPathAzureChatOpenAI`, you don't have to provide an OpenAI token.

```
from uipath_langchain.chat.models import UiPathAzureChatOpenAI

llm = UiPathAzureChatOpenAI(
    model="gpt-4.1-mini-2025-04-14",
    temperature=0,
    max_tokens=4000,
    timeout=30,
    max_retries=2,
    # other params...
)
```

`UiPathAzureChatOpenAI` supports the OpenAI models (the `OpenAi` column of [`uipath list-models`](#available-models)).

## UiPathChat

`UiPathChat` is a more versatile class that can suport models from diferent vendors including OpenAI.

### Example usage

Given the following code:

```
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20240620",
    temperature=0,
    max_tokens=1024,
    timeout=None,
    max_retries=2,
    # other params...
)
```

You can replace it with `UiPathChat` like so:

```
from uipath_langchain.chat.models import UiPathChat

llm = UiPathChat(
    model="anthropic.claude-3-opus-20240229-v1:0",
    temperature=0,
    max_tokens=1024,
    timeout=None,
    max_retries=2,
    # other params...
)
```

`UiPathChat` supports models from multiple vendors (AWS Bedrock, OpenAI, Google Vertex AI), so it can use any model from [`uipath list-models`](#available-models).

Warning

Please note that you may get errors related to data residency, as some models are not available on all regions.

Example: `[Enforced Region] No model configuration found for product uipath-python-sdk in EU using model anthropic.claude-3-opus-20240229-v1:0`.
