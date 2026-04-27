"""Limitador en memoria (ventana deslizante) para webhooks y endpoints públicos."""
import time
from collections import defaultdict
from typing import DefaultDict, List


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: DefaultDict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        events = self._events[key]
        events[:] = [t for t in events if t >= window_start]
        if len(events) >= self.max_events:
            return False
        events.append(now)
        return True
