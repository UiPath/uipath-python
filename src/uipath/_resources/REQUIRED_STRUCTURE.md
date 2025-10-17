## Required Agent Structure

**IMPORTANT**: All UiPath coded agents MUST follow this standard structure unless explicitly specified otherwise by the user.

### Required Components

Every agent implementation MUST include these two Pydantic models:

```python
from pydantic import BaseModel

class Input(BaseModel):
    """Define input fields that the agent accepts"""
    # Add your input fields here
    pass

class Output(BaseModel):
    """Define output fields that the agent returns"""
    # Add your output fields here
    pass
```

### SDK Initialization

```python
from uipath import UiPath

# Initialize with environment variables
uipath = UiPath()

# With explicit credentials
uipath = UiPath(base_url="https://cloud.uipath.com/...", secret="your_token")

# Or with client_id and client_secret
uipath = UiPath(
    client_id=UIPATH_CLIENT_ID,
    client_secret=UIPATH_CLIENT_SECRET,
    scope=UIPATH_SCOPE,
    base_url=UIPATH_URL
)
```

### Standard Agent Template

Every agent should follow this basic structure:

```python
from uipath import UiPath
from pydantic import BaseModel

# 1. Define Input, and Output models
class Input(BaseModel):
    field: str

class Output(BaseModel):
    result: str

# 2. Initialize with environment variables
uipath = UiPath()

# 3. Define the main function (the main function can be named "main", "run" or "execute")
def main(input_data: Input) -> Output:
     pass
```
