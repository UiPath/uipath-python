# Contributing to UiPath Runtime SDK

## Local Development Setup

### Prerequisites

1. **Install Python ≥ 3.11**:
    - Download and install Python 3.11 from the official [Python website](https://www.python.org/downloads/)
    - Verify the installation by running:
        ```sh
        python3.11 --version
        ```

    Alternative: [mise](https://mise.jdx.dev/lang/python.html)

2. **Install [uv](https://docs.astral.sh/uv/)**:
    Follow the official installation instructions for your operating system.

3. **Create a virtual environment in the current working directory**:
    ```sh
    uv venv
    ```

4. **Activate the virtual environment**:
    - Linux/Mac
    ```sh
    source .venv/bin/activate
    ```
    - Windows Powershell
    ```sh
    .venv\Scripts\Activate.ps1
    ```
    - Windows Bash
    ```sh
    source .venv/Scripts/activate
    ```

5. **Install dependencies**:
    ```sh
    uv sync --all-extras --no-cache
    ```

For additional commands related to linting, formatting, and building, run `just --list`.

### Using the SDK Locally

1. Create a project directory:
    ```sh
    mkdir project
    cd project
    ```

2. Initialize the Python project:
    ```sh
    uv init . --python 3.11
    ```

3. Set the SDK path:
    ```sh
    PATH_TO_SDK=/Users/YOUR_USERNAME/uipath-platform-python
    ```

4. Install the SDK in editable mode:
    ```sh
    uv add --editable ${PATH_TO_SDK}
    ```

> **Note:** Instead of cloning the project into `.venv/lib/python3.11/site-packages/uipath-platform`, this mode creates a file named `_uipath-platform.pth` inside `.venv/lib/python3.11/site-packages`. This file contains the value of `PATH_TO_SDK`, which is added to `sys.path`—the list of directories where Python searches for packages. To view the entries, run `python -c 'import sys; print(sys.path)'`.

## Service URL Overrides

When developing a UiPath service locally, you can redirect SDK requests to your local server using environment variables:

```bash
UIPATH_SERVICE_URL_<SERVICE>=http://localhost:<port>
```

The service name maps from the endpoint prefix — strip the trailing underscore and uppercase it:

| Prefix              | Env var                              |
|---------------------|--------------------------------------|
| `agenthub_/`        | `UIPATH_SERVICE_URL_AGENTHUB`        |
| `orchestrator_/`    | `UIPATH_SERVICE_URL_ORCHESTRATOR`    |
| `agentsruntime_/`   | `UIPATH_SERVICE_URL_AGENTSRUNTIME`   |
| `du_/`              | `UIPATH_SERVICE_URL_DU`              |
| `ecs_/`             | `UIPATH_SERVICE_URL_ECS`             |
| `connections_/`     | `UIPATH_SERVICE_URL_CONNECTIONS`     |
| `identity_/`        | `UIPATH_SERVICE_URL_IDENTITY`        |
| `apps_/`            | `UIPATH_SERVICE_URL_APPS`            |
| `datafabric_/`      | `UIPATH_SERVICE_URL_DATAFABRIC`      |
| `resourcecatalog_/` | `UIPATH_SERVICE_URL_RESOURCECATALOG` |

### What happens

1. The org/tenant prefix and service prefix are stripped — your local server receives only the API path:

   ```
   agenthub_/llm/api/chat/completions → http://localhost:5200/llm/api/chat/completions
   orchestrator_/odata/Processes      → http://localhost:5300/odata/Processes
   ```

2. Routing headers (`X-UiPath-Internal-TenantId`, `X-UiPath-Internal-AccountId`) are injected automatically since the platform routing layer is bypassed.

### Example `.env`

```bash
UIPATH_URL=https://alpha.uipath.com/org/tenant
UIPATH_ACCESS_TOKEN=your-token
UIPATH_ORGANIZATION_ID=your-org-id
UIPATH_TENANT_ID=your-tenant-id

# Override agenthub and orchestrator to local servers
UIPATH_SERVICE_URL_AGENTHUB=http://localhost:5200
UIPATH_SERVICE_URL_ORCHESTRATOR=http://localhost:5300
```
