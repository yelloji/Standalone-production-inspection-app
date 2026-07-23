"""Bounded background run-command dispatcher used by thin HTTP handlers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from backend.api.events import BoundedEventBroker


class RunCommandDispatcher:
    def __init__(
        self,
        *,
        execute_run: Callable[[str], None],
        cancel_run: Callable[[str], None],
        events: BoundedEventBroker,
        maximum_pending_runs: int = 8,
    ) -> None:
        if maximum_pending_runs < 1 or maximum_pending_runs > 100:
            raise ValueError("pending run limit must be from 1 through 100")
        self._execute_run = execute_run
        self._cancel_run = cancel_run
        self._events = events
        self._capacity = threading.BoundedSemaphore(maximum_pending_runs)
        self._active: set[str] = set()
        self._lock = threading.Lock()
        self._pool: ThreadPoolExecutor | None = None

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._pool is not None

    def start(self) -> None:
        with self._lock:
            if self._pool is None:
                self._pool = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix="run-command",
                )

    def close(self) -> None:
        with self._lock:
            pool = self._pool
            self._pool = None
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=False)

    def submit(self, run_id: str) -> bool:
        with self._lock:
            if self._pool is None:
                raise RuntimeError("run command dispatcher is not ready")
            if run_id in self._active or not self._capacity.acquire(blocking=False):
                return False
            self._active.add(run_id)
            future = self._pool.submit(self._execute, run_id)
        future.add_done_callback(lambda completed: self._finished(run_id, completed))
        return True

    def cancel(self, run_id: str) -> None:
        self._cancel_run(run_id)
        self._events.publish(event_type="run_cancel_requested", run_id=run_id)

    def _execute(self, run_id: str) -> None:
        self._events.publish(event_type="run_started", run_id=run_id)
        try:
            self._execute_run(run_id)
        except Exception as error:
            self._events.publish(
                event_type="run_failed",
                run_id=run_id,
                message=type(error).__name__,
            )
            raise
        else:
            self._events.publish(event_type="run_completed", run_id=run_id)

    def _finished(self, run_id: str, future: Future[None]) -> None:
        try:
            future.exception()
        finally:
            with self._lock:
                self._active.discard(run_id)
                self._capacity.release()
