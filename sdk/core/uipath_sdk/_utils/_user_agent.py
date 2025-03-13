import importlib

from .constants import HEADER_USER_AGENT


def user_agent_value(specific_component: str) -> str:
    product = "UiPath.Python.Sdk"
    product_component = f"UiPath.Python.Sdk.Activities.{specific_component}"

    version = importlib.metadata.version("uipath-sdk")

    return f"{product}/{product_component}/{version}"


def header_user_agent(specific_component: str) -> dict[str, str]:
    return {HEADER_USER_AGENT: user_agent_value(specific_component)}
