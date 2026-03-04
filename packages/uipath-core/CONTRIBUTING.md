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
    PATH_TO_SDK=/Users/YOUR_USERNAME/uipath-core-python
    ```

4. Install the SDK in editable mode:
    ```sh
    uv add --editable ${PATH_TO_SDK}
    ```

> **Note:** Instead of cloning the project into `.venv/lib/python3.11/site-packages/uipath-core`, this mode creates a file named `_uipath-core.pth` inside `.venv/lib/python3.11/site-packages`. This file contains the value of `PATH_TO_SDK`, which is added to `sys.path`—the list of directories where Python searches for packages. To view the entries, run `python -c 'import sys; print(sys.path)'`.
