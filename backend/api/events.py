"""Bounded thread-safe event delivery for polling UI clients."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone

from backend.api.contracts import EventBatch, RunEvent


class BoundedEventBroker:
    def __init__(self, maximum_events: int = 1000) -> None:
        if maximum_events < 10 or maximum_events > 100_000:
            raise ValueError("event capacity must be from 10 through 100000")
        self._events: deque[RunEvent] = deque(maxlen=maximum_events)
        self._next_sequence = 1
        self._lock = threading.Lock()

    def publish(
        self,
        *,
        event_type: str,
        run_id: str | None = None,
        stage: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        message: str | None = None,
    ) -> RunEvent:
        with self._lock:
            event = RunEvent(
                sequence=self._next_sequence,
                occurred_at=datetime.now(timezone.utc),
                event_type=event_type,
                run_id=run_id,
                stage=stage,
                progress_current=progress_current,
                progress_total=progress_total,
                message=message,
            )
            self._next_sequence += 1
            self._events.append(event)
            return event

    def read(self, *, after_sequence: int, limit: int) -> EventBatch:
        if after_sequence < 0:
            raise ValueError("event sequence must be nonnegative")
        if limit < 1 or limit > 500:
            raise ValueError("event read limit must be from 1 through 500")
        with self._lock:
            oldest = self._events[0].sequence if self._events else self._next_sequence
            gap = after_sequence > 0 and after_sequence < oldest - 1
            events = tuple(event for event in self._events if event.sequence > after_sequence)[
                :limit
            ]
            return EventBatch(
                events=events,
                latest_sequence=self._next_sequence - 1,
                gap_detected=gap,
            )
