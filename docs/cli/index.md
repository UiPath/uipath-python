# CLI Reference

::: mkdocs-click
    :module: uipath._cli
    :command: auth
    :depth: 1
    :style: table

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

/// warning

The `uipath init` command executes your `main.py` file to analyze its structure and collect information about inputs and outputs.
///

<!-- termynal -->
```shell
> uipath init
⠋ Initializing UiPath project ...
✓  Created 'uipath.json' file.
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: run
    :depth: 1
    :style: table

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
> uipath run main.py '{"message": "test"}'
[2025-04-11 10:13:58,857][INFO] {'message': 'test'}
```
---

::: mkdocs-click
    :module: uipath._cli
    :command: pack
    :depth: 1
    :style: table

Packages your project into a `.nupkg` file that can be deployed to UiPath.

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