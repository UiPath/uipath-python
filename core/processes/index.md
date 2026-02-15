## ProcessesService

Service for managing and executing UiPath automation processes.

Processes (also known as automations or workflows) are the core units of automation in UiPath, representing sequences of activities that perform specific business tasks.

### invoke

```
invoke(
    name,
    input_arguments=None,
    *,
    folder_key=None,
    folder_path=None,
    attachments=None,
    **kwargs,
)
```

Start execution of a process by its name.

Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

Parameters:

| Name              | Type             | Description                         | Default                                                                                           |
| ----------------- | ---------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------- |
| `name`            | `str`            | The name of the process to execute. | *required*                                                                                        |
| `input_arguments` | \`dict[str, Any] | None\`                              | The input arguments to pass to the process.                                                       |
| `attachments`     | \`list           | None\`                              | List of Attachment objects to pass to the process.                                                |
| `folder_key`      | \`str            | None\`                              | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path`     | \`str            | None\`                              | The path of the folder to execute the process in. Override the default one set in the SDK config. |

Returns:

| Name  | Type  | Description                |
| ----- | ----- | -------------------------- |
| `Job` | `Job` | The job execution details. |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

client.processes.invoke(name="MyProcess")
```

```
# if you want to execute the process in a specific folder
# another one than the one set in the SDK config
from uipath.platform import UiPath

client = UiPath()

client.processes.invoke(name="MyProcess", folder_path="my-folder-key")
```

### invoke_async

```
invoke_async(
    name,
    input_arguments=None,
    *,
    folder_key=None,
    folder_path=None,
    attachments=None,
    **kwargs,
)
```

Asynchronously start execution of a process by its name.

Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

Parameters:

| Name              | Type             | Description                         | Default                                                                                           |
| ----------------- | ---------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------- |
| `name`            | `str`            | The name of the process to execute. | *required*                                                                                        |
| `input_arguments` | \`dict[str, Any] | None\`                              | The input arguments to pass to the process.                                                       |
| `attachments`     | \`list           | None\`                              | List of Attachment objects to pass to the process.                                                |
| `folder_key`      | \`str            | None\`                              | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path`     | \`str            | None\`                              | The path of the folder to execute the process in. Override the default one set in the SDK config. |

Returns:

| Name  | Type  | Description                |
| ----- | ----- | -------------------------- |
| `Job` | `Job` | The job execution details. |

Examples:

```
import asyncio

from uipath.platform import UiPath

sdk = UiPath()

async def main():
    job = await sdk.processes.invoke_async("testAppAction")
    print(job)

asyncio.run(main())
```
