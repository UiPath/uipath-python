# Agent Code Patterns Reference

This document provides practical code patterns for building UiPath coded agents using LangGraph and the UiPath Python SDK.

---

## Documentation Structure

This documentation is split into multiple files for efficient context loading. Load only the files you need:

### Core Documentation Files

1. **@.agent/REQUIRED_STRUCTURE.md** - Agent structure patterns and templates
   - **When to load:** Creating a new agent or understanding required patterns
   - **Contains:** Required Pydantic models (Input, State, Output), LLM initialization patterns, standard agent template
   - **Size:** ~90 lines

2. **@.agent/SDK_REFERENCE.md** - Complete SDK API reference
   - **When to load:** Calling UiPath SDK methods, working with services (actions, assets, jobs, etc.)
   - **Contains:** All SDK services and methods with full signatures and type annotations
   - **Size:** ~400 lines

3. **@.agent/CLI_REFERENCE.md** - CLI commands documentation
   - **When to load:** Working with `uipath init`, `uipath run`, or `uipath eval` commands
   - **Contains:** Command syntax, options, usage examples, and workflows
   - **Size:** ~200 lines

### Usage Guidelines

**For LLMs:**
- Read this file (AGENTS.md) first to understand the documentation structure
- Load .agent/REQUIRED_STRUCTURE.md when building new agents or need structure reference
- Load .agent/SDK_REFERENCE.md only when you need to call specific SDK methods
- Load .agent/CLI_REFERENCE.md only when working with CLI commands

**Benefits:**
- Reduced token usage by loading only relevant context
- Faster response times
- More focused context for specific tasks
