from pydantic import BaseModel


class Config(BaseModel):
    base_url: str
    secret: str
