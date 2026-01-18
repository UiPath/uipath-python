---
description: UiPath Python SDK assistant - Create, run, and evaluate coded agents
allowed-tools: Bash, Read, Write, Glob, Grep
contextAware: true
autoDetect: true
---

# UiPath Python SDK Assistant

Welcome to the UiPath Python SDK Assistant! This tool helps you create, run, and evaluate UiPath coded agents with AI-powered assistance.

The assistant automatically detects your UiPath project structure—no setup needed!

## 📍 Project Context (Auto-Detected)

I've detected your current directory. Analyzing project structure...

**Project Status:**
- UiPath Project: Checking...
- Agents: Detecting...
- Evaluations: Scanning...

The context is cached and automatically refreshed as you work. You can use skills directly without needing this menu!

---

## Available Commands

### 🚀 Create a New Agent
**Command:** `/create-agent [agent-name]`
- Creates a new UiPath agent from scratch
- Interactive setup with input/output field configuration
- AI-powered business logic implementation
- Auto-generates Pydantic models and main function

### ▶️ Run an Agent
**Command:** `/run-agent [agent-name]`
- Execute an existing UiPath agent interactively
- Schema-driven input prompts
- Displays results in output panel
- Test agents without leaving Claude Code
- ℹ️ Requires: entry-points.json (create with `/create-agent`)

### 📋 Create Evaluation Test Cases
**Command:** `/create-eval [eval-name]`
- Create comprehensive test cases for your agents
- Define expected inputs and outputs
- AI-assisted test data generation
- Generates evaluation JSON files
- ℹ️ Requires: uipath.json project

### 🧪 Run Evaluations
**Command:** `/run-eval [eval-file]`
- Execute evaluation test cases against your agents
- View detailed results with pass/fail status
- Analyze performance metrics
- Get insights on failing test cases
- ℹ️ Requires: entry-points.json and evaluation files

### 📊 List Resources
**Command:** `/list [agents|evals]`
- View all agents in current project
- List available evaluation sets
- See input/output summaries
- Quick actions for each resource

---

## 🎯 Smart Command Detection

Based on your project context, the extension will:
- ✅ Auto-show available agents when you run `/run-agent`
- ✅ Auto-list evaluations when you run `/run-eval`
- ✅ Auto-detect missing requirements and show helpful guidance
- ✅ Cache project info for fast subsequent commands

**Example:**
- If you have agents, just type `/run-agent` and select from list
- If you have evaluations, just type `/run-eval` without specifying file
- If something's missing, you'll get a clear message on how to fix it

---

## Quick Start

### First Time?
1. Start with: `/create-agent my-first-agent`
2. Then run: `/run-agent my-first-agent`
3. Create tests: `/create-eval my-tests`
4. Run tests: `/run-eval my-tests`

### Have a Project?
- Just type `/run-agent` - auto-detects your agents
- Just type `/run-eval` - auto-discovers your tests
- Just type `/list` - see everything at once

---

## Tips

- All agents use the UiPath SDK with automatic tracing
- Input/output fields are strongly typed with Pydantic
- Evaluations support multiple test cases and custom metrics
- **Context is cached automatically** - instant detection on subsequent commands
- The extension works globally—use it in any directory!
- No `/uipath` needed! Use skills directly: `/create-agent`, `/run-agent`, etc.

---

## Context Awareness

**Automatic Detection:**
- Detects UiPath projects in current directory
- Caches agent and evaluation metadata
- Refreshes context every 5 minutes
- Makes context available to all skills via environment variables

**You don't need to run `/uipath`** to get context. Use skills directly:
```bash
/run-agent           # Auto-detects agents from cache
/run-eval            # Auto-discovers evaluation files
/list                # Shows cached project overview
/create-eval         # Uses cached project info
```

---

For more help, visit: https://github.com/uipath/uipath-python/docs
