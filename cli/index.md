# CLI Reference

## auth

Authenticate with UiPath Cloud Platform.

The domain for authentication is determined by the UIPATH_URL environment variable if set. Otherwise, it can be specified with --cloud (default), --staging, or --alpha flags.

Interactive mode (default): Opens browser for OAuth authentication.

Unattended mode: Use --client-id, --client-secret, --base-url and --scope for client credentials flow.

Network options:

- Set HTTP_PROXY/HTTPS_PROXY/NO_PROXY environment variables for proxy configuration
- Set REQUESTS_CA_BUNDLE to specify a custom CA bundle for SSL verification
- Set UIPATH_DISABLE_SSL_VERIFY to disable SSL verification (not recommended)

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

Package requirements (bindings) are dependencies that are required by the automation package for successful execution.

For more information about package requirements, see [the official documentation](https://docs.uipath.com/orchestrator/automation-cloud/latest/user-guide/managing-package-requirements)

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
✓ Created 'entry-points.json' file.

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
[uv] pip install debugpy
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
