import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aggregator.api import activity, connect, health, providers, tokens
from aggregator.core.activity import ActivityLog
from aggregator.core.oauth_states import OAuthStateStore
from aggregator.core.registry import ProviderRegistry
from aggregator.core.requests import RequestStore
from aggregator.core.worker import Janitor, TokenWorker
from aggregator.errors import OpenBaoError, install_error_handlers
from aggregator.logging import AccessLogMiddleware, configure_logging
from aggregator.metrics import metrics_app
from aggregator.openbao.auth import TokenProvider, create_auth
from aggregator.openbao.client import OpenBaoClient
from aggregator.openbao.oauthapp import HttpOAuthAppGateway, OAuthAppGateway
from aggregator.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    gateway_override: OAuthAppGateway | None = None,
    auth_override: TokenProvider | None = None,
) -> FastAPI:
    runtime = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(runtime.log_level)
        http_client = httpx.AsyncClient(
            base_url=runtime.openbao_addr.rstrip("/"), timeout=runtime.openbao_timeout_seconds
        )
        auth = auth_override or create_auth(http_client, runtime)
        oauth_client = OpenBaoClient(http_client, auth)
        gateway = gateway_override or HttpOAuthAppGateway(oauth_client, runtime.openbao_mount)
        registry = ProviderRegistry()
        states = OAuthStateStore(runtime.state_ttl_seconds, runtime.max_pending_states)
        requests = RequestStore(runtime.request_ttl_seconds)
        activity_log = ActivityLog()
        token_worker = TokenWorker(
            gateway, requests, runtime.worker_concurrency, runtime.queue_max_size, activity_log
        )
        janitor = Janitor(states, requests)
        app.state.settings = runtime
        app.state.http_client = http_client
        app.state.auth = auth
        app.state.gateway = gateway
        app.state.registry = registry
        app.state.states = states
        app.state.requests = requests
        app.state.activity = activity_log
        app.state.worker = token_worker
        app.state.shutting_down = False
        app.state.ready_cache = None
        token_worker.start()
        janitor.start()
        try:
            await auth.token()
            await registry.warm(gateway)
        except OpenBaoError:
            logger.warning(
                "OpenBao initialization failed; readiness remains false until connectivity returns."
            )
        try:
            yield
        finally:
            app.state.shutting_down = True
            await janitor.stop()
            await token_worker.stop(drain_timeout=20)
            await http_client.aclose()

    app = FastAPI(title="Integration Aggregator", version="0.1.0", lifespan=lifespan)
    install_error_handlers(app)
    app.add_middleware(AccessLogMiddleware)
    web_root = Path(__file__).parent / "web"
    app.mount("/assets", StaticFiles(directory=web_root), name="assets")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(web_root / "index.html", media_type="text/html")

    app.include_router(health.router)
    app.include_router(activity.router)
    app.include_router(providers.router)
    app.include_router(connect.router)
    app.include_router(tokens.router)
    app.mount("/metrics", metrics_app)
    return app
