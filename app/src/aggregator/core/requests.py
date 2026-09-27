import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

RequestStatus = Literal["pending", "running", "succeeded", "failed"]


@dataclass(slots=True)
class TokenRequest:
    request_id: str
    provider: str
    user: str
    status: RequestStatus
    created_at: float
    updated_at: float
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


class RequestStore:
    def __init__(
        self, ttl_seconds: int, max_size: int = 10_000, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.clock = clock
        self._requests: dict[str, TokenRequest] = {}

    def purge_expired(self) -> int:
        cutoff = self.clock() - self.ttl_seconds
        expired = [
            key
            for key, row in self._requests.items()
            if row.status in {"succeeded", "failed"} and row.updated_at <= cutoff
        ]
        for key in expired:
            self._requests.pop(key, None)
        return len(expired)

    def create(self, request_id: str, provider: str, user: str) -> TokenRequest:
        self.purge_expired()
        if len(self._requests) >= self.max_size:
            raise OverflowError("request store is full")
        now = self.clock()
        row = TokenRequest(request_id, provider, user, "pending", now, now)
        self._requests[request_id] = row
        return row

    def start(self, request_id: str) -> bool:
        row = self._requests.get(request_id)
        if row is None or row.status != "pending":
            return False
        row.status, row.updated_at = "running", self.clock()
        return True

    def succeed(self, request_id: str, result: dict[str, Any]) -> None:
        row = self._requests[request_id]
        row.status, row.result, row.updated_at = "succeeded", result, self.clock()

    def fail(self, request_id: str, code: str, message: str) -> None:
        row = self._requests[request_id]
        row.status, row.error, row.updated_at = (
            "failed",
            {"code": code, "message": message},
            self.clock(),
        )

    def get(self, request_id: str) -> TokenRequest | None:
        self.purge_expired()
        return self._requests.get(request_id)

    def delete(self, request_id: str) -> None:
        self._requests.pop(request_id, None)

    def __len__(self) -> int:
        return len(self._requests)
