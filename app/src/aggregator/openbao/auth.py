import asyncio
import time
from pathlib import Path

import httpx

from aggregator.errors import Unavailable
from aggregator.settings import Settings


class KubernetesAuth:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._token = ""
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def token(self, force: bool = False) -> str:
        if not force and self._token and self._expires_at - time.monotonic() > 60:
            return self._token
        async with self._lock:
            if not force and self._token and self._expires_at - time.monotonic() > 60:
                return self._token
            try:
                jwt = await asyncio.to_thread(Path(self.settings.openbao_k8s_token_file).read_text)
                response = await self.client.post(
                    f"/v1/auth/{self.settings.openbao_k8s_auth_path}/login",
                    json={"role": self.settings.openbao_k8s_role, "jwt": jwt.strip()},
                )
                response.raise_for_status()
                auth = response.json()["auth"]
                self._token = str(auth["client_token"])
                self._expires_at = time.monotonic() + int(auth.get("lease_duration", 900))
                return self._token
            except (OSError, KeyError, ValueError, httpx.HTTPError) as exc:
                raise Unavailable("Kubernetes auth login failed") from exc

    def valid(self) -> bool:
        return bool(self._token and self._expires_at > time.monotonic())


class StaticTokenAuth:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    async def token(self, force: bool = False) -> str:
        return self.secret

    def valid(self) -> bool:
        return bool(self.secret)


TokenProvider = KubernetesAuth | StaticTokenAuth


def create_auth(client: httpx.AsyncClient, settings: Settings) -> TokenProvider:
    if settings.openbao_auth_method == "token":
        assert settings.openbao_token is not None
        return StaticTokenAuth(settings.openbao_token.get_secret_value())
    return KubernetesAuth(client, settings)
