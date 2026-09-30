import asyncio
import uuid

from fastapi import APIRouter, Depends, Response

from aggregator.api.deps import activity, registry, requests_store, worker
from aggregator.api.schemas import RequestResponse, TokenResult
from aggregator.core.activity import ActivityLog
from aggregator.core.registry import ProviderRegistry
from aggregator.core.requests import RequestStore
from aggregator.core.worker import TokenWorker
from aggregator.errors import QueueFull, RequestNotFound
from aggregator.validation import provider_name, user_id

router = APIRouter()


@router.get("/requests/{request_id}", response_model=RequestResponse)
async def get_request(
    request_id: str, store: RequestStore = Depends(requests_store)
) -> Response | RequestResponse:
    row = store.get(request_id)
    if row is None:
        raise RequestNotFound()
    response = RequestResponse(
        request_id=row.request_id,
        status=row.status,
        provider=row.provider,
        user=row.user,
        error=row.error,
    )
    if row.status == "succeeded" and row.result:
        response.token = TokenResult.model_validate(row.result)
        return Response(
            content=response.model_dump_json(exclude_none=True),
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
    if row.status in {"pending", "running"}:
        return Response(
            content=response.model_dump_json(exclude_none=True),
            media_type="application/json",
            headers={"Retry-After": "1"},
        )
    return response


@router.get("/requests/{request_id}/status", response_model=RequestResponse)
async def get_request_status(
    request_id: str, store: RequestStore = Depends(requests_store)
) -> Response:
    """Token-free status for observers such as the local dashboard."""
    row = store.get(request_id)
    if row is None:
        raise RequestNotFound()
    result = RequestResponse(
        request_id=row.request_id,
        status=row.status,
        provider=row.provider,
        user=row.user,
        error=row.error,
    )
    headers = {"Cache-Control": "no-store"}
    if row.status in {"pending", "running"}:
        headers["Retry-After"] = "1"
    return Response(
        content=result.model_dump_json(exclude_none=True),
        media_type="application/json",
        headers=headers,
    )


@router.get("/{provider}/{user}", response_model=RequestResponse, status_code=202)
async def request_token(
    provider: str,
    user: str,
    providers: ProviderRegistry = Depends(registry),
    store: RequestStore = Depends(requests_store),
    token_worker: TokenWorker = Depends(worker),
    log: ActivityLog = Depends(activity),
) -> Response:
    provider, user = provider_name(provider), user_id(user)
    providers.get(provider)
    if token_worker.stopping:
        raise QueueFull()
    request_id = str(uuid.uuid4())
    try:
        store.create(request_id, provider, user)
    except OverflowError as exc:
        raise QueueFull() from exc
    try:
        token_worker.submit(request_id)
    except asyncio.QueueFull as exc:
        store.delete(request_id)
        raise QueueFull() from exc
    log.add("request_queued", provider, user, request_id)
    return Response(
        content=RequestResponse(request_id=request_id, status="pending").model_dump_json(
            exclude_none=True
        ),
        status_code=202,
        media_type="application/json",
        headers={"Location": f"/requests/{request_id}", "Retry-After": "1"},
    )
