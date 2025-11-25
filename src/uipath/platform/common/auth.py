"""Module defining the TokenData model for authentication tokens."""

from pydantic import BaseModel

class TokenData(BaseModel):
    """Pydantic model for token data structure."""

    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str | None = None
    scope: str | None = None
    id_token: str | None = None
