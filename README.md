# UiPath SDK

## CLI User's guide

`pip install uipath_sdk`
_(NOTE: create virtual env if needed)_

```
uipath init [PROJECT_NAME] [DIRECTORY] [DESCRIPTION]
```

defaults:

-   project name => my-agent
-   directory => ./
-   description => "my-agent description"

example:

```
uipath init
OR
uipath init custom-name ./my-projects/custom-dir "my custom description"
```

after init `cd` into the created folder, install the dependencies from requirements.txt then set your credentials in the `.env` file
_(NOTE: if you just want to publish the default package or edit basic things in the main.py file you may skip installing the dependencies)_

```
uipath pack [ROOT] [VERSION]
```

defaults:

-   root => ./
-   version => 1.0.0
    example:

```
uipath pack
OR
uipath pack ./my-projects/custom-dir 2.0.4
```

NOTE: if you run the pack command outside of the folder with the `config.json` it will throw an error

after packing it's time to publish

```
uipath publish [PATH_TO_NUPKG]

uipath publish my-custom-package.2.3.1.nupkg
```

defaults:

-   if no path provided, it will use the first `.nupkg` file it finds in your current directory

NOTE: this command also needs an `.env` file in your current directory

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
1. Set these env variables:
- `UIPATH_BASE_URL`
- `UIPATH_ACCOUNT_NAME`
- `UIPATH_TENANT_NAME`
- `UIPATH_FOLDER_ID`

2. Generate a PAT (Personal Access Token)
For example, to create a PAT for alpha, go to (replace ORG with your organization name)
https://alpha.uipath.com/[ORG]/portal_/personalAccessToken/add

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
