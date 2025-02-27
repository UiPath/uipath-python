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

## Installation
Use any package manager (e.g. `uv`) to install `uipath` from PyPi:
    `uv add uipath_sdk`

## Usage
### SDK
1. Generate a PAT (Personal Access Token)
For example, to create a PAT for alpha, go to (replace ORG with your organization name)
https://alpha.uipath.com/[ORG]/portal_/personalAccessToken/add

2. Set these env variables:
- `UIPATH_URL`
- `UIPATH_ACCESS_TOKEN`
- `UIPATH_FOLDER_PATH`

```py
import os
from uipath_sdk import UiPathSDK


def main():
    uipath = UiPathSDK()

    job = uipath.processes.invoke_process(name="process_name")
    print(job)

```

### CLI

## License
