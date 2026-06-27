"""In-process pub/sub event bus.

The Supervisor (L5) and any host UI subscribe to tool/supervisor events so they
can observe everything without being on the critical execution path. A single
bus keeps the layers decoupled: the router emits, listeners react, no layer
imports another just to be notified.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Handler) -> None:
        if handler in self._handlers.get(event, []):
            self._handlers[event].remove(handler)

    def emit(self, event: str, payload: Any) -> None:
        for handler in list(self._handlers.get(event, ())):
            try:
                handler(payload)
            except Exception:
                # A misbehaving listener must never break the pipeline.
                pass


# Shared singleton for a single-host deployment.
bus = EventBus()
