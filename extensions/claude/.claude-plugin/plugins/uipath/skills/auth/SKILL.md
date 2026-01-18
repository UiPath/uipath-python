---
description: Authenticate with UiPath using uipath auth --alpha
allowed-tools: Bash, AskUserQuestion
---

# UiPath Authentication

I'll help you authenticate with UiPath. Let me start by running the authentication command.

## Prerequisites Check

First, verify the UiPath SDK is available:

```bash
uv run uipath --version
```

If this command fails, you need to set up your project first with `/uipath:create-agent`.

## Running Authentication

Now I'll run the authentication command (this takes about 1 minute):

```bash
uv run uipath auth --alpha
```

## Tenant Selection

If the command prompts you to select a tenant, I will:
1. Extract and display the full list of available tenants
2. Ask you to choose one from the complete list
3. Input your selection into the authentication process

All available tenant options will be shown to you for selection.

Please wait for the command to complete and respond to any prompts that appear.