from httpx import Client


class BaseService:
    def __init__(self, client: Client) -> None:
        self.client = client
