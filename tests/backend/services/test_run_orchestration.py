"""Durable parallel run orchestration, recovery, retry, and cancellation tests."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.repositories import MetadataRepository
from backend.services.run_orchestration import (
    DurableRunOrchestrator,
    ReconstructionGateFailure,
    RetryableStageError,
    RunCancelled,
    RunLeaseUnavailable,
    RunOrchestratorConfiguration,
    StageEvidence,
)
from tests.backend.database.factories import inspection_run, model_bundle, pipeline_snapshot


class FakeStageExecutor:
    def __init__(
        self,
        paths: ApplicationPaths,
        *,
        parallel_barrier: threading.Barrier | None = None,
        validation_passed: bool = True,
        retry_inference_once: bool = False,
    ) -> None:
        self.paths = paths
        self.parallel_barrier = parallel_barrier
        self.validation_passed = validation_passed
        self.retry_inference_once = retry_inference_once
        self.calls = {
            "reconstruction": 0,
            "inference": 0,
            "validation": 0,
            "publication": 0,
        }
        self._lock = threading.Lock()

    def reconstruct(self, cancelled: Callable[[], bool]) -> StageEvidence:
        call = self._called("reconstruction")
        self._parallel_wait(cancelled)
        return self._evidence("reconstruction", call)

    def infer(self, cancelled: Callable[[], bool]) -> StageEvidence:
        call = self._called("inference")
        self._parallel_wait(cancelled)
        if self.retry_inference_once and call == 1:
            raise RetryableStageError("temporary GPU queue fault")
        return self._evidence("inference", call)

    def validate(
        self,
        reconstruction: StageEvidence,
        inference: StageEvidence,
        cancelled: Callable[[], bool],
    ) -> StageEvidence:
        del reconstruction, inference
        if cancelled():
            raise RunCancelled("cancelled before validation")
        call = self._called("validation")
        evidence = self._evidence("validation", call)
        return StageEvidence(
            relative_path=evidence.relative_path,
            sha256=evidence.sha256,
            reconstruction_passed=self.validation_passed,
        )

    def publish(
        self,
        reconstruction: StageEvidence,
        inference: StageEvidence,
        validation: StageEvidence,
        cancelled: Callable[[], bool],
    ) -> StageEvidence:
        del reconstruction, inference, validation
        if cancelled():
            raise RunCancelled("cancelled before publication")
        call = self._called("publication")
        return self._evidence("publication", call)

    def _called(self, name: str) -> int:
        with self._lock:
            self.calls[name] += 1
            return self.calls[name]

    def _parallel_wait(self, cancelled: Callable[[], bool]) -> None:
        if self.parallel_barrier is not None:
            self.parallel_barrier.wait(timeout=5)
        if cancelled():
            raise RunCancelled("parallel stage cancelled")

    def _evidence(self, stage: str, call: int) -> StageEvidence:
        path = self.paths.resolve_data_path(f"runs/run-001/{stage}-{call}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{stage}:{call}", encoding="utf-8")
        return StageEvidence(
            relative_path=self.paths.to_data_relative_path(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )


class BlockingStageExecutor(FakeStageExecutor):
    def __init__(self, paths: ApplicationPaths) -> None:
        super().__init__(paths)
        self.reconstruction_started = threading.Event()
        self.inference_started = threading.Event()

    def reconstruct(self, cancelled: Callable[[], bool]) -> StageEvidence:
        self._called("reconstruction")
        self.reconstruction_started.set()
        return self._wait_for_cancel(cancelled)

    def infer(self, cancelled: Callable[[], bool]) -> StageEvidence:
        self._called("inference")
        self.inference_started.set()
        return self._wait_for_cancel(cancelled)

    def _wait_for_cancel(self, cancelled: Callable[[], bool]) -> StageEvidence:
        deadline = time.monotonic() + 5
        while not cancelled() and time.monotonic() < deadline:
            time.sleep(0.005)
        raise RunCancelled("cooperative stage cancellation")


def _seed(session_factory: sessionmaker[Session]) -> None:
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        repository.add_model_bundle(model_bundle())
        repository.add_pipeline_snapshot(pipeline_snapshot())
        repository.add_run(inspection_run())


def _orchestrator(
    paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> DurableRunOrchestrator:
    return DurableRunOrchestrator(
        paths=paths,
        session_factory=session_factory,
        configuration=RunOrchestratorConfiguration(
            maximum_stage_attempts=2,
            lease_duration_seconds=5,
            heartbeat_interval_seconds=0.02,
        ),
    )


def test_parallel_stages_checkpoint_and_publish_only_after_validation(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    _seed(session_factory)
    executor = FakeStageExecutor(
        application_paths,
        parallel_barrier=threading.Barrier(2),
    )

    result = _orchestrator(application_paths, session_factory).execute(
        "run-001",
        executor,
    )

    assert result.run_id == "run-001"
    assert executor.calls == {
        "reconstruction": 1,
        "inference": 1,
        "validation": 1,
        "publication": 1,
    }
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        run = repository.get_run("run-001")
        assert run is not None
        assert run.status == "completed"
        assert run.failure_code is None
        checkpoints = repository.list_stage_checkpoints("run-001")
        assert [checkpoint.stage_name for checkpoint in checkpoints] == [
            "inference",
            "publication",
            "reconstruction",
            "validation",
        ]
        assert all(checkpoint.status == "completed" for checkpoint in checkpoints)
        assert all(checkpoint.attempt_count == 1 for checkpoint in checkpoints)
        control = repository.get_run_control("run-001")
        assert control is not None
        assert control.lease_owner is None


def test_gate_blocks_publication_and_resume_reuses_valid_evidence(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    _seed(session_factory)
    orchestrator = _orchestrator(application_paths, session_factory)
    failing = FakeStageExecutor(application_paths, validation_passed=False)

    with pytest.raises(ReconstructionGateFailure):
        orchestrator.execute("run-001", failing)

    assert failing.calls["publication"] == 0
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        run = repository.get_run("run-001")
        assert run is not None
        assert run.status == "failed"
        assert run.failure_code == ReconstructionGateFailure.code
        validation = repository.get_stage_checkpoint("run-001", "validation")
        assert validation is not None
        assert validation.status == "failed"

    resumed = FakeStageExecutor(application_paths, validation_passed=True)
    result = orchestrator.execute("run-001", resumed)

    assert result.validation.reconstruction_passed is True
    assert resumed.calls["reconstruction"] == 0
    assert resumed.calls["inference"] == 0
    assert resumed.calls["validation"] == 1
    assert resumed.calls["publication"] == 1
    with transaction(session_factory) as session:
        checkpoint = MetadataRepository(session).get_stage_checkpoint(
            "run-001",
            "validation",
        )
        assert checkpoint is not None
        assert checkpoint.status == "completed"
        assert checkpoint.attempt_count == 2


def test_only_explicit_retryable_failure_uses_bounded_second_attempt(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    _seed(session_factory)
    executor = FakeStageExecutor(application_paths, retry_inference_once=True)

    _orchestrator(application_paths, session_factory).execute("run-001", executor)

    assert executor.calls["inference"] == 2
    with transaction(session_factory) as session:
        checkpoint = MetadataRepository(session).get_stage_checkpoint("run-001", "inference")
        assert checkpoint is not None
        assert checkpoint.status == "completed"
        assert checkpoint.attempt_count == 2


def test_durable_cancellation_reaches_both_parallel_stages_and_run(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    _seed(session_factory)
    orchestrator = _orchestrator(application_paths, session_factory)
    executor = BlockingStageExecutor(application_paths)
    captured: list[BaseException] = []

    def execute() -> None:
        try:
            orchestrator.execute("run-001", executor)
        except BaseException as error:
            captured.append(error)

    thread = threading.Thread(target=execute)
    thread.start()
    assert executor.reconstruction_started.wait(timeout=5)
    assert executor.inference_started.wait(timeout=5)
    orchestrator.request_cancellation("run-001")
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(captured) == 1
    assert isinstance(captured[0], RunCancelled)
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        run = repository.get_run("run-001")
        assert run is not None
        assert run.status == "cancelled"
        control = repository.get_run_control("run-001")
        assert control is not None
        assert control.cancellation_requested
        assert control.lease_owner is None
        assert {
            checkpoint.status for checkpoint in repository.list_stage_checkpoints("run-001")
        } == {"cancelled"}


def test_active_lease_rejects_second_coordinator_without_changing_run(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    _seed(session_factory)
    now = datetime.now(timezone.utc)
    with transaction(session_factory) as session:
        acquired = MetadataRepository(session).try_acquire_run_lease(
            "run-001",
            "other-owner",
            now,
            now + timedelta(minutes=1),
        )
        assert acquired

    with pytest.raises(RunLeaseUnavailable):
        _orchestrator(application_paths, session_factory).execute(
            "run-001",
            FakeStageExecutor(application_paths),
        )

    with transaction(session_factory) as session:
        run = MetadataRepository(session).get_run("run-001")
        assert run is not None
        assert run.status == "created"


def test_tampered_completed_evidence_is_not_reused(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    _seed(session_factory)
    orchestrator = _orchestrator(application_paths, session_factory)
    first = FakeStageExecutor(application_paths, validation_passed=False)
    with pytest.raises(ReconstructionGateFailure):
        orchestrator.execute("run-001", first)
    application_paths.resolve_data_path("runs/run-001/reconstruction-1.json").write_text(
        "tampered",
        encoding="utf-8",
    )

    resumed = FakeStageExecutor(application_paths)
    orchestrator.execute("run-001", resumed)

    assert resumed.calls["reconstruction"] == 1
    assert resumed.calls["inference"] == 0
    with transaction(session_factory) as session:
        checkpoint = MetadataRepository(session).get_stage_checkpoint(
            "run-001",
            "reconstruction",
        )
        assert checkpoint is not None
        assert checkpoint.attempt_count == 2
