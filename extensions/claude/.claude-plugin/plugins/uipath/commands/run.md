---
description: Run a UiPath agent with interactive input collection
allowed-tools: Bash, Read, Glob, AskUserQuestion
argument-hint: [agent-name]
contextAware: true
autoDetect: true
---

# Run a UiPath Agent

Execute your UiPath agent with interactive, schema-driven input collection.

## Context-Aware Execution

This skill automatically detects your UiPath project! The context includes:
- ✅ Available agents (from cached entry-points.json)
- ✅ Agent input/output schemas
- ✅ Project configuration

**You can just type `/run-agent`** and the skill will:
1. Check cached context for available agents
2. Auto-select if only one agent exists
3. Show menu if multiple agents found
4. Proceed directly to input collection

No need to specify agent name if you only have one!

## Workflow

### Step 0: Automatic Context Detection
The extension automatically detects and caches:
- Your UiPath project (uipath.json)
- All agents from entry-points.json
- Evaluation files
- Project metadata

Cache is refreshed every 5 minutes or when files change.

### Step 1: Project Verification
I'll verify that your project has:
- `uipath.json` - Project configuration
- `entry-points.json` - Agent entry points with schemas

If missing, create an agent first with `/create-agent`.

### Step 2: Agent Discovery
I'll read `entry-points.json` to find all available agents and their schemas:
- **File path** and **entry point** (e.g., main.py:main)
- **Input schema** with field types and descriptions
- **Output schema** with expected return fields

If multiple agents exist, I'll prompt you to select one.

### Step 3: Input Collection
I'll parse the agent's JSON schema and generate interactive prompts for each input field:

**For simple types:**
```
Enter a (number) - First operand: 10
Enter b (number) - Second operand: 5
```

**For enums:**
```
Select operator (string) - Math operation:
  1. +
  2. -
  3. *
  4. /
Choice: 1
```

**For optional fields:**
```
Enter description (string) - Optional agent description [press Enter to skip]:
```

### Step 4: Execution
I'll execute:
```bash
uipath run <entrypoint> '<json-input>'
```

The agent runs with your provided inputs and returns structured output.

### Step 5: Results Display
Results are shown in a formatted output panel:

```
EXECUTION RESULTS
═══════════════════════════════════════════════════════════

Status:           ✅ SUCCESS
Execution Time:   0.45 seconds
Agent:            calculator (main.py:main)
Input:            {"a": 10, "b": 5, "operator": "+"}

OUTPUT:
{
  "result": 15
}
```

### Step 6: Follow-up Actions
After execution, you can:
- **Run again** with different inputs
- **Create evaluation tests** for this agent
- **List other agents** in your project
- **View trace data** for debugging

## Supported Input Types

The skill supports all JSON schema types:
- **string** - Text input
- **number** - Decimal numbers
- **integer** - Whole numbers
- **boolean** - Yes/No toggle
- **array** - List of items
- **object** - Complex nested data
- **enum** - Choice from predefined options

## Error Handling

If execution fails, I'll display:
- Error message from the agent
- Stack trace for debugging
- Suggestions for fixing the issue
- Option to re-run with modified inputs

## Integration

Execution traces are automatically collected and can be:
- Viewed in UiPath Cloud
- Analyzed for performance
- Used for debugging and optimization

Create agents with `/create-agent` and test them with this skill!