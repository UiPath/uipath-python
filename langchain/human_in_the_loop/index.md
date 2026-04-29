# Human In The Loop

Guide for **Human-In-The-Loop** scenarios within the UiPath-Langchain integration. It focuses on the **interrupt(model)** functionality, illustrating its role as a symbolic representation of an agent's wait state within the LangGraph framework.

## Models Overview

### 1. CreateTask

The `CreateTask` model is utilized to create an escalation action within the UiPath Action Center as part of an interrupt context. The action will rely on a previously created UiPath app. After addressing the escalation, the current agent will resume execution. For more information on UiPath apps, refer to the [UiPath Apps User Guide](https://docs.uipath.com/apps/automation-cloud/latest/user-guide/introduction).

#### Attributes:

- **app_name** (Optional[str]): The name of the app.
- **app_folder_path** (Optional[str]): The folder path of the app.
- **app_key** (Optional[str]): The key of the app.
- **title** (str): The title of the action to create.
- **data** (Optional\[Dict[str, Any]\]): Values that the action will be populated with.
- **assignee** (Optional[str]): The username or email of the person assigned to handle the escalation.

#### Example:

```
from uipath.platform.common import CreateTask
task_output = interrupt(CreateTask(app_name="AppName", app_folder_path="MyFolderPath", title="Escalate Issue", data={"key": "value"}, assignee="user@example.com"))
```

Info

The return value of the interrupt is the task output — only the data fields written back by the app, not the full task object. If the task did not produce any output, the return value will be the task status, e.g., `{"status": "completed"}`.

The human's decision (which Approve/Reject button was clicked, stored in `task.action`) is **not** included in the return value. To branch on the outcome, either add an explicit output field to the app schema (e.g. a boolean `IsApproved` wired to the buttons), or use [`CreateEscalation`](#3-createescalation) instead, which returns the full task object.

For a practical implementation of the `CreateTask` model, refer to the [ticket-classification sample](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/ticket-classification). This sample demonstrates how to create an action with dynamic input.

______________________________________________________________________

### 2. WaitTask

The `WaitTask` model is used to wait for a task to be handled. This model is intended for scenarios where the task has already been created.

#### Attributes:

- **task** (Task): The instance of the task to wait for.
- **app_folder_path** (Optional[str]): The folder path of the app.

#### Example:

```
from uipath.platform.common import WaitTask
task_output = interrupt(WaitTask(task=my_task_instance, app_folder_path="MyFolderPath"))
```

Info

Like `CreateTask`, the return value is the task output only. Use [`WaitEscalation`](#4-waitescalation) if you need the full task object back, including the selected action.

______________________________________________________________________

### 3. CreateEscalation

The `CreateEscalation` model creates an Action Center action the same way `CreateTask` does, but when the agent resumes it receives the **full `Task` object** instead of just `task.data`. Use this when the agent needs to branch on the human's decision (the button the reviewer clicked, stored in `task.action`) rather than only on the data fields written back by the app.

Accepts the same attributes as [`CreateTask`](#1-createtask).

#### Example:

```
from uipath.platform.common import CreateEscalation

task = interrupt(
    CreateEscalation(
        app_name="ApprovalApp",
        app_folder_path="MyFolderPath",
        title="Approve expense",
        data={"amount": 1200},
        assignee="reviewer@example.com",
    )
)

if task.action == "Approve":
    ...
else:
    ...
```

Info

The return value is the full `Task` object (including `task.action`, `task.data`, `task.status`, etc.). If the task is deleted while the agent is suspended, the task object is still returned rather than raising, so the agent can handle the deletion gracefully.

______________________________________________________________________

### 4. WaitEscalation

`WaitEscalation` is the escalation counterpart of [`WaitTask`](#2-waittask): wait on an already-created task and receive the full `Task` object on resume.

#### Attributes:

- **action** (Task): The instance of the task to wait for.
- **app_folder_path** (Optional[str]): The folder path of the app.

#### Example:

```
from uipath.platform.common import WaitEscalation
task = interrupt(WaitEscalation(action=my_task_instance, app_folder_path="MyFolderPath"))
```

______________________________________________________________________

> 💡The UiPath-LangChain SDK also supports **Robot/Agent-in-the-loop** scenarios. In this context, the execution of one agent can be suspended until another robot or agent finishes its execution.

### 5. InvokeProcess

The `InvokeProcess` model is utilized to invoke a process within the UiPath cloud platform. This process can be of various types, including API workflows, Agents or RPA automation. Upon completion of the invoked process, the current agent will automatically resume execution.

#### Attributes:

- **name** (str): The name of the process to invoke.
- **process_folder_path** (Optional[str]): The folder path of the process.
- **input_arguments** (Optional\[Dict[str, Any]\]): A dictionary containing the input arguments required for the invoked process.

#### Example:

```
from uipath.platform.common import InvokeProcess
process_output = interrupt(InvokeProcess(name="MyProcess", process_folder_path="MyFolderPath", input_arguments={"arg1": "value1"}))
```

Info

The return value of the interrupt is the job output. If the job did not produce any output, the return value will be the job state, e.g., `{"state": "successful"}`.

Warning

An agent can invoke itself if needed, but this must be done with caution. Be mindful that using the same name for invocation may lead to unintentional loops. To prevent recursion issues, implement safeguards like exit conditions.

For a practical implementation of the `InvokeProcess` model, refer to the [multi-agent-planner-researcher-coder-distributed sample](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/multi-agent-planner-researcher-coder-distributed). This sample demonstrates how to invoke a process with dynamic input arguments, showcasing the integration of the interrupt functionality within a multi-agent system or a system where an agent integrates with RPA processes and API workflows.

______________________________________________________________________

### 6. WaitJob

The `WaitJob` model is used to wait for a job completion. Unlike `InvokeProcess`, which automatically creates a job, this model is intended for scenarios where the job has already been created.

#### Attributes:

- **job** (Job): The instance of the job that the agent will wait for. This should be a valid job object that has been previously created.
- **process_folder_path** (Optional[str]): The folder path of the process.

#### Example:

```
from uipath.platform.common import WaitJob
job_output = interrupt(WaitJob(job=my_job_instance, process_folder_path="MyFolderPath"))
```

Info

The return value of the interrupt is the job output. If the job did not produce any output, the return value will be the job state, e.g., `{"state": "successful"}`.
