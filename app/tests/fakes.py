from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

from aggregator.errors import NotFound


class FakeGateway:
    def __init__(self) -> None:
        self.servers: dict[str, dict[str, Any]] = {}
        self.credentials: dict[str, dict[str, Any]] = {}
        self.put_calls = 0
        self.get_token_calls = 0
        self.exchanged_codes: list[str] = []

    async def put_server(self, name: str, config: dict[str, Any]) -> None:
        self.put_calls += 1
        self.servers[name] = dict(config)

    async def list_servers(self) -> list[str]:
        return list(self.servers)

    async def get_server(self, name: str) -> dict[str, Any]:
        return {key: value for key, value in self.servers[name].items() if key != "client_secret"}

    async def auth_code_url(
        self, name: str, state: str, redirect_url: str, scopes: list[str]
    ) -> str:
        return "https://mock.example/authorize?" + urlencode(
            {
                "client_id": self.servers[name]["client_id"],
                "redirect_uri": redirect_url,
                "scope": " ".join(scopes),
                "state": state,
            }
        )

    async def exchange_code(self, name: str, credential: str, code: str, redirect_url: str) -> None:
        self.exchanged_codes.append(code)
        self.credentials[credential] = {"access_token": "fake-access-token", "token_type": "Bearer"}

    async def get_token(self, credential: str) -> dict[str, Any]:
        self.get_token_calls += 1
        if credential not in self.credentials:
            raise NotFound()
        return dict(self.credentials[credential])


class FakeKubernetesAuth:
    def __init__(self) -> None:
        self.calls = 0

    async def token(self, force: bool = False) -> str:
        self.calls += 1
        return "fake-openbao-token"

    def valid(self) -> bool:
        return True


class MappingGateway(FakeGateway):
    def __init__(self, tokens: Mapping[str, dict[str, Any]]) -> None:
        super().__init__()
        self.credentials.update(tokens)
