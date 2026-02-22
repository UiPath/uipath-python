# Chat Models

UiPath provides two chat models `UiPathAzureChatOpenAI` and `UiPathChat`. These are compatible with LangGraph as drop in replacements. You do not need to add tokens from OpenAI or Anthropic, usage of these chat models will consume `Agent Units` on your account.

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

Currently, the following models can be used with `UiPathAzureChatOpenAI` (this list can be updated in the future):

- `gpt-4`, `gpt-4-1106-Preview`, `gpt-4-32k`, `gpt-4-turbo-2024-04-09`, `gpt-4-vision-preview`, `gpt-4o-2024-05-13`, `gpt-4o-2024-08-06`, `gpt-4o-mini-2024-07-18`, `gpt-4.1-mini-2025-04-14`, `o3-mini-2025-01-31`

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

Currently the following models can be used with `UiPathChat` (this list can be updated in the future):

- `anthropic.claude-3-5-sonnet-20240620-v1:0`, `anthropic.claude-3-5-sonnet-20241022-v2:0`, `anthropic.claude-3-7-sonnet-20250219-v1:0`, `anthropic.claude-3-haiku-20240307-v1:0`, `gemini-1.5-pro-001`, `gemini-2.0-flash-001`, `gpt-4o-2024-05-13`, `gpt-4o-2024-08-06`, `gpt-4o-2024-11-20`, `gpt-4o-mini-2024-07-18`, `o3-mini-2025-01-31`

Warning

Please note that you may get errors related to data residency, as some models are not available on all regions.

Example: `[Enforced Region] No model configuration found for product uipath-python-sdk in EU using model anthropic.claude-3-opus-20240229-v1:0`.
