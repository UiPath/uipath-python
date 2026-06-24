# CLI Reference

The following commands apply to both **coded functions** and **coded agents**. The entry point name (`main`, `agent`, or any key you define in `uipath.json`) is the first argument to `run`, `debug`, `eval`, and `invoke`.

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

/// info | Unattended Authentication (Client Credentials)

For CI/CD pipelines and other non-interactive contexts, authenticate with the OAuth client credentials flow by passing all three of `--client-id`, `--client-secret`, and `--base-url`. The CLI exchanges them for an access token and writes it to the same on-disk session used by interactive logins, so subsequent commands like `uipath publish` and `uipath invoke` work without further setup.

The `--base-url` must point at the tenant scope (`https://<host>/<organization>/<tenant>`). The optional `--scope` flag controls the OAuth scopes requested and defaults to `OR.Execution`. Pass a space-separated list (for example `"OR.Execution OR.Queues"`) to request additional scopes — match the scopes you granted to the External Application and the operations you intend to run.

**Setup:**

1. In the Automation Cloud **Admin** page, open **External Applications** and create one of type *Confidential*. Grant it the Orchestrator scopes you need (for example `OR.Execution`). See the [External Applications guide](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/managing-external-applications) for details.
2. Copy the generated **App ID** and **App Secret** — these become `--client-id` and `--client-secret`.

**Example:**

<!-- termynal -->
```shell
> uipath auth --client-id 12345678-c4c5-4f1f-93ff-4f5ab47d57ea \
              --client-secret 'your-secret' \
              --base-url https://cloud.uipath.com/your-org/your-tenant
✓  Authentication successful.
> uipath publish --tenant
```

/// warning
Treat `--client-secret` as a credential. In CI, prefer reading it from a secret store and passing it on the command line, rather than committing it to source control or leaving it in shell history.
///

