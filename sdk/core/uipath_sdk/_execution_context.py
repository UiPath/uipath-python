from os import environ as env
from typing import Optional

from dotenv import load_dotenv

from ._utils.constants import ENV_JOB_KEY, ENV_ROBOT_KEY

load_dotenv()


class ExecutionContext:
    def __init__(self) -> None:
        try:
            self._instance_id: Optional[str] = env[ENV_JOB_KEY]
        except KeyError:
            self._instance_id = None

        try:
            self._robot_key: Optional[str] = env[ENV_ROBOT_KEY]
        except KeyError:
            self._robot_key = None

        super().__init__()

    @property
    def instance_id(self) -> Optional[str]:
        if self._instance_id is None:
            raise ValueError(f"Instance ID is not set ({ENV_JOB_KEY})")

        return self._instance_id

    @property
    def robot_key(self) -> Optional[str]:
        if self._robot_key is None:
            raise ValueError(f"Robot key is not set ({ENV_ROBOT_KEY})")

        return self._robot_key
