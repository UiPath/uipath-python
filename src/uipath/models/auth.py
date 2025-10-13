from typing import Optional

from pydantic import BaseModel


class TokenData(BaseModel):
    """Pydantic model for token data structure."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
