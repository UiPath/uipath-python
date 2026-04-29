# CLI Reference

## auth

Authenticate with UiPath Cloud Platform.

The authentication domain is determined in the following order:

1. The `UIPATH_URL` environment variable (if set).
1. A flag: `--cloud` (default), `--staging`, or `--alpha`.

**Modes:**

- Interactive (default): Opens a browser window for OAuth authentication.
- Unattended: Uses the client credentials flow. Requires `--client-id`, `--client-secret`, `--base-url`, and `--scope`.

**Environment Variables:**

- `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` — proxy configuration.
- `REQUESTS_CA_BUNDLE` — path to a custom CA bundle for SSL verification.
- `UIPATH_DISABLE_SSL_VERIFY` — disables SSL verification (not recommended).

**Examples:**

```
Interactive login (opens browser for OAuth):

$ uipath auth

Unattended login using client credentials:

$ uipath auth --base-url https://cloud.uipath.com/organization/tenant --client-id 00000000-0000-0000-0000-000000000000 --client-secret 'secret_value_here'
```

**Usage:**

```
auth [OPTIONS]
```

**Options:**

| Name              | Type    | Description                                                                                                  | Default          |
| ----------------- | ------- | ------------------------------------------------------------------------------------------------------------ | ---------------- |
| `--cloud`         | text    | Use production environment                                                                                   | `Sentinel.UNSET` |
| `--staging`       | text    | Use staging environment                                                                                      | `Sentinel.UNSET` |
| `--alpha`         | text    | Use alpha environment                                                                                        | `Sentinel.UNSET` |
| `-f`, `--force`   | boolean | Force new token                                                                                              | `False`          |
| `--client-id`     | text    | Client ID for client credentials authentication (unattended mode)                                            | `Sentinel.UNSET` |
| `--client-secret` | text    | Client secret for client credentials authentication (unattended mode)                                        | `Sentinel.UNSET` |
| `--base-url`      | text    | Base URL for the UiPath tenant instance (required for client credentials)                                    | `Sentinel.UNSET` |
| `--tenant`        | text    | Tenant name within UiPath Automation Cloud                                                                   | `Sentinel.UNSET` |
| `--scope`         | text    | Space-separated list of OAuth scopes to request (e.g., 'OR.Execution OR.Queues'). Defaults to 'OR.Execution' | `OR.Execution`   |
| `--help`          | boolean | Show this message and exit.                                                                                  | `False`          |

UiPath Automation Suite

For UiPath Automation Suite deployments, you must set the `UIPATH_URL` environment variable to your dedicated instance URL before running this command.

Example:

```
UIPATH_URL=https://your-instance.com/account/tenant/orchestrator_/
```

You can set this environment variable either:

- In a `.env` file in your project directory
- As a system-wide environment variable

uipath auth⠋ Authenticating with UiPath ...\
🔗 If a browser window did not open, please open the following URL in your browser: [LINK]\
👇 Select tenant:\
0: Tenant1\
1: Tenant2\
Select tenant number: 0\
Selected tenant: Tenant1\
✓ Authentication successful.

______________________________________________________________________

## init

Initialize the project.

**Usage:**

```
init [OPTIONS]
```

**Options:**

| Name                      | Type    | Description                                              | Default |
| ------------------------- | ------- | -------------------------------------------------------- | ------- |
| `--no-agents-md-override` | boolean | Won't override existing .agent files and AGENTS.md file. | `False` |
| `--help`                  | boolean | Show this message and exit.                              | `False` |

Initializes a UiPath project by generating all required configuration and metadata files. Run this command when setting up a new project and after modifying your agent's or function's input/output schema.

### Generated Files

| File                                                                                 | Description                                           |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| `uipath.json`                                                                        | Project configuration with entrypoint definitions     |
| `bindings.json`                                                                      | Resource bindings (assets, processes, buckets, etc.)  |
| `entry-points.json`                                                                  | Entry point definitions with input/output schemas     |
| `project.uiproj`                                                                     | Project metadata for StudioWeb integration            |
| `.uipath/studio_metadata.json`                                                       | Studio metadata (schema and code version)             |
| `.env`                                                                               | Environment variables file                            |
| `AGENTS.md`, `CLAUDE.md`                                                             | Agent documentation and coding assistant instructions |
| `.agent/CLI_REFERENCE.md`, `.agent/SDK_REFERENCE.md`, `.agent/REQUIRED_STRUCTURE.md` | Agent reference docs                                  |

