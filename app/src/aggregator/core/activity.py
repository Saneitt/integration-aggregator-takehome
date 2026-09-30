from collections import deque
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

ActivityKind = Literal[
    "provider_registered",
    "provider_updated",
    "consent_started",
    "connected",
    "consent_denied",
    "request_queued",
    "request_succeeded",
    "request_failed",
]


class ActivityEvent(BaseModel):
    id: int
    at: datetime
    kind: ActivityKind
    provider: str
    user: str | None = None
    request_ref: str | None = None


class ActivityLog:
    """Recent non-secret events for the local demonstration page."""

    def __init__(self, limit: int = 80) -> None:
        self._events: deque[ActivityEvent] = deque(maxlen=limit)
        self._next_id = 1

    def add(
        self,
        kind: ActivityKind,
        provider: str,
        user: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self._events.append(
            ActivityEvent(
                id=self._next_id,
                at=datetime.now(UTC),
                kind=kind,
                provider=provider,
                user=user,
                request_ref=request_id[:8] if request_id else None,
            )
        )
        self._next_id += 1

    def recent(self) -> list[ActivityEvent]:
        return list(reversed(self._events))
