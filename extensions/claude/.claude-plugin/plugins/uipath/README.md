# UiPath SDK Assistant

Create, run, and evaluate UiPath coded agents with AI-powered assistance in Claude Code.

## Quick Start

### Installation

```bash
# Add the marketplace
claude plugin marketplace add extensions/claude

# Install the plugin
claude plugin install uipath@uipath-marketplace
```

### Use the Plugin

```bash
# Open main menu
/uipath

# Create a new agent
/uipath:create-agent my-calculator

# Run an agent
/uipath:run

# Create test cases
/uipath:create-eval test-suite

# Run evaluations
/uipath:eval

# List agents and evaluations
/uipath:list
```

## Features

- **🚀 Create Agents**: Build new UiPath agents with AI-powered implementation
- **▶️ Run Agents**: Execute agents with interactive input collection
- **✅ Create Evaluations**: Build comprehensive test cases for agents
- **📊 Run Evaluations**: Execute tests and view detailed results
- **🔍 Smart Context**: Auto-detects UiPath projects in your workspace
- **📚 Auto Setup**: Generates project templates and installs dependencies

## Commands

| Command | Description |
|---------|-------------|
| `/uipath` | Main menu with all commands |
| `/uipath:create-agent` | Create a new agent |
| `/uipath:run` | Run an existing agent |
| `/uipath:create-eval` | Create evaluation test cases |
| `/uipath:eval` | Run evaluations |
| `/uipath:list` | List all agents and evaluations |
| `/uipath:auth` | Authenticate with UiPath |
| `/uipath:plugin-env-setup` | Initialize plugin environment |

## Workflow

### 1. Create an Agent

```
User: /uipath:create-agent calculator
Claude: I'll help you create a calculator agent
- Asks for input fields (e.g., a, b, operator)
- Asks for output fields (e.g., result)
- Generates main.py with Pydantic models
- Implements business logic
- Runs uipath init to generate schemas
```

### 2. Run the Agent

```
User: /uipath:run
Claude: Which agent would you like to run?
- Shows list of agents
- Collects inputs based on schema
- Executes agent
- Shows results
```

### 3. Create Test Cases

```
User: /uipath:create-eval test-suite
Claude: I'll create test cases for your agent
- Asks for number of test cases
- Collects input/output for each case
- Saves to evaluations/test-suite.json
```

### 4. Run Evaluations

```
User: /uipath:eval
Claude: Running evaluations...
- Executes all test cases
- Shows results table with pass/fail
- Displays success rate
```

## Generated Files

When you create an agent, the plugin generates:

```
project-dir/
├── pyproject.toml          # Project dependencies and config
├── main.py                 # Agent implementation
├── uipath.json             # UiPath project metadata
├── entry-points.json       # Agent schemas and entry points
└── .claude/
    └── cpr.sh              # Plugin resolver (auto-created on first session)
```

When you create evaluations:

```
evaluations/
└── my-tests.json           # Test cases with inputs and expected outputs
```

## Requirements

- Python 3.12+
- `uv` (package manager)
- Claude Code CLI
- UiPath SDK (installed automatically via `uv sync`)

## Context Awareness

The plugin automatically detects:

- ✅ UiPath projects (checks for `uipath.json`)
- ✅ Existing agents (reads `entry-points.json`)
- ✅ Evaluation files (finds `.json` files in `evaluations/`)
- ✅ Project metadata (displays in main menu)

No setup needed - just run the commands!

## Troubleshooting

### "Unknown skill" or "Plugin not found"

Make sure the marketplace is installed:

```bash
claude plugin marketplace add extensions/claude
claude plugin install uipath@uipath-marketplace
```

### "UiPath SDK not found" or "uipath command not found"

The SDK is installed automatically, but if you need to manually reinstall:

```bash
uv sync
```

Make sure you're in a project directory with a `pyproject.toml` file.

### Agent creation fails

Make sure:
- You're in an empty or valid project directory
- You have proper file permissions
- The plugin environment is initialized (run `/uipath:plugin-env-setup` if needed)

## Getting Help

For detailed setup instructions and quick start guide, see:
- **[extensions/claude/README.md](../../../README.md)** - Main plugin setup guide

## Support

- GitHub Issues: https://github.com/uipath/uipath-python/issues
- UiPath Documentation: https://docs.uipath.com
- Community: https://community.uipath.com

## License

MIT License - See project LICENSE file for details
