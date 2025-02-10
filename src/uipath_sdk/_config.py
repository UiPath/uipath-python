from pydantic import BaseModel, HttpUrl, field_validator

PREFIX = "UIPATH_"
PRODUCT_URL = "uipath.com"


class Config(BaseModel):
    base_url: str
    secret: str

    @field_validator("base_url", mode="before")
    @classmethod
    def validate_url(cls, value: str) -> str:
        # assume that the URL is in the correct format.
        # https://{domain}.uipath.com/{account_name}/{tenant_name}
        urlValue = HttpUrl(url=value)
        assert urlValue.host and urlValue.host.endswith(PRODUCT_URL), "Invalid URL"
        assert (
            urlValue.path and len([x for x in urlValue.path.split("/") if x != ""]) == 2
        ), "Invalid URL"
        return value
