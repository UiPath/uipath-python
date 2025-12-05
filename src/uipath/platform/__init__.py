"""UiPath SDK for Python.

This package provides a Python interface to interact with UiPath's automation platform.


The main entry point is the UiPath class, which provides access to all SDK functionality.

Example:
```python
    # First set these environment variables:
    # export UIPATH_URL="https://cloud.uipath.com/organization-name/default-tenant"
    # export UIPATH_ACCESS_TOKEN="your_**_token"
    # export UIPATH_FOLDER_PATH="your/folder/path"

    from uipath.platform import UiPath
    sdk = UiPath()
    # Invoke a process by name
    sdk.processes.invoke("MyProcess")
```

## Error Handling

Exception classes are available in the `errors` module and should be imported explicitly:

```python
    from uipath.platform.errors import (
        BaseUrlMissingError,
        SecretMissingError,
        EnrichedException,
        IngestionInProgressException,
        FolderNotFoundException,
        UnsupportedDataSourceException,
    )
```
"""

from ._uipath import UiPath
from .common import UiPathApiConfig, UiPathExecutionContext

__all__ = ["UiPathApiConfig", "UiPath", "UiPathExecutionContext"]
