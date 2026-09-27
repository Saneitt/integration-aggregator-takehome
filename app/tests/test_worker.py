import asyncio

import httpx
import pytest

from aggregator.core.requests import RequestStore
from aggregator.core.worker import TokenWorker
from aggregator.main import create_app
from aggregator.openbao.auth import StaticTokenAuth
from aggregator.settings import Settings
from tests.fakes import FakeGateway


@pytest.mark.asyncio
async def test_worker_fulfils_one_thousand_requests_once() -> None:
    gateway = FakeGateway()
    gateway.credentials.update(
        {
            f"github_user-{index}": {"access_token": f"token-{index}", "token_type": "Bearer"}
            for index in range(1000)
        }
    )
    store = RequestStore(ttl_seconds=300, max_size=1100)
    worker = TokenWorker(gateway, store, concurrency=32, max_queue=1000)
    worker.start()
    for index in range(1000):
        request_id = str(index)
        store.create(request_id, "github", f"user-{index}")
        worker.submit(request_id)
    await asyncio.wait_for(worker.queue.join(), timeout=10)
    assert gateway.get_token_calls == 1000
    assert all(store.get(str(index)).status == "succeeded" for index in range(1000))
    await worker.stop()


@pytest.mark.asyncio
async def test_worker_queue_is_bounded() -> None:
    worker = TokenWorker(FakeGateway(), RequestStore(300), concurrency=1, max_queue=1)
    worker.queue.put_nowait("queued")
    with pytest.raises(asyncio.QueueFull):
        worker.submit("overflow")


@pytest.mark.asyncio
async def test_api_accepts_one_thousand_concurrent_token_requests() -> None:
    gateway = FakeGateway()
    gateway.credentials.update(
        {
            f"github_user-{index}": {"access_token": f"token-{index}", "token_type": "Bearer"}
            for index in range(1000)
        }
    )
    settings = Settings(
        openbao_addr="http://127.0.0.1:9",
        callback_url="http://localhost:8080/callback",
        openbao_auth_method="token",
        openbao_token="test-token",
        worker_concurrency=32,
        queue_max_size=1000,
    )
    app = create_app(settings, gateway, StaticTokenAuth("test-token"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            registered = await client.post(
                "/providers",
                json={
                    "name": "github",
                    "provider": "github",
                    "client_id": "fake",
                    "client_secret": "fake-secret",
                },
            )
            assert registered.status_code == 201
            accepted = await asyncio.gather(*(client.get(f"/github/user-{i}") for i in range(1000)))
            assert all(response.status_code == 202 for response in accepted)
            locations = [response.headers["location"] for response in accepted]
            for _ in range(100):
                results = await asyncio.gather(*(client.get(path) for path in locations))
                if all(result.json()["status"] == "succeeded" for result in results):
                    break
                await asyncio.sleep(0.01)
            assert all(result.json()["status"] == "succeeded" for result in results)
            assert gateway.get_token_calls == 1000
