import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from aggregator.errors import InvalidState


@dataclass(frozen=True, slots=True)
class OAuthState:
    provider: str
    user: str
    expires_at: float


class OAuthStateStore:
    def __init__(
        self, ttl_seconds: int, max_size: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.clock = clock
        self._states: dict[str, OAuthState] = {}

    def purge_expired(self) -> int:
        now = self.clock()
        expired = [key for key, value in self._states.items() if value.expires_at <= now]
        for key in expired:
            self._states.pop(key, None)
        return len(expired)

    def create(self, provider: str, user: str) -> str:
        self.purge_expired()
        if len(self._states) >= self.max_size:
            raise InvalidState("Too many pending OAuth states.")
        state = secrets.token_urlsafe(32)
        self._states[state] = OAuthState(provider, user, self.clock() + self.ttl_seconds)
        return state

    def consume(self, state: str) -> tuple[str, str]:
        value = self._states.pop(state, None)
        if value is None or value.expires_at <= self.clock():
            raise InvalidState()
        return value.provider, value.user

    def discard(self, state: str) -> None:
        self._states.pop(state, None)

    def __len__(self) -> int:
        return len(self._states)
