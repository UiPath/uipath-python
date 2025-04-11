# Getting Started

## Prerequisites

-   Python 3.10 or higher
-   `pip` or `uv` package manager
-   A UiPath Platform account with appropriate permissions

## Creating a New Project

We recommend using `uv` for package management. To create a new project:

```shell
mkdir example
cd example
uv init . --python 3.10
```

This command creates a basic project structure.

### Installing the UiPath SDK

Add the UiPath SDK to your project:

```shell
uv add uipath
```

To verify the installation, run:

```shell
uv run uipath --version
```

### Authentication

To debug your script locally and publish your project, you need to authenticate with UiPath:

```shell
uv run uipath auth
```

This command opens a new browser window. If you encounter any issues, copy the URL from the terminal and paste it into your browser. After authentication, select your tenant by typing its corresponding number in the terminal.

After completing this step, your project will contain a `.env` file with your access token, UiPath URL, and other configuration details.

### Writing Your Code

Open `main.py` in your code editor. You can start with this example code:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class EchoIn:
    message: str
    repeat: Optional[int] = 1
    prefix: Optional[str] = None


@dataclass
class EchoOut:
    message: str


def main(input: EchoIn) -> EchoOut:
    result = []
    for _ in range(input.repeat or 1):
        line = input.message
        if input.prefix:
            line = f"{input.prefix}: {line}"
        result.append(line)

    return EchoOut(message="\n".join(result))
```

### Initializing the UiPath Project

To create a UiPath project, run the following command in your terminal:

```shell
uv run uipath init
```

> **Note:**: The `uipath init` command will execute your `main.py` file to analyze its structure and collect information about inputs and outputs.

This creates a `uipath.json` file containing the project metadata.

### Debugging Your Project

To debug your project, run:

```shell
uv run uipath run main.py '{"message": "test"}'
```

If you see output similar to the following, congratulations! You're almost ready to create your first coded package for UiPath:

```shell
[2025-04-11 10:13:58,857][INFO] {'message': 'test'}
```

### Packaging and Publishing

Before packaging your project, add your details to the `pyproject.toml` file. Add the following line below the `description` field:

```toml
authors = [{ name = "Your name", email = "your.email@uipath.com" }]
```

Then, package your project:

```shell
uv run uipath pack
```

Finally, publish your package. After selecting your publishing destination (tenant or personal workspace), you'll see details about your package and the success message:

```shell
Publishing most recent package: test.0.1.0.nupkg
Package published successfully!
```

## Using the SDK

### Creating a Process Client

Now, let's create a new project to invoke the process we just created. We'll skip the installation and authentication steps since they're covered above.

Create a new project:

```shell
mkdir test2
cd test2
uv init . --python 3.10
uv add uipath
```

### Configuring the Project

First, open `.env` in your code editor and specify the folder where you want to run the code. For example, to use the "Shared" folder:

```shell
UIPATH_FOLDER_PATH=Shared
```

### Writing the Client Code

Open `main.py` in your code editor and add the following code:

```python
from uipath import UiPath


def main():
    sdk = UiPath()
    sdk.processes.invoke(
        "test-pack",
        input_arguments={
            "message": "Hello, World!",
            "repeat": 3,
            "prefix": "[Echo]"
        }
    )
```

> **Note:**: `test-pack` is the name of the process we created from the previous package.

### Verifying the Execution

Open your browser and navigate to UiPath. Go to the specified folder, and you'll see a new job for `test-pack` has been executed. The output will be:

```
[Echo]: Hello, World! Echo: Hello, World! Echo: Hello, World!
```

## Using an Agent Based on LangGraph

To use the UiPath SDK with a LangGraph-based project:

1. Add the `uipath-langchain` package to your project:

    ```shell
    uv add uipath-langchain
    ```

2. Initialize the project by running the following command in your activated virtual environment:

    ```shell
    uipath init
    ```

    > **Note:**: The `uipath init` command will execute your code to analyze its structure and collect information about inputs and outputs.

3. Package and publish your project:
    ```shell
    uipath pack
    uipath publish
    ```

This will create and publish your package to the UiPath platform, making it available for use in your automation workflows.

For more examples and implementation patterns, check out the [sample projects](https://github.com/UiPath/uipath-langchain-python/tree/main/samples) in our GitHub repository.
