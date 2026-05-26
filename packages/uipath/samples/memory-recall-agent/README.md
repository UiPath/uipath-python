# Memory Recall Coded Agent

This sample shows a coded agent using UiPath Memory Space constructs:

- `MemorySearchRequest`
- `SearchField`
- `SearchSettings`
- `SearchMode`
- `UiPath().memory.list_async`
- `UiPath().memory.create_async`
- `UiPath().memory.search_async`

The agent resolves a memory space by ID or by name and folder path, searches it with the incoming question, and returns the matched memories. When `generate_answer` is true, it also uses the returned `system_prompt_injection` as part of the system prompt for a UiPath LLM Gateway call.

## Prerequisites

1. Python 3.11+
2. UiPath authentication configured with `uipath auth --alpha`
3. A folder where Agent Memory is enabled
4. An existing Memory Space, or `create_if_missing` set to `true`

## Run Locally

```bash
uv sync
uv run uipath run main.py:main -f input.json
```

If you already know the memory space ID, set `memory_space_id` in `input.json`. Otherwise, the sample looks up `memory_space_name` in `folder_path`.

## Input

```json
{
  "question": "What is the standard refund handling policy for premium customers?",
  "memory_space_id": null,
  "memory_space_name": "support-agent-memory",
  "folder_path": "Shared",
  "result_count": 3,
  "threshold": 0,
  "search_mode": "Hybrid",
  "create_if_missing": false,
  "generate_answer": true
}
```

Set `generate_answer` to `false` to only inspect the raw memory search matches and `system_prompt_injection` without calling the LLM Gateway.

## Notes

- `result_count` is clamped to the Memory API range of 1 to 10.
- `threshold` is clamped to the Memory API range of 0.0 to 1.0.
- If `create_if_missing` creates a new memory space, the first search will usually return no matches because the memory space is empty.
