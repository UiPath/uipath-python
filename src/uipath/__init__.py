"""UiPath SDK for Python.

This package provides a Python interface to interact with UiPath's automation platform.


The main entry point is the UiPath class, which provides access to all SDK functionality.

Example:
```python
    # First set these environment variables:
    # export UIPATH_URL="https://cloud.uipath.com/organization-name/default-tenant"
    # export UIPATH_ACCESS_TOKEN="your_**_token"
    # export UIPATH_FOLDER_PATH="your/folder/path"

    from uipath import UiPath
    sdk = UiPath()
    # Invoke a process by name
    sdk.processes.invoke("MyProcess")
```
"""

from ._uipath import UiPath

__all__ = ["UiPath"]
