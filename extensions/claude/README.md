# UiPath Claude Code Plugin

Create, run, and evaluate UiPath coded agents with AI-powered assistance in Claude Code.

## Quick Start

### Step 1: Add the Marketplace

First, add the UiPath marketplace to Claude Code:

```bash
claude plugin marketplace add ./extensions/claude
```

### Step 2: Install the Plugin

Install the UiPath plugin from the marketplace:

```bash
claude plugin install uipath@uipath-marketplace
```

### Step 3: Create Your First Agent

Create an empty directory for your project:

```bash
mkdir my-uipath-project
cd my-uipath-project
```

Start Claude Code:

```bash
claude
```

### Step 4: Ask Claude to Create an Agent

In the Claude Code prompt, describe what you want to build:

```
create a uipath calculator agent that takes 2 numbers and one operator as input and produces number as output
```

Claude will:
- Set up your project structure
- Create `pyproject.toml` with dependencies
- Generate a `main.py` with your agent logic
- Initialize the UiPath project with `uipath init`

### Step 5: Authenticate (if needed)

If your agent requires authentication:

1. Claude will prompt you to authenticate
2. Your browser will open for UiPath login
3. If prompted, select the correct tenant from the available options
4. Authentication credentials will be saved locally

### Step 6: Run Your Agent

To test your agent:

```
run it
```

Claude will:
1. Show you available demo examples
2. Ask you to select one
3. Execute the agent with the example inputs
4. Display the results

## Available Commands

Once the plugin is installed, you can use:

- `/uipath` - Open the main UiPath menu
- `/uipath:create-agent` - Create a new agent
- `/uipath:run` - Run an existing agent
- `/uipath:create-eval` - Create evaluation test cases
- `/uipath:eval` - Run evaluations
- `/uipath:list` - List all agents and evaluations
- `/uipath:auth` - Authenticate with UiPath
- `/uipath:plugin-env-setup` - Initialize plugin environment

## Managing the Marketplace

### Remove the Marketplace

If you want to remove the marketplace:

```bash
claude plugin marketplace remove uipath-marketplace
```

This will uninstall the marketplace but keep any installed plugins.

### Remove the Plugin

To remove the UiPath plugin:

```bash
claude plugin uninstall uipath@uipath-marketplace
```

## Project Structure

After creating an agent, your project will look like:

```
my-uipath-project/
├── pyproject.toml           # Project dependencies
├── uipath.json              # UiPath project config
├── entry-points.json        # Agent schemas
├── main.py                  # Agent implementation
├── agents/                  # Agent files (if multiple)
├── evaluations/             # Test cases
└── .claude/
    └── cpr.sh               # Plugin resolver (auto-created)
```

## Requirements

- Python 3.12+
- `uv` (package manager)
- Claude Code CLI
- Active UiPath account (for authentication)

## Troubleshooting

### "Marketplace not found"

Make sure you added the marketplace:

```bash
claude plugin marketplace add ./extensions/claude
```

### "Plugin not installed"

Install the plugin:

```bash
claude plugin install uipath@uipath-marketplace
```

### "UiPath command not found"

Run `/uipath:create-agent` to properly initialize your project with the UiPath SDK.

### Authentication fails

Try running the authentication skill:

```
/uipath:auth
```

And select the correct tenant when prompted.

## Support

- **GitHub Issues**: https://github.com/uipath/uipath-python/issues
- **Documentation**: https://docs.uipath.com
- **Community**: https://community.uipath.com

## License

MIT License - See LICENSE for details
