import os

from dotenv import load_dotenv

from ._utils import SingletonMeta

load_dotenv()


class UiPathClientConfig(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._uipath_url = self._get_env_var("UIPATH_URL")
        self._account_name = self._get_env_var("UIPATH_ACCOUNT_NAME")
        self._tenant_name = self._get_env_var("UIPATH_TENANT_NAME")
        self._folder_id = self._get_env_var("UIPATH_FOLDER_ID")
        self._secret = self._get_env_var(
            "UNATTENDED_USER_ACCESS_TOKEN", "UIPATH_ACCESS_TOKEN"
        )

    @property
    def base_url(self) -> str:
        return f"{self._uipath_url}/{self._account_name}/{self._tenant_name}"

    @property
    def folder_id(self) -> str:
        return self._folder_id

    @folder_id.setter
    def folder_id(self, value: str) -> None:
        self._folder_id = value

    @property
    def secret(self) -> str:
        return self._secret

    @secret.setter
    def secret(self, value: str) -> None:
        self._secret = value

    @staticmethod
    def _get_env_var(*keys: str, default: str = "") -> str:
        for key in keys:
            value = os.getenv(key)
            if value:
                return value
        return default
