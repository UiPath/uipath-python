# Python Coded Agents

A coded agent is Python code that uses an LLM reasoning loop to make decisions, call tools, and produce a result. You write the agent logic using a framework of your choice — the `uipath` SDK provides the platform layer: authentication, assets, buckets, connections, tracing, and human-in-the-loop. Package it with the CLI and deploy it as an Orchestrator job.

Use a coded agent when your automation needs multi-step reasoning, dynamic tool selection, or LLM-driven decisions. Use a [coded function](./functions.md) when your logic is deterministic and no LLM is required.

---

## Architecture

Every coded agent is built from two layers:

| Layer | Package | Responsibility |
|-------|---------|---------------|
| **Platform** | `uipath` | Auth, assets, buckets, connections, tracing, human-in-the-loop, CLI, packaging |
| **Framework** | one extension (see below) | LLM calls, tool routing, agent loop, memory |

The `uipath` package is always required. Add one framework extension on top:

| Framework | Package | Best for |
|-----------|---------|---------|
| LangChain / LangGraph | `uipath-langchain` | Graph-based agents, complex multi-step flows |
| LlamaIndex | `uipath-llamaindex` | RAG-heavy agents, document reasoning |
| OpenAI Agents SDK | `uipath-openai-agents` | OpenAI-native tool use, handoffs |
| PydanticAI | `uipath-pydantic-ai` | Type-safe agents with Pydantic models |
| Google ADK | `uipath-google-adk` | Gemini models, Google ecosystem |
| UiPath Agent Framework | `uipath-agent-framework` | UiPath-native agent primitives |

---

## Quickstart

The example below uses LangChain. Swap `uipath-langchain` for the framework of your choice.

//// tab | uv

<!-- termynal -->

```shell
> mkdir my-agent && cd my-agent
> uv init . --python 3.11
> uv add uipath uipath-langchain

> uipath auth
⠋ Authenticating with UiPath ...
✓  Authentication successful.

> uipath new agent
✓  Created new agent project.

> uipath init
⠋ Initializing UiPath project ...
✓  Created 'entry-points.json' file.
✓  Created 'bindings.json' file.

> uipath run agent '{"message": "hello"}'
```

////

//// tab | pip

<!-- termynal -->

```shell
> mkdir my-agent && cd my-agent
> python -m venv .venv
> source .venv/bin/activate
> pip install uipath uipath-langchain

> uipath auth
⠋ Authenticating with UiPath ...
✓  Authentication successful.

> uipath new agent
✓  Created new agent project.

> uipath init
⠋ Initializing UiPath project ...
✓  Created 'entry-points.json' file.
✓  Created 'bindings.json' file.

> uipath run agent '{"message": "hello"}'
```

////

---

## Project Structure

```
my-agent/
├── main.py            # agent logic
├── pyproject.toml     # project metadata and dependencies
├── uipath.json        # entry point declarations
├── entry-points.json  # generated — I/O JSON Schema
└── bindings.json      # generated — resource binding overrides
```

### `uipath.json`

```json
{
  "agents": {
    "agent": "main.py:agent"
  }
}
```

### `pyproject.toml`

```toml
[project]
name = "my-agent"
version = "0.1.0"
description = "..."
authors = [{ name = "Your Name", email = "you@example.com" }]
requires-python = ">=3.11"
dependencies = ["uipath>=2.0", "uipath-langchain>=2.0"]
```

Standard project metadata and dependencies. The `agents` map in `uipath.json` (above) is what marks the project as a coded agent — `pyproject.toml` needs no UiPath-specific entries.

---

## Input & Output

Define `Input` and `Output` the same way as [coded functions](./functions.md#input--output) — a stdlib `@dataclass`, a pydantic `BaseModel`, or `pydantic.dataclasses.dataclass`:

```python
from dataclasses import dataclass


@dataclass
class Input:
    message: str


@dataclass
class Output:
    response: str


def agent(input: Input) -> Output:
    ...
```

---

## Platform Services

The `uipath` SDK gives your agent access to Orchestrator resources at runtime — credentials are injected automatically when running as a job.

```python
from uipath.platform import UiPath

sdk = UiPath()
```

The full set of Orchestrator services is available to agents:

- **Assets** — read credentials and configuration: [Assets reference](./assets.md)
- **Buckets** — download and upload files: [Buckets reference](./buckets.md)
- **Connections** — Integration Service connections for ERP and SaaS: [Connections reference](./connections.md)
- **Context Grounding** — semantic search over enterprise data: [Context Grounding reference](./context_grounding.md)

---

## Tracing

Apply `@traced` to custom steps inside your agent to make them visible in the Orchestrator job trace view and Maestro dashboards. Do **not** trace the entry point — the runtime wraps it automatically.

```python
from uipath.tracing import traced


@traced(name="lookup_vendor", run_type="uipath")
def lookup_vendor(vendor_id: str) -> dict:
    ...
```

See [Tracing](./traced.md) for the full decorator reference.

---

## Framework Guides

Each framework extension has its own getting started guide and sample agents:

| Framework | Guide | Samples |
|-----------|-------|---------|
| LangChain / LangGraph | [Get Started](../langchain/quick_start.md) | [Samples](https://github.com/UiPath/uipath-langchain-python/tree/main/samples) |
| LlamaIndex | [Get Started](../llamaindex/quick_start.md) | [Samples](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-llamaindex/samples) |
| OpenAI Agents SDK | [Get Started](../openai-agents/quick_start.md) | [Samples](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-openai-agents/samples) |
| PydanticAI | [README](https://github.com/UiPath/uipath-integrations-python/blob/main/packages/uipath-pydantic-ai/README.md) | [Samples](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-pydantic-ai/samples) |
| Google ADK | [README](https://github.com/UiPath/uipath-integrations-python/blob/main/packages/uipath-google-adk/README.md) | [Samples](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-google-adk/samples) |
| UiPath Agent Framework | [README](https://github.com/UiPath/uipath-integrations-python/blob/main/packages/uipath-agent-framework/README.md) | [Samples](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-agent-framework/samples) |


---

## Pack & Publish

The same CLI workflow applies as for coded functions:

<!-- termynal -->

```shell
> uipath pack
⠋ Packaging project ...
Name       : my-agent
Version    : 0.1.0
Description: Add your description here
Authors    : Your Name
✓  Project successfully packaged.

> uipath publish
⠋ Fetching available package feeds...
Select feed number: 0
✓  Package published successfully!
```

After publishing, the agent registers as an Orchestrator Process and can be invoked from Maestro, the Orchestrator API, or the CLI.

See [CLI Reference](../cli/index.md) for full `pack`, `publish`, and `invoke` options.

---

## Studio Web Integration

Connect your agent to a Studio Web solution for cloud debugging, evaluation, and solution packaging.

See [Studio Web Integration](./studio_web.md) for setup and sync details.

---

## Evaluations

Coded agents support evaluations in Studio Web and locally via `uipath eval`. Evaluators cover LLM output quality, tool call correctness, and trajectory analysis.

See the [Evaluations documentation](../eval/index.md) for available evaluators and how to define evaluation sets.
