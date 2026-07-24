"""Single-worker offline reconstruction jobs outside HTTP request handlers."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from backend.domain.contracts import DiscSide
from backend.services.offline_reconstruction import (
    OfflineReconstructionError,
    OfflineReconstructionResult,
    OfflineReconstructionService,
)

ReconstructionJobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class ReconstructionJob:
    job_id: str
    status: ReconstructionJobStatus
    stage: str
    progress_current: int
    progress_total: int
    result: OfflineReconstructionResult | None = None
    message: str | None = None


class ReconstructionJobDispatcher:
    def __init__(self, service: OfflineReconstructionService) -> None:
        self._service = service
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reconstruction")
        self._jobs: dict[str, ReconstructionJob] = {}
        self._lock = threading.Lock()
        self._closed = False

    def submit(self, source: Path, side: DiscSide, preview_size: int) -> ReconstructionJob:
        job = ReconstructionJob(uuid.uuid4().hex, "queued", "queued", 0, 1)
        with self._lock:
            if self._closed:
                raise RuntimeError("reconstruction job dispatcher is closed")
            self._jobs[job.job_id] = job
            self._executor.submit(self._execute, job.job_id, source, side, preview_size)
            return job

    def get(self, job_id: str) -> ReconstructionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def preview_path(self, job_id: str) -> Path | None:
        job = self.get(job_id)
        if job is None or job.result is None:
            return None
        return self._service.paths.resolve_data_path(job.result.preview.relative_path)

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _progress(self, job_id: str, stage: str, current: int, total: int) -> None:
        with self._lock:
            current_job = self._jobs[job_id]
            self._jobs[job_id] = replace(
                current_job,
                status="running",
                stage=stage,
                progress_current=current,
                progress_total=total,
            )

    def _execute(
        self,
        job_id: str,
        source: Path,
        side: DiscSide,
        preview_size: int,
    ) -> None:
        try:
            result = self._service.reconstruct(
                source_directory=source,
                side=side,
                preview_size=preview_size,
                progress=lambda stage, current, total: self._progress(
                    job_id, stage, current, total
                ),
            )
            completed = ReconstructionJob(job_id, "completed", "completed", 1, 1, result)
        except BaseException as error:
            message = (
                str(error)
                if isinstance(error, (OfflineReconstructionError, ValueError, RuntimeError))
                else "offline reconstruction failed"
            )
            completed = ReconstructionJob(job_id, "failed", "failed", 0, 1, message=message)
        with self._lock:
            self._jobs[job_id] = completed
