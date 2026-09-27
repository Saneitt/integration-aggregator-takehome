from collections.abc import Mapping
from typing import Any, Protocol

from aggregator.openbao.client import OpenBaoClient


class OAuthAppGateway(Protocol):
    async def put_server(self, name: str, config: dict[str, Any]) -> None: ...
    async def list_servers(self) -> list[str]: ...
    async def get_server(self, name: str) -> dict[str, Any]: ...
    async def auth_code_url(
        self, name: str, state: str, redirect_url: str, scopes: list[str]
    ) -> str: ...
    async def exchange_code(
        self, name: str, credential: str, code: str, redirect_url: str
    ) -> None: ...
    async def get_token(self, credential: str) -> dict[str, Any]: ...


class HttpOAuthAppGateway:
    def __init__(self, client: OpenBaoClient, mount: str) -> None:
        self.client = client
        self.mount = mount.strip("/")

    async def put_server(self, name: str, config: dict[str, Any]) -> None:
        await self.client.request("POST", f"{self.mount}/servers/{name}", json=config)

    async def list_servers(self) -> list[str]:
        response = await self.client.request("LIST", f"{self.mount}/servers")
        return list(response.get("data", {}).get("keys", []))

    async def get_server(self, name: str) -> dict[str, Any]:
        response = await self.client.request("GET", f"{self.mount}/servers/{name}")
        return dict(response.get("data", {}))

    async def auth_code_url(
        self, name: str, state: str, redirect_url: str, scopes: list[str]
    ) -> str:
        response = await self.client.request(
            "PUT",
            f"{self.mount}/auth-code-url",
            json={"server": name, "state": state, "redirect_url": redirect_url, "scopes": scopes},
        )
        data = response.get("data", {})
        return str(data.get("url", data.get("auth_url", "")))

    async def exchange_code(self, name: str, credential: str, code: str, redirect_url: str) -> None:
        await self.client.request(
            "POST",
            f"{self.mount}/creds/{credential}",
            json={
                "server": name,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_url": redirect_url,
            },
        )

    async def get_token(self, credential: str) -> dict[str, Any]:
        response = await self.client.request("GET", f"{self.mount}/creds/{credential}")
        data: Mapping[str, Any] = response.get("data", {})
        return {
            "access_token": data.get("access_token"),
            "token_type": data.get("type", data.get("token_type", "Bearer")),
            "expires_at": data.get("expire_time", data.get("expires_at")),
        }
