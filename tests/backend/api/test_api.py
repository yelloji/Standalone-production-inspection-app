"""Local API lifecycle, typed resources, commands, events, and safety tests."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api.commands import RunCommandDispatcher
from backend.api.events import BoundedEventBroker
from backend.api.routes import ApiServices
from backend.app.main import create_app
from backend.database.engine import transaction
from backend.database.records import RunStageCheckpointMetadata
from backend.database.repositories import MetadataRepository
from tests.backend.database.factories import NOW, artifact, model_bundle, pipeline_snapshot


def _seed_configuration(session_factory: sessionmaker[Session]) -> None:
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        repository.add_model_bundle(model_bundle())
        repository.add_pipeline_snapshot(pipeline_snapshot())


def _run_request() -> dict[str, object]:
    return {
        "run_id": "run-001",
        "acquisition_id": "acquisition-001",
        "pipeline_snapshot_id": "pipeline-upper-r1",
        "source": "offline",
        "side": "upper",
    }


def test_typed_resources_and_nonblocking_run_commands(
    session_factory: sessionmaker[Session],
) -> None:
    _seed_configuration(session_factory)
    events = BoundedEventBroker(maximum_events=20)
    started = threading.Event()
    release = threading.Event()
    cancelled: list[str] = []

    def execute_run(run_id: str) -> None:
        assert run_id == "run-001"
        started.set()
        assert release.wait(timeout=5)

    dispatcher = RunCommandDispatcher(
        execute_run=execute_run,
        cancel_run=cancelled.append,
        events=events,
        maximum_pending_runs=2,
    )
    services = ApiServices(
        session_factory=session_factory,
        commands=dispatcher,
        events=events,
    )

    with TestClient(create_app(services)) as client:
        readiness = client.get("/api/v1/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "ready"

        models = client.get("/api/v1/models")
        pipelines = client.get("/api/v1/pipelines")
        assert models.status_code == 200
        assert models.json()[0]["model_bundle_id"] == "model-v1"
        assert pipelines.status_code == 200
        assert pipelines.json()[0]["pipeline_snapshot_id"] == "pipeline-upper-r1"

        created = client.post("/api/v1/runs", json=_run_request())
        assert created.status_code == 201
        assert created.json()["status"] == "created"
        assert client.post("/api/v1/runs", json=_run_request()).status_code == 409

        accepted = client.post("/api/v1/runs/run-001/start")
        assert accepted.status_code == 202
        assert accepted.json() == {
            "run_id": "run-001",
            "command": "start",
            "accepted": True,
        }
        assert started.wait(timeout=2)
        assert client.post("/api/v1/runs/run-001/start").status_code == 409

        cancel = client.post("/api/v1/runs/run-001/cancel")
        assert cancel.status_code == 202
        assert cancelled == ["run-001"]
        release.set()

        deadline = time.monotonic() + 2
        event_types: list[str] = []
        while time.monotonic() < deadline:
            response = client.get("/api/v1/events")
            event_types = [event["event_type"] for event in response.json()["events"]]
            if "run_completed" in event_types:
                break
            time.sleep(0.01)
        assert event_types == [
            "run_created",
            "run_started",
            "run_cancel_requested",
            "run_completed",
        ]

        with transaction(session_factory) as session:
            repository = MetadataRepository(session)
            repository.add_artifact(artifact())
            repository.put_stage_checkpoint(
                RunStageCheckpointMetadata(
                    run_id="run-001",
                    stage_name="reconstruction",
                    status="completed",
                    attempt_count=1,
                    evidence_path="completed/run-001/reconstruction.json",
                    evidence_sha256="b" * 64,
                    failure_code=None,
                    updated_at=NOW,
                )
            )

        detail = client.get("/api/v1/runs/run-001")
        artifacts = client.get("/api/v1/runs/run-001/artifacts")
        runs = client.get("/api/v1/runs")
        assert detail.status_code == 200
        assert detail.json()["checkpoints"][0]["stage_name"] == "reconstruction"
        assert detail.json()["artifacts"][0]["artifact_id"] == "artifact-001"
        assert artifacts.json()[0]["relative_path"].endswith("artifact-001.tif")
        assert runs.json()[0]["run_id"] == "run-001"


def test_unconfigured_services_report_not_ready_and_return_503() -> None:
    with TestClient(create_app()) as client:
        readiness = client.get("/api/v1/readiness")
        models = client.get("/api/v1/models")

    assert readiness.status_code == 200
    assert readiness.json() == {
        "status": "not_ready",
        "components": {
            "database": "not_ready",
            "run_commands": "not_ready",
            "events": "ready",
        },
    }
    assert models.status_code == 503


def test_unknown_resources_invalid_requests_and_terminal_commands_are_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    _seed_configuration(session_factory)
    events = BoundedEventBroker()
    dispatcher = RunCommandDispatcher(
        execute_run=lambda _: None,
        cancel_run=lambda _: None,
        events=events,
    )
    with TestClient(
        create_app(
            ApiServices(
                session_factory=session_factory,
                commands=dispatcher,
                events=events,
            )
        )
    ) as client:
        assert client.get("/api/v1/runs/missing").status_code == 404
        assert client.get("/api/v1/runs/missing/artifacts").status_code == 404
        assert client.post("/api/v1/runs/missing/start").status_code == 404
        assert client.get("/api/v1/models?limit=0").status_code == 422
        malformed = _run_request()
        malformed["side"] = "invalid"
        assert client.post("/api/v1/runs", json=malformed).status_code == 422
        unknown_pipeline = _run_request()
        unknown_pipeline["run_id"] = "run-002"
        unknown_pipeline["pipeline_snapshot_id"] = "missing"
        assert client.post("/api/v1/runs", json=unknown_pipeline).status_code == 404


def test_event_buffer_is_bounded_and_reports_sequence_gap() -> None:
    events = BoundedEventBroker(maximum_events=10)
    for index in range(15):
        events.publish(
            event_type="stage_progress",
            run_id="run-001",
            stage="inference",
            progress_current=index + 1,
            progress_total=15,
        )

    batch = events.read(after_sequence=1, limit=3)

    assert batch.gap_detected
    assert [event.sequence for event in batch.events] == [6, 7, 8]
    assert batch.latest_sequence == 15


def test_untrusted_host_is_rejected() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health", headers={"host": "external.example"})

    assert response.status_code == 400
