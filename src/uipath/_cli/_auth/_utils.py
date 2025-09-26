import json
import os
from pathlib import Path
from typing import Optional

from ..._utils._auth import parse_access_token
from ...models.auth import TokenData
from ._models import AccessTokenData


def update_auth_file(token_data: TokenData):
    os.makedirs(Path.cwd() / ".uipath", exist_ok=True)
    auth_file = Path.cwd() / ".uipath" / ".auth.json"
    with open(auth_file, "w") as f:
        json.dump(token_data.model_dump(exclude_none=True), f)


def get_auth_data() -> TokenData:
    auth_file = Path.cwd() / ".uipath" / ".auth.json"
    if not auth_file.exists():
        raise Exception("No authentication file found")
    return TokenData.model_validate(json.load(open(auth_file)))


def get_parsed_token_data(token_data: Optional[TokenData] = None) -> AccessTokenData:
    if not token_data:
        token_data = get_auth_data()
    return parse_access_token(token_data.access_token)
