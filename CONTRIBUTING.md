# Contributing to UiPath SDK

## Local Development Setup

### Prerequisites

1. **Install Python ≥ 3.10**:
    - Download and install Python 3.10 from the official [Python website](https://www.python.org/downloads/)
    - Verify the installation by running:
        ```sh
        python3.10 --version
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
    uv init . --python 3.10
    ```

3. Set the SDK path:
    ```sh
    PATH_TO_SDK=/Users/YOUR_USERNAME/uipath-python
    ```

4. Install the SDK in editable mode:
    ```sh
    uv add --editable ${PATH_TO_SDK}
    ```

> **Note:** Instead of cloning the project into `.venv/lib/python3.10/site-packages/uipath`, this mode creates a file named `_uipath.pth` inside `.venv/lib/python3.10/site-packages`. This file contains the value of `PATH_TO_SDK`, which is added to `sys.path`—the list of directories where Python searches for packages. To view the entries, run `python -c 'import sys; print(sys.path)'`.

## API Style Guide

### General Rule
- Use `key` instead of `id` for resource identifiers

### Standard Methods and Naming Conventions

#### Retrieve a Single Resource
- **Method Name:** `retrieve`
- **Purpose:** Obtain a specific resource instance using its unique identifier (using `key` instead of `id`)
- **Variations:**
  - `retrieve_by_[field_name]` (for fields other than `key`)

#### List Multiple Resources
- **Method Name:** `list`
- **Purpose:** Fetch a collection of resources, optionally filtered by query parameters
- **Example:**
    ```python
    resources = Resource.list(filters={})
    ```

#### Create a Resource
- **Method Name:** `create`
- **Purpose:** Add a new resource to the system

#### Update a Resource
- **Method Name:** `update`
- **Purpose:** Modify an existing resource
