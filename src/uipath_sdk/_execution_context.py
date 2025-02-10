from os import environ as env

from dotenv import load_dotenv

load_dotenv()


class ExecutionContext:
    def __init__(self) -> None:
        try:
            self._instance_id: str | None = env["UIPATH_JOB_KEY"]
        except KeyError:
            self._instance_id = None

        try:
            self._robot_key: str | None = env["UIPATH_ROBOT_KEY"]
        except KeyError:
            self._robot_key = None

        super().__init__()

    @property
    def instance_id(self) -> None | str:
        if self._instance_id is None:
            raise ValueError("Instance ID is not set (UIPATH_JOB_KEY)")

        return self._instance_id

    @property
    def robot_key(self) -> None | str:
        if self._robot_key is None:
            raise ValueError("Robot key is not set (UIPATH_ROBOT_KEY)")

        return self._robot_key
