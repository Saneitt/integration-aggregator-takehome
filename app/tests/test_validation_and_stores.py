import pytest

from aggregator.core.oauth_states import OAuthStateStore
from aggregator.core.registry import ProviderRegistry
from aggregator.core.requests import RequestStore
from aggregator.errors import InvalidInput, InvalidState, ProviderNotFound, ReservedProviderName
from aggregator.validation import creds_name, provider_name, scopes_valid, user_id
from tests.fakes import FakeGateway


def test_identifier_validation() -> None:
    assert provider_name("gitlab-1") == "gitlab-1"
    assert user_id("Alice_1.test") == "Alice_1.test"
    assert creds_name("gitlab", "Alice") == "gitlab_Alice"
    for value in ("", "A-provider", "under_score", "a" * 33, "bad/path"):
        with pytest.raises(InvalidInput):
            provider_name(value)
    with pytest.raises(ReservedProviderName):
        provider_name("requests")
    for value in ("", "../x", "a/b", "a%2Fb", "x" * 65):
        with pytest.raises(InvalidInput):
            user_id(value)
    assert scopes_valid(["read:user", "openid"])
    assert not scopes_valid(["bad scope"])
    assert not scopes_valid(["scope"] * 21)


def test_oauth_state_is_single_use_expires_and_is_bounded() -> None:
    now = [100.0]
    store = OAuthStateStore(10, 1, clock=lambda: now[0])
    state = store.create("github", "alice")
    with pytest.raises(InvalidState):
        store.create("github", "bob")
    assert store.consume(state) == ("github", "alice")
    with pytest.raises(InvalidState):
        store.consume(state)
    expired = store.create("github", "alice")
    now[0] = 111
    with pytest.raises(InvalidState):
        store.consume(expired)
    assert store.purge_expired() == 0


def test_request_state_transitions_and_expiry() -> None:
    now = [10.0]
    store = RequestStore(5, max_size=2, clock=lambda: now[0])
    row = store.create("id", "github", "alice")
    assert row.status == "pending"
    assert store.start("id") is True
    assert store.start("id") is False
    store.succeed("id", {"access_token": "abc"})
    assert store.get("id") is row
    now[0] = 16
    assert store.get("id") is None
    assert store.purge_expired() == 0


@pytest.mark.asyncio
async def test_registry_warm_restores_provider_type_and_default_scopes() -> None:
    gateway = FakeGateway()
    await gateway.put_server("gitlab", {"provider": "gitlab", "client_id": "fake"})
    registry = ProviderRegistry()
    await registry.warm(gateway)
    assert registry.get("gitlab").scopes == ("read_user",)
    with pytest.raises(ProviderNotFound):
        registry.get("missing")
