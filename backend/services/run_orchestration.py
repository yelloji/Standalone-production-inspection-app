"""Durable bounded orchestration for parallel reconstruction and inference."""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.records import (
    RunControlMetadata,
    RunStageCheckpointMetadata,
)
from backend.database.repositories import MetadataRepository
from backend.domain.value_objects import normalize_relative_path


class RunOrchestrationError(RuntimeError):
    """Base class for durable run-coordination failures."""

    code = "run_orchestration_failed"


class RunLeaseUnavailable(RunOrchestrationError):
    code = "run_lease_unavailable"


class RunLeaseLost(RunOrchestrationError):
    code = "run_lease_lost"


class RunCancelled(RunOrchestrationError):
    code = "run_cancelled"


class ReconstructionGateFailure(RunOrchestrationError):
    code = "reconstruction_validation_failed"


class StageExecutionFailure(RunOrchestrationError):
    code = "stage_execution_failed"


class RetryableStageError(RuntimeError):
    """Explicitly marks a stage failure safe for a bounded retry."""

    code = "retryable_stage_failure"


class RunStage(str, Enum):
    RECONSTRUCTION = "reconstruction"
    INFERENCE = "inference"
    VALIDATION = "validation"
    PUBLICATION = "publication"


@dataclass(frozen=True, slots=True)
class StageEvidence:
    relative_path: str
    sha256: str
    reconstruction_passed: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relative_path",
            normalize_relative_path(self.relative_path),
        )
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in self.sha256
        ):
            raise ValueError("stage evidence requires a SHA-256 value")


class RunStageExecutor(Protocol):
    def reconstruct(self, cancelled: Callable[[], bool]) -> StageEvidence: ...

    def infer(self, cancelled: Callable[[], bool]) -> StageEvidence: ...

    def validate(
        self,
        reconstruction: StageEvidence,
        inference: StageEvidence,
        cancelled: Callable[[], bool],
    ) -> StageEvidence: ...

    def publish(
        self,
        reconstruction: StageEvidence,
        inference: StageEvidence,
        validation: StageEvidence,
        cancelled: Callable[[], bool],
    ) -> StageEvidence: ...


@dataclass(frozen=True, slots=True)
class RunOrchestratorConfiguration:
    maximum_stage_attempts: int = 2
    lease_duration_seconds: float = 30.0
    heartbeat_interval_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.maximum_stage_attempts < 1 or self.maximum_stage_attempts > 3:
            raise ValueError("maximum stage attempts must be from 1 through 3")
        if self.lease_duration_seconds < 5.0 or self.lease_duration_seconds > 300.0:
            raise ValueError("lease duration must be from 5 through 300 seconds")
        if (
            self.heartbeat_interval_seconds <= 0.0
            or self.heartbeat_interval_seconds >= self.lease_duration_seconds / 2
        ):
            raise ValueError("heartbeat must be positive and less than half the lease duration")


@dataclass(frozen=True, slots=True)
class CompletedRunEvidence:
    run_id: str
    reconstruction: StageEvidence
    inference: StageEvidence
    validation: StageEvidence
    publication: StageEvidence


