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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._uipath import UiPath
    from .common import UiPathApiConfig, UiPathExecutionContext

__all__ = ["UiPathApiConfig", "UiPath", "UiPathExecutionContext"]


def __getattr__(name: str):
    """Resolve top-level exports on demand.

    Keeps this package's ``__init__`` cheap so lightweight submodules such as
    ``uipath.platform.constants`` can be imported without pulling in the
    ``UiPath`` facade and the full service layer. The heavy import happens only
    when ``UiPath`` (or a config type) is actually accessed.
    """
    if name == "UiPath":
        from ._uipath import UiPath

        return UiPath
    if name in ("UiPathApiConfig", "UiPathExecutionContext"):
        from . import common

        return getattr(common, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