Warning

The `uipath.json` file should include your entry points in the `functions` section:

```
{
  "functions": {
    "main": "main.py:main"
  }
}
```

Running `uipath init` will process these function definitions and create the corresponding `entry-points.json` file needed for deployment.

uipath init⠋ Initializing UiPath project ...\
✓ Created 'uipath.json' file.\
✓ Created 'bindings.json' file.\
✓ Created 'entry-points.json' file with 1 entrypoint(s).\
✓ Created 1 mermaid diagram file(s).\
✓ Updated 'project.uiproj' file.\
✓ Created '.uipath/studio_metadata.json' file.\
✓ Created: CLAUDE.md, CLI_REFERENCE.md, SDK_REFERENCE.md, AGENTS.md, REQUIRED_STRUCTURE.md.

Info

### About the `.mermaid` files

`uipath init` generates one `<entrypoint>.mermaid` file per function/agent containing a static call graph, rendered in the UiPath Orchestrator UI. These files are regenerated on every `uipath init`.

______________________________________________________________________

## run

Execute the project.

**Usage:**

```
run [OPTIONS] [ENTRYPOINT] [INPUT]
```

**Options:**

| Name                | Type    | Description                                                                                                              | Default          |
| ------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------- |
| `--resume`          | boolean | Resume execution from a previous state                                                                                   | `False`          |
| `-f`, `--file`      | path    | File path for the .json input                                                                                            | `Sentinel.UNSET` |
| `--input-file`      | path    | Alias for '-f/--file' arguments                                                                                          | `Sentinel.UNSET` |
| `--output-file`     | path    | File path where the output will be written                                                                               | `Sentinel.UNSET` |
| `--trace-file`      | path    | File path where the trace spans will be written (JSON Lines format)                                                      | `Sentinel.UNSET` |
| `--state-file`      | path    | File path where the state file is stored for persisting execution state. If not provided, a temporary file will be used. | `Sentinel.UNSET` |
| `--debug`           | boolean | Enable debugging with debugpy. The process will wait for a debugger to attach.                                           | `False`          |
| `--debug-port`      | integer | Port for the debug server (default: 5678)                                                                                | `5678`           |
| `--keep-state-file` | boolean | Keep the temporary state file even when not resuming and no job id is provided                                           | `False`          |
| `--help`            | boolean | Show this message and exit.                                                                                              | `False`          |

Tip

For step-by-step debugging with breakpoints and variable inspection (supported from `2.0.66` onward):

```
# Install debugpy package
uv pip install debugpy
# Run agent with debugging enabled
uipath run [ENTRYPOINT] [INPUT] --debug
```

For vscode:

