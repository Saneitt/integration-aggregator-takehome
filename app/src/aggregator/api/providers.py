from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from aggregator.api.deps import activity, gateway, registry
from aggregator.api.schemas import ProviderCreate, ProviderResponse
from aggregator.core.activity import ActivityLog
from aggregator.core.registry import ProviderRegistry
from aggregator.errors import OpenBaoError, UpstreamUnavailable
from aggregator.openbao.oauthapp import OAuthAppGateway
from aggregator.validation import provider_name

router = APIRouter()


@router.post("/providers", response_model=ProviderResponse)
async def register_provider(
    body: ProviderCreate,
    providers: ProviderRegistry = Depends(registry),
    oauth: OAuthAppGateway = Depends(gateway),
    log: ActivityLog = Depends(activity),
) -> JSONResponse:
    name = provider_name(body.name)
    scopes = body.effective_scopes()
    config = {
        "provider": body.provider,
        "client_id": body.client_id,
        "client_secret": body.client_secret.get_secret_value(),
        "provider_options": body.provider_options,
    }
    try:
        await oauth.put_server(name, config)
    except OpenBaoError as exc:
        raise UpstreamUnavailable() from exc
    created = providers.add(name, body.provider, scopes)
    result = ProviderResponse(name=name, provider=body.provider, scopes=scopes)
    log.add("provider_registered" if created else "provider_updated", name)
    return JSONResponse(status_code=201 if created else 200, content=result.model_dump())


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(providers: ProviderRegistry = Depends(registry)) -> list[ProviderResponse]:
    return [
        ProviderResponse(name=row.name, provider=row.provider, scopes=list(row.scopes))
        for row in providers.all()
    ]
