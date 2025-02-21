import os
from langchain_core.tools import tool
from uipath_sdk import UiPathSDK
from uipath_connectors.uipath_airdk import UiPathAirdk, WebReaderRequest

@tool
def SupplierWebsiteReader(request: WebReaderRequest) -> str:
    """
    Use this tool to read data from the supplier website.
    Specifically, use it to get details about mismatched items from the site: '{{Supplier Website}}'. Replace '<SKU>' with the actual product SKU.

    Args:
        request: The request parameters
            url: A publicly accessible URL
            provider: The search engine to use. Must be one of: ['Jina']

    Returns:
        The text from the URL
    """

    airdk = UiPathSDK().connections(UiPathAirdk, os.environ.get('UIPATH_AIRDK_CONNECTION_KEY'))
    response = airdk.web_reader(body=request)
    return response.text
