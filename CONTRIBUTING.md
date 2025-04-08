# Contributing to UiPath SDK

## Local Development Setup

### Prerequisites

1. **Install Python 3.13**:
    - Download and install Python 3.13 from the official [Python website](https://www.python.org/downloads/)
    - Verify the installation by running:
        ```sh
        python3.13 --version
        ```

    Alternative: [mise](https://mise.jdx.dev/lang/python.html)

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

See `just --list` for linting, formatting and build commands.


### Use SDK Locally
1. Create a folder on your own device `mkdir project; cd project`
2. Initialize the python project `uv` `uv init . --python 3.9`
3. Obtain the project path `PATH_TO_SDK=/Users/YOU_USER/uipath-python`
4. Install the sdk in editable mode `uv  add --editable ${PATH_TO_SDK}`

:information_source: Instead of cloning the project into `.venv/lib/python3.9/site-packages/uipath`, this mode creates a file named `_uipath.pth` inside `.venv/lib/python3.9/site-packages`. This file contains the value of `PATH_TO_SDK`, which is added to `sys.path`—the list of directories where python searches for packages. (Run `python -c 'import sys; print(sys.path)'` to see the entries.)

## API Style Guide

### General Rule:
- use key instead of ID

### Standard Methods & Naming Conventions

#### Retrieve a Single Resource
- **Method Name:** `retrieve` instead of get
- **Usage:** To obtain a specific resource instance using its unique identifier (using *key* instead of ID).
- **Extended:**
  - `retrieve_by_[field_name]` (for fields other than key)

#### List Multiple Resources
- **Method Name:** `list`
- **Usage:** To fetch a collection of resources, optionally filtered by query parameters.
- **Example:**
  ```python
  resources = Resource.list(filters={})
  ```

#### Create a Resource
- **Method Name:** `create`
- **Usage:** To add a new resource to the system.

#### Update a Resource
- **Method Name:** `update`
- **Usage:** To modify an existing resource.