1. add the [debug configuration](https://github.com/UiPath/uipath-python/blob/main/.vscode/launch.json) in your `.vscode/launch.json` file.
1. Place breakpoints in your code where needed.
1. Use the shortcut `F5`, or navigate to Run -> Start Debugging -> Python Debugger: Attach.

Upon starting the debugging process, one should see the following logs in terminal:

```
🐛 Debug server started on port 5678
📌 Waiting for debugger to attach...
  - VS Code: Run -> Start Debugging -> Python Debugger: Attach
✓  Debugger attached successfully!
```

Warning

Depending on the shell you are using, it may be necessary to escape the input json:

```
uipath run agent '{"topic": "UiPath"}'
```

```
uipath run agent "{""topic"": ""UiPath""}"
```

```
uipath run agent '{\"topic\":\"uipath\"}'
```

uipath run main '{"message": "test"}'[2025-04-11 10:13:58,857][INFO] {'message': 'test'}

______________________________________________________________________

## pack

Pack the project.

**Usage:**

```
pack [OPTIONS] [ROOT]
```

**Options:**

| Name       | Type    | Description                                               | Default |
| ---------- | ------- | --------------------------------------------------------- | ------- |
| `--nolock` | boolean | Skip running uv lock and exclude uv.lock from the package | `False` |
| `--help`   | boolean | Show this message and exit.                               | `False` |

Packages your project into a `.nupkg` file that can be deployed to UiPath.

Info

### Default Files Included in `.nupkg`

By default, the following file types are included in the `.nupkg` file:

- `.py`
- `.mermaid`
- `.json`
- `.yaml`
- `.yml`

______________________________________________________________________

### Including Extra Files

To include additional files, update the `uipath.json` file by adding a `packOptions` section. Use the following configuration format:

```
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

Warning

Your `pyproject.toml` must include:

- A description field (avoid characters: &, \<, >, ", ', ;)
- Author information

Example:

```
description = "Your package description"
authors = [{name = "Your Name", email = "your.email@example.com"}]
```

uipath pack⠋ Packaging project ...\
Name : test\
Version : 0.1.0\
Description: Add your description here\
Authors : Your Name\
✓ Project successfully packaged.

______________________________________________________________________

## publish

Publish the package.

**Usage:**

```
publish [OPTIONS]
```

**Options:**

| Name                   | Type    | Description                                             | Default          |
| ---------------------- | ------- | ------------------------------------------------------- | ---------------- |
| `--tenant`, `-t`       | text    | Whether to publish to the tenant package feed           | `Sentinel.UNSET` |
| `--my-workspace`, `-w` | text    | Whether to publish to the personal workspace            | `Sentinel.UNSET` |
| `--folder`, `-f`       | text    | Folder name to publish to (skips interactive selection) | `Sentinel.UNSET` |
| `--help`               | boolean | Show this message and exit.                             | `False`          |

Warning

To properly use the CLI for packaging and publishing, your project should include:

- A `pyproject.toml` file with project metadata
- A `uipath.json` file (generated by `uipath init`)
- Any Python files needed for your automation

uipath publish⠋ Fetching available package feeds...\
👇 Select package feed:\
0: Orchestrator Tenant Processes Feed\
1: Orchestrator Personal Workspace Feed\
Select feed number: 0\
Selected feed: Orchestrator Tenant Processes Feed\
⠸ Publishing most recent package: test.0.1.0.nupkg ...\
✓ Package published successfully!

______________________________________________________________________

## deploy

Pack and publish the project.

**Usage:**

```
deploy [OPTIONS] [ROOT]
```

**Options:**

| Name                   | Type    | Description                                             | Default          |
| ---------------------- | ------- | ------------------------------------------------------- | ---------------- |
| `--tenant`, `-t`       | text    | Whether to publish to the tenant package feed           | `Sentinel.UNSET` |
| `--my-workspace`, `-w` | text    | Whether to publish to the personal workspace            | `Sentinel.UNSET` |
| `--folder`, `-f`       | text    | Folder name to publish to (skips interactive selection) | `Sentinel.UNSET` |
| `--help`               | boolean | Show this message and exit.                             | `False`          |

______________________________________________________________________

## invoke

Invoke an agent published in my workspace.

**Usage:**

```
invoke [OPTIONS] [ENTRYPOINT] [INPUT]
```

**Options:**

| Name           | Type    | Description                   | Default          |
| -------------- | ------- | ----------------------------- | ---------------- |
| `-f`, `--file` | path    | File path for the .json input | `Sentinel.UNSET` |
| `--help`       | boolean | Show this message and exit.   | `False`          |

uipath invoke agent '{"topic": "UiPath"}'⠴ Loading configuration ...\
⠴ Starting job ...\
✨ Job started successfully!\
🔗 Monitor your job here: [LINK]

______________________________________________________________________

## push

Push local project files to Studio Web.

This command pushes the local project files to a UiPath Studio Web project. It ensures that the remote project structure matches the local files by:

- Updating existing files that have changed
- Uploading new files
- Deleting remote files that no longer exist locally
- Optionally managing the UV lock file

**Environment Variables:**

- `UIPATH_PROJECT_ID`: Required. The ID of the UiPath Cloud project

**Example:**

```
$ uipath push
$ uipath push --nolock
$ uipath push --overwrite
$ uipath push --ignore-resources
```

**Usage:**

```
push [OPTIONS]
```

**Options:**

| Name                 | Type    | Description                                                    | Default |
| -------------------- | ------- | -------------------------------------------------------------- | ------- |
| `--ignore-resources` | boolean | Skip importing the referenced resources to Studio Web solution | `False` |
| `--nolock`           | boolean | Skip running uv lock and exclude uv.lock from the package      | `False` |
| `--overwrite`        | boolean | Automatically overwrite remote files without prompts           | `False` |
| `--help`             | boolean | Show this message and exit.                                    | `False` |

uipath pushPushing UiPath project to Studio Web...\
Uploading 'main.py'\
Uploading 'uipath.json'\
Updating 'pyproject.toml'\
Uploading '.uipath/studio_metadata.json'

Importing referenced resources to Studio Web project...

🔵 Resource import summary: 0 total resources - 0 created, 0 updated, 0 unchanged, 0 not found

______________________________________________________________________

## pull

Pull remote project files from Studio Web.

This command pulls the remote project files from a UiPath Studio Web project.

**Environment Variables:** UIPATH_PROJECT_ID: Required. The ID of the UiPath Studio Web project

**Example:**

```
$ uipath pull
$ uipath pull /path/to/project
$ uipath pull --overwrite
```

**Usage:**

```
pull [OPTIONS]
```

**Options:**

| Name          | Type    | Description                                         | Default |
| ------------- | ------- | --------------------------------------------------- | ------- |
| `--overwrite` | boolean | Automatically overwrite local files without prompts | `False` |
| `--help`      | boolean | Show this message and exit.                         | `False` |

uipath pullPulling UiPath project from Studio Web...\
Processing: main.py\
Updated 'main.py'\
Processing: uipath.json\
File 'uipath.json' is up to date\
✓ Project pulled successfully

______________________________________________________________________

## debug

Debug the project.

**Usage:**

```
debug [OPTIONS] [ENTRYPOINT] [INPUT]
```

**Options:**

| Name            | Type              | Description                                                                    | Default          |
| --------------- | ----------------- | ------------------------------------------------------------------------------ | ---------------- |
| `--resume`      | boolean           | Resume execution from a previous state                                         | `False`          |
| `-f`, `--file`  | path              | File path for the .json input                                                  | `Sentinel.UNSET` |
| `--input-file`  | path              | Alias for '-f/--file' arguments                                                | `Sentinel.UNSET` |
| `--output-file` | path              | File path where the output will be written                                     | `Sentinel.UNSET` |
| `--debug`       | boolean           | Enable debugging with debugpy. The process will wait for a debugger to attach. | `False`          |
| `--debug-port`  | integer           | Port for the debug server (default: 5678)                                      | `5678`           |
| `--attach`      | choice (`signalr` | `console`                                                                      | `none`)          |
| `--help`        | boolean           | Show this message and exit.                                                    | `False`          |

Runs your agent under the debug runtime, with a debug bridge attached. Locally, the bridge is the interactive **console** (read commands from stdin, stop at breakpoints). In the cloud, the bridge is **SignalR** (driven by Studio Web / Orchestrator). The `--attach` flag lets you override that default, including `none` for executors that need the debug command's surrounding behavior (bindings fetch, state streaming) but cannot speak the interactive debug protocol.

### Attach modes

| Mode      | When to use                                                                                                     |
| --------- | --------------------------------------------------------------------------------------------------------------- |
| `signalr` | Remote runs driven by Studio Web / Orchestrator. Default when `job_id` is set.                                  |
| `console` | Local interactive debugging from the terminal. Default when no `job_id`.                                        |
| `none`    | Run under the debug command without attaching a debugger. No wait-for-start gate, no breakpoints, no step mode. |

Info

`--attach` selects the **debug bridge**. It's unrelated to `--debug`, which starts a `debugpy` server for Python-level breakpoints in your IDE. The two can be combined.

uipath debug main '{"message": "test"}'Debug Mode Commands\
c, continue Continue until next breakpoint\
s, step Step to next node\
b <node> Set breakpoint at <node>\
l, list List all breakpoints\
r <node> Remove breakpoint at <node>\
h, help Show help\
q, quit Exit debugger\
▶ STARTb analyze_sentiment✓ Breakpoint set at: analyze_sentimentc────────────────────────────────────────\
■ BREAKPOINT analyze_sentiment (before)\
Next: analyze_sentiment\
────────────────────────────────────────s● analyze_sentimentc✓ Execution completed

______________________________________________________________________

## eval

Run an evaluation set against the agent.

Args: entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified) eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified) eval_ids: Optional list of evaluation IDs eval_set_run_id: Custom evaluation set run ID (optional, will generate UUID if not specified) workers: Number of parallel workers for running evaluations no_report: Do not report the evaluation results enable_mocker_cache: Enable caching for LLM mocker responses report_coverage: Report evaluation coverage model_settings_id: Model settings ID to override agent settings trace_file: File path where traces will be written in JSONL format max_llm_concurrency: Maximum concurrent LLM requests input_overrides: Input field overrides mapping (direct field override with deep merge) resume: Resume execution from a previous suspended state

**Usage:**

```
eval [OPTIONS] [ENTRYPOINT] [EVAL_SET]
```

**Options:**

| Name                    | Type    | Description                                                                                                                              | Default          |
| ----------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| `--eval-ids`            | text    | N/A                                                                                                                                      | `[]`             |
| `--eval-set-run-id`     | text    | Custom evaluation set run ID (if not provided, a UUID will be generated)                                                                 | `Sentinel.UNSET` |
| `--no-report`           | boolean | Do not report the evaluation results                                                                                                     | `False`          |
| `--workers`             | integer | Number of parallel workers for running evaluations (default: 1)                                                                          | `1`              |
| `--output-file`         | path    | File path where the output will be written                                                                                               | `Sentinel.UNSET` |
| `--enable-mocker-cache` | boolean | Enable caching for LLM mocker responses                                                                                                  | `False`          |
| `--report-coverage`     | boolean | Report evaluation coverage                                                                                                               | `False`          |
| `--model-settings-id`   | text    | Model settings ID from evaluation set to override agent settings (default: 'default')                                                    | `default`        |
| `--trace-file`          | path    | File path where traces will be written in JSONL format                                                                                   | `Sentinel.UNSET` |
| `--max-llm-concurrency` | integer | Maximum concurrent LLM requests (default: 20)                                                                                            | `20`             |
| `--input-overrides`     | text    | Input field overrides per evaluation ID: '{"eval-1": {"operator": "\*"}, "eval-2": {"a": 100}}'. Supports deep merge for nested objects. | `{}`             |
| `--resume`              | boolean | Resume execution from a previous suspended state                                                                                         | `False`          |
| `--verbose`             | boolean | Include agent execution output (trace, result) in the output file                                                                        | `False`          |
| `--help`                | boolean | Show this message and exit.                                                                                                              | `False`          |

Runs an evaluation set against your agent. Entry point and eval set are auto-discovered from the project if not passed explicitly. Evaluations run in parallel (see `--workers`) and, unless `--no-report` is passed, results are reported back to Studio Web when `UIPATH_PROJECT_ID` is set.

### Common flags

| Flag                    | Purpose                                                            |
| ----------------------- | ------------------------------------------------------------------ |
| `--eval-ids`            | Run only a subset of evaluations by id.                            |
| `--workers`             | Parallel workers for running evaluations (default 1).              |
| `--no-report`           | Skip reporting results back to UiPath.                             |
| `--enable-mocker-cache` | Cache LLM mocker responses across runs.                            |
| `--input-overrides`     | Per-eval input overrides, merged into the eval's input.            |
| `--trace-file`          | Write OpenTelemetry traces to a JSONL file for offline inspection. |
| `--resume`              | Resume evaluation from a previous suspended state.                 |

uipath eval⠋ Running evaluations ...\
Weather in Paris\
LLM Judge Output 0.7\
Tool Call Arguments 1.0\
Tool Call Count 1.0\
Tool Call Order 1.0

Evaluation Results\
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓\
┃ Evaluation ┃ LLM Judge Output ┃ Tool Call Args ┃ Tool Call Count ┃ Tool Call Order ┃\
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩\
│ Weather in Paris │ 0.7 │ 1.0 │ 1.0 │ 1.0 │\
├────────────────────┼────────────────────┼────────────────────┼────────────────────┼────────────────────┤\
│ Average │ 0.7 │ 1.0 │ 1.0 │ 1.0 │\
└────────────────────┴────────────────────┴────────────────────┴────────────────────┴────────────────────┘
