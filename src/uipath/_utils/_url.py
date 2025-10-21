from typing import Literal
from urllib.parse import urlparse


class UiPathUrl:
    """A class that represents a UiPath URL.

    This class is used to parse and manipulate UiPath URLs.

    >>> url = UiPathUrl("https://test.uipath.com/org/tenant")
    >>> url.base_url
    'https://test.uipath.com'
    >>> url.org_name
    'org'
    >>> url.tenant_name
    'tenant'

    Args:
        url (str): The URL to parse.
    """

    def __init__(self, url: str):
        self._url = url

    def __str__(self):
        return self._url

    def __repr__(self):
        return f"UiPathUrl({self._url})"

    def __eq__(self, other: object):
        if not isinstance(other, UiPathUrl):
            return NotImplemented

        return self._url == str(other)

    def __ne__(self, other: object):
        if not isinstance(other, UiPathUrl):
            return NotImplemented

        return self._url != str(other)

    def __hash__(self):
        return hash(self._url)

    @property
    def base_url(self):
        parsed = urlparse(self._url)

        return f"{parsed.scheme}://{parsed.hostname}{f':{parsed.port}' if parsed.port else ''}"

    @property
    def org_name(self):
        return self._org_tenant_names[0]

    @property
    def tenant_name(self):
        return self._org_tenant_names[1]

    def scope_url(self, url: str, scoped: Literal["org", "tenant"] = "tenant") -> str:
        if not self._is_relative_url(url):
            return url

        parts = [self.org_name]
        if scoped == "tenant":
            parts.append(self.tenant_name)
        parts.append(url.strip("/"))

        return "/".join(parts)

    @property
    def _org_tenant_names(self):
        parsed = urlparse(self._url)

        try:
            org_name, tenant_name = parsed.path.strip("/").split("/")
        except ValueError:
            return "", ""

        return org_name, tenant_name

    def _is_relative_url(self, url: str) -> bool:
        # Empty URLs are considered relative
        if not url:
            return True

        parsed = urlparse(url)

        # Protocol-relative URLs (starting with //) are not relative
        if url.startswith("//"):
            return False

        # URLs with schemes are not relative (http:, https:, mailto:, etc.)
        if parsed.scheme:
            return False

        # URLs with network locations are not relative
        if parsed.netloc:
            return False

        # If we've passed all the checks, it's a relative URL
        return True
