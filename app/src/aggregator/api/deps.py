from typing import cast

from fastapi import Request

from aggregator.core.oauth_states import OAuthStateStore
from aggregator.core.registry import ProviderRegistry
from aggregator.core.requests import RequestStore
from aggregator.core.worker import TokenWorker
from aggregator.openbao.oauthapp import OAuthAppGateway


def registry(request: Request) -> ProviderRegistry:
    return cast(ProviderRegistry, request.app.state.registry)


def states(request: Request) -> OAuthStateStore:
    return cast(OAuthStateStore, request.app.state.states)


def requests_store(request: Request) -> RequestStore:
    return cast(RequestStore, request.app.state.requests)


def worker(request: Request) -> TokenWorker:
    return cast(TokenWorker, request.app.state.worker)


def gateway(request: Request) -> OAuthAppGateway:
    return cast(OAuthAppGateway, request.app.state.gateway)
