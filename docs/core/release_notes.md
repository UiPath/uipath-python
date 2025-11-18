# 🚨 Breaking Changes for UiPath Python SDK (v2.2.0+)

**Release Date:** November 26, 2025

Version 2.2.0 of the **UiPath Python SDK** introduces several breaking changes affecting both the SDK and CLI.

## Breaking Changes

### 1. Minimum Python Version: 3.11+ Required

**What's changing:** Python 3.10 is no longer supported for `uipath-python`, `uipath-langchain-python`, `uipath-llamaindex-python`.

**Action required:** Upgrade to Python 3.11 or higher.

### 2. Import Path Change

**What's changing:** The `UiPath` class has moved from `uipath` to `uipath.platform`.

**Action required:** Update your imports:

```python
# Before
from uipath import UiPath
from uipath.models import Job, Asset, Queue
from uipath.models import Entity 

# After
from uipath.platform import UiPath, Job, Asset, Queue

client = UiPath(...)
```

### 3. Transition to LangChain v1 (for `uipath-langchain` only)

**What's changing:** Minimum required versions are now LangChain 1.0.0+ and LangGraph 1.0.0+

**Action required:** Review and update your code according to the [LangChain v1 Migration Guide](https://docs.langchain.com/oss/python/migrate/langchain-v1).

**Note:** This only applies if you're using the `uipath-langchain` package.

### 4. Configuration Architecture Redesign

We've restructured how UiPath projects define and manage their resources:

**`uipath.json` - Configuration File (Updated Purpose)**
- Previously contained entrypoints and bindings; now serves as a streamlined configuration file
- For **pure Python scripts**, define entrypoints in the `functions` section:
  ```json
  {
    "functions": {
      "entrypoint1": "src/main.py:",
      "entrypoint2": "src/graph.py:runtime"
    }
  }
  ```
- For **LangGraph graphs**, define entrypoints in `langgraph.json` (same as before)
- For **LlamaIndex workflows**, define entrypoints in `llamaindex.json` (same as before)

**`bindings.json` - Manual Binding Definitions (New)**
- Overridable resources (bindings) now stored in a separate file
- Bindings are **no longer automatically inferred** from code
- Must be manually defined by the user for now (we're working on an interactive configurator to simplify this process)

**`entry-points.json` - I/O Schema (New)**
- Contains the input/output schema for your entrypoints
- Automatically inferred from code based on entrypoints defined in `llamaindex.json`/`langgraph.json`/`uipath.json`

## Migration Guide

### Stay on v2.1.x

To avoid these breaking changes and keep your current setup, pin your dependency in `pyproject.toml`:

```toml
"uipath>=2.1.x,<2.2.0"
```

**For `uipath-langchain` users:** To stay on the current version without LangChain v1:
```toml
"uipath-langchain>=0.0.x,<0.1.0"
```

### Migrate to v2.2.0+

1. **Upgrade to v2.2.0+**
   
   Update the dependencies in `pyproject.toml` with:
   ```toml
   "uipath>=2.2.x,<2.3.0"
   ```

   Bounding the version to <2.3.0 prevents future breaking changes
   
   **For `uipath-langchain` users:**
    To migrate to LangChain v1:
   ```toml
   "uipath-langchain>=0.1.0,<0.2.0"
   ```
   **For `uipath-langchain`/`uipath-llamaindex` users:**
   Make sure to also reference `uipath` in your `pyproject.toml` - future versions will no longer reference the main `uipath` CLI package as a dependency.

2. **Upgrade the Python version to 3.11+**
   
   In `pyproject.toml` specify the required Python version by adding or updating the following field:
   ```toml
   requires-python = ">=3.11"
   ```

3. **Update imports**
   
   Change `from uipath import UiPath` to `from uipath.platform import UiPath`.

4. **Review LangChain v1 changes (if using `uipath-langchain`)**
   
   Review the [LangChain v1 Migration Guide](https://docs.langchain.com/oss/python/migrate/langchain-v1) and update your code accordingly.

5. **Update configuration files**
   
   - **Define your entrypoints** in `scripts` within `uipath.json` (not applicable if you already use `langgraph.json`/`llamaindex.json`)
   - **Run `uipath init`** to automatically generate the `entry-points.json` I/O schema from your configuration
   - **Create `bindings.json`** and manually define all overridable resources
   - **Important:** If you update your script/agent code, run `uipath init` again to regenerate the I/O schema

---

For questions or issues, please open a ticket: [UiPath Python SDK Submit Issue](https://github.com/UiPath/uipath-python/issues)