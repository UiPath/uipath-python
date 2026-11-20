# Human In The Loop

Guide for **Human-In-The-Loop** scenarios within the UiPath-LlamaIndex integration. It focuses on the **ctx.write_event_to_stream** LlamaIndex functionality.

## Models Overview

### 1. CreateTaskEvent

The `CreateTaskEvent` model is utilized to create an escalation task within the UiPath Action Center as part of an interrupt context. The task will rely on a previously created UiPath App. After addressing the escalation, the current agent will resume execution. For more information on UiPath Apps, refer to the [UiPath Apps User Guide](https://docs.uipath.com/apps/automation-cloud/latest/user-guide/introduction).

#### Attributes:

- **app_name** (Optional[str]): The name of the app.
- **app_folder_path** (Optional[str]): The folder path of the app.
- **app_key** (Optional[str]): The key of the app.
- **title** (str): The title of the task to create.
- **data** (Optional\[Dict[str, Any]\]): Values that the task will be populated with.
- **assignee** (Optional[str]): The username or email of the person assigned to handle the escalation.

#### Example:

```
from uipath_llamaindex.models import CreateTaskEvent
ctx.write_event_to_stream(CreateTaskEvent(app_name="AppName", app_folder_path="MyFolderPath", title="Escalate Issue", data={"key": "value"}, assignee="user@example.com"))
task_data = await ctx.wait_for_event(HumanResponseEvent)
```

For a practical implementation of the `CreateTaskEvent` model, refer to the [action-center-hitl-agent](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-llamaindex/samples/action-center-hitl-agent). This sample demonstrates how to create a task with dynamic input.

______________________________________________________________________

### 2. WaitTaskEvent

The `WaitTaskEvent` model is used to wait for a task to be approved. This model is intended for scenarios where the task has already been created.

#### Attributes:

- **action** (Task): The instance of the task to wait for.
- **app_folder_path** (Optional[str]): The folder path of the app.

#### Example:

```
from uipath_llamaindex.models import WaitTaskEvent
ctx.write_event_to_stream(WaitTaskEvent(action=my_task_instance, app_folder_path="MyFolderPath"))
task_data = await ctx.wait_for_event(HumanResponseEvent)
```

______________________________________________________________________

> 💡 UiPath LlamaIndex sdk also supports **Robot/Agent-in-the-loop** scenarios. In this context, the execution of one agent can be suspended until another robot or agent finishes its execution.

### 3. InvokeProcessEvent

The `InvokeProcessEvent` model is utilized to invoke a process within the UiPath cloud platform. This process can be of various types, including API workflows, Agents or RPA automation. Upon completion of the invoked process, the current agent will automatically resume execution.

#### Attributes:

- **name** (str): The name of the process to invoke.
- **process_folder_path** (Optional[str]): The folder path of the process.
- **input_arguments** (Optional\[Dict[str, Any]\]): A dictionary containing the input arguments required for the invoked process.

#### Example:

```
from uipath_llamaindex.models import InvokeProcessEvent
ctx.write_event_to_stream(InvokeProcessEvent(name="MyProcess", process_folder_path="MyFolderPath", input_arguments={"arg1": "value1"}))
job_data = await ctx.wait_for_event(HumanResponseEvent)
```

Warning

An agent can invoke itself if needed, but this must be done with caution. Be mindful that using the same name for invocation may lead to unintentional loops. To prevent recursion issues, implement safeguards like exit conditions.

For a practical implementation of the `InvokeProcessEvent` model, refer to the [multi-agent sample](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-llamaindex/samples/multi-agent). This sample demonstrates how to invoke a process with dynamic input arguments, showcasing the integration of the interrupt functionality within a multi-agent system or a system where an agent integrates with RPA processes and API workflows.

______________________________________________________________________

### 4. WaitJob

The `WaitJobEvent` model is used to wait for a job completion. Unlike `InvokeProcessEvent`, which automatically creates a job, this model is intended for scenarios where the job has already been created.

#### Attributes:

- **job** (Job): The instance of the job that the agent will wait for. This should be a valid job object that has been previously created.
- **process_folder_path** (Optional[str]): The folder path of the process.

#### Example:

```
from uipath_llamaindex.models import WaitJobEvent
ctx.write_event_to_stream(WaitJobEvent(job=my_job_instance, process_folder_path="MyFolderPath"))
job_data = await ctx.wait_for_event(HumanResponseEvent)
```
