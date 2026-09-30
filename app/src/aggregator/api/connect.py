from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from aggregator.api.deps import activity, gateway, registry, states
from aggregator.core.activity import ActivityLog
from aggregator.core.oauth_states import OAuthStateStore
from aggregator.core.registry import ProviderRegistry
from aggregator.errors import ExchangeFailed, InvalidState, OpenBaoError, UpstreamUnavailable
from aggregator.openbao.oauthapp import OAuthAppGateway
from aggregator.validation import creds_name, provider_name, user_id

router = APIRouter()


class ConnectResponse(BaseModel):
    provider: str
    user: str
    auth_url: str
    state: str
    expires_in: int


@router.post("/providers/{provider}/users/{user}/connect", response_model=ConnectResponse)
async def connect(
    provider: str,
    user: str,
    request: Request,
    providers: ProviderRegistry = Depends(registry),
    oauth_states: OAuthStateStore = Depends(states),
    oauth: OAuthAppGateway = Depends(gateway),
    log: ActivityLog = Depends(activity),
) -> ConnectResponse:
    provider, user = provider_name(provider), user_id(user)
    info = providers.get(provider)
    state = oauth_states.create(provider, user)
    try:
        url = await oauth.auth_code_url(
            provider, state, request.app.state.settings.callback_url, list(info.scopes)
        )
    except OpenBaoError as exc:
        oauth_states.discard(state)
        raise UpstreamUnavailable() from exc
    if not url:
        oauth_states.discard(state)
        raise UpstreamUnavailable()
    log.add("consent_started", provider, user)
    return ConnectResponse(
        provider=provider,
        user=user,
        auth_url=url,
        state=state,
        expires_in=request.app.state.settings.state_ttl_seconds,
    )


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    oauth_states: OAuthStateStore = Depends(states),
    oauth: OAuthAppGateway = Depends(gateway),
    log: ActivityLog = Depends(activity),
) -> Response:
    if not state:
        raise InvalidState()
    provider, user = oauth_states.consume(state)
    if error:
        from aggregator.errors import ConsentDenied

        log.add("consent_denied", provider, user)
        raise ConsentDenied()
    if not code:
        raise InvalidState()
    try:
        await oauth.exchange_code(
            provider, creds_name(provider, user), code, request.app.state.settings.callback_url
        )
    except OpenBaoError as exc:
        raise ExchangeFailed() from exc
    log.add("connected", provider, user)
    if "text/html" in request.headers.get("accept", ""):
        from urllib.parse import urlencode

        return RedirectResponse(
            url="/?" + urlencode({"connected": provider, "user": user}),
            status_code=303,
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        content={"status": "connected", "provider": provider, "user": user},
        headers={"Cache-Control": "no-store"},
    )
