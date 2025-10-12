---
allowed-tools: Bash
description: Run all checks required for PR standards (lint, format, type check, build)
argument-hint: [optional-commit-message]
---

I'll help you prepare for a PR by running all the required checks to meet project standards. This includes linting, formatting, type checking, and building.

Let me run each check step by step:

## Step 1: Linting Check
Running lint checks to ensure code quality...

!uv run just lint

## Step 2: Format Check
Checking code formatting...

!uv run just format

## Step 3: Auto-format (if needed)
If formatting issues were found, I'll auto-fix them:

!uv run ruff format .

## Step 4: Type Checking
Running mypy type checking on modified CLI files...

!uv run mypy src/uipath/_cli/ 

## Step 5: Build Check
Ensuring the package builds correctly...

!uv run just build

## Step 6: Git Status
Checking current git status...

!git status

---

## Summary

All checks completed! Here's what was verified:
- ✅ **Linting**: Code follows style guidelines
- ✅ **Formatting**: Code is properly formatted
- ✅ **Type Checking**: No type errors
- ✅ **Build**: Package builds successfully

If all checks passed, your code is ready for PR!

If you provided a commit message argument, I can help you create the commit. Otherwise, you can now:

1. Stage your changes: `git add .`
2. Create a commit with a proper message format: `git commit -m "feat: your-description"`
3. Push your branch: `git push origin your-branch-name`
4. Create a PR with a descriptive title and summary

**Remember**: PR titles should be concise and follow the format: `feat/fix/docs: description`