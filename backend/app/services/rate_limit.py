"""Per-client sliding-window rate limit for the chat endpoint.

Limitation, on purpose: this is in-memory and per-process. The API has no
auth, so this only stops casual abuse of a free-tier LLM key. With several
workers/instances each keeps its own counts (the effective limit is
N x the setting), counts reset on restart, and the client key is the address
the proxy reports, so clients behind one NAT share a budget. Put a real
limiter (Redis, or the platform's) in front before exposing this widely.
"""

from __future__ import annotations

import threading
import time
from collections import deque

WINDOW_SECONDS = 60.0
# Prune idle keys once the table grows past this, so memory stays bounded.
PRUNE_THRESHOLD = 1024


class SlidingWindowLimiter:
    def __init__(self, window: float = WINDOW_SECONDS) -> None:
        self._window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, now: float | None = None) -> float | None:
        """Records a hit and returns None if allowed, else seconds until a slot frees up."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > PRUNE_THRESHOLD:
                self._prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= limit:
                return max(self._window - (now - hits[0]), 1.0)
            hits.append(now)
            return None

    def _prune(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= self._window]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


chat_limiter = SlidingWindowLimiter()
