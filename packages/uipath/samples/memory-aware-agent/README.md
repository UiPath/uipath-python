# Memory-Aware Agent

A coded agent that recalls prior interactions from a UiPath **Agent Memory**
space and uses them to augment its LLM system prompt before answering.

## What it demonstrates

1. Searching a memory space via `UiPath().memory.search_async`
2. Stitching the LLMOps-rendered `system_prompt_injection` few-shot block
   into the system prompt
3. Calling the UiPath LLM Gateway with the augmented context

The Python SDK does **not** auto-wire memory based on the
`is_agent_memory_enabled` flag in agent definitions — recall and prompt
injection are explicit calls in your agent code, as shown here.

## Prerequisites

Set the following environment variables (a `.env` file works too):

| Variable | Purpose |
|----------|---------|
| `UIPATH_URL` | Base URL, e.g. `https://cloud.uipath.com/<org>/<tenant>` |
| `UIPATH_ACCESS_TOKEN` | PAT or service-to-service token |
| `UIPATH_FOLDER_KEY` | Folder that owns the memory space |

You also need a memory space. Create one via the UI/CLI or programmatically:

```python
from uipath.platform import UiPath
sdk = UiPath()
space = sdk.memory.create(
    name="customer-support-recall",
    description="Past resolved customer queries",
    folder_key="<your-folder-key>",
)
print(space.id)  # pass this as memory_space_id
```

## Run

```bash
cd packages/uipath/samples/memory-aware-agent
uv sync
uipath run main '{"query": "How do I reset my password?", "memory_space_id": "<space-id>"}'
```

## How it works

```
AgentInput.query
      │
      ▼
sdk.memory.search_async ──▶ MemorySearchResponse.system_prompt_injection
      │                              │
      └──── augmented system prompt ◀┘
                    │
                    ▼
        sdk.llm.chat_completions  ──▶ AgentOutput.response
```

`MemorySearchResponse.system_prompt_injection` is a pre-rendered few-shot
block produced by LLMOps — paste it directly into the system prompt and
let the model do the rest. No extra templating required.
