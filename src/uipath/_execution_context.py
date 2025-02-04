from os import environ as env
from typing import Optional

from dotenv import load_dotenv

from ._utils.constants import ENV_JOB_ID, ENV_JOB_KEY, ENV_ROBOT_KEY

load_dotenv()


class ExecutionContext:
    """Manages the execution context for UiPath automation processes.

    The ExecutionContext class handles information about the current execution environment,
    including the job instance ID and robot key. This information is essential for
    tracking and managing automation jobs in UiPath Automation Cloud.
    """

    def __init__(self) -> None:
        try:
            self._instance_key: Optional[str] = env[ENV_JOB_KEY]
        except KeyError:
            self._instance_key = None

        try:
            self._instance_id: Optional[str] = env[ENV_JOB_ID]
        except KeyError:
            self._instance_id = None

        try:
            self._robot_key: Optional[str] = env[ENV_ROBOT_KEY]
        except KeyError:
            self._robot_key = None

        super().__init__()

    @property
    def instance_id(self) -> Optional[str]:
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
    def instance_key(self) -> Optional[str]:
        """Get the current job instance key.

        The instance key uniquely identifies the current automation job execution
        in UiPath Automation Cloud.
        """
        if self._instance_key is None:
            raise ValueError(f"Instance key is not set ({ENV_JOB_KEY})")

        return self._instance_key

    @property
    def robot_key(self) -> Optional[str]:
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
