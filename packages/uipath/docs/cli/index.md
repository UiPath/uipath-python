# CLI Reference

::: mkdocs-click
    :module: uipath._cli
    :command: auth
    :depth: 1
    :style: table

/// info | UiPath Automation Suite
For UiPath Automation Suite deployments, you must set the `UIPATH_URL` environment variable to your dedicated instance URL before running this command.

Example:
```bash
UIPATH_URL=https://your-instance.com/account/tenant/orchestrator_/
```

You can set this environment variable either:
- In a `.env` file in your project directory
- As a system-wide environment variable
///

<!-- termynal -->

```shell
> uipath auth
⠋ Authenticating with UiPath ...
🔗 If a browser window did not open, please open the following URL in your browser: [LINK]
👇 Select tenant:
  0: Tenant1
  1: Tenant2
Select tenant number: 0
Selected tenant: Tenant1
✓  Authentication successful.
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: init
    :depth: 1
    :style: table

Initializes a UiPath project by generating all required configuration and metadata files. Run this command when setting up a new project and after modifying your agent's or function's input/output schema.

### Generated Files

| File | Description |
|------|-------------|
| `uipath.json` | Project configuration with entrypoint definitions |
| `bindings.json` | Resource bindings (assets, processes, buckets, etc.) |
| `entry-points.json` | Entry point definitions with input/output schemas |
| `project.uiproj` | Project metadata for StudioWeb integration |
| `.uipath/studio_metadata.json` | Studio metadata (schema and code version) |
| `.env` | Environment variables file |
| `AGENTS.md`, `CLAUDE.md` | Agent documentation and coding assistant instructions |
| `.agent/CLI_REFERENCE.md`, `.agent/SDK_REFERENCE.md`, `.agent/REQUIRED_STRUCTURE.md` | Agent reference docs |

/// warning

The `uipath.json` file should include your entry points in the `functions` section:
```json
{
  "functions": {
    "main": "main.py:main"
  }
}
```

Running `uipath init` will process these function definitions and create the corresponding `entry-points.json` file needed for deployment.
///


<!-- termynal -->
```shell
> uipath init
⠋ Initializing UiPath project ...
✓  Created 'uipath.json' file.
✓  Created 'bindings.json' file.
✓  Created 'entry-points.json' file with 1 entrypoint(s).
✓  Created 1 mermaid diagram file(s).
✓  Updated 'project.uiproj' file.
✓  Created '.uipath/studio_metadata.json' file.
✓  Created: CLAUDE.md, CLI_REFERENCE.md, SDK_REFERENCE.md, AGENTS.md, REQUIRED_STRUCTURE.md.
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: run
    :depth: 1
    :style: table

