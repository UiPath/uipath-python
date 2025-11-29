# Human In The Loop

Guide for **Human-In-The-Loop** scenarios within the UiPath-LlamaIndex integration. It focuses on the **ctx.write_event_to_stream** LlamaIndex functionality.

## Models Overview

### 1. CreateAction

The `CreateAction` model is utilized to create an escalation action within the UiPath Action Center as part of an interrupt context. The action will rely on a previously created UiPath app. After addressing the escalation, the current agent will resume execution. For more information on UiPath apps, refer to the [UiPath Apps User Guide](https://docs.uipath.com/apps/automation-cloud/latest/user-guide/introduction).

#### Attributes:

- **app_name** (Optional[str]): The name of the app.
- **app_folder_path** (Optional[str]): The folder path of the app.
- **app_key** (Optional[str]): The key of the app.
- **title** (str): The title of the action to create.
- **data** (Optional\[Dict[str, Any]\]): Values that the action will be populated with.
- **app_version** (Optional[int]): The version of the app (defaults to 1).
- **assignee** (Optional[str]): The username or email of the person assigned to handle the escalation.

#### Example:

```
from uipath_llamaindex.models import CreateActionEvent
action_output = ctx.write_event_to_stream(CreateActionEvent(app_name="AppName", app_folder_path="MyFolderPath", title="Escalate Issue", data={"key": "value"}, app_version=1, assignee="user@example.com"))
```

For a practical implementation of the `CreateAction` model, refer to the [action-center-hitl-agent](https://github.com/UiPath/uipath-llamaindex-python/tree/main/samples/action-center-hitl-agent). This sample demonstrates how to create an action with dynamic input.

______________________________________________________________________

### 2. WaitAction

The `WaitAction` model is used to wait for an action to be handled. This model is intended for scenarios where the action has already been created.

#### Attributes:

- **action** (Action): The instance of the action to wait for.
- **app_folder_path** (Optional[str]): The folder path of the app.

#### Example:

```
from uipath_llamaindex.models import WaitActionEvent
action_output = ctx.write_event_to_stream(WaitActionEvent(action=my_action_instance, app_folder_path="MyFolderPath"))
```

______________________________________________________________________

> 💡 UiPath LlamaIndex sdk also supports **Robot/Agent-in-the-loop** scenarios. In this context, the execution of one agent can be suspended until another robot or agent finishes its execution.

### 3. InvokeProcess

The `InvokeProcess` model is utilized to invoke a process within the UiPath cloud platform. This process can be of various types, including API workflows, Agents or RPA automation. Upon completion of the invoked process, the current agent will automatically resume execution.

#### Attributes:

- **name** (str): The name of the process to invoke.
- **process_folder_path** (Optional[str]): The folder path of the process.
- **input_arguments** (Optional\[Dict[str, Any]\]): A dictionary containing the input arguments required for the invoked process.

#### Example:

```
from uipath_llamaindex.models import InvokeProcessEvent
process_output = ctx.write_event_to_stream(InvokeProcessEvent(name="MyProcess", process_folder_path="MyFolderPath", input_arguments={"arg1": "value1"}))
```

Warning

An agent can invoke itself if needed, but this must be done with caution. Be mindful that using the same name for invocation may lead to unintentional loops. To prevent recursion issues, implement safeguards like exit conditions.

For a practical implementation of the `InvokeProcess` model, refer to the [multi-agent sample](https://github.com/UiPath/uipath-llamaindex-python/tree/main/samples/multi-agent). This sample demonstrates how to invoke a process with dynamic input arguments, showcasing the integration of the interrupt functionality within a multi-agent system or a system where an agent integrates with RPA processes and API workflows.

______________________________________________________________________

### 4. WaitJob

The `WaitJob` model is used to wait for a job completion. Unlike `InvokeProcess`, which automatically creates a job, this model is intended for scenarios where the job has already been created.

#### Attributes:

- **job** (Job): The instance of the job that the agent will wait for. This should be a valid job object that has been previously created.
- **process_folder_path** (Optional[str]): The folder path of the process.

#### Example:

```
from uipath_llamaindex.models import WaitJobEvent
job_output = ctx.write_event_to_stream(WaitJobEvent(job=my_job_instance, process_folder_path="MyFolderPath"))
```
