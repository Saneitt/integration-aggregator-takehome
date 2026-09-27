from dataclasses import dataclass

from aggregator.errors import ProviderNotFound
from aggregator.openbao.oauthapp import OAuthAppGateway
from aggregator.validation import DEFAULT_SCOPES


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    name: str
    provider: str
    scopes: tuple[str, ...]


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderInfo] = {}

    async def warm(self, gateway: OAuthAppGateway) -> None:
        providers: dict[str, ProviderInfo] = {}
        for name in await gateway.list_servers():
            data = await gateway.get_server(name)
            provider = str(data.get("provider", "custom"))
            scopes = tuple(data.get("scopes") or DEFAULT_SCOPES.get(provider, ["openid"]))
            providers[name] = ProviderInfo(name=name, provider=provider, scopes=scopes)
        self._providers = providers

    def add(self, name: str, provider: str, scopes: list[str]) -> bool:
        created = name not in self._providers
        self._providers[name] = ProviderInfo(name, provider, tuple(scopes))
        return created

    def get(self, name: str) -> ProviderInfo:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderNotFound() from exc

    def all(self) -> list[ProviderInfo]:
        return sorted(self._providers.values(), key=lambda item: item.name)
