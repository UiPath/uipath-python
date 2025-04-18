# This file is generated by the build system. Do not edit it directly.
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from .._config import Config as Config
from .._execution_context import ExecutionContext as ExecutionContext
from .._utils import Endpoint as Endpoint
from .._utils import RequestSpec as RequestSpec
from .._utils.constants import ENTRYPOINT as ENTRYPOINT
from ..models import Connection as Connection
from ..models import ConnectionToken as ConnectionToken
from ._base_service import BaseService as BaseService

if TYPE_CHECKING:
    from uipath_connectors.atlassian_jira import AtlassianJira  # type: ignore
    from uipath_connectors.box_box import BoxBox  # type: ignore
    from uipath_connectors.google_drive import GoogleDrive  # type: ignore
    from uipath_connectors.google_gmail import GoogleGmail  # type: ignore
    from uipath_connectors.google_sheets import GoogleSheets  # type: ignore
    from uipath_connectors.microsoft_github import MicrosoftGithub  # type: ignore
    from uipath_connectors.microsoft_onedrive import MicrosoftOneDrive  # type: ignore
    from uipath_connectors.oracle_netsuite import OracleNetsuite  # type: ignore
    from uipath_connectors.salesforce_sfdc import SalesforceSfdc  # type: ignore
    from uipath_connectors.salesforce_slack import SalesforceSlack  # type: ignore
    from uipath_connectors.uipath_airdk import UipathAirdk  # type: ignore

T_co = TypeVar("T_co", covariant=True)

class Connector(Protocol[T_co]):
    def __call__(self, *, client: Any, instance_id: str | int) -> T_co: ...

class ConnectionsService(BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None: ...
    def __call__(self, connector: Connector[T_co], key: str) -> T_co: ...
    def __getattr__(self, name: str) -> Any: ...
    def retrieve(self, key: str) -> Connection: ...
    async def retrieve_async(self, key: str) -> Connection: ...
    def retrieve_token(self, key: str) -> ConnectionToken: ...
    async def retrieve_token_async(self, key: str) -> ConnectionToken: ...

    atlassian_jira: "AtlassianJira"
    box_box: "BoxBox"
    google_drive: "GoogleDrive"
    google_gmail: "GoogleGmail"
    google_sheets: "GoogleSheets"
    microsoft_github: "MicrosoftGithub"
    microsoft_onedrive: "MicrosoftOneDrive"
    oracle_netsuite: "OracleNetsuite"
    salesforce_sfdc: "SalesforceSfdc"
    salesforce_slack: "SalesforceSlack"
    uipath_airdk: "UipathAirdk"
