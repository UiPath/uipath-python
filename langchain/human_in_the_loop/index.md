# Human In The Loop

Guide for **Human-In-The-Loop** scenarios within the UiPath-Langchain integration. It focuses on the **interrupt(model)** functionality, which is a symbolic representation of an agent's wait state within the LangGraph framework.

Each model below ties the agent's wait state to a specific UiPath operation. You pass the model to `interrupt(...)`, the agent suspends, and it resumes once the operation completes. The models are grouped by the kind of operation they wait on.

Info

Every model is imported from `uipath.platform.common`, for example `from uipath.platform.common import CreateTask`.

______________________________________________________________________

## Action Center tasks

These models drive human review through a UiPath app in Action Center. The agent suspends while a person handles the action, then resumes.

### CreateTask

Creates an action in Action Center backed by a previously created UiPath app. After the action is addressed, the agent resumes. For more information on UiPath apps, refer to the [UiPath Apps User Guide](https://docs.uipath.com/apps/automation-cloud/latest/user-guide/introduction).

| Attribute                       | Type             | Description                                              |
| ------------------------------- | ---------------- | -------------------------------------------------------- |
| `title`                         | `str`            | The title of the action to create.                       |
| `data`                          | \`dict[str, Any] | None\`                                                   |
| `assignee`                      | \`str            | None\`                                                   |
| `recipient`                     | \`TaskRecipient  | None\`                                                   |
| `app_name`                      | \`str            | None\`                                                   |
| `app_folder_path`               | \`str            | None\`                                                   |
| `app_folder_key`                | \`str            | None\`                                                   |
| `app_key`                       | \`str            | None\`                                                   |
| `priority`                      | \`str            | None\`                                                   |
| `labels`                        | \`list[str]      | None\`                                                   |
| `is_actionable_message_enabled` | \`bool           | None\`                                                   |
| `actionable_message_metadata`   | \`dict[str, Any] | None\`                                                   |
| `source_name`                   | `str`            | The source that created the action. Defaults to `Agent`. |

```
from uipath.platform.common import CreateTask
task_output = interrupt(CreateTask(app_name="AppName", app_folder_path="MyFolderPath", title="Escalate Issue", data={"key": "value"}, assignee="user@example.com"))
```

Info

The return value of the interrupt is the task output, meaning only the data fields written back by the app, not the full task object. If the task did not produce any output, the return value is the task status, for example `{"status": "completed"}`.

The human's decision (which Approve/Reject button was clicked, stored in `task.action`) is **not** included in the return value. To branch on the outcome, either add an explicit output field to the app schema (for example a boolean `IsApproved` wired to the buttons), or use [`CreateEscalation`](#createescalation) instead, which returns the full task object.

For a practical implementation, refer to the [ticket-classification sample](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/ticket-classification), which creates an action with dynamic input.

### WaitTask

Waits for a task that has already been created to be handled.

| Attribute         | Type            | Description                           |
| ----------------- | --------------- | ------------------------------------- |
| `action`          | `Task`          | The instance of the task to wait for. |
| `app_folder_path` | \`str           | None\`                                |
| `app_folder_key`  | \`str           | None\`                                |
| `app_name`        | \`str           | None\`                                |
| `recipient`       | \`TaskRecipient | None\`                                |

```
from uipath.platform.common import WaitTask
task_output = interrupt(WaitTask(action=my_task_instance, app_folder_path="MyFolderPath"))
```

Info

Like `CreateTask`, the return value is the task output only. Use [`WaitEscalation`](#waitescalation) if you need the full task object back, including the selected action.

### CreateEscalation

Creates an Action Center action the same way `CreateTask` does, but on resume the agent receives the **full `Task` object** instead of just `task.data`. Use this when the agent needs to branch on the human's decision (the button the reviewer clicked, stored in `task.action`) rather than only on the data fields written back by the app.

Accepts the same attributes as [`CreateTask`](#createtask), including `assignee` and `recipient`.

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

The return value is the full `Task` object (including `task.action`, `task.data`, `task.status`, and so on). If the task is deleted while the agent is suspended, the task object is still returned rather than raising, so the agent can handle the deletion gracefully.

### WaitEscalation

The escalation counterpart of [`WaitTask`](#waittask): wait on an already-created task and receive the full `Task` object on resume.

| Attribute         | Type            | Description                           |
| ----------------- | --------------- | ------------------------------------- |
| `action`          | `Task`          | The instance of the task to wait for. |
| `app_folder_path` | \`str           | None\`                                |
| `recipient`       | \`TaskRecipient | None\`                                |

```
from uipath.platform.common import WaitEscalation
task = interrupt(WaitEscalation(action=my_task_instance, app_folder_path="MyFolderPath"))
```

### Assigning the action to a user or group

`CreateTask` and `CreateEscalation`, together with their wait counterparts [`WaitTask`](#waittask) and [`WaitEscalation`](#waitescalation), support two ways to assign the action:

- **assignee** (`str | None`): The simple shortcut, a single username or email.
- **recipient** (`TaskRecipient | None`): A structured recipient that can target a **user** (by email or id) or a **group** (by name or id). When both are provided, `recipient` takes precedence over `assignee`.

`TaskRecipient` is imported from `uipath.platform.action_center.tasks` and has the following fields:

- **type** (`TaskRecipientType`): The kind of recipient (see the table below).
- **value** (`str`): The identifier, an email, group name, user id, or group id, matching `type`.
- **display_name** (`str | None`): An optional human-readable name. For `USER_ID` and `GROUP_ID` recipients it is resolved automatically from the identity service.

| TaskRecipientType | Assigns to              | `value` holds    |
| ----------------- | ----------------------- | ---------------- |
| `EMAIL`           | a single user, by email | the user's email |
| `USER_ID`         | a single user, by id    | the user id      |
| `GROUP_NAME`      | a group, by name        | the group name   |
| `GROUP_ID`        | a group, by id          | the group id     |

```
from uipath.platform.common import CreateTask
from uipath.platform.action_center.tasks import TaskRecipient, TaskRecipientType

# Assign to a single user by email
task_output = interrupt(
    CreateTask(
        app_name="AppName",
        app_folder_path="MyFolderPath",
        title="Escalate Issue",
        data={"key": "value"},
        recipient=TaskRecipient(type=TaskRecipientType.EMAIL, value="user@example.com"),
    )
)

# Or assign to a group by name
task_output = interrupt(
    CreateTask(
        app_name="AppName",
        app_folder_path="MyFolderPath",
        title="Escalate Issue",
        data={"key": "value"},
        recipient=TaskRecipient(type=TaskRecipientType.GROUP_NAME, value="Finance Approvers"),
    )
)
```

______________________________________________________________________

## Processes and jobs

These models suspend the agent until another process or job finishes. This enables **Robot/Agent-in-the-loop** scenarios, where one agent's execution is suspended until another robot or agent completes.

### InvokeProcess

Invokes a process within the UiPath cloud platform. The process can be an API workflow, an Agent, or an RPA automation. When it completes, the agent resumes automatically.

| Attribute             | Type             | Description                        |
| --------------------- | ---------------- | ---------------------------------- |
| `name`                | `str`            | The name of the process to invoke. |
| `process_folder_path` | \`str            | None\`                             |
| `input_arguments`     | \`dict[str, Any] | None\`                             |

```
from uipath.platform.common import InvokeProcess
process_output = interrupt(InvokeProcess(name="MyProcess", process_folder_path="MyFolderPath", input_arguments={"arg1": "value1"}))
```

Info

The return value of the interrupt is the job output. If the job did not produce any output, the return value is the job state, for example `{"state": "successful"}`.

**Raw variant:** `InvokeProcessRaw` accepts the same attributes but returns the raw `Job` object without validating its terminal state. Use it when you want to inspect the job state and handle non-successful jobs yourself instead of having the SDK extract the output or raise.

Warning

An agent can invoke itself if needed, but this must be done with caution. Using the same name for invocation may lead to unintentional loops. To prevent recursion issues, implement safeguards like exit conditions.

For a practical implementation, refer to the [multi-agent-planner-researcher-coder-distributed sample](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/multi-agent-planner-researcher-coder-distributed), which invokes a process with dynamic input arguments.

### WaitJob

Waits for a job to complete. Unlike `InvokeProcess`, which creates the job, this model is for jobs that have already been created.

| Attribute             | Type  | Description                          |
| --------------------- | ----- | ------------------------------------ |
| `job`                 | `Job` | The instance of the job to wait for. |
| `process_folder_path` | \`str | None\`                               |

```
from uipath.platform.common import WaitJob
job_output = interrupt(WaitJob(job=my_job_instance, process_folder_path="MyFolderPath"))
```

Info

The return value of the interrupt is the job output. If the job did not produce any output, the return value is the job state, for example `{"state": "successful"}`.

**Raw variant:** `WaitJobRaw` accepts the same attributes but returns the raw `Job` object without state validation.

______________________________________________________________________

## Context Grounding (RAG)

These models drive Context Grounding operations: Deep RAG queries, ephemeral indexes, and batch transforms. Each `Create*` model starts an asynchronous operation and suspends the agent; the matching `Wait*` model resumes once the operation completes. Where a `Raw` variant exists, it returns the underlying response without validating its final status, so the agent can inspect the status itself.

### CreateDeepRag

Starts a Deep RAG query against a Context Grounding index and suspends the agent until the query completes.

| Attribute            | Type           | Description                                                    |
| -------------------- | -------------- | -------------------------------------------------------------- |
| `name`               | `str`          | A name for the Deep RAG task.                                  |
| `prompt`             | `str`          | The query to run against the index.                            |
| `index_name`         | \`str          | None\`                                                         |
| `index_id`           | \`str          | None\`                                                         |
| `glob_pattern`       | `str`          | Glob filter for which documents to consider. Defaults to `**`. |
| `citation_mode`      | `CitationMode` | `Skip` (default) or `Inline`.                                  |
| `index_folder_key`   | \`str          | None\`                                                         |
| `index_folder_path`  | \`str          | None\`                                                         |
| `is_ephemeral_index` | \`bool         | None\`                                                         |

```
from uipath.platform.common import CreateDeepRag
result = interrupt(CreateDeepRag(name="research", index_name="MyIndex", prompt="Summarize the contract terms"))
```

Info

The return value is the validated Deep RAG response (the SDK checks the task reached a successful status).

**Raw variant:** `CreateDeepRagRaw` returns the raw Deep RAG response without status validation.

### WaitDeepRag

Waits for an already-created Deep RAG task to complete.

| Attribute           | Type                      | Description                                |
| ------------------- | ------------------------- | ------------------------------------------ |
| `deep_rag`          | `DeepRagCreationResponse` | The Deep RAG creation response to wait on. |
| `index_folder_path` | \`str                     | None\`                                     |
| `index_folder_key`  | \`str                     | None\`                                     |

```
from uipath.platform.common import WaitDeepRag
result = interrupt(WaitDeepRag(deep_rag=my_deep_rag_response, index_folder_path="MyFolderPath"))
```

Info

**Raw variant:** `WaitDeepRagRaw` returns the raw Deep RAG response without status validation.

### CreateEphemeralIndex

Creates a short-lived Context Grounding index from attachments and suspends the agent until the index is ready. Ephemeral indexes are typically created on the fly to back a Deep RAG or Batch Transform operation.

| Attribute     | Type                  | Description                                               |
| ------------- | --------------------- | --------------------------------------------------------- |
| `usage`       | `EphemeralIndexUsage` | What the index will be used for: `DeepRAG` or `BatchRAG`. |
| `attachments` | `List[str]`           | The attachment ids to index.                              |

```
from uipath.platform.common import CreateEphemeralIndex
from uipath.platform.context_grounding import EphemeralIndexUsage
index = interrupt(CreateEphemeralIndex(usage=EphemeralIndexUsage.DEEP_RAG, attachments=["attachment-id-1"]))
```

Info

The return value is the validated index.

**Raw variant:** `CreateEphemeralIndexRaw` returns the raw ephemeral index response without status validation.

### WaitEphemeralIndex

Waits for an already-created ephemeral index to become ready.

| Attribute | Type                    | Description                    |
| --------- | ----------------------- | ------------------------------ |
| `index`   | `ContextGroundingIndex` | The index instance to wait on. |

```
from uipath.platform.common import WaitEphemeralIndex
index = interrupt(WaitEphemeralIndex(index=my_index))
```

Info

**Raw variant:** `WaitEphemeralIndexRaw` returns the raw index response without status validation.

### CreateBatchTransform

Starts a Batch Transform (batch RAG) job that applies a prompt across a set of documents and writes structured output columns to a destination, then suspends the agent until the job completes.

| Attribute                           | Type                               | Description                                                               |
| ----------------------------------- | ---------------------------------- | ------------------------------------------------------------------------- |
| `name`                              | `str`                              | A name for the batch transform task.                                      |
| `prompt`                            | `str`                              | The prompt applied to each document.                                      |
| `output_columns`                    | `List[BatchTransformOutputColumn]` | The structured columns to extract (each with a `name` and `description`). |
| `destination_path`                  | `str`                              | Where the transformed output is written.                                  |
| `index_name`                        | \`str                              | None\`                                                                    |
| `index_id`                          | \`str                              | None\`                                                                    |
| `storage_bucket_folder_path_prefix` | \`str                              | None\`                                                                    |
| `enable_web_search_grounding`       | `bool`                             | Whether to ground answers with web search. Defaults to `False`.           |
| `index_folder_key`                  | \`str                              | None\`                                                                    |
| `index_folder_path`                 | \`str                              | None\`                                                                    |
| `is_ephemeral_index`                | \`bool                             | None\`                                                                    |

```
from uipath.platform.common import CreateBatchTransform
from uipath.platform.context_grounding import BatchTransformOutputColumn

result = interrupt(
    CreateBatchTransform(
        name="extract-fields",
        index_name="MyIndex",
        prompt="Extract the vendor and total amount",
        output_columns=[
            BatchTransformOutputColumn(name="vendor", description="The vendor name"),
            BatchTransformOutputColumn(name="total", description="The total amount"),
        ],
        destination_path="output/results",
    )
)
```

### WaitBatchTransform

Waits for an already-created Batch Transform job to complete.

| Attribute           | Type                             | Description                                       |
| ------------------- | -------------------------------- | ------------------------------------------------- |
| `batch_transform`   | `BatchTransformCreationResponse` | The batch transform creation response to wait on. |
| `index_folder_path` | \`str                            | None\`                                            |
| `index_folder_key`  | \`str                            | None\`                                            |

```
from uipath.platform.common import WaitBatchTransform
result = interrupt(WaitBatchTransform(batch_transform=my_batch_transform_response, index_folder_path="MyFolderPath"))
```

______________________________________________________________________

## Document Understanding (IXP)

These models extract structured data from documents and, optionally, route the result to a human for validation.

### DocumentExtraction

Starts an IXP extraction over a document and suspends the agent until extraction completes. Provide the document via **exactly one** of `file` or `file_path`.

| Attribute      | Type          | Description                             |
| -------------- | ------------- | --------------------------------------- |
| `project_name` | `str`         | The IXP project to run extraction with. |
| `tag`          | `str`         | The project tag or version to use.      |
| `file`         | \`FileContent | None\`                                  |
| `file_path`    | \`str         | None\`                                  |

```
from uipath.platform.common import DocumentExtraction
extraction = interrupt(DocumentExtraction(project_name="Invoices", tag="production", file_path="invoice.pdf"))
```

Warning

Provide exactly one of `file` or `file_path`. Supplying both or neither raises a validation error.

### WaitDocumentExtraction

Waits for an already-started document extraction to complete.

| Attribute    | Type                      | Description                               |
| ------------ | ------------------------- | ----------------------------------------- |
| `extraction` | `StartExtractionResponse` | The extraction-start response to wait on. |

```
from uipath.platform.common import WaitDocumentExtraction
result = interrupt(WaitDocumentExtraction(extraction=my_extraction_response))
```

### DocumentExtractionValidation

Routes an extraction result to a human for validation in Action Center, creating a document validation action and suspending the agent until it is handled.

| Attribute                       | Type                    | Description                         |
| ------------------------------- | ----------------------- | ----------------------------------- |
| `extraction_response`           | `ExtractionResponseIXP` | The extraction result to validate.  |
| `action_title`                  | `str`                   | The title of the validation action. |
| `action_catalog`                | \`str                   | None\`                              |
| `action_priority`               | \`ActionPriority        | None\`                              |
| `action_folder`                 | \`str                   | None\`                              |
| `storage_bucket_name`           | \`str                   | None\`                              |
| `storage_bucket_directory_path` | \`str                   | None\`                              |

```
from uipath.platform.common import DocumentExtractionValidation
from uipath.platform.documents import ActionPriority

result = interrupt(
    DocumentExtractionValidation(
        extraction_response=my_extraction_result,
        action_title="Validate invoice extraction",
        action_priority=ActionPriority.HIGH,
    )
)
```

### WaitDocumentExtractionValidation

Waits for an already-created document validation action to be handled.

| Attribute               | Type                                | Description                               |
| ----------------------- | ----------------------------------- | ----------------------------------------- |
| `extraction_validation` | `StartExtractionValidationResponse` | The validation-start response to wait on. |
| `task_url`              | \`str                               | None\`                                    |

```
from uipath.platform.common import WaitDocumentExtractionValidation
result = interrupt(WaitDocumentExtractionValidation(extraction_validation=my_validation_response))
```

______________________________________________________________________

## Integration Services events

### WaitIntegrationEvent

Suspends the agent until a remote event is delivered through Integration Services (for example a Slack message or a Teams reply). The SDK resolves `connection_name` (scoped to `connection_folder_path` when provided) to the underlying connection id and subscribes to the described event via the Connections service.

| Attribute                | Type             | Description                                                    |
| ------------------------ | ---------------- | -------------------------------------------------------------- |
| `connector`              | `str`            | The connector to subscribe through (for example Slack, Teams). |
| `connection_name`        | `str`            | The name of the connection to use.                             |
| `connection_folder_path` | \`str            | None\`                                                         |
| `operation`              | `str`            | The event operation to subscribe to.                           |
| `object_name`            | `str`            | The remote object the event relates to.                        |
| `filter_expression`      | \`str            | None\`                                                         |
| `parameters`             | \`dict[str, str] | None\`                                                         |

```
from uipath.platform.common import WaitIntegrationEvent
event = interrupt(
    WaitIntegrationEvent(
        connector="slack",
        connection_name="MySlackConnection",
        operation="new_message",
        object_name="message",
    )
)
```

For a practical implementation, refer to the [email-triage-agent sample](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/email-triage-agent).

______________________________________________________________________

## Resuming with a plain value (API trigger)

All the models above are typed interrupts that tie the agent's wait state to a specific UiPath operation. When you call `interrupt(...)` with a value that is **not** one of those models, most commonly a plain string but any JSON-serializable value works, the SDK creates an **API resume trigger**. The agent suspends and waits to be resumed by an explicit external API call rather than by polling a UiPath operation.

When the trigger is created the SDK generates a fresh `inbox_id` and stores the interrupted value as the trigger's request payload. The agent stays suspended until a caller posts a payload to the job's resume inbox, and that payload becomes the return value of the `interrupt(...)` call.

This is the right approach for human-in-the-loop or system-to-system handoffs driven from outside the agent (a custom UI, a webhook, another service) instead of a UiPath task, job, or RAG operation.

While the job is suspended, open its job details page in Orchestrator and expand **Resume conditions**. The **API** condition exposes the resume URL, which you can copy with the button next to it. Post your payload to that URL to resume the job. For the full request shape and authentication, see the [Orchestrator API triggers documentation](https://docs.uipath.com/orchestrator/automation-cloud/latest/user-guide/api-triggers).

```
from langgraph.types import interrupt

# Suspend with an arbitrary prompt or payload; the resume value is whatever the caller posts back.
human_response = interrupt("Please review the draft and reply with your decision.")
```

Info

The interrupt value can be any JSON-serializable object (string, dict, and so on), and the resume value is the payload delivered to the trigger's inbox. There is no status validation, so the agent resumes with exactly what the external caller provides.