**Configuring the same flow in code:** if you would rather skip the CLI session and pass credentials directly to the SDK, the [`asset-modifier-agent` sample](https://github.com/UiPath/uipath-python/tree/main/packages/uipath/samples/asset-modifier-agent) shows how to construct a `UiPath` client with `client_id`, `client_secret`, `scope`, and `base_url` from environment variables.

///

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

/// info
### About the `.mermaid` files

`uipath init` generates one `<entrypoint>.mermaid` file per function/agent containing a static call graph, rendered in the UiPath Orchestrator UI. These files are regenerated on every `uipath init`.
///

/// warning
### About the `id` field

The first `uipath init` mints a stable `id` (GUID) into `uipath.json` and preserves it across subsequent runs. It is what identifies your project consistently wherever it is deployed and run.

Do not change or remove it. Changing it makes the project look like a brand-new, unrelated one, so you lose the link to everything previously published and tracked under the old id. `uipath pack` rejects an `id` that is not a valid GUID.
///
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
# Run with debugging enabled
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
uipath run main '{"message": "hello"}'
```
///

/// tab | Windows CMD
```console
uipath run main "{""message"": ""hello""}"
```
///

/// tab | Windows PowerShell
```console
uipath run main '{\"message\":\"hello\"}'
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
- `.md`

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
            "<new file extension to include, with leading dot (e.g., '.go')>"
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

/// info
### Dependency Locking

By default, `uipath pack` includes `uv.lock` in the `.nupkg` (creating it if it does not exist). The executor then installs the pinned versions from the lock file, so every run uses the exact same dependency versions.

Use `--nolock` to opt out — `uv.lock` is not added to the package. With no lock file present, the executor resolves dependencies on each run and picks the latest versions compatible with the constraints in your `pyproject.toml`.

<!-- termynal -->
```shell
> uipath pack --nolock
⠋ Packaging project ...
✓  Project successfully packaged.
```

**When to lock (default):** you want reproducible runs and protection against breaking changes or malicious upgrades in your dependencies. The versions you tested with are the versions that run.

**When to use `--nolock`:** you want each run to pick up the latest patches automatically within your declared constraints, or your project does not use uv.
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
> uipath invoke main '{"message": "hello"}'
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

/// info
### Dependency Locking

By default, `uipath push` includes `uv.lock` in the upload (creating it if it does not exist). The executor then installs the pinned versions from the lock file, so every run uses the exact same dependency versions.

Use `--nolock` to opt out — `uv.lock` is not uploaded. With no lock file present, the executor resolves dependencies on each run and picks the latest versions compatible with the constraints in your `pyproject.toml`.

**When to lock (default):** you want reproducible runs and protection against breaking changes or malicious upgrades in your dependencies. The versions you tested with are the versions that run.

**When to use `--nolock`:** you want each run to pick up the latest patches automatically within your declared constraints, or your project does not use uv.
///

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
---

::: mkdocs-click
    :module: uipath._cli
    :command: debug
    :depth: 1
    :style: table

Runs your project under the debug runtime, with a debug bridge attached. Locally, the bridge is the interactive **console** (read commands from stdin, stop at breakpoints). In the cloud, the bridge is **SignalR** (driven by Studio Web / Orchestrator). The `--attach` flag lets you override that default, including `none` for executors that need the debug command's surrounding behavior (bindings fetch, state streaming) but cannot speak the interactive debug protocol.

### Attach modes

| Mode | When to use |
|------|-------------|
| `signalr` | Remote runs driven by Studio Web / Orchestrator. Default when `job_id` is set. |
| `console` | Local interactive debugging from the terminal. Default when no `job_id`. |
| `none` | Run under the debug command without attaching a debugger. No wait-for-start gate, no breakpoints, no step mode. |

/// info
`--attach` selects the **debug bridge**. It's unrelated to `--debug`, which starts a `debugpy` server for Python-level breakpoints in your IDE. The two can be combined.
///

<!-- termynal -->

```shell
> uipath debug main '{"message": "test"}'
Debug Mode Commands
  c, continue     Continue until next breakpoint
  s, step         Step to next node
  b <node>        Set breakpoint at <node>
  l, list         List all breakpoints
  r <node>        Remove breakpoint at <node>
  h, help         Show help
  q, quit         Exit debugger
▶ START
> b analyze_sentiment
✓ Breakpoint set at: analyze_sentiment
> c
────────────────────────────────────────
■ BREAKPOINT analyze_sentiment (before)
Next: analyze_sentiment
────────────────────────────────────────
> s
● analyze_sentiment
> c
✓ Execution completed
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: eval
    :depth: 1
    :style: table

Runs an evaluation set against your project. Entry point and eval set are auto-discovered from the project if not passed explicitly. Evaluations run in parallel (see `--workers`) and, unless `--no-report` is passed, results are reported back to Studio Web when `UIPATH_PROJECT_ID` is set.

### Common flags

| Flag | Purpose |
|------|---------|
| `--eval-ids` | Run only a subset of evaluations by id. |
| `--workers` | Parallel workers for running evaluations (default 1). |
| `--no-report` | Skip reporting results back to UiPath. |
| `--enable-mocker-cache` | Cache LLM mocker responses across runs. |
| `--input-overrides` | Per-eval input overrides, merged into the eval's input. |
| `--trace-file` | Write OpenTelemetry traces to a JSONL file for offline inspection. |
| `--resume` | Resume evaluation from a previous suspended state. |

<!-- termynal -->

```shell
> uipath eval
⠋ Running evaluations ...
  Weather in Paris
  LLM Judge Output       0.7
  Tool Call Arguments    1.0
  Tool Call Count        1.0
  Tool Call Order        1.0

Evaluation Results
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃  Evaluation        ┃  LLM Judge Output  ┃  Tool Call Args    ┃  Tool Call Count   ┃  Tool Call Order   ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│  Weather in Paris  │               0.7  │               1.0  │               1.0  │               1.0  │
├────────────────────┼────────────────────┼────────────────────┼────────────────────┼────────────────────┤
│  Average           │               0.7  │               1.0  │               1.0  │               1.0  │
└────────────────────┴────────────────────┴────────────────────┴────────────────────┴────────────────────┘
```
