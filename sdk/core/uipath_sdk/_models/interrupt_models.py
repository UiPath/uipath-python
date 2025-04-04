from typing import Any, Dict, Optional

from pydantic import BaseModel

from .actions import Action
from .job import Job


class InvokeProcess(BaseModel):
    """Interrupt model to invoke a process identified by its name.

    This model is utilized to invoke a process within UiPath cloud platform. Upon completion of the invoked
    process, the current agent will automatically resume execution.

    Attributes:
        name (str): The name of the process to invoke.
        input_arguments (Optional[Dict[str, Any]]): A dictionary containing the input arguments required for the invoked process.

    Example:
        >>> process_output = interrupt(InvokeProcess(name="MyProcess", input_arguments={"arg1": "value1"}))
    """

    name: str
    input_arguments: Optional[Dict[str, Any]]


class WaitJob(BaseModel):
    """Interrupt model to wait for the completion of a job.

    This model is used to wait for a job completion.
    Unlike `InvokeProcess`, which automatically creates a job, this model is intended for scenarios where
    the job has already been created and should be tracked.

    Attributes:
        job (Job): The instance of the job that the model will wait for. This should be a valid job object
        that has been previously created.

    Example:
        >>> job_output = interrupt(WaitJob(job=my_job_instance))
    """

    job: Job


class CreateAction(BaseModel):
    """Interrupt model to create an escalation action in the UiPath Action Center.

    This model is utilized to create an action within the UiPath Action Center as part of an interrupt context.
    The action schema must be defined as part of a UiPath app, which must be created prior to using this model.
    The app can be identified either by its name or by its key. When the Human-in-the-loop process is addressed,
    the agent will resume execution.

    For more information on UiPath apps, refer to the [UiPath Apps User Guide](https://docs.uipath.com/apps/automation-cloud/latest/user-guide/introduction).

    Attributes:
        name (Optional[str]): The name of the action.
        key (Optional[str]): The key of the action.
        title (str): The title of the action to create.
        data (Optional[Dict[str, Any]]): Values that the action will be populated with.
        app_version (Optional[int]): The version of the application (default is 1).
        assignee (Optional[str]): The username or email of the person assigned to handle the escalation.

    Example:
        >>> action_output = interrupt(CreateAction(name="ActionName", key="ActionKey", title="Escalate Issue", data={"key": "value"}, app_version=1, assignee="user@example.com"))
    """

    name: Optional[str] = None
    key: Optional[str] = None
    title: str
    data: Optional[Dict[str, Any]] = None
    app_version: Optional[int] = 1
    assignee: Optional[str] = ""


class WaitAction(BaseModel):
    """Interrupt model to wait for an action to be handled.

    This model is analogous to `CreateAction`, but it is intended for scenarios where the action has already been created.

    Attributes:
        action (Action): The instance of the action to wait for.

    Example:
        >>> action_output = interrupt(WaitAction(action=my_action_instance))
    """

    action: Action
