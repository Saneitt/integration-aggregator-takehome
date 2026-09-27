import time
from typing import Any

import httpx

from aggregator.errors import BadRequest, NotFound, PermissionDenied, Unavailable
from aggregator.metrics import openbao_request_duration_seconds, openbao_requests_total
from aggregator.openbao.auth import TokenProvider


class OpenBaoClient:
    def __init__(self, client: httpx.AsyncClient, auth: TokenProvider) -> None:
        self.client = client
        self.auth = auth

    async def request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        started = time.perf_counter()
        op = f"{method.lower()}:{path.split('/')[-1]}"
        status = "error"
        try:
            token = await self.auth.token()
            response = await self.client.request(
                method, f"/v1/{path.lstrip('/')}", json=json, headers={"X-Vault-Token": token}
            )
            if response.status_code == 403:
                token = await self.auth.token(force=True)
                response = await self.client.request(
                    method, f"/v1/{path.lstrip('/')}", json=json, headers={"X-Vault-Token": token}
                )
            status = str(response.status_code)
            if response.status_code == 404:
                raise NotFound()
            if response.status_code == 400:
                raise BadRequest()
            if response.status_code == 403:
                raise PermissionDenied()
            if response.status_code >= 500:
                raise Unavailable()
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException as exc:
            raise Unavailable("OpenBao request timed out") from exc
        except httpx.HTTPError as exc:
            raise Unavailable("OpenBao request failed") from exc
        finally:
            openbao_requests_total.labels(op=op, status=status).inc()
            openbao_request_duration_seconds.labels(op=op).observe(time.perf_counter() - started)
