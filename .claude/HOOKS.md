# Claude Code Hooks

This project uses Claude Code hooks to ensure Python code quality and prevent CI/CD failures.

## How Hooks Work

Hooks are configured in `.claude/settings.json` and automatically execute scripts when certain events occur. The hooks receive JSON input via stdin and can process files before showing results to Claude.

## Configured Hooks

### PostToolUse Hook

**Triggers**: Automatically runs after `Edit`, `Write`, or `MultiEdit` tool calls

**What it does**:
- Monitors all file edits made by Claude Code
- Detects Python files (`.py`)
- Automatically runs `uv run ruff format` to format the file
- Automatically runs `uv run ruff check --fix` to fix auto-fixable linting issues
- Ensures all code changes meet project quality standards

**Configuration**: `.claude/settings.json`
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/lint-and-format.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Script Location**: `.claude/hooks/lint-and-format.sh`

## Python Tooling

This project uses the following tools:

- **Ruff**: Fast Python linter and formatter (replaces Black, isort, flake8, etc.)
- **MyPy**: Static type checker
- **Pre-commit**: Git hooks framework (optional)

### Ruff Configuration

Located in `pyproject.toml`:
- Line length: 88 characters
- Linting: Enabled for errors (E), pyflakes (F), bugbear (B), imports (I), docstrings (D)
- Formatting: Double quotes, space indentation
- Excludes: `samples/**`, `testcases/**`

## Hook Script

### lint-and-format.sh

Located at `.claude/hooks/lint-and-format.sh`

This script:
1. Reads JSON input from stdin (provided by Claude Code)
2. Extracts the `file_path` from `tool_input`
3. Checks if it's a Python file (`.py`)
4. Runs `uv run ruff format <file>` to format the file
5. Runs `uv run ruff check --fix <file>` to fix linting issues
6. Outputs status messages

## How to Test

To test if hooks are working:

1. **Make a change to a Python file**:
   ```bash
   echo "# test comment" >> src/uipath/__init__.py
   ```

2. **Watch for hook execution messages**:
   - You should see "🔧 Auto-formatting and linting src/uipath/__init__.py..."
   - Followed by "✅ Formatted and linted src/uipath/__init__.py"

3. **Verify the file was formatted**:
   ```bash
   git diff src/uipath/__init__.py
   ```

## Manual Linting

If you need to manually run linting:

```bash
# Format code
uv run ruff format .

# Check linting (without fixing)
uv run ruff check .

# Fix linting issues
uv run ruff check --fix .

# Run type checking
uv run mypy --config-file pyproject.toml .

# Run all CI checks locally
uv run ruff check . && uv run ruff format --check . && uv run mypy --config-file pyproject.toml .
```

## Troubleshooting

### Hooks Not Running

1. **Check hook configuration**:
   ```bash
   # In Claude Code, run:
   /hooks
   ```
   This shows all registered hooks.

2. **Verify script is executable**:
   ```bash
   chmod +x .claude/hooks/lint-and-format.sh
   ```

3. **Test script manually**:
   ```bash
   echo '{"tool_input":{"file_path":"src/uipath/__init__.py"}}' | .claude/hooks/lint-and-format.sh
   ```

4. **Check for errors in debug mode**:
   ```bash
   claude --debug
   ```

### Common Issues

- **Script not found**: Ensure `.claude/hooks/lint-and-format.sh` exists and is executable
- **uv not found**: Ensure `uv` is installed (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Ruff not found**: Run `uv sync` to install dependencies
- **Permission denied**: Run `chmod +x .claude/hooks/lint-and-format.sh`
- **Hooks modified externally**: Restart Claude Code to load new hook configuration

## CI/CD Integration

The CI/CD pipeline (`.github/workflows/lint.yml`) runs:
- `uv run mypy --config-file pyproject.toml .` - Static type checking
- `uv run ruff check .` - Linting
- `uv run ruff format --check .` - Format checking
- `uv run python scripts/lint_httpx_client.py` - Custom linting

The PostToolUse hook ensures that files touched by Claude Code are automatically formatted and linted, preventing CI/CD failures.

## Commit Message Format

This project uses conventional commits for commit messages. All commits must follow the format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semi-colons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example**:
```
feat(cli): add new eval command for running evaluations

- Implement eval command with support for evaluation sets
- Add progress reporting to Studio Web
- Support both legacy and coded evaluation formats

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Hook Execution Details

- **Timeout**: 30 seconds per hook execution
- **Environment**: Runs in project directory with `CLAUDE_PROJECT_DIR` environment variable
- **Input**: JSON via stdin containing tool name, tool input, and session information
- **Output**:
  - Exit code 0: Success (output shown to user)
  - Exit code 2: Blocking error (stderr shown to Claude)
  - Other codes: Non-blocking error (stderr shown to user)

## Modifying Hooks

To modify hook behavior:

1. **Edit the hook script**: `.claude/hooks/lint-and-format.sh`
2. **Or update configuration**: `.claude/settings.json`
3. **Restart Claude Code** to load changes (or review changes in `/hooks` menu)

**Note**: For security, hook configuration changes require review before taking effect.

## Resources

- [Claude Code Hooks Documentation](https://code.claude.com/docs/en/hooks)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [UV Package Manager](https://docs.astral.sh/uv/)
