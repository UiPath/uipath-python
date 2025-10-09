from pydantic import BaseModel, Field


class ExampleCall(BaseModel):
    """Example invocation for a resource."""

    id: str = Field(..., alias="id")
    input: str = Field(..., alias="input")
    output: str = Field(..., alias="output")
