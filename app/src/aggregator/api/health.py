import time

import httpx
from fastapi import APIRouter, Request, Response

from aggregator.errors import OpenBaoError

router = APIRouter()


@router.get("/healthz", response_model=None)
async def healthz(request: Request) -> Response:
    if request.app.state.shutting_down or not request.app.state.worker.healthy():
        return Response(status_code=503)
    return Response(content='{"status":"ok"}', media_type="application/json")


@router.get("/readyz", response_model=None)
async def readyz(request: Request) -> Response:
    now = time.monotonic()
    cached = request.app.state.ready_cache
    if cached and now - cached[0] < 2:
        return Response(
            status_code=200 if cached[1] else 503,
            media_type="application/json",
            content='{"status":"ready"}' if cached[1] else '{"status":"not_ready"}',
        )
    healthy = False
    if not request.app.state.shutting_down and request.app.state.worker.healthy():
        try:
            # Refresh the short-lived OpenBao login token before declaring readiness.
            await request.app.state.auth.token()
            response = await request.app.state.http_client.get("/v1/sys/health")
            healthy = response.status_code in {200, 429, 472, 473}
        except (OpenBaoError, httpx.HTTPError):
            healthy = False
    request.app.state.ready_cache = (now, healthy)
    return Response(
        status_code=200 if healthy else 503,
        media_type="application/json",
        content='{"status":"ready"}' if healthy else '{"status":"not_ready"}',
    )