/// tip
For step-by-step debugging with breakpoints and variable inspection (supported from `2.0.66` onward):
```console
# Install debugpy package
uv pip install debugpy
# Run agent with debugging enabled
uipath run [ENTRYPOINT] [INPUT] --debug
```
For vscode:
1. add the [debug configuration](https://github.com/UiPath/uipath-python/blob/main/.vscode/launch.json) in your `.vscode/launch.json` file.
2. Place breakpoints in your code where needed.
3. Use the shortcut `F5`, or navigate to Run -> Start Debugging -> Python Debugger: Attach.

Upon starting the debugging process, one should see the following logs in terminal:
```console
🐛 Debug server started on port 5678
📌 Waiting for debugger to attach...
  - VS Code: Run -> Start Debugging -> Python Debugger: Attach
✓  Debugger attached successfully!
```
///

/// warning
Depending on the shell you are using, it may be necessary to escape the input json:

/// tab | Bash/ZSH
```console
uipath run agent '{"topic": "UiPath"}'
```
///

/// tab | Windows CMD
```console
uipath run agent "{""topic"": ""UiPath""}"
```
///

/// tab | Windows PowerShell
```console
uipath run agent '{\"topic\":\"uipath\"}'
```
///

///

<!-- termynal -->

```shell
> uipath run main '{"message": "test"}'
[2025-04-11 10:13:58,857][INFO] {'message': 'test'}
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: trace
    :depth: 1
    :style: table

Visualize an agent execution trace. Reads JSONL trace files produced by `uipath run --trace-file` or `uipath eval --trace-file`, and renders a span tree showing the agent's trajectory.

<!-- termynal -->

```shell
> uipath run main '{"query": "hello"}' --trace-file
Trace written to .uipath/traces/run_2026-04-07T14-58-30.jsonl
> uipath trace view .uipath/traces/run_2026-04-07T14-58-30.jsonl
Trace abcdef12…34567890
└── agent (12.5s) ✓
    ├── input: {"messages": [{"role": "user", "content": "Book a flight..."}]}
    ├── LLM (gpt-4o) (2.2s) ✓
    │   └── tokens: prompt=847, completion=156, total=1003
    ├── 🔧 search_flights (1.7s) ✓
    │   ├── input: {"origin": "SFO", "destination": "NRT"}
    │   └── output: {"flights": [...]}
    ├── LLM (gpt-4o) (1.8s) ✓
    │   └── tokens: prompt=1456, completion=203, total=1659
    └── 🔧 book_flight (1.2s) ✓
        └── output: {"confirmation": {"booking_ref": "BK-UA837"}}
9 spans total
```

/// tip
Use `--trace-file` without a path to automatically write traces to `.uipath/traces/`, then use `uipath trace list` to find them:
```console
uipath run main '{"query": "hello"}' --trace-file
uipath trace list
uipath trace view .uipath/traces/run_2026-04-07T14-58-30.jsonl
```
///

/// tip
Use `--contains` to search across eval traces and extract full agent trajectories where a specific function was called:
```console
uipath eval main eval-set.json --trace-file traces.jsonl
uipath trace view traces.jsonl --contains "get_random*"
```
///

---

::: mkdocs-click
    :module: uipath._cli
    :command: pack
    :depth: 1
    :style: table

Packages your project into a `.nupkg` file that can be deployed to UiPath.

/// info
### Default Files Included in `.nupkg`

By default, the following file types are included in the `.nupkg` file:

- `.py`
- `.mermaid`
- `.json`
- `.yaml`
- `.yml`

---

### Including Extra Files

To include additional files, update the `uipath.json` file by adding a `packOptions` section. Use the following configuration format:

```json
{
    "packOptions": {
        "filesIncluded": [
            "<file here>"
        ],
        "fileExtensionsIncluded": [
            "<new file extension to include (e.g., 'go')>"
        ]
    }
}
```

///

/// warning
Your `pyproject.toml` must include:

-   A description field (avoid characters: &, <, >, ", ', ;)
-   Author information

Example:

```toml
description = "Your package description"
authors = [{name = "Your Name", email = "your.email@example.com"}]
```
///

<!-- termynal -->
```shell
> uipath pack
⠋ Packaging project ...
Name       : test
Version    : 0.1.0
Description: Add your description here
Authors    : Your Name
✓  Project successfully packaged.
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: publish
    :depth: 1
    :style: table

/// warning
To properly use the CLI for packaging and publishing, your project should include:

-   A `pyproject.toml` file with project metadata
-   A `uipath.json` file (generated by `uipath init`)
-   Any Python files needed for your automation
///

<!-- termynal -->

```shell
> uipath publish
⠋ Fetching available package feeds...
👇 Select package feed:
  0: Orchestrator Tenant Processes Feed
  1: Orchestrator Personal Workspace Feed
Select feed number: 0
Selected feed: Orchestrator Tenant Processes Feed
⠸ Publishing most recent package: test.0.1.0.nupkg ...
✓  Package published successfully!
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: deploy
    :depth: 1
    :style: table

---

::: mkdocs-click
    :module: uipath._cli
    :command: invoke
    :depth: 1
    :style: table

<!-- termynal -->

```shell
> uipath invoke agent '{"topic": "UiPath"}'
⠴ Loading configuration ...
⠴ Starting job ...
✨ Job started successfully!
🔗 Monitor your job here: [LINK]
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: push
    :depth: 1
    :style: table

<!-- termynal -->

```shell
> uipath push
Pushing UiPath project to Studio Web...
Uploading 'main.py'
Uploading 'uipath.json'
Updating 'pyproject.toml'
Uploading '.uipath/studio_metadata.json'

Importing referenced resources to Studio Web project...

 🔵 Resource import summary: 0 total resources - 0 created, 0 updated, 0 unchanged, 0 not found
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: pull
    :depth: 1
    :style: table

<!-- termynal -->

```shell
> uipath pull
Pulling UiPath project from Studio Web...
Processing: main.py
Updated 'main.py'
Processing: uipath.json
File 'uipath.json' is up to date
✓  Project pulled successfully
```
