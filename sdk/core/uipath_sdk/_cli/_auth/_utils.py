import base64
import json
import os
from pathlib import Path
from typing import Optional

from ._models import AccessTokenData, TokenData


def update_auth_file(token_data: TokenData):
    os.makedirs(Path.cwd() / ".uipath", exist_ok=True)
    auth_file = Path.cwd() / ".uipath" / ".auth.json"
    with open(auth_file, "w") as f:
        json.dump(token_data, f)


def get_auth_data() -> TokenData:
    auth_file = Path.cwd() / ".uipath" / ".auth.json"
    if not auth_file.exists():
        raise Exception("No authentication file found")
    return json.load(open(auth_file))


def parse_access_token(access_token: str) -> AccessTokenData:
    token_parts = access_token.split(".")
    if len(token_parts) < 2:
        raise Exception("Invalid access token")
    payload = base64.urlsafe_b64decode(
        token_parts[1] + "=" * (-len(token_parts[1]) % 4)
    )
    return json.loads(payload)


def get_parsed_token_data(token_data: Optional[TokenData] = None) -> AccessTokenData:
    if not token_data:
        token_data = get_auth_data()
    return parse_access_token(token_data["access_token"])


def update_env_file(env_contents):
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    if key not in env_contents:
                        env_contents[key] = value
    lines = [f"{key}={value}\n" for key, value in env_contents.items()]
    with open(env_path, "w") as f:
        f.writelines(lines)
