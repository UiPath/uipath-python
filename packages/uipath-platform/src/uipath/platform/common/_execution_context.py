from contextvars import ContextVar, Token
from os import environ as env

from uipath.platform.constants import ENV_JOB_ID, ENV_JOB_KEY, ENV_ROBOT_KEY

_execution_source: ContextVar[str | None] = ContextVar("execution_source", default=None)


class ExecutionSourceContext:
    """Scope the execution source for the duration of a run.

    Carries the source (e.g. ``runtime``/``playground``/``eval``) via a context
    variable and releases it on exit so it stays correctly scoped in concurrent
    runs. The CLI enters this with ``UiPathRuntimeContext.execution_source`` so
    platform clients can read it via
    :attr:`UiPathExecutionContext.execution_source`.
    """

    def __init__(self, execution_source: str | None) -> None:
        self._execution_source = execution_source
        self._token: Token[str | None] | None = None

    def __enter__(self) -> "ExecutionSourceContext":
        self._token = _execution_source.set(self._execution_source)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._token is not None:
            _execution_source.reset(self._token)
            self._token = None


class UiPathExecutionContext:
    """Manages the execution context for UiPath automation processes.

    The UiPathExecutionContext class handles information about the current execution environment,
    including the job instance ID and robot key. This information is essential for
    tracking and managing automation jobs in UiPath Automation Cloud.
    """

    def __init__(self) -> None:
        try:
            self._instance_key: str | None = env[ENV_JOB_KEY]
        except KeyError:
            self._instance_key = None

        try:
            self._instance_id: str | None = env[ENV_JOB_ID]
        except KeyError:
            self._instance_id = None

        try:
            self._robot_key: str | None = env[ENV_ROBOT_KEY]
        except KeyError:
            self._robot_key = None

        super().__init__()

    @property
    def instance_id(self) -> str | None:
        """Get the current job instance ID.

        The instance ID uniquely identifies the current automation job execution
        in UiPath Automation Cloud.

        Returns:
            Optional[str]: The job instance ID.

        Raises:
            ValueError: If the instance ID is not set in the environment.
        """
        if self._instance_id is None:
            raise ValueError(f"Instance ID is not set ({ENV_JOB_ID})")

        return self._instance_id

    @property
    def instance_key(self) -> str | None:
        """Get the current job instance key.

        The instance key uniquely identifies the current automation job execution
        in UiPath Automation Cloud.
        """
        if self._instance_key is None:
            raise ValueError(f"Instance key is not set ({ENV_JOB_KEY})")

        return self._instance_key

    @property
    def robot_key(self) -> str | None:
        """Get the current robot key.

        The robot key identifies the UiPath Robot that is executing the current
        automation job.

        Returns:
            Optional[str]: The robot key.

        Raises:
            ValueError: If the robot key is not set in the environment.
        """
        if self._robot_key is None:
            raise ValueError(f"Robot key is not set ({ENV_ROBOT_KEY})")

        return self._robot_key

    @property
    def execution_source(self) -> str | None:
        """Get the execution source for the current run.

        Identifies the run context (e.g. ``runtime``/``playground``/``eval``),
        derived from the CLI command and carried via
        :class:`ExecutionSourceContext`. Returns ``None`` when not set.
        """
        return _execution_source.get()
