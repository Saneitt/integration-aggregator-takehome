import json

import httpx
import pytest

from aggregator.errors import BadRequest, NotFound, PermissionDenied, Unavailable
from aggregator.openbao.auth import KubernetesAuth, StaticTokenAuth
from aggregator.openbao.client import OpenBaoClient
from aggregator.openbao.oauthapp import HttpOAuthAppGateway
from aggregator.settings import Settings


class SequenceAuth:
    def __init__(self) -> None:
        self.values = ["old-token", "new-token"]
        self.forced = 0

    async def token(self, force: bool = False) -> str:
        if force:
            self.forced += 1
            return self.values[1]
        return self.values[0]

    def valid(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_client_sets_token_and_supports_list() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": {"keys": ["github"]}})

    async with httpx.AsyncClient(
        base_url="http://bao", transport=httpx.MockTransport(handler)
    ) as raw:
        result = await OpenBaoClient(raw, StaticTokenAuth("local-test-token")).request(
            "LIST", "/oauthapp/servers"
        )
    assert result["data"]["keys"] == ["github"]
    assert seen[0].method == "LIST"
    assert seen[0].headers["X-Vault-Token"] == "local-test-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [(400, BadRequest), (403, PermissionDenied), (404, NotFound), (503, Unavailable)],
)
async def test_client_maps_openbao_status(status: int, error: type[Exception]) -> None:
    async with httpx.AsyncClient(
        base_url="http://bao",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, json={"errors": ["hidden detail"]})
        ),
    ) as raw:
        with pytest.raises(error):
            await OpenBaoClient(raw, StaticTokenAuth("fake")).request("GET", "missing")


@pytest.mark.asyncio
async def test_client_reauthenticates_once_after_forbidden() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-Vault-Token"))
        return httpx.Response(403 if len(seen) == 1 else 200, json={})

    auth = SequenceAuth()
    async with httpx.AsyncClient(
        base_url="http://bao", transport=httpx.MockTransport(handler)
    ) as raw:
        await OpenBaoClient(raw, auth).request("GET", "oauthapp/servers")
    assert seen == ["old-token", "new-token"]
    assert auth.forced == 1


@pytest.mark.asyncio
async def test_kubernetes_auth_reads_fresh_jwt_and_caches_openbao_token(tmp_path) -> None:
    token_file = tmp_path / "sa-token"
    token_file.write_text("projected-jwt")
    received: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(
            200, json={"auth": {"client_token": "short-token", "lease_duration": 900}}
        )

    settings = Settings(
        openbao_addr="http://bao",
        callback_url="http://localhost/callback",
        openbao_k8s_token_file=str(token_file),
    )
    async with httpx.AsyncClient(
        base_url="http://bao", transport=httpx.MockTransport(handler)
    ) as raw:
        auth = KubernetesAuth(raw, settings)
        assert await auth.token() == "short-token"
        assert await auth.token() == "short-token"
        assert len(received) == 1
        assert received[0]["jwt"] == "projected-jwt"
        assert received[0]["role"] == "integration-aggregator"
        assert auth.valid()


@pytest.mark.asyncio
async def test_gateway_maps_plugin_data() -> None:
    requests: list[tuple[str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, body))
        if request.url.path.endswith("/auth-code-url"):
            return httpx.Response(200, json={"data": {"url": "https://provider/authorize"}})
        if request.url.path.endswith("/creds/github_alice") and request.method == "GET":
            return httpx.Response(
                200, json={"data": {"access_token": "secret-token", "type": "Bearer"}}
            )
        return httpx.Response(204)

    async with httpx.AsyncClient(
        base_url="http://bao", transport=httpx.MockTransport(handler)
    ) as raw:
        gateway = HttpOAuthAppGateway(OpenBaoClient(raw, StaticTokenAuth("fake")), "oauthapp/")
        url = await gateway.auth_code_url(
            "github", "opaque", "http://localhost/callback", ["read:user"]
        )
        token = await gateway.get_token("github_alice")
        await gateway.exchange_code(
            "github", "github_alice", "one-time-code", "http://localhost/callback"
        )
    assert url == "https://provider/authorize"
    assert token == {"access_token": "secret-token", "token_type": "Bearer", "expires_at": None}
    assert requests[0][1] == {
        "server": "github",
        "state": "opaque",
        "redirect_url": "http://localhost/callback",
        "scopes": ["read:user"],
    }
    assert requests[2][1]["grant_type"] == "authorization_code"