class DurableRunOrchestrator:
    """Coordinate one run with durable checkpoints and at most two workers."""

    def __init__(
        self,
        *,
        paths: ApplicationPaths,
        session_factory: sessionmaker[Session],
        configuration: RunOrchestratorConfiguration | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._configuration = (
            RunOrchestratorConfiguration() if configuration is None else configuration
        )
        self._now = _utc_now if now is None else now

    def request_cancellation(self, run_id: str) -> None:
        now = self._now()
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            if repository.get_run(run_id) is None:
                raise KeyError(f"unknown run: {run_id}")
            control = repository.get_run_control(run_id)
            if control is None:
                repository.add_run_control(
                    RunControlMetadata(
                        run_id=run_id,
                        cancellation_requested=True,
                        lease_owner=None,
                        lease_expires_at=None,
                        updated_at=now,
                    )
                )
            else:
                repository.set_cancellation_requested(run_id, True, now)

    def execute(
        self,
        run_id: str,
        stage_executor: RunStageExecutor,
    ) -> CompletedRunEvidence:
        owner = uuid.uuid4().hex
        cancellation = threading.Event()
        self._acquire(run_id, owner)
        run_started = False
        try:
            self._mark_running(run_id)
            run_started = True
            if self._is_cancellation_requested(run_id):
                cancellation.set()
                raise RunCancelled("run cancellation was already requested")
            with ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="inspection-run",
            ) as pool:
                reconstruction_future = self._resume_or_submit(
                    pool,
                    run_id,
                    RunStage.RECONSTRUCTION,
                    lambda: stage_executor.reconstruct(cancellation.is_set),
                    cancellation,
                )
                inference_future = self._resume_or_submit(
                    pool,
                    run_id,
                    RunStage.INFERENCE,
                    lambda: stage_executor.infer(cancellation.is_set),
                    cancellation,
                )
                parallel = self._await_futures(
                    run_id,
                    owner,
                    {
                        RunStage.RECONSTRUCTION: reconstruction_future,
                        RunStage.INFERENCE: inference_future,
                    },
                    cancellation,
                )
                reconstruction = parallel[RunStage.RECONSTRUCTION]
                inference = parallel[RunStage.INFERENCE]

                def validate_with_gate() -> StageEvidence:
                    evidence = stage_executor.validate(
                        reconstruction,
                        inference,
                        cancellation.is_set,
                    )
                    if evidence.reconstruction_passed is not True:
                        raise ReconstructionGateFailure(
                            "reconstruction validation gate did not pass"
                        )
                    return evidence

                validation = self._run_sequential_stage(
                    pool,
                    run_id,
                    owner,
                    RunStage.VALIDATION,
                    validate_with_gate,
                    cancellation,
                )
                publication = self._run_sequential_stage(
                    pool,
                    run_id,
                    owner,
                    RunStage.PUBLICATION,
                    lambda: stage_executor.publish(
                        reconstruction,
                        inference,
                        validation,
                        cancellation.is_set,
                    ),
                    cancellation,
                )
            self._mark_terminal(run_id, "completed", None)
            return CompletedRunEvidence(
                run_id=run_id,
                reconstruction=reconstruction,
                inference=inference,
                validation=validation,
                publication=publication,
            )
        except RunCancelled:
            cancellation.set()
            if run_started:
                self._mark_terminal(run_id, "cancelled", RunCancelled.code)
            raise
        except Exception as error:
            cancellation.set()
            if run_started:
                self._mark_terminal(run_id, "failed", _failure_code(error))
            raise
        finally:
            self._release(run_id, owner)

    def _resume_or_submit(
        self,
        pool: ThreadPoolExecutor,
        run_id: str,
        stage: RunStage,
        operation: Callable[[], StageEvidence],
        cancellation: threading.Event,
    ) -> Future[StageEvidence]:
        completed = self._completed_evidence(run_id, stage)
        if completed is not None:
            future: Future[StageEvidence] = Future()
            future.set_result(completed)
            return future
        return pool.submit(
            self._execute_stage,
            run_id,
            stage,
            operation,
            cancellation,
        )

    def _run_sequential_stage(
        self,
        pool: ThreadPoolExecutor,
        run_id: str,
        owner: str,
        stage: RunStage,
        operation: Callable[[], StageEvidence],
        cancellation: threading.Event,
    ) -> StageEvidence:
        future = self._resume_or_submit(pool, run_id, stage, operation, cancellation)
        return self._await_futures(
            run_id,
            owner,
            {stage: future},
            cancellation,
        )[stage]

    def _execute_stage(
        self,
        run_id: str,
        stage: RunStage,
        operation: Callable[[], StageEvidence],
        cancellation: threading.Event,
    ) -> StageEvidence:
        attempts = self._checkpoint_attempts(run_id, stage)
        while attempts < self._configuration.maximum_stage_attempts:
            if cancellation.is_set() or self._is_cancellation_requested(run_id):
                self._cancel_checkpoint(run_id, stage)
                raise RunCancelled(f"{stage.value} cancelled")
            attempts += 1
            self._start_checkpoint(run_id, stage, attempts)
            try:
                evidence = operation()
                if cancellation.is_set():
                    raise RunCancelled(f"{stage.value} cancelled")
                self._verify_evidence(evidence)
                self._complete_checkpoint(run_id, stage, attempts, evidence)
                return evidence
            except RunCancelled:
                self._cancel_checkpoint(run_id, stage)
                raise
            except RetryableStageError as error:
                self._fail_checkpoint(run_id, stage, _failure_code(error))
                if attempts >= self._configuration.maximum_stage_attempts:
                    raise StageExecutionFailure(
                        f"{stage.value} exhausted its retry limit"
                    ) from error
            except Exception as error:
                self._fail_checkpoint(run_id, stage, _failure_code(error))
                raise
        raise StageExecutionFailure(f"{stage.value} has no attempts remaining")

    def _await_futures(
        self,
        run_id: str,
        owner: str,
        futures: dict[RunStage, Future[StageEvidence]],
        cancellation: threading.Event,
    ) -> dict[RunStage, StageEvidence]:
        remaining = set(futures.values())
        first_error: BaseException | None = None
        while remaining:
            done, remaining = wait(
                remaining,
                timeout=self._configuration.heartbeat_interval_seconds,
                return_when=FIRST_COMPLETED,
            )
            self._heartbeat(run_id, owner, cancellation)
            for future in done:
                error = future.exception()
                if error is not None and first_error is None:
                    first_error = error
                    cancellation.set()
        if first_error is not None:
            raise first_error
        return {stage: future.result() for stage, future in futures.items()}

    def _heartbeat(
        self,
        run_id: str,
        owner: str,
        cancellation: threading.Event,
    ) -> None:
        now = self._now()
        expires = now + timedelta(seconds=self._configuration.lease_duration_seconds)
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            control = repository.get_run_control(run_id)
            if control is None or control.cancellation_requested:
                cancellation.set()
            if not repository.renew_run_lease(run_id, owner, now, expires):
                cancellation.set()
                raise RunLeaseLost("run lease was lost")

    def _acquire(self, run_id: str, owner: str) -> None:
        now = self._now()
        expires = now + timedelta(seconds=self._configuration.lease_duration_seconds)
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            if repository.get_run(run_id) is None:
                raise KeyError(f"unknown run: {run_id}")
            if repository.get_run_control(run_id) is None:
                repository.add_run_control(
                    RunControlMetadata(
                        run_id=run_id,
                        cancellation_requested=False,
                        lease_owner=None,
                        lease_expires_at=None,
                        updated_at=now,
                    )
                )
            if not repository.try_acquire_run_lease(run_id, owner, now, expires):
                raise RunLeaseUnavailable("run is already owned by another coordinator")

    def _release(self, run_id: str, owner: str) -> None:
        with transaction(self._session_factory) as session:
            MetadataRepository(session).release_run_lease(run_id, owner, self._now())

    def _mark_running(self, run_id: str) -> None:
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            run = repository.get_run(run_id)
            if run is None:
                raise KeyError(f"unknown run: {run_id}")
            if run.status in {"completed", "cancelled"}:
                raise RunOrchestrationError(f"cannot execute terminal {run.status} run")
            repository.set_run_status(
                run_id,
                "running",
                failure_code=None,
                started_at=run.started_at or self._now(),
                finished_at=None,
            )

    def _mark_terminal(self, run_id: str, status: str, failure_code: str | None) -> None:
        with transaction(self._session_factory) as session:
            MetadataRepository(session).set_run_status(
                run_id,
                status,
                failure_code=failure_code,
                started_at=None,
                finished_at=self._now(),
            )

    def _is_cancellation_requested(self, run_id: str) -> bool:
        with transaction(self._session_factory) as session:
            control = MetadataRepository(session).get_run_control(run_id)
            return control is not None and control.cancellation_requested

    def _checkpoint_attempts(self, run_id: str, stage: RunStage) -> int:
        with transaction(self._session_factory) as session:
            checkpoint = MetadataRepository(session).get_stage_checkpoint(
                run_id,
                stage.value,
            )
            return 0 if checkpoint is None else checkpoint.attempt_count

    def _start_checkpoint(self, run_id: str, stage: RunStage, attempts: int) -> None:
        self._put_checkpoint(run_id, stage, "running", attempts, None, None)

    def _complete_checkpoint(
        self,
        run_id: str,
        stage: RunStage,
        attempts: int,
        evidence: StageEvidence,
    ) -> None:
        self._put_checkpoint(run_id, stage, "completed", attempts, evidence, None)

    def _fail_checkpoint(self, run_id: str, stage: RunStage, code: str) -> None:
        attempts = self._checkpoint_attempts(run_id, stage)
        self._put_checkpoint(run_id, stage, "failed", attempts, None, code)

    def _cancel_checkpoint(self, run_id: str, stage: RunStage) -> None:
        attempts = self._checkpoint_attempts(run_id, stage)
        self._put_checkpoint(
            run_id,
            stage,
            "cancelled",
            attempts,
            None,
            RunCancelled.code,
        )

    def _put_checkpoint(
        self,
        run_id: str,
        stage: RunStage,
        status: str,
        attempts: int,
        evidence: StageEvidence | None,
        failure_code: str | None,
    ) -> None:
        with transaction(self._session_factory) as session:
            MetadataRepository(session).put_stage_checkpoint(
                RunStageCheckpointMetadata(
                    run_id=run_id,
                    stage_name=stage.value,
                    status=status,
                    attempt_count=attempts,
                    evidence_path=None if evidence is None else evidence.relative_path,
                    evidence_sha256=None if evidence is None else evidence.sha256.lower(),
                    failure_code=failure_code,
                    updated_at=self._now(),
                )
            )

    def _completed_evidence(
        self,
        run_id: str,
        stage: RunStage,
    ) -> StageEvidence | None:
        with transaction(self._session_factory) as session:
            checkpoint = MetadataRepository(session).get_stage_checkpoint(
                run_id,
                stage.value,
            )
        if (
            checkpoint is None
            or checkpoint.status != "completed"
            or checkpoint.evidence_path is None
            or checkpoint.evidence_sha256 is None
        ):
            return None
        evidence = StageEvidence(
            relative_path=checkpoint.evidence_path,
            sha256=checkpoint.evidence_sha256,
            reconstruction_passed=True if stage is RunStage.VALIDATION else None,
        )
        try:
            self._verify_evidence(evidence)
        except Exception:
            self._fail_checkpoint(run_id, stage, "checkpoint_evidence_invalid")
            return None
        return evidence

    def _verify_evidence(self, evidence: StageEvidence) -> None:
        path = self._paths.resolve_data_path(evidence.relative_path)
        if not path.is_file() or path.is_symlink():
            raise StageExecutionFailure("stage evidence is not a regular file")
        if _file_sha256(path) != evidence.sha256.lower():
            raise StageExecutionFailure("stage evidence checksum mismatch")


def _failure_code(error: BaseException) -> str:
    value = getattr(error, "code", type(error).__name__)
    return str(value)[:128]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
