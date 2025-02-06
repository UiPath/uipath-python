# UiPath SDK

## Setup

1. **Install Python 3.13**:

    - Download and install Python 3.13 from the official [Python website](https://www.python.org/downloads/).
    - Verify the installation by running:
        ```sh
        python3.13 --version
        ```

2. **Install [uv](https://docs.astral.sh/uv/)**:

    ```sh
    pip install uv
    ```

3. **Create a virtual environment in the current working directory**:

    ```sh
        uv venv
    ```

4. **Install dependencies**:
    ```sh

        uv sync --all-extras
    ```

See `just --list` for linting, formatting and build

## Installation
Use any package manager (e.g. `uv`) to install `uipath` from PyPi:
    `uv add uipath_sdk`

## Usage
### SDK
Set these env variables:
- UIPATH_BASE_URL
- UIPATH_ACCOUNT_NAME
- UIPATH_TENANT_NAME
- UIPATH_FOLDER_ID



```py
import os
from uipath_sdk import UiPathSDK


def main():
    secret = os.environ.get("UIPATH_ALPHA_SECRET")

    uipath = UiPathSDK(secret)

    job = uipath.processes.invoke_process(release_key="")
    print(job)

```

### CLI


## License
