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

The return value of the interrupt is the task output. If the task did not produce any output, the return value will be the task status, e.g., `{"status": "completed"}`.

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

The return value of the interrupt is the task output. If the task did not produce any output, the return value will be the task status, e.g., `{"status": "completed"}`.

______________________________________________________________________

> 💡The UiPath-LangChain SDK also supports **Robot/Agent-in-the-loop** scenarios. In this context, the execution of one agent can be suspended until another robot or agent finishes its execution.

### 3. InvokeProcess

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

### 4. WaitJob

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
