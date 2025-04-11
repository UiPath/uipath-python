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

> **Note:**: `test-pack` is the name of the process we created from the [previous package.](./getting_started_cli.md)

### Verifying the Execution

Open your browser and navigate to UiPath. Go to the specified folder, and you'll see a new job for `test-pack` has been executed. The output will be:

```
[Echo]: Hello, World! Echo: Hello, World! Echo: Hello, World!
```
