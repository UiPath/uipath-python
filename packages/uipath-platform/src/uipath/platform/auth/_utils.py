import base64
import json
import os
from pathlib import Path
from typing import Optional

from uipath.platform.common.auth import TokenData

from ._models import AccessTokenData


def parse_access_token(access_token: str) -> AccessTokenData:
    token_parts = access_token.split(".")
    if len(token_parts) < 2:
        raise ValueError("Invalid access token: expected a JWT with at least 2 parts")
    payload = base64.urlsafe_b64decode(
        token_parts[1] + "=" * (-len(token_parts[1]) % 4)
    )
    return json.loads(payload)


def update_auth_file(token_data: TokenData) -> None:
    os.makedirs(Path.cwd() / ".uipath", exist_ok=True)
    auth_file = Path.cwd() / ".uipath" / ".auth.json"
    with open(auth_file, "w") as f:
        json.dump(token_data.model_dump(exclude_none=True), f)


def get_auth_data() -> TokenData:
    auth_file = Path.cwd() / ".uipath" / ".auth.json"
    if not auth_file.exists():
        raise FileNotFoundError(
            "No authentication file found. Run 'uipath auth' first."
        )
    return TokenData.model_validate(json.load(open(auth_file)))


def get_parsed_token_data(token_data: Optional[TokenData] = None) -> AccessTokenData:
    if not token_data:
        token_data = get_auth_data()
    return parse_access_token(token_data.access_token)
