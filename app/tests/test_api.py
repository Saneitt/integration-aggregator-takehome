from fastapi.testclient import TestClient

from aggregator.main import create_app
from aggregator.openbao.auth import StaticTokenAuth
from aggregator.settings import Settings
from tests.fakes import FakeGateway


def build(
    gateway: FakeGateway | None = None, **overrides: object
) -> tuple[TestClient, FakeGateway]:
    oauth = gateway or FakeGateway()
    settings = Settings(
        openbao_addr="http://127.0.0.1:9",
        callback_url="http://localhost:8080/callback",
        openbao_auth_method="token",
        openbao_token="local-test-token",
        worker_concurrency=2,
        queue_max_size=2,
        **overrides,
    )
    return TestClient(create_app(settings, oauth, StaticTokenAuth("local-test-token"))), oauth


def provider_payload(name: str = "github") -> dict[str, object]:
    return {
        "name": name,
        "provider": "github",
        "client_id": "fake-client",
        "client_secret": "super-secret-test-value",
        "scopes": ["read:user"],
    }


def test_provider_registration_is_redacted_and_idempotent() -> None:
    client, oauth = build()
    with client:
        first = client.post("/providers", json=provider_payload())
        assert first.status_code == 201
        assert first.json() == {"name": "github", "provider": "github", "scopes": ["read:user"]}
        assert "super-secret-test-value" not in first.text
        second = client.post("/providers", json=provider_payload())
        assert second.status_code == 200
        listed = client.get("/providers")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert "super-secret-test-value" not in listed.text
        assert oauth.put_calls == 2


def test_provider_validation_and_custom_options() -> None:
    client, _ = build()
    with client:
        assert (
            client.post("/providers", json=provider_payload("metrics")).json()["code"]
            == "reserved_provider_name"
        )
        assert client.post("/providers", json={**provider_payload("bad_name")}).status_code == 422
        missing = provider_payload("custom")
        missing["provider"] = "custom"
        assert client.post("/providers", json=missing).status_code == 422
        missing.pop("client_secret")
        assert client.post("/providers", json=missing).status_code == 422
        oidc = provider_payload("oidc")
        oidc.update(provider="oidc", provider_options={"issuer_url": "https://issuer.example"})
        assert client.post("/providers", json=oidc).status_code == 201
        assert client.get("/bad%2Fname/alice").status_code == 422


def test_connect_callback_and_single_use_state() -> None:
    client, oauth = build()
    with client:
        client.post("/providers", json=provider_payload())
        connected = client.post("/providers/github/users/alice/connect")
        assert connected.status_code == 200
        payload = connected.json()
        assert payload["provider"] == "github"
        assert payload["user"] == "alice"
        assert payload["state"] in payload["auth_url"]
        callback = client.get(
            "/callback", params={"code": "known-secret-code", "state": payload["state"]}
        )
        assert callback.status_code == 200
        assert callback.headers["cache-control"] == "no-store"
        assert callback.json() == {"status": "connected", "provider": "github", "user": "alice"}
        assert "known-secret-code" not in callback.text
        assert (
            client.get(
                "/callback", params={"code": "replay", "state": payload["state"]}
            ).status_code
            == 400
        )
        assert oauth.exchanged_codes == ["known-secret-code"]


def test_denied_and_unknown_oauth_state() -> None:
    client, _ = build()
    with client:
        client.post("/providers", json=provider_payload())
        payload = client.post("/providers/github/users/alice/connect").json()
        denied = client.get(
            "/callback", params={"error": "access_denied", "state": payload["state"]}
        )
        assert denied.status_code == 400
        assert denied.json()["code"] == "consent_denied"
        missing = client.get("/callback", params={"state": "not-known", "code": "x"})
        assert missing.status_code == 400
        assert missing.json()["code"] == "invalid_state"


def test_async_token_flow_and_not_connected() -> None:
    client, _ = build()
    with client:
        client.post("/providers", json=provider_payload())
        accepted = client.get("/github/alice")
        assert accepted.status_code == 202
        assert set(accepted.json()) == {"request_id", "status"}
        assert accepted.headers["retry-after"] == "1"
        assert accepted.headers["location"].startswith("/requests/")
        result = client.get(accepted.headers["location"])
        assert result.status_code == 200
        assert result.json()["status"] == "failed"
        assert result.json()["error"]["code"] == "not_connected"
        assert client.get("/not-known/alice").json()["code"] == "provider_not_found"
        assert client.get("/requests/not-known").json()["code"] == "request_not_found"


def test_successful_token_result_is_no_store() -> None:
    client, oauth = build()
    with client:
        client.post("/providers", json=provider_payload())
        oauth.credentials["github_alice"] = {
            "access_token": "only-token-endpoint",
            "token_type": "Bearer",
        }
        accepted = client.get("/github/alice")
        result = client.get(accepted.headers["location"])
        assert result.json()["status"] == "succeeded"
        assert result.json()["token"]["access_token"] == "only-token-endpoint"
        assert result.headers["cache-control"] == "no-store"


def test_backpressure_returns_503_without_orphan() -> None:
    client, _ = build()
    with client:
        client.post("/providers", json=provider_payload())
        client.app.state.worker.stopping = True
        response = client.get("/github/alice")
        assert response.status_code == 503
        assert response.json()["code"] == "queue_full"
        assert len(client.app.state.requests) == 0


def test_health_and_metrics_endpoints() -> None:
    client, _ = build()
    with client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.get("/metrics").status_code == 200
        client.app.state.shutting_down = True
        assert client.get("/healthz").status_code == 503


def test_readiness_refreshes_expired_openbao_login() -> None:
    class ExpiredAuth(StaticTokenAuth):
        def __init__(self) -> None:
            super().__init__("local-test-token")
            self.refresh_calls = 0

        async def token(self, force: bool = False) -> str:
            self.refresh_calls += 1
            return await super().token(force)

        def valid(self) -> bool:
            return False

    auth = ExpiredAuth()
    settings = Settings(
        openbao_addr="http://127.0.0.1:9",
        callback_url="http://localhost:8080/callback",
        openbao_auth_method="token",
        openbao_token="local-test-token",
    )
    client = TestClient(create_app(settings, FakeGateway(), auth))
    with client:
        auth.refresh_calls = 0
        assert client.get("/readyz").status_code == 503
        assert auth.refresh_calls == 1
