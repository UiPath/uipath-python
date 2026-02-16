---
allowed-tools: Bash, Read, Write, Edit, Glob
description: Create a new UiPath coded agent from a description
---

I'll help you create a new UiPath coded agent.

## Step 1: Check existing project

Let me check if this is an existing UiPath project:

!ls uipath.json main.py 2>/dev/null || echo "NEW_PROJECT"

## Step 2: Gather requirements

**What should this agent do?**

Please describe:

-   What inputs it needs (e.g., "a file path and bucket name")
-   What it should accomplish (e.g., "process CSV data")
-   What outputs it should return (e.g., "total count and status")

I'll generate the agent structure based on your description.

## Step 3: Generate agent

After you describe the agent, I will:

1. Create `main.py` with Input/Output Pydantic models and `async def main()`
2. Add entrypoint to `uipath.json` under `"functions": {"agent_name": "main.py:main"}`
3. Run `uv run uipath init --no-agents-md-override` to generate schemas

**Template structure** (from .agent/REQUIRED_STRUCTURE.md):

```python
from pydantic import BaseModel
from uipath.platform import UiPath

class Input(BaseModel):
    """Input fields for the agent."""
    # Fields based on your description
    pass


class Output(BaseModel):
    """Output fields returned by the agent."""
    # Fields based on your description
    pass


async def main(input: Input) -> Output:
    """Main entry point for the agent.

    Args:
        input: The input data for the agent.

    Returns:
        The output data from the agent.
    """

    uipath = UiPath()

    # TODO: Implement agent logic
    return Output()
```

**Important notes:**

-   Use `async def main` - many SDK methods are async
-   Initialize `UiPath()` inside the function, not at module level
-   After creating main.py, add entrypoint to `uipath.json` under `"functions"`

## Step 4: Update entry-point schemas

After creating main.py, regenerate the schemas:

!uv run uipath init --no-agents-md-override

## Step 5: Verify

Quick test to verify the setup:

!uv run uipath run main '{}' 2>&1 | head -30

## Summary

Once complete, you'll have:

| File                | Purpose                             |
| ------------------- | ----------------------------------- |
| `main.py`           | Agent code with Input/Output models |
| `uipath.json`       | Project configuration               |
| `entry-points.json` | Entry point schemas                 |
| `bindings.json`     | Resource bindings                   |
| `.agent/`           | SDK and CLI reference docs          |

**Next steps:**

1. Implement your logic in `main()`
2. Test: `uv run uipath run main '{"field": "value"}'`
3. Create `eval_set.json` for evaluations
4. Evaluate: `uv run uipath eval`
