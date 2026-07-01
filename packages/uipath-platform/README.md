# UiPath Platform

Python SDK for interacting programmatically with UiPath services.

## Constants

`uipath.platform.constants` is the single source of truth for the string
constants shared across the SDK — environment-variable names, HTTP headers,
file/folder names, and data-source identifiers. It lives directly under
`uipath.platform` (the package's `__init__` resolves its heavy exports lazily),
so it can be imported without pulling in the service layer.

```python
from uipath.platform.constants import ENV_BASE_URL, HEADER_FOLDER_KEY
```

> `uipath.platform.common.constants` re-exports these for backward
> compatibility and is deprecated.
