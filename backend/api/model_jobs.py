"""Single-worker model-library jobs outside HTTP request handlers."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from backend.services.model_import import ModelImportError, ModelImportService
from backend.services.model_library import ModelLibraryError, ModelLibraryService
from backend.services.model_validation import ModelBundleValidationError

ModelJobAction = Literal["import", "archive", "delete"]
ModelJobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class ModelJob:
    job_id: str
    action: ModelJobAction
    status: ModelJobStatus
    model_bundle_id: str | None = None
    message: str | None = None


class ModelJobDispatcher:
    def __init__(
        self,
        *,
        importer: ModelImportService,
        library: ModelLibraryService,
        maximum_retained_jobs: int = 200,
    ) -> None:
        if maximum_retained_jobs < 10:
            raise ValueError("maximum retained model jobs must be at least 10")
        self._importer = importer
        self._library = library
        self._maximum_retained_jobs = maximum_retained_jobs
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="model-library")
        self._jobs: dict[str, ModelJob] = {}
        self._lock = threading.Lock()
        self._closed = False

    @property
    def ready(self) -> bool:
        with self._lock:
            return not self._closed

    def submit_import(self, source: Path) -> ModelJob:
        return self._submit("import", lambda: self._importer.import_bundle(source))

    def submit_archive(self, model_bundle_id: str) -> ModelJob:
        return self._submit(
            "archive",
            lambda: self._library.archive(model_bundle_id),
            requested_model_id=model_bundle_id,
        )

    def submit_delete(self, model_bundle_id: str) -> ModelJob:
        def delete() -> None:
            self._library.delete_archived(model_bundle_id)

        return self._submit(
            "delete",
            delete,
            requested_model_id=model_bundle_id,
        )

    def get(self, job_id: str) -> ModelJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _submit(
        self,
        action: ModelJobAction,
        operation: Callable[[], object],
        *,
        requested_model_id: str | None = None,
    ) -> ModelJob:
        job = ModelJob(
            job_id=uuid.uuid4().hex,
            action=action,
            status="queued",
            model_bundle_id=requested_model_id,
        )
        with self._lock:
            if self._closed:
                raise RuntimeError("model job dispatcher is closed")
            self._trim_completed_jobs()
            self._jobs[job.job_id] = job
            future = self._executor.submit(operation)

        def complete(
            completed: Future[object],
            job_id: str = job.job_id,
        ) -> None:
            self._complete(job_id, completed)

        future.add_done_callback(complete)
        with self._lock:
            current = self._jobs[job.job_id]
            if current.status == "queued":
                self._jobs[job.job_id] = replace(current, status="running")
            return self._jobs[job.job_id]

    def _complete(self, job_id: str, future: Future[object]) -> None:
        try:
            result = future.result()
            model_bundle_id = getattr(result, "model_bundle_id", None)
            completed = ModelJob(
                job_id=job_id,
                action=self._job_action(job_id),
                status="completed",
                model_bundle_id=model_bundle_id or self._job_model_id(job_id),
            )
        except BaseException as error:
            completed = ModelJob(
                job_id=job_id,
                action=self._job_action(job_id),
                status="failed",
                model_bundle_id=self._job_model_id(job_id),
                message=_safe_error_message(error),
            )
        with self._lock:
            self._jobs[job_id] = completed

    def _job_action(self, job_id: str) -> ModelJobAction:
        with self._lock:
            return self._jobs[job_id].action

    def _job_model_id(self, job_id: str) -> str | None:
        with self._lock:
            return self._jobs[job_id].model_bundle_id

    def _trim_completed_jobs(self) -> None:
        overflow = len(self._jobs) - self._maximum_retained_jobs + 1
        if overflow <= 0:
            return
        removable = [
            job_id for job_id, job in self._jobs.items() if job.status in {"completed", "failed"}
        ]
        for job_id in removable[:overflow]:
            self._jobs.pop(job_id, None)


def _safe_error_message(error: BaseException) -> str:
    if isinstance(
        error,
        (ModelImportError, ModelBundleValidationError, ModelLibraryError),
    ):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "the selected model bundle is no longer available"
    return "the model operation failed"
