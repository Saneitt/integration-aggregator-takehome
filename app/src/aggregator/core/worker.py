import asyncio
import logging
import time

from aggregator.core.activity import ActivityLog
from aggregator.core.oauth_states import OAuthStateStore
from aggregator.core.requests import RequestStore
from aggregator.metrics import (
    token_queue_depth,
    token_request_duration_seconds,
    token_requests_total,
)
from aggregator.openbao.oauthapp import OAuthAppGateway

logger = logging.getLogger(__name__)


class TokenWorker:
    def __init__(
        self,
        gateway: OAuthAppGateway,
        requests: RequestStore,
        concurrency: int,
        max_queue: int,
        activity: ActivityLog | None = None,
    ) -> None:
        self.gateway = gateway
        self.activity = activity
        self.requests = requests
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=max_queue)
        self.concurrency = concurrency
        self.tasks: list[asyncio.Task[None]] = []
        self.stopping = False

    def start(self) -> None:
        self.stopping = False
        self.tasks = [
            asyncio.create_task(self._run(), name=f"token-worker-{n}")
            for n in range(self.concurrency)
        ]

    def submit(self, request_id: str) -> None:
        if self.stopping:
            raise asyncio.QueueFull
        self.queue.put_nowait(request_id)
        token_queue_depth.set(self.queue.qsize())

    async def _run(self) -> None:
        while True:
            request_id = await self.queue.get()
            try:
                if request_id is None:
                    return
                row = self.requests.get(request_id)
                if row is None or not self.requests.start(request_id):
                    continue
                started = time.perf_counter()
                try:
                    token = await self.gateway.get_token(f"{row.provider}_{row.user}")
                    if not token.get("access_token"):
                        self.requests.fail(
                            request_id,
                            "upstream_error",
                            "The token service returned no access token.",
                        )
                        token_requests_total.labels(outcome="failed").inc()
                        if self.activity:
                            self.activity.add("request_failed", row.provider, row.user, request_id)
                    else:
                        self.requests.succeed(request_id, token)
                        token_requests_total.labels(outcome="succeeded").inc()
                        if self.activity:
                            self.activity.add(
                                "request_succeeded", row.provider, row.user, request_id
                            )
                except Exception as exc:
                    from aggregator.errors import NotFound

                    if isinstance(exc, NotFound):
                        self.requests.fail(
                            request_id, "not_connected", "This user has not connected the provider."
                        )
                    else:
                        logger.warning("Token retrieval failed for an asynchronous request.")
                        self.requests.fail(
                            request_id,
                            "upstream_error",
                            "The token service could not complete the request.",
                        )
                    token_requests_total.labels(outcome="failed").inc()
                    if self.activity:
                        self.activity.add("request_failed", row.provider, row.user, request_id)
                finally:
                    token_request_duration_seconds.observe(time.perf_counter() - started)
            finally:
                self.queue.task_done()
                token_queue_depth.set(self.queue.qsize())

    async def stop(self, drain_timeout: float = 20) -> None:
        self.stopping = True
        try:
            await asyncio.wait_for(self.queue.join(), timeout=drain_timeout)
        except TimeoutError:
            logger.warning("Token queue did not drain before shutdown deadline.")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    def healthy(self) -> bool:
        return bool(self.tasks) and all(not task.done() for task in self.tasks)


class Janitor:
    def __init__(
        self, states: OAuthStateStore, requests: RequestStore, interval: float = 30
    ) -> None:
        self.states, self.requests, self.interval = states, requests, interval
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._run(), name="state-janitor")

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            self.states.purge_expired()
            self.requests.purge_expired()

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
